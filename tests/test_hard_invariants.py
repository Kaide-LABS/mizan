"""Part B proofs that each hard invariant is rejected when deliberately flipped."""

import inspect

import pytest
from pydantic import ValidationError

from mizan.config.boot_check import InvariantViolationError, check_invariants
from mizan.config.invariants import INVARIANTS, Invariants
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS


def test_spot_only_cannot_be_disabled() -> None:
    with pytest.raises(InvariantViolationError, match="spot_only"):
        check_invariants(Invariants(spot_only=False))


def test_no_margin_or_leverage_cannot_be_disabled() -> None:
    cases = ((Invariants(margin_allowed=True), "margin_allowed"),
             (Invariants(fully_funded=False), "fully_funded"))
    for violating, field_name in cases:
        with pytest.raises(InvariantViolationError, match=field_name):
            check_invariants(violating)


def test_no_perps_futures_options_cannot_be_disabled() -> None:
    with pytest.raises(InvariantViolationError, match="derivatives_allowed"):
        check_invariants(Invariants(derivatives_allowed=True))


def test_no_cfd_synthetic_exposure_cannot_be_disabled() -> None:
    with pytest.raises(InvariantViolationError, match="synthetic_exposure_allowed"):
        check_invariants(Invariants(synthetic_exposure_allowed=True))


def test_no_lending_or_yield_cannot_be_disabled() -> None:
    with pytest.raises(InvariantViolationError, match="lending_or_yield_allowed"):
        check_invariants(Invariants(lending_or_yield_allowed=True))


def test_cash_yield_is_zero_and_cannot_be_disabled() -> None:
    with pytest.raises(InvariantViolationError, match="cash_yield"):
        check_invariants(Invariants(cash_yield=0.01))


def test_invariants_singleton_is_frozen_and_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        INVARIANTS.spot_only = False
    with pytest.raises(ValidationError):
        Invariants(bogus=1)  # type: ignore[call-arg]


def test_invariants_field_count_is_locked_at_ten() -> None:
    # An eleventh field requires a matching hand-written boot_check change.
    assert len(Invariants.model_fields) == 10


def test_staking_rewards_enabled_cannot_leak_into_the_invariant_surface() -> None:
    flipped = CRYPTO_FIQH_PARAMS.model_copy(update={
        "staking_rewards_enabled": CRYPTO_FIQH_PARAMS.staking_rewards_enabled.model_copy(
            update={"value": True}
        )
    })
    assert flipped.staking_rewards_enabled.value is True
    assert INVARIANTS.cash_yield == 0.0
    assert INVARIANTS.lending_or_yield_allowed is False
    check_invariants()


def test_check_invariants_references_every_invariants_field_by_name() -> None:
    source = inspect.getsource(check_invariants)
    for field_name in Invariants.model_fields:
        assert field_name in source
