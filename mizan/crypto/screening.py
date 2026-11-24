"""Crypto token screening; implements ``docs/crypto/PHASE_3_SPEC.md`` A1-A5."""

from __future__ import annotations

from enum import StrEnum

from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS, CryptoFiqhParams
from mizan.crypto.universe import CRYPTO_UNIVERSE
from mizan.screening.verdict import ReasonTraceEntry, ScreenName


class CryptoBusinessActivityCategory(StrEnum):
    LENDING_RIBA = "lending_riba"
    EXCHANGE_MARGIN_FUTURES_INCOME = "exchange_margin_futures_income"
    MAYSIR_GHARAR_MEMECOIN = "maysir_gharar_memecoin"
    NONE = "none"


class CryptoTokenVerdict(MizanBaseModel):
    ticker: str
    verdict: Verdict
    category: CryptoBusinessActivityCategory
    reason: ReasonTraceEntry


class UnknownTokenError(RuntimeError):
    """Raised when a caller asks to screen a token outside the curated map."""


DEFAULT_REJECT_LIST: tuple[str, ...] = (
    "AAVE", "COMP", "MKR", "BNB", "OKB", "CRO", "DOGE", "SHIB", "PEPE"
)

_NONE = CryptoBusinessActivityCategory.NONE
_LENDING = CryptoBusinessActivityCategory.LENDING_RIBA
_EXCHANGE = CryptoBusinessActivityCategory.EXCHANGE_MARGIN_FUTURES_INCOME
_MEMECOIN = CryptoBusinessActivityCategory.MAYSIR_GHARAR_MEMECOIN

_TOKEN_CLASSIFICATIONS: dict[str, tuple[CryptoBusinessActivityCategory, str]] = {
    "BTC": (
        _NONE, "Store-of-value and payment network; no lending or derivative revenue identified."
    ),
    "LTC": (
        _NONE,
        "Proof-of-work payment network focused on peer-to-peer transfer, without lending revenue.",
    ),
    "BCH": (
        _NONE,
        "Payment-focused proof-of-work network; no identified lending or margin business model.",
    ),
    "ETH": (
        _NONE,
        "General-purpose smart-contract settlement network; this screen identifies no "
        "disqualifying core activity.",
    ),
    "SOL": (
        _NONE,
        "High-throughput smart-contract network used for settlement and applications, not "
        "lending income.",
    ),
    "ADA": (
        _NONE,
        "Proof-of-stake smart-contract network; the token classification has no disqualifying "
        "business category.",
    ),
    "AVAX": (
        _NONE,
        "Smart-contract and subnet settlement network; no lending or exchange-fee core activity "
        "identified.",
    ),
    "DOT": (
        _NONE,
        "Interoperability and shared-security network token; no disqualifying activity "
        "identified.",
    ),
    "NEAR": (
        _NONE,
        "Smart-contract platform token supporting network utility, without a lending-business "
        "classification.",
    ),
    "ATOM": (
        _NONE,
        "Interchain coordination and staking network token; no lending or derivative revenue "
        "identified.",
    ),
    "ALGO": (
        _NONE,
        "Payment and smart-contract network token; no disqualifying core business identified.",
    ),
    "XRP": (
        _NONE,
        "Payment and settlement network token; this map identifies no lending or maysir "
        "business model.",
    ),
    "XLM": (
        _NONE,
        "Cross-border payment network token; no disqualifying lending or exchange activity "
        "identified.",
    ),
    "LINK": (
        _NONE,
        "Oracle infrastructure token providing data services to protocols, not an "
        "interest-bearing lender.",
    ),
    "AAVE": (
        _LENDING,
        "AAVE: lending/borrowing protocol governance token; core business is interest-based "
        "(riba) lending, per the PRD.",
    ),
    "COMP": (
        _LENDING,
        "COMP: lending/borrowing protocol governance token; core business is interest-based "
        "(riba) lending, per the PRD.",
    ),
    "MKR": (
        _LENDING,
        "MKR: lending/borrowing protocol governance token; core business is interest-based "
        "(riba) lending, per the PRD.",
    ),
    "BNB": (
        _EXCHANGE,
        "BNB: exchange token; issuing exchange core revenue includes margin/futures trading "
        "fees, per the PRD.",
    ),
    "OKB": (
        _EXCHANGE,
        "OKB: exchange token; issuing exchange core revenue includes margin/futures trading "
        "fees, per the PRD.",
    ),
    "CRO": (
        _EXCHANGE,
        "CRO: exchange token; issuing exchange core revenue includes margin/futures trading "
        "fees, per the PRD.",
    ),
    "DOGE": (
        _MEMECOIN,
        "DOGE: memecoin; maysir/gharar basis, excluded by the configurable memecoin parameter.",
    ),
    "SHIB": (
        _MEMECOIN,
        "SHIB: memecoin; maysir/gharar basis, excluded by the configurable memecoin parameter.",
    ),
    "PEPE": (
        _MEMECOIN,
        "PEPE: memecoin; maysir/gharar basis, excluded by the configurable memecoin parameter.",
    ),
}


def screen_token(
    ticker: str, *, fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS
) -> ResultEnvelope:
    """Return the documented, in-memory business-activity verdict for one curated ticker."""
    classification = _TOKEN_CLASSIFICATIONS.get(ticker)
    if classification is None:
        raise UnknownTokenError(f"unrecognised crypto token: {ticker}")
    category, detail = classification
    passed = (
        not fiqh_params.memecoin_exclusion_enabled.value
        if category is CryptoBusinessActivityCategory.MAYSIR_GHARAR_MEMECOIN
        else category is CryptoBusinessActivityCategory.NONE
    )
    reason = ReasonTraceEntry(
        screen=ScreenName.BUSINESS_ACTIVITY, passed=passed, threshold=None,
        actual_value=None, margin=None, detail=detail,
    )
    result = CryptoTokenVerdict(
        ticker=ticker, verdict=Verdict.PURE if passed else Verdict.NON_COMPLIANT,
        category=category, reason=reason,
    )
    return ResultEnvelope(
        active_caveats=(Caveat.PENDING_SCHOLARLY_VERIFICATION,),
        payload=result.model_dump(),
    )


def screen_universe(
    *, fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS
) -> dict[str, ResultEnvelope]:
    """Screen all 23 named tokens in deterministic sorted order without I/O."""
    return {ticker: screen_token(ticker, fiqh_params=fiqh_params)
            for ticker in sorted(CRYPTO_UNIVERSE + DEFAULT_REJECT_LIST)}
