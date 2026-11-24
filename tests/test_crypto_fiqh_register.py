from typing import Any

import pytest

from mizan.config.boot_check import check_crypto_fiqh_register
from mizan.config.fiqh_params import FiqhParam, VerificationStatus
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS, CustodyModel


def test_crypto_fiqh_register_is_complete() -> None:
    check_crypto_fiqh_register()
    assert len(type(CRYPTO_FIQH_PARAMS).model_fields) == 4
    ids = {getattr(CRYPTO_FIQH_PARAMS, name).register_id
           for name in type(CRYPTO_FIQH_PARAMS).model_fields}
    assert ids == {1, 2, 3, 4}


def _entries() -> list[FiqhParam[Any]]:
    return [getattr(CRYPTO_FIQH_PARAMS, name) for name in type(CRYPTO_FIQH_PARAMS).model_fields]


def test_every_entry_is_pending_scholarly_verification() -> None:
    assert all(
        entry.status is VerificationStatus.PENDING_SCHOLARLY_VERIFICATION
        for entry in _entries()
    )


def test_every_entry_has_nonempty_source() -> None:
    assert all(entry.source.strip() for entry in _entries())


def test_every_entry_is_configurable() -> None:
    assert all(entry.configurable is True for entry in _entries())


def test_custody_entry_states_freeze_risk_unmodelled() -> None:
    gap = CRYPTO_FIQH_PARAMS.custody_model.primary_source_gap.lower()
    assert "freeze" in gap
    assert "failure" in gap
    assert "self-custody" in gap


def test_register_ids_are_exactly_one_to_four() -> None:
    assert {entry.register_id for entry in _entries()} == {1, 2, 3, 4}


def test_check_rejects_blanked_source() -> None:
    broken = CRYPTO_FIQH_PARAMS.model_copy(update={
        "stablecoins_allowed": CRYPTO_FIQH_PARAMS.stablecoins_allowed.model_copy(
            update={"source": ""}
        )
    })
    with pytest.raises(Exception, match="source"):
        check_crypto_fiqh_register(broken)


def test_check_rejects_status_drift() -> None:
    broken_entry = CRYPTO_FIQH_PARAMS.staking_rewards_enabled.model_copy(update={"status": "bad"})
    broken = CRYPTO_FIQH_PARAMS.model_copy(update={"staking_rewards_enabled": broken_entry})
    with pytest.raises(Exception, match="status"):
        check_crypto_fiqh_register(broken)


def test_default_values() -> None:
    assert CRYPTO_FIQH_PARAMS.stablecoins_allowed.value is True
    assert CRYPTO_FIQH_PARAMS.staking_rewards_enabled.value is False
    assert CRYPTO_FIQH_PARAMS.custody_model.value is CustodyModel.EXCHANGE_QABD_HUKMI
    assert CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled.value is True
