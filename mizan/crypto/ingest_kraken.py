"""Kraken public fallback candles; see ``docs/crypto/PHASE_2_SPEC.md`` §B1."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

import httpx

from mizan.crypto.models import CandleBar, _parse_kraken_row
from mizan.data.raw_cache import cache_path, is_cached, read_raw_json, write_raw_json

_KRAKEN_GRANULARITY_MINUTES = {"1d": 1440}
_KRAKEN_MAX_CANDLES = 720


class KrakenPairNotFoundError(RuntimeError):
    """Raised when Kraken has no freely tradable USD pair for a ticker."""


class UnsupportedGranularityError(RuntimeError):
    """Raised when Kraken has no mapping for a requested granularity."""


def resolve_kraken_pair(ticker: str, *, client: httpx.Client, cache_dir: Path) -> str:
    """Resolve a ticker from the cached public AssetPairs response."""
    path = cache_path(cache_dir=cache_dir, source="kraken/asset_pairs", key="all")
    if is_cached(path):
        payload = read_raw_json(path)
    else:
        response = client.get("https://api.kraken.com/0/public/AssetPairs")
        response.raise_for_status()
        write_raw_json(path, response.content)
        payload = json.loads(response.content)
    if not isinstance(payload, dict):
        raise KrakenPairNotFoundError(ticker)
    result = payload.get("result")
    if not isinstance(result, dict):
        raise KrakenPairNotFoundError(ticker)
    for key, value in result.items():
        if not isinstance(value, dict):
            continue
        altname = str(value.get("altname", key)).upper()
        base = str(value.get("base", "")).upper().lstrip("X").lstrip("Z")
        quote = str(value.get("quote", "")).upper().lstrip("X").lstrip("Z")
        if (
            altname in {f"{ticker}USD", f"{ticker}ZUSD"} or (base == ticker and quote == "USD")
        ) and value.get("status", "online") == "online":
            return str(value.get("altname", key))
    raise KrakenPairNotFoundError(ticker)


def fetch_kraken_candles(
    *, ticker: str, granularity: str, client: httpx.Client, cache_dir: Path
) -> tuple[CandleBar, ...]:
    """Fetch closed daily OHLC bars; Kraken exposes only its latest ~720 candles (~2 years)."""
    minutes = _KRAKEN_GRANULARITY_MINUTES.get(granularity)
    if minutes is None:
        raise UnsupportedGranularityError(granularity)
    pair = resolve_kraken_pair(ticker, client=client, cache_dir=cache_dir)
    path = cache_path(cache_dir=cache_dir, source="kraken/ohlc", key=f"{ticker}_{granularity}")
    if is_cached(path):
        payload = read_raw_json(path)
    else:
        response = client.get(
            "https://api.kraken.com/0/public/OHLC", params={"pair": pair, "interval": minutes}
        )
        response.raise_for_status()
        write_raw_json(path, response.content)
        payload = json.loads(response.content)
    result = payload.get("result") if isinstance(payload, dict) else None
    rows = result.get(pair) if isinstance(result, dict) else None
    if rows is None and isinstance(result, dict):
        rows = next((v for k, v in result.items() if k != "last"), None)
    if not isinstance(rows, list):
        return ()
    bars: dict[datetime, CandleBar] = {}
    for raw in rows[:-1]:
        if not isinstance(raw, list):
            raise ValueError("Kraken candle row must be an array")
        ts, opening, high, low, close, volume = _parse_kraken_row(cast(list[object], raw))
        bar = CandleBar(
            exchange="kraken",
            symbol=ticker,
            granularity=granularity,
            ts=ts,
            open=opening,
            high=high,
            low=low,
            close=close,
            volume=volume,
            source="kraken_ohlc_public",
        )
        bars[ts] = bar
    return tuple(bars[key] for key in sorted(bars))
