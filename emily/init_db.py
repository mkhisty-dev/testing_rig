"""Initialize the SQLite database for the grade testing rig."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "grades.db"


def init_database() -> None:
    """Create the grades table if it does not already exist."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                grade TEXT NOT NULL
            )
            """
        )
        connection.commit()


if __name__ == "__main__":
    init_database()
    print(f"Database initialized at {DATABASE_PATH}")
