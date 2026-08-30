"""Tests for mizan/data/ingest_tiingo.py.

Implements PHASE_2_SPEC.md §8 acceptance criteria 1 (replayability), 5 (budget limiting actually
throttles), 8 (token never touches the cache or the URL), 10 (corporate-action anomalies are
flagged, not dropped), 11 (monthly universe drift is caught), and guards G-T1, G-T2, G-T4, G-T5.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest

from mizan.data import ingest_tiingo

_DUMMY_TOKEN = "SUPER-SECRET-TEST-TOKEN-VALUE"  # a fixture value only, never a real credential


def _bar(day: date, *, div_cash: float = 0.0, split_factor: float = 1.0) -> dict[str, object]:
    return {
        "date": day.isoformat(),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000,
        "adjOpen": 99.0,
        "adjHigh": 100.0,
        "adjLow": 98.0,
        "adjClose": 99.5,
        "adjVolume": 1000,
        "divCash": div_cash,
        "splitFactor": split_factor,
    }


class _FakeClock:
    """A controllable wall clock: `sleep` advances `time` deterministically instead of blocking."""

    def __init__(self, start: float) -> None:
        self.now = start

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def _reset_tiingo_budget() -> None:
    """Give every test a fresh budget instance so cross-test counters never leak."""
    ingest_tiingo._budget = ingest_tiingo._TiingoBudget()


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _static_json_handler(payload: object) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return handler


def _counting_handler(
    payload: object,
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=payload)

    return handler, captured


# ── _TiingoBudget (G-T1, AC5) ────────────────────────────────────────────────────────────────────


def test_the_51st_consume_within_one_hour_sleeps_to_the_next_hour_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock(0.0)
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)

    budget = ingest_tiingo._TiingoBudget(hourly_limit=50, daily_limit=1000)
    for _ in range(50):
        budget.consume()
    assert clock.now == 0.0  # no sleep needed for the first 50

    budget.consume()  # the 51st call must throttle

    assert clock.now >= 3600.0


def test_consume_does_not_sleep_below_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock(0.0)
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)

    budget = ingest_tiingo._TiingoBudget(hourly_limit=50, daily_limit=1000)
    for _ in range(49):
        budget.consume()

    assert clock.now == 0.0


def test_consume_throttles_on_the_daily_limit_too(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock(0.0)
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)

    budget = ingest_tiingo._TiingoBudget(hourly_limit=1000, daily_limit=2)
    budget.consume()
    budget.consume()
    assert clock.now == 0.0

    budget.consume()  # the 3rd call exceeds the daily cap of 2

    assert clock.now >= 3600.0


def test_hourly_counter_resets_after_the_hour_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock(0.0)
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)

    budget = ingest_tiingo._TiingoBudget(hourly_limit=1, daily_limit=1000)
    budget.consume()
    clock.now = 3600.0  # advance into the next hour bucket without sleeping
    budget.consume()  # should NOT block — new hour, counter reset

    assert clock.now == 3600.0


# ── Monthly unique-symbol cap (G-T2, AC11) ──────────────────────────────────────────────────────

_A_MONTH = date(2026, 8, 30)
_A_MONTH_KEY = "2026-08"


def test_a_501st_distinct_symbol_raises_universe_drift_error(tmp_path: Path) -> None:
    symbols = {f"SYM{i:04d}" for i in range(500)}
    ingest_tiingo._save_symbol_log(ingest_tiingo._symbol_log_path(tmp_path, _A_MONTH_KEY), symbols)

    with pytest.raises(ingest_tiingo.TiingoUniverseDriftError):
        ingest_tiingo._register_symbol_or_raise(tmp_path, "NEWSYM", today=_A_MONTH)


def test_a_ticker_already_logged_this_month_does_not_count_twice(tmp_path: Path) -> None:
    symbols = {f"SYM{i:04d}" for i in range(500)}
    log_path = ingest_tiingo._symbol_log_path(tmp_path, _A_MONTH_KEY)
    ingest_tiingo._save_symbol_log(log_path, symbols)

    ingest_tiingo._register_symbol_or_raise(tmp_path, "sym0000", today=_A_MONTH)

    assert ingest_tiingo._load_symbol_log(log_path) == symbols


def test_a_new_symbol_under_the_cap_is_registered(tmp_path: Path) -> None:
    log_path = ingest_tiingo._symbol_log_path(tmp_path, _A_MONTH_KEY)

    ingest_tiingo._register_symbol_or_raise(tmp_path, "AAPL", today=_A_MONTH)

    assert ingest_tiingo._load_symbol_log(log_path) == {"AAPL"}


def test_ingest_tiingo_eod_raises_universe_drift_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return _A_MONTH

    monkeypatch.setattr(ingest_tiingo, "date", _FixedDate)
    symbols = {f"SYM{i:04d}" for i in range(500)}
    ingest_tiingo._save_symbol_log(ingest_tiingo._symbol_log_path(tmp_path, _A_MONTH_KEY), symbols)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(f"unexpected request to {request.url}")

    with (
        _client_with_handler(handler) as client,
        pytest.raises(ingest_tiingo.TiingoUniverseDriftError),
    ):
        ingest_tiingo.ingest_tiingo_eod(
            "NEWSYM",
            date(2026, 8, 1),
            date(2026, 8, 30),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )


# ── Corporate-action anomaly scan (G-T4, AC10) ──────────────────────────────────────────────────


def test_anomaly_scan_raises_and_still_writes_the_cache_first(tmp_path: Path) -> None:
    bars = [
        _bar(date(2020, 1, 2), div_cash=0.0, split_factor=1.0),
        _bar(date(2020, 1, 3), div_cash=0.0, split_factor=2.0),  # flagged: split, no divCash
    ]
    handler = _static_json_handler(bars)

    with (
        _client_with_handler(handler) as client,
        pytest.raises(ingest_tiingo.SuspectedCorporateActionAnomalyError) as excinfo,
    ):
        ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 3),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )

    assert "2020-01-03" in str(excinfo.value)
    cache_file = tmp_path / "tiingo" / "eod" / "AAPL_2020-01-02_2020-01-03.json"
    assert cache_file.is_file()


def test_a_clean_bar_set_raises_no_anomaly(tmp_path: Path) -> None:
    bars = [
        _bar(date(2020, 1, 2), div_cash=0.5, split_factor=1.0),
        _bar(date(2020, 1, 3), div_cash=0.0, split_factor=1.0),
    ]
    handler = _static_json_handler(bars)

    with _client_with_handler(handler) as client:
        path = ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 3),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )

    assert path.is_file()


# ── Token never leaks (G-T5, AC8) ───────────────────────────────────────────────────────────────


def test_token_is_sent_only_via_the_authorization_header(tmp_path: Path) -> None:
    handler, captured = _counting_handler([_bar(date(2020, 1, 2))])

    with _client_with_handler(handler) as client:
        ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 2),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )

    assert len(captured) == 1
    request = captured[0]
    assert request.headers["Authorization"] == f"Token {_DUMMY_TOKEN}"
    assert _DUMMY_TOKEN not in str(request.url)


def test_token_never_appears_in_any_cached_file(tmp_path: Path) -> None:
    handler = _static_json_handler([_bar(date(2020, 1, 2))])

    with _client_with_handler(handler) as client:
        ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 2),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )

    cached_files = list(tmp_path.rglob("*.json"))
    assert cached_files  # sanity: something was actually cached
    for cached_file in cached_files:
        assert _DUMMY_TOKEN not in cached_file.read_text(encoding="utf-8")


# ── Replayability (AC1) ─────────────────────────────────────────────────────────────────────────


def test_ingest_tiingo_eod_cache_hit_issues_zero_requests(tmp_path: Path) -> None:
    handler, captured = _counting_handler([_bar(date(2020, 1, 2))])

    with _client_with_handler(handler) as client:
        first = ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 2),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )
        assert len(captured) == 1
        second = ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 2),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )

    assert len(captured) == 1
    assert first == second


def test_force_refetch_bypasses_the_cache(tmp_path: Path) -> None:
    handler, captured = _counting_handler([_bar(date(2020, 1, 2))])

    with _client_with_handler(handler) as client:
        ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 2),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
        )
        ingest_tiingo.ingest_tiingo_eod(
            "AAPL",
            date(2020, 1, 2),
            date(2020, 1, 2),
            cache_dir=tmp_path,
            token=_DUMMY_TOKEN,
            client=client,
            force_refetch=True,
        )

    assert len(captured) == 2
