"""Tests for mizan/purification/attribution.py — Fork C: forced-divestment price-appreciation
attribution.

Implements PHASE_6_SPEC.md §8 acceptance criteria 3 (correctly-bounded attribution, floored at
zero), 9 (flip_date <= divest_date, both by construction and by the guard assertion), 12 (every
model inherits MizanBaseModel), plus guard G-P2.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from mizan.backtest.clock import DailySnapshot
from mizan.backtest.compliance_state import (
    ComplianceStateRecord,
    DivestmentEvent,
    HoldingComplianceState,
    VerdictObservation,
)
from mizan.core.base import MizanBaseModel
from mizan.core.verdict import Verdict
from mizan.data import db
from mizan.purification.attribution import (
    DivestmentPurificationEntry,
    compute_divestment_attribution,
)

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

_TICKER = "ZZATTRIB01"
_CIK = "9990000501"
_FLIP_DATE = date(2026, 4, 1)
_DIVEST_DATE = date(2026, 7, 1)


def _con_with_price_bars(
    tmp_path: Path, *, price_at_flip: float, price_at_divest: float
) -> duckdb.DuckDBPyConnection:
    con = db.connect(tmp_path / "test.duckdb")
    for trade_date, raw_close in ((_FLIP_DATE, price_at_flip), (_DIVEST_DATE, price_at_divest)):
        con.execute(
            "INSERT INTO price_bars "
            "(ticker, trade_date, raw_open, raw_high, raw_low, raw_close, volume, adj_open, "
            "adj_high, adj_low, adj_close, adj_volume, div_cash, split_factor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _TICKER,
                trade_date,
                raw_close,
                raw_close,
                raw_close,
                raw_close,
                1_000,
                raw_close,
                raw_close,
                raw_close,
                raw_close,
                1_000,
                0.0,
                1.0,
            ],
        )
    return con


def _compliance_record(*, flip_date: date, divest_date: date) -> ComplianceStateRecord:
    return ComplianceStateRecord(
        ticker=_TICKER,
        cik=_CIK,
        state=HoldingComplianceState.DIVESTED,
        flip_date=flip_date,
        divest_date=divest_date,
        grace_rebalances_remaining=None,
        verdict_history=(
            VerdictObservation(as_of_date=date(2026, 1, 1), verdict=Verdict.PURE),
            VerdictObservation(as_of_date=flip_date, verdict=Verdict.NON_COMPLIANT),
            VerdictObservation(as_of_date=divest_date, verdict=Verdict.NON_COMPLIANT),
        ),
    )


def _flip_date_snapshot(quantity: float) -> DailySnapshot:
    return DailySnapshot(
        as_of_date=_FLIP_DATE,
        cash=0.0,
        holdings={_TICKER: quantity},
        portfolio_value=quantity * 100.0,
    )


# ── §8 AC3: correct, worked computation ─────────────────────────────────────────────────────────


def test_purified_amount_is_quantity_times_price_appreciation(tmp_path: Path) -> None:
    con = _con_with_price_bars(tmp_path, price_at_flip=100.0, price_at_divest=130.0)
    try:
        event = DivestmentEvent(
            ticker=_TICKER, cik=_CIK, flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE
        )
        compliance_states = {
            _TICKER: _compliance_record(flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE)
        }
        daily_snapshots = (_flip_date_snapshot(10_000.0),)

        entry = compute_divestment_attribution(event, compliance_states, daily_snapshots, con=con)

        assert entry.ticker == _TICKER
        assert entry.flip_date == _FLIP_DATE
        assert entry.divest_date == _DIVEST_DATE
        assert entry.quantity_liquidated == pytest.approx(10_000.0)
        assert entry.price_at_flip == pytest.approx(100.0)
        assert entry.price_at_divest == pytest.approx(130.0)
        assert entry.purified_amount == pytest.approx(10_000.0 * 30.0)
    finally:
        con.close()


# ── §6b: a price DECLINE over the window floors purified_amount at zero, never negative ───────────


def test_price_decline_over_the_window_floors_purified_amount_at_zero(tmp_path: Path) -> None:
    con = _con_with_price_bars(tmp_path, price_at_flip=100.0, price_at_divest=80.0)
    try:
        event = DivestmentEvent(
            ticker=_TICKER, cik=_CIK, flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE
        )
        compliance_states = {
            _TICKER: _compliance_record(flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE)
        }
        daily_snapshots = (_flip_date_snapshot(10_000.0),)

        entry = compute_divestment_attribution(event, compliance_states, daily_snapshots, con=con)
        assert entry.purified_amount == pytest.approx(0.0)
    finally:
        con.close()


def test_flat_price_over_the_window_produces_a_zero_amount_entry_not_an_omission(
    tmp_path: Path,
) -> None:
    con = _con_with_price_bars(tmp_path, price_at_flip=100.0, price_at_divest=100.0)
    try:
        event = DivestmentEvent(
            ticker=_TICKER, cik=_CIK, flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE
        )
        compliance_states = {
            _TICKER: _compliance_record(flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE)
        }
        daily_snapshots = (_flip_date_snapshot(10_000.0),)

        entry = compute_divestment_attribution(event, compliance_states, daily_snapshots, con=con)
        # §3.3: a checked, recorded 0.0 entry — not an omission, distinct from Fork A's Pure-verdict
        # non-entry.
        assert entry.purified_amount == pytest.approx(0.0)
    finally:
        con.close()


# ── §8 AC9 / §7 G-P2: flip_date <= divest_date, both guarded sites ────────────────────────────────


def test_mismatched_compliance_states_dates_raise_assertion_error(tmp_path: Path) -> None:
    con = _con_with_price_bars(tmp_path, price_at_flip=100.0, price_at_divest=130.0)
    try:
        event = DivestmentEvent(
            ticker=_TICKER, cik=_CIK, flip_date=_FLIP_DATE, divest_date=_DIVEST_DATE
        )
        # A deliberately mismatched flip_date — a different event log than the DivestmentEvent's
        # own.
        mismatched_states = {
            _TICKER: _compliance_record(flip_date=date(2026, 1, 1), divest_date=_DIVEST_DATE)
        }
        daily_snapshots = (_flip_date_snapshot(10_000.0),)

        with pytest.raises(AssertionError):
            compute_divestment_attribution(event, mismatched_states, daily_snapshots, con=con)
    finally:
        con.close()


def test_divestment_purification_entry_rejects_divest_before_flip() -> None:
    with pytest.raises(ValidationError):
        DivestmentPurificationEntry(
            ticker=_TICKER,
            cik=_CIK,
            flip_date=_DIVEST_DATE,  # deliberately later than divest_date, below
            divest_date=_FLIP_DATE,
            quantity_liquidated=10_000.0,
            price_at_flip=100.0,
            price_at_divest=130.0,
            purified_amount=300_000.0,
        )


def test_divestment_purification_entry_accepts_flip_equal_divest() -> None:
    """`<=`, not strictly `<` — a zero-length grace window (grace_period_rebalances == 0-equivalent
    edge case) is not itself forbidden at this type's own boundary."""
    entry = DivestmentPurificationEntry(
        ticker=_TICKER,
        cik=_CIK,
        flip_date=_FLIP_DATE,
        divest_date=_FLIP_DATE,
        quantity_liquidated=10_000.0,
        price_at_flip=100.0,
        price_at_divest=100.0,
        purified_amount=0.0,
    )
    assert entry.flip_date == entry.divest_date


# ── §8 AC12: model discipline ─────────────────────────────────────────────────────────────────────


def test_divestment_purification_entry_inherits_mizan_base_model() -> None:
    assert issubclass(DivestmentPurificationEntry, MizanBaseModel)
