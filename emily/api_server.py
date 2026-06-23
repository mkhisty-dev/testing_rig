"""Flask API server for the microservice observability testing rig."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

import testing_rig.emily.db_server as db_server


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE_PATH = BASE_DIR / "app_activity.log"
COMPONENT_NAME = "Frontend-API"
REQUIRED_GRADE_FIELDS = ("first_name", "last_name", "class_name", "grade")


# Format log records as compact JSON for observability tooling.
class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON for observability tooling."""

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


# Configure the logger for the API.
def configure_logger() -> logging.Logger:
    """Configure and return the API logger."""
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


# Write a structured API log event.
def log_event(level: int, correlation_id: str, message: str, **extra_fields: Any) -> None:
    """Write a structured API log event."""
    logger.log(
        level,
        message,
        extra={
            "component": COMPONENT_NAME,
            "correlation_id": correlation_id,
            "extra_fields": extra_fields,
        },
    )


# Attach a correlation ID to every incoming request.
@app.before_request
def attach_correlation_id() -> None:
    """Attach a correlation ID to every incoming request."""
    request.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    # Authentication placeholder:
    # auth_token = request.headers.get("Authorization")
    # TODO: Integrate with Reem's auth service
    # if not auth_token:
    #     return jsonify({"error": "Missing Authorization token"}), 401

    log_event(
        logging.INFO,
        request.correlation_id,
        "Received incoming HTTP request",
        method=request.method,
        path=request.path,
        remote_addr=request.remote_addr,
    )


@app.after_request
# Add the correlation ID to the response headers.
def add_correlation_id_header(response):
    """Return the correlation ID so callers can cross-reference logs."""
    response.headers["X-Correlation-ID"] = request.correlation_id
    log_event(
        logging.INFO,
        request.correlation_id,
        "Completed HTTP request",
        method=request.method,
        path=request.path,
        status_code=response.status_code,
    )
    return response


# Serve the single-page frontend.
@app.route("/")
def index():
    """Serve the single-page frontend."""
    return render_template("index.html")


@app.post("/api/grades")
# Create a grade record from JSON input.
def create_grade():
    """Create a grade record from JSON input."""
    correlation_id = request.correlation_id
    payload = request.get_json(silent=True) or {}

    log_event(
        logging.INFO,
        correlation_id,
        "Received submit grade request",
        payload_keys=sorted(payload.keys()),
    )

    missing_fields = [field for field in REQUIRED_GRADE_FIELDS if not str(payload.get(field, "")).strip()]
    if missing_fields:
        log_event(
            logging.WARNING,
            correlation_id,
            "Rejecting submit grade request due to missing fields",
            missing_fields=missing_fields,
        )
        return jsonify({"error": "Missing required fields", "missing_fields": missing_fields}), 400

    row_id = db_server.insert_grade(
        first_name=payload["first_name"].strip(),
        last_name=payload["last_name"].strip(),
        class_name=payload["class_name"].strip(),
        grade=payload["grade"].strip(),
        correlation_id=correlation_id,
    )

    log_event(
        logging.INFO,
        correlation_id,
        "Grade record created",
        row_id=row_id,
        first_name=payload["first_name"].strip(),
        last_name=payload["last_name"].strip(),
    )
    return jsonify({"id": row_id, "message": "Grade submitted", "correlation_id": correlation_id}), 201


@app.get("/api/grades")
# Fetch grade records by first and last name.
def get_grades():
    """Fetch grade records by first and last name."""
    correlation_id = request.correlation_id
    first_name = request.args.get("first_name", "").strip()
    last_name = request.args.get("last_name", "").strip()

    log_event(
        logging.INFO,
        correlation_id,
        "Received fetch request for student grades",
        first_name=first_name,
        last_name=last_name,
    )

    if not first_name or not last_name:
        log_event(logging.WARNING, correlation_id, "Rejecting fetch request due to missing name fields")
        return jsonify({"error": "first_name and last_name are required"}), 400

    rows = db_server.fetch_grades(first_name, last_name, correlation_id)
    return jsonify({"grades": rows, "count": len(rows), "correlation_id": correlation_id})


if __name__ == "__main__":
    db_server.initialize_database("api-startup")
    app.run(host="0.0.0.0", port=5000, debug=True)
