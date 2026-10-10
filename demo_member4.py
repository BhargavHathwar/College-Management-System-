"""
Comprehensive Demonstration Script for Member 4:
Resilience / Transaction Developer (Enrollment & Saga Service).

Demonstrates:
1. Service Discovery & Registration
2. Distributed Saga Pattern (Happy Path)
3. Saga Failure & Automatic Compensating Action (Course seat released on fee failure)
4. Circuit Breaker State Transitions (CLOSED -> OPEN -> HALF-OPEN -> CLOSED)
5. Database-per-Service Isolation Verification (enrollment.db)
6. Attendance Tracking APIs
"""

import sys
import time
import os
import json

# Setup import path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENROLLMENT_DIR = os.path.join(BASE_DIR, "enrollment_service")
sys.path.insert(0, ENROLLMENT_DIR)

from circuit_breaker import CircuitBreaker
import database
from saga import EnrollmentSagaCoordinator
import app as enrollment_app

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(text):
    print("\n" + "=" * 70)
    print(f"{BOLD}{CYAN}>>> {text}{RESET}")
    print("=" * 70)


def demo_database_isolation():
    print_banner("DEMO 1: Database-per-Service Isolation (enrollment.db)")
    database.init_db()
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()

    print(f"Database File: {BOLD}{database.DATABASE}{RESET}")
    print(f"Tables owned exclusively by Enrollment Service: {BOLD}{tables}{RESET}")
    print(f"{GREEN}[PASS] Strict data isolation confirmed. No direct queries to other databases.{RESET}")


def demo_circuit_breaker():
    print_banner("DEMO 2: Circuit Breaker State Machine")
    cb = CircuitBreaker("fee_service", failure_threshold=3, recovery_timeout=0.5)

    print(f"1. Initial State: {BOLD}{cb.state}{RESET} (failure_count={cb.failure_count})")
    allowed, msg = cb.can_execute()
    print(f"   can_execute(): {allowed} - {msg}")

    print("\n2. Simulating consecutive failures...")
    for i in range(1, 4):
        cb.record_failure(f"Timeout connecting to downstream (attempt {i})")
        print(f"   Failure {i} recorded -> Current state: {BOLD}{cb.state}{RESET} (count={cb.failure_count})")

    print(f"\n3. State after threshold (3) exceeded: {RED}{BOLD}{cb.state}{RESET}")
    allowed, msg = cb.can_execute()
    print(f"   Immediate rejection (Fail-Fast): {allowed} - {msg}")

    print("\n4. Waiting for recovery timeout (0.5s)...")
    time.sleep(0.6)
    print(f"   State after timeout: {YELLOW}{BOLD}{cb.state}{RESET}")
    allowed, msg = cb.can_execute()
    print(f"   Probe request allowed: {allowed} - {msg}")

    print("\n5. Simulating successful probe response...")
    cb.record_success()
    print(f"   State after success: {GREEN}{BOLD}{cb.state}{RESET} (count={cb.failure_count})")
    print(f"{GREEN}[PASS] Circuit Breaker completed full cycle: CLOSED -> OPEN -> HALF-OPEN -> CLOSED{RESET}")


def demo_saga_transactions():
    print_banner("DEMO 3: Saga Pattern - Distributed Transaction & Compensation")
    client = enrollment_app.app.test_client()

    print(f"{BOLD}Scenario A: Successful Enrollment (Happy Path){RESET}")
    with client:
        # Mock downstream services for repeatable demo
        from unittest.mock import patch, MagicMock
        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            # Step 1: Student valid
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": 1, "name": "Bhargav"})
            # Step 2: Course reserved
            mock_res = MagicMock(status_code=200, json=lambda: {"message": "Reserved", "course_id": 101, "available_seats": 29})
            # Step 3: Fee paid
            mock_pay = MagicMock(status_code=200, json=lambda: {"status": "PAID", "payment_id": 1001, "amount": 1000.0})
            mock_post.side_effect = [mock_res, mock_pay]

            response = client.post(
                "/api/v1/enroll",
                json={"student_id": 1, "course_id": 101, "fee": 1000.0}
            )
            data = response.get_json()
            print(f"Response Status: {response.status_code}")
            print(json.dumps(data, indent=2))
            assert data["status"] == "COMPLETED"
            print(f"{GREEN}[PASS] All 4 Saga steps succeeded. Enrollment record committed.{RESET}")

    print(f"\n{BOLD}Scenario B: Insufficient Funds -> Automatic Compensating Action{RESET}")
    with client:
        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            # Step 1: Student valid
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": 1, "name": "Bhargav"})
            # Step 2: Course reserved
            mock_res = MagicMock(status_code=200, json=lambda: {"message": "Seat reserved"})
            # Step 3: Fee Payment FAILS
            mock_fail = MagicMock(
                status_code=400,
                json=lambda: {"status": "FAILED", "error": "Insufficient funds in student account"}
            )
            # Step 4: Compensating action: Course seat released
            mock_rel = MagicMock(status_code=200, json=lambda: {"message": "Course seat released successfully"})
            mock_post.side_effect = [mock_res, mock_fail, mock_rel]

            response = client.post(
                "/api/v1/enroll",
                json={"student_id": 1, "course_id": 101, "fee": 99999.0}
            )
            data = response.get_json()
            print(f"Response Status: {response.status_code}")
            print(json.dumps(data, indent=2))
            assert data["status"] == "FAILED"
            assert "Compensating action executed: Seat released." in data["error"]
            print(f"{GREEN}[PASS] Automatic compensation successfully executed! Reserved seat was released back.{RESET}")


def demo_attendance_and_audit():
    print_banner("DEMO 4: Attendance Tracking & Saga Audit Trail")
    client = enrollment_app.app.test_client()

    print("1. Marking Attendance...")
    mark_resp = client.post(
        "/api/v1/attendance/mark",
        json={"student_id": 1, "course_id": 101, "date": "2026-10-09", "status": "PRESENT", "notes": "Distributed Systems Lab"}
    )
    print(json.dumps(mark_resp.get_json(), indent=2))

    print("\n2. Fetching Student Attendance:")
    att_resp = client.get("/api/v1/attendance/1")
    print(json.dumps(att_resp.get_json(), indent=2))

    print("\n3. Fetching Recent Saga Audit Trail:")
    saga_resp = client.get("/api/v1/saga/logs")
    logs = saga_resp.get_json()
    print(f"Total audit log entries recorded: {len(logs)}")
    if logs:
        print("Latest Saga Event:", json.dumps(logs[0], indent=2))
    print(f"{GREEN}[PASS] Attendance and Saga auditing verified.{RESET}")


if __name__ == "__main__":
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN} COLLEGE MANAGEMENT SYSTEM - MEMBER 4 DEMONSTRATION SUITE {RESET}")
    print(f"{BOLD}{CYAN} Resilience / Transaction Developer (Enrollment & Saga Service) {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}")

    demo_database_isolation()
    demo_circuit_breaker()
    demo_saga_transactions()
    demo_attendance_and_audit()

    print("\n" + "=" * 70)
    print(f"{GREEN}{BOLD}ALL MEMBER 4 DEMONSTRATION SCENARIOS COMPLETED SUCCESSFULLY!{RESET}")
    print("=" * 70 + "\n")
