"""mizan/screening/verdict.py — the `screen()` entry point; combines both screening layers into a
`Verdict` + full reason trace.

Implements PHASE_4_SPEC.md §3.1, §3.4, §4.3, §6b, §6c, §6d.

**DISTINCT from `mizan.core.verdict`**, which defines only the three-state `Verdict` **enum**
(Phase 1, unmodified). Every reference to the enum in this module imports it as
``from mizan.core.verdict import Verdict`` rather than a bare ``Verdict``, so a reviewer's
``grep -n "Verdict"`` distinguishes "the enum" from "the module that produces it"
(PHASE_4_SPEC.md §0).

This module is the ONLY function body in `mizan/` permitted to treat "most-recently-filed fact
with `filed <= as_of_date`" as sufficient point-in-time resolution (the Fork-1 simplification,
ULTIMATE_PRD.md §3.3, `Caveat.LOOK_AHEAD_BIAS`) — every private helper that touches `filed` lives
here, takes `as_of_date`, and is reachable only from `screen()`. Neither
`mizan.screening.business_activity` nor `mizan.screening.financial_ratios` references `filed` at
all; they operate purely on already-resolved plain values passed in by this module (§6d).

**Import-order note, read before touching this file's imports:**
`mizan.screening.business_activity` and `mizan.screening.financial_ratios` both need
`ReasonTraceEntry`/`ScreenName` (defined here, §3.1) to type their own result models
(`BusinessActivityScreenResult.reason`, `FinancialRatioScreenResult.debt_ratio`, etc.) — a genuine
two-way dependency between this module and its two siblings. Rather than importing those two
sibling modules at THIS module's top level (which would deadlock on whichever module Python
happens to import first — a fragile, import-order-dependent circular import), `screen()` imports
`classify_business_activity`/`resolve_sic_offline` and `compute_financial_ratio_screen` LOCALLY,
inside its own function body. A function body's imports do not execute until the function is
actually called, by which point every module in `mizan.screening`
has already finished loading (regardless of which one a caller imports first) — the standard,
well-understood pattern for breaking a two-way import dependency between sibling modules. This
module's own top-level code has zero import-time dependency on either sibling.
"""

from __future__ import annotations

from datetime import date as _Date  # noqa: N812 -- underscore-prefixed alias, matches normalize.py
from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from mizan.config.fiqh_params import (
    FIQH_PARAMS,
    FiqhParams,
    RatioDenominatorBasis,
    RatioDenominatorSmoothing,
)
from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict
from mizan.data.normalize import resolve_cik_offline

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

    from mizan.screening.business_activity import BusinessActivityOverrideMap

# ── §3.1 The reason trace ────────────────────────────────────────────────────────────────────────


class ScreenName(StrEnum):
    """Which of the four screens produced one `ReasonTraceEntry`.

    Four, not three, because the financial-ratio screen's three checks (`MASTER_PRD.md` §6.2) are
    individually distinguishable — "which ratio" means each ratio gets its own trace entry, not one
    combined "financial_ratios" entry hiding which of the three actually failed.
    """

    BUSINESS_ACTIVITY = "business_activity"
    DEBT_RATIO = "debt_ratio"
    INTEREST_INVESTMENTS_RATIO = "interest_investments_ratio"
    NON_PERMISSIBLE_INCOME_RATIO = "non_permissible_income_ratio"


class ReasonTraceEntry(MizanBaseModel):
    """One inspectable line of `MASTER_PRD.md` §6.3's "reason trace... which screen, which ratio,
    what value vs. threshold." Every screen actually EXECUTED produces exactly one entry — including
    a PASSING one; any pass/fail is inspectable, not just failures.

    `threshold`/`actual_value`/`margin` are all `None` for a `BUSINESS_ACTIVITY` entry (a tier match
    is categorical, not a threshold comparison) and all non-`None` for the three ratio entries.
    `margin` is `threshold - actual_value` for a passing ratio check (positive = comfortable margin)
    or `actual_value - threshold` for a failing one (positive = how far over) — retained because the
    ratio functions already compute this value to decide pass/fail (arXiv:2608.12634's finding that
    distance-to-threshold predicts next-period compliance transitions), with zero effect on the
    verdict itself.
    """

    screen: ScreenName
    passed: bool
    threshold: float | None
    actual_value: float | None
    margin: float | None
    detail: str
    """Human-readable: which tier/SIC/override, or which XBRL-derived figures, drove this entry."""


class ScreeningVerdict(MizanBaseModel):
    """The purpose-built, fully-typed per-ticker screening result.

    Wrapped inside `ResultEnvelope.payload` by `screen()` (§3.4) rather than returned directly —
    `screen()` returns
    `ResultEnvelope(active_caveats=(...), payload=screening_verdict.model_dump())`,
    and any caller needing the typed shape back reconstructs it via
    `ScreeningVerdict.model_validate(envelope.payload)`, a lossless, `extra="forbid"`-checked round
    trip. This keeps the caveats living structurally on the envelope (never buried inside
    `ScreeningVerdict` itself) while still giving every internal function and test a fully-typed
    value to work with before that final wrapping step.
    """

    ticker: str
    cik: str
    as_of_date: _Date
    verdict: Verdict
    """`mizan.core.verdict.Verdict` — imported by full path, see this module's own docstring."""
    reason_trace: tuple[ReasonTraceEntry, ...]


# ── §4.3 screen() and its private helpers ───────────────────────────────────────────────────────


class NotNormalizedError(RuntimeError):
    """Raised when NEITHER `fundamentals_facts` (by `cik`) NOR `price_bars` (by `ticker`) has any
    row at all, for a ticker/CIK that PASSED Layer 1 — i.e. `mizan normalize` was never run for it.

    A ticker that FAILS Layer 1 never reaches this check at all (§6e's fail-fast ordering) — it
    never needs Phase 3's tables, so it can never raise this error.
    """


class InsufficientDataError(RuntimeError):
    """Raised when a REQUIRED denominator-side figure (total assets, OR shares-outstanding-times-
    price for market cap, OR total revenue) has no resolvable value as of `as_of_date`, for a ticker
    that passed Layer 1. Never silently defaulted to 0 or 1 — a missing denominator cannot be
    guessed without either a division-by-zero or a fabricated scale, both of which are "reject
    rather than guess" (ULTIMATE_PRD.md §4.3) violations. Distinct from a numerator-side miss (§4.2
    of the spec), which is a legitimate `0.0`, not an error.
    """


def _ensure_normalized(cik: str, ticker: str, *, con: duckdb.DuckDBPyConnection) -> None:
    """Raise `NotNormalizedError` iff BOTH `fundamentals_facts` (keyed by `cik`) and `price_bars`
    (keyed by `ticker`) have zero rows — i.e. this ticker/CIK has never been normalized at all.

    Does not reference `filed` — this is a coarse "was `mizan normalize` ever run for this
    ticker" gate, not a point-in-time resolution, so it takes no `as_of_date` parameter.
    """
    facts_row = con.execute(
        "SELECT count(*) FROM fundamentals_facts WHERE cik = ?", [cik]
    ).fetchone()
    bars_row = con.execute("SELECT count(*) FROM price_bars WHERE ticker = ?", [ticker]).fetchone()
    facts_count = int(facts_row[0]) if facts_row is not None else 0
    bars_count = int(bars_row[0]) if bars_row is not None else 0
    if facts_count == 0 and bars_count == 0:
        raise NotNormalizedError(
            f"{ticker} (CIK {cik}): no normalized fundamentals_facts or price_bars rows at all — "
            "run `mizan normalize` first"
        )


def _resolve_total_assets_denominator(
    cik: str,
    as_of_date: _Date,
    *,
    con: duckdb.DuckDBPyConnection,
    smoothing: RatioDenominatorSmoothing,
) -> float:
    """Resolve the `RatioDenominatorBasis.TOTAL_ASSETS` axis (§6b), hard-filtered `filed <=
    as_of_date` and `period_end <= as_of_date`. SPOT takes the single most-recently-filed row
    (ties broken by the most recent `period_end`); AVERAGED takes the mean of one value per
    distinct `period_end` within the trailing 12 months of `as_of_date`, using the
    most-recently-filed value for each `period_end` to avoid double-counting a restated period.

    Raises:
        InsufficientDataError: if no `us-gaap:Assets` fact (unit USD, instantaneous) satisfies the
            `filed <= as_of_date` filter at all, or (AVERAGED only) none falls within the trailing
            12-month window.
    """
    rows = con.execute(
        "SELECT value, period_end, filed FROM fundamentals_facts "
        "WHERE cik = ? AND taxonomy = 'us-gaap' AND tag = 'Assets' AND unit = 'USD' "
        "AND is_instantaneous AND filed <= ? AND period_end <= ?",
        [cik, as_of_date, as_of_date],
    ).fetchall()
    if not rows:
        raise InsufficientDataError(f"CIK {cik}: no us-gaap:Assets fact filed <= {as_of_date}")

    if smoothing == RatioDenominatorSmoothing.SPOT:
        best_value, _best_period_end, _best_filed = max(rows, key=lambda row: (row[2], row[1]))
        return float(best_value)

    window_start = as_of_date - timedelta(days=365)
    latest_by_period_end: dict[_Date, tuple[float, _Date]] = {}
    for value, period_end, filed in rows:
        if period_end <= window_start:
            continue
        current = latest_by_period_end.get(period_end)
        if current is None or filed > current[1]:
            latest_by_period_end[period_end] = (float(value), filed)
    if not latest_by_period_end:
        raise InsufficientDataError(
            f"CIK {cik}: no us-gaap:Assets fact with period_end within the trailing 12 months of "
            f"{as_of_date}"
        )
    values = [value for value, _filed in latest_by_period_end.values()]
    return sum(values) / len(values)


def _resolve_market_cap_denominator(
    cik: str,
    ticker: str,
    as_of_date: _Date,
    *,
    con: duckdb.DuckDBPyConnection,
    smoothing: RatioDenominatorSmoothing,
) -> float:
    """Resolve the `RatioDenominatorBasis.MARKET_CAP` axis (§6b, the default): shares outstanding
    (always spot — the single most-recently-filed `dei:EntityCommonStockSharesOutstanding` fact,
    `filed <= as_of_date`) times price. SPOT price is `price_bars.raw_close` on the most recent
    `trade_date <= as_of_date`; AVERAGED price is the mean of `raw_close` over
    `(as_of_date - 365 days, as_of_date]`.

    `raw_close`, never `adj_close` — a deliberate, explicit choice (§6b): pairing a
    split-back-adjusted price with a not-similarly-adjusted shares-outstanding count would silently
    misstate the dollar figure (`ULTIMATE_PRD.md` §4.2 guard G-T3).

    Raises:
        InsufficientDataError: if no shares-outstanding fact, or no matching `price_bars` row(s),
            is found.
    """
    shares_row = con.execute(
        "SELECT value FROM fundamentals_facts WHERE cik = ? AND taxonomy = 'dei' "
        "AND tag = 'EntityCommonStockSharesOutstanding' AND unit = 'shares' AND filed <= ? "
        "ORDER BY filed DESC, period_end DESC LIMIT 1",
        [cik, as_of_date],
    ).fetchone()
    if shares_row is None:
        raise InsufficientDataError(
            f"CIK {cik}: no dei:EntityCommonStockSharesOutstanding fact filed <= {as_of_date}"
        )
    shares = float(shares_row[0])

    if smoothing == RatioDenominatorSmoothing.SPOT:
        price_row = con.execute(
            "SELECT raw_close FROM price_bars WHERE ticker = ? AND trade_date <= ? "
            "ORDER BY trade_date DESC LIMIT 1",
            [ticker, as_of_date],
        ).fetchone()
        if price_row is None:
            raise InsufficientDataError(f"{ticker}: no price_bars row on or before {as_of_date}")
        price = float(price_row[0])
    else:
        window_start = as_of_date - timedelta(days=365)
        price_rows = con.execute(
            "SELECT raw_close FROM price_bars WHERE ticker = ? AND trade_date > ? "
            "AND trade_date <= ?",
            [ticker, window_start, as_of_date],
        ).fetchall()
        if not price_rows:
            raise InsufficientDataError(
                f"{ticker}: no price_bars rows in the trailing 12 months of {as_of_date}"
            )
        price = sum(float(row[0]) for row in price_rows) / len(price_rows)

    return shares * price


def _resolve_denominator(
    cik: str,
    ticker: str,
    as_of_date: _Date,
    *,
    con: duckdb.DuckDBPyConnection,
    fiqh_params: FiqhParams,
) -> float:
    """Dispatch to the total-assets or market-cap denominator resolution per
    `fiqh_params.ratio_denominator_basis.value`, read fresh on every call (§7 guard G-S5) — never a
    module-level cached basis/smoothing constant.
    """
    smoothing = fiqh_params.ratio_denominator_smoothing.value
    if fiqh_params.ratio_denominator_basis.value == RatioDenominatorBasis.TOTAL_ASSETS:
        return _resolve_total_assets_denominator(cik, as_of_date, con=con, smoothing=smoothing)
    return _resolve_market_cap_denominator(cik, ticker, as_of_date, con=con, smoothing=smoothing)


def _resolve_tag_set_sum(
    cik: str, tags: frozenset[str], as_of_date: _Date, *, con: duckdb.DuckDBPyConnection
) -> tuple[float, bool]:
    """Sum the most-recently-filed (`filed <= as_of_date`) value per distinct tag in `tags` (§6b):
    for each tag, at most one row contributes (the single most-recently-filed one for THAT tag); a
    tag with zero matching rows contributes `0.0`. Returns `(total, any_row_found)` —
    `any_row_found` is `False` iff EVERY tag in `tags` had zero matching rows, letting the caller
    distinguish "every tag genuinely reported 0.0" from "no data exists under any of these tags at
    all" (the latter is an `InsufficientDataError` when `tags` is `TOTAL_REVENUE_TAGS`, §4.2).
    """
    total = 0.0
    any_found = False
    for tag in sorted(tags):
        row = con.execute(
            "SELECT value FROM fundamentals_facts WHERE cik = ? AND taxonomy = 'us-gaap' "
            "AND tag = ? AND unit = 'USD' AND filed <= ? "
            "ORDER BY filed DESC, period_end DESC LIMIT 1",
            [cik, tag, as_of_date],
        ).fetchone()
        if row is not None:
            total += float(row[0])
            any_found = True
    return total, any_found


def screen(
    ticker: str,
    as_of_date: _Date,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None = None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ResultEnvelope:
    """THE canonical, singular screening entry point (`MASTER_PRD.md` §11 item 2, `ULTIMATE_PRD.md`
    §2.2) and the ONLY function in `mizan/` whose own body (including its private helpers above, all
    reachable only from here) may treat "most-recently-filed fact with `filed <= as_of_date`" as
    sufficient point-in-time resolution, PER CONCEPT, without additionally pinning every
    numerator/denominator to one single governing filing/accession number — the precise, checkable
    content of the Fork-1 simplification (§6d), stamped on every result as `Caveat.LOOK_AHEAD_BIAS`.
    `classify_business_activity` and `compute_financial_ratio_screen` (and everything in
    `financial_ratios.py`/`business_activity.py`) receive already-resolved plain values and NEVER
    reference `filed` themselves.

    `overrides` defaults to `None`, resolved here to `BusinessActivityOverrideMap(overrides={})` —
    the honest empty default (§3.2) — without constructing a module-level shared instance as the
    literal default expression (`ruff`'s B008 forbids a function call in an argument default; the
    `None`-sentinel resolved in the body is behaviourally identical for every caller, since the
    map is `frozen=True` and comparing empty to empty is never observable).

    Fail-fast ordering (§6c, §6e): resolves `cik` (`resolve_cik_offline`, reused from Phase 3) and
    `sic` (`resolve_sic_offline`, §4.1) from the cache ONLY — no DuckDB touch yet — then runs
    `classify_business_activity`. If Layer 1 fails: returns immediately with a single-entry reason
    trace and `Verdict.NON_COMPLIANT`, WITHOUT ever opening a query against `fundamentals_facts`/
    `price_bars` — a Layer-1-failing ticker need never even have been normalized (§8 AC2). If
    Layer 1 passes: confirms the ticker was normalized at all (`NotNormalizedError` otherwise),
    resolves the two-axis denominator and every ratio numerator from `con` (§6b, §6d), raising
    `InsufficientDataError` on a missing REQUIRED denominator-side figure, then runs
    `compute_financial_ratio_screen` and combines both layers via §6c's taxonomy.

    Returns a `ResultEnvelope` per §3.4 — `payload` is `ScreeningVerdict.model_dump()`,
    `active_caveats` is always `(Caveat.LOOK_AHEAD_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION)`.
    `Caveat.SURVIVORSHIP_BIAS` is deliberately never stamped here — it is a universe-selection
    concern (Phase 5), not something one `screen(ticker, as_of_date)` call can assert about itself.

    Local imports, not module-level: see this module's own docstring "Import-order note" — breaks
    the two-way `ReasonTraceEntry`/`ScreenName` dependency between this module and its two siblings.
    """
    from mizan.screening.business_activity import (
        BusinessActivityOverrideMap,
        classify_business_activity,
        resolve_sic_offline,
    )
    from mizan.screening.financial_ratios import (
        INTEREST_BEARING_DEBT_TAGS,
        INTEREST_BEARING_INVESTMENT_TAGS,
        NON_PERMISSIBLE_INCOME_TAGS,
        TOTAL_REVENUE_TAGS,
        compute_financial_ratio_screen,
    )

    resolved_overrides = (
        overrides if overrides is not None else BusinessActivityOverrideMap(overrides={})
    )

    cik = resolve_cik_offline(ticker, cache_dir=cache_dir)
    sic = resolve_sic_offline(cik, cache_dir=cache_dir)
    business_activity_result = classify_business_activity(
        cik, sic, overrides=resolved_overrides, fiqh_params=fiqh_params
    )

    active_caveats = (Caveat.LOOK_AHEAD_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION)

    if not business_activity_result.passed:
        screening_verdict = ScreeningVerdict(
            ticker=ticker,
            cik=cik,
            as_of_date=as_of_date,
            verdict=Verdict.NON_COMPLIANT,
            reason_trace=(business_activity_result.reason,),
        )
        return ResultEnvelope(active_caveats=active_caveats, payload=screening_verdict.model_dump())

    _ensure_normalized(cik, ticker, con=con)

    denominator = _resolve_denominator(cik, ticker, as_of_date, con=con, fiqh_params=fiqh_params)
    interest_bearing_debt, _ = _resolve_tag_set_sum(
        cik, INTEREST_BEARING_DEBT_TAGS, as_of_date, con=con
    )
    interest_bearing_investments, _ = _resolve_tag_set_sum(
        cik, INTEREST_BEARING_INVESTMENT_TAGS, as_of_date, con=con
    )
    non_permissible_income, _ = _resolve_tag_set_sum(
        cik, NON_PERMISSIBLE_INCOME_TAGS, as_of_date, con=con
    )
    total_revenue, total_revenue_found = _resolve_tag_set_sum(
        cik, TOTAL_REVENUE_TAGS, as_of_date, con=con
    )
    if not total_revenue_found:
        raise InsufficientDataError(
            f"CIK {cik}: no total-revenue fact (any of {sorted(TOTAL_REVENUE_TAGS)}) "
            f"filed <= {as_of_date}"
        )

    ratio_result = compute_financial_ratio_screen(
        interest_bearing_debt=interest_bearing_debt,
        interest_bearing_investments=interest_bearing_investments,
        non_permissible_income=non_permissible_income,
        total_revenue=total_revenue,
        denominator=denominator,
        fiqh_params=fiqh_params,
    )
    reason_trace = (
        business_activity_result.reason,
        ratio_result.debt_ratio,
        ratio_result.interest_investments_ratio,
        ratio_result.non_permissible_income_ratio,
    )

    if not ratio_result.passed:
        verdict = Verdict.NON_COMPLIANT
    elif (
        ratio_result.debt_ratio.actual_value == 0.0
        and ratio_result.interest_investments_ratio.actual_value == 0.0
        and ratio_result.non_permissible_income_ratio.actual_value == 0.0
    ):
        verdict = Verdict.PURE
    else:
        verdict = Verdict.MIXED

    screening_verdict = ScreeningVerdict(
        ticker=ticker, cik=cik, as_of_date=as_of_date, verdict=verdict, reason_trace=reason_trace
    )
    return ResultEnvelope(active_caveats=active_caveats, payload=screening_verdict.model_dump())
