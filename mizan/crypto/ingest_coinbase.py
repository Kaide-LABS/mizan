"""Coinbase public candle ingestion; see ``docs/crypto/PHASE_2_SPEC.md`` §A3."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from mizan.crypto.models import CandleBar, _parse_coinbase_row
from mizan.crypto.universe import CRYPTO_UNIVERSE
from mizan.data.raw_cache import cache_path, is_cached, read_raw_json, write_raw_json

_COINBASE_PRODUCT_IDS = {ticker: f"{ticker}-USD" for ticker in CRYPTO_UNIVERSE}
_COINBASE_GRANULARITY_SECONDS = {"1d": 86400}


def _key_stamp(moment: datetime) -> str:
    """ISO-8601 timestamp made safe for use inside a cache filename.

    Colons are illegal in Windows filenames (OSError Errno 22), so they become hyphens. This is
    used for the cache KEY only; the request parameters keep the exact ISO-8601 form.
    """
    return moment.isoformat().replace(":", "-")


class CoinbaseProductNotFoundError(RuntimeError):
    """Raised when Coinbase has no product for a universe ticker."""


class UnsupportedGranularityError(RuntimeError):
    """Raised when this exchange has no mapping for the requested granularity."""


def fetch_coinbase_candles(
    ticker: str,
    *,
    granularity: str,
    start: datetime,
    end: datetime,
    client: httpx.Client,
    cache_dir: Path,
) -> tuple[CandleBar, ...]:
    """Fetch cached Coinbase Exchange API candles in windows of at most 300 rows."""
    product = _COINBASE_PRODUCT_IDS[ticker]
    seconds = _COINBASE_GRANULARITY_SECONDS.get(granularity)
    if seconds is None:
        raise UnsupportedGranularityError(granularity)
    current_end = end.astimezone(UTC)
    bars: dict[datetime, CandleBar] = {}
    first = True
    while current_end > start:
        window_start = max(start, current_end - timedelta(seconds=seconds * 300))
        key = f"{ticker}_{granularity}_{_key_stamp(window_start)}_{_key_stamp(current_end)}"
        path = cache_path(cache_dir=cache_dir, source="coinbase/candles", key=key)
        if is_cached(path):
            payload = read_raw_json(path)
        else:
            response = client.get(
                f"https://api.exchange.coinbase.com/products/{product}/candles",
                params={
                    "granularity": seconds,
                    "start": window_start.isoformat(),
                    "end": current_end.isoformat(),
                },
            )
            if response.status_code == 404 and first:
                raise CoinbaseProductNotFoundError(product)
            response.raise_for_status()
            write_raw_json(path, response.content)
            payload = json.loads(response.content)
        first = False
        if not isinstance(payload, list) or not payload:
            break
        for raw in payload:
            if not isinstance(raw, list):
                raise ValueError("Coinbase candle row must be an array")
            ts, opening, high, low, close, volume = _parse_coinbase_row(raw)
            bars[ts] = CandleBar(
                exchange="coinbase",
                symbol=ticker,
                granularity=granularity,
                ts=ts,
                open=opening,
                high=high,
                low=low,
                close=close,
                volume=volume,
                source="coinbase_exchange_api",
            )
        if window_start <= start or len(payload) < 300:
            break
        current_end = window_start
    return tuple(bars[key] for key in sorted(bars))
