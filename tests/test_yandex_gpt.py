"""Tests for YandexGPT integration in bot/services/llm.py."""

from bot.services.llm import _yandex_messages, _yandex_model_uri
from bot.config import settings


def test_yandex_messages_format():
    """Convert OpenAI-style messages to YandexGPT format (content → text)."""
    oai = [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуйте!"},
    ]
    result = _yandex_messages(oai, system_prompt="")
    assert result == [
        {"role": "user", "text": "Привет"},
        {"role": "assistant", "text": "Здравствуйте!"},
    ]


def test_yandex_messages_with_system_prompt():
    """System prompt должен стать первым сообщением с role=system."""
    result = _yandex_messages(
        [{"role": "user", "content": "Q"}],
        system_prompt="Ты бот.",
    )
    assert result[0] == {"role": "system", "text": "Ты бот."}
    assert result[1] == {"role": "user", "text": "Q"}


def test_yandex_model_uri_format():
    """modelUri должен быть в формате gpt://<folder_id>/<model>/latest."""
    settings.yandex_gpt_folder_id = "b1g_test_folder"
    uri = _yandex_model_uri("yandexgpt")
    assert uri == "gpt://b1g_test_folder/yandexgpt/latest"

    uri_lite = _yandex_model_uri("yandexgpt-lite")
    assert uri_lite == "gpt://b1g_test_folder/yandexgpt-lite/latest"


def test_yandex_empty_messages():
    """Пустой список сообщений — пустой результат."""
    result = _yandex_messages([], system_prompt="")
    assert result == []
