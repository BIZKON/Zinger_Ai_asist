"""Tests for notifications service."""

from datetime import date

from bot.services.notifications import _parse_date, SCENARIOS


def test_parse_date_dot_format():
    d = _parse_date("15.03.1990")
    assert d == date(1990, 3, 15)


def test_parse_date_iso():
    d = _parse_date("1990-03-15")
    assert d == date(1990, 3, 15)


def test_parse_date_short():
    d = _parse_date("15.03")
    assert d is not None
    assert d.month == 3
    assert d.day == 15


def test_parse_date_in_text():
    d = _parse_date("ДР жены 25.06.1992")
    assert d is not None
    assert d.month == 6
    assert d.day == 25


def test_parse_date_none():
    assert _parse_date("") is None
    assert _parse_date("какой-то текст") is None


def test_scenarios_have_required_fields():
    for s in SCENARIOS:
        assert "id" in s, f"Scenario missing id: {s}"
        assert "category" in s, f"Scenario {s['id']} missing category"
        assert "template" in s, f"Scenario {s['id']} missing template"


def test_scenarios_unique_ids():
    ids = [s["id"] for s in SCENARIOS]
    assert len(ids) == len(set(ids)), "Duplicate scenario IDs"
