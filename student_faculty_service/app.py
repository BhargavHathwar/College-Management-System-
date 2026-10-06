from flask import Flask, request, jsonify
from models import init_db, get_db

app = Flask(__name__)

# Initialize the database
init_db()


# ---------------- HOME ----------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "Student and Faculty Service",
        "status": "running",
        "port": 5003
    })


# =========================================================
# STUDENT APIs
# =========================================================

# GET all students
@app.route("/api/v1/students", methods=["GET"])
def get_students():
    db = get_db()

    students = db.execute(
        "SELECT * FROM students"
    ).fetchall()

    db.close()

    return jsonify([dict(student) for student in students])


# GET student by ID
@app.route("/api/v1/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    db = get_db()

    student = db.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    db.close()

    if student is None:
        return jsonify({"error": "Student not found"}), 404

    return jsonify(dict(student))


# CREATE student
@app.route("/api/v1/students", methods=["POST"])
def create_student():

    data = request.get_json()

    required_fields = [
        "name",
        "email",
        "department",
        "year"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"{field} is required"
            }), 400

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO students
        (name, email, department, year)
        VALUES (?, ?, ?, ?)
        """,
        (
            data["name"],
            data["email"],
            data["department"],
            data["year"]
        )
    )

    db.commit()

    student_id = cursor.lastrowid

    db.close()

    return jsonify({
        "message": "Student created successfully",
        "student_id": student_id
    }), 201


# UPDATE student
@app.route("/api/v1/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):

    data = request.get_json()

    db = get_db()

    student = db.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    if student is None:
        db.close()

        return jsonify({
            "error": "Student not found"
        }), 404

    db.execute(
        """
        UPDATE students
        SET name = ?,
            email = ?,
            department = ?,
            year = ?
        WHERE id = ?
        """,
        (
            data.get("name", student["name"]),
            data.get("email", student["email"]),
            data.get("department", student["department"]),
            data.get("year", student["year"]),
            student_id
        )
    )

    db.commit()
    db.close()

    return jsonify({
        "message": "Student updated successfully"
    })


# DELETE student
@app.route("/api/v1/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):

    db = get_db()

    student = db.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    if student is None:
        db.close()

        return jsonify({
            "error": "Student not found"
        }), 404

    db.execute(
        "DELETE FROM students WHERE id = ?",
        (student_id,)
    )

    db.commit()
    db.close()

    return jsonify({
        "message": "Student deleted successfully"
    })


# =========================================================
# FACULTY APIs
# =========================================================

# GET all faculty
@app.route("/api/v1/faculty", methods=["GET"])
def get_faculty():

    db = get_db()

    faculty = db.execute(
        "SELECT * FROM faculty"
    ).fetchall()

    db.close()

    return jsonify([dict(member) for member in faculty])


# GET faculty by ID
@app.route("/api/v1/faculty/<int:faculty_id>", methods=["GET"])
def get_faculty_member(faculty_id):

    db = get_db()

    member = db.execute(
        "SELECT * FROM faculty WHERE id = ?",
        (faculty_id,)
    ).fetchone()

    db.close()

    if member is None:
        return jsonify({
            "error": "Faculty member not found"
        }), 404

    return jsonify(dict(member))


# CREATE faculty
@app.route("/api/v1/faculty", methods=["POST"])
def create_faculty():

    data = request.get_json()

    required_fields = [
        "name",
        "email",
        "department"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"{field} is required"
            }), 400

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO faculty
        (name, email, department)
        VALUES (?, ?, ?)
        """,
        (
            data["name"],
            data["email"],
            data["department"]
        )
    )

    db.commit()

    faculty_id = cursor.lastrowid

    db.close()

    return jsonify({
        "message": "Faculty created successfully",
        "faculty_id": faculty_id
    }), 201


# UPDATE faculty
@app.route("/api/v1/faculty/<int:faculty_id>", methods=["PUT"])
def update_faculty(faculty_id):

    data = request.get_json()

    db = get_db()

    member = db.execute(
        "SELECT * FROM faculty WHERE id = ?",
        (faculty_id,)
    ).fetchone()

    if member is None:
        db.close()

        return jsonify({
            "error": "Faculty member not found"
        }), 404

    db.execute(
        """
        UPDATE faculty
        SET name = ?,
            email = ?,
            department = ?
        WHERE id = ?
        """,
        (
            data.get("name", member["name"]),
            data.get("email", member["email"]),
            data.get("department", member["department"]),
            faculty_id
        )
    )

    db.commit()
    db.close()

    return jsonify({
        "message": "Faculty updated successfully"
    })


# DELETE faculty
@app.route("/api/v1/faculty/<int:faculty_id>", methods=["DELETE"])
def delete_faculty(faculty_id):

    db = get_db()

    member = db.execute(
        "SELECT * FROM faculty WHERE id = ?",
        (faculty_id,)
    ).fetchone()

    if member is None:
        db.close()

        return jsonify({
            "error": "Faculty member not found"
        }), 404

    db.execute(
        "DELETE FROM faculty WHERE id = ?",
        (faculty_id,)
    )

    db.commit()
    db.close()

    return jsonify({
        "message": "Faculty deleted successfully"
    })


# =========================================================
# START SERVICE
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5003,
        debug=True
    )