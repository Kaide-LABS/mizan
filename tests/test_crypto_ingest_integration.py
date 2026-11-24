"""End-to-end tests for mizan/crypto/ingest.py::ingest_universe_candles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
import pytest

import mizan.config.boot_check as boot_check
from mizan.crypto.ingest import ingest_universe_candles
from mizan.crypto.universe import CRYPTO_UNIVERSE
from mizan.data.db import ensure_schema

_FAILING_COINBASE_TICKER = CRYPTO_UNIVERSE[0]


def _coinbase_row(ts: datetime) -> list[float]:
    return [ts.timestamp(), 0.5, 2.0, 1.0, 1.5, 10.0]


def _kraken_rows(ts: datetime) -> list[list[object]]:
    return [[ts.timestamp(), "1.0", "2.0", "0.5", "1.5", "1.1", "10.0", 5]] * 2


@pytest.fixture(autouse=True)
def _patched_io(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("mizan.crypto.ingest_coinbase", "mizan.crypto.ingest_kraken"):
        monkeypatch.setattr(f"{module}.is_cached", lambda path: False)
        monkeypatch.setattr(f"{module}.write_raw_json", lambda path, payload: None)
    monkeypatch.setattr(
        "mizan.crypto.ingest_kraken.resolve_kraken_pair",
        lambda ticker, *, client, cache_dir: f"{ticker}USD",
    )


def _make_client(ts: datetime, *, calls: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "exchange.coinbase.com" in url:
            calls.append("coinbase")
            product = url.split("/products/")[1].split("/")[0]
            ticker = product.split("-")[0]
            if ticker == _FAILING_COINBASE_TICKER:
                return httpx.Response(404)
            return httpx.Response(200, content=json.dumps([_coinbase_row(ts)]).encode())
        calls.append("kraken")
        if "AssetPairs" in url:
            return httpx.Response(200, content=b'{"result": {}}')
        pair = request.url.params.get("pair", "XUSD")
        return httpx.Response(
            200, content=json.dumps({"result": {pair: _kraken_rows(ts)}}).encode()
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ingest_universe_candles_writes_every_ticker_into_candles_table(tmp_path: Path) -> None:
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    con = duckdb.connect(":memory:")
    ensure_schema(con)
    calls: list[str] = []
    client = _make_client(ts, calls=calls)

    selected = ingest_universe_candles(
        granularity="1d", start=ts, end=ts, cache_dir=tmp_path, con=con, client=client
    )
    assert set(selected) == set(CRYPTO_UNIVERSE)
    assert selected[_FAILING_COINBASE_TICKER] == "kraken"

    symbols = {row[0] for row in con.execute("SELECT DISTINCT symbol FROM candles").fetchall()}
    assert symbols == set(CRYPTO_UNIVERSE)
    granularities = {
        row[0] for row in con.execute("SELECT DISTINCT granularity FROM candles").fetchall()
    }
    assert granularities == {"1d"}
    con.close()


def test_rerunning_ingestion_is_idempotent(tmp_path: Path) -> None:
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    con = duckdb.connect(":memory:")
    ensure_schema(con)

    calls_first: list[str] = []
    client1 = _make_client(ts, calls=calls_first)
    ingest_universe_candles(
        granularity="1d", start=ts, end=ts, cache_dir=tmp_path, con=con, client=client1
    )
    count_after_first = con.execute("SELECT count(*) FROM candles").fetchone()
    assert count_after_first is not None

    calls_second: list[str] = []
    client2 = _make_client(ts, calls=calls_second)
    ingest_universe_candles(
        granularity="1d", start=ts, end=ts, cache_dir=tmp_path, con=con, client=client2
    )
    count_after_second = con.execute("SELECT count(*) FROM candles").fetchone()
    assert count_after_second is not None
    assert count_after_second[0] == count_after_first[0]
    con.close()


def test_boot_check_still_passes_after_a_full_ingestion_run(tmp_path: Path) -> None:
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    con = duckdb.connect(":memory:")
    ensure_schema(con)
    calls: list[str] = []
    client = _make_client(ts, calls=calls)

    ingest_universe_candles(
        granularity="1d", start=ts, end=ts, cache_dir=tmp_path, con=con, client=client
    )
    boot_check.check_all()
    con.close()
