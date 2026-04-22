from __future__ import annotations

from facturas_app.app import create_app
from facturas_app.config import get_settings
from facturas_app.legacy.bridge import get_invoice_legacy

# Backward-compatible exports expected by existing diagnostics scripts.
main_facturas = get_invoice_legacy()
procesar_facturas = getattr(main_facturas, "procesar_facturas", None)

app = create_app()


if __name__ == "__main__":
    settings = get_settings()

    print("=" * 60)
    print("SERVIDOR UNIFICADO - POSTOBON S.A. (Arquitectura Modular)")
    print("=" * 60)
    print("Servidor ejecutandose en:")
    print(f"  http://localhost:{settings.flask_port}")
    print(f"  http://127.0.0.1:{settings.flask_port}")
    print("=" * 60)
    print("Aplicaciones disponibles:")
    print(f"  - Menu Principal:           http://localhost:{settings.flask_port}/")
    print(
        f"  - FactuVal:                 http://localhost:{settings.flask_port}/facturas"
    )
    print(
        f"  - Validador de Diferencias: http://localhost:{settings.flask_port}/diferencias"
    )
    print(
        f"  - Validador de Listas:      http://localhost:{settings.flask_port}/listas"
    )
    print(
        f"  - Actualizador de Portafolios: http://localhost:{settings.flask_port}/portafolios"
    )
    print(f"  - Consulta de pedidos DSD:  http://localhost:{settings.flask_port}/dsd")
    print("=" * 60)

    app.run(
        debug=settings.flask_debug,
        host=settings.flask_host,
        port=settings.flask_port,
        threaded=True,
    )
