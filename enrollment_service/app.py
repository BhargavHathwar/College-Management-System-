"""
Enrollment & Saga Service (Member 4 - Resilience / Transaction Developer).

Responsibilities:
- Distributed Saga Transaction Management (Enrollment Orchestrator)
- Automatic Compensating Transactions (Release Seat / Refund Payment)
- Circuit Breaker Pattern (CLOSED, OPEN, HALF-OPEN states)
- Service Discovery Integration with Service Registry
- Database-per-Service Architecture (enrollment.db)
- Attendance Tracking and Management
"""

import os
import sys
import requests
from flask import Flask, request, jsonify

# Ensure local imports work when executing from root or inside service directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from database import init_db, get_db
from circuit_breaker import CircuitBreaker
from saga import EnrollmentSagaCoordinator

app = Flask(__name__)

# Service configuration
SERVICE_NAME = "enrollment_service"
SERVICE_PORT = int(os.environ.get("PORT", 5005))
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://127.0.0.1:5001")

# Default service URLs (fallbacks if registry is not active)
DEFAULT_SERVICE_URLS = {
    "student_service": os.environ.get("STUDENT_SERVICE_URL", "http://127.0.0.1:5002"),
    "course_service": os.environ.get("COURSE_SERVICE_URL", "http://127.0.0.1:5003"),
    "fee_service": os.environ.get("FEE_SERVICE_URL", "http://127.0.0.1:5004"),
}

# Alternate port fallbacks (e.g., student at 5003, course at 5004, fee at 5005)
ALT_SERVICE_URLS = {
    "student_service": "http://127.0.0.1:5003",
    "course_service": "http://127.0.0.1:5004",
    "fee_service": "http://127.0.0.1:5005",
}

# Cache for discovered service URLs
discovered_cache = {}

# Initialize Circuit Breakers for each downstream dependency
student_circuit = CircuitBreaker("student_service", failure_threshold=3, recovery_timeout=10.0)
course_circuit = CircuitBreaker("course_service", failure_threshold=3, recovery_timeout=10.0)
fee_circuit = CircuitBreaker("fee_service", failure_threshold=3, recovery_timeout=10.0)


def discover_service(service_name: str) -> str:
    """
    Dynamically discover service URL via Service Registry,
    with smart fallback to known ports.
    """
    # 1. Try Primary Registry URL (e.g., port 5001)
    for reg_url in [REGISTRY_URL, "http://127.0.0.1:5002"]:
        try:
            resp = requests.get(f"{reg_url}/discover/{service_name}", timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("url")
                if url:
                    discovered_cache[service_name] = url
                    return url
        except requests.exceptions.RequestException:
            pass

    # 2. Return cached value if previously discovered
    if service_name in discovered_cache:
        return discovered_cache[service_name]

    # 3. Test primary default vs alt fallback port
    default_url = DEFAULT_SERVICE_URLS.get(service_name, "http://127.0.0.1:5000")
    alt_url = ALT_SERVICE_URLS.get(service_name)
    if alt_url:
        try:
            # Quick check if default URL is alive
            requests.get(default_url, timeout=0.8)
            return default_url
        except requests.exceptions.RequestException:
            try:
                # If alt URL is alive, use alt URL
                requests.get(alt_url, timeout=0.8)
                return alt_url
            except requests.exceptions.RequestException:
                pass

    return default_url


# Initialize Saga Coordinator
saga_coordinator = EnrollmentSagaCoordinator(
    student_circuit=student_circuit,
    course_circuit=course_circuit,
    fee_circuit=fee_circuit,
    get_service_url_fn=discover_service
)


def register_with_registry():
    """Register enrollment service with the Service Registry on startup."""
    service_urls = [
        {"name": SERVICE_NAME, "url": f"http://127.0.0.1:{SERVICE_PORT}"},
        {"name": "enrollment", "url": f"http://127.0.0.1:{SERVICE_PORT}"},
        {"name": "enrollments", "url": f"http://127.0.0.1:{SERVICE_PORT}"},
        {"name": "enroll", "url": f"http://127.0.0.1:{SERVICE_PORT}"}
    ]
    for reg_url in [REGISTRY_URL, "http://127.0.0.1:5002"]:
        for item in service_urls:
            try:
                requests.post(f"{reg_url}/register", json=item, timeout=2)
                print(f"Registered {item['name']} with registry at {reg_url}")
            except requests.exceptions.RequestException:
                pass


# =========================================================
# SYSTEM & HEALTH ENDPOINTS
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "Enrollment & Saga Service",
        "role": "Member 4 - Resilience / Transaction Developer",
        "status": "running",
        "port": SERVICE_PORT,
        "database": "enrollment.db",
        "features": [
            "Saga Pattern Orchestration",
            "Automatic Compensating Actions",
            "Circuit Breaker (CLOSED, OPEN, HALF-OPEN)",
            "Dynamic Service Discovery",
            "Database-per-Service Isolation",
            "Attendance Tracking"
        ]
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "Enrollment & Saga Service",
        "status": "UP",
        "port": SERVICE_PORT
    }), 200


# =========================================================
# CIRCUIT BREAKER STATUS & CONTROLS
# =========================================================

@app.route("/circuit-status", methods=["GET"])
def circuit_status():
    """
    Returns the current state of all downstream circuit breakers.
    Matches the schema documented in the project specification.
    """
    return jsonify({
        "student_service_circuit": student_circuit.get_status(),
        "course_service_circuit": course_circuit.get_status(),
        "fee_service_circuit": fee_circuit.get_status()
    }), 200


@app.route("/circuit-breaker/reset", methods=["POST"])
def reset_circuit_breaker():
    """Reset all circuit breakers back to CLOSED for demonstration testing."""
    student_circuit.reset()
    course_circuit.reset()
    fee_circuit.reset()
    return jsonify({
        "message": "All circuit breakers reset to CLOSED state",
        "status": {
            "student_service_circuit": student_circuit.state,
            "course_service_circuit": course_circuit.state,
            "fee_service_circuit": fee_circuit.state
        }
    }), 200


@app.route("/circuit-breaker/trip/<service_name>", methods=["POST"])
def trip_circuit_breaker(service_name):
    """Manually trip a circuit breaker to OPEN state for failure scenario testing."""
    circuits = {
        "student_service": student_circuit,
        "course_service": course_circuit,
        "fee_service": fee_circuit
    }
    if service_name not in circuits:
        return jsonify({"error": f"Unknown service '{service_name}'. Valid: {list(circuits.keys())}"}), 400

    circuits[service_name].trip(f"Manually tripped for testing {service_name}")
    return jsonify({
        "message": f"Circuit breaker for {service_name} tripped to OPEN",
        "circuit": circuits[service_name].get_status()
    }), 200


# =========================================================
# ENROLLMENT & SAGA ENDPOINTS
# =========================================================

@app.route("/api/v1/enroll", methods=["POST"])
@app.route("/enroll", methods=["POST"])
def enroll_student():
    """
    Executes the distributed Saga transaction:
    1. Validate Student -> 2. Reserve Seat -> 3. Pay Fee -> 4. Record Enrollment
    With compensation: If step 3 fails, seat is released automatically.
    """
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    course_id = data.get("course_id")
    # Accept either 'fee' or 'amount'
    fee_amount = data.get("fee", data.get("amount"))

    if student_id is None or course_id is None:
        return jsonify({"error": "student_id and course_id are required"}), 400

    if fee_amount is None:
        return jsonify({"error": "fee is required"}), 400

    try:
        student_id = int(student_id)
        course_id = int(course_id)
        fee_amount = float(fee_amount)
    except (ValueError, TypeError):
        return jsonify({"error": "student_id, course_id, and fee must be valid numbers"}), 400

    if fee_amount <= 0:
        return jsonify({"error": "fee amount must be greater than 0"}), 400

    response_data, status_code = saga_coordinator.execute_enrollment(
        student_id=student_id,
        course_id=course_id,
        fee_amount=fee_amount
    )
    return jsonify(response_data), status_code


@app.route("/api/v1/enrollments/<int:student_id>", methods=["GET"])
@app.route("/enrollments/<int:student_id>", methods=["GET"])
def get_student_enrollments(student_id):
    """Retrieve all completed enrollments for a specific student."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT * FROM enrollments
        WHERE student_id = ?
        ORDER BY created_at DESC
        """,
        (student_id,)
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200


@app.route("/api/v1/enrollments", methods=["GET"])
@app.route("/enrollments", methods=["GET"])
def get_all_enrollments():
    """Retrieve all enrollments across students."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM enrollments ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200


@app.route("/api/v1/enrollments/detail/<int:enrollment_id>", methods=["GET"])
@app.route("/enrollments/detail/<int:enrollment_id>", methods=["GET"])
def get_enrollment_detail(enrollment_id):
    """Retrieve specific enrollment record by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM enrollments WHERE id = ?",
        (enrollment_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Enrollment not found"}), 404

    return jsonify(dict(row)), 200


# =========================================================
# ATTENDANCE ENDPOINTS
# =========================================================

@app.route("/api/v1/attendance/mark", methods=["POST"])
@app.route("/attendance/mark", methods=["POST"])
def mark_attendance():
    """
    Mark student attendance for a course session.
    Payload: {"student_id": 1, "course_id": 101, "date": "2026-10-09", "status": "PRESENT", "notes": ""}
    """
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    course_id = data.get("course_id")
    date_val = data.get("date")
    status_val = data.get("status", "PRESENT").upper()
    notes = data.get("notes", "")

    if student_id is None or course_id is None or not date_val:
        return jsonify({"error": "student_id, course_id, and date are required"}), 400

    if status_val not in ["PRESENT", "ABSENT", "EXCUSED", "LATE"]:
        return jsonify({"error": "status must be one of: PRESENT, ABSENT, EXCUSED, LATE"}), 400

    conn = get_db()
    cursor = conn.execute(
        """
        INSERT INTO attendance (student_id, course_id, date, status, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (student_id, course_id, date_val, status_val, notes)
    )
    conn.commit()
    att_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Attendance marked successfully",
        "attendance_id": att_id,
        "student_id": student_id,
        "course_id": course_id,
        "date": date_val,
        "status": status_val
    }), 201


@app.route("/api/v1/attendance/<int:student_id>", methods=["GET"])
@app.route("/attendance/<int:student_id>", methods=["GET"])
def get_student_attendance(student_id):
    """Retrieve all attendance records for a specific student."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC",
        (student_id,)
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200


@app.route("/api/v1/attendance/course/<int:course_id>", methods=["GET"])
@app.route("/attendance/course/<int:course_id>", methods=["GET"])
def get_course_attendance(course_id):
    """Retrieve all attendance records for a specific course."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM attendance WHERE course_id = ? ORDER BY date DESC, student_id ASC",
        (course_id,)
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200


# =========================================================
# SAGA AUDIT & LOGGING ENDPOINTS
# =========================================================

@app.route("/api/v1/saga/logs", methods=["GET"])
@app.route("/saga/logs", methods=["GET"])
def get_saga_logs():
    """Retrieve recent Saga transaction execution and compensation logs."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM saga_logs ORDER BY timestamp DESC LIMIT 100"
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200


@app.route("/api/v1/saga/logs/<saga_id>", methods=["GET"])
@app.route("/saga/logs/<saga_id>", methods=["GET"])
def get_saga_details(saga_id):
    """Retrieve full step-by-step audit trail for a specific Saga transaction."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM saga_logs WHERE saga_id = ? ORDER BY id ASC",
        (saga_id,)
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200


# =========================================================
# START SERVICE
# =========================================================

if __name__ == "__main__":
    init_db()
    register_with_registry()
    print(f"Starting Enrollment & Saga Service on port {SERVICE_PORT}...")
    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=True)
