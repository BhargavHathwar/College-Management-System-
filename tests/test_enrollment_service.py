"""
Unit and Integration Tests for Enrollment & Saga Service (Member 4).
Tests:
1. Circuit Breaker State Machine (CLOSED -> OPEN -> HALF-OPEN -> CLOSED)
2. Saga Coordinator Happy Path (Validate -> Reserve -> Pay -> Create)
3. Saga Failure and Automatic Compensation (Fee fails -> Seat released)
4. Circuit Breaker protection during service failure
5. Database Isolation and schema verification
6. Attendance marking and queries
"""

import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Add enrollment_service directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENROLLMENT_DIR = os.path.join(BASE_DIR, "enrollment_service")
sys.path.insert(0, ENROLLMENT_DIR)

from circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
import database
from saga import EnrollmentSagaCoordinator
import app as enrollment_app


class TestCircuitBreaker(unittest.TestCase):
    """Test Circuit Breaker states and transitions."""

    def setUp(self):
        self.cb = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=0.2)

    def test_initial_state_is_closed(self):
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_CLOSED)
        allowed, _ = self.cb.can_execute()
        self.assertTrue(allowed)
        self.assertEqual(self.cb.failure_count, 0)

    def test_transitions_to_open_after_threshold(self):
        self.cb.record_failure("Err 1")
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_CLOSED)
        self.cb.record_failure("Err 2")
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_CLOSED)
        self.cb.record_failure("Err 3")
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_OPEN)

        # Requests should now be rejected immediately
        allowed, msg = self.cb.can_execute()
        self.assertFalse(allowed)
        self.assertIn("OPEN", msg)

    def test_transitions_to_half_open_after_timeout(self):
        self.cb.trip("Force trip")
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_OPEN)

        # Wait for recovery timeout (0.2s)
        time.sleep(0.25)
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_HALF_OPEN)
        allowed, _ = self.cb.can_execute()
        self.assertTrue(allowed)

    def test_half_open_success_recovers_to_closed(self):
        self.cb.trip()
        time.sleep(0.25)
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_HALF_OPEN)

        self.cb.record_success()
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_CLOSED)
        self.assertEqual(self.cb.failure_count, 0)

    def test_half_open_failure_returns_to_open(self):
        self.cb.trip()
        time.sleep(0.25)
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_HALF_OPEN)

        self.cb.record_failure("Probe failed")
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_OPEN)

    def test_manual_reset(self):
        self.cb.trip()
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_OPEN)
        self.cb.reset()
        self.assertEqual(self.cb.state, CircuitBreaker.STATE_CLOSED)
        self.assertEqual(self.cb.failure_count, 0)


class TestDatabaseAndIsolation(unittest.TestCase):
    """Test enrollment database setup and isolation."""

    def setUp(self):
        database.init_db()

    def test_tables_exist(self):
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        self.assertIn("enrollments", tables)
        self.assertIn("saga_logs", tables)
        self.assertIn("attendance", tables)


class TestSagaCoordinator(unittest.TestCase):
    """Test distributed transaction and compensation logic."""

    def setUp(self):
        database.init_db()
        self.student_cb = CircuitBreaker("student_service", failure_threshold=3, recovery_timeout=1.0)
        self.course_cb = CircuitBreaker("course_service", failure_threshold=3, recovery_timeout=1.0)
        self.fee_cb = CircuitBreaker("fee_service", failure_threshold=3, recovery_timeout=1.0)

        def mock_service_url(service_name):
            return f"http://mock-{service_name}"

        self.coordinator = EnrollmentSagaCoordinator(
            self.student_cb,
            self.course_cb,
            self.fee_cb,
            mock_service_url
        )

    @patch("requests.post")
    @patch("requests.get")
    def test_successful_enrollment_saga(self, mock_get, mock_post):
        # 1. Student check succeeds
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": 1, "name": "Alice"})

        # 2. Course reserve succeeds
        mock_reserve = MagicMock(status_code=200, json=lambda: {"message": "Reserved", "course_id": 101, "available_seats": 29})
        # 3. Fee payment succeeds
        mock_pay = MagicMock(status_code=200, json=lambda: {"status": "PAID", "payment_id": 999, "amount": 1500.0})

        mock_post.side_effect = [mock_reserve, mock_pay]

        resp, code = self.coordinator.execute_enrollment(student_id=1, course_id=101, fee_amount=1500.0)

        self.assertEqual(code, 201)
        self.assertEqual(resp["status"], "COMPLETED")
        self.assertEqual(resp["payment_id"], 999)
        self.assertIn("saga_id", resp)

    @patch("requests.post")
    @patch("requests.get")
    def test_saga_failure_triggers_compensation(self, mock_get, mock_post):
        # 1. Student check succeeds
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": 1, "name": "Alice"})

        # 2. Course reserve succeeds
        mock_reserve = MagicMock(status_code=200, json=lambda: {"message": "Seat reserved"})
        # 3. Fee payment FAILS (insufficient funds)
        mock_fee_fail = MagicMock(
            status_code=400,
            json=lambda: {"status": "FAILED", "error": "Insufficient funds in student account"},
            text='{"status": "FAILED", "error": "Insufficient funds in student account"}'
        )
        # 4. Compensating action: Course release
        mock_release = MagicMock(status_code=200, json=lambda: {"message": "Seat released"})

        mock_post.side_effect = [mock_reserve, mock_fee_fail, mock_release]

        resp, code = self.coordinator.execute_enrollment(student_id=1, course_id=101, fee_amount=99999.0)

        self.assertEqual(code, 400)
        self.assertEqual(resp["status"], "FAILED")
        self.assertIn("Compensating action executed: Seat released.", resp["error"])
        self.assertIn("Insufficient funds", resp["reason"])
        self.assertTrue(resp["compensation"]["seat_released"])

        # Verify that course release endpoint was indeed called (compensating action)
        self.assertEqual(mock_post.call_count, 3)
        last_call_url = mock_post.call_args_list[2][0][0]
        self.assertIn("/api/v1/courses/101/release", last_call_url)

    @patch("requests.get")
    def test_circuit_breaker_open_blocks_execution(self, mock_get):
        self.student_cb.trip("Manually tripped")

        resp, code = self.coordinator.execute_enrollment(student_id=1, course_id=101, fee_amount=1000.0)
        self.assertEqual(code, 503)
        self.assertEqual(resp["status"], "FAILED")
        self.assertIn("Circuit Breaker Active", resp["error"])
        mock_get.assert_not_called()


class TestFlaskEndpoints(unittest.TestCase):
    """Test Flask REST APIs."""

    def setUp(self):
        database.init_db()
        self.client = enrollment_app.app.test_client()

    def test_health_and_home(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "UP")

        res_home = self.client.get("/")
        self.assertEqual(res_home.status_code, 200)
        self.assertIn("features", res_home.get_json())

    def test_circuit_status_endpoint(self):
        res = self.client.get("/circuit-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("student_service_circuit", data)
        self.assertIn("course_service_circuit", data)
        self.assertIn("fee_service_circuit", data)
        self.assertEqual(data["fee_service_circuit"]["state"], "CLOSED")

    def test_circuit_breaker_controls(self):
        # Trip
        res_trip = self.client.post("/circuit-breaker/trip/fee_service")
        self.assertEqual(res_trip.status_code, 200)

        res_status = self.client.get("/circuit-status")
        self.assertEqual(res_status.get_json()["fee_service_circuit"]["state"], "OPEN")

        # Reset
        res_reset = self.client.post("/circuit-breaker/reset")
        self.assertEqual(res_reset.status_code, 200)

        res_status2 = self.client.get("/circuit-status")
        self.assertEqual(res_status2.get_json()["fee_service_circuit"]["state"], "CLOSED")

    def test_attendance_endpoints(self):
        mark_res = self.client.post(
            "/api/v1/attendance/mark",
            json={
                "student_id": 99,
                "course_id": 101,
                "date": "2026-10-09",
                "status": "PRESENT",
                "notes": "Testing attendance"
            }
        )
        self.assertEqual(mark_res.status_code, 201)

        get_res = self.client.get("/api/v1/attendance/99")
        self.assertEqual(get_res.status_code, 200)
        records = get_res.get_json()
        self.assertTrue(len(records) >= 1)
        self.assertEqual(records[0]["student_id"], 99)
        self.assertEqual(records[0]["status"], "PRESENT")


if __name__ == "__main__":
    unittest.main()
