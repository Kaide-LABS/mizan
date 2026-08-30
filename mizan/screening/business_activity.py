"""mizan/screening/business_activity.py — SIC-code first-pass business-activity classifier plus a
pluggable, hand-fillable activity-override map.

Implements PHASE_4_SPEC.md §3.2, §4.1, §6a.

**Scoping decision this module implements, verbatim from PHASE_4_SPEC.md's own Provenance header:**
the real ~100-ticker curated universe and its hand-verified business-activity map
(`MASTER_PRD.md` §6.1) do NOT exist in this repository and are explicitly out of scope for this
phase (PHASE_4_SPEC.md §9's first, most prominent non-goal). This module ships a fully generic,
configurable MECHANISM instead: `SIC_TIER_MAP` (a small, closed, publicly-sourced engineering
constant — the same *kind* of thing as `mizan.data.normalize.RECOGNIZED_XBRL_UNITS`, not per-ticker
research) plus `BusinessActivityOverrideMap` (a pluggable map that ships empty and takes precedence
over the SIC first-pass in both directions). No file in this module contains, or ever may contain, a
large-scale "hand-verified" ticker classification presented as real research.

**Offline-only SIC resolution, and why this module (not Phase 3's `normalize.py`) reads it:**
`fundamentals_facts`/`price_bars` are the only two Phase 3 tables and neither carries a SIC column
(`ULTIMATE_PRD.md` §2's System Map: SIC lives only in `https://data.sec.gov/submissions/…`, cached
by Phase 2 as `edgar/submissions/{cik}.json`). Reading it here, directly from that already-cached
raw file, applies the exact same offline-only pattern `mizan.data.normalize.resolve_cik_offline`
already established for `company_tickers.json` — not a re-reading of Phase 3's scope, since Phase 3
never touched this file at all (PHASE_4_SPEC.md §1).

**The override-map JSON format, in full, for a future human author with no other document:**

    {
      "overrides": {
        "0000320193": {
          "cik": "0000320193",
          "ticker": "AAPL",
          "tier_override": null,
          "rationale": "Diversified consumer electronics; SIC first-pass over-broad, researched 10-K
                        business-segment note confirms no interest-bearing-deposit core business."
        },
        "0000019617": {
          "cik": "0000019617",
          "ticker": "JPM",
          "tier_override": "tier_0",
          "rationale": "Commercial bank holding company; core business is interest-based lending."
        }
      }
    }

Keying and field rules, exhaustively:

* The map is keyed by **zero-padded 10-digit CIK**
  (`overrides.overrides: dict[str, ActivityOverride]`), matching every other Phase 2/3 CIK key in
  this codebase — NEVER by ticker. A ticker can change (merger, rename); a CIK does not.
  `ActivityOverride.ticker` is carried alongside purely for a human reader's audit cross-check;
  `classify_business_activity` (§4.1 below) never looks it up by ticker.
* `tier_override: null` (Python `None`) is a MEANINGFUL, deliberate value distinct from the key
  being absent entirely: it means "this CIK was researched and found compliant on business activity
  DESPITE what the generic SIC first-pass alone would suggest" (a false positive the SIC pass would
  have wrongly failed). A key simply not present in `overrides` means "no research has been
  supplied for this CIK yet — fall back to the generic SIC first-pass," which is a different thing
  from an explicit `null`.
* `tier_override: "tier_0"` / `"tier_0_5"` / `"tier_1"` (any `BusinessActivityTier` value) means
  "this CIK was researched and found NON-COMPLIANT at that tier, REGARDLESS of what its SIC code
  alone would suggest" (a false negative the SIC pass would have wrongly passed).
* `rationale` is MANDATORY and must be non-empty (`Field(min_length=1)`) — a bare tier label with no
  stated reason is exactly the silent-judgment-call failure mode this project's honesty surface
  exists to prevent (`MASTER_PRD.md` §0). A real hand-verified map's whole value IS its stated
  reasoning, not just its conclusion; `classify_business_activity`'s reason trace surfaces this
  string verbatim so a human reviewer always sees it, not just the pass/fail conclusion.

An override, once present for a CIK, wins OUTRIGHT over `SIC_TIER_MAP` in both directions — it can
either rescue a SIC-first-pass false positive or flag a SIC-first-pass false negative (§4.1, §7
guard G-S3). Loading is via `load_override_map(path)` (§4.1): `path=None` returns the honest empty
default with no file read at all; a malformed file raises `pydantic.ValidationError` — never
partially loaded, never silently ignored.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import Field

from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.core.base import MizanBaseModel
from mizan.data.raw_cache import cache_path, is_cached, read_raw_json
from mizan.screening.verdict import ReasonTraceEntry, ScreenName

if TYPE_CHECKING:
    from pathlib import Path

# ── §3.2 Schemas ─────────────────────────────────────────────────────────────────────────────────


class BusinessActivityTier(StrEnum):
    """`MASTER_PRD.md` §6.1's three tiers. Values are the tier NAME, not a numeric level — never
    compare these with `<`/`>`: there is no ordering, and Tier 0.5 is not "between" 0 and 1 in a
    numeric sense — it is a distinct, AAOIFI-catch-all-derived category (`MASTER_PRD.md` §6.1's own
    table)."""

    TIER_0 = "tier_0"
    TIER_0_5 = "tier_0_5"
    TIER_1 = "tier_1"


class ClassificationSource(StrEnum):
    """Where a `BusinessActivityScreenResult`'s tier match (or non-match) came from — surfaced in
    the reason trace so a reviewer can immediately tell "the SIC first-pass caught this" apart from
    "a human-supplied override caught this." Makes the override mechanism's precedence over SIC
    TESTABLE, not merely present."""

    SIC_FIRST_PASS = "sic_first_pass"
    OVERRIDE_MAP = "override_map"


class ActivityOverride(MizanBaseModel):
    """One entry of the pluggable override map — the shape the owner's real, hand-verified ~100-
    ticker activity map (`MASTER_PRD.md` §6.1, explicitly out of scope for this build, §9) will
    eventually be supplied through. See this module's own top-of-file docstring for the full JSON
    format, keying convention, and the `tier_override: null`-vs-absent-key distinction.
    """

    cik: str
    """Zero-padded 10-digit CIK, matching `fundamentals_facts.cik` and every other Phase 3 key."""
    ticker: str
    """For human readability / audit cross-check only — lookup keys on `cik`, never `ticker`."""
    tier_override: BusinessActivityTier | None
    rationale: str = Field(min_length=1)


class BusinessActivityOverrideMap(MizanBaseModel):
    """The full pluggable override map, keyed by zero-padded CIK. Ships, by default, EMPTY —
    `BusinessActivityOverrideMap(overrides={})` — meaning "no per-ticker research has been supplied
    yet; fall back to the generic SIC first-pass for everything." An empty map is not a placeholder
    bug; it is the correct, honest default for a map the owner has not yet populated.
    `load_override_map` (§4.1) is how an operator supplies a populated one later, with no code
    change to this module.
    """

    overrides: dict[str, ActivityOverride]


class BusinessActivityScreenResult(MizanBaseModel):
    """The Layer-1 (business-activity) screen's full result for one CIK/SIC pair."""

    passed: bool
    failed_tier: BusinessActivityTier | None
    source: ClassificationSource
    matched_sic: str
    reason: ReasonTraceEntry


class SicResolutionError(RuntimeError):
    """Raised when `resolve_sic_offline` cannot find a cached submissions record for `cik`, or the
    cached record has no usable `sic` key — mirrors `mizan.data.ingest_edgar.MissingSicError`'s
    rationale (`ULTIMATE_PRD.md` §4.1: "a ticker with fundamentals but no SIC must be `unanalyzed`")
    applied to the offline read path, exactly as `mizan.data.normalize.resolve_cik_offline` mirrors
    `CikResolutionError` for the analogous `company_tickers.json` lookup."""


# ── §4.1 SIC_TIER_MAP ────────────────────────────────────────────────────────────────────────────

#: The SIC-code first-pass table: a CLOSED, GENERIC, publicly-sourced mapping from 4-digit SIC codes
#: to `BusinessActivityTier`, grounded in `MASTER_PRD.md` §6.1's tier definitions. This is
#: emphatically NOT the owner's curated ~100-ticker hand-verified activity map (§9 of the spec) — it
#: is the same *kind* of thing `mizan.data.normalize.RECOGNIZED_XBRL_UNITS` is: a small, closed,
#: reviewable constant, not per-ticker research.
#:
#: Every code below was verified LIVE on 2026-08-30 against two independent SEC sources and logged
#: in `docs/modernization_log.md` §6.3: (a) SEC's own published SIC code list
#: (https://www.sec.gov/corpfin/division-of-corporation-finance-standard-industrial-classification-
#: sic-code-list) confirms each code is an actually-ASSIGNED SIC code (not merely a plausible number
#: inside a range — SIC code ranges are non-contiguous; most 4-digit numbers inside a named "range"
#: are unassigned); (b) `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&SIC={code}`
#: confirms each code has at least one real EDGAR-registered filer under it (an assigned-but-never-
#: used code would be a dead entry). One PHASE_4_SPEC.md §4.1 illustrative example did NOT survive
#: this verification and is deliberately OMITTED — see the note below the map.
SIC_TIER_MAP: dict[str, BusinessActivityTier] = {
    # ── Tier 0 (MASTER_PRD.md §6.1; always fails, never gated by a fiqh_params toggle) ──────────
    # 2000-2013: meat/food (non-halal-food-adjacent; SEC's assigned codes in this band)
    "2000": BusinessActivityTier.TIER_0,  # FOOD AND KINDRED PRODUCTS
    "2011": BusinessActivityTier.TIER_0,  # MEAT PACKING PLANTS
    "2013": BusinessActivityTier.TIER_0,  # SAUSAGES & OTHER PREPARED MEAT PRODUCTS
    # 2080-2085: beverages (alcohol)
    "2080": BusinessActivityTier.TIER_0,  # BEVERAGES
    "2082": BusinessActivityTier.TIER_0,  # MALT BEVERAGES
    # 2100-2199: tobacco
    "2100": BusinessActivityTier.TIER_0,  # TOBACCO PRODUCTS
    "2111": BusinessActivityTier.TIER_0,  # CIGARETTES
    # 6020-6036: commercial/savings banks
    "6021": BusinessActivityTier.TIER_0,  # NATIONAL COMMERCIAL BANKS
    "6022": BusinessActivityTier.TIER_0,  # STATE COMMERCIAL BANKS
    "6029": BusinessActivityTier.TIER_0,  # COMMERCIAL BANKS, NEC
    "6035": BusinessActivityTier.TIER_0,  # SAVINGS INSTITUTION, FEDERALLY CHARTERED
    "6036": BusinessActivityTier.TIER_0,  # SAVINGS INSTITUTIONS, NOT FEDERALLY CHARTERED
    # 6311-6411: insurance
    "6311": BusinessActivityTier.TIER_0,  # LIFE INSURANCE
    "6321": BusinessActivityTier.TIER_0,  # ACCIDENT & HEALTH INSURANCE
    "6324": BusinessActivityTier.TIER_0,  # HOSPITAL & MEDICAL SERVICE PLANS
    "6331": BusinessActivityTier.TIER_0,  # FIRE, MARINE & CASUALTY INSURANCE
    "6351": BusinessActivityTier.TIER_0,  # SURETY INSURANCE
    "6361": BusinessActivityTier.TIER_0,  # TITLE INSURANCE
    "6399": BusinessActivityTier.TIER_0,  # INSURANCE CARRIERS, NEC
    "6411": BusinessActivityTier.TIER_0,  # INSURANCE AGENTS, BROKERS & SERVICE
    # NOTE — PHASE_4_SPEC.md §4.1's illustrative "7993 (gambling)" entry is NOT included: verified
    # live 2026-08-30 that SIC 7993 is not an assigned SEC SIC code at all (absent from SEC's own
    # published code list; a live EDGAR company-search for SIC=7993 returns zero filers). Real
    # gambling/casino issuers (verified live against Wynn Resorts LTD, CIK 0001174922, and Caesars
    # Entertainment, Inc., CIK 0001590895) file under SIC 7011 (Hotels & Motels) instead — which
    # this map already carries under Tier 1 below. This is a known, documented granularity
    # limitation of a generic SIC-code first-pass (a real gambling-core-business issuer filed under
    # 7011 is only caught when `business_activity_tier_1_enabled` is on, or via a hand-researched
    # override — not via a dedicated Tier-0 gambling code, because SEC's own taxonomy does not carry
    # one). Logged in `docs/modernization_log.md` §6.3; inventing a substitute code that was itself
    # never verified would have been exactly the "fabricated-precision" failure mode this project's
    # honesty discipline forbids.
    # ── Tier 0.5 (MASTER_PRD.md §6.1; fails only if business_activity_tier_0_5_enabled) ─────────
    # 2741/2750-class: publishing/printing (index-provider convention for adult-content publishers)
    "2741": BusinessActivityTier.TIER_0_5,  # MISCELLANEOUS PUBLISHING
    "2750": BusinessActivityTier.TIER_0_5,  # COMMERCIAL PRINTING
    # 3480/3760: ordnance/guided missiles (weapons)
    "3480": BusinessActivityTier.TIER_0_5,  # ORDNANCE & ACCESSORIES, (NO VEHICLES/GUIDED MISSILES)
    "3760": BusinessActivityTier.TIER_0_5,  # GUIDED MISSILES & SPACE VEHICLES & PARTS
    # ── Tier 1 (MASTER_PRD.md §6.1; fails only if business_activity_tier_1_enabled) ──────────────
    # 7812/7822: motion picture
    "7812": BusinessActivityTier.TIER_1,  # SERVICES-MOTION PICTURE & VIDEO TAPE PRODUCTION
    "7822": BusinessActivityTier.TIER_1,  # SERVICES-MOTION PICTURE & VIDEO TAPE DISTRIBUTION
    # 7011: hotels (also, in practice, the SIC real casino/gambling issuers file under — see note
    # above)
    "7011": BusinessActivityTier.TIER_1,  # HOTELS & MOTELS
}


# ── §4.1 Functions ───────────────────────────────────────────────────────────────────────────────


def resolve_sic_offline(cik: str, *, cache_dir: Path) -> str:
    """Read the already-cached `edgar/submissions/{cik}.json` raw file (`PHASE_2_SPEC.md` §6.1's
    `ingest_edgar_submissions` cache key) and return its `sic` field.

    No network parameter exists on this function — zero network capability, structurally (§7 guard
    G-S8, mirroring `PHASE_3_SPEC.md`'s G-N8). Does not reference `filed` at all — SIC has no
    temporal dimension in this cache — so this function is exempt from §6d's `as_of_date`
    discipline for that reason, not by oversight.

    Raises:
        SicResolutionError: if no cached submissions record exists for `cik`, the cached file is not
            a JSON object, or it carries no usable (non-empty string) `sic` key.
    """
    path = cache_path(cache_dir=cache_dir, source="edgar/submissions", key=cik)
    if not is_cached(path):
        raise SicResolutionError(
            f"CIK {cik}: no cached submissions record — run `mizan ingest` first"
        )
    raw = read_raw_json(path)
    if not isinstance(raw, dict):
        raise SicResolutionError(f"CIK {cik}: cached submissions record is not a JSON object")
    sic = raw.get("sic")
    if not isinstance(sic, str) or not sic.strip():
        raise SicResolutionError(f"CIK {cik}: cached submissions record has no usable `sic` key")
    return sic


def load_override_map(path: Path | None) -> BusinessActivityOverrideMap:
    """`path is None` returns `BusinessActivityOverrideMap(overrides={})` — the honest empty
    default (§3.2) — with NO file read at all. A given `path` is read and validated via
    `model_validate_json`, which unifies "the file is not valid JSON at all" and "the JSON is valid
    but fails `extra='forbid'`/type validation" into a single `pydantic.ValidationError` — never
    partially loaded, never silently ignored.
    """
    if path is None:
        return BusinessActivityOverrideMap(overrides={})
    raw_text = path.read_text(encoding="utf-8")
    return BusinessActivityOverrideMap.model_validate_json(raw_text)


def classify_business_activity(
    cik: str,
    sic: str,
    *,
    overrides: BusinessActivityOverrideMap,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> BusinessActivityScreenResult:
    """Pure function — no DB, no cache, no dates, no network. Precedence (§7, §8 tested both
    directions):

    1. If `cik` is a key in `overrides.overrides`: the override WINS outright, regardless of what
       SIC alone would say. `tier_override=None` means "researched, compliant despite SIC" (passed
       `True`); a set tier means "researched, non-compliant at that tier" (passed `False`,
       `source=OVERRIDE_MAP`).
    2. Otherwise, look up `sic` in `SIC_TIER_MAP`. A Tier 0 match always fails. A Tier 0.5 match
       fails ONLY if `fiqh_params.business_activity_tier_0_5_enabled.value is True` (default
       `True`); a Tier 1 match fails ONLY if `fiqh_params.business_activity_tier_1_enabled.value is
       True` (default `False`) — read from `fiqh_params` on every call, never a module-level cached
       bool (§7 guard G-S4, `MASTER_PRD.md` §6.1/§10 register #6/#7). No SIC match, or a
       disabled-tier match, passes.
    3. Either way, `source` on the result names which branch fired, and `reason.detail` names the
       matched SIC/tier or the override's own `rationale` string verbatim, so a human reviewer sees
       a real-map entry's stated reasoning in the output, not just its conclusion.
    """
    override = overrides.overrides.get(cik)
    if override is not None:
        passed = override.tier_override is None
        tier_label = (
            "no tier (override rescues)"
            if override.tier_override is None
            else override.tier_override.value
        )
        reason = ReasonTraceEntry(
            screen=ScreenName.BUSINESS_ACTIVITY,
            passed=passed,
            threshold=None,
            actual_value=None,
            margin=None,
            detail=f"override map: CIK {cik} -> {tier_label} — {override.rationale}",
        )
        return BusinessActivityScreenResult(
            passed=passed,
            failed_tier=override.tier_override,
            source=ClassificationSource.OVERRIDE_MAP,
            matched_sic=sic,
            reason=reason,
        )

    matched_tier = SIC_TIER_MAP.get(sic)
    failed_tier: BusinessActivityTier | None
    if matched_tier is None:
        passed = True
        failed_tier = None
        detail = f"SIC {sic!r} not in SIC_TIER_MAP — no tier match, passes by default"
    elif matched_tier is BusinessActivityTier.TIER_0:
        passed = False
        failed_tier = matched_tier
        detail = f"SIC {sic!r} matched Tier 0 — always fails, not gated by any fiqh_params toggle"
    elif matched_tier is BusinessActivityTier.TIER_0_5:
        enabled = fiqh_params.business_activity_tier_0_5_enabled.value
        passed = not enabled
        failed_tier = matched_tier if enabled else None
        detail = f"SIC {sic!r} matched Tier 0.5 (business_activity_tier_0_5_enabled={enabled})"
    else:  # BusinessActivityTier.TIER_1
        enabled = fiqh_params.business_activity_tier_1_enabled.value
        passed = not enabled
        failed_tier = matched_tier if enabled else None
        detail = f"SIC {sic!r} matched Tier 1 (business_activity_tier_1_enabled={enabled})"

    reason = ReasonTraceEntry(
        screen=ScreenName.BUSINESS_ACTIVITY,
        passed=passed,
        threshold=None,
        actual_value=None,
        margin=None,
        detail=detail,
    )
    return BusinessActivityScreenResult(
        passed=passed,
        failed_tier=failed_tier,
        source=ClassificationSource.SIC_FIRST_PASS,
        matched_sic=sic,
        reason=reason,
    )
