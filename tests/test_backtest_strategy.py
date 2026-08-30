"""Tests for mizan/backtest/strategy.py — AllocationInstruction, Strategy, EqualWeightStrategy.

Implements PHASE_5_SPEC.md §8 acceptance criterion 7 (leverage/shorting structurally rejected) and
the EqualWeightStrategy half of criterion 4 (a strategy cannot select a Non-compliant ticker) — the
rebalance()-level enforcement / StrategyContractViolationError-raising half lives in
test_backtest_clock.py, since raising it requires the full `rebalance()` call site.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from mizan.backtest.portfolio import Portfolio
from mizan.backtest.strategy import (
    AllocationInstruction,
    EqualWeightStrategy,
    StrategyContractViolationError,
)

# ── §8 AC7: leverage/shorting structurally rejected ─────────────────────────────────────────────


def test_allocation_instruction_rejects_a_negative_weight() -> None:
    with pytest.raises(ValidationError):
        AllocationInstruction(target_weights={"ZZPURE01": -0.1})


def test_allocation_instruction_rejects_a_weight_above_one() -> None:
    with pytest.raises(ValidationError):
        AllocationInstruction(target_weights={"ZZPURE01": 1.1})


def test_allocation_instruction_rejects_weights_summing_above_one() -> None:
    with pytest.raises(ValidationError):
        AllocationInstruction(target_weights={"ZZPURE01": 0.6, "ZZMIXED01": 0.6})


def test_allocation_instruction_accepts_weights_summing_to_exactly_one() -> None:
    AllocationInstruction(target_weights={"ZZPURE01": 0.5, "ZZMIXED01": 0.5})


def test_allocation_instruction_accepts_an_empty_all_cash_instruction() -> None:
    AllocationInstruction(target_weights={})


def test_allocation_instruction_accepts_a_partial_weight_leaving_cash_as_residual() -> None:
    AllocationInstruction(target_weights={"ZZPURE01": 0.4})


def test_allocation_instruction_is_frozen_and_forbids_unknown_fields() -> None:
    instruction = AllocationInstruction(target_weights={"ZZPURE01": 1.0})
    with pytest.raises(ValidationError):
        instruction.target_weights = {}
    with pytest.raises(ValidationError):
        AllocationInstruction(target_weights={}, extra_field=1)  # type: ignore[call-arg]


# ── EqualWeightStrategy ──────────────────────────────────────────────────────────────────────────


def test_equal_weight_strategy_splits_evenly_across_compliant_tickers() -> None:
    strategy = EqualWeightStrategy()
    instruction = strategy.select(
        as_of_date=date(2026, 1, 1),
        compliant_tickers=frozenset({"ZZPURE01", "ZZMIXED01"}),
        portfolio=Portfolio(cash=1_000.0, holdings={}),
    )
    assert instruction.target_weights == {"ZZPURE01": 0.5, "ZZMIXED01": 0.5}


def test_equal_weight_strategy_with_a_single_compliant_ticker_allocates_it_fully() -> None:
    strategy = EqualWeightStrategy()
    instruction = strategy.select(
        as_of_date=date(2026, 1, 1),
        compliant_tickers=frozenset({"ZZPURE01"}),
        portfolio=Portfolio(cash=1_000.0, holdings={}),
    )
    assert instruction.target_weights == {"ZZPURE01": 1.0}


def test_equal_weight_strategy_with_no_compliant_tickers_holds_all_cash() -> None:
    strategy = EqualWeightStrategy()
    instruction = strategy.select(
        as_of_date=date(2026, 1, 1),
        compliant_tickers=frozenset(),
        portfolio=Portfolio(cash=1_000.0, holdings={}),
    )
    assert instruction.target_weights == {}


def test_strategy_contract_violation_error_is_a_runtime_error() -> None:
    assert issubclass(StrategyContractViolationError, RuntimeError)
