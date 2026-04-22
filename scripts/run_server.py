from __future__ import annotations

from facturas_app.app import create_app
from facturas_app.config import get_settings


def main() -> None:
    """Run Flask server using centralized configuration."""
    settings = get_settings()
    app = create_app(settings)
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.flask_debug,
        threaded=True,
    )


if __name__ == "__main__":
    main()
