"""Tests for Telegram WebApp auth validation."""

from bot.api.auth import validate_init_data


def test_validate_empty():
    assert validate_init_data("") is None
    assert validate_init_data(None) is None


def test_validate_no_hash():
    assert validate_init_data("user=%7B%7D") is None


def test_validate_invalid_hash():
    result = validate_init_data("user=%7B%22id%22%3A123%7D&hash=invalidhash")
    assert result is None
