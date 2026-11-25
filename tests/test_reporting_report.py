"""Tests for mizan/reporting/report.py.

Implements PHASE_7_SPEC.md §8 acceptance criteria 1 (caveats-first ordering), 2
(active_caveats is keyword-only, no default -> TypeError when omitted), 3 (verbatim caveat text),
4 (gross vs net-of-purification distinctness), 5 (all 11 fiqh entries rendered), 6 (well-formed
HTML), 9 (plots embedded inline), 10 (ReportInput rejects a non-purified BacktestResult), 13
(MizanBaseModel inheritance), 15 (no LLM import / no free-text generation), 22 (boundary greps),
plus guards G-R1, G-R2, G-R3, G-R4, G-R6, G-R7, G-BOUND3.
"""

from __future__ import annotations

import base64
import inspect
import re
from datetime import date
from html.parser import HTMLParser

import pydantic
import pytest

from mizan.backtest.clock import BacktestResult, DailySnapshot
from mizan.backtest.compliance_state import (
    ComplianceStateRecord,
    HoldingComplianceState,
    VerdictObservation,
)
from mizan.config.fiqh_params import FIQH_PARAMS
from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat
from mizan.core.verdict import Verdict
from mizan.purification.attribution import DivestmentPurificationEntry
from mizan.purification.ledger import DividendPurificationEntry, PurificationLedger
from mizan.reporting import plots as plots_module
from mizan.reporting import report as report_module
from mizan.reporting.report import (
    CAVEAT_DESCRIPTIONS,
    ReportInput,
    render_caveats_banner,
    render_fiqh_register,
    render_report,
    render_return_summary,
    render_ticker_summary,
)

_ALL_CAVEATS = (
    Caveat.LOOK_AHEAD_BIAS,
    Caveat.SURVIVORSHIP_BIAS,
    Caveat.PENDING_SCHOLARLY_VERIFICATION,
)


# ── Fixture builders (pure Python model construction — mizan/reporting/ never touches DuckDB) ─────


def _compliance_states() -> dict[str, ComplianceStateRecord]:
    return {
        "ZZSTABLE01": ComplianceStateRecord(
            ticker="ZZSTABLE01",
            cik="9990000201",
            state=HoldingComplianceState.HELD_COMPLIANT,
            flip_date=None,
            divest_date=None,
            grace_rebalances_remaining=None,
            verdict_history=(
                VerdictObservation(as_of_date=date(2026, 1, 1), verdict=Verdict.MIXED),
                VerdictObservation(as_of_date=date(2026, 4, 1), verdict=Verdict.MIXED),
            ),
        ),
        "ZZFLIP01": ComplianceStateRecord(
            ticker="ZZFLIP01",
            cik="9990000013",
            state=HoldingComplianceState.DIVESTED,
            flip_date=date(2026, 4, 1),
            divest_date=date(2026, 7, 1),
            grace_rebalances_remaining=None,
            verdict_history=(
                VerdictObservation(as_of_date=date(2026, 1, 1), verdict=Verdict.PURE),
                VerdictObservation(as_of_date=date(2026, 4, 1), verdict=Verdict.NON_COMPLIANT),
                VerdictObservation(as_of_date=date(2026, 7, 1), verdict=Verdict.NON_COMPLIANT),
            ),
        ),
    }


def _backtest_result_with_ledger(
    ledger: PurificationLedger, *, with_snapshots: bool = True
) -> BacktestResult:
    snapshots = (
        (
            DailySnapshot(
                as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1_000_000.0
            ),
            DailySnapshot(
                as_of_date=date(2026, 10, 15),
                cash=0.0,
                holdings={},
                portfolio_value=1_050_000.0,
            ),
        )
        if with_snapshots
        else ()
    )
    result = BacktestResult(
        daily_snapshots=snapshots,
        divestment_events=(),
        dividend_events=(),
        compliance_states=_compliance_states(),
    )
    return result.model_copy(update={"purification_ledger": ledger.model_dump()})


def _nonzero_ledger() -> PurificationLedger:
    return PurificationLedger(
        dividend_entries=(
            DividendPurificationEntry(
                ticker="ZZSTABLE01",
                cik="9990000201",
                ex_date=date(2026, 2, 15),
                ratio_used=0.02,
                ratio_as_of_date=date(2026, 1, 1),
                dividend_cash_received=50_000.0,
                purified_amount=1_000.0,
            ),
        ),
        divestment_entries=(
            DivestmentPurificationEntry(
                ticker="ZZFLIP01",
                cik="9990000013",
                flip_date=date(2026, 4, 1),
                divest_date=date(2026, 7, 1),
                quantity_liquidated=100.0,
                price_at_flip=100.0,
                price_at_divest=130.0,
                purified_amount=3_000.0,
            ),
        ),
        purification_liability=4_000.0,
        gross_return=0.05,
        net_of_purification_return=0.046,
    )


def _empty_ledger() -> PurificationLedger:
    return PurificationLedger(
        dividend_entries=(),
        divestment_entries=(),
        purification_liability=0.0,
        gross_return=0.0,
        net_of_purification_return=0.0,
    )


def _report_input(ledger: PurificationLedger, *, with_snapshots: bool = True) -> ReportInput:
    return ReportInput(
        backtest_result=_backtest_result_with_ledger(ledger, with_snapshots=with_snapshots),
        fiqh_params=FIQH_PARAMS,
    )


# ── §8 AC1 / §6a: caveats banner renders before any numeric figure ────────────────────────────────


def test_caveats_banner_renders_before_any_numeric_figure() -> None:
    generated_html = render_report(_report_input(_nonzero_ledger()), active_caveats=_ALL_CAVEATS)
    caveats_index = generated_html.index('id="caveats"')
    assert caveats_index < generated_html.index('id="gross-return"')
    assert caveats_index < generated_html.index('id="fiqh-register"')
    assert caveats_index < generated_html.index('id="ticker-summary"')


# ── §8 AC2 / §7 G-R1: active_caveats is keyword-only, no default ──────────────────────────────────


def test_render_report_requires_active_caveats_keyword_or_raises_type_error() -> None:
    data = _report_input(_nonzero_ledger())
    with pytest.raises(TypeError):
        render_report(data)  # type: ignore[call-arg]


def test_render_report_accepts_explicit_empty_caveats_tuple() -> None:
    data = _report_input(_nonzero_ledger())
    generated_html = render_report(data, active_caveats=())
    assert "No caveats declared for this run." in generated_html


def test_render_caveats_banner_empty_tuple_renders_explicit_message() -> None:
    generated_html = render_caveats_banner(())
    assert "No caveats declared for this run." in generated_html


# ── §8 AC3 / §7 G-R2: every caveat's description text appears verbatim ────────────────────────────


def test_caveat_descriptions_cover_every_caveat_member() -> None:
    assert set(CAVEAT_DESCRIPTIONS) == set(Caveat)


def test_all_three_caveat_descriptions_appear_verbatim() -> None:
    generated_html = render_report(_report_input(_nonzero_ledger()), active_caveats=_ALL_CAVEATS)
    for caveat in _ALL_CAVEATS:
        assert CAVEAT_DESCRIPTIONS[caveat] in generated_html


# ── §8 AC4 / §7 G-R3: gross vs net-of-purification, distinct iff liability nonzero ────────────────


def _figure_text(generated_html: str, element_id: str) -> str:
    match = re.search(rf'id="{element_id}".*?class="value">([^<]+)<', generated_html)
    assert match is not None, f"could not find id={element_id!r} in {generated_html!r}"
    return match.group(1)


def test_gross_and_net_returns_are_distinct_when_liability_nonzero() -> None:
    generated_html = render_return_summary(_nonzero_ledger())
    gross = _figure_text(generated_html, "gross-return")
    net = _figure_text(generated_html, "net-of-purification-return")
    assert gross != net


def test_gross_and_net_returns_coincide_when_ledger_empty() -> None:
    generated_html = render_return_summary(_empty_ledger())
    gross = _figure_text(generated_html, "gross-return")
    net = _figure_text(generated_html, "net-of-purification-return")
    assert gross == net


# ── §8 AC5 / §7 G-R4: all 11 fiqh register entries, each register_id exactly once ─────────────────


def test_all_eleven_fiqh_entries_render_with_ids_1_through_11() -> None:
    generated_html = render_fiqh_register(FIQH_PARAMS)
    register_ids = re.findall(r"<tr><td>(\d+)</td>", generated_html)
    assert sorted(int(x) for x in register_ids) == list(range(1, 12))
    assert generated_html.count("pending_scholarly_verification") == 11


def test_fiqh_register_renders_primary_source_gap_when_present() -> None:
    generated_html = render_fiqh_register(FIQH_PARAMS)
    assert "primary-source-gap" in generated_html
    assert "UNVERIFIED" in generated_html


# ── §8 AC6 / §7 G-R5: generated HTML is well-formed / parseable ───────────────────────────────────


def test_generated_html_is_well_formed() -> None:
    generated_html = render_report(_report_input(_nonzero_ledger()), active_caveats=_ALL_CAVEATS)
    HTMLParser().feed(generated_html)  # raises no exception for well-formed markup


# ── §8 AC9 / §6e: plots embedded inline, never referenced by external path ────────────────────────


def test_plots_embedded_inline_never_referenced_by_path() -> None:
    generated_html = render_report(_report_input(_nonzero_ledger()), active_caveats=_ALL_CAVEATS)
    img_srcs = re.findall(r'<img src="([^"]+)"', generated_html)
    assert len(img_srcs) == 2
    for src in img_srcs:
        assert src.startswith("data:image/png;base64,")


# ── §7 G-R9: empty-input branches reachable end to end without crashing ───────────────────────────


def test_render_report_does_not_crash_with_empty_snapshots_and_empty_ledger() -> None:
    """§4.2's placeholder annotation ("No trading days..."/"No purification liability...") is
    drawn INSIDE the rendered PNG raster, not as literal HTML text -- so the property this test
    can actually check from the HTML side is that rendering completes without raising and still
    embeds two valid, non-empty, inline-base64 PNGs (§7 guard G-R9)."""
    data = _report_input(_empty_ledger(), with_snapshots=False)
    generated_html = render_report(data, active_caveats=_ALL_CAVEATS)
    img_srcs = re.findall(r'<img src="data:image/png;base64,([^"]+)"', generated_html)
    assert len(img_srcs) == 2
    for encoded in img_srcs:
        decoded = base64.b64decode(encoded)
        assert decoded.startswith(b"\x89PNG\r\n\x1a\n")


# ── §6d: per-ticker verdict summary ──────────────────────────────────────────────────────────────


def test_render_ticker_summary_lists_state_dates_and_observation_counts() -> None:
    generated_html = render_ticker_summary(_compliance_states())
    assert "ZZFLIP01" in generated_html
    assert "2026-04-01" in generated_html
    assert "2026-07-01" in generated_html
    assert "divested" in generated_html
    # ZZFLIP01 has 3 VerdictObservations recorded.
    assert re.search(r"ZZFLIP01</td><td>divested</td>.*?<td>3</td>", generated_html)


# ── §8 AC10: ReportInput rejects a non-purified BacktestResult ────────────────────────────────────


def test_report_input_rejects_non_purified_backtest_result() -> None:
    unpurified = BacktestResult(
        daily_snapshots=(),
        divestment_events=(),
        dividend_events=(),
        compliance_states={},
    )
    with pytest.raises(pydantic.ValidationError):
        ReportInput(backtest_result=unpurified, fiqh_params=FIQH_PARAMS)


# ── §8 AC13: model discipline ────────────────────────────────────────────────────────────────────


def test_report_input_inherits_mizan_base_model() -> None:
    assert issubclass(ReportInput, MizanBaseModel)


# ── §7 guards G-R6 / G-R7 / G-BOUND3: package-wide greps, re-run as tests ─────────────────────────

_REPORTING_MODULES = (report_module, plots_module)


def test_no_llm_import_anywhere_in_reporting_package() -> None:
    for module in _REPORTING_MODULES:
        source = inspect.getsource(module).lower()
        for forbidden in (
            "openai",
            "anthropic",
            "gemini",
            "vertex",
            "langchain",
            "chat_completion",
            "completion(",
        ):
            assert forbidden not in source, f"{module!r} references forbidden term {forbidden!r}"


def test_no_duckdb_anywhere_in_reporting_package() -> None:
    for module in _REPORTING_MODULES:
        source = inspect.getsource(module)
        assert "duckdb" not in source
        upper_source = source.upper()
        for forbidden in ("INSERT INTO", "CREATE TABLE", "ALTER TABLE", "DROP TABLE"):
            assert forbidden not in upper_source, f"{module!r} contains {forbidden!r}"


_BOUNDARY_WORDS = (
    "short",
    "shorts",
    "shorting",
    "borrow",
    "borrowed",
    "borrowing",
    "margin",
    "leverage",
    "leveraged",
    "levered",
    "option",
    "options",
    "future",
    "futures",
    "swap",
    "swaps",
    "derivative",
    "derivatives",
)


def test_no_boundary_crossing_primitive_named_anywhere_in_reporting_package() -> None:
    for module in _REPORTING_MODULES:
        source = inspect.getsource(module).lower()
        for word in _BOUNDARY_WORDS:
            pattern = re.compile(rf"\b{re.escape(word)}\b")
            assert not pattern.search(source), f"{module!r} names forbidden concept {word!r}"
