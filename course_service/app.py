from flask import Flask, jsonify
import sqlite3
import os

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "course.db")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            faculty TEXT NOT NULL,
            credits INTEGER NOT NULL,
            total_seats INTEGER NOT NULL,
            available_seats INTEGER NOT NULL
        )
    """)

    if con.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
        con.executemany("""
            INSERT INTO courses VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (101, "CS101", "Data Structures", "Computer Science", 4, 60, 60),
            (102, "CS102", "Database Management Systems", "Computer Science", 4, 50, 50),
            (103, "CS103", "Operating Systems", "Computer Science", 4, 60, 60),
            (104, "CS104", "Computer Networks", "Computer Science", 3, 45, 45),
            (105, "CS105", "Software Engineering", "Computer Science", 3, 40, 40)
        ])

    con.commit()
    con.close()


@app.route("/health")
def health():
    return jsonify(service="course_service", status="UP", port=5003)


@app.route("/api/v1/courses/<int:id>")
def get_course(id):
    con = db()
    course = con.execute(
        "SELECT * FROM courses WHERE id=?", (id,)
    ).fetchone()
    con.close()

    return jsonify(dict(course)) if course else (
        jsonify(error="Course not found"), 404
    )


@app.route("/api/v1/courses/<int:id>/reserve", methods=["POST"])
def reserve(id):
    con = db()
    course = con.execute(
        "SELECT * FROM courses WHERE id=?", (id,)
    ).fetchone()

    if not course:
        con.close()
        return jsonify(error="Course not found"), 404

    if course["available_seats"] <= 0:
        con.close()
        return jsonify(error="No available seats"), 409

    con.execute(
        "UPDATE courses SET available_seats=available_seats-1 WHERE id=?",
        (id,)
    )
    con.commit()
    seats = course["available_seats"] - 1
    con.close()

    return jsonify(status="RESERVED", course_id=id, available_seats=seats)


@app.route("/api/v1/courses/<int:id>/release", methods=["POST"])
def release(id):
    con = db()
    course = con.execute(
        "SELECT * FROM courses WHERE id=?", (id,)
    ).fetchone()

    if not course:
        con.close()
        return jsonify(error="Course not found"), 404

    if course["available_seats"] >= course["total_seats"]:
        con.close()
        return jsonify(error="All seats are already available"), 409

    con.execute(
        "UPDATE courses SET available_seats=available_seats+1 WHERE id=?",
        (id,)
    )
    con.commit()
    seats = course["available_seats"] + 1
    con.close()

    return jsonify(status="RELEASED", course_id=id, available_seats=seats)


if __name__ == "__main__":
    init_db()
    app.run(port=5003, debug=True)