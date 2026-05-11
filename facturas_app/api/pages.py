from __future__ import annotations

from flask import Blueprint, current_app, send_from_directory

from facturas_app.config import Settings, get_settings

pages_bp = Blueprint("pages", __name__)


def _get_settings() -> Settings:
    settings = current_app.config.get("SETTINGS")
    if isinstance(settings, Settings):
        return settings
    return get_settings()


@pages_bp.route("/", methods=["GET"])
def index():
    settings = _get_settings()
    return send_from_directory(str(settings.web_assets_path), "index.html")


@pages_bp.route("/styles.css", methods=["GET"])
def styles():
    settings = _get_settings()
    return send_from_directory(
        str(settings.web_assets_path),
        "styles.css",
        mimetype="text/css",
        max_age=0,
    )


@pages_bp.route("/dsd", methods=["GET"])
@pages_bp.route("/dsd/", methods=["GET"])
def dsd_page():
    settings = _get_settings()
    return send_from_directory(str(settings.web_assets_path), "dsd.html")


@pages_bp.route("/dsd.css", methods=["GET"])
def dsd_css():
    settings = _get_settings()
    return send_from_directory(
        str(settings.web_assets_path),
        "dsd.css",
        mimetype="text/css",
        max_age=0,
    )
