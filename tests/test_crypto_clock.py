"""Tests for mizan/crypto/clock.py — the gap-free UTC crypto calendar."""

from __future__ import annotations

from datetime import date

from mizan.crypto.clock import generate_market_days


def test_generate_market_days_includes_weekends_and_arbitrary_calendar_dates() -> None:
    days = generate_market_days(date(2024, 7, 1), date(2024, 7, 8))
    assert date(2024, 7, 6) in days  # Saturday
    assert date(2024, 7, 7) in days  # Sunday
    assert date(2024, 7, 4) in days  # US-equity-market holiday (Independence Day)


def test_generate_market_days_is_pure_and_inclusive_of_both_endpoints() -> None:
    single = generate_market_days(date(2024, 1, 1), date(2024, 1, 1))
    assert single == (date(2024, 1, 1),)

    first = generate_market_days(date(2024, 1, 1), date(2024, 1, 5))
    second = generate_market_days(date(2024, 1, 1), date(2024, 1, 5))
    assert first == second
    assert first[0] == date(2024, 1, 1)
    assert first[-1] == date(2024, 1, 5)
