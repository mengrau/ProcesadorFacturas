"""Legacy adapters that preserve the original business logic unchanged."""

from facturas_app.legacy.bridge import get_invoice_legacy, get_server_legacy

__all__ = ["get_invoice_legacy", "get_server_legacy"]
