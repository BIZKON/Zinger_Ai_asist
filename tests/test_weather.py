"""Tests for weather service."""

from bot.services.weather import _translate_condition, format_weather


def test_translate_condition():
    assert "Ясно" in _translate_condition("clear")
    assert "Дождь" in _translate_condition("rain")
    assert _translate_condition("unknown") == "unknown"


def test_format_weather():
    w = {
        "temp": 15,
        "feels_like": 12,
        "condition": "Ясно ☀️",
        "wind_speed": 3,
        "sunrise": "06:30",
        "sunset": "20:15",
        "city": "Санкт-Петербург",
    }
    result = format_weather(w)
    assert "15°C" in result
    assert "12°C" in result
    assert "06:30" in result


def test_format_weather_none():
    assert "недоступна" in format_weather(None)
    assert "недоступна" in format_weather({})
