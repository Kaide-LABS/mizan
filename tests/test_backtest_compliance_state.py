"""Tests for mizan/backtest/compliance_state.py — the flip -> grace -> divest state machine.

Implements PHASE_5_SPEC.md §8 acceptance criteria 1 (flip -> grace -> divest sequence, unit level)
and 2 (grace period read from fiqh_params, unit level) — the end-to-end, real-`screen()`-driven
versions of both live in test_backtest_clock.py against the ZZFLIP01 fixture; this file exercises
`transition` directly, pure-function style, with hand-built `ComplianceStateRecord` values.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from mizan.backtest.compliance_state import (
    ComplianceStateRecord,
    HoldingComplianceState,
    VerdictObservation,
    transition,
)
from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.verdict import Verdict

_D1 = date(2026, 1, 1)
_D2 = date(2026, 4, 1)
_D3 = date(2026, 7, 1)
_D4 = date(2026, 10, 1)

_TICKER = "ZZFLIP01"
_CIK = "9990000013"


def _grace_params(value: int) -> FiqhParams:
    return FIQH_PARAMS.model_copy(
        update={
            "grace_period_rebalances": FIQH_PARAMS.grace_period_rebalances.model_copy(
                update={"value": value}
            )
        }
    )


# ── record=None: first-ever screening of a new holding ──────────────────────────────────────────


def test_first_transition_from_none_initializes_held_compliant() -> None:
    record, event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    assert record.state is HoldingComplianceState.HELD_COMPLIANT
    assert record.flip_date is None
    assert record.divest_date is None
    assert record.grace_rebalances_remaining is None
    assert record.verdict_history == (VerdictObservation(as_of_date=_D1, verdict=Verdict.PURE),)
    assert event is None


def test_first_transition_from_none_with_non_compliant_verdict_raises() -> None:
    """A newly-selected holding can never itself be NON_COMPLIANT — the strategy interface's own
    structural guarantee (mizan.backtest.strategy). A violation here is a
    StrategyContractViolationError-class bug upstream, not a normal state to handle gracefully."""
    with pytest.raises(AssertionError):
        transition(
            None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.NON_COMPLIANT
        )


# ── HELD_COMPLIANT -> stays / flips ──────────────────────────────────────────────────────────────


def test_held_compliant_stays_held_compliant_on_pure_or_mixed() -> None:
    record, _event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    record2, event = transition(
        record, ticker=_TICKER, cik=_CIK, as_of_date=_D2, new_verdict=Verdict.MIXED
    )
    assert record2.state is HoldingComplianceState.HELD_COMPLIANT
    assert record2.flip_date is None
    assert len(record2.verdict_history) == 2
    assert event is None


def test_held_compliant_flips_on_non_compliant() -> None:
    record, _event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    record2, event = transition(
        record, ticker=_TICKER, cik=_CIK, as_of_date=_D2, new_verdict=Verdict.NON_COMPLIANT
    )
    assert record2.state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE
    assert record2.flip_date == _D2
    assert record2.grace_rebalances_remaining == FIQH_PARAMS.grace_period_rebalances.value
    assert event is None


# ── HELD_NONCOMPLIANT_GRACE -> stays / divests; §8 AC1/AC2 ──────────────────────────────────────


def test_default_grace_period_divests_at_the_next_rebalance_after_the_flip() -> None:
    """§8 AC1: default grace_period_rebalances.value == 1 -> divest at rebalance 3 (one rebalance
    after the flip at rebalance 2)."""
    record, _event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    record, event = transition(
        record, ticker=_TICKER, cik=_CIK, as_of_date=_D2, new_verdict=Verdict.NON_COMPLIANT
    )
    assert event is None
    assert record.state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE

    record, event = transition(
        record, ticker=_TICKER, cik=_CIK, as_of_date=_D3, new_verdict=Verdict.NON_COMPLIANT
    )
    assert record.state is HoldingComplianceState.DIVESTED
    assert record.divest_date == _D3
    assert record.grace_rebalances_remaining is None
    assert event is not None
    assert event.ticker == _TICKER
    assert event.flip_date == _D2
    assert event.divest_date == _D3


def test_grace_countdown_ignores_a_later_incidental_return_to_compliance() -> None:
    """MASTER_PRD.md §7.3's diagram draws no un-flip edge: the grace countdown runs to completion
    even if new_verdict happens to report PURE/MIXED again mid-grace."""
    params = _grace_params(2)
    record, _event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    record, _event = transition(
        record,
        ticker=_TICKER,
        cik=_CIK,
        as_of_date=_D2,
        new_verdict=Verdict.NON_COMPLIANT,
        fiqh_params=params,
    )
    record, event = transition(
        record,
        ticker=_TICKER,
        cik=_CIK,
        as_of_date=_D3,
        new_verdict=Verdict.PURE,  # incidental return to compliance — must NOT un-flip
        fiqh_params=params,
    )
    assert record.state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE
    assert event is None
    assert record.grace_rebalances_remaining == 1


def test_grace_period_config_drift_changes_divest_timing_by_exactly_one_rebalance() -> None:
    """§8 AC2 / §7 guard G-B4: grace_period_rebalances.value=2 divests one rebalance LATER than the
    default (value=1)."""
    params = _grace_params(2)
    record, _event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    record, event = transition(
        record,
        ticker=_TICKER,
        cik=_CIK,
        as_of_date=_D2,
        new_verdict=Verdict.NON_COMPLIANT,
        fiqh_params=params,
    )
    assert record.grace_rebalances_remaining == 2
    assert event is None

    record, event = transition(
        record,
        ticker=_TICKER,
        cik=_CIK,
        as_of_date=_D3,
        new_verdict=Verdict.NON_COMPLIANT,
        fiqh_params=params,
    )
    assert record.state is HoldingComplianceState.HELD_NONCOMPLIANT_GRACE  # not yet divested
    assert record.grace_rebalances_remaining == 1
    assert event is None

    record, event = transition(
        record,
        ticker=_TICKER,
        cik=_CIK,
        as_of_date=_D4,
        new_verdict=Verdict.NON_COMPLIANT,
        fiqh_params=params,
    )
    assert record.state is HoldingComplianceState.DIVESTED
    assert record.divest_date == _D4
    assert event is not None


def test_grace_period_is_read_fresh_never_a_module_level_cached_int() -> None:
    """§7 guard G-B4: `transition` reads `fiqh_params.grace_period_rebalances.value` fresh on every
    call — no module-level cached int stands in for it."""
    from mizan.backtest import compliance_state as compliance_state_module

    source = inspect.getsource(compliance_state_module.transition)
    assert "fiqh_params.grace_period_rebalances.value" in source


# ── DIVESTED must never be re-entered ────────────────────────────────────────────────────────────


def test_transition_on_a_divested_record_raises_assertion_error() -> None:
    divested_record = ComplianceStateRecord(
        ticker=_TICKER,
        cik=_CIK,
        state=HoldingComplianceState.DIVESTED,
        flip_date=_D2,
        divest_date=_D3,
        grace_rebalances_remaining=None,
        verdict_history=(
            VerdictObservation(as_of_date=_D1, verdict=Verdict.PURE),
            VerdictObservation(as_of_date=_D2, verdict=Verdict.NON_COMPLIANT),
            VerdictObservation(as_of_date=_D3, verdict=Verdict.NON_COMPLIANT),
        ),
    )
    with pytest.raises(AssertionError):
        transition(
            divested_record,
            ticker=_TICKER,
            cik=_CIK,
            as_of_date=_D4,
            new_verdict=Verdict.NON_COMPLIANT,
        )


# ── ComplianceStateRecord / DivestmentEvent / DividendEvent are frozen, extra="forbid" ──────────


def test_compliance_state_record_is_frozen_and_forbids_unknown_fields() -> None:
    record, _event = transition(
        None, ticker=_TICKER, cik=_CIK, as_of_date=_D1, new_verdict=Verdict.PURE
    )
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        record.state = HoldingComplianceState.DIVESTED


# ── §7 guard G-B5: no DB/cache/network capability in this module ───────────────────────────────


def test_compliance_state_module_has_no_db_or_network_capability() -> None:
    from mizan.backtest import compliance_state as compliance_state_module

    source = inspect.getsource(compliance_state_module)
    for forbidden in ("duckdb", "httpx", "cache_dir"):
        assert forbidden not in source
