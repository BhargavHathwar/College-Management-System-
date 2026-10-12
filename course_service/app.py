from flask import Flask, request, jsonify
from database import init_db, get_db
import requests

app = Flask(__name__)

REGISTRY_URL = "http://127.0.0.1:5002"
SERVICE_NAME = "course_service"
SERVICE_PORT = 5004

# Initialize the database
init_db()

# Home route
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "Course Service",
        "status": "running",
        "port": 5004
    })

# Get all courses
@app.route("/api/v1/courses", methods=["GET"])
def get_courses():
    db = get_db()
    courses = db.execute("SELECT * FROM courses").fetchall()
    db.close()
    return jsonify([dict(course) for course in courses])

# Get course by ID
@app.route("/api/v1/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    db = get_db()
    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()
    db.close()

    if course is None:
        return jsonify({"error": "Course not found"}), 404

    return jsonify(dict(course))

# Create a new course
@app.route("/api/v1/courses", methods=["POST"])
def create_course():
    data = request.get_json()

    # Check required fields
    required_fields = ["code", "name", "faculty", "credits", "total_seats"]

    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    db = get_db()

    # Insert the new course
    cursor = db.execute(
        """
        INSERT INTO courses
        (code, name, faculty, credits, total_seats, available_seats)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            data["code"],
            data["name"],
            data["faculty"],
            data["credits"],
            data["total_seats"],
            data["total_seats"]
        )
    )

    db.commit()
    course_id = cursor.lastrowid
    db.close()

    return jsonify({
        "message": "Course created successfully",
        "course_id": course_id
    }), 201

# Update an existing course
@app.route("/api/v1/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    data = request.get_json()
    db = get_db()

    # Check if course exists
    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    if course is None:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    # Update course details
    db.execute(
        """
        UPDATE courses
        SET code = ?,
            name = ?,
            faculty = ?,
            credits = ?
        WHERE id = ?
        """,
        (
            data.get("code", course["code"]),
            data.get("name", course["name"]),
            data.get("faculty", course["faculty"]),
            data.get("credits", course["credits"]),
            course_id
        )
    )

    db.commit()
    db.close()

    return jsonify({"message": "Course updated successfully"})

# Delete a course
@app.route("/api/v1/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    db = get_db()

    # Check if course exists
    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    if course is None:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    # Delete the course
    db.execute(
        "DELETE FROM courses WHERE id = ?",
        (course_id,)
    )

    db.commit()
    db.close()

    return jsonify({"message": "Course deleted successfully"})

# Reserve a course seat
@app.route("/api/v1/courses/<int:course_id>/reserve", methods=["POST"])
def reserve_course(course_id):
    db = get_db()

    # Check if course exists
    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    if course is None:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    # Check seat availability
    if course["available_seats"] <= 0:
        db.close()
        return jsonify({"error": "No available seats"}), 409

    # Reduce available seats
    db.execute(
        """
        UPDATE courses
        SET available_seats = available_seats - 1
        WHERE id = ?
        """,
        (course_id,)
    )

    db.commit()
    db.close()

    return jsonify({
        "message": "Course seat reserved successfully",
        "course_id": course_id,
        "available_seats": course["available_seats"] - 1
    })

# Release a course seat
@app.route("/api/v1/courses/<int:course_id>/release", methods=["POST"])
def release_course(course_id):
    db = get_db()

    # Check if course exists
    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    if course is None:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    # Check if all seats are available
    if course["available_seats"] >= course["total_seats"]:
        db.close()
        return jsonify({"error": "All seats are already available"}), 409

    # Increase available seats
    db.execute(
        """
        UPDATE courses
        SET available_seats = available_seats + 1
        WHERE id = ?
        """,
        (course_id,)
    )

    db.commit()
    db.close()

    return jsonify({
        "message": "Course seat released successfully",
        "course_id": course_id,
        "available_seats": course["available_seats"] + 1
    })

def register_with_registry():
    try:
        response = requests.post(
            f"{REGISTRY_URL}/register",
            json={
                "name": SERVICE_NAME,
                "url": f"http://127.0.0.1:{SERVICE_PORT}"
            },
            timeout=3
        )
        response.raise_for_status()
        print("Course Service registered successfully")

    except requests.RequestException as exc:
        print(f"Could not register Course Service: {exc}")


# Start the Course Service
if __name__ == "__main__":
    register_with_registry()
    app.run(
        host="0.0.0.0",
        port=SERVICE_PORT,
        debug=True
    )