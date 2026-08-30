"""mizan/data/ingest_tiingo.py — Tiingo EOD ingestion: request-budget limiter, raw cache.

Implements PHASE_2_SPEC.md §4.3, §6.2, §6.4.

Tiingo's binding limits are request-rate limits (50/hour, 1,000/day) and a monthly unique-symbol
cap (500) — not a per-second limit (`docs/modernization_log.md` §6.2: "we do not rate limit to
minute or second"). This is a deliberately different mechanism from `ingest_edgar.py`'s
spacing-plus-cooldown limiter (`ULTIMATE_PRD.md` §6: "the two ingestion jobs must not share one
rate-limiter implementation").
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import TYPE_CHECKING

from mizan.data.models import TiingoCorporateActionEvent, TiingoEodBar
from mizan.data.raw_cache import RawCacheError, cache_path, is_cached, read_raw_json, write_raw_json

if TYPE_CHECKING:
    from pathlib import Path

    import httpx

_TIINGO_EOD_URL_TEMPLATE = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"

_HOURLY_REQUEST_LIMIT = 50
_DAILY_REQUEST_LIMIT = 1000
_MONTHLY_UNIQUE_SYMBOL_LIMIT = 500
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_DAY = 86400
_EST_OFFSET_SECONDS = 5 * _SECONDS_PER_HOUR  # EST = UTC-5; Tiingo's daily reset is midnight EST.


class TiingoUniverseDriftError(RuntimeError):
    """Raised when the running ticker universe for the current calendar month would exceed the
    500-unique-symbols/month cap (ULTIMATE_PRD.md §4.2) — indicates universe drift, not transient
    load, per that section's categorization; never auto-retried."""


class SuspectedCorporateActionAnomalyError(RuntimeError):
    """Raised when `ingest_tiingo_eod`'s anomaly scan (§6.4) finds a `splitFactor` discontinuity
    with no matching `divCash` on the same date — `ULTIMATE_PRD.md` §4.2's "missing divCash on a
    known ex-dividend date" guard, deliberately conservative (some flagged rows will be ordinary
    splits, not missed dividends; a false-positive flag is cheap, a silently-missed dividend is
    not)."""


class _TiingoBudget:
    """Tracks hourly (reset on the hour) and daily (reset at UTC-adjusted midnight EST) request
    counts, per `ULTIMATE_PRD.md` §4.2: the binding limits are 50 requests/hour and 1,000/day — NOT
    a per-symbol or per-second limit; Tiingo explicitly does not rate-limit to the second.

    Module-private — an implementation detail of `ingest_tiingo_eod`, which routes every request
    through the single module-level `_budget` instance.
    """

    def __init__(
        self, *, hourly_limit: int = _HOURLY_REQUEST_LIMIT, daily_limit: int = _DAILY_REQUEST_LIMIT
    ) -> None:
        self._hourly_limit = hourly_limit
        self._daily_limit = daily_limit
        self._hour_bucket: int | None = None
        self._hour_count = 0
        self._day_bucket: int | None = None
        self._day_count = 0

    def consume(self) -> None:
        """Block (sleep) until a slot is available if the hourly or daily budget is currently
        exhausted, sleeping to the next hour boundary — matches `ULTIMATE_PRD.md` §4.2's
        categorization of budget exhaustion as Auto-retryable, in contrast to EDGAR's HALT-style
        403 case."""
        now = time.time()
        self._reset_expired_buckets(now)
        while self._hour_count >= self._hourly_limit or self._day_count >= self._daily_limit:
            time.sleep(_SECONDS_PER_HOUR - (now % _SECONDS_PER_HOUR))
            now = time.time()
            self._reset_expired_buckets(now)
        self._hour_count += 1
        self._day_count += 1

    def _reset_expired_buckets(self, now: float) -> None:
        hour_bucket = int(now // _SECONDS_PER_HOUR)
        if hour_bucket != self._hour_bucket:
            self._hour_bucket = hour_bucket
            self._hour_count = 0
        day_bucket = int((now - _EST_OFFSET_SECONDS) // _SECONDS_PER_DAY)
        if day_bucket != self._day_bucket:
            self._day_bucket = day_bucket
            self._day_count = 0


_budget = _TiingoBudget()


def _symbol_log_path(cache_dir: Path, year_month: str) -> Path:
    """Path to the persisted per-calendar-month unique-symbol log (G-T2, PHASE_2_SPEC.md §7)."""
    return cache_dir / "tiingo" / "symbol_log" / f"{year_month}.json"


def _load_symbol_log(log_path: Path) -> set[str]:
    """Load the set of tickers already registered for one calendar month, if any."""
    if not is_cached(log_path):
        return set()
    payload = read_raw_json(log_path)
    if not isinstance(payload, dict):
        raise RawCacheError(f"corrupt Tiingo symbol log at {log_path}: expected a JSON object")
    symbols = payload.get("symbols", [])
    if not isinstance(symbols, list):
        raise RawCacheError(f"corrupt Tiingo symbol log at {log_path}: `symbols` is not a list")
    return {str(symbol) for symbol in symbols}


def _save_symbol_log(log_path: Path, symbols: set[str]) -> None:
    """Atomically persist the updated symbol set for one calendar month."""
    payload = json.dumps({"symbols": sorted(symbols)}).encode("utf-8")
    write_raw_json(log_path, payload)


def _register_symbol_or_raise(cache_dir: Path, ticker: str, *, today: date | None = None) -> None:
    """Register `ticker` against the current calendar month's unique-symbol log.

    Raises `TiingoUniverseDriftError` if `ticker` is new to the month and the running count would
    exceed `_MONTHLY_UNIQUE_SYMBOL_LIMIT`. A ticker already logged this month is a no-op — it does
    not count twice (G-T2).
    """
    resolved_today = today if today is not None else date.today()
    year_month = f"{resolved_today.year:04d}-{resolved_today.month:02d}"
    log_path = _symbol_log_path(cache_dir, year_month)

    symbols = _load_symbol_log(log_path)
    normalized_ticker = ticker.upper()
    if normalized_ticker in symbols:
        return
    if len(symbols) >= _MONTHLY_UNIQUE_SYMBOL_LIMIT:
        raise TiingoUniverseDriftError(
            f"{ticker!r} would be unique symbol #{len(symbols) + 1} for {year_month}, exceeding "
            f"the {_MONTHLY_UNIQUE_SYMBOL_LIMIT}/month cap"
        )
    symbols.add(normalized_ticker)
    _save_symbol_log(log_path, symbols)


def ingest_tiingo_eod(
    ticker: str,
    start_date: date,
    end_date: date,
    *,
    cache_dir: Path,
    token: str,
    client: httpx.Client,
    force_refetch: bool = False,
) -> Path:
    """Fetch (or return cached) one ranged GET to
    https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate=...&endDate=....

    Sends `token` via the `Authorization: Token {token}` header, never as a URL query parameter
    (`ULTIMATE_PRD.md` §4.2 NEW row) — the cache key is `(ticker, start_date, end_date)`, which
    never contains the token, so grepping the cache directory or any logged URL for the token value
    finds nothing by construction.

    Before issuing the request, registers `ticker` against the current calendar month's
    unique-symbol log (raising `TiingoUniverseDriftError` if this ticker is new to the month and
    the running count would exceed 500) and consumes one unit from the module-level `_TiingoBudget`
    (§6.3). After a successful fetch, parses every bar as `TiingoEodBar` (§3) and runs the anomaly
    scan (§6.4), raising `SuspectedCorporateActionAnomalyError` if any bar is flagged — the
    response is still written to the raw cache first (a flagged anomaly is a "look at this," not
    "discard this"), then the exception is raised so the caller (the CLI, §4.4) surfaces it rather
    than silently proceeding.
    """
    key = f"{ticker}_{start_date.isoformat()}_{end_date.isoformat()}"
    path = cache_path(cache_dir=cache_dir, source="tiingo/eod", key=key)
    if is_cached(path) and not force_refetch:
        return path

    _register_symbol_or_raise(cache_dir, ticker)
    _budget.consume()

    url = _TIINGO_EOD_URL_TEMPLATE.format(ticker=ticker)
    params = {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    response = client.get(url, params=params, headers=headers)
    response.raise_for_status()

    write_raw_json(path, response.content)

    bars_raw = json.loads(response.content)
    if not isinstance(bars_raw, list):
        raise RawCacheError(f"{ticker}: expected a JSON array of bars, got {type(bars_raw)!r}")
    bars = [TiingoEodBar.model_validate(row) for row in bars_raw]

    _scan_for_corporate_action_anomalies(ticker, bars)
    return path


def _scan_for_corporate_action_anomalies(ticker: str, bars: list[TiingoEodBar]) -> None:
    """Flag any bar with a `splitFactor` discontinuity and no matching `divCash` (§6.4).

    Deliberately conservative: an ordinary stock split with no accompanying dividend will also
    flag. This phase does not attempt to distinguish "expected split" from "suspected missed
    dividend" — that requires a reference corporate-actions signal this phase has no access to; it
    surfaces every candidate to a human (`ULTIMATE_PRD.md` §4.2's HALT-for-human categorization)
    rather than guessing.
    """
    events = [TiingoCorporateActionEvent.from_bar(bar) for bar in bars]
    flagged = [event for event in events if event.split_factor != 1.0 and event.div_cash == 0.0]
    if flagged:
        raise SuspectedCorporateActionAnomalyError(
            f"{ticker}: {len(flagged)} date(s) with a splitFactor discontinuity and no matching "
            f"divCash: {[event.trade_date.isoformat() for event in flagged]}"
        )
