from __future__ import annotations

from facturas_app.services.invoice_parser import (
    clean_product_description,
    extract_customer,
    extract_expedition_date,
    extract_generation_date,
    extract_invoice_number,
    extract_products,
    format_number,
    normalize_customer_name,
    normalize_number,
)


def test_normalize_number_handles_common_formats() -> None:
    assert normalize_number("1.234,56") == "1234.56"
    assert normalize_number("1,234.56") == "1234.56"
    assert normalize_number("1234,56") == "1234.56"
    assert normalize_number("1,234") == "1.234"
    assert normalize_number("1234") == "1234"


def test_format_number_uses_colombian_separators() -> None:
    assert format_number("1234.56") == "1.234,56"
    assert format_number("1234.567") == "1.234,567"
    assert format_number("no-numero") == "no-numero"


def test_extract_invoice_number_from_text() -> None:
    text = "FACTURA ELECTRÓNICA DE VENTA No. FE12345\nCLIENTE: 900.123.456-7"

    assert extract_invoice_number(text) == "FE12345"


def test_extract_customer_fields_from_invoice_text() -> None:
    text = """
    CLIENTE: 900.123.456-7
    GREEN POINT DISTRIBUIDORA LA 80 S.A.S.
    COD. CLIENTE 100200
    FECHA GENERACIÓN 01/02/2025 10:20:30
    """

    nit, name, code = extract_customer(text)

    assert nit == "900.123.456-7"
    assert name == "Distribuidora La S.A.S."
    assert code == "100200"


def test_extract_dates_from_invoice_text() -> None:
    text = """
    FECHA GENERACIÓN 01/02/2025 10:20:30
    FECHA DE EXPEDICIÓN: 03/02/2025
    """

    assert extract_generation_date(text) == "01/02/2025"
    assert extract_expedition_date(text) == "03/02/2025"


def test_extract_expedition_date_returns_empty_when_only_place_context_exists() -> None:
    text = """
    LUGAR DE EXPEDICIÓN: MEDELLIN
    FECHA DE EMISIÓN 04/02/2025
    """

    assert extract_expedition_date(text) == ""


def test_clean_product_description_removes_noise() -> None:
    assert (
        clean_product_description("001. Gaseosa Manzana 2.5L @@@")
        == "Gaseosa Manzana 2.5L"
    )
    assert normalize_customer_name("GREEN POINT ACME S.A.S. 123") == "Acme S.A.S."


def test_extract_products_from_invoice_lines() -> None:
    text = """
    Encabezado que no aplica
    123456 GASEOSA MANZANA 2.5L PZA 2 1.000,00 2.000,00 19 2.380,00
    987654 AGUA CRISTAL SIX 1 500,00 500,00 0 500,00
    """

    products = extract_products(text)

    assert products == [
        (
            "123456",
            "GASEOSA MANZANA 2.5L",
            "PZA",
            "2",
            "1000.00",
            "19.00",
            "2380.00",
            "OK",
            "GASEOSA MANZANA 2.5L",
            "",
        ),
        (
            "987654",
            "AGUA CRISTAL",
            "SIX",
            "1",
            "500.00",
            "0.00",
            "500.00",
            "OK",
            "AGUA CRISTAL",
            "",
        ),
    ]
