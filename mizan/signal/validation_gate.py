"""Validation-gate typed criteria and blocking decision; see ``docs/crypto/PHASE_5_SPEC.md`` §B1-B2.

This module defines the gate's *structural* contract only: no scoring-rule computation,
calibration measurement, or baseline comparison is implemented here. ``GateCriteria``'s
booleans are caller-attested inputs that a future adapter-implementing phase must populate
honestly; ``gate_passed``/``require_passing_gate`` are the one blocking seam that phase is
contractually required to call before letting any ``Signal`` drive allocations.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from mizan.core.base import MizanBaseModel


class BaselineKind(StrEnum):
    NAIVE_LAST_VALUE = "naive_last_value"
    TIMESFM_2_5 = "timesfm_2_5"


class ScoringRule(StrEnum):
    CRPS = "crps"
    PINBALL = "pinball"


class CalibrationMethod(StrEnum):
    RELIABILITY_DIAGRAM = "reliability_diagram"
    PIT_HISTOGRAM = "pit_histogram"


class SignificanceTest(StrEnum):
    DIEBOLD_MARIANO = "diebold_mariano"


class ValidationGateSpec(MizanBaseModel):
    scoring_rule: ScoringRule
    calibration_method: CalibrationMethod
    significance_test: SignificanceTest = SignificanceTest.DIEBOLD_MARIANO
    required_baselines: frozenset[BaselineKind]

    @model_validator(mode="after")
    def _both_baselines_are_required(self) -> ValidationGateSpec:
        if self.required_baselines != frozenset(BaselineKind):
            raise ValueError(
                "validation gate must require beating every BaselineKind, not a subset — "
                "requiring only one baseline lets a signal pass by tying a weak comparator"
            )
        return self


DEFAULT_VALIDATION_GATE_SPEC = ValidationGateSpec(
    scoring_rule=ScoringRule.CRPS,
    calibration_method=CalibrationMethod.RELIABILITY_DIAGRAM,
    required_baselines=frozenset(BaselineKind),
)


class GateCriteria(MizanBaseModel):
    out_of_sample_disjoint: bool
    calibration_checked: bool
    beats_naive_last_value: bool
    beats_timesfm: bool
    per_token_breakdown_reported: bool
    per_regime_breakdown_reported: bool


def gate_passed(criteria: GateCriteria) -> bool:
    return all(criteria.model_dump().values())


class SignalNotValidatedError(RuntimeError):
    """Raised when a signal is used to drive allocations without a passing gate."""


def require_passing_gate(criteria: GateCriteria) -> None:
    if not gate_passed(criteria):
        raise SignalNotValidatedError(
            f"signal failed the validation gate: {criteria.model_dump()}"
        )
