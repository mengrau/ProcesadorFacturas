from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import Response, jsonify


def _utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO-8601 format."""
    return datetime.now(tz=timezone.utc).isoformat()


def success_response(
    data: dict[str, Any] | None = None,
    *,
    status: int = 200,
    message: str = "ok",
) -> tuple[Response, int]:
    """Build a standardized success JSON response."""
    payload: dict[str, Any] = {
        "ok": True,
        "message": message,
        "timestamp": _utc_now_iso(),
    }
    if data:
        payload.update(data)
    return jsonify(payload), status


def error_response(
    message: str,
    *,
    status: int = 400,
    details: dict[str, Any] | None = None,
) -> tuple[Response, int]:
    """Build a standardized error JSON response."""
    payload: dict[str, Any] = {
        "ok": False,
        "error": message,
        "timestamp": _utc_now_iso(),
    }
    if details:
        payload["details"] = details
    return jsonify(payload), status
