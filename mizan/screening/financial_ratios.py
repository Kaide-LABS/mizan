"""mizan/screening/financial_ratios.py — the 30/30/5 financial-ratio screen.

Implements PHASE_4_SPEC.md §3.3, §4.2, §6b.

Every function here is pure arithmetic over already-resolved plain `float`s — no DB access, no
cache access, no dates, no network, anywhere in this module (§7 guard G-S7). The two-axis
denominator (market cap vs. total assets, spot vs. averaged) is resolved exactly once, upstream, in
`mizan.screening.verdict`; this module does not know or care which basis produced the `denominator`
value it is handed.

**XBRL tag verification (PHASE_4_SPEC.md §2.2), performed live 2026-08-30 and logged in
`docs/modernization_log.md` §6.3:** every tag below was checked against at least one real EDGAR
`companyfacts` response. `us-gaap:Assets`, `LongTermDebtNoncurrent`, `LongTermDebtCurrent`,
`MarketableSecuritiesCurrent`, `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`,
and `dei:EntityCommonStockSharesOutstanding` were all confirmed present with the expected shape
against Apple Inc. (CIK 0000320193). `ShortTermBorrowings`, `InvestmentIncomeInterest`,
`InterestIncomeOther`, and `InterestAndDividendIncomeOperating` were confirmed against JPMorgan
Chase & Co. (CIK 0000019617) — Apple, having no interest-bearing-deposit core business, simply
never files those bank-typical tags, which is exactly the "0.0, not an error" numerator-absence
case this module's design already anticipates. `DebtCurrent` was confirmed against The Travelers
Companies, Inc. (CIK 0000086312); `ShortTermInvestments` against both NIKE, Inc. (CIK 0000320187)
and Caterpillar Inc. (CIK 0000018230). `LongTermInvestments` could NOT be confirmed live against
any of the six real companyfacts responses checked in this pass — it remains a standard,
taxonomically valid `us-gaap` concept name, but its live presence is unconfirmed; logged as such
rather than silently assumed.
"""

from __future__ import annotations

from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.base import MizanBaseModel
from mizan.screening.verdict import ReasonTraceEntry, ScreenName

#: Candidate XBRL tags for the debt-ratio numerator (interest-bearing debt), a closed allow-list
#: over which tags are SUMMED AS AVAILABLE (§6b) — a numerator absent from a company's companyfacts
#: (no matching tag reported at all) is treated as `0.0`, not an error: many genuinely debt-free
#: firms simply never file these tags. This is the opposite posture from
#: `mizan.data.normalize.RECOGNIZED_XBRL_UNITS` (Phase 3), which REJECTS a miss — here a miss on the
#: NUMERATOR side is a legitimate "this company has none of this."
INTEREST_BEARING_DEBT_TAGS: frozenset[str] = frozenset(
    {"LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings", "DebtCurrent"}
)

#: Candidate XBRL tags for the interest/investments-ratio numerator (interest-bearing investments),
#: same summed-as-available posture as `INTEREST_BEARING_DEBT_TAGS`.
INTEREST_BEARING_INVESTMENT_TAGS: frozenset[str] = frozenset(
    {"ShortTermInvestments", "LongTermInvestments", "MarketableSecuritiesCurrent"}
)

#: Candidate XBRL tags for the non-permissible-income-ratio numerator. **A documented, sourced
#: proxy decision, not a settled fact:** most issuers never file a line item literally labeled
#: "non-halal income" — this allow-list is Phase 4's concrete, transparent, cited stand-in for that
#: concept, carrying the same "not settled, here is exactly what it stands in for" honesty
#: treatment the fiqh register gives its own entries, without itself being promoted into the
#: 11-entry register (it is a data-mapping proxy for register #5's numerator, not a new judgment
#: call about a threshold or a toggle — register #5 itself,
#: `mizan.config.fiqh_params.FIQH_PARAMS.non_permissible_income_threshold`, is untouched).
NON_PERMISSIBLE_INCOME_TAGS: frozenset[str] = frozenset(
    {"InvestmentIncomeInterest", "InterestIncomeOther", "InterestAndDividendIncomeOperating"}
)

#: Register #5's own `primary_source_gap` ("Phase 4 must pick one explicitly and cite this gap",
#: `mizan/config/fiqh_params.py`) — Phase 4 picks the "total revenue" reading (`MASTER_PRD.md`
#: §6.2's own wording), NOT the "Total Income" reading the AAOIFI primary source literally uses
#: (verified verbatim, `docs/modernization_log.md` §7). This does NOT resolve `ULTIMATE_PRD.md` Q2
#: — that remains escalated (PHASE_4_SPEC.md §9) — it is Phase 4 making a concrete, transparent,
#: cited choice so the code can run. Unlike the three numerator allow-lists above, an EMPTY result
#: over this set is an `InsufficientDataError` (§6b) — total revenue is a REQUIRED denominator for
#: ratio 3, not an optional numerator.
TOTAL_REVENUE_TAGS: frozenset[str] = frozenset(
    {"Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"}
)


class FinancialRatioScreenResult(MizanBaseModel):
    """The Layer-2 (financial-ratio) screen's full result: all three checks, always computed and
    always present in the reason trace, regardless of whether any individual one failed."""

    passed: bool
    """`True` iff all three of the below pass."""
    debt_ratio: ReasonTraceEntry
    interest_investments_ratio: ReasonTraceEntry
    non_permissible_income_ratio: ReasonTraceEntry


def _ratio_reason(
    *, screen: ScreenName, numerator: float, denominator: float, threshold: float, detail_label: str
) -> ReasonTraceEntry:
    """Shared arithmetic + `ReasonTraceEntry` construction for all three ratio checks (§6c): a
    value AT the threshold passes (`<=`, AAOIFI's own verbatim "should not EXCEED" wording,
    `docs/modernization_log.md` §7 — inclusive of the boundary itself; `MASTER_PRD.md` §6.2's
    "< 30%" phrasing is the less precise restatement, and this is the primary-source-verbatim
    reading).
    `margin` is `threshold - actual` when passing (positive = comfortable margin) or
    `actual - threshold` when failing (positive = how far over) — arXiv:2608.12634's finding that
    distance-to-threshold predicts next-period compliance transitions.
    """
    actual = numerator / denominator
    passed = actual <= threshold
    margin = (threshold - actual) if passed else (actual - threshold)
    return ReasonTraceEntry(
        screen=screen,
        passed=passed,
        threshold=threshold,
        actual_value=actual,
        margin=margin,
        detail=(
            f"{detail_label}: {numerator!r} / {denominator!r} = {actual:.6f} vs. threshold "
            f"{threshold:.6f}"
        ),
    )


def compute_debt_ratio(
    interest_bearing_debt: float, denominator: float, *, fiqh_params: FiqhParams = FIQH_PARAMS
) -> ReasonTraceEntry:
    """Pure arithmetic: `interest_bearing_debt / denominator`, compared against
    `fiqh_params.debt_ratio_threshold.value` using `<=`. `denominator` is ALREADY the resolved,
    config-selected two-axis value (§6b) — this function does not know or care whether it is
    market-cap or total-assets, spot or averaged; that resolution happens once, upstream, in
    `mizan.screening.verdict`.
    """
    return _ratio_reason(
        screen=ScreenName.DEBT_RATIO,
        numerator=interest_bearing_debt,
        denominator=denominator,
        threshold=fiqh_params.debt_ratio_threshold.value,
        detail_label="interest_bearing_debt / denominator",
    )


def compute_interest_investments_ratio(
    interest_bearing_investments: float,
    denominator: float,
    *,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ReasonTraceEntry:
    """Identical shape to `compute_debt_ratio`, against
    `fiqh_params.interest_investments_threshold.value`."""
    return _ratio_reason(
        screen=ScreenName.INTEREST_INVESTMENTS_RATIO,
        numerator=interest_bearing_investments,
        denominator=denominator,
        threshold=fiqh_params.interest_investments_threshold.value,
        detail_label="interest_bearing_investments / denominator",
    )


def compute_non_permissible_income_ratio(
    non_permissible_income: float, total_revenue: float, *, fiqh_params: FiqhParams = FIQH_PARAMS
) -> ReasonTraceEntry:
    """Against `fiqh_params.non_permissible_income_threshold.value`; the denominator is ALWAYS
    `total_revenue` — never the two-axis market-cap/assets choice, which applies only to
    `compute_debt_ratio`/`compute_interest_investments_ratio`."""
    return _ratio_reason(
        screen=ScreenName.NON_PERMISSIBLE_INCOME_RATIO,
        numerator=non_permissible_income,
        denominator=total_revenue,
        threshold=fiqh_params.non_permissible_income_threshold.value,
        detail_label="non_permissible_income / total_revenue",
    )


def compute_financial_ratio_screen(
    *,
    interest_bearing_debt: float,
    interest_bearing_investments: float,
    non_permissible_income: float,
    total_revenue: float,
    denominator: float,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> FinancialRatioScreenResult:
    """Runs all three checks above and combines them — `passed` iff all three pass. Every field is a
    plain float already resolved by the caller; no DB access, no dates, anywhere in this module.
    """
    debt_ratio = compute_debt_ratio(interest_bearing_debt, denominator, fiqh_params=fiqh_params)
    interest_investments_ratio = compute_interest_investments_ratio(
        interest_bearing_investments, denominator, fiqh_params=fiqh_params
    )
    non_permissible_income_ratio = compute_non_permissible_income_ratio(
        non_permissible_income, total_revenue, fiqh_params=fiqh_params
    )
    passed = (
        debt_ratio.passed
        and interest_investments_ratio.passed
        and non_permissible_income_ratio.passed
    )
    return FinancialRatioScreenResult(
        passed=passed,
        debt_ratio=debt_ratio,
        interest_investments_ratio=interest_investments_ratio,
        non_permissible_income_ratio=non_permissible_income_ratio,
    )
