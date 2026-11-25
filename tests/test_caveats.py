"""Tests for mizan/core/caveats.py's Phase 6 addition.

Implements PHASE_6_SPEC.md §A5, §Implications S8.
"""

from __future__ import annotations

from mizan.core.caveats import Caveat


def test_custody_freeze_risk_member_value() -> None:
    assert Caveat.CUSTODY_FREEZE_RISK.value == "custody_freeze_risk"


def test_caveat_has_exactly_four_members() -> None:
    assert len(set(Caveat)) == 4


def test_reporting_report_still_imports_after_caveat_growth() -> None:
    """Regression test for PHASE_6_SPEC.md §A3's forced CAVEAT_DESCRIPTIONS edit: importing
    mizan.reporting.report must succeed now that Caveat has a fourth member, since that module's
    own completeness assert (`set(CAVEAT_DESCRIPTIONS) == set(Caveat)`) runs at import time."""
    import mizan.reporting.report  # noqa: F401
