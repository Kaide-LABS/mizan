"""Tests for mizan/crypto/ingest_coinbase.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mizan.crypto.ingest_coinbase import (
    CoinbaseProductNotFoundError,
    fetch_coinbase_candles,
)


def _coinbase_row(ts: datetime, *, low: float, high: float, opening: float, close: float,
                   volume: float) -> list[float]:
    return [ts.timestamp(), low, high, opening, close, volume]


def test_fetch_coinbase_candles_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The on-disk cache key embeds an ISO-8601 window boundary (colons included), which Windows
    # filesystems reject as a path character -- irrelevant to what this test actually proves (row
    # parsing/field-reordering), so the cache write is stubbed out here rather than exercising an
    # unrelated, pre-existing cross-platform cache-key limitation.
    monkeypatch.setattr("mizan.crypto.ingest_coinbase.write_raw_json", lambda path, payload: None)
    monkeypatch.setattr("mizan.crypto.ingest_coinbase.is_cached", lambda path: False)

    ts = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [_coinbase_row(ts, low=0.5, high=2.0, opening=1.0, close=1.5, volume=10.0)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(rows).encode())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    bars = fetch_coinbase_candles(
        "BTC", granularity="1d", start=ts, end=ts + timedelta(days=1), client=client,
        cache_dir=tmp_path,
    )
    assert len(bars) == 1
    bar = bars[0]
    assert (bar.open, bar.high, bar.low, bar.close, bar.volume) == (1.0, 2.0, 0.5, 1.5, 10.0)


def test_fetch_coinbase_candles_raises_on_404(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(CoinbaseProductNotFoundError):
        fetch_coinbase_candles(
            "BTC",
            granularity="1d",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
            client=client,
            cache_dir=tmp_path,
        )
