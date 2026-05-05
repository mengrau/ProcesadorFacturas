from __future__ import annotations

from facturas_app.services.invoice_validator import (
    INVALID_INVOICE_MESSAGE,
    InvoiceValidator,
    validate_invoice_pdf,
)


def _valid_invoice_text() -> str:
    return """
    POSTOBON S.A.
    FACTURA ELECTRÓNICA DE VENTA No. FE12345
    CLIENTE: 90012345
    COD. CLIENTE 100200
    PZA
    TOTAL 1.234,56
    """


def test_validate_text_accepts_valid_invoice_content() -> None:
    validator = InvoiceValidator()

    is_valid, message = validator.validate_text(_valid_invoice_text())

    assert is_valid is True
    assert message == "Archivo válido"


def test_validate_text_rejects_content_without_required_indicators() -> None:
    validator = InvoiceValidator()

    is_valid, message = validator.validate_text("Documento cualquiera sin señales")

    assert is_valid is False
    assert message == INVALID_INVOICE_MESSAGE


def test_validate_text_rejects_when_cliente_label_is_missing() -> None:
    validator = InvoiceValidator()
    text = """
    POSTOBON
    FACTURA DE VENTA No. FE222
    COD. CLIENTE 100200
    PZA
    TOTAL 1000,00
    """

    is_valid, message = validator.validate_text(text)

    assert is_valid is False
    assert message == INVALID_INVOICE_MESSAGE


def test_validate_text_rejects_when_units_are_missing() -> None:
    validator = InvoiceValidator()
    text = """
    POSTOBON
    FACTURA DE VENTA No. FE333
    CLIENTE: 90012345
    COD. CLIENTE 100200
    TOTAL 1000,00
    """

    is_valid, message = validator.validate_text(text)

    assert is_valid is False
    assert message == INVALID_INVOICE_MESSAGE


def test_validate_text_emits_debug_messages_when_callback_is_provided() -> None:
    messages: list[str] = []
    validator = InvoiceValidator(debug_callback=messages.append)

    validator.validate_text(_valid_invoice_text())

    assert any("Indicadores encontrados" in message for message in messages)
    assert any("Contiene POSTOBON" in message for message in messages)


def test_validate_invoice_pdf_returns_read_error_for_non_existing_file() -> None:
    is_valid, message = validate_invoice_pdf("archivo_que_no_existe.pdf")

    assert is_valid is False
    assert message.startswith("Error al leer el archivo:")
