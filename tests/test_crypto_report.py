"""Tests for mizan/crypto/report.py.

Implements PHASE_6_SPEC.md §A5 (Part A).
"""

from __future__ import annotations

from datetime import date

import pytest

from mizan.config.fiqh_params import FiqhParam
from mizan.core.caveats import Caveat
from mizan.core.verdict import Verdict
from mizan.crypto.backtest import BacktestCostParams, CryptoBacktestResult, DailySnapshot
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS, CryptoFiqhParams, CustodyModel
from mizan.crypto.report import (
    CryptoReportInput,
    render_crypto_fiqh_register,
    render_crypto_report,
    render_crypto_token_verdicts,
    resolve_crypto_report_caveats,
)
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


def _backtest_result() -> CryptoBacktestResult:
    return CryptoBacktestResult(
        strategy_label="baseline",
        daily_snapshots=(
            DailySnapshot(
                as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1000.0
            ),
        ),
        rebalance_dates=(date(2026, 1, 1),),
        excluded_tickers=("AAVE",),
        cost_params=BacktestCostParams(),
    )


def _report_input() -> CryptoReportInput:
    return CryptoReportInput(
        backtest_result=_backtest_result(), token_verdicts=_verdicts_from_screen_universe()
    )


def test_resolve_crypto_report_caveats_adds_custody_risk_for_exchange_custody() -> None:
    result = resolve_crypto_report_caveats((Caveat.SURVIVORSHIP_BIAS,), CRYPTO_FIQH_PARAMS)
    assert result == (Caveat.SURVIVORSHIP_BIAS, Caveat.CUSTODY_FREEZE_RISK)


def test_resolve_crypto_report_caveats_excludes_custody_risk_for_self_custody() -> None:
    self_custody_params = CryptoFiqhParams(
        custody_model=FiqhParam(
            register_id=3, value=CustodyModel.SELF_CUSTODY, source="test"
        )
    )
    result = resolve_crypto_report_caveats((Caveat.SURVIVORSHIP_BIAS,), self_custody_params)
    assert result == (Caveat.SURVIVORSHIP_BIAS,)


def test_render_crypto_report_contains_survivorship_and_custody_caveat_text() -> None:
    html_out = render_crypto_report(
        _report_input(),
        active_caveats=(Caveat.SURVIVORSHIP_BIAS, Caveat.CUSTODY_FREEZE_RISK),
    )
    assert html_out.startswith("<!DOCTYPE html>")
    from mizan.reporting.report import CAVEAT_DESCRIPTIONS

    assert CAVEAT_DESCRIPTIONS[Caveat.SURVIVORSHIP_BIAS] in html_out
    assert CAVEAT_DESCRIPTIONS[Caveat.CUSTODY_FREEZE_RISK] in html_out


def test_render_crypto_report_requires_active_caveats_keyword() -> None:
    with pytest.raises(TypeError):
        render_crypto_report(_report_input())  # type: ignore[call-arg]
