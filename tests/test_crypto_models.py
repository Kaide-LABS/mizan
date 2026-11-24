"""Tests for mizan/crypto/models.py — CandleBar validation and row parsing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from mizan.crypto.models import (
    CandleBar,
    MalformedCandleRowError,
    _parse_coinbase_row,
    _parse_kraken_row,
)


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "exchange": "coinbase",
        "symbol": "BTC",
        "granularity": "1d",
        "ts": datetime(2024, 1, 1, tzinfo=UTC),
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "volume": 10.0,
        "source": "coinbase_exchange_api",
    }
    defaults.update(overrides)
    return defaults


def test_candle_bar_happy_path() -> None:
    bar = CandleBar(**_valid_kwargs())  # type: ignore[arg-type]
    assert bar.open == 1.0
    assert bar.close == 1.5


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_candle_bar_rejects_non_positive_price_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        CandleBar(**_valid_kwargs(**{field: 0.0}))  # type: ignore[arg-type]


def test_candle_bar_rejects_a_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        CandleBar(**_valid_kwargs(ts=datetime(2024, 1, 1)))  # type: ignore[arg-type]


def test_candle_bar_rejects_a_non_utc_aware_datetime() -> None:
    import datetime as dt

    offset_tz = dt.timezone(timedelta(hours=5))
    with pytest.raises(ValidationError):
        CandleBar(**_valid_kwargs(ts=datetime(2024, 1, 1, tzinfo=offset_tz)))  # type: ignore[arg-type]


def test_parse_coinbase_row_reorders_fields_correctly() -> None:
    # Coinbase wire order: [time, low, high, open, close, volume]
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    row = [ts.timestamp(), 0.5, 2.0, 1.0, 1.5, 10.0]
    parsed_ts, opening, high, low, close, volume = _parse_coinbase_row(row)
    assert parsed_ts == ts
    assert (opening, high, low, close, volume) == (1.0, 2.0, 0.5, 1.5, 10.0)


def test_parse_coinbase_row_rejects_wrong_length() -> None:
    with pytest.raises(MalformedCandleRowError):
        _parse_coinbase_row([1.0, 2.0, 3.0])


def test_parse_kraken_row_happy_path() -> None:
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    row: list[object] = [ts.timestamp(), 1.0, 2.0, 0.5, 1.5, "1.1", 10.0, 5]
    parsed_ts, opening, high, low, close, volume = _parse_kraken_row(row)
    assert parsed_ts == ts
    assert (opening, high, low, close, volume) == (1.0, 2.0, 0.5, 1.5, 10.0)


def test_parse_kraken_row_rejects_wrong_length() -> None:
    with pytest.raises(MalformedCandleRowError):
        _parse_kraken_row([1.0, 2.0])


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_parse_rejects_nan_and_infinity_rows(bad_value: float) -> None:
    ts = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    coinbase_row = [ts, 0.5, 2.0, 1.0, bad_value, 10.0]
    with pytest.raises(MalformedCandleRowError):
        _parse_coinbase_row(coinbase_row)

    kraken_row: list[object] = [ts, 1.0, 2.0, 0.5, bad_value, "1.1", 10.0, 5]
    with pytest.raises(MalformedCandleRowError):
        _parse_kraken_row(kraken_row)
