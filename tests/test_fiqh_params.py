"""Register-completeness and honesty tests for the fiqh judgment-call register.

Implements PHASE_1_SPEC.md §8 acceptance criteria 3, 4, 5, 6, 7.
"""

from typing import Any, TypeVar, cast

import pytest
from pydantic import ValidationError

from mizan.config.boot_check import FiqhRegisterError, check_fiqh_register
from mizan.config.fiqh_params import (
    FIQH_PARAMS,
    FiqhParam,
    FiqhParams,
    VerificationStatus,
)

GAP_REQUIRED_IDS = {1, 2, 5}


def test_check_fiqh_register_passes_on_module_singleton() -> None:
    """The module-level ``FIQH_PARAMS`` singleton must satisfy the boot gate."""
    check_fiqh_register()  # must not raise
    check_fiqh_register(FIQH_PARAMS)  # equivalent, explicit form


def test_register_has_exactly_eleven_fields() -> None:
    """The register is exactly 11 entries, 1:1 with MASTER_PRD.md §10 (AC 4)."""
    assert len(FiqhParams.model_fields) == 11


def test_register_ids_are_exactly_one_to_eleven() -> None:
    """The sorted ``register_id`` set is exactly ``[1, ..., 11]``, no duplicates (AC 4)."""
    ids = sorted(getattr(FIQH_PARAMS, name).register_id for name in FiqhParams.model_fields)
    assert ids == list(range(1, 12))


@pytest.mark.parametrize("field_name", list(FiqhParams.model_fields))
def test_every_entry_is_flagged_and_sourced(field_name: str) -> None:
    """Every register entry has a non-empty source, pending status, and configurable=True (AC 5)."""
    entry = getattr(FIQH_PARAMS, field_name)
    assert entry.source.strip() != ""
    assert entry.status is VerificationStatus.PENDING_SCHOLARLY_VERIFICATION
    assert entry.configurable is True


@pytest.mark.parametrize("field_name", list(FiqhParams.model_fields))
def test_gap_required_entries_have_nonempty_primary_source_gap(field_name: str) -> None:
    """Entries #1, #2, #5 carry a mandatory, non-empty ``primary_source_gap`` (AC 6)."""
    entry = getattr(FIQH_PARAMS, field_name)
    assert isinstance(entry.primary_source_gap, str)
    if entry.register_id in GAP_REQUIRED_IDS:
        assert entry.primary_source_gap.strip() != ""
    # Entries outside {1, 2, 5} are NOT required to have a primary_source_gap, but several
    # (#6-#10) carry one anyway to record a genuine, non-mandatory gap — that is permitted by
    # FiqhParam's contract ("empty string where the primary source is clear") and is not asserted
    # against here.


def test_entry_one_states_denominator_basis_is_unverified_inference() -> None:
    """#1's gap text must say AAOIFI's denominator basis is not stated and the default is
    inferred."""
    gap = FIQH_PARAMS.ratio_denominator_basis.primary_source_gap.lower()
    assert "unverified" in gap
    assert "not stated" in gap
    assert "inference" in gap


def test_entry_two_states_averaging_window_is_unverified_inference() -> None:
    """#2's gap text must say AAOIFI's averaging window is not stated and the default is
    inferred."""
    gap = FIQH_PARAMS.ratio_denominator_smoothing.primary_source_gap.lower()
    assert "unverified" in gap
    assert "not stated" in gap
    assert "inference" in gap


def test_entry_five_states_total_income_vs_total_revenue_ambiguity() -> None:
    """#5's gap text must state the 'Total Income' vs 'total revenue' ambiguity."""
    gap = FIQH_PARAMS.non_permissible_income_threshold.primary_source_gap
    assert "Total Income" in gap
    assert "total revenue" in gap


def test_fiqh_param_is_generic_not_a_union() -> None:
    """``FiqhParam`` is declared generic (``FiqhParam(MizanBaseModel, Generic[T])``), not a union
    (AC 7). A union on the honesty surface would depend on Pydantic's unspecified,
    minor-release-mutable smart-union resolution (ULTIMATE_PRD.md §3.4)."""
    # __parameters__ is populated at runtime by typing.Generic's __init_subclass__ but is not
    # part of FiqhParam's static type surface, hence the Any cast for mypy --strict.
    type_params: tuple[Any, ...] = cast(Any, FiqhParam).__parameters__
    assert len(type_params) == 1
    assert isinstance(type_params[0], TypeVar)
    # Every FiqhParams field is an explicitly parameterised FiqhParam[...] — no bare FiqhParam.
    # Pydantic materialises `FiqhParam[X]` as a concrete subclass carrying
    # `__pydantic_generic_metadata__["origin"] is FiqhParam`, rather than a typing generic alias
    # exposing `__origin__` directly.
    for field_name, field_info in FiqhParams.model_fields.items():
        metadata = cast(Any, field_info.annotation).__pydantic_generic_metadata__
        assert metadata["origin"] is FiqhParam, (
            f"{field_name} is not an explicitly parameterised FiqhParam[T]"
        )


def test_register_rejects_a_blanked_source_via_check_function() -> None:
    """A register copy with entry #3's ``source`` blanked must fail ``check_fiqh_register``
    (AC 3)."""
    broken = FIQH_PARAMS.model_copy(
        update={
            "debt_ratio_threshold": FIQH_PARAMS.debt_ratio_threshold.model_copy(
                update={"source": ""}
            )
        }
    )

    with pytest.raises(FiqhRegisterError, match="source is empty"):
        check_fiqh_register(broken)


def test_register_rejects_a_blanked_primary_source_gap_on_entry_one() -> None:
    """A register copy with entry #1's ``primary_source_gap`` blanked must fail (AC 3)."""
    broken = FIQH_PARAMS.model_copy(
        update={
            "ratio_denominator_basis": FIQH_PARAMS.ratio_denominator_basis.model_copy(
                update={"primary_source_gap": ""}
            )
        }
    )

    with pytest.raises(FiqhRegisterError, match="primary_source_gap"):
        check_fiqh_register(broken)


def test_constructing_fiqh_params_with_duplicate_register_id_is_rejected() -> None:
    """The ``@model_validator`` fires on real construction (unlike ``model_copy``) and rejects a
    duplicate ``register_id`` — here, entry #3 is overridden to collide with entry #1's id."""
    with pytest.raises(ValidationError, match="register_id"):
        FiqhParams(
            debt_ratio_threshold=FiqhParam[float](
                register_id=1,  # duplicate of ratio_denominator_basis's id
                value=0.30,
                source="deliberately-broken test fixture",
            )
        )


def test_register_rejects_status_drift() -> None:
    """An entry whose ``status`` drifts off PENDING_SCHOLARLY_VERIFICATION must fail check."""
    broken = FIQH_PARAMS.model_copy(
        update={
            "purify_capital_gains": FIQH_PARAMS.purify_capital_gains.model_copy(
                update={"status": "scholar_ratified"}
            )
        }
    )

    with pytest.raises(FiqhRegisterError, match="expected pending verification"):
        check_fiqh_register(broken)


def test_check_fiqh_register_rejects_duplicate_register_id_via_model_copy() -> None:
    """``model_copy(update=...)`` bypasses the ``@model_validator`` (PHASE_1_SPEC.md §3.3.3), so
    ``check_fiqh_register`` is the only remaining gate against a duplicated ``register_id`` reaching
    a live register — this proves that gate independently fires."""
    broken = FIQH_PARAMS.model_copy(
        update={
            "debt_ratio_threshold": FIQH_PARAMS.debt_ratio_threshold.model_copy(
                update={"register_id": 1}
            )
        }
    )

    with pytest.raises(FiqhRegisterError, match=r"register_id set must be exactly 1\.\.11"):
        check_fiqh_register(broken)


def test_register_rejects_configurable_false() -> None:
    """An entry whose ``configurable`` flag is flipped to False must fail check."""
    broken = FIQH_PARAMS.model_copy(
        update={
            "purify_capital_gains": FIQH_PARAMS.purify_capital_gains.model_copy(
                update={"configurable": False}
            )
        }
    )

    with pytest.raises(FiqhRegisterError, match="configurable must be True"):
        check_fiqh_register(broken)
