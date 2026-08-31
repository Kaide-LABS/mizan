"""mizan/purification/attribution.py — Fork C: forced-divestment price-appreciation attribution.

Implements PHASE_6_SPEC.md §3.3, §4.2, §6b, §6c.

Gated entirely by `fiqh_params.purify_capital_gains.value` at the `ledger.py` call site (§6c) —
this module's own `compute_divestment_attribution` has no gate of its own; it is only ever invoked
once the gate is already confirmed open. `mizan/purification/` never opens its own DuckDB
connection and never writes to it (§5, §7 guard G-DB6/G-P5) — every query here is a read-only
`SELECT raw_close FROM price_bars ...` against the caller-supplied, already-open `con`.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.base import MizanBaseModel

if TYPE_CHECKING:
    import duckdb

    from mizan.backtest.clock import DailySnapshot
    from mizan.backtest.compliance_state import ComplianceStateRecord, DivestmentEvent


class DivestmentPurificationEntry(MizanBaseModel):
    """One Fork-C purification event: the price appreciation of a forced-divested holding over its
    exact non-compliant window (`MASTER_PRD.md` §8 Fork C, `flip_date` -> `divest_date`,
    time-bounded). Produced for EVERY `DivestmentEvent` in `BacktestResult.divestment_events` when
    `fiqh_params.purify_capital_gains.value` is `True` (§6c) — including a `purified_amount == 0.0`
    entry when the window's price appreciation is zero or negative (§6b) — never omitted the way a
    Pure-verdict dividend's non-entry is (§3.2): a `DivestmentEvent` is a concrete, already-happened
    event, and recording "the window was checked, nothing to purify" is the auditable choice, not an
    ambiguous absence.
    """

    ticker: str
    cik: str
    flip_date: date
    """Copied verbatim from `DivestmentEvent.flip_date` / `ComplianceStateRecord.flip_date` —
    never re-derived independently (`ULTIMATE_PRD.md` §4.7's 2nd named failure mode, guard
    G-P2, §7)."""
    divest_date: date
    """Copied verbatim from `DivestmentEvent.divest_date` / `ComplianceStateRecord.divest_date`,
    same non-re-derivation guarantee as `flip_date`."""
    quantity_liquidated: float = Field(ge=0.0)
    """The holding's quantity at the moment of forced liquidation, read from `BacktestResult.
    daily_snapshots` at `as_of_date == flip_date` (§6b) — never re-queried from `Portfolio` (Phase 6
    never holds a live `Portfolio` reference; it only ever reads a completed `BacktestResult`)."""
    price_at_flip: float = Field(ge=0.0)
    """`price_bars.raw_close` for `ticker` on `flip_date`, per §6a's raw-close-governs-valuation
    precedent (`PHASE_5_SPEC.md` §6a) — never `adj_close`."""
    price_at_divest: float = Field(ge=0.0)
    """`price_bars.raw_close` for `ticker` on `divest_date`, same precedent."""
    purified_amount: float = Field(ge=0.0)
    """`max(0.0, quantity_liquidated * (price_at_divest - price_at_flip))` — floored at zero
    because a price DECLINE during the non-compliant window produces no gain to purify; AAOIFI's
    purification concept removes impermissible INCOME, and there is no income, let alone
    non-halal income, in a loss (§6b's own worked reasoning, a named judgment call, not silently
    assumed)."""

    @model_validator(mode="after")
    def _flip_before_or_equal_divest(self) -> DivestmentPurificationEntry:
        """`ULTIMATE_PRD.md` §4.7's own guard, restated at the type level: `flip_date <=
        divest_date` is asserted here, not merely hoped for by the function that constructs
        this entry."""
        if self.flip_date > self.divest_date:
            raise ValueError(
                f"{self.ticker}: flip_date {self.flip_date} must be <= divest_date "
                f"{self.divest_date}"
            )
        return self


def _raw_close_on(con: duckdb.DuckDBPyConnection, ticker: str, as_of_date: date) -> float:
    """One read-only `SELECT raw_close FROM price_bars WHERE ticker = ? AND trade_date = ?` —
    `InsufficientDataError`-class failures are not expected here: `ticker` and `as_of_date` are
    always a `flip_date`/`divest_date` pair Phase 5 itself already priced (a divestment can only
    fire at a rebalance date the backtest already resolved `price_bars` rows for), so a missing row
    indicates a genuine data-integrity bug upstream rather than a normal, tolerable gap — raised as
    a plain `LookupError`, not silently defaulted to `0.0`.
    """
    row = con.execute(
        "SELECT raw_close FROM price_bars WHERE ticker = ? AND trade_date = ?",
        [ticker, as_of_date],
    ).fetchone()
    if row is None:
        raise LookupError(f"{ticker}: no price_bars row for trade_date {as_of_date}")
    return float(row[0])


def compute_divestment_attribution(
    event: DivestmentEvent,
    compliance_states: dict[str, ComplianceStateRecord],
    daily_snapshots: tuple[DailySnapshot, ...],
    *,
    con: duckdb.DuckDBPyConnection,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> DivestmentPurificationEntry:
    """Fork C for one `DivestmentEvent`. Asserts `compliance_states[event.ticker].flip_date ==
    event.flip_date and .divest_date == event.divest_date` (`AssertionError` otherwise — guard G-P2,
    §7: both dates must come from the SAME `compliance_state.py`-owned event log, never re-derived
    independently). Finds the `DailySnapshot` in `daily_snapshots` with `as_of_date ==
    event.flip_date` and reads `holdings[event.ticker]` as `quantity_liquidated` (§6b — the
    frozen-grace-holding property `mizan/backtest/clock.py`'s own docstring establishes means this
    quantity is unchanged all the way through to `event.divest_date`, so the flip-date snapshot is
    the correct, and only, read site). Queries `price_bars.raw_close` for `event.ticker` at
    `event.flip_date` and `event.divest_date` (read-only), and reads
    `fiqh_params.divestment_attribution_method.value` — currently only
    `DivestmentAttributionMethod.TIME_BOUNDED_PRICE_APPRECIATION` is defined (`mizan/config/
    fiqh_params.py` register #10) — and computes `purified_amount = max(0.0, quantity_liquidated *
    (price_at_divest - price_at_flip))` (§6b). Returns one `DivestmentPurificationEntry`; its own
    `model_validator` (§3.3) re-asserts `flip_date <= divest_date` at construction, a second,
    type-level instance of the same guard.
    """
    record = compliance_states.get(event.ticker)
    if (
        record is None
        or record.flip_date != event.flip_date
        or record.divest_date != event.divest_date
    ):
        raise AssertionError(
            f"{event.ticker}: compliance_states flip_date/divest_date does not match the "
            f"DivestmentEvent's own dates (event flip_date={event.flip_date} "
            f"divest_date={event.divest_date}; compliance_states record="
            f"{record!r}) — both must come from the same compliance_state.py-owned event log"
        )

    flip_snapshot = next(
        (snapshot for snapshot in daily_snapshots if snapshot.as_of_date == event.flip_date), None
    )
    if flip_snapshot is None:
        raise LookupError(
            f"{event.ticker}: no DailySnapshot with as_of_date == flip_date {event.flip_date}"
        )
    quantity_liquidated = flip_snapshot.holdings.get(event.ticker, 0.0)

    # Register #10 currently has exactly one defined member — read fresh from `fiqh_params` on
    # every call (§7 guard G-P4's own posture), never a module-level cached constant, even though
    # there is only one branch to dispatch to (§9's own restated non-goal: no dispatch table
    # anticipating a member that does not exist).
    _ = fiqh_params.divestment_attribution_method.value

    price_at_flip = _raw_close_on(con, event.ticker, event.flip_date)
    price_at_divest = _raw_close_on(con, event.ticker, event.divest_date)
    purified_amount = max(0.0, quantity_liquidated * (price_at_divest - price_at_flip))

    return DivestmentPurificationEntry(
        ticker=event.ticker,
        cik=event.cik,
        flip_date=event.flip_date,
        divest_date=event.divest_date,
        quantity_liquidated=quantity_liquidated,
        price_at_flip=price_at_flip,
        price_at_divest=price_at_divest,
        purified_amount=purified_amount,
    )
