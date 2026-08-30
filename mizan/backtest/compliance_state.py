"""mizan/backtest/compliance_state.py — the flip -> grace -> divest state machine and its event
models.

Implements PHASE_5_SPEC.md §3.3, §4.4, §6c.

`MASTER_PRD.md` §7.3's own state-machine diagram, transcribed:

    HELD(compliant)
       |  quarterly rebalance re-screens holding as-of date
       v
    flip detected? --no--> stay HELD(compliant)
       |yes
       v
    HELD(non-compliant, grace)  --forced-divestment scheduled at next rebalance-->
       v
    DIVEST  -->purify gains attributable to the non-compliant holding window (Fork C)

The diagram draws no "un-flip" edge back from `HELD(non-compliant, grace)` to `HELD(compliant)` —
`transition` below implements that absence structurally: once `HELD_NONCOMPLIANT_GRACE` fires, the
grace countdown runs to completion regardless of a later, incidental return to compliance.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.base import MizanBaseModel
from mizan.core.verdict import (
    Verdict,
)  # imported by full path, mirrors mizan/screening/verdict.py's

# own convention (PHASE_4_SPEC.md §0) — a grep for "Verdict" in this module unambiguously means "the
# enum"


class HoldingComplianceState(StrEnum):
    """`MASTER_PRD.md` §7.3's state-machine diagram, transcribed as an enum. A newly-selected
    holding always starts `HELD_COMPLIANT` — the strategy interface (`mizan.backtest.strategy`)
    makes it structurally impossible for a holding to ever be FIRST established while
    `NON_COMPLIANT`."""

    HELD_COMPLIANT = "held_compliant"
    HELD_NONCOMPLIANT_GRACE = "held_noncompliant_grace"
    DIVESTED = "divested"


class VerdictObservation(MizanBaseModel):
    """One rebalance's re-screen result for one holding — the "verdict history" the outer dispatch
    asks Phase 5 to record for Phase 6's future purification-attribution use (`MASTER_PRD.md` §8:
    "the ratio comes from that holding's most-recent screen")."""

    as_of_date: date
    verdict: Verdict


class ComplianceStateRecord(MizanBaseModel):
    """The full compliance-tracking record for one ticker across the life of a backtest. One
    record per ticker ever held; `state`/`flip_date`/`divest_date`/`grace_rebalances_remaining`
    describe ONLY the state machine (`MASTER_PRD.md` §7.3); `verdict_history` is the append-only
    audit trail — every rebalance's `screen()` result for this ticker, in order, for as long as it
    is held.
    """

    ticker: str
    cik: str
    state: HoldingComplianceState
    flip_date: date | None
    """Set the rebalance a HELD_COMPLIANT -> HELD_NONCOMPLIANT_GRACE transition first fires for
    this ticker. Never cleared or overwritten once set — a ticker flips at most once per backtest
    (the state machine has no HELD_NONCOMPLIANT_GRACE -> HELD_COMPLIANT edge, per MASTER_PRD.md
    §7.3's own diagram, which draws no "un-flip" branch)."""
    divest_date: date | None
    """Set the rebalance a HELD_NONCOMPLIANT_GRACE -> DIVESTED transition fires. `flip_date` and
    `divest_date`, together, are MASTER_PRD.md §8 Fork C's "time-bounded flip-date to
    divestment-date" window — the exact pair Phase 6's forced-divestment purification attribution
    will read, unchanged from how this record leaves them."""
    grace_rebalances_remaining: int | None
    """`None` outside HELD_NONCOMPLIANT_GRACE. Set to `fiqh_params.grace_period_rebalances.value`
    (read fresh at the flip) the rebalance the flip fires, and decremented by exactly 1 at every
    SUBSEQUENT rebalance until it reaches 0, at which point DIVESTED fires."""
    verdict_history: tuple[VerdictObservation, ...]


class DivestmentEvent(MizanBaseModel):
    """One completed forced-divestment, as a standalone record — the minimum Phase 6 needs without
    having to re-derive it from a full `ComplianceStateRecord` (`MASTER_PRD.md` §8 Fork C)."""

    ticker: str
    cik: str
    flip_date: date
    divest_date: date


class DividendEvent(MizanBaseModel):
    """One dividend cash credit received while a ticker was held — Phase 6's other required input
    (`MASTER_PRD.md` §8: "the dividend cash comes from Tiingo's per-day divCash field" and "the
    ratio comes from that holding's most-recent screen"). `verdict_at_ex_date` is the MOST RECENT
    REBALANCE's verdict for this ticker as of `ex_date` — screening only happens at rebalances, so
    a dividend paid between rebalances is attributed to whichever verdict was most recently
    established, exactly matching MASTER_PRD.md §8's own wording.
    """

    ticker: str
    cik: str
    ex_date: date
    div_cash_per_share: float
    quantity_held: float
    cash_received: float
    verdict_at_ex_date: Verdict


def transition(
    record: ComplianceStateRecord | None,
    *,
    ticker: str,
    cik: str,
    as_of_date: date,
    new_verdict: Verdict,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> tuple[ComplianceStateRecord, DivestmentEvent | None]:
    """Pure function — no DB, no cache, no network (§7 guard G-B5, mirroring Phase 4's own
    `classify_business_activity` purity). `record=None` means this is the FIRST rebalance this
    ticker has ever been screened as a holding: initializes a new `HELD_COMPLIANT` record
    (asserting `new_verdict != Verdict.NON_COMPLIANT` — a newly-selected holding can never itself
    be `NON_COMPLIANT`, by the strategy interface's own structural guarantee; a violation here
    indicates a `StrategyContractViolationError`-class bug upstream, not a normal state to handle
    gracefully).

    Transition table (§6c), read from `record.state`:
      * `HELD_COMPLIANT`, `new_verdict` in `{PURE, MIXED}`: stays `HELD_COMPLIANT`; append a
        `VerdictObservation` to `verdict_history`; no other field changes.
      * `HELD_COMPLIANT`, `new_verdict == NON_COMPLIANT`: **flip detected.** Transitions to
        `HELD_NONCOMPLIANT_GRACE`, `flip_date=as_of_date`, `grace_rebalances_remaining=
        fiqh_params.grace_period_rebalances.value` (read fresh from `fiqh_params` on every call,
        never hardcoded — §7 guard G-B4).
      * `HELD_NONCOMPLIANT_GRACE`, any `new_verdict`: decrements `grace_rebalances_remaining` by
        exactly 1 (append the `VerdictObservation` regardless of what `new_verdict` says — the grace
        countdown, once started, runs to completion irrespective of a later, incidental return to
        compliance; `MASTER_PRD.md` §7.3's own diagram draws no un-flip edge, and this is where that
        absence is implemented, not merely documented). If the decremented value reaches `0`:
        transitions to `DIVESTED`, `divest_date=as_of_date`, `grace_rebalances_remaining=None`, and
        returns a populated `DivestmentEvent` as the second tuple element. Otherwise stays
        `HELD_NONCOMPLIANT_GRACE`.
      * `DIVESTED`: **must never be called again for this ticker.** `mizan.backtest.clock.rebalance`
        never re-screens a ticker once it force-liquidates it this same rebalance, so this branch is
        asserted unreachable (`AssertionError`, not a silently-tolerated no-op) rather than handled.

    Returns `(updated_record, divestment_event_or_none)` — the caller (`mizan.backtest.clock.
    rebalance`) is responsible for actually liquidating the position in the SAME rebalance a
    `DivestmentEvent` is returned; this function only updates bookkeeping, it never touches a
    `Portfolio`.
    """
    observation = VerdictObservation(as_of_date=as_of_date, verdict=new_verdict)

    if record is None:
        if new_verdict is Verdict.NON_COMPLIANT:
            raise AssertionError(
                f"{ticker}: a holding may never be FIRST established while NON_COMPLIANT — this "
                "indicates a StrategyContractViolationError-class bug upstream"
            )
        new_record = ComplianceStateRecord(
            ticker=ticker,
            cik=cik,
            state=HoldingComplianceState.HELD_COMPLIANT,
            flip_date=None,
            divest_date=None,
            grace_rebalances_remaining=None,
            verdict_history=(observation,),
        )
        return new_record, None

    if record.state is HoldingComplianceState.HELD_COMPLIANT:
        verdict_history = (*record.verdict_history, observation)
        if new_verdict is Verdict.NON_COMPLIANT:
            flipped_record = record.model_copy(
                update={
                    "state": HoldingComplianceState.HELD_NONCOMPLIANT_GRACE,
                    "flip_date": as_of_date,
                    "grace_rebalances_remaining": fiqh_params.grace_period_rebalances.value,
                    "verdict_history": verdict_history,
                }
            )
            return flipped_record, None
        stayed_record = record.model_copy(update={"verdict_history": verdict_history})
        return stayed_record, None

    if record.state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE:
        if record.grace_rebalances_remaining is None:
            raise AssertionError(
                f"{ticker}: HELD_NONCOMPLIANT_GRACE record must carry a non-None "
                "grace_rebalances_remaining"
            )
        if record.flip_date is None:
            raise AssertionError(
                f"{ticker}: HELD_NONCOMPLIANT_GRACE record must carry a non-None flip_date"
            )
        verdict_history = (*record.verdict_history, observation)
        remaining = record.grace_rebalances_remaining - 1
        if remaining <= 0:
            divested_record = record.model_copy(
                update={
                    "state": HoldingComplianceState.DIVESTED,
                    "divest_date": as_of_date,
                    "grace_rebalances_remaining": None,
                    "verdict_history": verdict_history,
                }
            )
            divestment_event = DivestmentEvent(
                ticker=ticker, cik=cik, flip_date=record.flip_date, divest_date=as_of_date
            )
            return divested_record, divestment_event
        still_grace_record = record.model_copy(
            update={"grace_rebalances_remaining": remaining, "verdict_history": verdict_history}
        )
        return still_grace_record, None

    raise AssertionError(f"{ticker}: transition() must never be called again for a DIVESTED ticker")
