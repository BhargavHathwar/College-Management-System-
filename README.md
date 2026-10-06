# College Management System — Microservices Architecture

A distributed **College Management System** built using **Python, Flask, SQLite, and REST APIs**, following a production-oriented **Microservices Architecture**.

The system is designed around independent domain services with **Database-per-Service**, **API Gateway**, **Dynamic Service Discovery**, **API Versioning**, **Circuit Breaker**, and **Saga-based distributed transaction management**.

The architecture focuses on service independence, fault tolerance, data isolation, and reliable inter-service communication.

---

## 🚀 Key Features

- 🧩 **Microservices Architecture**
- 🌐 **API Gateway** as a single entry point
- 🔎 **Dynamic Service Discovery**
- 🔄 **API Versioning** with `/v1` and `/v2`
- 🗄️ **Database-per-Service** architecture
- 🔐 **Strict Data Isolation**
- 🛡️ **Circuit Breaker** for fault tolerance
- 🔁 **Saga Pattern** for distributed transactions
- ↩️ **Automatic Compensating Actions**
- 👨‍🎓 Student & Faculty Management
- 📚 Course & Seat Management
- 💰 Fee & Billing Management
- 📝 Enrollment Management
- 📊 Examination & Grading
- 📄 GPA and Transcript Generation
- 🔌 RESTful APIs
- 🧪 cURL/Postman based testing

---

# 🏗️ System Architecture

```text
                         ┌──────────────────────┐
                         │        Client        │
                         │ Browser / Postman /  │
                         │        cURL          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │        API Gateway           │
                    │          Port 5000            │
                    │                              │
                    │ • Routing                   │
                    │ • API Versioning             │
                    │ • Single Entry Point         │
                    └──────────────┬───────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
                     ▼                           ▼
          ┌──────────────────┐       ┌────────────────────┐
          │ Service Registry │       │ Circuit Breaker    │
          │    Port 5001     │       │    Protection      │
          │                  │       └─────────┬──────────┘
          │ Service Discovery│                 │
          └──────────────────┘                 │
                                               │
       ┌───────────────────────────────────────┼─────────────────────┐
       │                 │                     │                     │
       ▼                 ▼                     ▼                     ▼
┌─────────────┐   ┌─────────────┐     ┌─────────────┐       ┌─────────────┐
│   Student   │   │   Course    │     │     Fee     │       │    Exam     │
│  & Faculty  │   │  Service    │     │   Service   │       │   Service   │
│ Port 5002   │   │ Port 5003   │     │ Port 5004   │       │ Port 5006   │
│             │   │             │     │             │       │             │
│  user.db    │   │ course.db   │     │  fee.db     │       │  exam.db    │
└─────────────┘   └─────────────┘     └─────────────┘       └─────────────┘
                           │                  │
                           │                  │
                           └────────┬─────────┘
                                    ▼
                         ┌────────────────────┐
                         │ Enrollment & Saga  │
                         │     Service        │
                         │     Port 5005      │
                         │                    │
                         │ • Saga Coordinator │
                         │ • Circuit Breaker  │
                         │ • Compensation     │
                         │ • enrollment.db    │
                         └────────────────────┘
```

---

# 🧩 Microservices

| Service | Port | Database | Responsibility |
|---|---:|---|---|
| API Gateway | `5000` | — | Routing, versioning, unified API entry point |
| Service Registry | `5001` | In-memory | Dynamic service registration & discovery |
| Student & Faculty | `5002` | `user.db` | Student and faculty management |
| Course & Academic | `5003` | `course.db` | Courses, seats and reservations |
| Fee & Billing | `5004` | `fee.db` | Student fees and payments |
| Enrollment & Saga | `5005` | `enrollment.db` | Enrollment orchestration & transactions |
| Exam & Grading | `5006` | `exam.db` | Grades, transcripts and GPA |

---

# 🔌 API Gateway

The API Gateway acts as the **single entry point** for external clients.

It hides the internal service topology and forwards requests to the appropriate microservice through dynamic service discovery.

### API Versioning

### Version 1

```http
/api/v1/<service>/<resource>
```

Provides standard resource-level API responses.

### Version 2

```http
/api/v2/students/<id>
```

Provides an aggregated response containing:

- Student profile
- Academic standing
- Portal notices

Example:

```bash
curl http://127.0.0.1:5000/api/v2/students/1
```

---

# 🔎 Service Discovery

The Service Registry maintains the active locations of all microservices.

Services register themselves when they start.

### Register Service

```http
POST /register
```

Example payload:

```json
{
  "name": "student_service",
  "url": "http://127.0.0.1:5002"
}
```

### Discover Service

```http
GET /discover/<service_name>
```

### View Registered Services

```http
GET /services
```

This eliminates the need for hardcoded service locations throughout the system.

---

# 🗄️ Database-per-Service

Each microservice owns its own SQLite database.

```text
student_faculty_service/
└── user.db

course_service/
└── course.db

fee_service/
└── fee.db

enrollment_service/
└── enrollment.db

exam_service/
└── exam.db
```

### Data Isolation Principle

A service does **not** directly access another service's database.

Instead, cross-service information is obtained through REST APIs.

```text
❌ Service A → Service B Database

✅ Service A → HTTP REST API → Service B
```

This keeps services independently deployable and prevents tight database coupling.

---

# 🔁 Saga Pattern

Enrollment is implemented as a distributed transaction using the **Saga Pattern**.

### Successful Enrollment

```text
Student Validation
       │
       ▼
Reserve Course Seat
       │
       ▼
Process Fee Payment
       │
       ▼
Create Enrollment
       │
       ▼
   COMPLETED
```

### Failure Scenario

If payment fails after the course seat has already been reserved:

```text
Student Validation
       │
       ▼
Reserve Course Seat
       │
       ▼
Fee Payment ❌
       │
       ▼
Compensating Action
       │
       ▼
Release Course Seat
       │
       ▼
   SAGA FAILED
```

This prevents partially completed enrollment transactions.

---

# 🛡️ Circuit Breaker

The Enrollment Service contains a Circuit Breaker protecting communication with dependent services.

The Circuit Breaker uses three states:

```text
       ┌──────────┐
       │  CLOSED  │
       └────┬─────┘
            │
       Failure Threshold
            │
            ▼
       ┌──────────┐
       │   OPEN   │
       └────┬─────┘
            │
       Recovery Timeout
            │
            ▼
      ┌────────────┐
      │ HALF-OPEN  │
      └─────┬──────┘
            │
       Successful Probe
            │
            ▼
       ┌──────────┐
       │  CLOSED  │
       └──────────┘
```

### States

| State | Behavior |
|---|---|
| `CLOSED` | Requests are allowed normally |
| `OPEN` | Requests fail immediately |
| `HALF-OPEN` | Allows a recovery probe |
| Success | Returns to `CLOSED` |
| Failure | Returns to `OPEN` |

This prevents repeated failures and reduces cascading failures between services.

---

# 📡 REST API Endpoints

## Student & Faculty Service — `5002`

```http
GET    /api/v1/students
GET    /api/v1/students/<id>
POST   /api/v1/students
PUT    /api/v1/students/<id>
DELETE /api/v1/students/<id>

GET    /api/v1/faculty/<id>
```

---

## Course & Academic Service — `5003`

```http
GET  /api/v1/courses/<id>

POST /api/v1/courses/<id>/reserve

POST /api/v1/courses/<id>/release
```

The `release` endpoint acts as a Saga compensating action when an enrollment transaction fails.

---

## Fee & Billing Service — `5004`

```http
GET  /api/v1/fees/<student_id>

POST /api/v1/fees/pay

POST /api/v1/fees/refund
```

---

## Enrollment & Saga Service — `5005`

```http
POST /api/v1/enroll

GET  /api/v1/enrollments/<student_id>

GET  /circuit-status
```

---

## Exam & Grading Service — `5006`

```http
POST /api/v1/grades/submit

GET /api/v1/grades/transcript/<student_id>
```

---

# 📁 Project Structure

```text
college-management-microservices/
│
├── api_gateway/
│   └── gateway.py
│
├── service_registry/
│   └── app.py
│
├── student_faculty_service/
│   ├── app.py
│   └── user.db
│
├── course_service/
│   ├── app.py
│   └── course.db
│
├── fee_service/
│   ├── app.py
│   └── fee.db
│
├── enrollment_service/
│   ├── app.py
│   └── enrollment.db
│
├── exam_service/
│   ├── app.py
│   └── exam.db
│
├── requirements.txt
└── README.md
```

---

# ⚙️ Technology Stack

### Backend

- Python
- Flask
- REST APIs

### Database

- SQLite
- Database-per-Service

### Architecture

- Microservices
- API Gateway
- Service Discovery
- Saga Pattern
- Circuit Breaker

### Testing

- cURL
- Postman

### Development

- Git
- GitHub
- VS Code

---

# 🚀 Getting Started

## Prerequisites

Make sure the following are installed:

- Python `3.10+`
- pip
- Git
- cURL or Postman

---

## 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/college-management-microservices.git

cd college-management-microservices
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

If a `requirements.txt` is not available:

```bash
pip install flask requests
```

---

# ▶️ Running the System

The services should be started in the following order.

### Terminal 1 — Service Registry

```bash
python service_registry/app.py
```

**Port:** `5001`

---

### Terminal 2 — Student & Faculty Service

```bash
python student_faculty_service/app.py
```

**Port:** `5002`

---

### Terminal 3 — Course Service

```bash
python course_service/app.py
```

**Port:** `5003`

---

### Terminal 4 — Fee Service

```bash
python fee_service/app.py
```

**Port:** `5004`

---

### Terminal 5 — Exam Service

```bash
python exam_service/app.py
```

**Port:** `5006`

---

### Terminal 6 — Enrollment Service

```bash
python enrollment_service/app.py
```

**Port:** `5005`

---

### Terminal 7 — API Gateway

```bash
python api_gateway/gateway.py
```

**Port:** `5000`

---

# 🧪 Testing

## Test Student API

```bash
curl http://127.0.0.1:5000/api/v1/students/1
```

---

## Test API Versioning

### V1

```bash
curl http://127.0.0.1:5000/api/v1/students/1
```

### V2

```bash
curl http://127.0.0.1:5000/api/v2/students/1
```

V2 provides an aggregated response with additional academic information and portal notices.

---

# 💳 Test Successful Enrollment

Example enrollment request:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/enroll \
  -H "Content-Type: application/json" \
  -d '{"student_id":1,"course_id":101,"fee":1000.0}'
```

Expected result:

```json
{
  "status": "COMPLETED"
}
```

### Transaction Flow

```text
Student Validation
        ↓
Course Seat Reservation
        ↓
Fee Payment
        ↓
Enrollment Creation
        ↓
Transaction Completed
```

---

# ❌ Test Saga Rollback

Use a fee amount greater than the available student balance:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/enroll \
  -H "Content-Type: application/json" \
  -d '{"student_id":1,"course_id":101,"fee":99999.0}'
```

Expected behavior:

```text
Student exists
      ↓
Course seat reserved
      ↓
Payment fails
      ↓
Compensating action triggered
      ↓
Course seat released
      ↓
Saga transaction failed safely
```

Example response:

```json
{
  "error": "Saga Failed. Compensating action executed: Seat released.",
  "reason": "Insufficient funds in student account"
}
```

---

# 🛡️ Test Circuit Breaker

Check the current state:

```bash
curl http://127.0.0.1:5005/circuit-status
```

Example:

```json
{
  "fee_service_circuit": {
    "state": "CLOSED",
    "failure_count": 0,
    "threshold": 3
  }
}
```

Stop the Fee Service and send multiple enrollment requests.

After the configured failure threshold is reached, the circuit transitions to:

```text
CLOSED
   ↓
OPEN
```

Further requests are immediately rejected instead of repeatedly waiting for a failed downstream service.

After the recovery timeout:

```text
OPEN
   ↓
HALF-OPEN
   ↓
Successful request
   ↓
CLOSED
```

---

# 🎯 Design Principles

This project demonstrates several important distributed-system principles:

### Loose Coupling

Each service owns its own business logic and database.

### Independent Deployment

Services communicate through APIs instead of directly sharing implementation details.

### Fault Isolation

Circuit Breaker prevents downstream failures from propagating throughout the system.

### Transaction Reliability

Saga orchestration and compensating actions maintain consistency across distributed operations.

### Service Independence

Database-per-Service prevents services from becoming tightly coupled through a shared database.

### API Abstraction

The API Gateway hides the internal service topology from clients.

---

# 👥 Team Contributions

| Role | Responsibility |
|---|---|
| Microservice Developer 1 | Student & Faculty Service |
| Microservice Developer 2 | Course & Academic Service |
| Communication Developer | Service Registry & Fee Service |
| Resilience / Transaction Developer | Saga Coordinator & Circuit Breaker |
| Integration / Gateway Developer | API Gateway & Exam Service |

---

# 📌 Evaluation Coverage

The system demonstrates:

- [x] Microservices Architecture
- [x] Service Decomposition
- [x] RESTful API Design
- [x] API Versioning
- [x] API Gateway
- [x] Dynamic Service Discovery
- [x] Database-per-Service
- [x] Data Isolation
- [x] Inter-Service Communication
- [x] Circuit Breaker
- [x] Fault Tolerance
- [x] Saga Pattern
- [x] Compensating Transactions
- [x] API Testing
- [x] Technical Documentation

---

# 📚 Learning Outcomes

Through this project, the team gained practical experience with:

- Designing distributed applications
- Decomposing monolithic functionality into microservices
- Building REST APIs using Flask
- Implementing service discovery
- Designing API gateways
- Managing isolated databases
- Handling distributed transactions
- Implementing failure recovery
- Applying resilience patterns
- Testing distributed systems

---

# 👨‍💻 Project

**College Management System — Microservices Architecture**

Built with **Python · Flask · SQLite · REST APIs**

---

⭐ If you found this project useful, consider giving the repository a star.
