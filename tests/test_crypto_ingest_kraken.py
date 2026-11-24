"""Tests for mizan/crypto/ingest_kraken.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mizan.crypto.ingest_kraken import (
    KrakenPairNotFoundError,
    fetch_kraken_candles,
    resolve_kraken_pair,
)


def _asset_pairs_payload(*, status: str) -> dict[str, object]:
    return {
        "result": {
            "XXBTZUSD": {
                "altname": "XBTUSD",
                "base": "XXBT",
                "quote": "ZUSD",
                "status": status,
            }
        }
    }


def test_resolve_kraken_pair_rejects_a_non_online_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mizan.crypto.ingest_kraken.is_cached", lambda path: False)
    monkeypatch.setattr("mizan.crypto.ingest_kraken.write_raw_json", lambda path, payload: None)

    payload = _asset_pairs_payload(status="cancel_only")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(payload).encode())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(KrakenPairNotFoundError):
        resolve_kraken_pair("BTC", client=client, cache_dir=tmp_path)


def test_kraken_always_drops_the_last_open_candle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mizan.crypto.ingest_kraken.is_cached", lambda path: False)
    monkeypatch.setattr("mizan.crypto.ingest_kraken.write_raw_json", lambda path, payload: None)
    monkeypatch.setattr(
        "mizan.crypto.ingest_kraken.resolve_kraken_pair",
        lambda ticker, *, client, cache_dir: "XBTUSD",
    )

    base_ts = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    closed_row = [base_ts, "1.0", "2.0", "0.5", "1.5", "1.1", "10.0", 5]
    open_row = [base_ts + 86400, "99.0", "99.0", "99.0", "99.0", "99.0", "99.0", 1]
    raw_rows = [closed_row, open_row]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=json.dumps({"result": {"XBTUSD": raw_rows}}).encode()
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    bars = fetch_kraken_candles(ticker="BTC", granularity="1d", client=client, cache_dir=tmp_path)
    assert len(bars) == len(raw_rows) - 1
    assert all(bar.close != 99.0 for bar in bars)


def test_kraken_requests_are_never_issued_as_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mizan.crypto.ingest_kraken.resolve_kraken_pair",
        lambda ticker, *, client, cache_dir: "XBTUSD",
    )
    methods: list[str] = []
    base_ts = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    raw_rows = [[base_ts, "1.0", "2.0", "0.5", "1.5", "1.1", "10.0", 5]] * 2

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(
            200, content=json.dumps({"result": {"XBTUSD": raw_rows}}).encode()
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch_kraken_candles(ticker="BTC", granularity="1d", client=client, cache_dir=tmp_path)
    assert methods
    assert all(method == "GET" for method in methods)


def test_kraken_720_candle_cap_is_not_silently_treated_as_full_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mizan.crypto.ingest_kraken.resolve_kraken_pair",
        lambda ticker, *, client, cache_dir: "XBTUSD",
    )
    base_ts = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    raw_rows = [
        [base_ts + i * 86400, "1.0", "2.0", "0.5", "1.5", "1.1", "10.0", 5] for i in range(720)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=json.dumps({"result": {"XBTUSD": raw_rows}}).encode()
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    bars = fetch_kraken_candles(ticker="BTC", granularity="1d", client=client, cache_dir=tmp_path)
    assert len(bars) == 719

    source = (
        Path(__file__).parents[1] / "mizan/crypto/ingest_kraken.py"
    ).read_text(encoding="utf-8")
    assert "720" in source
