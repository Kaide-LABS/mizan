"""mizan/crypto/report.py — the crypto report's render primitives.

Implements ``docs/crypto/PHASE_6_SPEC.md`` §A4 (Part A). A new, parallel module rather than a
reuse of ``mizan.reporting.report.ReportInput``/``render_report``: ``ReportInput`` requires an
equity ``FiqhParams`` (11 fields) and a ``BacktestResult`` whose ``purification_ledger`` is
non-``None``, while ``CryptoFiqhParams`` has exactly 4 fields and ``CryptoBacktestResult`` carries
no ``purification_ledger`` field at all.
"""

from __future__ import annotations

import base64
import html

from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat
from mizan.crypto.backtest import CryptoBacktestResult
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS, CryptoFiqhParams, CustodyModel
from mizan.crypto.screening import CryptoTokenVerdict
from mizan.reporting.plots import render_crypto_equity_curve_plot
from mizan.reporting.report import render_caveats_banner


def _escape(value: str) -> str:
    """``html.escape(value, quote=False)`` — this module's own copy of the escaping discipline
    ``mizan.reporting.report._escape`` already established, not an import of that private
    helper across a package boundary."""
    return html.escape(value, quote=False)


class CryptoReportInput(MizanBaseModel):
    """Everything ``render_crypto_report`` needs to render one crypto report, bundled into one
    typed value. ``token_verdicts`` carries all 23 named tokens (the 14-token ``CRYPTO_UNIVERSE``
    plus the 9-token ``DEFAULT_REJECT_LIST``), the same set ``screen_universe()`` iterates."""

    backtest_result: CryptoBacktestResult
    fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS
    token_verdicts: tuple[CryptoTokenVerdict, ...]


def render_crypto_fiqh_register(fiqh_params: CryptoFiqhParams) -> str:
    """Renders one ``<section id="fiqh-register">`` table, one row per ``CryptoFiqhParams`` field,
    sorted by ``.register_id``. Asserts exactly 4 rows are produced."""
    entries = sorted(
        ((name, getattr(fiqh_params, name)) for name in type(fiqh_params).model_fields),
        key=lambda item: item[1].register_id,
    )
    if len(entries) != 4:
        raise AssertionError(
            f"render_crypto_fiqh_register: expected exactly 4 fields, got {len(entries)}"
        )
    rows: list[str] = []
    for name, param in entries:
        gap_html = (
            f'<div class="primary-source-gap">{_escape(param.primary_source_gap)}</div>'
            if param.primary_source_gap
            else ""
        )
        rows.append(
            "<tr>"
            f"<td>{param.register_id}</td>"
            f"<td>{_escape(name)}</td>"
            f"<td>{_escape(str(param.value))}</td>"
            f"<td>{_escape(param.source)}{gap_html}</td>"
            f"<td>{_escape(param.status.value)}</td>"
            "</tr>"
        )
    table_rows = "".join(rows)
    return (
        '<section id="fiqh-register"><h2>Crypto Fiqh Judgment-Call Register</h2>'
        "<table><thead><tr><th>#</th><th>Parameter</th><th>Value</th><th>Source</th>"
        "<th>Status</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></section>"
    )


def render_crypto_token_verdicts(token_verdicts: tuple[CryptoTokenVerdict, ...]) -> str:
    """Renders one ``<section id="token-verdicts">`` table, one row per ``CryptoTokenVerdict``
    (ticker, verdict, category, reason detail), sorted by ticker."""
    rows = "".join(
        "<tr>"
        f"<td>{_escape(verdict.ticker)}</td>"
        f"<td>{_escape(verdict.verdict.value)}</td>"
        f"<td>{_escape(verdict.category.value)}</td>"
        f"<td>{_escape(verdict.reason.detail)}</td>"
        "</tr>"
        for verdict in sorted(token_verdicts, key=lambda v: v.ticker)
    )
    return (
        '<section id="token-verdicts"><h2>Token Verdicts</h2>'
        "<table><thead><tr><th>Ticker</th><th>Verdict</th><th>Category</th>"
        "<th>Reason</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></section>"
    )


def render_crypto_backtest_summary(result: CryptoBacktestResult) -> str:
    """Renders one ``<section id="backtest-summary">``: the literal ``strategy_label`` (always
    ``"baseline"``), the final portfolio value (or a "no trading days" sentence if
    ``daily_snapshots`` is empty), the comma-joined ``excluded_tickers``, and ``cost_params``'
    two rates to 4 decimal places (PHASE_6_SPEC.md §B1)."""
    if result.daily_snapshots:
        final_value_html = f"{result.daily_snapshots[-1].portfolio_value:.2f}"
    else:
        final_value_html = "No trading days in this backtest window."
    excluded_html = _escape(", ".join(result.excluded_tickers)) if result.excluded_tickers else ""
    return (
        '<section id="backtest-summary"><h2>Backtest Summary</h2>'
        f'<p>Strategy: {_escape(result.strategy_label)}</p>'
        f"<p>Final portfolio value: {final_value_html}</p>"
        f"<p>Excluded tickers: {excluded_html}</p>"
        f"<p>Taker fee rate: {result.cost_params.taker_fee_rate:.4f}</p>"
        f"<p>Slippage rate: {result.cost_params.slippage_rate:.4f}</p>"
        "</section>"
    )


def resolve_crypto_report_caveats(
    backtest_caveats: tuple[Caveat, ...], fiqh_params: CryptoFiqhParams
) -> tuple[Caveat, ...]:
    """Composes the backtest's own ``active_caveats`` with ``Caveat.CUSTODY_FREEZE_RISK``, added
    only when ``fiqh_params.custody_model.value`` is ``CustodyModel.EXCHANGE_QABD_HUKMI`` — a pure
    function, no I/O, independent of ``render_crypto_report`` itself (PHASE_6_SPEC.md §B1)."""
    if fiqh_params.custody_model.value is CustodyModel.EXCHANGE_QABD_HUKMI:
        return (*backtest_caveats, Caveat.CUSTODY_FREEZE_RISK)
    return backtest_caveats


def _render_crypto_plots_section(equity_curve_png: bytes) -> str:
    """One ``<section id="plots">`` with the single crypto equity-curve plot inline, base64-encoded
    — mirrors ``mizan.reporting.report._render_plots_section``'s own embedding discipline, but with
    exactly one figure (crypto has no gross-vs-net-of-purification split to plot a second line
    for, PHASE_6_SPEC.md §B2)."""
    equity_b64 = base64.b64encode(equity_curve_png).decode("ascii")
    return (
        '<section id="plots"><h2>Plots</h2>'
        '<figure id="equity-curve-plot">'
        "<figcaption>Portfolio Equity Curve</figcaption>"
        f'<img src="data:image/png;base64,{equity_b64}" '
        'alt="Portfolio equity curve"></figure>'
        "</section>"
    )


def render_crypto_report(
    data: CryptoReportInput, *, active_caveats: tuple[Caveat, ...]
) -> str:
    """THE canonical crypto-report entry point. ``active_caveats`` is keyword-only, with no
    default — ``render_crypto_report(data)`` raises ``TypeError`` at the call site, before this
    function's own body ever runs, mirroring ``mizan.reporting.report.render_report``'s own
    contract exactly (PHASE_6_SPEC.md §B1). Returns a complete, self-contained
    ``<!DOCTYPE html>…</html>`` document string.

    Builds the document in a fixed section order — caveats first, before any numeric figure —
    then the fiqh register, the token verdicts, the backtest summary, and the embedded plot.
    """
    caveats_html = render_caveats_banner(active_caveats)
    fiqh_html = render_crypto_fiqh_register(data.fiqh_params)
    verdicts_html = render_crypto_token_verdicts(data.token_verdicts)
    summary_html = render_crypto_backtest_summary(data.backtest_result)
    plots_html = _render_crypto_plots_section(
        render_crypto_equity_curve_plot(data.backtest_result.daily_snapshots)
    )

    body = caveats_html + fiqh_html + verdicts_html + summary_html + plots_html
    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8"><title>Mizan Crypto Report</title></head>'
        f"<body><h1>Mizan Crypto Report</h1>{body}</body></html>"
    )
