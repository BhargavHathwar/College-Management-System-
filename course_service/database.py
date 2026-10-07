import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "course.db")

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS courses(
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            name TEXT,
            faculty TEXT,
            credits INTEGER,
            total_seats INTEGER,
            available_seats INTEGER
        )
    """)

    if not db.execute("SELECT 1 FROM courses LIMIT 1").fetchone():
        db.executemany(
            "INSERT INTO courses VALUES(?,?,?,?,?,?,?)",
            [
                (101,"CS101","Data Structures","Computer Science",4,60,60),
                (102,"CS102","Database Management Systems","Computer Science",4,50,50),
                (103,"CS103","Operating Systems","Computer Science",4,60,60),
                (104,"CS104","Computer Networks","Computer Science",3,45,45),
                (105,"CS105","Software Engineering","Computer Science",3,40,40)
            ]
        )

    db.commit()
    db.close()