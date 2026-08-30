"""Tests for mizan/data/normalize.py.

Implements PHASE_3_SPEC.md §8 acceptance criteria 1 (fixture normalization), 2 (genuine duplicate
raises), 3 (unrecognized unit rejected), 4 (idempotent re-run), 6 (raw/adj independence), 7
(is_instantaneous correctness), 9 (never-ingested halts), and guards G-N1 through G-N8.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from mizan.data import db, normalize
from mizan.data.ingest_edgar import CikResolutionError
from mizan.data.raw_cache import write_raw_json

_CIK = "0000320193"
_TICKER = "AAPL"
_START = date(2020, 1, 1)
_END = date(2020, 1, 3)


def _instantaneous_fact(
    *, value: float = 100.0, accn: str = "0000320193-20-000096", filed: str = "2020-10-30"
) -> dict[str, object]:
    return {
        "end": "2020-09-26",
        "val": value,
        "accn": accn,
        "fy": 2020,
        "fp": "FY",
        "form": "10-K",
        "filed": filed,
    }


def _duration_fact(
    *, value: float = 200.0, accn: str = "0000320193-20-000096"
) -> dict[str, object]:
    return {
        "start": "2019-09-29",
        "end": "2020-09-26",
        "val": value,
        "accn": accn,
        "fy": 2020,
        "fp": "FY",
        "form": "10-K",
        "filed": "2020-10-30",
    }


def _companyfacts_payload(*, assets_value: float = 100.0) -> dict[str, object]:
    """One instantaneous concept (`Assets`, unit USD), one duration concept (`Revenues`, unit
    USD), and one instantaneous concept under unit `shares` — enough to exercise both branches of
    G-N6 and the `RECOGNIZED_XBRL_UNITS` allow-list in one fixture (AC1)."""
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Assets": {"units": {"USD": [_instantaneous_fact(value=assets_value)]}},
                "Revenues": {"units": {"USD": [_duration_fact()]}},
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": [_instantaneous_fact(value=1_000_000.0)]}
                }
            },
        },
    }


def _companyfacts_with_bad_unit() -> dict[str, object]:
    """A payload carrying one good fact (`Assets`, USD) and one fact under a unit outside
    `RECOGNIZED_XBRL_UNITS` — used to prove the bad unit halts before ANY row is loaded (AC3)."""
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Assets": {"units": {"USD": [_instantaneous_fact()]}},
                "EarningsPerShareBasic": {"units": {"USD/shares": [_instantaneous_fact()]}},
            },
        },
    }


def _write_companyfacts(cache_dir: Path, payload: dict[str, object], *, cik: str = _CIK) -> None:
    path = cache_dir / "edgar" / "companyfacts" / f"{cik}.json"
    write_raw_json(path, json.dumps(payload).encode("utf-8"))


def _bar(day: date, *, close: float = 100.5, div_cash: float = 0.0) -> dict[str, object]:
    return {
        "date": day.isoformat(),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": close,
        "volume": 1000,
        "adjOpen": 99.0,
        "adjHigh": 100.0,
        "adjLow": 98.0,
        "adjClose": 99.5,
        "adjVolume": 900,
        "divCash": div_cash,
        "splitFactor": 1.0,
    }


def _write_tiingo_eod(
    cache_dir: Path,
    bars: list[dict[str, object]],
    *,
    ticker: str = _TICKER,
    start: date = _START,
    end: date = _END,
) -> None:
    key = f"{ticker}_{start.isoformat()}_{end.isoformat()}"
    path = cache_dir / "tiingo" / "eod" / f"{key}.json"
    write_raw_json(path, json.dumps(bars).encode("utf-8"))


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """A fresh, isolated, on-disk-under-tmp_path DuckDB connection per test — never a shared file
    (the DuckDB file is derived/regenerable, gitignored, and must never leak across tests)."""
    connection = db.connect(tmp_path / "test.duckdb")
    try:
        yield connection
    finally:
        connection.close()


# ── normalize_edgar_facts: fixture normalization + is_instantaneous (AC1, AC7, G-N6) ───────────


def test_normalize_edgar_facts_produces_expected_typed_rows(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    _write_companyfacts(tmp_path, _companyfacts_payload())

    inserted = normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)

    assert inserted == 3
    rows = con.execute(
        "SELECT tag, unit, period_start, period_end, is_instantaneous, value "
        "FROM fundamentals_facts ORDER BY tag"
    ).fetchall()
    by_tag = {row[0]: row for row in rows}
    assert set(by_tag) == {"Assets", "Revenues", "EntityCommonStockSharesOutstanding"}

    assets = by_tag["Assets"]
    assert assets[1] == "USD"
    assert assets[2] == assets[3] == date(2020, 9, 26)
    assert assets[4] is True
    assert assets[5] == 100.0

    revenues = by_tag["Revenues"]
    assert revenues[1] == "USD"
    assert revenues[2] == date(2019, 9, 29)
    assert revenues[3] == date(2020, 9, 26)
    assert revenues[4] is False
    assert revenues[2] != revenues[3]

    shares_row = by_tag["EntityCommonStockSharesOutstanding"]
    assert shares_row[1] == "shares"
    assert shares_row[4] is True


def test_normalize_edgar_facts_is_cik_zero_padded_string(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    _write_companyfacts(tmp_path, _companyfacts_payload())

    normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)

    row = con.execute("SELECT cik FROM fundamentals_facts LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == _CIK
    assert len(row[0]) == 10


# ── Unrecognized unit (AC3, G-N1) ────────────────────────────────────────────────────────────────


def test_unrecognized_unit_raises_before_any_row_is_loaded(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    _write_companyfacts(tmp_path, _companyfacts_with_bad_unit())

    with pytest.raises(normalize.UnrecognizedUnitError, match="USD/shares"):
        normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)

    count = con.execute("SELECT count(*) FROM fundamentals_facts").fetchone()
    assert count is not None
    assert count[0] == 0


# ── Genuine duplicate-with-conflicting-values (AC2, G-N2) ───────────────────────────────────────


def test_duplicate_fact_with_conflicting_value_raises_and_does_not_mutate(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    _write_companyfacts(tmp_path, _companyfacts_payload(assets_value=100.0))
    first = normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)
    assert first == 3

    _write_companyfacts(tmp_path, _companyfacts_payload(assets_value=999.0))

    with pytest.raises(normalize.DuplicateFactRowError):
        normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)

    row = con.execute("SELECT value FROM fundamentals_facts WHERE tag = 'Assets'").fetchone()
    assert row is not None
    assert row[0] == 100.0
    count = con.execute("SELECT count(*) FROM fundamentals_facts").fetchone()
    assert count is not None
    assert count[0] == 3


# ── Idempotent re-run (AC4, G-N3) ────────────────────────────────────────────────────────────────


def test_renormalizing_an_unchanged_cache_inserts_zero_rows(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    _write_companyfacts(tmp_path, _companyfacts_payload())
    first = normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)
    assert first == 3

    second = normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)

    assert second == 0
    count = con.execute("SELECT count(*) FROM fundamentals_facts").fetchone()
    assert count is not None
    assert count[0] == 3


# ── Never-ingested halts (AC9, G-N7) ─────────────────────────────────────────────────────────────


def test_normalize_edgar_facts_raises_not_ingested_when_cache_is_empty(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    with pytest.raises(normalize.NotIngestedError):
        normalize.normalize_edgar_facts(_CIK, cache_dir=tmp_path, con=con)

    count = con.execute("SELECT count(*) FROM fundamentals_facts").fetchone()
    assert count is not None
    assert count[0] == 0


def test_normalize_tiingo_bars_raises_not_ingested_when_cache_is_empty(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    with pytest.raises(normalize.NotIngestedError):
        normalize.normalize_tiingo_bars(_TICKER, _START, _END, cache_dir=tmp_path, con=con)

    count = con.execute("SELECT count(*) FROM price_bars").fetchone()
    assert count is not None
    assert count[0] == 0


# ── normalize_tiingo_bars: fixture normalization + raw/adj independence (AC1, AC6, G-N4) ───────


def test_normalize_tiingo_bars_produces_expected_typed_rows(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    bars = [
        _bar(date(2020, 1, 1)),
        _bar(date(2020, 1, 2), close=105.0, div_cash=0.25),
        _bar(date(2020, 1, 3)),
    ]
    _write_tiingo_eod(tmp_path, bars)

    inserted = normalize.normalize_tiingo_bars(_TICKER, _START, _END, cache_dir=tmp_path, con=con)

    assert inserted == 3
    rows = con.execute(
        "SELECT trade_date, raw_close, adj_close, div_cash FROM price_bars ORDER BY trade_date"
    ).fetchall()
    assert len(rows) == 3

    dividend_day = next(row for row in rows if row[0] == date(2020, 1, 2))
    assert dividend_day[1] == 105.0
    assert dividend_day[2] == 99.5
    assert dividend_day[3] == 0.25
    # raw_close and adj_close are independently populated — never derived from one another.
    assert dividend_day[1] != dividend_day[2]


def test_duplicate_price_bar_with_conflicting_value_raises_and_does_not_mutate(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    bars = [_bar(date(2020, 1, 1), close=100.5)]
    _write_tiingo_eod(tmp_path, bars)
    first = normalize.normalize_tiingo_bars(_TICKER, _START, _END, cache_dir=tmp_path, con=con)
    assert first == 1

    conflicting_bars = [_bar(date(2020, 1, 1), close=200.0)]
    _write_tiingo_eod(tmp_path, conflicting_bars)

    with pytest.raises(normalize.DuplicatePriceBarError):
        normalize.normalize_tiingo_bars(_TICKER, _START, _END, cache_dir=tmp_path, con=con)

    row = con.execute("SELECT raw_close FROM price_bars").fetchone()
    assert row is not None
    assert row[0] == 100.5
    count = con.execute("SELECT count(*) FROM price_bars").fetchone()
    assert count is not None
    assert count[0] == 1


def test_renormalizing_unchanged_tiingo_cache_inserts_zero_rows(
    tmp_path: Path, con: duckdb.DuckDBPyConnection
) -> None:
    bars = [_bar(date(2020, 1, 1)), _bar(date(2020, 1, 2))]
    _write_tiingo_eod(tmp_path, bars)
    first = normalize.normalize_tiingo_bars(_TICKER, _START, _END, cache_dir=tmp_path, con=con)
    assert first == 2

    second = normalize.normalize_tiingo_bars(_TICKER, _START, _END, cache_dir=tmp_path, con=con)

    assert second == 0


# ── resolve_cik_offline (G-N8) ───────────────────────────────────────────────────────────────────


def test_resolve_cik_offline_finds_and_zero_pads_a_cached_ticker(tmp_path: Path) -> None:
    payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    path = tmp_path / "edgar" / "company_tickers" / "company_tickers.json"
    write_raw_json(path, json.dumps(payload).encode("utf-8"))

    cik = normalize.resolve_cik_offline("aapl", cache_dir=tmp_path)

    assert cik == "0000320193"


def test_resolve_cik_offline_raises_when_no_cache_exists(tmp_path: Path) -> None:
    with pytest.raises(CikResolutionError):
        normalize.resolve_cik_offline("AAPL", cache_dir=tmp_path)


def test_resolve_cik_offline_raises_when_ticker_absent(tmp_path: Path) -> None:
    payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    path = tmp_path / "edgar" / "company_tickers" / "company_tickers.json"
    write_raw_json(path, json.dumps(payload).encode("utf-8"))

    with pytest.raises(CikResolutionError):
        normalize.resolve_cik_offline("NOPE", cache_dir=tmp_path)


def test_resolve_cik_offline_has_no_network_parameter() -> None:
    """Structural guard (G-N8): the function signature has no client/httpx parameter at all."""
    import inspect

    params = inspect.signature(normalize.resolve_cik_offline).parameters
    assert "client" not in params
    assert "httpx" not in params
