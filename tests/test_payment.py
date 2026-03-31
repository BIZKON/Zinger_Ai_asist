"""Tests for payment service."""

from bot.services.payment import TIERS, format_tier_info, format_all_tiers


def test_tiers_have_required_fields():
    for key, tier in TIERS.items():
        assert "price" in tier, f"{key} missing price"
        assert "name" in tier, f"{key} missing name"
        assert "description" in tier, f"{key} missing description"
        assert tier["price"] > 0, f"{key} price must be positive"


def test_format_tier_info():
    result = format_tier_info("pro")
    assert "Pro" in result
    assert "1490" in result


def test_format_tier_info_invalid():
    result = format_tier_info("nonexistent")
    assert "не найден" in result


def test_format_all_tiers():
    result = format_all_tiers()
    assert "Free" in result
    assert "Starter" in result
    assert "Pro" in result
    assert "Business" in result


def test_tier_prices_ascending():
    prices = [TIERS[t]["price"] for t in ("starter", "pro", "business")]
    assert prices == sorted(prices)
