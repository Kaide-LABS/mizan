"""The fiqh judgment-call register — the honesty surface (11 rows).

Implements PHASE_1_SPEC.md §3.3.

This module is the reason the project exists (MASTER_PRD.md §0). Its correctness bar is higher
than the rest of Phase 1: a source string that overstates what the primary source actually says is
the honesty surface lying, and is categorised HALT-for-human in ULTIMATE_PRD.md §4.4.
"""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import Field, model_validator

from mizan.core.base import MizanBaseModel

# ── §3.3.1 Supporting enums ─────────────────────────────────────────────────────────────────────


class VerificationStatus(StrEnum):
    """Verification state of a fiqh judgment call."""

    PENDING_SCHOLARLY_VERIFICATION = "pending_scholarly_verification"
    # No other member is defined in Phase 1. A future member (e.g. SCHOLAR_RATIFIED) may only be
    # added once an actual scholarly ruling exists — never speculatively.


class RatioDenominatorBasis(StrEnum):
    """Fork/register #1: the asset base a financial-ratio screen divides by."""

    MARKET_CAP = "market_cap"  # AAOIFI-faithful default (INFERRED — see register #1 source)
    TOTAL_ASSETS = "total_assets"  # MSCI/FTSE-style alternative


class RatioDenominatorSmoothing(StrEnum):
    """Register #2: whether the ratio denominator is a spot value or time-smoothed."""

    SPOT = "spot"  # AAOIFI-faithful default (INFERRED — see register #2 source)
    AVERAGED = "averaged"  # index-provider style (DJ/S&P use a 12-month average)


class DivestmentAttributionMethod(StrEnum):
    """Fork C. Only the V1 default is defined.

    ULTIMATE_PRD.md §3.2 and the Step 10 literature sweep found NO settled formula and NO proposed
    alternative in the 2024-2026 literature. Defining a speculative second member here would
    manufacture a false menu of options. Adding a member requires a phase-spec revision.
    """

    TIME_BOUNDED_PRICE_APPRECIATION = "time_bounded_price_appreciation"


class PurificationAccountingMethod(StrEnum):
    """Fork B. Only the side-ledger is defined.

    ULTIMATE_PRD.md §3.2 quotes the primary source verbatim: non-halal income "will have to be
    donated to Charity and cannot be included in the investors P&L accounts." A netted-into-NAV
    member would be a member that violates the primary source, so it is not defined. The entry
    stays in the register (it is a fiqh judgment call, not a permissibility invariant) but there is
    nothing to configure it TO without a phase-spec revision.
    """

    SIDE_LEDGER = "side_ledger"


# ── §3.3.2 FiqhParam[T] — a GENERIC model, not a union ─────────────────────────────────────────

T = TypeVar("T")


class FiqhParam(MizanBaseModel, Generic[T]):
    """One row of the judgment-call register (MASTER_PRD.md §10).

    Generic, deliberately. The pre-modernization spec typed ``value`` as ``bool | float | str``.
    Pydantic's default union mode is ``smart`` and its docs state the algorithm "may change between
    Pydantic minor releases"; the docs do not specify bool-vs-int resolution (``bool`` is an ``int``
    subclass). Putting an explicitly-unspecified, minor-release-mutable resolution rule underneath
    the one module whose entire purpose is that nothing is silently decided is the wrong
    dependency. A generic parameter removes the union entirely.
    (ULTIMATE_PRD.md §3.4; https://pydantic.dev/docs/validation/latest/concepts/unions/ ·
     https://pydantic.dev/docs/validation/latest/concepts/models/)
    """

    register_id: int = Field(ge=1, le=11)
    """Row number in MASTER_PRD.md §10. Makes the 1:1 register mapping machine-checkable, which is
    exactly what baby_prd.md acceptance criterion #2 requires a third party to be able to
    confirm."""

    value: T

    source: str = Field(min_length=1)
    """Human-readable citation for the DEFAULT. Must never imply more settledness than the primary
    source supports."""

    primary_source_gap: str = ""
    """What the primary source does NOT settle about this entry. Non-empty and specific for entries
    #1, #2 and #5 (ULTIMATE_PRD.md §3.1(d) and Q1/Q2); empty string where the primary source is
    clear. This field exists because 'pending scholarly verification' alone does not distinguish
    'the standard says X and a scholar should confirm our reading of X' from 'the standard does not
    say anything and we inferred X'."""

    status: VerificationStatus = VerificationStatus.PENDING_SCHOLARLY_VERIFICATION

    configurable: bool = True
    """True for every register entry (MASTER_PRD.md §0: every judgment call is configurable).
    Means 'this is a fiqh judgment call, not a permissibility invariant' — it does NOT assert that
    more than one option is currently implemented (see DivestmentAttributionMethod,
    PurificationAccountingMethod)."""


# Field defaults that are ``FiqhParam`` instances (below) are shared across all ``FiqhParams``
# instances. That is safe and intended here precisely because ``MizanBaseModel`` is ``frozen=True``.
# Do not "fix" this with ``default_factory`` — it would create per-instance copies of immutable
# objects for no benefit and would obscure that these are single canonical values.


class FiqhParams(MizanBaseModel):
    """The full judgment-call register. Every field maps 1:1 to a row of MASTER_PRD.md §10."""

    # ── #1 ────────────────────────────────────────────────────────────────────────────────────
    ratio_denominator_basis: FiqhParam[RatioDenominatorBasis] = FiqhParam[RatioDenominatorBasis](
        register_id=1,
        value=RatioDenominatorBasis.MARKET_CAP,
        source=(
            "AAOIFI SS21 public methodology (Merah, Oct 2017). Market-cap is the conventional "
            "reading; the MSCI/FTSE-style alternative is total assets."
        ),
        primary_source_gap=(
            "UNVERIFIED: AAOIFI's own denominator basis is NOT stated anywhere in the public "
            "methodology. The Merah presentation states the OTHER standards' denominators "
            "explicitly (slide 31: DJ = trailing 12-month moving average market cap; FTSE = total "
            "assets; S&P = market value of equity) but never AAOIFI's. market_cap is an INFERENCE. "
            "See ULTIMATE_PRD.md §3.1(d) and OPEN ARCHITECTURE QUESTIONS Q1."
        ),
    )

    # ── #2 ────────────────────────────────────────────────────────────────────────────────────
    ratio_denominator_smoothing: FiqhParam[RatioDenominatorSmoothing] = FiqhParam[
        RatioDenominatorSmoothing
    ](
        register_id=2,
        value=RatioDenominatorSmoothing.SPOT,
        source=(
            "Spot (unsmoothed) is the conventional AAOIFI-faithful reading; index providers "
            "bolt on 12/24/36-month smoothing."
        ),
        primary_source_gap=(
            "UNVERIFIED: AAOIFI's averaging window (or its absence) is NOT stated in the "
            "public methodology. The previously-asserted SS21 fragment 'the last budget or "
            "verified financial position' could not be verified against any reachable source. "
            "spot is an INFERENCE. See ULTIMATE_PRD.md §3.1(d) and Q1."
        ),
    )

    # ── #3 ────────────────────────────────────────────────────────────────────────────────────
    debt_ratio_threshold: FiqhParam[float] = FiqhParam[float](
        register_id=3,
        value=0.30,
        source=(
            "AAOIFI SS21, verified verbatim in the Merah presentation slides 32-34: AAOIFI 30% "
            "vs DJ/FTSE/S&P 33%."
        ),
    )

    # ── #4 ────────────────────────────────────────────────────────────────────────────────────
    interest_investments_threshold: FiqhParam[float] = FiqhParam[float](
        register_id=4,
        value=0.30,
        source="AAOIFI SS21, verified verbatim in the Merah presentation slides 33-34 (30%).",
    )

    # ── #5 ────────────────────────────────────────────────────────────────────────────────────
    non_permissible_income_threshold: FiqhParam[float] = FiqhParam[float](
        register_id=5,
        value=0.05,
        source=(
            "AAOIFI SS21, verified verbatim (Merah slide 32): 'Non Halal Income Should not Exceed "
            "5% of Total Income'."
        ),
        primary_source_gap=(
            "DENOMINATOR AMBIGUITY: the primary source says 'Total Income'; MASTER_PRD.md §6.2 "
            "item 3 says 'total revenue'. Under US GAAP these are different line items, and the "
            "gap is material precisely for firms near the 5% boundary. Phase 4 must pick one "
            "explicitly and cite this gap. See ULTIMATE_PRD.md OPEN ARCHITECTURE QUESTIONS Q2 — "
            "the human may promote this into a 12th register entry, which would move "
            "MASTER_PRD.md §10, baby_prd.md AC #2 and this spec together."
        ),
    )

    # ── #6 ────────────────────────────────────────────────────────────────────────────────────
    business_activity_tier_0_5_enabled: FiqhParam[bool] = FiqhParam[bool](
        register_id=6,
        value=True,
        source=(
            "Tier 0.5 = adult content, weapons/defence. Reaches AAOIFI only via enumerated item 8, "
            "'Any activities deemed unlawful'. Default ON."
        ),
        primary_source_gap=(
            "Verified NOT AAOIFI-enumerated: the Merah presentation's AAOIFI industry list (slide "
            "18) is exactly 8 items and contains neither adult content nor weapons/defence; both "
            "appear only in the index-provider comparison column (slide 31). Keeping this "
            "configurable rather than hardcoded is the primary-source-faithful choice."
        ),
    )

    # ── #7 ────────────────────────────────────────────────────────────────────────────────────
    business_activity_tier_1_enabled: FiqhParam[bool] = FiqhParam[bool](
        register_id=7,
        value=False,
        source=(
            "Tier 1 = media/music/entertainment, hotels. Genuinely contested across scholarly "
            "bodies. Default OFF."
        ),
        primary_source_gap=(
            "Not AAOIFI-enumerated (Merah slide 18); 'Entertainment' appears only in the "
            "index-provider comparison column (slide 31)."
        ),
    )

    # ── #8 ────────────────────────────────────────────────────────────────────────────────────
    grace_period_rebalances: FiqhParam[int] = FiqhParam[int](
        register_id=8,
        value=1,
        source=(
            "Common Islamic-fund practice: divest at the next rebalance after a compliance flip. "
            "Unit is WHOLE REBALANCE PERIODS, not days."
        ),
        primary_source_gap=(
            "No AAOIFI-stated grace period found in the public methodology. This tunes divestment "
            "timing WITHIN the quarterly cadence; it is not a licence to change the cadence "
            "itself (ULTIMATE_PRD.md §1.1)."
        ),
    )

    # ── #9 ────────────────────────────────────────────────────────────────────────────────────
    purify_capital_gains: FiqhParam[bool] = FiqhParam[bool](
        register_id=9,
        value=False,
        source="Fork A: dividends-only for V1; capital-gains purification default OFF.",
        primary_source_gap=(
            "The primary source establishes THAT non-halal income must be purified (Merah slides "
            "24-25) but gives no formula for capital gains. Genuinely underdetermined."
        ),
    )

    # ── #10 ───────────────────────────────────────────────────────────────────────────────────
    divestment_attribution_method: FiqhParam[DivestmentAttributionMethod] = FiqhParam[
        DivestmentAttributionMethod
    ](
        register_id=10,
        value=DivestmentAttributionMethod.TIME_BOUNDED_PRICE_APPRECIATION,
        source="Fork C: price appreciation over the flip-date to divestment-date window.",
        primary_source_gap=(
            "No settled formula exists. The Step 10 literature sweep (2024-2026) found no "
            "proposed alternative either — an explicit null result, not an unsearched gap. "
            "See ULTIMATE_PRD.md §3.5."
        ),
    )

    # ── #11 ───────────────────────────────────────────────────────────────────────────────────
    purification_accounting_method: FiqhParam[PurificationAccountingMethod] = FiqhParam[
        PurificationAccountingMethod
    ](
        register_id=11,
        value=PurificationAccountingMethod.SIDE_LEDGER,
        source=(
            "Fork B, now PRIMARY-SOURCE VERBATIM (Merah slide 25): purification means "
            "non-halal income 'will have to be donated to Charity and cannot be included in "
            "the investors P&L accounts'. A side-ledger is the only faithful reading."
        ),
    )

    @model_validator(mode="after")
    def _register_ids_are_exactly_one_to_eleven(self) -> "FiqhParams":
        """The register must cover MASTER_PRD.md §10 rows #1-#11 exactly once each."""
        ids = sorted(getattr(self, name).register_id for name in type(self).model_fields)
        if ids != list(range(1, 12)):
            raise ValueError(
                f"fiqh register_id set must be exactly 1..11 with no duplicates; got {ids}"
            )
        return self


# The single module-level instance every other module imports
# (``from mizan.config.fiqh_params import FIQH_PARAMS``). Exactly 11 fields, matching
# MASTER_PRD.md §10 rows #1-#11 and satisfying baby_prd.md AC #2's requirement that a third party
# can count them and confirm 1:1 coverage. Do not add a 12th entry in Phase 1 (PHASE_1_SPEC.md §9).
FIQH_PARAMS = FiqhParams()
