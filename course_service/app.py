from flask import Flask, jsonify
from database import get_db, init_db
app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "course_service",
        "status": "UP",
        "port": 5004
    })

@app.route("/api/v1/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    db = get_db()

    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    db.close()

    if not course:
        return jsonify({"error": "Course not found"}), 404

    return jsonify(dict(course))

@app.route("/api/v1/courses/<int:course_id>/reserve", methods=["POST"])
def reserve_course(course_id):
    db = get_db()

    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    if course["available_seats"] <= 0:
        db.close()
        return jsonify({"error": "No available seats"}), 409

    db.execute(
        """
        UPDATE courses
        SET available_seats = available_seats - 1
        WHERE id = ?
        """,
        (course_id,)
    )

    db.commit()

    seats = course["available_seats"] - 1
    db.close()

    return jsonify({
        "status": "RESERVED",
        "course_id": course_id,
        "available_seats": seats
    })

@app.route("/api/v1/courses/<int:course_id>/release", methods=["POST"])
def release_course(course_id):
    db = get_db()

    course = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,)
    ).fetchone()

    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    if course["available_seats"] >= course["total_seats"]:
        db.close()
        return jsonify({
            "error": "All seats are already available"
        }), 409

    db.execute(
        """
        UPDATE courses
        SET available_seats = available_seats + 1
        WHERE id = ?
        """,
        (course_id,)
    )

    db.commit()

    seats = course["available_seats"] + 1
    db.close()

    return jsonify({
        "status": "RELEASED",
        "course_id": course_id,
        "available_seats": seats
    })

if __name__ == "__main__":
    init_db()
    app.run(
        host="127.0.0.1",
        port=5004,
        debug=True
    )