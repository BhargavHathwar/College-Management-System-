"""
Database module for Enrollment & Saga Service.
Enforces the Database-per-Service architecture with strict data isolation.
Owns `enrollment.db`. Never directly accesses other services' databases.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "enrollment.db")


def get_db():
    """Create and return a database connection configured with Row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite tables for enrollments, saga audit logs, and attendance."""
    conn = get_db()
    cursor = conn.cursor()

    # Table 1: Enrollments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            saga_id TEXT NOT NULL,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            fee_amount REAL NOT NULL,
            payment_id INTEGER,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 2: Saga Audit & Execution Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saga_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            saga_id TEXT NOT NULL,
            student_id INTEGER,
            course_id INTEGER,
            step TEXT NOT NULL,
            status TEXT NOT NULL,
            compensation_executed INTEGER DEFAULT 0,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 3: Attendance Records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
