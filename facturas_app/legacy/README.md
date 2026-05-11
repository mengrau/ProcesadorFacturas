# Legacy Layer

Esta carpeta mantiene solo compatibilidad historica del procesamiento de
facturas.

- `invoice_legacy.py`: wrappers de compatibilidad para nombres antiguos.
- `bridge.py`: carga cacheada del modulo legacy de facturas.

Los endpoints historicos que no estan en la interfaz actual fueron retirados de
la app modular. La evolucion debe hacerse en las capas `api`, `services`,
`utils` y `models`.
