from __future__ import annotations

from flask import Blueprint

from facturas_app.utils.responses import success_response

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health() -> tuple:
    """Liveness endpoint for local monitoring and diagnostics."""
    return success_response({"status": "healthy"})
