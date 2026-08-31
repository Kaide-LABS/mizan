"""mizan/purification/ledger.py — Fork A trigger + Fork B side-ledger accrual.

Implements PHASE_6_SPEC.md §3.1, §3.2, §4.1, §6a, §6c, §6d.

`purify_backtest_result` is THE canonical Phase 6 entry point (this phase's analogue of `screen()`/
`run_backtest()`). Neither this module nor `mizan/purification/attribution.py` opens its own DuckDB
connection, writes to DuckDB, or mutates a `BacktestResult`/`ComplianceStateRecord`/`DailySnapshot`
in place (§5, §6d, §7 guards G-P3/G-P5/G-DB6) — every value from an earlier phase is read-only input
here.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import Field

from mizan.backtest.compliance_state import ComplianceStateRecord, DividendEvent
from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.base import MizanBaseModel
from mizan.core.verdict import Verdict
from mizan.purification.attribution import (
    DivestmentPurificationEntry,
    compute_divestment_attribution,
)
from mizan.screening.verdict import ScreeningVerdict, ScreenName, screen

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

    from mizan.backtest.clock import BacktestResult, DailySnapshot
    from mizan.screening.business_activity import BusinessActivityOverrideMap


class DividendPurificationEntry(MizanBaseModel):
    """One Fork-A purification event: `non_compliant_income_ratio x dividend_amount` for one
    dividend paid by a Mixed holding (`MASTER_PRD.md` §8's own trigger wording). Produced only
    for a dividend whose PINNED verdict (§6a) is `Verdict.MIXED` — never for a Pure-verdict
    dividend (ratio is definitionally 0, so no entry is produced at all, not a zero-amount one,
    §6a) — and, for a dividend pinned to a Non-compliant grace-window verdict, using §6a's
    documented last-Mixed-ratio fallback, never the Non-compliant verdict's own (frequently
    absent, §6a) ratio.
    """

    ticker: str
    cik: str
    ex_date: date
    """`DividendEvent.ex_date` this entry purifies — 1:1, never aggregated across dividends."""
    ratio_used: float = Field(ge=0.0)
    """`non_permissible_income_ratio.actual_value` from the re-derived
    `ScreeningVerdict.reason_trace` at `ratio_as_of_date` (§6a) — never the ratio active at any
    OTHER date, including the backtest's own most-recent rebalance if that differs from the
    verdict active at `ex_date`."""
    ratio_as_of_date: date
    """The rebalance date the pinned `VerdictObservation` was recorded at — the auditable proof
    this is a date-indexed lookup, not a "most recent screen" shortcut (`ULTIMATE_PRD.md` §4.7's
    own named failure mode, guard G-P1, §7). Always `<= ex_date`."""
    dividend_cash_received: float = Field(ge=0.0)
    """`DividendEvent.cash_received` this entry purifies, copied verbatim (never re-derived) so a
    reconciliation pass (§8) can sum this field across every entry and compare against
    `BacktestResult.dividend_events`' own total without re-computing anything."""
    purified_amount: float = Field(ge=0.0)
    """`ratio_used * dividend_cash_received`, exactly."""


class PurificationLedger(MizanBaseModel):
    """The full Phase 6 result: every Fork-A dividend entry, every Fork-C divestment entry (§3.3,
    `mizan/purification/attribution.py`), the Fork-B running liability, and the two Fork-B return
    figures (`MASTER_PRD.md` §8: "report two numbers... so the drag is its own visible figure, not a
    silent NAV distortion"). This is the concrete type `BacktestResult.purification_ledger`'s dict
    placeholder is populated FROM (§3.1) — never the field's own declared type.
    """

    dividend_entries: tuple[DividendPurificationEntry, ...]
    divestment_entries: tuple[DivestmentPurificationEntry, ...]
    """`DivestmentPurificationEntry` is defined in `mizan/purification/attribution.py` (§3.3) and
    imported directly into `ledger.py` (`attribution.py` has no reverse dependency on
    `ledger.py`, so this is a plain one-way import, not a circular one requiring string
    forward-references or `model_rebuild()`). Empty `()` whenever
    `fiqh_params.purify_capital_gains.value` is `False` (the V1 default, §6c) — never populated
    with zero-amount placeholder entries in that case, distinct from an individual divestment's
    own zero-appreciation entry when the gate IS open (§6b)."""
    purification_liability: float = Field(ge=0.0)
    """`sum(e.purified_amount for e in dividend_entries) + sum(e.purified_amount for e in
    divestment_entries)` — the Fork-B "running purification_liability", exactly. A single, final
    aggregate for V1; a day-by-day running series, if ever wanted, is trivially reconstructible by a
    later phase from each entry's own date field and is a Phase-7 reporting concern, not something
    this phase materializes as a second parallel time series alongside `BacktestResult.
    daily_snapshots` (§6d)."""
    gross_return: float
    """`(daily_snapshots[-1].portfolio_value - daily_snapshots[0].portfolio_value) /
    daily_snapshots[0].portfolio_value` — a plain point-to-point total return over the backtest
    window, computed directly from Phase 5's own `daily_snapshots` series, untouched by
    purification (§6d). Deliberately NOT annualized, risk-adjusted, or time-weighted —
    `MASTER_PRD.md` §8 Fork B's literal requirement is "report two numbers... so the drag is its
    own visible figure", which this satisfies without anticipating Phase 7's own, richer return
    methodology; Phase 7's
    reporter is free to compute additional return figures FROM `daily_snapshots` and
    `purification_liability` directly, and does not need this field to be the final word on return
    methodology (§6d)."""
    net_of_purification_return: float
    """`(daily_snapshots[-1].portfolio_value - purification_liability -
    daily_snapshots[0].portfolio_value) / daily_snapshots[0].portfolio_value` — computed ONLY
    here, at this ledger's own top level, as a reporting-level subtraction. This is the ONLY
    place in Phase 6's own code `purification_liability` is subtracted from anything —
    `daily_snapshots`, `Portfolio.cash`, and every other Phase-5-owned value are read but never
    written by this phase
    (`ULTIMATE_PRD.md` §4.7's "purification silently netted into NAV" failure mode, guard G-P3, §7).
    `gross_return` and `net_of_purification_return` are always both present and are equal to each
    other iff `purification_liability == 0.0` exactly (an empty ledger) — never silently equal
    otherwise (§8 AC)."""


def _pinned_verdict_observation(
    compliance_state: ComplianceStateRecord, ex_date: date
) -> tuple[date, Verdict] | None:
    """Find the `VerdictObservation` in `compliance_state.verdict_history` with the LARGEST
    `as_of_date <= ex_date` — the rebalance whose screen was "active" at the dividend's date (§6a).
    Returns `None` if no observation qualifies (should not occur for a ticker that actually paid a
    dividend while held, since it must have been screened at least once before `ex_date` to have
    ever been selected — defensive completeness only).
    """
    candidates = [obs for obs in compliance_state.verdict_history if obs.as_of_date <= ex_date]
    if not candidates:
        return None
    latest = max(candidates, key=lambda obs: obs.as_of_date)
    return latest.as_of_date, latest.verdict


def _most_recent_prior_mixed_observation(
    compliance_state: ComplianceStateRecord, before: date
) -> date | None:
    """Walk `verdict_history` backwards from (but not including) `before` and return the
    `as_of_date` of the most recent STRICTLY PRIOR `Verdict.MIXED` observation (§6a's grace-window
    fallback, §7 guard G-P6). Returns `None` if no such observation exists (the most recent prior
    observation was `Verdict.PURE`, or there is no prior observation at all)."""
    candidates = [
        obs
        for obs in compliance_state.verdict_history
        if obs.as_of_date < before and obs.verdict is Verdict.MIXED
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda obs: obs.as_of_date).as_of_date


def _ratio_from_screen(
    ticker: str,
    cik: str,
    ratio_as_of_date: date,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None,
    fiqh_params: FiqhParams,
) -> float:
    """Re-invoke `mizan.screening.verdict.screen` at `ratio_as_of_date` (§6a) and read
    `non_permissible_income_ratio.actual_value` off the returned `ScreeningVerdict.reason_trace`.
    """
    envelope = screen(
        ticker,
        ratio_as_of_date,
        con=con,
        cache_dir=cache_dir,
        overrides=overrides,
        fiqh_params=fiqh_params,
    )
    verdict = ScreeningVerdict.model_validate(envelope.payload)
    for entry in verdict.reason_trace:
        if entry.screen is ScreenName.NON_PERMISSIBLE_INCOME_RATIO:
            if entry.actual_value is None:
                raise AssertionError(
                    f"{ticker} (CIK {cik}): non_permissible_income_ratio reason-trace entry at "
                    f"{ratio_as_of_date} carries no actual_value"
                )
            return entry.actual_value
    raise AssertionError(
        f"{ticker} (CIK {cik}): re-derived ScreeningVerdict at {ratio_as_of_date} carries no "
        "non_permissible_income_ratio reason-trace entry — expected for a re-screen of a ticker "
        "already known to have passed Layer 1"
    )


def purify_dividend(
    dividend_event: DividendEvent,
    compliance_state: ComplianceStateRecord,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> DividendPurificationEntry | None:
    """Fork A for one `DividendEvent`. Looks up the `VerdictObservation` in `compliance_state.
    verdict_history` most recently established as of `dividend_event.ex_date`
    (`ratio_as_of_date`, §6a) — asserting its `.verdict` equals `dividend_event.verdict_at_ex_date`,
    since Phase 5 already
    computed and stamped that value from this exact lookup (`mizan/backtest/clock.py`'s own
    `run_backtest` loop body) and a mismatch here would mean Phase 6 mis-derived the pin, not that
    Phase 5 was wrong.

    * Pinned verdict is `Verdict.PURE`: returns `None` — no entry (§3.2, ratio is definitionally 0).
    * Pinned verdict is `Verdict.MIXED`: re-invokes `mizan.screening.verdict.screen(dividend_event.
      ticker, ratio_as_of_date, con=con, cache_dir=cache_dir, overrides=overrides,
      fiqh_params=fiqh_params)` (§6a — the SAME `con`/`cache_dir`/`overrides`/`fiqh_params` the
      caller's own backtest run used, never a freshly-loaded or different config, guard G-P7 §7),
      reads `non_permissible_income_ratio.actual_value` off the returned `ScreeningVerdict.
      reason_trace`, and returns a `DividendPurificationEntry` with `purified_amount = ratio_used *
      dividend_event.cash_received`.
    * Pinned verdict is `Verdict.NON_COMPLIANT` (the dividend was received during the grace
      window, between `flip_date` and `divest_date`, before forced-divestment fired): §6a's
      named, explicitly-flagged V1 default: walk `compliance_state.verdict_history` backwards
      from the flip to the
      most recent STRICTLY PRIOR `Verdict.MIXED` observation and re-derive ITS ratio via `screen()`
      at ITS OWN `as_of_date` (never the flip's own date, never zero by default, never the
      Non-compliant verdict's own absent ratio). If the most recent prior observation was `Verdict.
      PURE` instead, returns `None` (the Pure case above, unchanged).
    """
    pinned = _pinned_verdict_observation(compliance_state, dividend_event.ex_date)
    if pinned is None:
        raise AssertionError(
            f"{dividend_event.ticker}: no VerdictObservation with as_of_date <= "
            f"{dividend_event.ex_date} — a ticker paying a dividend while held must have been "
            "screened at least once before its ex_date"
        )
    ratio_as_of_date, pinned_verdict = pinned
    if pinned_verdict is not dividend_event.verdict_at_ex_date:
        raise AssertionError(
            f"{dividend_event.ticker}: re-derived pinned verdict {pinned_verdict!r} at "
            f"{ratio_as_of_date} does not match DividendEvent.verdict_at_ex_date "
            f"{dividend_event.verdict_at_ex_date!r} — Phase 6 mis-derived the pin"
        )

    if pinned_verdict is Verdict.PURE:
        return None

    if pinned_verdict is Verdict.MIXED:
        ratio_used = _ratio_from_screen(
            dividend_event.ticker,
            dividend_event.cik,
            ratio_as_of_date,
            con=con,
            cache_dir=cache_dir,
            overrides=overrides,
            fiqh_params=fiqh_params,
        )
        return DividendPurificationEntry(
            ticker=dividend_event.ticker,
            cik=dividend_event.cik,
            ex_date=dividend_event.ex_date,
            ratio_used=ratio_used,
            ratio_as_of_date=ratio_as_of_date,
            dividend_cash_received=dividend_event.cash_received,
            purified_amount=ratio_used * dividend_event.cash_received,
        )

    # pinned_verdict is Verdict.NON_COMPLIANT — the grace-window edge case (§6a, §7 guard G-P6).
    fallback_as_of_date = _most_recent_prior_mixed_observation(
        compliance_state, dividend_event.ex_date
    )
    if fallback_as_of_date is None:
        return None
    ratio_used = _ratio_from_screen(
        dividend_event.ticker,
        dividend_event.cik,
        fallback_as_of_date,
        con=con,
        cache_dir=cache_dir,
        overrides=overrides,
        fiqh_params=fiqh_params,
    )
    return DividendPurificationEntry(
        ticker=dividend_event.ticker,
        cik=dividend_event.cik,
        ex_date=dividend_event.ex_date,
        ratio_used=ratio_used,
        ratio_as_of_date=fallback_as_of_date,
        dividend_cash_received=dividend_event.cash_received,
        purified_amount=ratio_used * dividend_event.cash_received,
    )


def _compute_returns(
    daily_snapshots: tuple[DailySnapshot, ...], purification_liability: float
) -> tuple[float, float]:
    """`(gross_return, net_of_purification_return)` from `daily_snapshots` (§3.2, §6d). An empty
    `daily_snapshots` (no trading days resolved at all — an edge case Phase 5's own `run_backtest`
    does not rule out, e.g. a `start_date`/`end_date` window with zero `price_bars` rows) has no
    point-to-point window to compute a return over; since an empty snapshot series also implies zero
    dividend/divestment events (both are only ever recorded inside the same per-trading-day loop
    that appends a snapshot, `mizan/backtest/clock.py`'s own `run_backtest` body), and hence
    `purification_liability == 0.0`, both figures are `0.0` in that case — consistent with, not an
    exception to, "the two values are equal iff the ledger is empty" (§8 AC5).
    """
    if not daily_snapshots:
        return 0.0, 0.0
    start_value = daily_snapshots[0].portfolio_value
    end_value = daily_snapshots[-1].portfolio_value
    gross_return = (end_value - start_value) / start_value
    net_of_purification_return = (end_value - purification_liability - start_value) / start_value
    return gross_return, net_of_purification_return


def purify_backtest_result(
    result: BacktestResult,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None = None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> BacktestResult:
    """THE canonical, singular Phase 6 entry point — this phase's analogue of `screen()`/
    `run_backtest()`. Takes an already-completed `BacktestResult` (Phase 5's own scoped type,
    `purification_ledger is None`) and returns a NEW `BacktestResult` (§3's own frozen-model
    discipline — never mutates `result` in place) with `purification_ledger` populated.

    Calls `purify_dividend` (above) once per `result.dividend_events` entry, skipping `None`s;
    calls `mizan.purification.attribution.compute_divestment_attribution` (§4.2) once per
    `result.divestment_events` entry IFF `fiqh_params.purify_capital_gains.value` is `True` (§6c) —
    `divestment_entries` is `()` entirely when the gate is closed, never populated with skipped/
    zero-amount placeholders. Sums both entry sets into `purification_liability`, computes
    `gross_return`/`net_of_purification_return` from `result.daily_snapshots` (§3.2), constructs one
    `PurificationLedger`, and returns `result.model_copy(update={"purification_ledger": ledger.
    model_dump()})` (§3.1).

    Raises nothing this function's own body doesn't already document — every exception `screen()`
    can raise (`CikResolutionError`, `SicResolutionError`, `NotNormalizedError`,
    `InsufficientDataError`) can, in principle, propagate from a re-invoked `screen()` call, exactly
    the same halting posture `mizan/cli/backtest.py`'s own `run()` already gives `run_backtest()`
    (§4.3) — a ticker `screen()`-able once during the original backtest is `screen()`-able again
    here against the SAME, unchanged `con`/`cache_dir` (§6a's own determinism argument), so this
    is a defensive re-statement of an already-proven-reachable code path, not a new failure surface.
    """
    dividend_entries: list[DividendPurificationEntry] = []
    for dividend_event in result.dividend_events:
        compliance_state = result.compliance_states.get(dividend_event.ticker)
        if compliance_state is None:
            raise AssertionError(
                f"{dividend_event.ticker}: no ComplianceStateRecord in result.compliance_states "
                "for a ticker that paid a dividend"
            )
        entry = purify_dividend(
            dividend_event,
            compliance_state,
            con=con,
            cache_dir=cache_dir,
            overrides=overrides,
            fiqh_params=fiqh_params,
        )
        if entry is not None:
            dividend_entries.append(entry)

    divestment_entries: list[DivestmentPurificationEntry] = []
    if fiqh_params.purify_capital_gains.value:
        for divestment_event in result.divestment_events:
            divestment_entries.append(
                compute_divestment_attribution(
                    divestment_event,
                    result.compliance_states,
                    result.daily_snapshots,
                    con=con,
                    fiqh_params=fiqh_params,
                )
            )

    purification_liability = sum(e.purified_amount for e in dividend_entries) + sum(
        e.purified_amount for e in divestment_entries
    )
    gross_return, net_of_purification_return = _compute_returns(
        result.daily_snapshots, purification_liability
    )

    ledger = PurificationLedger(
        dividend_entries=tuple(dividend_entries),
        divestment_entries=tuple(divestment_entries),
        purification_liability=purification_liability,
        gross_return=gross_return,
        net_of_purification_return=net_of_purification_return,
    )
    return result.model_copy(update={"purification_ledger": ledger.model_dump()})
