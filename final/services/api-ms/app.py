"""Flask frontend API microservice for the observability testing rig.

Calls db-ms (HTTP) for persistence and auth-ms (HTTP) for token validation.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse as url_parse, request as url_request
from urllib.error import URLError

from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE_PATH = BASE_DIR / "app_activity.log"
COMPONENT_NAME = "Frontend-API"
REQUIRED_GRADE_FIELDS = ("first_name", "last_name", "class_name", "grade")
DB_URL = os.environ.get("DB_URL", "http://localhost:6000")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:3000")


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


def log_event(level: int, correlation_id: str, message: str, **extra_fields: Any) -> None:
    logger.log(
        level,
        message,
        extra={
            "component": COMPONENT_NAME,
            "correlation_id": correlation_id,
            "extra_fields": extra_fields,
        },
    )


def _http_request(
    base_url: str,
    method: str,
    path: str,
    body: dict | None = None,
    params: dict[str, str] | None = None,
    correlation_id: str = "",
) -> tuple[dict, int]:
    url = f"{base_url}{path}"
    if params:
        url += "?" + url_parse.urlencode(params)
    headers = {"Content-Type": "application/json"}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    data = json.dumps(body).encode("utf-8") if body else None
    req = url_request.Request(url, data=data, headers=headers, method=method)
    try:
        with url_request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except URLError as e:
        log_event(logging.ERROR, correlation_id, "Upstream request failed",
                  error=str(e), url=url, upstream=base_url)
        return {"error": "Service unavailable"}, 503


def _validate_token(headers: dict[str, str], correlation_id: str) -> bool:
    auth_token = headers.get("Authorization", "")
    if not auth_token:
        return False
    data, status = _http_request(AUTH_URL, "POST", "/validate-token",
                                 body={"token": auth_token},
                                 correlation_id=correlation_id)
    return data.get("valid", False) if status == 200 else False


@app.before_request
def attach_correlation_id() -> None:
    request.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    if not _validate_token(dict(request.headers), request.correlation_id):
        log_event(logging.WARNING, request.correlation_id, "Missing or invalid auth token")
        # Uncomment to enforce auth:
        # return jsonify({"error": "Unauthorized"}), 401

    log_event(logging.INFO, request.correlation_id, "Received incoming HTTP request",
              method=request.method, path=request.path,
              remote_addr=request.remote_addr)


@app.after_request
def add_correlation_id_header(response):
    response.headers["X-Correlation-ID"] = request.correlation_id
    log_event(logging.INFO, request.correlation_id, "Completed HTTP request",
              method=request.method, path=request.path,
              status_code=response.status_code)
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/grades")
def create_grade():
    correlation_id = request.correlation_id
    payload = request.get_json(silent=True) or {}

    log_event(logging.INFO, correlation_id, "Received submit grade request",
              payload_keys=sorted(payload.keys()))

    missing = [f for f in REQUIRED_GRADE_FIELDS if not str(payload.get(f, "")).strip()]
    if missing:
        log_event(logging.WARNING, correlation_id,
                  "Rejecting submit grade request due to missing fields",
                  missing_fields=missing)
        return jsonify({"error": "Missing required fields", "missing_fields": missing}), 400

    data, status = _http_request(
        DB_URL, "POST", "/grades",
        body={
            "first_name": payload["first_name"].strip(),
            "last_name": payload["last_name"].strip(),
            "class_name": payload["class_name"].strip(),
            "grade": payload["grade"].strip(),
        },
        correlation_id=correlation_id,
    )

    if status != 201:
        return jsonify(data), status

    row_id = data.get("id")
    log_event(logging.INFO, correlation_id, "Grade record created",
              row_id=row_id, first_name=payload["first_name"].strip(),
              last_name=payload["last_name"].strip())
    return jsonify({"id": row_id, "message": "Grade submitted",
                    "correlation_id": correlation_id}), 201


@app.get("/api/grades")
def get_grades():
    correlation_id = request.correlation_id
    first_name = request.args.get("first_name", "").strip()
    last_name = request.args.get("last_name", "").strip()

    log_event(logging.INFO, correlation_id, "Received fetch request for student grades",
              first_name=first_name, last_name=last_name)

    if not first_name or not last_name:
        log_event(logging.WARNING, correlation_id,
                  "Rejecting fetch request due to missing name fields")
        return jsonify({"error": "first_name and last_name are required"}), 400

    data, status = _http_request(
        DB_URL, "GET", "/grades",
        params={"first_name": first_name, "last_name": last_name},
        correlation_id=correlation_id,
    )

    if status != 200:
        return jsonify(data), status

    return jsonify({"grades": data.get("grades", []),
                    "count": data.get("count", 0),
                    "correlation_id": correlation_id})


if __name__ == "__main__":
    try:
        _http_request(DB_URL, "POST", "/init", correlation_id="api-startup")
    except Exception:
        log_event(logging.WARNING, "api-startup",
                  "Could not reach db-ms for init — will retry on first request")
    app.run(host="0.0.0.0", port=5000, debug=True)
