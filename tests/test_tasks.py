"""Tests for task handler utilities."""

from bot.handlers.tasks import _detect_priority


def test_detect_priority_urgent():
    assert _detect_priority("Срочно позвонить клиенту") == "urgent"
    assert _detect_priority("Критично: сервер упал") == "urgent"


def test_detect_priority_high():
    assert _detect_priority("Важно: проверить отгрузку") == "high"


def test_detect_priority_low():
    assert _detect_priority("Когда-нибудь обновить сайт") == "low"


def test_detect_priority_medium():
    assert _detect_priority("Позвонить Иванову") == "medium"
    assert _detect_priority("Проверить накладную") == "medium"
