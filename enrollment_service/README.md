# Enrollment & Saga Service (Member 4)

**Role:** Resilience / Transaction Developer  
**Port:** `5005` (configurable via `PORT` environment variable)  
**Database:** `enrollment.db` (SQLite, strict Database-per-Service isolation)

---

## 📋 Responsibilities

As assigned in the project specification:
1. **Saga Coordinator:** Implements distributed transaction management across Student, Course, and Fee services.
2. **Compensating Actions:** Automatically releases reserved course seats and rolls back transactions if downstream operations (e.g. fee payment) fail.
3. **Circuit Breaker Pattern:** Implements `CLOSED`, `OPEN`, and `HALF-OPEN` states with configurable failure thresholds and recovery timeouts to protect the system against cascading failures.
4. **Dynamic Service Discovery:** Dynamically locates dependent services via the Service Registry and registers itself on startup.
5. **Database Isolation:** Owns and manages `enrollment.db`. Never accesses `user.db`, `course.db`, `fee.db`, or `exam.db`.
6. **Attendance Management:** Records and tracks student course attendance.

---

## 🏗️ Architecture & Interaction Flow

```text
               ┌──────────────────────────────────────────────┐
               │         Enrollment & Saga Service            │
               │                 (Port 5005)                  │
               │                                              │
               │   ┌──────────────────────────────────────┐   │
               │   │      Circuit Breaker Protection      │   │
               │   │     • Student   • Course   • Fee     │   │
               │   └──────────────────┬───────────────────┘   │
               │                      │                       │
               │   ┌──────────────────┴───────────────────┐   │
               │   │           Saga Coordinator           │   │
               │   └──────────────────┬───────────────────┘   │
               │                      │                       │
               │                enrollment.db                 │
               └──────────────────────┼───────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
      Student Service          Course Service            Fee Service
        (Port 5002)              (Port 5003)             (Port 5004)
     GET /students/<id>      POST /courses/<id>/reserve   POST /fees/pay
                             POST /courses/<id>/release   POST /fees/refund
```

---

## 🔁 Distributed Saga Workflow

### Happy Path (Successful Enrollment)
```text
Client Request: POST /api/v1/enroll
      │
      ▼
1. Validate Student (Student Service)  ─────────► [200 OK: Student Validated]
      │
      ▼
2. Reserve Course Seat (Course Service) ────────► [200 OK: Seat Reserved]
      │
      ▼
3. Process Fee Payment (Fee Service)   ─────────► [200 OK: Payment Processed]
      │
      ▼
4. Record in enrollment.db             ─────────► [Created: Status COMPLETED]
      │
      ▼
Client Response: 201 Created {"status": "COMPLETED", ...}
```

### Failure Path (Compensating Transaction)
```text
Client Request: POST /api/v1/enroll
      │
      ▼
1. Validate Student (Student Service)  ─────────► [200 OK]
      │
      ▼
2. Reserve Course Seat (Course Service) ────────► [200 OK: Seat Reserved]
      │
      ▼
3. Process Fee Payment (Fee Service)   ─────────► [400 FAILED: Insufficient Funds]
      │
      ▼
4. TRIGGER COMPENSATION ───────────────► POST /api/v1/courses/<id>/release
      │                                  (Seat returned to available pool)
      ▼
5. Log Rollback in saga_logs           ─────────► Status: COMPENSATED
      │
      ▼
Client Response: 400 Bad Request
{
  "status": "FAILED",
  "error": "Saga Failed. Compensating action executed: Seat released.",
  "reason": "Insufficient funds in student account"
}
```

---

## 🛡️ Circuit Breaker State Machine

```text
              ┌───────────────┐
              │    CLOSED     │◄───────────────────┐
              │(Normal calls) │                    │
              └───────┬───────┘                    │
                      │                            │
             Failure Threshold (3)                 │ Probe Success
                      │                            │
                      ▼                            │
              ┌───────────────┐                    │
              │     OPEN      │                    │
              │  (Fail-fast)  │                    │
              └───────┬───────┘                    │
                      │                            │
             Recovery Timeout (10s)                │
                      │                            │
                      ▼                            │
              ┌───────────────┐                    │
              │   HALF-OPEN   │────────────────────┘
              │ (Test probe)  │
              └───────┬───────┘
                      │ Probe Failure
                      ▼
                 (Back to OPEN)
```

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service information, role, and capabilities |
| `GET` | `/health` | Service health status |
| `GET` | `/circuit-status` | State of all circuit breakers (`CLOSED`, `OPEN`, `HALF-OPEN`) |
| `POST` | `/circuit-breaker/reset` | Reset all circuit breakers to `CLOSED` (testing/demo) |
| `POST` | `/circuit-breaker/trip/<service>` | Trip a circuit breaker to `OPEN` (testing/demo) |
| `POST` | `/api/v1/enroll` | Execute distributed Saga enrollment transaction |
| `GET` | `/api/v1/enrollments/<student_id>` | List enrollments for a given student |
| `GET` | `/api/v1/enrollments` | List all enrollments |
| `GET` | `/api/v1/enrollments/detail/<id>` | View details of a specific enrollment |
| `POST` | `/api/v1/attendance/mark` | Record student attendance |
| `GET` | `/api/v1/attendance/<student_id>` | View student attendance history |
| `GET` | `/api/v1/attendance/course/<course_id>`| View course attendance history |
| `GET` | `/api/v1/saga/logs` | Audit trail of Saga executions and compensations |
| `GET` | `/api/v1/saga/logs/<saga_id>` | Full step-by-step history of a specific Saga |

---

## 🧪 Testing with cURL

### 1. Test Service Health & Circuit Status
```bash
curl http://127.0.0.1:5005/health
curl http://127.0.0.1:5005/circuit-status
```

### 2. Successful Enrollment (Saga Happy Path)
```bash
curl -X POST http://127.0.0.1:5005/api/v1/enroll \
  -H "Content-Type: application/json" \
  -d '{"student_id": 1, "course_id": 101, "fee": 1000.0}'
```

### 3. Saga Rollback & Compensation Test
```bash
curl -X POST http://127.0.0.1:5005/api/v1/enroll \
  -H "Content-Type: application/json" \
  -d '{"student_id": 1, "course_id": 101, "fee": 999999.0}'
```

### 4. Verify Circuit Breaker Trip
```bash
# Manually trip circuit breaker for demonstration
curl -X POST http://127.0.0.1:5005/circuit-breaker/trip/course_service

# Request fails fast without contacting course service
curl -X POST http://127.0.0.1:5005/api/v1/enroll \
  -H "Content-Type: application/json" \
  -d '{"student_id": 1, "course_id": 101, "fee": 1000.0}'

# Reset back to CLOSED
curl -X POST http://127.0.0.1:5005/circuit-breaker/reset
```

### 5. Mark and Check Attendance
```bash
curl -X POST http://127.0.0.1:5005/api/v1/attendance/mark \
  -H "Content-Type: application/json" \
  -d '{"student_id": 1, "course_id": 101, "date": "2026-10-09", "status": "PRESENT"}'

curl http://127.0.0.1:5005/api/v1/attendance/1
```
