"""
Script de diagnóstico para verificar el estado del servidor de facturas
"""

import os
import sys

BASE_PATH = r"C:\Users\pracrmofc\OneDrive - Gaseosas Postobon S.A\Escritorio\Automatizaciones_postobon"
FACTURAS_CODIGO_PATH = os.path.join(BASE_PATH, "Facturas", "cod_facturas")

print("=" * 60)
print("DIAGNÓSTICO DEL SERVIDOR DE FACTURAS")
print("=" * 60)

main_path = os.path.join(FACTURAS_CODIGO_PATH, "main.py")
print(f"\n1. Verificando archivo main.py...")
print(f"   Ruta: {main_path}")
print(f"   Existe: {os.path.exists(main_path)}")

if os.path.exists(main_path):
    print(f"   Tamaño: {os.path.getsize(main_path)} bytes")
else:
    print("   ERROR: El archivo main.py no existe!")
    sys.exit(1)

print(f"\n2. Intentando cargar el módulo...")
try:
    import importlib.util

    spec = importlib.util.spec_from_file_location("main_facturas", main_path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print("   [OK] Modulo cargado exitosamente")

        if hasattr(mod, "procesar_facturas"):
            print("   [OK] Funcion 'procesar_facturas' encontrada")
            print(f"   Tipo: {type(mod.procesar_facturas)}")
        else:
            print("   ERROR: La funcion 'procesar_facturas' no existe en el modulo")

        if hasattr(mod, "_es_factura_valida"):
            print("   [OK] Funcion '_es_factura_valida' encontrada")
        else:
            print("   ADVERTENCIA: La funcion '_es_factura_valida' no existe")

        if hasattr(mod, "mover_archivo_seguro"):
            print("   [OK] Funcion 'mover_archivo_seguro' encontrada")
        else:
            print("   ADVERTENCIA: La funcion 'mover_archivo_seguro' no existe")
    else:
        print("   ERROR: No se pudo crear el spec del módulo")
        sys.exit(1)
except Exception as e:
    print(f"   ERROR al cargar el módulo: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print(f"\n3. Verificando dependencias...")
dependencias = ["flask", "flask_cors", "pandas", "pdfplumber", "openpyxl"]

for dep in dependencias:
    try:
        __import__(dep)
        print(f"   [OK] {dep} instalado")
    except ImportError:
        print(f"   [ERROR] {dep} NO instalado")

print(f"\n4. Verificando estructura de carpetas...")
FACTURAS_ROOT = os.path.join(BASE_PATH, "Facturas")
FACTURAS_PATH = os.path.join(FACTURAS_ROOT, "entrada")
FACTURAS_RECHAZADOS = os.path.join(FACTURAS_ROOT, "rechazados")
FACTURAS_ERRORES = os.path.join(FACTURAS_ROOT, "errores")

carpetas = {
    "Facturas": FACTURAS_ROOT,
    "entrada": FACTURAS_PATH,
    "rechazados": FACTURAS_RECHAZADOS,
    "errores": FACTURAS_ERRORES,
    "cod_facturas": FACTURAS_CODIGO_PATH,
}

for nombre, ruta in carpetas.items():
    existe = os.path.exists(ruta)
    estado = "[OK]" if existe else "[FALTA]"
    print(f"   {nombre}: {estado} {ruta}")
    if not existe:
        print(f"      Creando carpeta...")
        os.makedirs(ruta, exist_ok=True)

print(f"\n5. Verificando si el servidor puede iniciarse...")
try:
    sys.path.insert(0, os.path.join(BASE_PATH, "Facturas"))
    from server import app, main_facturas, procesar_facturas

    print("   [OK] Modulo server importado correctamente")
    print(f"   main_facturas: {main_facturas is not None}")
    print(f"   procesar_facturas: {procesar_facturas is not None}")
    print(f"   app: {app is not None}")

    if main_facturas is None:
        print("   ERROR: main_facturas es None - el módulo no se cargó")
    if procesar_facturas is None:
        print("   ERROR: procesar_facturas es None - la función no se encontró")

except Exception as e:
    print(f"   ERROR al importar server: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 60)
print("\nSi todo está correcto, puedes iniciar el servidor con:")
print(f"  python {os.path.join(BASE_PATH, 'Facturas', 'server.py')}")
print("\nO desde el directorio Facturas:")
print("  cd Facturas")
print("  python server.py")
