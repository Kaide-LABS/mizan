"""Tests for mizan/purification/ledger.py — Fork A trigger + Fork B side-ledger accrual.

Implements PHASE_6_SPEC.md §8 acceptance criteria 1 (anti-undercount date-pinned ratio), 2
(Pure-verdict zero entries), 4 (grace-window fallback, never zero), 5 (gross vs net distinctness),
6 (lossless round-trip), 7 (every other BacktestResult field unchanged), 8 (reconciliation), 12
(every model inherits MizanBaseModel), 13 (BacktestResult.purification_ledger type unchanged),
plus guards G-P1, G-P3, G-P4, G-P6, G-P7, G-DB6, G-LLM6, G-BOUND2.
"""

from __future__ import annotations

import inspect
from datetime import date
from typing import TYPE_CHECKING

import pytest

from mizan.backtest.clock import BacktestResult, run_backtest
from mizan.backtest.strategy import EqualWeightStrategy
from mizan.config.fiqh_params import FIQH_PARAMS
from mizan.core.base import MizanBaseModel
from mizan.core.verdict import Verdict
from mizan.data import db
from mizan.purification.ledger import (
    DividendPurificationEntry,
    PurificationLedger,
    purify_backtest_result,
)
from tests.fixtures import synthetic_universe as fx

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import duckdb

_CLEAN_SIC = "7372"


def _build_db(tmp_path: Path, tickers: Sequence[fx.SyntheticTicker]) -> duckdb.DuckDBPyConnection:
    fx.write_universe_cache(tmp_path, tickers)
    con = db.connect(tmp_path / "test.duckdb")
    for ticker in tickers:
        fx.load_into_duckdb(con, ticker)
    return con


# ── §8 AC1 / G-P1: the core anti-undercount property — date-pinned ratio, not "most recent" ───────


def test_two_dividends_same_ticker_different_ratios_purified_at_own_period_ratio(
    tmp_path: Path,
) -> None:
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZMIXED_RATIODRIFT01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        assert len(result.dividend_events) == 2  # sanity: the fixture's own two div_cash days

        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)

        assert len(ledger.dividend_entries) == 2
        by_ex_date = {entry.ex_date: entry for entry in ledger.dividend_entries}

        early = by_ex_date[date(2026, 2, 15)]
        assert early.ratio_used == pytest.approx(0.02)
        assert early.ratio_as_of_date == date(2026, 1, 1)
        assert early.purified_amount == pytest.approx(early.dividend_cash_received * 0.02)

        later = by_ex_date[date(2026, 5, 15)]
        assert later.ratio_used == pytest.approx(0.04)
        assert later.ratio_as_of_date == date(2026, 4, 1)
        assert later.purified_amount == pytest.approx(later.dividend_cash_received * 0.04)

        # The never-undercount property, stated as a direct assertion: neither entry's ratio was
        # cross-applied to the other's dividend.
        assert early.ratio_used != later.ratio_used
    finally:
        con.close()


# ── §8 AC2 / §3.2: a Pure-verdict ticker's dividends produce ZERO ledger entries ──────────────────


def test_pure_verdict_dividend_produces_zero_entries_not_a_zero_amount_entry(
    tmp_path: Path,
) -> None:
    con = _build_db(tmp_path, (fx.ZZPURE_DIV01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZPURE_DIV01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        assert len(result.dividend_events) == 1
        assert result.dividend_events[0].verdict_at_ex_date is Verdict.PURE

        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)
        assert ledger.dividend_entries == ()
        assert ledger.purification_liability == pytest.approx(0.0)
    finally:
        con.close()


# ── §8 AC4 / G-P6: a grace-window dividend falls back to the last-Mixed ratio, never 0.0 ──────────


def _grace_dividend_ticker() -> fx.SyntheticTicker:
    """Ad-hoc, test-local fixture (mirrors `test_backtest_clock.py`'s own `_stable_ticker`/`ZZDIV01`
    precedent): MIXED at rebalance 1 (2026-01-01, non_permissible_income_ratio 2%), flips
    NON_COMPLIANT at rebalance 2 (2026-04-01, debt ratio 35% > 30% threshold — the same
    debt-fact-drift mechanism `ZZNONCOMP_RATIO01`/`ZZFLIP01` already exercise), and pays a dividend
    on 2026-05-15 — squarely inside its `HELD_NONCOMPLIANT_GRACE` window (flip 2026-04-01, divest
    2026-07-01 under the default 1-rebalance grace period)."""
    early_income = fx.FundamentalsFactFixture(
        taxonomy="us-gaap",
        tag="InvestmentIncomeInterest",
        unit="USD",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        is_instantaneous=False,
        value=1_000_000.0,
        accn="9990000401-26-000003",
        filed=date(2025, 6, 1),
    )
    early_debt = fx.FundamentalsFactFixture(
        taxonomy="us-gaap",
        tag="LongTermDebtNoncurrent",
        unit="USD",
        period_start=date(2025, 12, 31),
        period_end=date(2025, 12, 31),
        is_instantaneous=True,
        value=0.0,
        accn="9990000401-26-000004",
        filed=date(2025, 6, 1),
    )
    flip_debt = fx.FundamentalsFactFixture(
        taxonomy="us-gaap",
        tag="LongTermDebtNoncurrent",
        unit="USD",
        period_start=date(2025, 12, 31),
        period_end=date(2025, 12, 31),
        is_instantaneous=True,
        value=35_000_000.0,
        accn="9990000401-26-000005",
        filed=date(2026, 2, 1),
    )
    return fx.SyntheticTicker(
        ticker="ZZGRACE_DIV01",
        cik="9990000401",
        sic=_CLEAN_SIC,
        description="ad-hoc Phase 6 test fixture: a dividend paid during the grace window.",
        facts=(
            fx.FundamentalsFactFixture(
                taxonomy="dei",
                tag="EntityCommonStockSharesOutstanding",
                unit="shares",
                period_start=date(2025, 12, 31),
                period_end=date(2025, 12, 31),
                is_instantaneous=True,
                value=1_000_000.0,
                accn="9990000401-26-000001",
                filed=date(2025, 6, 1),
            ),
            fx.FundamentalsFactFixture(
                taxonomy="us-gaap",
                tag="Revenues",
                unit="USD",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                is_instantaneous=False,
                value=50_000_000.0,
                accn="9990000401-26-000002",
                filed=date(2025, 6, 1),
            ),
            early_income,
            early_debt,
            flip_debt,
        ),
        price_bars=(
            fx.PriceBarFixture(trade_date=date(2026, 1, 1), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 4, 1), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 5, 15), raw_close=100.0, div_cash=5.0),
            fx.PriceBarFixture(trade_date=date(2026, 7, 1), raw_close=100.0),
        ),
    )


def test_grace_window_dividend_falls_back_to_last_mixed_ratio_never_zero(tmp_path: Path) -> None:
    ticker = _grace_dividend_ticker()
    con = _build_db(tmp_path, (ticker,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZGRACE_DIV01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        assert len(result.dividend_events) == 1
        dividend_event = result.dividend_events[0]
        assert dividend_event.verdict_at_ex_date is Verdict.NON_COMPLIANT  # paid during grace

        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)

        assert len(ledger.dividend_entries) == 1
        entry = ledger.dividend_entries[0]
        # Falls back to rebalance 1's MIXED ratio (2%) — never the flip rebalance's own (absent)
        # ratio, and never a bare 0.0.
        assert entry.ratio_as_of_date == date(2026, 1, 1)
        assert entry.ratio_used == pytest.approx(0.02)
        assert entry.ratio_used != 0.0
        assert entry.purified_amount == pytest.approx(entry.dividend_cash_received * 0.02)
    finally:
        con.close()


# ── §8 AC3 / §7 G-P4: Fork C is gated by fiqh_params.purify_capital_gains, not hardcoded ──────────


def _divest_apprec_backtest_result(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> BacktestResult:
    envelope = run_backtest(
        tickers=frozenset({"ZZDIVEST_APPREC01"}),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 7, 1),
        initial_cash=1_000_000.0,
        strategy=EqualWeightStrategy(),
        con=con,
        cache_dir=tmp_path,
    )
    return BacktestResult.model_validate(envelope.payload)


def test_divestment_attribution_gated_by_purify_capital_gains_config(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZDIVEST_APPREC01,))
    try:
        result = _divest_apprec_backtest_result(con, tmp_path)
        assert len(result.divestment_events) == 1
        event = result.divestment_events[0]
        assert event.flip_date == date(2026, 4, 1)
        assert event.divest_date == date(2026, 7, 1)

        # DEFAULT: purify_capital_gains.value is False -> zero divestment entries.
        purified_default = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger_default = PurificationLedger.model_validate(purified_default.purification_ledger)
        assert ledger_default.divestment_entries == ()

        # Explicit opt-in via model_copy -> one, correctly-bounded entry.
        opted_in_params = FIQH_PARAMS.model_copy(
            update={
                "purify_capital_gains": FIQH_PARAMS.purify_capital_gains.model_copy(
                    update={"value": True}
                )
            }
        )
        purified_opt_in = purify_backtest_result(
            result, con=con, cache_dir=tmp_path, fiqh_params=opted_in_params
        )
        ledger_opt_in = PurificationLedger.model_validate(purified_opt_in.purification_ledger)
        assert len(ledger_opt_in.divestment_entries) == 1
        entry = ledger_opt_in.divestment_entries[0]
        assert entry.flip_date == event.flip_date
        assert entry.divest_date == event.divest_date
        assert entry.price_at_flip == pytest.approx(100.0)
        assert entry.price_at_divest == pytest.approx(130.0)
        assert entry.purified_amount == pytest.approx(entry.quantity_liquidated * 30.0)
        assert entry.quantity_liquidated > 0.0
    finally:
        con.close()


# ── §8 AC5 / §7 G-P3: gross_return and net_of_purification_return, distinct and correctly related


def test_gross_and_net_of_purification_return_distinct_when_liability_nonzero(
    tmp_path: Path,
) -> None:
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZMIXED_RATIODRIFT01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)

        assert ledger.purification_liability > 0.0
        start_value = result.daily_snapshots[0].portfolio_value
        expected_net = ledger.gross_return - ledger.purification_liability / start_value
        assert ledger.net_of_purification_return == pytest.approx(expected_net)
        assert ledger.gross_return != pytest.approx(ledger.net_of_purification_return)
    finally:
        con.close()


def test_gross_and_net_of_purification_return_equal_when_ledger_empty(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZPURE01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZPURE01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            initial_cash=1_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)

        assert ledger.purification_liability == pytest.approx(0.0)
        assert ledger.gross_return == pytest.approx(ledger.net_of_purification_return)
    finally:
        con.close()


# ── §8 AC6: BacktestResult.purification_ledger round-trips losslessly ─────────────────────────────


def test_purification_ledger_round_trips_losslessly(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZMIXED_RATIODRIFT01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)

        reconstructed = PurificationLedger.model_validate(purified.purification_ledger)
        assert reconstructed.model_dump() == purified.purification_ledger
    finally:
        con.close()


# ── §8 AC7 / §7 G-P3: every OTHER BacktestResult field is unchanged ───────────────────────────────


def test_purify_backtest_result_changes_only_the_purification_ledger_field(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZMIXED_RATIODRIFT01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)

        assert purified.daily_snapshots == result.daily_snapshots
        assert purified.divestment_events == result.divestment_events
        assert purified.dividend_events == result.dividend_events
        assert purified.compliance_states == result.compliance_states
        assert result.purification_ledger is None
        assert purified.purification_ledger is not None
    finally:
        con.close()


# ── §8 AC8: a reconciliation pass accounts for every dividend ─────────────────────────────────────


def test_reconciliation_every_dividend_is_accounted_for(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01, fx.ZZPURE_DIV01))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZMIXED_RATIODRIFT01", "ZZPURE_DIV01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)

        purified_dividend_cash = sum(e.dividend_cash_received for e in ledger.dividend_entries)
        pure_dividend_cash = sum(
            d.cash_received for d in result.dividend_events if d.verdict_at_ex_date is Verdict.PURE
        )
        total_dividend_cash = sum(d.cash_received for d in result.dividend_events)

        assert purified_dividend_cash + pure_dividend_cash == pytest.approx(total_dividend_cash)
        assert total_dividend_cash > 0.0  # sanity: the fixtures actually paid dividends
    finally:
        con.close()


# ── §7 G-P7: purify_backtest_result reuses the caller's own con/cache_dir/overrides/fiqh_params ───


def test_purify_backtest_result_reuses_caller_supplied_con_and_cache_dir(tmp_path: Path) -> None:
    """A ticker `screen()`-able once against a given `con`/`cache_dir` must be `screen()`-able again
    here against the SAME values — proven by running `purify_backtest_result` a second time, against
    a freshly-materialized DIFFERENT cache_dir with no fixture data at all, and observing it fail
    (there is nothing to fall back to) precisely because the caller-supplied `cache_dir` is what
    Phase 6 actually reads, not some other, implicitly-derived location.
    """
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01,))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZMIXED_RATIODRIFT01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)

        # The SAME cache_dir the backtest itself used -> succeeds.
        purified = purify_backtest_result(result, con=con, cache_dir=tmp_path)
        ledger = PurificationLedger.model_validate(purified.purification_ledger)
        assert len(ledger.dividend_entries) == 2

        # A DIFFERENT, empty cache_dir -> the re-derivation cannot resolve the ticker's CIK at all.
        empty_cache_dir = tmp_path / "empty_cache"
        empty_cache_dir.mkdir()
        with pytest.raises(Exception):  # noqa: B017, PT011 -- CikResolutionError, re-raised as-is
            purify_backtest_result(result, con=con, cache_dir=empty_cache_dir)
    finally:
        con.close()


# ── §8 AC12 / §8 AC13: model discipline ───────────────────────────────────────────────────────────


def test_every_purification_model_inherits_mizan_base_model() -> None:
    assert issubclass(DividendPurificationEntry, MizanBaseModel)
    assert issubclass(PurificationLedger, MizanBaseModel)


def test_backtest_result_purification_ledger_field_type_is_unchanged() -> None:
    import mizan.backtest.clock as clock_module

    source = inspect.getsource(clock_module)
    assert "purification_ledger: dict[str, object] | None = None" in source


# ── §7 guards G-LLM6 / G-BOUND2 / G-DB6 / G-P5: package-wide greps, re-run as tests ───────────────

_PURIFICATION_MODULE_NAMES = (
    "mizan.purification.ledger",
    "mizan.purification.attribution",
)


def _import_purification_modules() -> list[object]:
    import importlib

    return [importlib.import_module(name) for name in _PURIFICATION_MODULE_NAMES]


def test_no_llm_import_anywhere_in_purification_package() -> None:
    for module in _import_purification_modules():
        source = inspect.getsource(module).lower()  # type: ignore[arg-type]
        for forbidden in (
            "openai",
            "anthropic",
            "gemini",
            "vertex",
            "langchain",
            "chat_completion",
        ):
            assert forbidden not in source, f"{module!r} references forbidden term {forbidden!r}"


def test_no_write_statement_anywhere_in_purification_package() -> None:
    """G-DB6 / G-P5: no INSERT/CREATE/ALTER/DROP anywhere under mizan/purification/."""
    for module in _import_purification_modules():
        source = inspect.getsource(module).upper()  # type: ignore[arg-type]
        for forbidden in ("INSERT INTO", "CREATE TABLE", "ALTER TABLE", "DROP TABLE"):
            assert forbidden not in source, f"{module!r} contains {forbidden!r}"


def test_no_duckdb_connect_anywhere_in_purification_package() -> None:
    """G-DB6: `mizan/purification/` never opens its own DuckDB connection."""
    for module in _import_purification_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        assert "duckdb.connect" not in source


_BOUNDARY_WORDS = (
    "short",
    "shorts",
    "shorting",
    "borrow",
    "borrowed",
    "borrowing",
    "margin",
    "leverage",
    "leveraged",
    "levered",
    "option",
    "options",
    "future",
    "futures",
    "swap",
    "swaps",
    "derivative",
    "derivatives",
)


def test_no_boundary_crossing_primitive_named_anywhere_in_purification_package() -> None:
    """G-BOUND2 / §8 AC14: none of short/borrow/margin/leverage/option/future/swap/derivative
    appears anywhere (docstring, comment, or identifier) under mizan/purification/. `\\b`-delimited
    word matching (the same semantics `§7`'s own grep line uses) so `from __future__ import
    annotations` — a Python language keyword, not the boundary-crossing "future" concept — does not
    false-positive: `_` is a word character, so `\\bfuture\\b` never matches inside `__future__`.
    """
    import re

    for module in _import_purification_modules():
        source = inspect.getsource(module).lower()  # type: ignore[arg-type]
        for word in _BOUNDARY_WORDS:
            pattern = re.compile(rf"\b{re.escape(word)}\b")
            assert not pattern.search(source), f"{module!r} names forbidden concept {word!r}"


def test_no_pandas_or_matplotlib_or_pyarrow_import_in_purification_package() -> None:
    """§8 AC19: no premature imports."""
    for module in _import_purification_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        for forbidden in ("import pandas", "import matplotlib", "import pyarrow"):
            assert forbidden not in source, f"{module!r} contains {forbidden!r}"
