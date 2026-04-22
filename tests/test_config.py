from __future__ import annotations

from pathlib import Path

from facturas_app.config import Settings


def test_settings_from_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BASE_PATH", str(tmp_path))
    monkeypatch.setenv("FACTURAS_ROOT", str(tmp_path / "Facturas"))
    monkeypatch.setenv("MAX_CONTENT_LENGTH_MB", "50")
    monkeypatch.setenv("FLASK_PORT", "5055")
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000")

    settings = Settings.from_env()

    assert settings.base_path == tmp_path
    assert settings.facturas_root == tmp_path / "Facturas"
    assert settings.max_content_length_mb == 50
    assert settings.max_content_length_bytes == 50 * 1024 * 1024
    assert settings.flask_port == 5055
    assert settings.flask_debug is True
    assert settings.cors_origins == (
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    )
