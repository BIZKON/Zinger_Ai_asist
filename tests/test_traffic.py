"""Tests for traffic service."""

from bot.services.traffic import format_traffic


def test_format_traffic_free():
    t = {
        "duration_min": 15,
        "duration_traffic_min": 18,
        "distance_km": 12.5,
        "jams_level": 2,
    }
    result = format_traffic(t)
    assert "12.5 км" in result
    assert "Свободно" in result


def test_format_traffic_heavy():
    t = {
        "duration_min": 15,
        "duration_traffic_min": 45,
        "distance_km": 12.5,
        "jams_level": 8,
    }
    result = format_traffic(t)
    assert "Серьёзные" in result


def test_format_traffic_none():
    assert "недоступны" in format_traffic(None)
    assert "недоступны" in format_traffic({})
