"""Database interface layer for the microservice observability testing rig.

This module intentionally acts like a distinct database backend boundary even
though it runs in-process for simplicity. Every public function accepts a
correlation ID so API requests can be traced through SQL execution logs.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "grades.db"
LOG_FILE_PATH = BASE_DIR / "app_activity.log"
COMPONENT_NAME = "DB-Backend"


class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON for log aggregation platforms."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", COMPONENT_NAME),
            "correlation_id": getattr(record, "correlation_id", "N/A"),
            "message": record.getMessage(),
        }

        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)

        return json.dumps(payload, separators=(",", ":"))


def configure_logger() -> logging.Logger:
    """Configure and return the database layer logger."""
    logger = logging.getLogger(COMPONENT_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = JsonLogFormatter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


logger = configure_logger()


def _log(level: int, correlation_id: str, message: str, **extra_fields: Any) -> None:
    logger.log(
        level,
        message,
        extra={
            "component": COMPONENT_NAME,
            "correlation_id": correlation_id,
            "extra_fields": extra_fields,
        },
    )


def initialize_database(correlation_id: str = "startup") -> None:
    """Create the grades table if it does not already exist."""
    _log(logging.INFO, correlation_id, "Ensuring grades table exists", database=str(DATABASE_PATH))

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

    _log(logging.INFO, correlation_id, "Database initialization complete")


def insert_grade(
    first_name: str,
    last_name: str,
    class_name: str,
    grade: str,
    correlation_id: str,
) -> int:
    """Insert a grade record and return the new row ID."""
    _log(
        logging.INFO,
        correlation_id,
        "Executing SQL INSERT for grade record",
        first_name=first_name,
        last_name=last_name,
        class_name=class_name,
    )

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO grades (first_name, last_name, class_name, grade)
            VALUES (?, ?, ?, ?)
            """,
            (first_name, last_name, class_name, grade),
        )
        connection.commit()
        row_id = int(cursor.lastrowid)

    _log(logging.INFO, correlation_id, "SQL INSERT committed", row_id=row_id)
    return row_id


def fetch_grades(first_name: str, last_name: str, correlation_id: str) -> list[dict[str, Any]]:
    """Fetch grade records for a student by first and last name."""
    _log(
        logging.INFO,
        correlation_id,
        "Executing SQL SELECT for grade records",
        first_name=first_name,
        last_name=last_name,
    )

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, first_name, last_name, class_name, grade
            FROM grades
            WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?)
            ORDER BY id DESC
            """,
            (first_name, last_name),
        ).fetchall()

    results = [dict(row) for row in rows]
    _log(logging.INFO, correlation_id, "SQL SELECT complete", row_count=len(results))
    return results


if __name__ == "__main__":
    initialize_database("manual-db-startup")
    print(f"Database layer ready. SQLite file: {DATABASE_PATH}")
