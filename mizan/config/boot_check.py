"""Fail-fast boot validators and the ``mizan-boot-check`` CLI entrypoint.

Implements PHASE_1_SPEC.md §4.1, §6.1-§6.3.
"""

import sys

from mizan.config.fiqh_params import FIQH_PARAMS, FiqhParams, VerificationStatus
from mizan.config.invariants import INVARIANTS, Invariants


class InvariantViolationError(RuntimeError):
    """Raised by ``check_invariants()`` when any ``Invariants`` field fails its required value."""


class FiqhRegisterError(RuntimeError):
    """Raised by ``check_fiqh_register()`` when the honesty surface is structurally broken."""


def check_invariants(invariants: Invariants | None = None) -> None:
    """Assert every permissibility invariant holds.

    Args:
        invariants: the instance to check. Defaults to the module-level ``INVARIANTS`` singleton.
            The parameter exists SOLELY so tests can construct a deliberately-violating instance
            and prove this function rejects it (PHASE_1_SPEC.md §8 criterion 2). No production
            call site may pass it.

    Raises:
        InvariantViolationError: on any violation, listing every violated field.

    Never returns a boolean. Never logs-and-continues. Callers wanting a non-raising check catch
    the exception themselves; this function's contract is raise-or-silently-pass.
    """
    inv = INVARIANTS if invariants is None else invariants
    violations: list[str] = []

    if inv.cash_yield != 0.0:
        violations.append(f"cash_yield must be 0.0, got {inv.cash_yield!r}")
    if not inv.long_only:
        violations.append("long_only must be True")
    if not inv.fully_funded:
        violations.append("fully_funded must be True")
    if inv.derivatives_allowed:
        violations.append("derivatives_allowed must be False")
    if inv.margin_allowed:
        violations.append("margin_allowed must be False")
    if inv.riba_modeling_allowed:
        violations.append("riba_modeling_allowed must be False")
    if inv.llm_in_compliance_path_allowed:
        violations.append("llm_in_compliance_path_allowed must be False")

    if violations:
        raise InvariantViolationError("; ".join(violations))


def check_fiqh_register(params: FiqhParams | None = None) -> None:
    """Assert the fiqh judgment-call register is structurally honest.

    Checks, for the register as a whole and every entry:
      * exactly 11 entries;
      * register_ids are exactly {1..11}, each once;
      * every entry's ``source`` is non-empty;
      * every entry's ``status`` is ``PENDING_SCHOLARLY_VERIFICATION``;
      * every entry's ``configurable`` is True;
      * entries #1, #2 and #5 have a non-empty ``primary_source_gap``.

    Args:
        params: defaults to the module-level ``FIQH_PARAMS`` singleton. Parameter exists for
            tests only, same rationale as ``check_invariants()``.

    Raises:
        FiqhRegisterError: listing every structural failure found.

    Rationale: the register IS the honesty surface (MASTER_PRD.md §0). A silently-dropped
    verification flag or an empty source string is exactly the kind of silent-correctness failure
    MASTER_PRD.md §13 names as this project's dangerous class, so it is gated at boot rather than
    left to review.
    """
    reg = FIQH_PARAMS if params is None else params
    problems: list[str] = []

    field_names = list(type(reg).model_fields)
    if len(field_names) != 11:
        problems.append(f"register must have exactly 11 entries, found {len(field_names)}")

    seen_ids: list[int] = []
    gap_required = {1, 2, 5}

    for name in field_names:
        entry = getattr(reg, name)
        seen_ids.append(entry.register_id)
        if not entry.source.strip():
            problems.append(f"{name}: source is empty")
        if entry.status is not VerificationStatus.PENDING_SCHOLARLY_VERIFICATION:
            problems.append(f"{name}: status is {entry.status!r}, expected pending verification")
        if not entry.configurable:
            problems.append(f"{name}: configurable must be True (MASTER_PRD.md §0)")
        if entry.register_id in gap_required and not entry.primary_source_gap.strip():
            problems.append(
                f"{name}: register #{entry.register_id} requires a non-empty "
                f"primary_source_gap (ULTIMATE_PRD.md §3.1(d), Q1/Q2)"
            )

    if sorted(seen_ids) != list(range(1, 12)):
        problems.append(f"register_id set must be exactly 1..11, got {sorted(seen_ids)}")

    if problems:
        raise FiqhRegisterError("; ".join(problems))


def check_all() -> None:
    """Run ``check_invariants()`` then ``check_fiqh_register()``. Raises on the first failure."""
    check_invariants()
    check_fiqh_register()


def main() -> int:
    """CLI entrypoint for ``mizan-boot-check``.

    Calls ``check_all()``. Returns 0 on success; 1 on ``InvariantViolationError`` or
    ``FiqhRegisterError`` (message printed to stderr). A non-zero exit code is the
    machine-readable signal the phase loop's review agent checks for.

    Every later phase's CLI entrypoints (ingest | screen | backtest | report, Phases 2-7) MUST
    call ``check_all()`` as their first action and exit non-zero on failure, matching this
    behaviour.
    """
    try:
        check_all()
    except InvariantViolationError as exc:
        print(f"BOOT FAILED — permissibility invariant violated: {exc}", file=sys.stderr)
        return 1
    except FiqhRegisterError as exc:
        print(f"BOOT FAILED — fiqh register is structurally broken: {exc}", file=sys.stderr)
        return 1
    print("Boot check passed: permissibility invariants hold; fiqh register is intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
