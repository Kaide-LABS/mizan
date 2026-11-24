"""Normalized crypto candles; see ``docs/crypto/PHASE_2_SPEC.md`` §A2."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import cast

from pydantic import Field, field_validator

from mizan.core.base import MizanBaseModel


class MalformedCandleRowError(ValueError):
    """Raised when an exchange's positional candle row is malformed."""


class CandleBar(MizanBaseModel):
    exchange: str
    symbol: str
    granularity: str
    ts: datetime
    open: float = Field(gt=0.0)
    high: float = Field(gt=0.0)
    low: float = Field(gt=0.0)
    close: float = Field(gt=0.0)
    volume: float = Field(ge=0.0)
    source: str = Field(min_length=1)

    @field_validator("ts")
    @classmethod
    def _utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("candle timestamp must be timezone-aware UTC")
        if value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("candle timestamp must be UTC")
        return value


def _finite(value: object) -> float:
    result = float(cast(float, value))
    if not math.isfinite(result):
        raise MalformedCandleRowError("candle row contains a non-finite value")
    return result


def _parse_coinbase_row(row: list[float]) -> tuple[datetime, float, float, float, float, float]:
    if len(row) != 6:
        raise MalformedCandleRowError("Coinbase candle row must contain six values")
    timestamp, low, high, opening, close, volume = (_finite(item) for item in row)
    return datetime.fromtimestamp(timestamp, tz=UTC), opening, high, low, close, volume


def _parse_kraken_row(row: list[object]) -> tuple[datetime, float, float, float, float, float]:
    if len(row) != 8:
        raise MalformedCandleRowError("Kraken OHLC row must contain eight values")
    timestamp, opening, high, low, close, _vwap, volume, _count = (_finite(item) for item in row)
    return datetime.fromtimestamp(timestamp, tz=UTC), opening, high, low, close, volume
