"""Tests for bot configuration."""

from bot.config import Settings


def test_settings_defaults():
    s = Settings(bot_token="test:token")
    assert s.postgres_db == "personalai"
    assert s.default_persona == "sergiy"
    assert s.default_voice_id == "Maxim"
    assert not s.is_production


def test_database_url():
    s = Settings(bot_token="test:token")
    assert "asyncpg" in s.database_url
    assert "personalai" in s.database_url


def test_admin_ids_parsing():
    s = Settings(bot_token="test:token", admin_user_ids="123,456,789")
    assert s.admin_ids == [123, 456, 789]


def test_admin_ids_empty():
    s = Settings(bot_token="test:token", admin_user_ids="")
    assert s.admin_ids == []
