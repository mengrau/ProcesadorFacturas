# Automatizacion de Facturas - Arquitectura Modular

Este proyecto automatiza la gestion de facturas PDF, validacion de archivos, procesamiento a Excel y exposicion de API web para integraciones operativas.

La logica de negocio original se mantiene sin cambios en la capa legacy, pero ahora esta encapsulada dentro de una arquitectura modular, tipada y testeable.

## Objetivos de la refactorizacion

- Separar responsabilidades por capas: API, servicios, utilidades, modelos y configuracion.
- Mantener compatibilidad con los flujos actuales (server.py, cod_facturas/main.py, iniciar_servidor.bat).
- Mejorar seguridad de carga de archivos y control de rutas.
- Estandarizar respuestas JSON y manejo de errores.
- Facilitar pruebas unitarias con pytest.

## Estructura del proyecto

```text
Facturas/
  facturas_app/
    api/
      facturas.py
      health.py
      legacy_proxy.py
    services/
      invoice_service.py
    utils/
      file_security.py
      responses.py
    models/
      dto.py
    legacy/
      invoice_legacy.py
      server_legacy.py
      bridge.py
    app.py
    config.py
    logging_config.py
  scripts/
    run_server.py
    diagnostico.py
  tests/
    test_config.py
    test_file_security.py
    test_invoice_service.py
  server.py
  verificar_servidor.py
  iniciar_servidor.bat
  cod_facturas/main.py
```

## Capas implementadas

- API:
  - Blueprints de Flask para separar dominios.
  - Endpoint de salud en `/api/health`.
  - Endpoint de facturas modernizado con validacion de entrada y sanitizacion de archivos.
  - Proxy controlado para endpoints legacy (listas, diferencias, portafolios, dsd).

- Servicios:
  - `InvoiceService` como facade tipada sobre la logica legacy.
  - Facilita pruebas y reemplazo futuro de implementaciones.

- Seguridad:
  - Sanitizacion de nombres de archivo (`secure_filename`).
  - Restriccion por extensiones permitidas.
  - Resolucion segura de rutas para evitar traversal.
  - Limite de tamano de carga configurable (`MAX_CONTENT_LENGTH_MB`).

- Configuracion:
  - `facturas_app/config.py` centraliza variables y paths.
  - Soporte de `.env` (si `python-dotenv` esta instalado).
  - Archivo ejemplo en `.env.example`.

- Logging:
  - Configuracion profesional con salida a consola y archivo rotativo (`logs/app.log`).

## Ejecucion local (Windows)

1. Crear y activar entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. (Opcional) Configurar variables:

- Copia `.env.example` a `.env` y ajusta rutas.

4. Ejecutar diagnostico:

```powershell
python verificar_servidor.py
```

5. Iniciar servidor:

```powershell
python server.py
```

Tambien puedes iniciar con el batch:

```bat
iniciar_servidor.bat
```

## Pruebas unitarias

```powershell
pytest
```

Incluye pruebas para:

- Configuracion (`test_config.py`).
- Seguridad de archivos y rutas (`test_file_security.py`).
- Servicio de facturas y contrato con capa legacy (`test_invoice_service.py`).

## Compatibilidad y migracion

- `cod_facturas/main.py` ahora es un wrapper de compatibilidad.
- `server.py` ahora inicializa la app modular.
- La logica original se preserva en:
  - `facturas_app/legacy/invoice_legacy.py`
  - `facturas_app/legacy/server_legacy.py`

Esto permite evolucionar la arquitectura sin romper la operacion actual.
