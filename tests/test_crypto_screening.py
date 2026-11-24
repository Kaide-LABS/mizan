import pytest

from mizan.config.boot_check import check_all
from mizan.core.caveats import Caveat
from mizan.core.verdict import Verdict
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS
from mizan.crypto.screening import (
    DEFAULT_REJECT_LIST,
    CryptoBusinessActivityCategory,
    UnknownTokenError,
    screen_token,
    screen_universe,
)
from mizan.crypto.universe import CRYPTO_UNIVERSE


def _verdict(ticker: str, **kwargs: object) -> dict[str, object]:
    return screen_token(ticker, **kwargs).payload


def test_screen_token_happy_path_and_caveat() -> None:
    payload = _verdict("BTC")
    assert payload["verdict"] == Verdict.PURE
    assert payload["category"] == CryptoBusinessActivityCategory.NONE
    assert screen_token("BTC").active_caveats == (Caveat.PENDING_SCHOLARLY_VERIFICATION,)


def test_default_reject_categories_are_non_compliant() -> None:
    assert _verdict("AAVE")["verdict"] == Verdict.NON_COMPLIANT
    assert _verdict("BNB")["verdict"] == Verdict.NON_COMPLIANT
    assert _verdict("DOGE")["verdict"] == Verdict.NON_COMPLIANT


def test_unknown_token_is_rejected() -> None:
    with pytest.raises(UnknownTokenError):
        screen_token("NOTATOKEN")


def test_memecoin_parameter_gates_only_memecoins() -> None:
    params = CRYPTO_FIQH_PARAMS.model_copy(update={
        "memecoin_exclusion_enabled": CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled.model_copy(
            update={"value": False}
        )
    })
    assert _verdict("DOGE", fiqh_params=params)["verdict"] == Verdict.PURE
    assert _verdict("DOGE")["verdict"] == Verdict.NON_COMPLIANT
    assert _verdict("AAVE", fiqh_params=params)["verdict"] == Verdict.NON_COMPLIANT
    assert _verdict("BNB", fiqh_params=params)["verdict"] == Verdict.NON_COMPLIANT


def test_screen_universe_covers_all_named_tokens_with_distinct_reasons() -> None:
    results = screen_universe()
    assert set(results) == set(CRYPTO_UNIVERSE + DEFAULT_REJECT_LIST)
    assert all(_verdict(ticker)["verdict"] == Verdict.PURE for ticker in CRYPTO_UNIVERSE)
    assert all(
        _verdict(ticker)["verdict"] == Verdict.NON_COMPLIANT for ticker in DEFAULT_REJECT_LIST
    )
    reasons = [results[ticker].payload["reason"]["detail"] for ticker in CRYPTO_UNIVERSE]
    assert len(set(reasons)) == len(CRYPTO_UNIVERSE)


def test_boot_check_after_full_screen() -> None:
    screen_universe()
    check_all()


def test_lending_and_exchange_categories_are_never_parameter_gated() -> None:
    permissive = CRYPTO_FIQH_PARAMS.model_copy(update={
        "memecoin_exclusion_enabled": CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled.model_copy(
            update={"value": False}
        )
    })
    for ticker in ("AAVE", "COMP", "MKR", "BNB", "OKB", "CRO"):
        assert _verdict(ticker, fiqh_params=permissive)["verdict"] == Verdict.NON_COMPLIANT


def test_screen_universe_covers_all_23_named_tokens_with_the_right_verdicts() -> None:
    results = screen_universe()
    assert len(results) == 23
    assert set(results) == set(CRYPTO_UNIVERSE) | set(DEFAULT_REJECT_LIST)
    for ticker in CRYPTO_UNIVERSE:
        assert results[ticker].payload["verdict"] == Verdict.PURE
    for ticker in DEFAULT_REJECT_LIST:
        assert results[ticker].payload["verdict"] == Verdict.NON_COMPLIANT


def test_flipping_memecoin_parameter_changes_only_the_three_memecoin_verdicts() -> None:
    default_results = {t: v.payload["verdict"] for t, v in screen_universe().items()}
    flipped_params = CRYPTO_FIQH_PARAMS.model_copy(update={
        "memecoin_exclusion_enabled": CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled.model_copy(
            update={"value": False}
        )
    })
    flipped_results = {
        t: v.payload["verdict"] for t, v in screen_universe(fiqh_params=flipped_params).items()
    }
    changed = {t for t in default_results if default_results[t] != flipped_results[t]}
    assert changed == {"DOGE", "SHIB", "PEPE"}


def test_screen_token_never_branches_on_register_id() -> None:
    tampered = CRYPTO_FIQH_PARAMS.model_copy(update={
        "memecoin_exclusion_enabled": CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled.model_copy(
            update={"register_id": "tampered-id-999"}
        )
    })
    assert _verdict("DOGE", fiqh_params=tampered)["verdict"] == Verdict.NON_COMPLIANT
