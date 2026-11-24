"""Crypto fiqh register; see ``docs/crypto/PHASE_1_SPEC.md`` §A4."""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from mizan.config.fiqh_params import FiqhParam
from mizan.core.base import MizanBaseModel


class CustodyModel(StrEnum):
    EXCHANGE_QABD_HUKMI = "exchange_qabd_hukmi"
    SELF_CUSTODY = "self_custody"


class CryptoFiqhParams(MizanBaseModel):
    stablecoins_allowed: FiqhParam[bool] = FiqhParam(
        register_id=1,
        value=True,
        source=(
            "islamqa.info Q504160: USDC is the cash leg, yield 0; "
            "Coinbase USDC rewards never modelled."
        ),
    )
    staking_rewards_enabled: FiqhParam[bool] = FiqhParam(
        register_id=2,
        value=False,
        source="islamqa.info Q106094/Q125758/Q310956: staking rewards disputed; default OFF.",
    )
    custody_model: FiqhParam[CustodyModel] = FiqhParam(
        register_id=3,
        value=CustodyModel.EXCHANGE_QABD_HUKMI,
        source="islamqa.info Q504160: exchange custody accepted as qabd hukmi for V1.",
        primary_source_gap=(
            "FTX-type failure and freeze risk are caveated-not-modelled; "
            "self-custody is the long-term target."
        ),
    )
    memecoin_exclusion_enabled: FiqhParam[bool] = FiqhParam(
        register_id=4,
        value=True,
        source="Maysir/gharar basis: memecoin exclusion is enabled by default as a parameter.",
    )

    @model_validator(mode="after")
    def _register_ids_are_exactly_one_to_four(self) -> CryptoFiqhParams:
        ids = sorted(getattr(self, name).register_id for name in type(self).model_fields)
        if ids != [1, 2, 3, 4]:
            raise ValueError(f"crypto fiqh register_id set must be exactly 1..4; got {ids}")
        return self


CRYPTO_FIQH_PARAMS = CryptoFiqhParams()
