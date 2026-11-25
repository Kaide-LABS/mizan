"""Tests for mizan/crypto/report.py.

Implements PHASE_6_SPEC.md §A5 (Part A).
"""

from __future__ import annotations

from mizan.core.verdict import Verdict
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS
from mizan.crypto.report import render_crypto_fiqh_register, render_crypto_token_verdicts
from mizan.crypto.screening import CryptoTokenVerdict, screen_universe
from mizan.screening.verdict import ReasonTraceEntry, ScreenName


def _verdicts_from_screen_universe() -> tuple[CryptoTokenVerdict, ...]:
    envelopes = screen_universe()
    return tuple(
        CryptoTokenVerdict.model_validate(envelope.payload) for envelope in envelopes.values()
    )


def test_render_crypto_fiqh_register_has_exactly_four_rows() -> None:
    html_out = render_crypto_fiqh_register(CRYPTO_FIQH_PARAMS)
    tbody = html_out.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count("<tr>") == 4
    assert "exchange_qabd_hukmi" in html_out


def test_render_crypto_token_verdicts_has_exactly_twenty_three_rows() -> None:
    verdicts = _verdicts_from_screen_universe()
    assert len(verdicts) == 23
    html_out = render_crypto_token_verdicts(verdicts)
    tbody = html_out.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count("<tr>") == 23


def test_render_crypto_token_verdicts_contains_real_reject_reasons() -> None:
    verdicts = _verdicts_from_screen_universe()
    html_out = render_crypto_token_verdicts(verdicts)
    by_ticker = {v.ticker: v for v in verdicts}
    assert by_ticker["AAVE"].reason.detail in html_out
    assert by_ticker["BNB"].reason.detail in html_out
    assert by_ticker["DOGE"].reason.detail in html_out


def test_render_crypto_token_verdicts_escapes_html() -> None:
    verdict = CryptoTokenVerdict(
        ticker="TEST",
        verdict=Verdict.PURE,
        category="none",
        reason=ReasonTraceEntry(
            screen=ScreenName.BUSINESS_ACTIVITY,
            passed=True,
            threshold=None,
            actual_value=None,
            margin=None,
            detail="a <b> & c",
        ),
    )
    html_out = render_crypto_token_verdicts((verdict,))
    assert "&lt;b&gt;" in html_out
    assert "&amp;" in html_out
