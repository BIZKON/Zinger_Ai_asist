"""Tests for research service."""

from bot.services.research import _detect_depth


def test_detect_depth_quick():
    assert _detect_depth("что такое OData") == "quick"
    assert _detect_depth("какой курс доллара") == "quick"


def test_detect_depth_deep():
    assert _detect_depth("исследуй рынок грузоперевозок СПб за 2025 год") == "deep"
    assert _detect_depth("сделай подробный анализ конкурентов в логистике") == "deep"


def test_detect_depth_medium():
    assert _detect_depth("тарифы на грузоперевозки из СПб в Москву") == "medium"
