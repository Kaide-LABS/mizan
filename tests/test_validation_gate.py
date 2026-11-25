"""Tests for ``mizan/signal/validation_gate.py``; see ``docs/crypto/PHASE_5_SPEC.md`` §B3."""

from __future__ import annotations

import pytest

from mizan.signal.validation_gate import (
    DEFAULT_VALIDATION_GATE_SPEC,
    BaselineKind,
    CalibrationMethod,
    GateCriteria,
    ScoringRule,
    SignalNotValidatedError,
    ValidationGateSpec,
    gate_passed,
    require_passing_gate,
)


def test_default_validation_gate_spec_requires_both_baselines() -> None:
    assert DEFAULT_VALIDATION_GATE_SPEC.required_baselines == frozenset(
        {BaselineKind.NAIVE_LAST_VALUE, BaselineKind.TIMESFM_2_5}
    )


@pytest.mark.parametrize(
    "required_baselines",
    [
        frozenset({BaselineKind.TIMESFM_2_5}),
        frozenset({BaselineKind.NAIVE_LAST_VALUE}),
        frozenset(),
    ],
)
def test_validation_gate_spec_rejects_a_single_baseline_subset(
    required_baselines: frozenset[BaselineKind],
) -> None:
    with pytest.raises(ValueError, match="every BaselineKind"):
        ValidationGateSpec(
            scoring_rule=ScoringRule.CRPS,
            calibration_method=CalibrationMethod.RELIABILITY_DIAGRAM,
            required_baselines=required_baselines,
        )


def _all_true() -> GateCriteria:
    return GateCriteria(
        out_of_sample_disjoint=True,
        calibration_checked=True,
        beats_naive_last_value=True,
        beats_timesfm=True,
        per_token_breakdown_reported=True,
        per_regime_breakdown_reported=True,
    )


def _all_false() -> GateCriteria:
    return GateCriteria(
        out_of_sample_disjoint=False,
        calibration_checked=False,
        beats_naive_last_value=False,
        beats_timesfm=False,
        per_token_breakdown_reported=False,
        per_regime_breakdown_reported=False,
    )


def test_gate_passed_is_true_when_every_criterion_is_true() -> None:
    assert gate_passed(_all_true()) is True


def test_gate_passed_is_false_when_every_criterion_is_false() -> None:
    assert gate_passed(_all_false()) is False


@pytest.mark.parametrize(
    "field_name",
    [
        "out_of_sample_disjoint",
        "calibration_checked",
        "beats_naive_last_value",
        "beats_timesfm",
        "per_token_breakdown_reported",
        "per_regime_breakdown_reported",
    ],
)
def test_gate_passed_is_false_for_any_single_false_criterion(field_name: str) -> None:
    kwargs = {
        "out_of_sample_disjoint": True,
        "calibration_checked": True,
        "beats_naive_last_value": True,
        "beats_timesfm": True,
        "per_token_breakdown_reported": True,
        "per_regime_breakdown_reported": True,
    }
    kwargs[field_name] = False
    assert gate_passed(GateCriteria(**kwargs)) is False


def test_require_passing_gate_does_not_raise_when_all_true() -> None:
    require_passing_gate(_all_true())


def test_require_passing_gate_raises_with_failing_criteria_named() -> None:
    with pytest.raises(SignalNotValidatedError, match="calibration_checked"):
        require_passing_gate(_all_false())
