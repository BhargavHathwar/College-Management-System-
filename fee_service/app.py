import os
import sqlite3

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "fee.db")

REGISTRY_URL = "http://127.0.0.1:5001"
SERVICE_NAME = "fee_service"
SERVICE_PORT = 5004

# Demo balance given to any student who has no account yet
DEFAULT_BALANCE = 50000.0


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            student_id INTEGER PRIMARY KEY,
            balance REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_balance(conn, student_id):
    """Return the student's balance, creating a demo account if needed."""
    row = conn.execute(
        "SELECT balance FROM accounts WHERE student_id = ?", (student_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO accounts (student_id, balance) VALUES (?, ?)",
            (student_id, DEFAULT_BALANCE),
        )
        conn.commit()
        return DEFAULT_BALANCE
    return row["balance"]


# ---------------- SERVICE REGISTRY ----------------

def register_with_registry():
    try:
        requests.post(
            f"{REGISTRY_URL}/register",
            json={"name": SERVICE_NAME, "url": f"http://127.0.0.1:{SERVICE_PORT}"},
            timeout=3,
        )
        print("Registered with service registry")
    except requests.exceptions.RequestException:
        print("Registry not running, skipping registration")


# ---------------- ROUTES ----------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Fee Service is running"})


@app.route("/api/v1/fees/<int:student_id>", methods=["GET"])
def get_fees(student_id):
    conn = get_db()
    balance = get_balance(conn, student_id)
    rows = conn.execute(
        "SELECT * FROM payments WHERE student_id = ? ORDER BY id", (student_id,)
    ).fetchall()
    conn.close()
    return jsonify({
        "student_id": student_id,
        "balance": balance,
        "payments": [dict(r) for r in rows],
    })


@app.route("/api/v1/fees/pay", methods=["POST"])
def pay_fee():
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    # accept either "amount" or "fee" as the field name
    amount = data.get("amount", data.get("fee"))

    if student_id is None or amount is None:
        return jsonify({"error": "student_id and amount are required"}), 400
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be greater than 0"}), 400

    conn = get_db()
    balance = get_balance(conn, student_id)

    if amount > balance:
        conn.close()
        return jsonify({
            "status": "FAILED",
            "error": "Insufficient funds in student account",
        }), 400

    conn.execute(
        "UPDATE accounts SET balance = balance - ? WHERE student_id = ?",
        (amount, student_id),
    )
    cur = conn.execute(
        "INSERT INTO payments (student_id, course_id, amount, status) "
        "VALUES (?, ?, ?, 'PAID')",
        (student_id, data.get("course_id"), amount),
    )
    conn.commit()
    payment_id = cur.lastrowid
    conn.close()

    return jsonify({
        "status": "PAID",
        "payment_id": payment_id,
        "student_id": student_id,
        "amount": amount,
        "balance": balance - amount,
    }), 200


@app.route("/api/v1/fees/refund", methods=["POST"])
def refund_fee():
    data = request.get_json(silent=True) or {}
    payment_id = data.get("payment_id")

    conn = get_db()

    if payment_id is not None:
        payment = conn.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        if payment is None:
            conn.close()
            return jsonify({"error": "Payment not found"}), 404
        if payment["status"] == "REFUNDED":
            conn.close()
            return jsonify({"error": "Payment already refunded"}), 400
        student_id = payment["student_id"]
        amount = payment["amount"]
        conn.execute("UPDATE payments SET status = 'REFUNDED' WHERE id = ?",
                     (payment_id,))
    else:
        student_id = data.get("student_id")
        amount = data.get("amount", data.get("fee"))
        if student_id is None or amount is None:
            conn.close()
            return jsonify({"error": "payment_id, or student_id and amount, required"}), 400
        amount = float(amount)
        conn.execute(
            "INSERT INTO payments (student_id, course_id, amount, status) "
            "VALUES (?, ?, ?, 'REFUNDED')",
            (student_id, data.get("course_id"), amount),
        )

    get_balance(conn, student_id)
    conn.execute(
        "UPDATE accounts SET balance = balance + ? WHERE student_id = ?",
        (amount, student_id),
    )
    conn.commit()
    new_balance = get_balance(conn, student_id)
    conn.close()

    return jsonify({
        "status": "REFUNDED",
        "student_id": student_id,
        "amount": amount,
        "balance": new_balance,
    }), 200


# ---------------- START SERVICE ----------------

if __name__ == "__main__":
    init_db()
    register_with_registry()
    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=True)