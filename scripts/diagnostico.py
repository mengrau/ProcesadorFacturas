from __future__ import annotations

import importlib
from pathlib import Path

from facturas_app.app import create_app
from facturas_app.config import ensure_directories, get_settings
from facturas_app.legacy.bridge import get_invoice_legacy, get_server_legacy


def _check_dependency(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def main() -> None:
    """Run local diagnostics for server, dependencies and runtime folders."""
    settings = get_settings()

    print("=" * 72)
    print("DIAGNOSTICO DEL SERVIDOR DE FACTURAS (ARQUITECTURA MODULAR)")
    print("=" * 72)

    print("\n1. Configuracion activa")
    print(f"   BASE_PATH: {settings.base_path}")
    print(f"   FACTURAS_ROOT: {settings.facturas_root}")
    print(f"   FACTURAS_PATH: {settings.facturas_path}")
    print(f"   EXCEL_SALIDA: {settings.excel_salida}")

    print("\n2. Verificando estructura de carpetas")
    ensure_directories(settings)
    required_paths = [
        settings.facturas_root,
        settings.facturas_path,
        settings.facturas_procesadas,
        settings.facturas_rechazados,
        settings.facturas_errores,
        settings.facturas_codigo_path,
        settings.dsd_temp_path,
    ]
    for path in required_paths:
        exists = path.exists()
        marker = "[OK]" if exists else "[FALTA]"
        print(f"   {marker} {path}")

    print("\n3. Verificando modulo legacy de facturas")
    legacy_invoice = get_invoice_legacy()
    print(f"   [OK] Modulo cargado: {legacy_invoice.__name__}")
    print(
        f"   [OK] procesar_facturas disponible: {hasattr(legacy_invoice, 'procesar_facturas')}"
    )
    print(
        f"   [OK] _es_factura_valida disponible: {hasattr(legacy_invoice, '_es_factura_valida')}"
    )

    print("\n4. Verificando modulo legacy de servidor")
    legacy_server = get_server_legacy()
    print(f"   [OK] Modulo cargado: {legacy_server.__name__}")
    print(f"   [OK] app legacy disponible: {hasattr(legacy_server, 'app')}")

    print("\n5. Verificando dependencias principales")
    dependencies = [
        "flask",
        "flask_cors",
        "pandas",
        "pdfplumber",
        "openpyxl",
        "xlsxwriter",
    ]
    for dependency in dependencies:
        marker = "[OK]" if _check_dependency(dependency) else "[ERROR]"
        print(f"   {marker} {dependency}")

    print("\n6. Verificando app factory")
    app = create_app(settings)
    print(f"   [OK] Flask app creada: {app is not None}")
    print(f"   [OK] MAX_CONTENT_LENGTH: {app.config.get('MAX_CONTENT_LENGTH')}")

    print("\n7. Validando archivos UI")
    expected_ui_files = [
        settings.facturas_codigo_path / "index.html",
        settings.facturas_codigo_path / "styles.css",
    ]
    for file_path in expected_ui_files:
        marker = "[OK]" if file_path.exists() else "[FALTA]"
        print(f"   {marker} {file_path}")

    print("\n" + "=" * 72)
    print("DIAGNOSTICO COMPLETADO")
    print("=" * 72)
    print("\nPara iniciar el servidor:")
    print("  python server.py")
    print("\nO usando script:")
    print("  python scripts/run_server.py")


if __name__ == "__main__":
    main()
