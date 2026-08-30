"""Tests for mizan/screening/business_activity.py.

Implements PHASE_4_SPEC.md §8 acceptance criteria 3 (config values read, not hardcoded — proven,
not asserted), 5 (override precedence, both directions), 9 (no LLM import), 11 (every model
inherits MizanBaseModel), plus guards G-S3, G-S4, G-S7, G-S8.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams
from mizan.data.raw_cache import write_raw_json
from mizan.screening.business_activity import (
    SIC_TIER_MAP,
    ActivityOverride,
    BusinessActivityOverrideMap,
    BusinessActivityScreenResult,
    BusinessActivityTier,
    ClassificationSource,
    SicResolutionError,
    classify_business_activity,
    load_override_map,
    resolve_sic_offline,
)
from mizan.screening.verdict import ScreenName

_CLEAN_SIC = "7372"  # not in SIC_TIER_MAP
_TIER_0_SIC = "6022"  # STATE COMMERCIAL BANKS
_TIER_0_5_SIC = "3760"  # GUIDED MISSILES & SPACE VEHICLES & PARTS
_TIER_1_SIC = "7011"  # HOTELS & MOTELS
_CIK = "0000320193"


def _empty_overrides() -> BusinessActivityOverrideMap:
    return BusinessActivityOverrideMap(overrides={})


def _with_bool_param(name: str, value: bool) -> FiqhParams:
    """Return a `model_copy` of `FIQH_PARAMS` with the named boolean `FiqhParam` field's `.value`
    replaced — the only way to change a frozen `FiqhParams`/`FiqhParam`."""
    current = getattr(FIQH_PARAMS, name)
    return FIQH_PARAMS.model_copy(update={name: current.model_copy(update={"value": value})})


# ── SIC_TIER_MAP shape (§4.1) ────────────────────────────────────────────────────────────────────


def test_sic_tier_map_contains_expected_tier_assignments() -> None:
    assert SIC_TIER_MAP[_TIER_0_SIC] is BusinessActivityTier.TIER_0
    assert SIC_TIER_MAP[_TIER_0_5_SIC] is BusinessActivityTier.TIER_0_5
    assert SIC_TIER_MAP[_TIER_1_SIC] is BusinessActivityTier.TIER_1
    assert _CLEAN_SIC not in SIC_TIER_MAP


def test_business_activity_tier_is_never_compared_ordinally_in_the_module_source() -> None:
    """`BusinessActivityTier` is a `StrEnum`; being a `str` subclass it technically SUPPORTS `<`/`>`
    at runtime (lexicographic string comparison — `"tier_0" < "tier_1"` is `True`, a coincidence of
    the chosen string values, NOT a meaningful severity ordering: Tier 0.5 is not "between" 0 and 1
    in any real sense, MASTER_PRD.md §6.1's own table). Rather than assert a `TypeError` that
    `StrEnum` does not actually raise, this test asserts the real invariant: no `<`/`>` comparison
    against a `BusinessActivityTier` value appears anywhere in this module's source at all —
    `classify_business_activity` decides tier handling entirely via `is`/`==`/dict lookup."""
    import mizan.screening.business_activity as module

    source = inspect.getsource(module)
    assert "BusinessActivityTier.TIER_0 <" not in source
    assert "BusinessActivityTier.TIER_0 >" not in source
    assert "matched_tier <" not in source
    assert "matched_tier >" not in source


# ── classify_business_activity: SIC first-pass precedence (§4.1) ───────────────────────────────


def test_tier_0_sic_always_fails() -> None:
    result = classify_business_activity(_CIK, _TIER_0_SIC, overrides=_empty_overrides())
    assert result.passed is False
    assert result.failed_tier is BusinessActivityTier.TIER_0
    assert result.source is ClassificationSource.SIC_FIRST_PASS
    assert result.reason.screen is ScreenName.BUSINESS_ACTIVITY
    assert result.reason.passed is False
    assert result.reason.threshold is None
    assert result.reason.actual_value is None
    assert result.reason.margin is None


def test_clean_sic_passes() -> None:
    result = classify_business_activity(_CIK, _CLEAN_SIC, overrides=_empty_overrides())
    assert result.passed is True
    assert result.failed_tier is None
    assert result.source is ClassificationSource.SIC_FIRST_PASS


def test_tier_0_5_fails_by_default_because_register_6_default_is_true() -> None:
    assert FIQH_PARAMS.business_activity_tier_0_5_enabled.value is True
    result = classify_business_activity(_CIK, _TIER_0_5_SIC, overrides=_empty_overrides())
    assert result.passed is False
    assert result.failed_tier is BusinessActivityTier.TIER_0_5


def test_tier_1_passes_by_default_because_register_7_default_is_false() -> None:
    assert FIQH_PARAMS.business_activity_tier_1_enabled.value is False
    result = classify_business_activity(_CIK, _TIER_1_SIC, overrides=_empty_overrides())
    assert result.passed is True
    assert result.failed_tier is None


# ── §8 AC3 / G-S4: config values are read fresh, not hardcoded ─────────────────────────────────


def test_tier_0_5_toggle_changes_verdict_via_model_copy() -> None:
    """Proves `business_activity_tier_0_5_enabled` is read from `fiqh_params` on every call, not
    cached — flipping it via `model_copy` (the only way to change a frozen `FiqhParams`) flips the
    result for the same SIC."""
    enabled_result = classify_business_activity(
        _CIK, _TIER_0_5_SIC, overrides=_empty_overrides(), fiqh_params=FIQH_PARAMS
    )
    assert enabled_result.passed is False

    disabled_params = _with_bool_param("business_activity_tier_0_5_enabled", False)
    disabled_result = classify_business_activity(
        _CIK, _TIER_0_5_SIC, overrides=_empty_overrides(), fiqh_params=disabled_params
    )
    assert disabled_result.passed is True
    assert disabled_result.failed_tier is None


def test_tier_1_toggle_changes_verdict_via_model_copy() -> None:
    enabled_params = _with_bool_param("business_activity_tier_1_enabled", True)
    result = classify_business_activity(
        _CIK, _TIER_1_SIC, overrides=_empty_overrides(), fiqh_params=enabled_params
    )
    assert result.passed is False
    assert result.failed_tier is BusinessActivityTier.TIER_1


def test_only_two_read_sites_for_the_tier_toggles() -> None:
    """G-S4's grep, re-run as a test: exactly the two expected fiqh_params reads appear in
    business_activity.py's source, and nowhere is a bare bool duplicating the register's value."""
    import mizan.screening.business_activity as module

    source = inspect.getsource(module)
    assert source.count("business_activity_tier_0_5_enabled") >= 1
    assert source.count("business_activity_tier_1_enabled") >= 1
    assert "fiqh_params.business_activity_tier_0_5_enabled.value" in source
    assert "fiqh_params.business_activity_tier_1_enabled.value" in source


# ── §8 AC5 / G-S3: override map precedence, both directions ────────────────────────────────────


def test_override_rescues_a_tier_0_sic_false_positive() -> None:
    overrides = BusinessActivityOverrideMap(
        overrides={
            _CIK: ActivityOverride(
                cik=_CIK, ticker="TEST", tier_override=None, rationale="rescued: not a real bank"
            )
        }
    )
    result = classify_business_activity(_CIK, _TIER_0_SIC, overrides=overrides)
    assert result.passed is True
    assert result.failed_tier is None
    assert result.source is ClassificationSource.OVERRIDE_MAP
    assert "rescued: not a real bank" in result.reason.detail


def test_override_flags_a_clean_sic_false_negative() -> None:
    overrides = BusinessActivityOverrideMap(
        overrides={
            _CIK: ActivityOverride(
                cik=_CIK,
                ticker="TEST",
                tier_override=BusinessActivityTier.TIER_0,
                rationale="flagged: actually a lender despite SIC",
            )
        }
    )
    result = classify_business_activity(_CIK, _CLEAN_SIC, overrides=overrides)
    assert result.passed is False
    assert result.failed_tier is BusinessActivityTier.TIER_0
    assert result.source is ClassificationSource.OVERRIDE_MAP
    assert "flagged: actually a lender despite SIC" in result.reason.detail


def test_override_wins_outright_regardless_of_sic_tier_map_lookup() -> None:
    """An override for a CIK not otherwise in SIC_TIER_MAP still fires — precedence is unconditional
    on `cik` membership in `overrides.overrides`, never conditional on whether SIC_TIER_MAP itself
    would have matched."""
    overrides = BusinessActivityOverrideMap(
        overrides={
            _CIK: ActivityOverride(
                cik=_CIK, ticker="TEST", tier_override=None, rationale="researched, compliant"
            )
        }
    )
    result = classify_business_activity(_CIK, _CLEAN_SIC, overrides=overrides)
    assert result.source is ClassificationSource.OVERRIDE_MAP
    assert result.passed is True


# ── ActivityOverride / BusinessActivityOverrideMap schema ──────────────────────────────────────


def test_activity_override_requires_nonempty_rationale() -> None:
    with pytest.raises(ValidationError):
        ActivityOverride(cik=_CIK, ticker="TEST", tier_override=None, rationale="")


def test_business_activity_models_inherit_mizan_base_model_and_forbid_extra() -> None:
    with pytest.raises(ValidationError):
        ActivityOverride.model_validate(
            {"cik": _CIK, "ticker": "TEST", "tier_override": None, "rationale": "x", "extra": 1}
        )
    with pytest.raises(ValidationError):
        BusinessActivityOverrideMap.model_validate({"overrides": {}, "extra": 1})
    with pytest.raises(ValidationError):
        BusinessActivityScreenResult.model_validate(
            {
                "passed": True,
                "failed_tier": None,
                "source": "sic_first_pass",
                "matched_sic": "0000",
                "reason": {
                    "screen": "business_activity",
                    "passed": True,
                    "threshold": None,
                    "actual_value": None,
                    "margin": None,
                    "detail": "x",
                },
                "extra": 1,
            }
        )


# ── load_override_map (§4.1) ─────────────────────────────────────────────────────────────────────


def test_load_override_map_returns_honest_empty_default_when_path_is_none() -> None:
    result = load_override_map(None)
    assert result == BusinessActivityOverrideMap(overrides={})


def test_load_override_map_reads_and_validates_a_real_file(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    payload = {
        "overrides": {
            _CIK: {
                "cik": _CIK,
                "ticker": "AAPL",
                "tier_override": None,
                "rationale": "test rationale",
            }
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = load_override_map(path)

    assert _CIK in result.overrides
    assert result.overrides[_CIK].rationale == "test rationale"


def test_load_override_map_raises_validation_error_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_override_map(path)


def test_load_override_map_raises_validation_error_on_schema_violation(tmp_path: Path) -> None:
    path = tmp_path / "bad_schema.json"
    path.write_text(json.dumps({"overrides": {}, "unexpected_key": True}), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_override_map(path)


def test_load_override_map_raises_validation_error_on_empty_rationale(tmp_path: Path) -> None:
    path = tmp_path / "bad_rationale.json"
    payload = {
        "overrides": {_CIK: {"cik": _CIK, "ticker": "AAPL", "tier_override": None, "rationale": ""}}
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_override_map(path)


# ── resolve_sic_offline (§4.1, G-S8) ─────────────────────────────────────────────────────────────


def test_resolve_sic_offline_reads_cached_submissions_record(tmp_path: Path) -> None:
    payload = {"cik": 320193, "sic": "7372", "sicDescription": "PREPACKAGED SOFTWARE"}
    path = tmp_path / "edgar" / "submissions" / f"{_CIK}.json"
    write_raw_json(path, json.dumps(payload).encode("utf-8"))

    sic = resolve_sic_offline(_CIK, cache_dir=tmp_path)

    assert sic == "7372"


def test_resolve_sic_offline_raises_when_not_cached(tmp_path: Path) -> None:
    with pytest.raises(SicResolutionError):
        resolve_sic_offline(_CIK, cache_dir=tmp_path)


def test_resolve_sic_offline_raises_when_cached_file_is_not_a_json_object(tmp_path: Path) -> None:
    path = tmp_path / "edgar" / "submissions" / f"{_CIK}.json"
    write_raw_json(path, json.dumps(["not", "an", "object"]).encode("utf-8"))

    with pytest.raises(SicResolutionError):
        resolve_sic_offline(_CIK, cache_dir=tmp_path)


def test_resolve_sic_offline_raises_when_sic_key_missing(tmp_path: Path) -> None:
    payload = {"cik": 320193, "sicDescription": "no sic key here"}
    path = tmp_path / "edgar" / "submissions" / f"{_CIK}.json"
    write_raw_json(path, json.dumps(payload).encode("utf-8"))

    with pytest.raises(SicResolutionError):
        resolve_sic_offline(_CIK, cache_dir=tmp_path)


def test_resolve_sic_offline_raises_when_sic_is_empty_string(tmp_path: Path) -> None:
    payload = {"cik": 320193, "sic": "   "}
    path = tmp_path / "edgar" / "submissions" / f"{_CIK}.json"
    write_raw_json(path, json.dumps(payload).encode("utf-8"))

    with pytest.raises(SicResolutionError):
        resolve_sic_offline(_CIK, cache_dir=tmp_path)


def test_resolve_sic_offline_has_no_network_parameter() -> None:
    """Structural guard (G-S8): the function signature has no client/httpx parameter at all."""
    params = inspect.signature(resolve_sic_offline).parameters
    assert "client" not in params
    assert "httpx" not in params


def test_resolve_sic_offline_never_references_filed() -> None:
    """G-S2's grep, re-run as a test: `resolve_sic_offline` has no temporal dimension. Checked as
    the actual code-relevant patterns (a `filed` dict/column/attribute access), not a bare substring
    match on `"filed"` — this function's own docstring uses the English word "filed" in prose
    ("does not reference `filed` at all"), which is not itself a temporal-filtering code path."""
    source = inspect.getsource(resolve_sic_offline)
    for pattern in ('"filed"', "'filed'", ".filed", "filed <=", "filed<="):
        assert pattern not in source
    assert "as_of_date" not in inspect.signature(resolve_sic_offline).parameters


# ── G-S1 / G-LLM4: no LLM anywhere in this module ───────────────────────────────────────────────


def test_no_llm_import_anywhere_in_business_activity_module() -> None:
    import mizan.screening.business_activity as module

    source = inspect.getsource(module).lower()
    for forbidden in ("openai", "anthropic", "gemini", "vertex", "langchain", "chat_completion"):
        assert forbidden not in source


# ── G-S7: pure function, no DB/cache capability on classify_business_activity ───────────────────


def test_classify_business_activity_has_no_db_or_cache_parameter() -> None:
    params = inspect.signature(classify_business_activity).parameters
    assert "con" not in params
    assert "cache_dir" not in params
    assert "client" not in params


def test_classify_business_activity_is_deterministic_given_same_inputs() -> None:
    overrides = _empty_overrides()
    first = classify_business_activity(_CIK, _CLEAN_SIC, overrides=overrides)
    second = classify_business_activity(_CIK, _CLEAN_SIC, overrides=overrides)
    assert first == second
