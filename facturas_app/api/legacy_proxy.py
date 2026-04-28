from __future__ import annotations

from flask import Blueprint

from facturas_app.legacy.bridge import get_server_legacy

legacy_bp = Blueprint("legacy_proxy", __name__)


def _legacy():
    """Return loaded legacy server module."""
    return get_server_legacy()


@legacy_bp.route("/", methods=["GET"])
def index():
    return _legacy().index()


@legacy_bp.route("/styles.css", methods=["GET"])
def styles():
    return _legacy().styles()


@legacy_bp.route("/dsd", methods=["GET"])
@legacy_bp.route("/dsd/", methods=["GET"])
def dsd_page():
    return _legacy().dsd_page()


@legacy_bp.route("/dsd.css", methods=["GET"])
def dsd_css():
    return _legacy().dsd_css()


@legacy_bp.route("/api/dsd/upload", methods=["POST"])
def api_dsd_upload():
    return _legacy().api_dsd_upload()


@legacy_bp.route("/api/dsd/iniciar", methods=["POST"])
def api_dsd_iniciar():
    return _legacy().api_dsd_iniciar()


@legacy_bp.route("/api/dsd/estado", methods=["GET"])
def api_dsd_estado():
    return _legacy().api_dsd_estado()


@legacy_bp.route("/api/dsd/descargar", methods=["GET"])
def api_dsd_descargar():
    return _legacy().api_dsd_descargar()


@legacy_bp.route("/<path:filename>", methods=["GET"])
def serve_static(filename: str):
    return _legacy().serve_static(filename)
