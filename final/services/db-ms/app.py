"""HTTP database microservice for the observability testing rig."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path("/data/grades.db")
LOG_FILE_PATH = BASE_DIR / "app_activity.log"
COMPONENT_NAME = "DB-Backend"


class JsonLogFormatter(logging.Formatter):
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
app = Flask(__name__)


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


@app.before_request
def attach_correlation_id() -> None:
    request.correlation_id = request.headers.get("X-Correlation-ID") or "db-unknown"


def _init_tables() -> None:
    _log(logging.INFO, "startup", "Ensuring grades table exists", database=str(DATABASE_PATH))
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                grade TEXT NOT NULL
            )"""
        )
        connection.commit()
    _log(logging.INFO, "startup", "Database initialization complete")


@app.post("/init")
def handle_init():
    correlation_id = request.correlation_id
    _init_tables()
    _log(logging.INFO, correlation_id, "Database initialized via HTTP")
    return jsonify({"status": "ok"}), 200


@app.post("/grades")
def insert_grade():
    correlation_id = request.correlation_id
    data = request.get_json(silent=True) or {}
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    class_name = data.get("class_name", "").strip()
    grade = data.get("grade", "").strip()

    _log(logging.INFO, correlation_id, "Executing SQL INSERT for grade record",
         first_name=first_name, last_name=last_name, class_name=class_name)

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            "INSERT INTO grades (first_name, last_name, class_name, grade) VALUES (?, ?, ?, ?)",
            (first_name, last_name, class_name, grade),
        )
        connection.commit()
        row_id = int(cursor.lastrowid)

    _log(logging.INFO, correlation_id, "SQL INSERT committed", row_id=row_id)
    return jsonify({"id": row_id}), 201


@app.get("/grades")
def fetch_grades():
    correlation_id = request.correlation_id
    first_name = request.args.get("first_name", "").strip()
    last_name = request.args.get("last_name", "").strip()

    _log(logging.INFO, correlation_id, "Executing SQL SELECT for grade records",
         first_name=first_name, last_name=last_name)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT id, first_name, last_name, class_name, grade
               FROM grades
               WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?)
               ORDER BY id DESC""",
            (first_name, last_name),
        ).fetchall()

    results = [dict(row) for row in rows]
    _log(logging.INFO, correlation_id, "SQL SELECT complete", row_count=len(results))
    return jsonify({"grades": results, "count": len(results)}), 200


if __name__ == "__main__":
    os.makedirs("/data", exist_ok=True)
    _init_tables()
    app.run(host="0.0.0.0", port=6000)
