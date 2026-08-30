"""Boot-gate tests for the permissibility invariants.

Implements PHASE_1_SPEC.md §8 acceptance criteria 1, 2, 11, 12.
"""

import pytest
from pydantic import ValidationError

from mizan.config.boot_check import (
    FiqhRegisterError,
    InvariantViolationError,
    check_invariants,
    main,
)
from mizan.config.invariants import INVARIANTS, Invariants


def test_check_invariants_passes_on_module_singleton() -> None:
    """The module-level ``INVARIANTS`` singleton must satisfy the boot gate (AC 1)."""
    check_invariants()  # must not raise
    check_invariants(INVARIANTS)  # equivalent, explicit form


def test_main_exits_zero_and_prints_pass_message(capsys: pytest.CaptureFixture[str]) -> None:
    """``mizan-boot-check`` exits 0 and prints the exact pass message (AC 1)."""
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Boot check passed: permissibility invariants hold; fiqh register is intact."
        in captured.out
    )


def test_nonzero_cash_yield_is_rejected() -> None:
    """A nonzero ``cash_yield`` must raise ``InvariantViolationError`` (AC 2).

    This is the ONE permitted call site outside ``invariants.py`` that constructs a
    non-default ``Invariants()`` — solely to prove the boot gate rejects it
    (PHASE_1_SPEC.md §3.2).
    """
    violating = Invariants(cash_yield=0.01)

    with pytest.raises(InvariantViolationError, match="cash_yield"):
        check_invariants(violating)


def test_margin_allowed_true_is_rejected() -> None:
    """A boolean invariant flipped away from its safe default must be rejected (AC 2)."""
    violating = Invariants(margin_allowed=True)

    with pytest.raises(InvariantViolationError, match="margin_allowed"):
        check_invariants(violating)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("long_only", False),
        ("fully_funded", False),
        ("derivatives_allowed", True),
        ("margin_allowed", True),
        ("riba_modeling_allowed", True),
        ("llm_in_compliance_path_allowed", True),
    ],
)
def test_each_boolean_invariant_is_individually_rejected(field_name: str, bad_value: bool) -> None:
    """Every one of the seven fields' explicit hand-written check (PHASE_1_SPEC.md §6.1) actually
    fires — not just the two spot-checked above."""
    violating = Invariants(**{field_name: bad_value})

    with pytest.raises(InvariantViolationError, match=field_name):
        check_invariants(violating)


def test_main_reports_invariant_violation_on_stderr_and_exits_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``main()``'s ``InvariantViolationError`` branch prints to stderr and returns 1."""

    def _raise() -> None:
        raise InvariantViolationError("fake violation for coverage")

    monkeypatch.setattr("mizan.config.boot_check.check_all", _raise)
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "BOOT FAILED" in captured.err
    assert "fake violation for coverage" in captured.err


def test_main_reports_fiqh_register_error_on_stderr_and_exits_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``main()``'s ``FiqhRegisterError`` branch prints to stderr and returns 1."""

    def _raise() -> None:
        raise FiqhRegisterError("fake register break for coverage")

    monkeypatch.setattr("mizan.config.boot_check.check_all", _raise)
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "fiqh register is structurally broken" in captured.err
    assert "fake register break for coverage" in captured.err


def test_multiple_violations_are_all_reported_together() -> None:
    """All violated fields are collected before raising, not just the first
    (PHASE_1_SPEC.md §6.1)."""
    violating = Invariants(cash_yield=0.02, derivatives_allowed=True, long_only=False)

    with pytest.raises(InvariantViolationError) as exc_info:
        check_invariants(violating)

    message = str(exc_info.value)
    assert "cash_yield" in message
    assert "derivatives_allowed" in message
    assert "long_only" in message


def test_invariants_rejects_unknown_field() -> None:
    """``extra='forbid'`` must be real on ``Invariants`` (AC 11)."""
    with pytest.raises(ValidationError):
        Invariants(nonexistent_field=1)  # type: ignore[call-arg]


def test_invariants_singleton_is_frozen() -> None:
    """``frozen=True`` must be real on the ``INVARIANTS`` singleton (AC 12)."""
    with pytest.raises(ValidationError):
        INVARIANTS.cash_yield = 0.01


def test_invariants_has_exactly_seven_fields() -> None:
    """Seven fields, exactly (PHASE_1_SPEC.md §3.2) — an eighth requires a check-function update."""
    assert len(Invariants.model_fields) == 7


def test_invariants_default_values_are_the_safe_defaults() -> None:
    """Every field's default is already the boot-gate-passing value."""
    defaults = Invariants()
    assert defaults.cash_yield == 0.0
    assert defaults.long_only is True
    assert defaults.fully_funded is True
    assert defaults.derivatives_allowed is False
    assert defaults.margin_allowed is False
    assert defaults.riba_modeling_allowed is False
    assert defaults.llm_in_compliance_path_allowed is False
