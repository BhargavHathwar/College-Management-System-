import os
import sqlite3

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# DB file sits next to this app.py, so it works from any folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "fees.db")

REGISTRY_URL = "http://localhost:5000"
SERVICE_NAME = "fee_service"
SERVICE_PORT = 5003


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            due_date TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()


# ---------------- SERVICE REGISTRY ----------------

def register_with_registry():
    try:
        requests.post(
            f"{REGISTRY_URL}/register",
            json={"name": SERVICE_NAME, "url": f"http://localhost:{SERVICE_PORT}"},
            timeout=3,
        )
        print("Registered with service registry")
    except requests.exceptions.RequestException:
        print("Registry not running, skipping registration")


# ---------------- ROUTES ----------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Fee Service is running"})


@app.route("/fees", methods=["POST"])
def add_fee():
    data = request.get_json(silent=True)
    if not data or "student_id" not in data or "amount" not in data:
        return jsonify({"error": "student_id and amount are required"}), 400

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO fees (student_id, description, amount, due_date, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            data["student_id"],
            data.get("description"),
            data["amount"],
            data.get("due_date"),
            data.get("status", "pending"),
        ),
    )
    conn.commit()
    fee_id = cur.lastrowid
    conn.close()
    return jsonify({"message": "Fee added successfully", "id": fee_id}), 201


@app.route("/fees", methods=["GET"])
def get_all_fees():
    conn = get_db()
    rows = conn.execute("SELECT * FROM fees").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/fees/<int:fee_id>", methods=["GET"])
def get_fee(fee_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Fee not found"}), 404
    return jsonify(dict(row))


@app.route("/fees/student/<int:student_id>", methods=["GET"])
def get_student_fees(student_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM fees WHERE student_id = ?", (student_id,)
    ).fetchall()
    conn.close()
    fees = [dict(r) for r in rows]
    return jsonify({
        "student_id": student_id,
        "total": sum(f["amount"] for f in fees),
        "pending": sum(f["amount"] for f in fees if f["status"] == "pending"),
        "fees": fees,
    })


@app.route("/fees/<int:fee_id>", methods=["PUT"])
def update_fee(fee_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
    if not fee:
        conn.close()
        return jsonify({"error": "Fee not found"}), 404

    conn.execute(
        "UPDATE fees SET description = ?, amount = ?, due_date = ?, status = ? "
        "WHERE id = ?",
        (
            data.get("description", fee["description"]),
            data.get("amount", fee["amount"]),
            data.get("due_date", fee["due_date"]),
            data.get("status", fee["status"]),
            fee_id,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Fee updated successfully"})


@app.route("/fees/<int:fee_id>/pay", methods=["POST"])
def pay_fee(fee_id):
    conn = get_db()
    fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
    if not fee:
        conn.close()
        return jsonify({"error": "Fee not found"}), 404

    conn.execute("UPDATE fees SET status = 'paid' WHERE id = ?", (fee_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Fee marked as paid", "id": fee_id})


@app.route("/fees/<int:fee_id>", methods=["DELETE"])
def delete_fee(fee_id):
    conn = get_db()
    fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
    if not fee:
        conn.close()
        return jsonify({"error": "Fee not found"}), 404

    conn.execute("DELETE FROM fees WHERE id = ?", (fee_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Fee deleted successfully"})


# ---------------- START SERVICE ----------------

if __name__ == "__main__":
    init_db()
    register_with_registry()
    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=True)