# Plan de Mantenimiento

La refactorizacion principal ya saco de la app modular los flujos sin interfaz
activa y dejo el sistema centrado en FactuVal y DSD.

## Estado Actual

- `api/pages.py` sirve las pantallas visibles.
- `api/facturas.py` maneja FactuVal.
- `api/dsd.py` maneja Consulta DSD.
- `services/dsd_service.py` contiene la logica DSD.
- `legacy/invoice_legacy.py` queda solo como compatibilidad de facturas.
- No se registra servidor legacy en Flask.

## Reglas

1. No agregar endpoints sin pantalla o consumidor confirmado.
2. Mantener la logica nueva en `api/`, `services/`, `utils/` y `models/`.
3. Mantener `legacy/` solo para compatibilidad de facturas.
4. Cada nueva ruta visible debe tener prueba en `tests/test_app_routes.py`.
5. Cada cambio en Excel, parser, validacion o DSD debe tener prueba enfocada.
6. Mantener estables los endpoints activos:

```text
/
/facturas
/dsd
/upload
/resultado
/descargar_excel
/api/dsd/*
/api/health
```

## Proximos Pasos Recomendados

- Revisar `docs/FLUJO_FACTURAS.md` y alinearlo con el pipeline modular actual.
- Agregar pruebas de API DSD usando `client.post("/api/dsd/upload")`.
- Reducir dependencias si algun paquete deja de usarse.
- Convertir los diccionarios de facturas en modelos de dominio cuando el flujo
  este estable.
