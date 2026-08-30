"""Tests for mizan/screening/financial_ratios.py.

Implements PHASE_4_SPEC.md §8 acceptance criteria 3 (config-drift, threshold half), 7 (missing
numerator -> 0.0, not an error), 8 (boundary semantics are `<=`), plus guard G-S7.
"""

from __future__ import annotations

import inspect

import pytest

from mizan.config.fiqh_params import FIQH_PARAMS
from mizan.screening.financial_ratios import (
    INTEREST_BEARING_DEBT_TAGS,
    INTEREST_BEARING_INVESTMENT_TAGS,
    NON_PERMISSIBLE_INCOME_TAGS,
    TOTAL_REVENUE_TAGS,
    compute_debt_ratio,
    compute_financial_ratio_screen,
    compute_interest_investments_ratio,
    compute_non_permissible_income_ratio,
)
from mizan.screening.verdict import ScreenName

_DENOMINATOR = 100_000_000.0


# ── compute_debt_ratio / compute_interest_investments_ratio / compute_non_permissible_income_ratio


def test_compute_debt_ratio_zero_numerator_passes_with_full_margin() -> None:
    entry = compute_debt_ratio(0.0, _DENOMINATOR)
    assert entry.screen is ScreenName.DEBT_RATIO
    assert entry.passed is True
    assert entry.actual_value == 0.0
    assert entry.threshold == FIQH_PARAMS.debt_ratio_threshold.value
    assert entry.margin == pytest.approx(FIQH_PARAMS.debt_ratio_threshold.value)


def test_compute_debt_ratio_above_threshold_fails_with_positive_margin() -> None:
    entry = compute_debt_ratio(35_000_000.0, _DENOMINATOR)
    assert entry.passed is False
    assert entry.actual_value == pytest.approx(0.35)
    assert entry.margin == pytest.approx(0.05)


def test_compute_debt_ratio_exactly_at_threshold_passes() -> None:
    """§8 AC8: boundary semantics are `<=` — a value AT the threshold passes."""
    threshold = FIQH_PARAMS.debt_ratio_threshold.value
    numerator = threshold * _DENOMINATOR
    entry = compute_debt_ratio(numerator, _DENOMINATOR)
    assert entry.passed is True
    assert entry.actual_value == pytest.approx(threshold)
    assert entry.margin == pytest.approx(0.0)


def test_compute_interest_investments_ratio_uses_its_own_threshold() -> None:
    entry = compute_interest_investments_ratio(40_000_000.0, _DENOMINATOR)
    assert entry.screen is ScreenName.INTEREST_INVESTMENTS_RATIO
    assert entry.threshold == FIQH_PARAMS.interest_investments_threshold.value
    assert entry.passed is False  # 0.40 > 0.30


def test_compute_non_permissible_income_ratio_denominator_is_total_revenue_not_two_axis() -> None:
    """The income ratio's denominator is ALWAYS `total_revenue`, regardless of what the two-axis
    market-cap/assets denominator would be — this test passes a deliberately different value for
    each to prove they are never conflated."""
    total_revenue = 20_000_000.0
    entry = compute_non_permissible_income_ratio(1_000_000.0, total_revenue)
    assert entry.screen is ScreenName.NON_PERMISSIBLE_INCOME_RATIO
    assert entry.threshold == FIQH_PARAMS.non_permissible_income_threshold.value
    assert entry.actual_value == pytest.approx(1_000_000.0 / total_revenue)


def test_non_permissible_income_ratio_exactly_at_threshold_passes() -> None:
    threshold = FIQH_PARAMS.non_permissible_income_threshold.value
    total_revenue = 50_000_000.0
    numerator = threshold * total_revenue
    entry = compute_non_permissible_income_ratio(numerator, total_revenue)
    assert entry.passed is True
    assert entry.margin == pytest.approx(0.0)


# ── §8 AC3 / G-S5: threshold config-drift changes the verdict ──────────────────────────────────


def test_debt_ratio_threshold_change_via_model_copy_flips_pass_fail() -> None:
    numerator = 25_000_000.0  # 25%, passes the default 30% threshold
    default_entry = compute_debt_ratio(numerator, _DENOMINATOR)
    assert default_entry.passed is True

    lowered_params = FIQH_PARAMS.model_copy(
        update={
            "debt_ratio_threshold": FIQH_PARAMS.debt_ratio_threshold.model_copy(
                update={"value": 0.20}
            )
        }
    )
    lowered_entry = compute_debt_ratio(numerator, _DENOMINATOR, fiqh_params=lowered_params)
    assert lowered_entry.passed is False
    assert lowered_entry.threshold == 0.20


# ── compute_financial_ratio_screen: combination + always-computed-all-three ────────────────────


def test_compute_financial_ratio_screen_passes_iff_all_three_pass() -> None:
    result = compute_financial_ratio_screen(
        interest_bearing_debt=10_000_000.0,
        interest_bearing_investments=5_000_000.0,
        non_permissible_income=1_000_000.0,
        total_revenue=50_000_000.0,
        denominator=_DENOMINATOR,
    )
    assert result.passed is True
    assert result.debt_ratio.passed is True
    assert result.interest_investments_ratio.passed is True
    assert result.non_permissible_income_ratio.passed is True


def test_compute_financial_ratio_screen_fails_overall_if_any_one_check_fails() -> None:
    result = compute_financial_ratio_screen(
        interest_bearing_debt=35_000_000.0,  # fails
        interest_bearing_investments=0.0,
        non_permissible_income=0.0,
        total_revenue=50_000_000.0,
        denominator=_DENOMINATOR,
    )
    assert result.passed is False
    assert result.debt_ratio.passed is False
    # §6c: all three checks are still computed and present, even though only one failed.
    assert result.interest_investments_ratio.passed is True
    assert result.non_permissible_income_ratio.passed is True


def test_compute_financial_ratio_screen_all_zero_numerators() -> None:
    """§8 AC7: a missing numerator (represented here as an already-resolved 0.0, per §4.2's
    absence-is-zero rule enforced upstream in verdict.py) computes a ratio of exactly 0.0, never an
    error."""
    result = compute_financial_ratio_screen(
        interest_bearing_debt=0.0,
        interest_bearing_investments=0.0,
        non_permissible_income=0.0,
        total_revenue=50_000_000.0,
        denominator=_DENOMINATOR,
    )
    assert result.passed is True
    assert result.debt_ratio.actual_value == 0.0
    assert result.interest_investments_ratio.actual_value == 0.0
    assert result.non_permissible_income_ratio.actual_value == 0.0


# ── G-S7: pure functions, no DB/cache/date capability anywhere in this module ───────────────────


def test_no_ratio_function_has_a_db_cache_or_date_parameter() -> None:
    for func in (
        compute_debt_ratio,
        compute_interest_investments_ratio,
        compute_non_permissible_income_ratio,
        compute_financial_ratio_screen,
    ):
        params = inspect.signature(func).parameters
        assert "con" not in params
        assert "cache_dir" not in params
        assert "as_of_date" not in params


def test_no_llm_or_db_import_in_financial_ratios_module() -> None:
    import mizan.screening.financial_ratios as module

    source = inspect.getsource(module).lower()
    for forbidden in ("openai", "anthropic", "gemini", "vertex", "langchain", "duckdb", "httpx"):
        assert forbidden not in source


# ── The four tag allow-lists exist and are the exact, closed sets §4.2 specifies ────────────────


def test_tag_allow_lists_are_closed_and_exact() -> None:
    assert (
        frozenset(
            {"LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings", "DebtCurrent"}
        )
        == INTEREST_BEARING_DEBT_TAGS
    )
    assert (
        frozenset({"ShortTermInvestments", "LongTermInvestments", "MarketableSecuritiesCurrent"})
        == INTEREST_BEARING_INVESTMENT_TAGS
    )
    assert (
        frozenset(
            {
                "InvestmentIncomeInterest",
                "InterestIncomeOther",
                "InterestAndDividendIncomeOperating",
            }
        )
        == NON_PERMISSIBLE_INCOME_TAGS
    )
    assert (
        frozenset({"Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"})
        == TOTAL_REVENUE_TAGS
    )
