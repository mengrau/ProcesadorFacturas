"""Compatibility wrapper for the modular invoice processing architecture.

This module preserves the original import path used by legacy scripts and UI code.
Business logic remains unchanged in facturas_app.legacy.invoice_legacy.
"""

from facturas_app.legacy.invoice_legacy import *  # noqa: F401,F403


if __name__ == "__main__":
    procesar_facturas()
