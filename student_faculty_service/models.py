import sqlite3

DATABASE = "user.db"


def get_db():
    db = sqlite3.connect(DATABASE)

    # Allows us to access columns by name
    db.row_factory = sqlite3.Row

    return db


def init_db():

    db = get_db()

    # ---------------- STUDENTS ----------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            year INTEGER NOT NULL
        )
    """)

    # ---------------- FACULTY ----------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL
        )
    """)

    db.commit()
    db.close()