from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

EXAM_PORT = 5007
DATABASE = "exam_service/exam.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            exam_type TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT NOT NULL,
            max_marks INTEGER NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            marks REAL NOT NULL,
            grade TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        )
    """)

    connection.commit()
    connection.close()


def calculate_grade(marks):
    if marks >= 90:
        return "A+"
    elif marks >= 80:
        return "A"
    elif marks >= 70:
        return "B+"
    elif marks >= 60:
        return "B"
    elif marks >= 50:
        return "C"
    elif marks >= 40:
        return "D"
    else:
        return "F"


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "service": "Exam & Grading Service",
        "status": "UP",
        "port": EXAM_PORT
    }), 200


@app.route("/api/v1/exams/schedule", methods=["POST"])
def schedule_exam():

    data = request.get_json()

    required_fields = [
        "course_id",
        "exam_type",
        "exam_date",
        "start_time",
        "end_time",
        "room",
        "max_marks"
    ]

    missing_fields = [
        field for field in required_fields
        if field not in data
    ]

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    connection = get_db_connection()

    cursor = connection.execute("""
        INSERT INTO exams (
            course_id,
            exam_type,
            exam_date,
            start_time,
            end_time,
            room,
            max_marks
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["course_id"],
        data["exam_type"],
        data["exam_date"],
        data["start_time"],
        data["end_time"],
        data["room"],
        data["max_marks"]
    ))

    connection.commit()

    exam_id = cursor.lastrowid

    connection.close()

    return jsonify({
        "message": "Exam scheduled successfully",
        "exam_id": exam_id
    }), 201


@app.route("/api/v1/exams", methods=["GET"])
def get_exams():

    connection = get_db_connection()

    exams = connection.execute("""
        SELECT * FROM exams
        ORDER BY exam_date, start_time
    """).fetchall()

    connection.close()

    return jsonify([
        dict(exam)
        for exam in exams
    ]), 200


@app.route("/api/v1/exams/<int:exam_id>", methods=["GET"])
def get_exam(exam_id):

    connection = get_db_connection()

    exam = connection.execute("""
        SELECT * FROM exams
        WHERE id = ?
    """, (exam_id,)).fetchone()

    connection.close()

    if exam is None:
        return jsonify({
            "error": "Exam not found"
        }), 404

    return jsonify(dict(exam)), 200


@app.route("/api/v1/exams/<int:exam_id>", methods=["PUT"])
def update_exam(exam_id):

    data = request.get_json()

    connection = get_db_connection()

    existing_exam = connection.execute("""
        SELECT * FROM exams
        WHERE id = ?
    """, (exam_id,)).fetchone()

    if existing_exam is None:
        connection.close()

        return jsonify({
            "error": "Exam not found"
        }), 404

    connection.execute("""
        UPDATE exams
        SET course_id = ?,
            exam_type = ?,
            exam_date = ?,
            start_time = ?,
            end_time = ?,
            room = ?,
            max_marks = ?
        WHERE id = ?
    """, (
        data.get("course_id", existing_exam["course_id"]),
        data.get("exam_type", existing_exam["exam_type"]),
        data.get("exam_date", existing_exam["exam_date"]),
        data.get("start_time", existing_exam["start_time"]),
        data.get("end_time", existing_exam["end_time"]),
        data.get("room", existing_exam["room"]),
        data.get("max_marks", existing_exam["max_marks"]),
        exam_id
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Exam updated successfully",
        "exam_id": exam_id
    }), 200


@app.route("/api/v1/exams/<int:exam_id>", methods=["DELETE"])
def delete_exam(exam_id):

    connection = get_db_connection()

    existing_exam = connection.execute("""
        SELECT * FROM exams
        WHERE id = ?
    """, (exam_id,)).fetchone()

    if existing_exam is None:
        connection.close()

        return jsonify({
            "error": "Exam not found"
        }), 404

    connection.execute("""
        DELETE FROM exams
        WHERE id = ?
    """, (exam_id,))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Exam deleted successfully",
        "exam_id": exam_id
    }), 200


@app.route("/api/v1/grades/submit", methods=["POST"])
def submit_grade():

    data = request.get_json()

    required_fields = [
        "student_id",
        "course_id",
        "exam_id",
        "marks"
    ]

    missing_fields = [
        field for field in required_fields
        if field not in data
    ]

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    marks = float(data["marks"])

    if marks < 0 or marks > 100:
        return jsonify({
            "error": "Marks must be between 0 and 100"
        }), 400

    connection = get_db_connection()

    exam = connection.execute("""
        SELECT * FROM exams
        WHERE id = ?
    """, (data["exam_id"],)).fetchone()

    if exam is None:
        connection.close()

        return jsonify({
            "error": "Exam not found"
        }), 404

    grade = calculate_grade(marks)

    cursor = connection.execute("""
        INSERT INTO grades (
            student_id,
            course_id,
            exam_id,
            marks,
            grade,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["student_id"],
        data["course_id"],
        data["exam_id"],
        marks,
        grade,
        datetime.now().isoformat()
    ))

    connection.commit()

    grade_id = cursor.lastrowid

    connection.close()

    return jsonify({
        "message": "Grade submitted successfully",
        "grade_id": grade_id,
        "student_id": data["student_id"],
        "marks": marks,
        "grade": grade
    }), 201


@app.route(
    "/api/v1/grades/transcript/<int:student_id>",
    methods=["GET"]
)
def get_transcript(student_id):

    connection = get_db_connection()

    grades = connection.execute("""
        SELECT
            grades.id,
            grades.student_id,
            grades.course_id,
            grades.exam_id,
            exams.exam_type,
            exams.exam_date,
            grades.marks,
            grades.grade,
            grades.created_at
        FROM grades
        JOIN exams
        ON grades.exam_id = exams.id
        WHERE grades.student_id = ?
        ORDER BY exams.exam_date
    """, (student_id,)).fetchall()

    connection.close()

    return jsonify({
        "student_id": student_id,
        "transcript": [
            dict(grade)
            for grade in grades
        ]
    }), 200


if __name__ == "__main__":
    initialize_database()

    app.run(
        host="127.0.0.1",
        port=EXAM_PORT,
        debug=True
    )