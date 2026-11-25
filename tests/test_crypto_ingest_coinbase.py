"""Tests for mizan/crypto/ingest_coinbase.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mizan.crypto.ingest_coinbase import (
    CoinbaseProductNotFoundError,
    _key_stamp,
    fetch_coinbase_candles,
)


def _coinbase_row(ts: datetime, *, low: float, high: float, opening: float, close: float,
                   volume: float) -> list[float]:
    return [ts.timestamp(), low, high, opening, close, volume]


def test_fetch_coinbase_candles_happy_path(tmp_path: Path) -> None:
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


_WINDOWS_ILLEGAL = set(r'<>:"/\|?*')


def test_key_stamp_has_no_windows_illegal_characters() -> None:
    stamp = _key_stamp(datetime(2024, 1, 1, 13, 45, 7, tzinfo=UTC))
    assert not (set(stamp) & _WINDOWS_ILLEGAL)
    assert stamp.startswith("2024-01-01T13-45-07")


def test_fetch_coinbase_candles_writes_real_cache_file_and_reuses_it(tmp_path: Path) -> None:
    """Unstubbed: a real cache directory, real filenames (regression for the Windows colon bug)."""
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [_coinbase_row(ts, low=0.5, high=2.0, opening=1.0, close=1.5, volume=10.0)]
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=json.dumps(rows).encode())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    end = ts + timedelta(days=1)
    first = fetch_coinbase_candles(
        "BTC", granularity="1d", start=ts, end=end, client=client, cache_dir=tmp_path
    )
    files = list((tmp_path / "coinbase" / "candles").glob("*.json"))
    assert len(files) == 1
    assert not (set(files[0].name) & _WINDOWS_ILLEGAL)
    # request parameters keep the exact ISO-8601 form (colons intact)
    assert ":" in calls[0].url.params["start"]
    second = fetch_coinbase_candles(
        "BTC", granularity="1d", start=ts, end=end, client=client, cache_dir=tmp_path
    )
    assert second == first
    assert len(calls) == 1, "the second call is served from the on-disk cache"
