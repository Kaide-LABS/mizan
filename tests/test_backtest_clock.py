"""Tests for mizan/backtest/clock.py — the daily loop, the rebalance trigger, and run_backtest().

Implements PHASE_5_SPEC.md §8 acceptance criteria 1 (flip -> grace -> divest, end-to-end), 2 (grace
period config drift, end-to-end), 4 (a strategy cannot select a Non-compliant ticker, end-to-end), 6
(every holding re-screened every rebalance), 8 (rebalance cadence exactly quarterly), 10 (a
divestment records flip/divest dates), 11 (a dividend records the verdict active at its ex-date), 12
(purification_ledger always None), 13/24 (boundary greps), 14 (never writes to DuckDB), plus guards
G-B2a, G-B3, G-B6, G-DB4, G-VB1, G-LLM5, G-BOUND1.
"""

from __future__ import annotations

import inspect
import io
import tokenize
from datetime import date
from typing import TYPE_CHECKING

import pytest

from mizan.backtest.clock import (
    BacktestResult,
    generate_rebalance_dates,
    run_backtest,
    step,
)
from mizan.backtest.compliance_state import HoldingComplianceState
from mizan.backtest.portfolio import Holding, Portfolio
from mizan.backtest.strategy import (
    AllocationInstruction,
    EqualWeightStrategy,
    StrategyContractViolationError,
)
from mizan.config.fiqh_params import FIQH_PARAMS
from mizan.core.verdict import Verdict
from mizan.data import db
from tests.fixtures import synthetic_universe as fx

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import duckdb

_CLEAN_SIC = "7372"


def _stable_ticker(ticker: str, cik: str) -> fx.SyntheticTicker:
    """An ad-hoc, always Layer-1-clean, all-zero-ratio PURE fixture ticker — a Phase 5 test-only
    "always compliant" companion, distinct from `ALL_SYNTHETIC_TICKERS`, resolvable from
    `date(2026, 1, 1)` onward (every fact filed `2025-06-01`, well before this suite's earliest
    rebalance date)."""
    return fx.SyntheticTicker(
        ticker=ticker,
        cik=cik,
        sic=_CLEAN_SIC,
        description="ad-hoc Phase 5 test fixture: always Layer-1-clean, all-zero-ratio compliant.",
        facts=(
            fx.FundamentalsFactFixture(
                taxonomy="dei",
                tag="EntityCommonStockSharesOutstanding",
                unit="shares",
                period_start=date(2025, 12, 31),
                period_end=date(2025, 12, 31),
                is_instantaneous=True,
                value=1_000_000.0,
                accn=f"{cik}-26-000001",
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
                accn=f"{cik}-26-000002",
                filed=date(2025, 6, 1),
            ),
        ),
        price_bars=(
            fx.PriceBarFixture(trade_date=date(2026, 1, 1), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 4, 1), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 7, 1), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 10, 1), raw_close=100.0),
        ),
    )


def _build_db(tmp_path: Path, tickers: Sequence[fx.SyntheticTicker]) -> duckdb.DuckDBPyConnection:
    fx.write_universe_cache(tmp_path, tickers)
    con = db.connect(tmp_path / "test.duckdb")
    for ticker in tickers:
        fx.load_into_duckdb(con, ticker)
    return con


_START = date(2026, 1, 1)
_END = date(2026, 10, 15)


# ── §8 AC8 / G-VB1: generate_rebalance_dates is exactly quarterly ──────────────────────────────


def test_generate_rebalance_dates_includes_start_date_first() -> None:
    dates = generate_rebalance_dates(date(2026, 2, 15), date(2026, 12, 31))
    assert dates[0] == date(2026, 2, 15)


def test_generate_rebalance_dates_lands_only_on_quarter_boundaries_after_start() -> None:
    dates = generate_rebalance_dates(_START, date(2027, 12, 31))
    assert dates == (
        date(2026, 1, 1),
        date(2026, 4, 1),
        date(2026, 7, 1),
        date(2026, 10, 1),
        date(2027, 1, 1),
        date(2027, 4, 1),
        date(2027, 7, 1),
        date(2027, 10, 1),
    )


def test_generate_rebalance_dates_includes_end_date_exactly_on_a_boundary() -> None:
    dates = generate_rebalance_dates(_START, date(2026, 4, 1))
    assert dates == (date(2026, 1, 1), date(2026, 4, 1))


def test_generate_rebalance_dates_excludes_a_boundary_strictly_after_end_date() -> None:
    dates = generate_rebalance_dates(_START, date(2026, 3, 31))
    assert dates == (date(2026, 1, 1),)


def test_generate_rebalance_dates_is_pure_and_deterministic() -> None:
    args = (_START, date(2026, 12, 31))
    assert generate_rebalance_dates(*args) == generate_rebalance_dates(*args)


# ── step(): split-only, no-trade day advance ────────────────────────────────────────────────────


def test_step_applies_split_to_a_held_ticker_with_a_nontrivial_factor() -> None:
    portfolio = Portfolio(
        cash=0.0, holdings={"ZZFLIP01": Holding(ticker="ZZFLIP01", quantity=10.0)}
    )
    result = step(portfolio, prices={}, splits={"ZZFLIP01": 2.0})
    assert result.holdings["ZZFLIP01"].quantity == pytest.approx(20.0)


def test_step_leaves_a_holding_with_no_split_entry_untouched() -> None:
    portfolio = Portfolio(
        cash=0.0, holdings={"ZZFLIP01": Holding(ticker="ZZFLIP01", quantity=10.0)}
    )
    result = step(portfolio, prices={}, splits={})
    assert result.holdings["ZZFLIP01"].quantity == pytest.approx(10.0)


# ── §8 AC1 / AC10: the flip -> grace -> divest sequence, end-to-end ─────────────────────────────


def test_full_backtest_flip_grace_divest_sequence(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZFLIP01, _stable_ticker("ZZSTABLE01", "9990000201")))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZFLIP01", "ZZSTABLE01"}),
            start_date=_START,
            end_date=_END,
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)

        record = result.compliance_states["ZZFLIP01"]
        assert record.state is HoldingComplianceState.DIVESTED
        assert record.flip_date == date(2026, 4, 1)
        assert record.divest_date == date(2026, 7, 1)
        verdicts = [obs.verdict for obs in record.verdict_history]
        assert verdicts == [Verdict.PURE, Verdict.NON_COMPLIANT, Verdict.NON_COMPLIANT]

        assert len(result.divestment_events) == 1
        event = result.divestment_events[0]
        assert event.ticker == "ZZFLIP01"
        assert event.flip_date == date(2026, 4, 1)
        assert event.divest_date == date(2026, 7, 1)
        assert event.flip_date <= event.divest_date  # §8 AC10
    finally:
        con.close()


def test_grace_holding_survives_unsold_through_its_grace_window(tmp_path: Path) -> None:
    """MASTER_PRD.md §7.3's own diagram: HELD(non-compliant, grace) is still HELD, not sold, until
    the scheduled forced-divestment rebalance."""
    con = _build_db(tmp_path, (fx.ZZFLIP01, _stable_ticker("ZZSTABLE01", "9990000201")))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZFLIP01", "ZZSTABLE01"}),
            start_date=_START,
            end_date=date(2026, 6, 30),  # stop BEFORE the divest rebalance (2026-07-01)
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        record = result.compliance_states["ZZFLIP01"]
        assert record.state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE
        last_snapshot = result.daily_snapshots[-1]
        assert last_snapshot.holdings.get("ZZFLIP01", 0.0) > 0.0
    finally:
        con.close()


# ── §8 AC2 / G-B4: grace period is read from config, not hardcoded ──────────────────────────────


def test_grace_period_config_drift_delays_divestment_by_one_rebalance(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZFLIP01, _stable_ticker("ZZSTABLE01", "9990000201")))
    try:
        params = FIQH_PARAMS.model_copy(
            update={
                "grace_period_rebalances": FIQH_PARAMS.grace_period_rebalances.model_copy(
                    update={"value": 2}
                )
            }
        )
        envelope = run_backtest(
            tickers=frozenset({"ZZFLIP01", "ZZSTABLE01"}),
            start_date=_START,
            end_date=_END,
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
            fiqh_params=params,
        )
        result = BacktestResult.model_validate(envelope.payload)
        record = result.compliance_states["ZZFLIP01"]
        assert record.state is HoldingComplianceState.DIVESTED
        assert record.flip_date == date(2026, 4, 1)
        assert record.divest_date == date(2026, 10, 1)  # one full rebalance later than the default
        assert result.divestment_events[0].divest_date == date(2026, 10, 1)
    finally:
        con.close()


# ── §8 AC4 / G-B2a: a strategy cannot select a Non-compliant ticker ─────────────────────────────


class _SpyStrategy:
    """Wraps `EqualWeightStrategy`'s own logic while recording every `compliant_tickers` argument it
    was ever called with."""

    def __init__(self) -> None:
        self.received_compliant_tickers: list[frozenset[str]] = []
        self._inner = EqualWeightStrategy()

    def select(
        self, *, as_of_date: date, compliant_tickers: frozenset[str], portfolio: Portfolio
    ) -> AllocationInstruction:
        self.received_compliant_tickers.append(compliant_tickers)
        return self._inner.select(
            as_of_date=as_of_date, compliant_tickers=compliant_tickers, portfolio=portfolio
        )


def test_compliant_tickers_never_includes_a_noncompliant_ticker(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (fx.ZZFLIP01, _stable_ticker("ZZSTABLE01", "9990000201")))
    try:
        spy = _SpyStrategy()
        run_backtest(
            tickers=frozenset({"ZZFLIP01", "ZZSTABLE01"}),
            start_date=_START,
            end_date=_END,
            initial_cash=1_000_000.0,
            strategy=spy,
            con=con,
            cache_dir=tmp_path,
        )
        assert spy.received_compliant_tickers[0] == frozenset({"ZZFLIP01", "ZZSTABLE01"})
        for later_call in spy.received_compliant_tickers[1:]:
            assert "ZZFLIP01" not in later_call
    finally:
        con.close()


class _BrokenStrategy:
    """A deliberately-broken test `Strategy` that manufactures a hardcoded ticker name from OUTSIDE
    `compliant_tickers` — the adversarial case `StrategyContractViolationError` exists to catch."""

    def select(
        self, *, as_of_date: date, compliant_tickers: frozenset[str], portfolio: Portfolio
    ) -> AllocationInstruction:
        return AllocationInstruction(target_weights={"ZZFLIP01": 1.0})


def test_broken_strategy_naming_a_noncompliant_ticker_raises_contract_violation(
    tmp_path: Path,
) -> None:
    con = _build_db(tmp_path, (fx.ZZFLIP01, _stable_ticker("ZZSTABLE01", "9990000201")))
    try:
        with pytest.raises(StrategyContractViolationError):
            run_backtest(
                tickers=frozenset({"ZZFLIP01", "ZZSTABLE01"}),
                start_date=date(2026, 4, 1),  # ZZFLIP01 is already NON_COMPLIANT here
                end_date=date(2026, 4, 1),
                initial_cash=1_000_000.0,
                strategy=_BrokenStrategy(),
                con=con,
                cache_dir=tmp_path,
            )
    finally:
        con.close()


# ── §8 AC6 / G-B3: every universe ticker is re-screened at every rebalance ──────────────────────


def test_every_universe_ticker_is_rescreened_at_every_rebalance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mizan.screening.verdict as screening_verdict_module

    con = _build_db(tmp_path, (fx.ZZFLIP01, _stable_ticker("ZZSTABLE01", "9990000201")))
    try:
        original_screen = screening_verdict_module.screen
        call_count = 0

        def _counting_screen(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            return original_screen(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(screening_verdict_module, "screen", _counting_screen)

        universe = frozenset({"ZZFLIP01", "ZZSTABLE01"})
        rebalance_dates = generate_rebalance_dates(_START, _END)

        run_backtest(
            tickers=universe,
            start_date=_START,
            end_date=_END,
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )

        assert call_count == len(universe) * len(rebalance_dates)
    finally:
        con.close()


# ── §8 AC11: a dividend records the verdict active at its ex-date ──────────────────────────────


def test_dividend_event_records_the_most_recently_established_verdict(tmp_path: Path) -> None:
    ticker = fx.SyntheticTicker(
        ticker="ZZDIV01",
        cik="9990000301",
        sic=_CLEAN_SIC,
        description="ad-hoc Phase 5 dividend-event fixture.",
        facts=(
            fx.FundamentalsFactFixture(
                taxonomy="dei",
                tag="EntityCommonStockSharesOutstanding",
                unit="shares",
                period_start=date(2025, 12, 31),
                period_end=date(2025, 12, 31),
                is_instantaneous=True,
                value=1_000_000.0,
                accn="9990000301-26-000001",
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
                accn="9990000301-26-000002",
                filed=date(2025, 6, 1),
            ),
        ),
        price_bars=(
            fx.PriceBarFixture(trade_date=date(2026, 1, 1), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 2, 15), raw_close=100.0),
            fx.PriceBarFixture(trade_date=date(2026, 4, 1), raw_close=100.0),
        ),
    )
    con = _build_db(tmp_path, (ticker,))
    try:
        con.execute(
            "UPDATE price_bars SET div_cash = ? WHERE ticker = ? AND trade_date = ?",
            [2.0, "ZZDIV01", date(2026, 2, 15)],
        )

        envelope = run_backtest(
            tickers=frozenset({"ZZDIV01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            initial_cash=1_000_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)

        assert len(result.dividend_events) == 1
        event = result.dividend_events[0]
        assert event.ticker == "ZZDIV01"
        assert event.ex_date == date(2026, 2, 15)
        assert event.div_cash_per_share == pytest.approx(2.0)
        assert event.verdict_at_ex_date is Verdict.PURE
        assert event.cash_received == pytest.approx(event.quantity_held * 2.0)
    finally:
        con.close()


# ── §8 AC12: purification_ledger is always None ─────────────────────────────────────────────────


def test_purification_ledger_is_always_none(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (_stable_ticker("ZZSTABLE01", "9990000201"),))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZSTABLE01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            initial_cash=1_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        result = BacktestResult.model_validate(envelope.payload)
        assert result.purification_ledger is None
    finally:
        con.close()


def test_run_backtest_stamps_the_three_expected_caveats(tmp_path: Path) -> None:
    from mizan.core.caveats import Caveat

    con = _build_db(tmp_path, (_stable_ticker("ZZSTABLE01", "9990000201"),))
    try:
        envelope = run_backtest(
            tickers=frozenset({"ZZSTABLE01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            initial_cash=1_000.0,
            strategy=EqualWeightStrategy(),
            con=con,
            cache_dir=tmp_path,
        )
        assert envelope.active_caveats == (
            Caveat.LOOK_AHEAD_BIAS,
            Caveat.SURVIVORSHIP_BIAS,
            Caveat.PENDING_SCHOLARLY_VERIFICATION,
        )
    finally:
        con.close()


# ── §8 AC14 / G-DB4: backtest never writes to DuckDB ────────────────────────────────────────────


def test_run_backtest_works_against_a_read_only_connection(tmp_path: Path) -> None:
    con = _build_db(tmp_path, (_stable_ticker("ZZSTABLE01", "9990000201"),))
    con.close()
    ro_con = db.connect(tmp_path / "test.duckdb", read_only=True)
    try:
        run_backtest(
            tickers=frozenset({"ZZSTABLE01"}),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            initial_cash=1_000.0,
            strategy=EqualWeightStrategy(),
            con=ro_con,
            cache_dir=tmp_path,
        )
    finally:
        ro_con.close()


# ── §8 AC13/AC24, §7 boundary guards: package-wide greps, re-run as tests ───────────────────────

_BACKTEST_MODULE_NAMES = (
    "mizan.backtest.portfolio",
    "mizan.backtest.strategy",
    "mizan.backtest.compliance_state",
    "mizan.backtest.clock",
    "mizan.cli.backtest",
)


def _import_backtest_modules() -> list[object]:
    import importlib

    return [importlib.import_module(name) for name in _BACKTEST_MODULE_NAMES]


def test_no_llm_import_anywhere_in_backtest_package() -> None:
    for module in _import_backtest_modules():
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


def test_no_write_statement_anywhere_in_backtest_package() -> None:
    """G-DB4: no INSERT/CREATE/ALTER anywhere under mizan/backtest/ or mizan/cli/backtest.py."""
    for module in _import_backtest_modules():
        source = inspect.getsource(module).upper()  # type: ignore[arg-type]
        for forbidden in ("INSERT INTO", "CREATE TABLE", "ALTER TABLE"):
            assert forbidden not in source, f"{module!r} contains {forbidden!r}"


def test_no_date_today_or_datetime_now_anywhere_in_backtest_package() -> None:
    """G-B6: `rebalance()` always passes the current rebalance's own as_of_date to screen() — never
    a cached/stale date, never `date.today()`."""
    for module in _import_backtest_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        assert "date.today" not in source
        assert "datetime.now" not in source


#: Token types that hold docstring/comment/string-literal text — excluded from the executable-code
#: checks below, both of which must tolerate a docstring/comment NAMING a forbidden word (to explain
#: why it is forbidden, or as a negative example of a flag that does NOT exist) without that prose
#: counting as a violation. Looked up by name via `getattr` so this test passes on both pre-3.12
#: Python (a single `STRING` token per f-string) and 3.12+ (an f-string is split into
#: `FSTRING_START`/`FSTRING_MIDDLE`/`FSTRING_END` tokens) without needing a version branch.
_NON_EXECUTABLE_TOKEN_TYPES = frozenset(
    token_type
    for name in ("STRING", "COMMENT", "FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
    if (token_type := getattr(tokenize, name, None)) is not None
)


def _word_in_executable_code(source: str, word: str) -> bool:
    """True iff `word` appears, as a whole word (`\\b`-delimited — so `future` does NOT match
    inside `__future__`), in a NAME/OP/NUMBER token executed by the interpreter — never inside a
    string literal, an f-string text segment, or a `#` comment."""
    import re

    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for tok in tokens:
        if tok.type in _NON_EXECUTABLE_TOKEN_TYPES:
            continue
        if pattern.search(tok.string):
            return True
    return False


def test_no_rebalance_frequency_flag_or_daily_signal_naming_anywhere() -> None:
    """§7 guard G-VB1: no CLI flag, function parameter, or naming anywhere under mizan/backtest/ or
    mizan/cli/backtest.py can shorten the rebalance cadence below quarterly. A docstring naming
    `--rebalance-frequency` as a flag that does NOT exist (this module's own documentation of the
    guard) is not itself a violation — only an actual identifier/flag/string LITERAL in executable
    code would be."""
    for module in _import_backtest_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        for forbidden in (
            "rebalance_frequency",
            "daily_rebalance",
            "intraday",
            "hourly_rebalance",
            "minute_rebalance",
            "tick_rebalance",
        ):
            assert not _word_in_executable_code(source, forbidden), (
                f"{module!r} contains {forbidden!r} in executable code"
            )


#: Words `PHASE_5_SPEC.md` §7 guard G-BOUND1 forbids in EXECUTABLE code (never in a docstring/
#: comment explaining why the concept is forbidden — those are permitted and expected).
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


def test_no_boundary_crossing_primitive_named_in_executable_code() -> None:
    """§7 guard G-BOUND1 / §8 AC13: none of short/borrow/margin/leverage/option/future/swap/
    derivative appears in EXECUTABLE code anywhere under mizan/backtest/ or mizan/cli/backtest.py —
    only ever inside a docstring/comment explaining why the concept is forbidden (or, for `future`,
    as part of the `__future__` import statement, which `\\b`-word-boundary matching excludes)."""
    for module in _import_backtest_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        for word in _BOUNDARY_WORDS:
            assert not _word_in_executable_code(source, word), (
                f"{module!r} names forbidden concept {word!r} in executable code, not just prose"
            )


def test_no_pandas_or_matplotlib_or_pyarrow_import_in_backtest_package() -> None:
    """§8 AC21: no premature imports — pandas/matplotlib imported by no module under mizan/;
    pyarrow imported by no module under mizan/backtest/."""
    for module in _import_backtest_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        for forbidden in ("import pandas", "import matplotlib", "import pyarrow"):
            assert forbidden not in source, f"{module!r} contains {forbidden!r}"


def test_no_screening_or_data_module_is_reshaped() -> None:
    """§9's own restated non-goal: Phase 5 imports and calls screen()/db.connect()/
    load_override_map — it reshapes none of them. A crude but effective proxy: no module under
    mizan/backtest/ or mizan/cli/backtest.py contains a `def screen(` or `def connect(` definition
    of its own (which would shadow/reshape the real ones)."""
    for module in _import_backtest_modules():
        source = inspect.getsource(module)  # type: ignore[arg-type]
        assert "def screen(" not in source
        assert "def connect(" not in source
