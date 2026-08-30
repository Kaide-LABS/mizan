"""Tests for mizan/backtest/portfolio.py — holdings and cash bookkeeping.

Implements PHASE_5_SPEC.md §8 acceptance criteria 3 (negative quantity/cash rejected at
validation), 5 (cash never accrues yield), 9 (INVARIANTS.cash_yield is read, never re-hardcoded),
plus guards G-B1a, G-B1b, G-B2b, G-B2d.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from mizan.backtest.clock import step
from mizan.backtest.portfolio import (
    Holding,
    Portfolio,
    apply_allocation,
    apply_cash_yield,
    apply_split,
    credit_dividend,
    mark_to_market,
)
from mizan.backtest.strategy import AllocationInstruction
from mizan.config.invariants import INVARIANTS

# ── §8 AC3 / G-B2b / G-B2d: negative quantity/cash rejected at validation ──────────────────────


def test_holding_rejects_negative_quantity() -> None:
    with pytest.raises(ValidationError):
        Holding(ticker="ZZPURE01", quantity=-1.0)


def test_holding_accepts_zero_and_fractional_quantity() -> None:
    Holding(ticker="ZZPURE01", quantity=0.0)
    Holding(ticker="ZZPURE01", quantity=0.5)


def test_portfolio_rejects_negative_cash() -> None:
    with pytest.raises(ValidationError):
        Portfolio(cash=-1.0, holdings={})


def test_portfolio_accepts_zero_cash() -> None:
    Portfolio(cash=0.0, holdings={})


def test_holding_and_portfolio_are_frozen() -> None:
    holding = Holding(ticker="ZZPURE01", quantity=1.0)
    portfolio = Portfolio(cash=1.0, holdings={})
    with pytest.raises(ValidationError):
        holding.quantity = 2.0
    with pytest.raises(ValidationError):
        portfolio.cash = 2.0


def test_holding_and_portfolio_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Holding(ticker="ZZPURE01", quantity=1.0, extra_field=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Portfolio(cash=1.0, holdings={}, extra_field=1)  # type: ignore[call-arg]


# ── §8 AC5 / G-B1a / G-B1b: cash never accrues yield ────────────────────────────────────────────


def test_invariants_cash_yield_is_zero() -> None:
    """Sanity check on the fixture itself: this suite's own "cash is bit-for-bit identical" tests
    are only meaningful if INVARIANTS.cash_yield really is 0.0."""
    assert INVARIANTS.cash_yield == 0.0


def test_apply_cash_yield_is_a_structural_no_op() -> None:
    portfolio = Portfolio(cash=12_345.6789, holdings={})
    result = apply_cash_yield(portfolio)
    assert result.cash == portfolio.cash


def test_cash_bit_for_bit_identical_across_a_multi_day_idle_window() -> None:
    """§8 AC5: a multi-day window with idle cash, no trade, no dividend -> cash unchanged, checked
    with `==` since no arithmetic altering it ever runs."""
    portfolio = Portfolio(cash=1_000_000.0, holdings={})
    starting_cash = portfolio.cash
    for _ in range(10):
        portfolio = step(portfolio, prices={}, splits={})
    assert portfolio.cash == starting_cash


def test_apply_cash_yield_reads_invariants_directly_never_a_parameter() -> None:
    """G-B1b: apply_cash_yield's own body reads INVARIANTS.cash_yield directly; it accepts no such
    parameter, and no other function in this module re-hardcodes a bare 0.0 standing in for it."""
    from mizan.backtest import portfolio as portfolio_module

    signature = inspect.signature(portfolio_module.apply_cash_yield)
    assert "cash_yield" not in signature.parameters
    source = inspect.getsource(portfolio_module.apply_cash_yield)
    assert "INVARIANTS.cash_yield" in source


def _function_body_references_name(func: Callable[..., object], name: str) -> bool:
    """True iff `name` is referenced as a bare identifier anywhere in `func`'s EXECUTABLE body —
    excluding its own docstring, which may legitimately discuss the name in prose (e.g.
    `credit_dividend`'s docstring explains it is UNAFFECTED by `INVARIANTS.cash_yield`, which must
    not itself count as a body reference)."""
    source = textwrap.dedent(inspect.getsource(func))
    func_def = ast.parse(source).body[0]
    assert isinstance(func_def, ast.FunctionDef)
    body = func_def.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]  # drop the docstring statement
    return any(
        isinstance(node, ast.Name) and node.id == name
        for statement in body
        for node in ast.walk(statement)
    )


def test_cash_yield_is_read_only_from_apply_cash_yields_own_body() -> None:
    """G-B1b, checked precisely: `INVARIANTS` is referenced in the EXECUTABLE body of
    `apply_cash_yield` only — no other function in this module (`apply_split`, `mark_to_market`,
    `credit_dividend`, `apply_allocation`) references it in its own body, even though several of
    their docstrings legitimately discuss `INVARIANTS.cash_yield` in prose."""
    from mizan.backtest import portfolio as portfolio_module

    assert _function_body_references_name(portfolio_module.apply_cash_yield, "INVARIANTS")
    for other in (
        portfolio_module.apply_split,
        portfolio_module.mark_to_market,
        portfolio_module.credit_dividend,
        portfolio_module.apply_allocation,
    ):
        assert not _function_body_references_name(other, "INVARIANTS"), (
            f"{other.__name__} references INVARIANTS in its own executable body"
        )


# ── apply_split — verified direction (docs/modernization_log.md §6.2b) ─────────────────────────


def test_apply_split_multiplies_quantity_by_split_factor() -> None:
    """A 2-for-1 split (Tiingo splitFactor = splitTo/splitFrom = 2.0) doubles a held share count."""
    holding = Holding(ticker="ZZPURE01", quantity=100.0)
    result = apply_split(holding, 2.0)
    assert result.quantity == pytest.approx(200.0)


def test_apply_split_is_a_no_op_at_factor_one() -> None:
    holding = Holding(ticker="ZZPURE01", quantity=100.0)
    result = apply_split(holding, 1.0)
    assert result.quantity == pytest.approx(100.0)


def test_apply_split_reverse_split_below_one_reduces_quantity() -> None:
    holding = Holding(ticker="ZZPURE01", quantity=100.0)
    result = apply_split(holding, 0.5)
    assert result.quantity == pytest.approx(50.0)


# ── mark_to_market ───────────────────────────────────────────────────────────────────────────────


def test_mark_to_market_sums_cash_and_holdings_value() -> None:
    portfolio = Portfolio(
        cash=1_000.0, holdings={"ZZPURE01": Holding(ticker="ZZPURE01", quantity=10.0)}
    )
    value = mark_to_market(portfolio, {"ZZPURE01": 50.0})
    assert value == pytest.approx(1_000.0 + 10.0 * 50.0)


def test_mark_to_market_with_no_holdings_is_just_cash() -> None:
    portfolio = Portfolio(cash=500.0, holdings={})
    assert mark_to_market(portfolio, {}) == pytest.approx(500.0)


# ── credit_dividend ──────────────────────────────────────────────────────────────────────────────


def test_credit_dividend_increases_cash_by_quantity_times_div_cash_per_share() -> None:
    portfolio = Portfolio(
        cash=0.0, holdings={"ZZPURE01": Holding(ticker="ZZPURE01", quantity=10.0)}
    )
    result = credit_dividend(portfolio, "ZZPURE01", 2.0)
    assert result.cash == pytest.approx(20.0)


def test_credit_dividend_on_an_unheld_ticker_is_a_no_op() -> None:
    portfolio = Portfolio(cash=100.0, holdings={})
    result = credit_dividend(portfolio, "ZZPURE01", 2.0)
    assert result.cash == pytest.approx(100.0)
    assert result.holdings == {}


def test_credit_dividend_never_touches_cash_yield() -> None:
    """§3.1's own clarifying note: a dividend is a realized distribution, unrelated to
    INVARIANTS.cash_yield — checked at the executable-body level (see
    `test_cash_yield_is_read_only_from_apply_cash_yields_own_body`, which covers this function
    too); this test additionally confirms `credit_dividend` never calls `apply_cash_yield`."""
    from mizan.backtest import portfolio as portfolio_module

    source = inspect.getsource(portfolio_module.credit_dividend)
    assert "apply_cash_yield(" not in source


# ── apply_allocation ─────────────────────────────────────────────────────────────────────────────


def test_apply_allocation_full_investment_leaves_zero_cash() -> None:
    portfolio = Portfolio(cash=1_000.0, holdings={})
    instruction = AllocationInstruction(target_weights={"ZZPURE01": 1.0})
    result = apply_allocation(portfolio, instruction, {"ZZPURE01": 100.0})
    assert result.cash == pytest.approx(0.0)
    assert result.holdings["ZZPURE01"].quantity == pytest.approx(10.0)


def test_apply_allocation_partial_weight_leaves_the_residual_as_cash() -> None:
    portfolio = Portfolio(cash=1_000.0, holdings={})
    instruction = AllocationInstruction(target_weights={"ZZPURE01": 0.4})
    result = apply_allocation(portfolio, instruction, {"ZZPURE01": 100.0})
    assert result.cash == pytest.approx(600.0)
    assert result.holdings["ZZPURE01"].quantity == pytest.approx(4.0)


def test_apply_allocation_liquidates_a_ticker_absent_from_target_weights() -> None:
    portfolio = Portfolio(
        cash=0.0, holdings={"ZZPURE01": Holding(ticker="ZZPURE01", quantity=10.0)}
    )
    instruction = AllocationInstruction(target_weights={})
    result = apply_allocation(portfolio, instruction, {"ZZPURE01": 100.0})
    assert result.holdings == {}
    assert result.cash == pytest.approx(1_000.0)


def test_apply_allocation_rebalances_between_two_tickers() -> None:
    portfolio = Portfolio(
        cash=0.0, holdings={"ZZPURE01": Holding(ticker="ZZPURE01", quantity=10.0)}
    )
    instruction = AllocationInstruction(target_weights={"ZZMIXED01": 1.0})
    result = apply_allocation(portfolio, instruction, {"ZZPURE01": 100.0, "ZZMIXED01": 50.0})
    assert "ZZPURE01" not in result.holdings
    assert result.holdings["ZZMIXED01"].quantity == pytest.approx(1_000.0 / 50.0)
    assert result.cash == pytest.approx(0.0)


def test_apply_allocation_never_produces_negative_cash_or_quantity() -> None:
    """§7 guard G-B2b/G-B2d, restated at the function level: a conforming AllocationInstruction can
    never drive apply_allocation to construct an invalid Portfolio, and a zero-weight ticker is
    never retained in holdings (§3.1)."""
    portfolio = Portfolio(cash=100.0, holdings={})
    instruction = AllocationInstruction(target_weights={"ZZPURE01": 1.0, "ZZMIXED01": 0.0})
    result = apply_allocation(portfolio, instruction, {"ZZPURE01": 100.0, "ZZMIXED01": 50.0})
    assert result.cash >= 0.0
    assert all(h.quantity >= 0.0 for h in result.holdings.values())
    assert "ZZMIXED01" not in result.holdings
