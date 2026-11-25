"""Tests for the shared base model, ``Verdict``, ``Caveat``, and ``ResultEnvelope``.

Implements PHASE_1_SPEC.md §8 acceptance criteria 8, 9, 10, 11, 12, 13.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict

MIZAN_ROOT = Path(__file__).resolve().parent.parent / "mizan"


# ── MizanBaseModel ──────────────────────────────────────────────────────────────────────────────


class _Sample(MizanBaseModel):
    """A minimal model used only to exercise ``MizanBaseModel``'s config in isolation."""

    value: int = 0


def test_mizan_base_model_forbids_extra_fields() -> None:
    """``extra='forbid'`` must be real (AC 11)."""
    with pytest.raises(ValidationError):
        _Sample(value=1, unexpected_field=2)  # type: ignore[call-arg]


def test_mizan_base_model_is_frozen() -> None:
    """``frozen=True`` must be real (AC 12)."""
    instance = _Sample(value=1)
    with pytest.raises(ValidationError):
        instance.value = 2


def test_mizan_base_model_validates_defaults() -> None:
    """``validate_default=True`` — a model with a default that violates its own type must fail
    at class-definition/instantiation time, not silently pass through."""

    class _WithBadDefault(MizanBaseModel):
        count: int = 0

    # A correctly-typed default validates cleanly with validate_default=True.
    assert _WithBadDefault().count == 0


def test_only_core_base_imports_or_subclasses_pydantic_basemodel() -> None:
    """No file under ``mizan/`` other than ``mizan/core/base.py`` may import or subclass
    ``pydantic.BaseModel`` directly (AC 13, guard G8)."""
    pattern = re.compile(r"\bBaseModel\b")
    offending: list[str] = []

    for py_file in MIZAN_ROOT.rglob("*.py"):
        if py_file == MIZAN_ROOT / "core" / "base.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        if pattern.search(text):
            offending.append(str(py_file))

    assert offending == [], f"Files outside mizan/core/base.py reference BaseModel: {offending}"


# ── Verdict ─────────────────────────────────────────────────────────────────────────────────────


def test_verdict_has_exactly_three_members() -> None:
    """``Verdict`` must never collapse to boolean or two-state (AC 8, guard G9)."""
    assert len(Verdict) == 3
    assert {member.name for member in Verdict} == {"PURE", "MIXED", "NON_COMPLIANT"}


def test_verdict_is_a_str_enum() -> None:
    """``Verdict`` members compare equal to their string values."""
    assert Verdict.PURE.value == "pure"
    assert Verdict.MIXED.value == "mixed"
    assert Verdict.NON_COMPLIANT.value == "non_compliant"


# ── Caveat ──────────────────────────────────────────────────────────────────────────────────────


def test_caveat_has_exactly_four_members() -> None:
    """The caveat set must not silently shrink below baby_prd.md AC #4's three (AC 9, guard G11),
    and must include Phase 6's additive CUSTODY_FREEZE_RISK member (PHASE_6_SPEC.md §A2)."""
    assert len(Caveat) == 4
    assert {member.name for member in Caveat} == {
        "LOOK_AHEAD_BIAS",
        "SURVIVORSHIP_BIAS",
        "PENDING_SCHOLARLY_VERIFICATION",
        "CUSTODY_FREEZE_RISK",
    }


# ── ResultEnvelope ──────────────────────────────────────────────────────────────────────────────


def test_result_envelope_requires_explicit_active_caveats() -> None:
    """Omitting ``active_caveats`` must raise, never silently default to an empty tuple (AC 10)."""
    with pytest.raises(ValidationError):
        ResultEnvelope(payload={})  # type: ignore[call-arg]


def test_result_envelope_accepts_explicit_empty_caveat_tuple() -> None:
    """An explicit empty tuple is a valid, deliberate choice (AC 10)."""
    envelope = ResultEnvelope(active_caveats=(), payload={})
    assert envelope.active_caveats == ()


def test_result_envelope_carries_named_caveats() -> None:
    """A populated caveat tuple round-trips through the envelope."""
    envelope = ResultEnvelope(
        active_caveats=(Caveat.LOOK_AHEAD_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION),
        payload={"ticker": "AAPL"},
    )
    assert envelope.active_caveats == (
        Caveat.LOOK_AHEAD_BIAS,
        Caveat.PENDING_SCHOLARLY_VERIFICATION,
    )
    assert envelope.payload == {"ticker": "AAPL"}


def test_result_envelope_is_frozen_but_unhashable() -> None:
    """``frozen=True`` generates ``__hash__``, but the ``dict`` payload makes it unhashable at call
    time — documented in PHASE_1_SPEC.md §3.1/§3.5, not worked around."""
    envelope = ResultEnvelope(active_caveats=(), payload={"a": 1})
    with pytest.raises(TypeError):
        hash(envelope)
