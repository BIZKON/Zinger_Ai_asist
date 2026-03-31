"""Tests for rate limiting middleware."""

from bot.middleware.rate_limit import _current_minute, RateLimitMiddleware


def test_current_minute_format():
    minute = _current_minute()
    assert len(minute) == 12  # YYYYMMDDHHmm
    assert minute.isdigit()


def test_rate_limit_middleware_init():
    m = RateLimitMiddleware(limit=10)
    assert m.limit == 10


def test_rate_limit_middleware_default():
    m = RateLimitMiddleware()
    assert m.limit > 0
