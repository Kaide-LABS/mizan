"""Crypto source selection; see ``docs/crypto/PHASE_2_SPEC.md`` §B2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import httpx

from mizan.crypto.ingest_coinbase import CoinbaseProductNotFoundError, fetch_coinbase_candles
from mizan.crypto.ingest_kraken import fetch_kraken_candles
from mizan.crypto.universe import CRYPTO_UNIVERSE
from mizan.data.db import upsert_candles


def ingest_universe_candles(
    *,
    granularity: str,
    start: datetime,
    end: datetime,
    cache_dir: Path,
    con: duckdb.DuckDBPyConnection,
    client: httpx.Client,
) -> dict[str, str]:
    """Fetch each ticker from Coinbase, falling back wholly to Kraken on 404/empty."""
    selected: dict[str, str] = {}
    for ticker in sorted(CRYPTO_UNIVERSE):
        try:
            bars = fetch_coinbase_candles(
                ticker,
                granularity=granularity,
                start=start,
                end=end,
                client=client,
                cache_dir=cache_dir,
            )
        except CoinbaseProductNotFoundError:
            bars = ()
        if not bars:
            bars = fetch_kraken_candles(
                ticker=ticker, granularity=granularity, client=client, cache_dir=cache_dir
            )
            selected[ticker] = "kraken"
        else:
            selected[ticker] = "coinbase"
        upsert_candles(con, bars)
    return selected
