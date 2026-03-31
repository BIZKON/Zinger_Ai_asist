"""Tests for 1С OData service."""

from bot.services.one_c import (
    OneCClient,
    format_waybill,
    format_waybills_list,
    format_contractor,
    format_order,
)


def test_client_not_configured():
    client = OneCClient()
    # With empty settings, should not be configured
    assert not client.is_configured or client.base_url == ""


def test_format_waybill():
    wb = {
        "Number": "А-2847",
        "Date": "2026-03-15T10:00:00",
        "Status": "Отгружена",
        "Contractor": "ООО Ромашка",
        "Amount": "150000",
    }
    result = format_waybill(wb)
    assert "А-2847" in result
    assert "2026-03-15" in result
    assert "Отгружена" in result
    assert "Ромашка" in result
    assert "150000" in result


def test_format_waybills_list_empty():
    assert "не найдено" in format_waybills_list([])


def test_format_waybills_list():
    waybills = [
        {"Number": "001", "Status": "Новая"},
        {"Number": "002", "Status": "В пути"},
    ]
    result = format_waybills_list(waybills)
    assert "001" in result
    assert "002" in result


def test_format_contractor():
    c = {
        "Description": "ООО Логистик Про",
        "ИНН": "7812345678",
        "Телефон": "+7-812-555-1234",
    }
    result = format_contractor(c)
    assert "Логистик Про" in result
    assert "7812345678" in result
    assert "555-1234" in result


def test_format_order():
    o = {
        "Number": "З-100",
        "Date": "2026-03-20T09:00:00",
        "Status": "В обработке",
        "Contractor": "ИП Сидоров",
    }
    result = format_order(o)
    assert "З-100" in result
    assert "В обработке" in result
    assert "Сидоров" in result


def test_format_waybill_minimal():
    """Minimal waybill with only Number."""
    wb = {"Number": "X-1"}
    result = format_waybill(wb)
    assert "X-1" in result
