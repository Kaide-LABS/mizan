"""mizan/backtest/clock.py — the daily event loop, the quarterly rebalance trigger, and
`run_backtest()`, the canonical Phase 5 entry point.

Implements PHASE_5_SPEC.md §3.4, §4.3, §6b, §6c.

**Grace holdings are frozen during `rebalance()`, stated once here, applying everywhere in this
module:** `MASTER_PRD.md` §7.3's own state-machine diagram shows a flipped holding
(`HoldingComplianceState.HELD_NONCOMPLIANT_GRACE`) surviving, UNSOLD, through its grace window —
"HELD(non-compliant, grace) --forced-divestment scheduled at NEXT rebalance-->". A conforming
`Strategy` can never NAME a non-compliant ticker (`mizan.backtest.strategy`'s own structural
argument), so it never includes a grace-holding in its returned `AllocationInstruction.
target_weights` — and `apply_allocation` (`mizan.backtest.portfolio`) fully liquidates any currently
held ticker absent from `target_weights`. Left alone, that combination would force-sell a grace
holding at the very first non-compliant rebalance, defeating the grace period entirely. `rebalance`
below therefore partitions the post-divestment portfolio into a FROZEN sub-holdings dict (every
ticker currently `HELD_NONCOMPLIANT_GRACE`) and a WORKABLE sub-portfolio (cash + every other
holding); the strategy is consulted with, and `apply_allocation` applied to, only the workable
sub-portfolio, and the frozen holdings are merged back into the result completely untouched (same
quantity, no cash flow). This is the only implementation consistent with the state machine's own
documented intent without weakening `apply_allocation`'s own "absent-from-target liquidates"
contract for every other ticker.

**Import-order note:** `mizan.screening.verdict` is imported as a MODULE (`from mizan.screening
import verdict as screening_verdict`), never as `from mizan.screening.verdict import screen` — a
test wrapping `mizan.screening.verdict.screen` with a call-counting spy (`monkeypatch.setattr(
"mizan.screening.verdict.screen", spy)`, §7 guard G-B3's own literal wording) must actually affect
every call this module makes; importing the bare name would bind this module's own local reference
to the ORIGINAL function object at import time, permanently invisible to a later patch on the
`mizan.screening.verdict` module's own attribute.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from mizan.backtest.compliance_state import (
    ComplianceStateRecord,
    DivestmentEvent,
    DividendEvent,
    HoldingComplianceState,
    transition,
)
from mizan.backtest.portfolio import (
    Holding,
    Portfolio,
    apply_allocation,
    apply_cash_yield,
    apply_split,
    credit_dividend,
    mark_to_market,
)
from mizan.backtest.strategy import StrategyContractViolationError
from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict
from mizan.screening import verdict as screening_verdict

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

    from mizan.backtest.strategy import Strategy
    from mizan.screening.business_activity import BusinessActivityOverrideMap

#: The rebalance cadence. HARDCODED — not a `FiqhParams` register entry, not a CLI flag, not a
#: function parameter anywhere in this module. `ULTIMATE_PRD.md` §1.1: "a proposal to shorten the
#: rebalance cadence below quarterly... is crossing a values boundary, not tuning a
#: parameter... must be escalated to the human, never absorbed as an enhancement." This is the
#: simplest possible
#: guarantee of that: there is no code path, flag, or config value anywhere under `mizan/backtest/`
#: that can make a backtest rebalance faster than quarterly, because the calendar-quarter-boundary
#: months below are the ONLY rebalance-date generator this module contains.
_REBALANCE_MONTHS: tuple[int, ...] = (1, 4, 7, 10)


class DailySnapshot(MizanBaseModel):
    """One trading day's mark-to-market state — the `returns` element of `ULTIMATE_PRD.md` §2.1's
    `(returns, purification_ledger, active_caveats)` tuple, in its raw (not-yet-return-computed)
    form; Phase 7's reporter is where a snapshot series becomes an actual return series."""

    as_of_date: date
    cash: float
    holdings: dict[str, float]
    """ticker -> quantity, a snapshot copy (never the live `Portfolio` object)."""
    portfolio_value: float
    """`cash + sum(quantity * raw_close)` that day — see this module's own docstring /
    PHASE_5_SPEC.md §6a for why `raw_close`."""


class BacktestResult(MizanBaseModel):
    """The Phase-5-scoped result type: a fully-typed value every internal function/test works
    with, wrapped in `ResultEnvelope` only at the final return (`run_backtest`), never exposed
    unwrapped to a human-facing caller — the same precedent `mizan.screening.verdict.
    ScreeningVerdict` set.

    `purification_ledger` is a deliberate, loose placeholder — `dict[str, object] | None`,
    defaulting to `None` — for exactly the same reason `mizan.core.caveats.ResultEnvelope.
    payload` is `dict[str, object]` rather than a phase-specific type: Phase 6 needs to attach a
    real, typed ledger here WITHOUT Phase 5 having to guess its shape, and WITHOUT this field's
    own type ever changing. Phase 5 always leaves it `None` — it computes no purification amount
    (PHASE_5_SPEC.md §1, §9).
    """

    daily_snapshots: tuple[DailySnapshot, ...]
    divestment_events: tuple[DivestmentEvent, ...]
    dividend_events: tuple[DividendEvent, ...]
    compliance_states: dict[str, ComplianceStateRecord]
    """Every ticker ever held, final state."""
    purification_ledger: dict[str, object] | None = None


def generate_rebalance_dates(start_date: date, end_date: date) -> tuple[date, ...]:
    """Deterministic, pure function of its two arguments: `start_date` itself, plus the first
    calendar day of every `_REBALANCE_MONTHS` month strictly between `start_date` and `end_date`
    (inclusive of `end_date` if it happens to land exactly on one). `start_date` is always
    included as the FIRST rebalance — a backtest must deploy its initial capital on day one, not
    wait for the next calendar-quarter boundary; this is a scheduling convenience, not a cadence
    change (the SECOND rebalance is still governed by `_REBALANCE_MONTHS`, so the cadence between
    rebalances 2..N is always exactly quarterly).
    """
    dates: list[date] = [start_date]
    year, month = start_date.year, start_date.month
    while True:
        month += 1
        if month > 12:
            month = 1
            year += 1
        candidate = date(year, month, 1)
        if candidate > end_date:
            break
        if month in _REBALANCE_MONTHS:
            dates.append(candidate)
    return tuple(dates)


def step(portfolio: Portfolio, prices: dict[str, float], splits: dict[str, float]) -> Portfolio:
    """Advance `portfolio` by exactly one trading day with NO trading and NO re-screening:
    applies `apply_split` to every currently-held ticker with a `splits[ticker] != 1.0` entry that
    day, then `apply_cash_yield` (a structural no-op). Dividend crediting is NOT done here — see
    `run_backtest`'s own per-day loop body for why dividend crediting and marking-to-market happen
    at the orchestration level, not inside this single-responsibility step function.

    `prices` is accepted (matching `PHASE_5_SPEC.md` §4.3's exact given signature) but not read by
    this function's own body — it is not needed for a split-only, no-trade, no-valuation day step;
    valuation happens in `run_backtest`'s own loop via `mark_to_market`.
    """
    updated_holdings = dict(portfolio.holdings)
    for ticker, holding in portfolio.holdings.items():
        factor = splits.get(ticker, 1.0)
        if factor != 1.0:
            updated_holdings[ticker] = apply_split(holding, factor)
    split_adjusted = portfolio.model_copy(update={"holdings": updated_holdings})
    return apply_cash_yield(split_adjusted)


def _resolve_trading_dates(
    con: duckdb.DuckDBPyConnection, tickers: frozenset[str], start_date: date, end_date: date
) -> tuple[date, ...]:
    """Every distinct `price_bars.trade_date` for `tickers`, between `start_date` and `end_date`
    inclusive, ascending."""
    if not tickers:
        return ()
    placeholders = ",".join("?" for _ in tickers)
    rows = con.execute(
        f"SELECT DISTINCT trade_date FROM price_bars WHERE ticker IN ({placeholders}) "
        "AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
        [*sorted(tickers), start_date, end_date],
    ).fetchall()
    return tuple(row[0] for row in rows)


def _resolve_day_rows(
    con: duckdb.DuckDBPyConnection, tickers: frozenset[str], as_of_date: date
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """One query for `as_of_date`, decomposed into `(prices, splits, divs)` — `prices`/`splits`
    cover every ticker with a `price_bars` row that day; `divs` covers only tickers with a nonzero
    `div_cash` that day (`PHASE_5_SPEC.md` §6b's own pseudocode shape)."""
    if not tickers:
        return {}, {}, {}
    placeholders = ",".join("?" for _ in tickers)
    rows = con.execute(
        f"SELECT ticker, raw_close, split_factor, div_cash FROM price_bars "
        f"WHERE ticker IN ({placeholders}) AND trade_date = ?",
        [*sorted(tickers), as_of_date],
    ).fetchall()
    prices = {str(ticker): float(raw_close) for ticker, raw_close, _split, _div in rows}
    splits = {str(ticker): float(split) for ticker, _raw, split, _div in rows}
    divs = {str(ticker): float(div) for ticker, _raw, _split, div in rows if float(div) != 0.0}
    return prices, splits, divs


def rebalance(
    portfolio: Portfolio,
    as_of_date: date,
    *,
    universe: frozenset[str],
    strategy: Strategy,
    compliance_states: dict[str, ComplianceStateRecord],
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> tuple[Portfolio, dict[str, ComplianceStateRecord], tuple[DivestmentEvent, ...]]:
    """One quarterly rebalance boundary. Re-screens (via `mizan.screening.verdict.screen`) EVERY
    ticker in `universe` (the full requested candidate set, not just currently-held tickers — a
    strategy must be able to newly ENTER a ticker that only just started passing) plus every ticker
    currently held that has since fallen out of `universe` (should not normally occur, since
    `universe` is fixed for the whole backtest — defensive completeness only). Runs
    `compliance_state.transition` for every currently-held ticker using this rebalance's fresh
    `Verdict`, force-liquidates any ticker whose transition produces `HoldingComplianceState.
    DIVESTED` THIS rebalance (selling it out of the portfolio entirely, at this rebalance's price,
    BEFORE the strategy is consulted — a divested ticker is never offered to `strategy.select()`
    even if its fresh verdict happened to be compliant again), computes `compliant_tickers =
    frozenset of every universe ticker whose fresh Verdict is PURE or MIXED`, freezes every
    currently-held ticker still in its grace window (this module's own top-of-file docstring),
    calls `strategy.select(as_of_date=as_of_date, compliant_tickers=compliant_tickers,
    portfolio=<workable sub-portfolio>)`, validates the returned `AllocationInstruction` names
    only tickers in `compliant_tickers` (`StrategyContractViolationError` otherwise), applies it
    via `apply_allocation`, merges the frozen grace holdings back untouched, and seeds a fresh
    `ComplianceStateRecord` for any ticker newly entering the portfolio this rebalance.
    """
    tickers_to_screen = universe | frozenset(portfolio.holdings)

    fresh_verdicts: dict[str, screening_verdict.ScreeningVerdict] = {}
    for ticker in sorted(tickers_to_screen):
        envelope = screening_verdict.screen(
            ticker,
            as_of_date,
            con=con,
            cache_dir=cache_dir,
            overrides=overrides,
            fiqh_params=fiqh_params,
        )
        fresh_verdicts[ticker] = screening_verdict.ScreeningVerdict.model_validate(envelope.payload)

    prices, _splits, _divs = _resolve_day_rows(con, tickers_to_screen, as_of_date)

    new_compliance_states = dict(compliance_states)
    cash = portfolio.cash
    holdings = dict(portfolio.holdings)
    divestment_events: list[DivestmentEvent] = []

    for ticker in sorted(portfolio.holdings):
        record = new_compliance_states.get(ticker)
        if record is None:
            raise AssertionError(
                f"{ticker}: a currently-held ticker must already have a ComplianceStateRecord"
            )
        verdict_obj = fresh_verdicts[ticker]
        updated_record, divestment_event = transition(
            record,
            ticker=ticker,
            cik=verdict_obj.cik,
            as_of_date=as_of_date,
            new_verdict=verdict_obj.verdict,
            fiqh_params=fiqh_params,
        )
        new_compliance_states[ticker] = updated_record
        if divestment_event is not None:
            divestment_events.append(divestment_event)
            cash += holdings[ticker].quantity * prices[ticker]
            del holdings[ticker]

    portfolio_after_divest = Portfolio(cash=cash, holdings=holdings)

    frozen_holdings: dict[str, Holding] = {}
    workable_holdings: dict[str, Holding] = {}
    for ticker, holding in portfolio_after_divest.holdings.items():
        state = new_compliance_states[ticker].state
        if state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE:
            frozen_holdings[ticker] = holding
        else:
            workable_holdings[ticker] = holding
    workable_portfolio = Portfolio(cash=portfolio_after_divest.cash, holdings=workable_holdings)

    compliant_tickers = frozenset(
        ticker
        for ticker in universe
        if fresh_verdicts[ticker].verdict in (Verdict.PURE, Verdict.MIXED)
    )

    instruction = strategy.select(
        as_of_date=as_of_date, compliant_tickers=compliant_tickers, portfolio=workable_portfolio
    )
    offending = frozenset(instruction.target_weights) - compliant_tickers
    if offending:
        raise StrategyContractViolationError(
            f"strategy {strategy!r} returned target_weights naming ticker(s) {sorted(offending)} "
            f"outside compliant_tickers {sorted(compliant_tickers)}"
        )

    allocated_workable = apply_allocation(workable_portfolio, instruction, prices)

    final_holdings = dict(allocated_workable.holdings)
    final_holdings.update(frozen_holdings)
    final_portfolio = Portfolio(cash=allocated_workable.cash, holdings=final_holdings)

    for ticker in sorted(final_portfolio.holdings):
        if ticker not in new_compliance_states:
            verdict_obj = fresh_verdicts[ticker]
            seeded_record, _event = transition(
                None,
                ticker=ticker,
                cik=verdict_obj.cik,
                as_of_date=as_of_date,
                new_verdict=verdict_obj.verdict,
                fiqh_params=fiqh_params,
            )
            new_compliance_states[ticker] = seeded_record

    return final_portfolio, new_compliance_states, tuple(divestment_events)


def run_backtest(
    *,
    tickers: frozenset[str],
    start_date: date,
    end_date: date,
    initial_cash: float,
    strategy: Strategy,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None = None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ResultEnvelope:
    """THE canonical, singular backtest entry point — this phase's analogue of `screen()`.
    Boot-check is NOT re-run here (`mizan/cli/main.py`'s centralized `check_all()`, unmodified,
    already runs before ANY subcommand — including `backtest` — dispatches, and
    `mizan.config.invariants.INVARIANTS` is a frozen singleton that cannot change value between
    that check and this call within one process).

    Builds `generate_rebalance_dates(start_date, end_date)`, then iterates every trading day
    present in `price_bars` for `tickers`, from `start_date` to `end_date` inclusive, in order. On
    every day: applies `step()` (split adjustment), credits any dividends via `credit_dividend`
    for tickers with a nonzero `price_bars.div_cash` that day (recording a `DividendEvent` per
    credit, stamped with the most-recently-established verdict for that ticker), and appends one
    `DailySnapshot`. On a day that is ALSO a rebalance date: calls `rebalance()` instead of the
    plain no-trade path, threading its updated portfolio/compliance-state/divestment-event outputs
    forward.

    Returns `ResultEnvelope(active_caveats=(Caveat.LOOK_AHEAD_BIAS, Caveat.SURVIVORSHIP_BIAS,
    Caveat.PENDING_SCHOLARLY_VERIFICATION), payload=BacktestResult(...).model_dump())`.
    """
    rebalance_dates = generate_rebalance_dates(start_date, end_date)
    rebalance_date_set = frozenset(rebalance_dates)
    trading_dates = _resolve_trading_dates(con, tickers, start_date, end_date)

    portfolio = Portfolio(cash=initial_cash, holdings={})
    compliance_states: dict[str, ComplianceStateRecord] = {}
    snapshots: list[DailySnapshot] = []
    divestment_events: list[DivestmentEvent] = []
    dividend_events: list[DividendEvent] = []

    for as_of_date in trading_dates:
        prices, splits, divs = _resolve_day_rows(con, tickers, as_of_date)

        portfolio = step(portfolio, prices, splits)

        for ticker in sorted(divs):
            div_cash_per_share = divs[ticker]
            if ticker in portfolio.holdings:
                quantity_held = portfolio.holdings[ticker].quantity
                portfolio = credit_dividend(portfolio, ticker, div_cash_per_share)
                record = compliance_states.get(ticker)
                if record is None or not record.verdict_history:
                    raise AssertionError(
                        f"{ticker}: a currently-held ticker paying a dividend must already have a "
                        "ComplianceStateRecord with at least one VerdictObservation"
                    )
                dividend_events.append(
                    DividendEvent(
                        ticker=ticker,
                        cik=record.cik,
                        ex_date=as_of_date,
                        div_cash_per_share=div_cash_per_share,
                        quantity_held=quantity_held,
                        cash_received=div_cash_per_share * quantity_held,
                        verdict_at_ex_date=record.verdict_history[-1].verdict,
                    )
                )

        if as_of_date in rebalance_date_set:
            portfolio, compliance_states, new_divestments = rebalance(
                portfolio,
                as_of_date,
                universe=tickers,
                strategy=strategy,
                compliance_states=compliance_states,
                con=con,
                cache_dir=cache_dir,
                overrides=overrides,
                fiqh_params=fiqh_params,
            )
            divestment_events.extend(new_divestments)

        snapshots.append(
            DailySnapshot(
                as_of_date=as_of_date,
                cash=portfolio.cash,
                holdings={t: h.quantity for t, h in portfolio.holdings.items()},
                portfolio_value=mark_to_market(portfolio, prices),
            )
        )

    result = BacktestResult(
        daily_snapshots=tuple(snapshots),
        divestment_events=tuple(divestment_events),
        dividend_events=tuple(dividend_events),
        compliance_states=compliance_states,
    )
    return ResultEnvelope(
        active_caveats=(
            Caveat.LOOK_AHEAD_BIAS,
            Caveat.SURVIVORSHIP_BIAS,
            Caveat.PENDING_SCHOLARLY_VERIFICATION,
        ),
        payload=result.model_dump(),
    )
