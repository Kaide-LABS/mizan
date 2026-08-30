"""The permissibility boundary — fixed constants, never runtime knobs.

Implements PHASE_1_SPEC.md §3.2.
"""

from mizan.core.base import MizanBaseModel


class Invariants(MizanBaseModel):
    """The permissibility boundary. Every field here is a fixed constant, never a runtime knob.

    There is no mechanism anywhere in this class, this module, or its callers to override these
    values via environment variable, CLI flag, config file, or constructor argument. A field
    becoming configurable is itself a hard-boundary violation (PHASE_1_SPEC.md §7).

    Source: MASTER_PRD.md §2 INVARIANTS; ULTIMATE_PRD.md §5; baby_prd.md §Boundary.

    Seven fields, exactly. Adding an eighth requires adding its check to
    ``mizan.config.boot_check.check_invariants`` in the same diff — the deliberately hand-written
    check style makes the omission visible.
    """

    cash_yield: float = 0.0
    long_only: bool = True
    fully_funded: bool = True
    derivatives_allowed: bool = False
    margin_allowed: bool = False
    riba_modeling_allowed: bool = False
    llm_in_compliance_path_allowed: bool = False


# The single module-level instance every other module imports
# (``from mizan.config.invariants import INVARIANTS``). No module constructs its own
# ``Invariants()``. There is exactly one instance, constructed once at import time, with zero
# arguments. A call site passing any argument into ``Invariants(...)`` is a review-blocking
# finding (PHASE_1_SPEC.md §3.2) — the one permitted exception is inside
# ``tests/test_invariants.py``, which must construct violating instances in order to prove the
# boot gate rejects them.
INVARIANTS = Invariants()
