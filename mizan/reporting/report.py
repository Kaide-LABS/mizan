"""mizan/reporting/report.py — static-HTML generation, the caveat-mandatory render function.

Implements PHASE_7_SPEC.md §3, §4.1, §6a, §6b, §6c, §6d, §6e.

`render_report` is THE canonical, singular Phase 7 entry point — this phase's analogue of
`screen()`/`run_backtest()`/`purify_backtest_result()`. Every dynamic string this module
interpolates into HTML output passes through `html.escape()` (§6e) — there is no free-text
generation step anywhere in this module; every string is either a fixed template fragment or a
direct, escaped formatting of an already-computed, already-typed value from an earlier phase.
"""

from __future__ import annotations

import base64
import html
from typing import TYPE_CHECKING

from pydantic import model_validator

from mizan.backtest.clock import BacktestResult
from mizan.config.fiqh_params import FiqhParams
from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat
from mizan.purification.ledger import PurificationLedger
from mizan.reporting import plots

if TYPE_CHECKING:
    from mizan.backtest.compliance_state import ComplianceStateRecord


def _escape(value: str) -> str:
    """`html.escape(value, quote=False)` — escapes `&`/`<`/`>` (the characters that can actually
    break HTML markup, §6e, §7 guard G-R5) but leaves quote characters (`'`/`"`) untouched. Every
    value this module escapes is interpolated into element TEXT CONTENT (a `<p>`/`<td>`/`<div>`
    body), never into an HTML attribute value — quote-escaping is only load-bearing inside an
    attribute value, and it would otherwise turn an apostrophe in, e.g., a caveat description or a
    fiqh `source` citation into a literal `&#x27;` entity, breaking §8 AC3's own verbatim-substring
    requirement (`CAVEAT_DESCRIPTIONS[caveat] in generated_html`) for no HTML-safety benefit."""
    return html.escape(value, quote=False)


class ReportInput(MizanBaseModel):
    """Everything `render_report` needs to render one report, bundled into one typed value.

    Deliberately **not** wrapped in a `mizan.core.caveats.ResultEnvelope`: `active_caveats` lives
    as its own required, keyword-only parameter on `render_report` itself (§6a), not as a field on
    this model or on an enclosing envelope — that placement, not this one, is the mechanism that
    makes `ULTIMATE_PRD.md` §2.2's "no code path renders a number without its caveat set" a
    call-time (`TypeError`-raising), not merely a construction-time (`pydantic.ValidationError`-
    raising), guarantee.
    """

    backtest_result: BacktestResult
    """The already-purified result — `purification_ledger` MUST be populated (i.e. not `None`),
    the output of `mizan.purification.ledger.purify_backtest_result`, never a raw,
    pre-purification `run_backtest()` result. Enforced below, not merely hoped for."""
    fiqh_params: FiqhParams
    """The register actually used to produce `backtest_result` — rendered in full (§6b) as the
    honesty-surface requirement `MASTER_PRD.md` §10 and `ULTIMATE_PRD.md` §1 both name."""

    @model_validator(mode="after")
    def _purification_ledger_is_populated(self) -> ReportInput:
        """`backtest_result.purification_ledger is None` means `purify_backtest_result` was never
        called — a Phase-5-only, pre-Phase-6 result. Rendering a report from one would silently
        omit the gross-vs-net-of-purification distinction §6c requires to be structurally present;
        this is caught here, at construction, rather than left for `render_report`'s own body to
        discover via a `None`-shaped `PurificationLedger.model_validate` failure."""
        if self.backtest_result.purification_ledger is None:
            raise ValueError(
                "ReportInput.backtest_result.purification_ledger is None — pass the output of "
                "purify_backtest_result(), never a raw run_backtest() result"
            )
        return self


#: The honesty-surface text registry — one entry per `mizan.core.caveats.Caveat` member,
#: completeness-checked below at import time (§3.2, §7 guard G-R2).
CAVEAT_DESCRIPTIONS: dict[Caveat, str] = {
    Caveat.LOOK_AHEAD_BIAS: (
        "Look-ahead bias: screen(ticker, as_of_date) uses the most-recently-filed fact as of "
        "as_of_date rather than true filing-lag-corrected point-in-time data. EDGAR facts "
        "routinely carry a multi-year gap between a reporting period's end date and its actual "
        "filing date — this backtest's verdicts may be more favorable than a strictly "
        "point-in-time reconstruction would produce."
    ),
    Caveat.SURVIVORSHIP_BIAS: (
        'Survivorship bias: the ticker universe supplied to this run is "companies that exist '
        'today", which silently excludes anything delisted or gone to zero over the backtest '
        "window. This backtest cannot see, and does not account for, any company that failed or "
        "was delisted during the period it covers."
    ),
    Caveat.PENDING_SCHOLARLY_VERIFICATION: (
        "Pending scholarly verification: at least one fiqh judgment call governing this run's "
        "screening, backtest, and purification logic is an engineering-team default, not a "
        "scholar-ratified ruling. The full register, with every entry's current status, is "
        "rendered below."
    ),
}
assert set(CAVEAT_DESCRIPTIONS) == set(Caveat), (
    "CAVEAT_DESCRIPTIONS must cover every mizan.core.caveats.Caveat member exactly — a caveat with "
    "no rendered description would be a silent gap in the exact honesty surface this module exists "
    "to guarantee"
)


def render_caveats_banner(active_caveats: tuple[Caveat, ...]) -> str:
    """Renders one `<section id="caveats">` block, one `<p>` per caveat in `active_caveats`, each
    containing `CAVEAT_DESCRIPTIONS[caveat]` verbatim, `html.escape()`-d. An empty `active_caveats`
    tuple renders the section with an explicit "No caveats declared for this run." line rather
    than an empty, ambiguous-looking `<section>` — the empty case is a genuine, valid input and
    must render honestly, not silently disappear (§4.1, §6a).
    """
    if not active_caveats:
        body = "<p>No caveats declared for this run.</p>"
    else:
        body = "".join(
            f"<p>{_escape(CAVEAT_DESCRIPTIONS[caveat])}</p>" for caveat in active_caveats
        )
    return f'<section id="caveats"><h2>Caveats</h2>{body}</section>'


def render_fiqh_register(fiqh_params: FiqhParams) -> str:
    """Renders one `<section id="fiqh-register">` table, one row per `FiqhParams` field, sorted by
    `.register_id` (never relying on `model_fields`' own declaration-order coincidence). Each row
    shows `register_id`, the field's own attribute name, `value` (`str()`-formatted), `source`,
    `primary_source_gap` (rendered as its own labelled line within the source cell only when
    non-empty — never as an empty cell), and `status.value`. Asserts exactly 11 rows are produced
    (§6b, §7 guard G-R4).
    """
    entries = sorted(
        ((name, getattr(fiqh_params, name)) for name in type(fiqh_params).model_fields),
        key=lambda item: item[1].register_id,
    )
    if len(entries) != 11:
        raise AssertionError(
            f"render_fiqh_register: expected exactly 11 FiqhParams fields, got {len(entries)}"
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
        '<section id="fiqh-register"><h2>Fiqh Judgment-Call Register</h2>'
        "<table><thead><tr><th>#</th><th>Parameter</th><th>Value</th><th>Source</th>"
        "<th>Status</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></section>"
    )


def render_return_summary(ledger: PurificationLedger) -> str:
    """Renders one `<section id="returns">` containing two SEPARATE, distinctly-`id`'d `<div>`
    elements — `id="gross-return"` and `id="net-of-purification-return"` — each showing its own
    label and its own `.6f`-formatted value (matching `mizan/cli/backtest.py`'s own established
    `.6f` precedent), never combined into one figure or one sentence (§6c, §7 guard G-R3).
    """
    return (
        '<section id="returns"><h2>Returns</h2>'
        f'<div id="gross-return"><span class="label">Gross return:</span> '
        f'<span class="value">{ledger.gross_return:.6f}</span></div>'
        f'<div id="net-of-purification-return"><span class="label">Net-of-purification return:'
        f'</span> <span class="value">{ledger.net_of_purification_return:.6f}</span></div>'
        f'<div id="purification-liability"><span class="label">Purification liability:</span> '
        f'<span class="value">{ledger.purification_liability:.2f}</span></div>'
        "</section>"
    )


def render_ticker_summary(compliance_states: dict[str, ComplianceStateRecord]) -> str:
    """Renders one `<section id="ticker-summary">` table, one row per ticker in
    `compliance_states` (sorted by ticker for determinism), showing final `state`,
    `flip_date`/`divest_date` (blank if `None`), and the number of `verdict_history` observations
    recorded — built entirely from Phase 5's own already-computed `ComplianceStateRecord` values
    (§6d), no re-invocation of `screen()`, no new computation.
    """
    rows: list[str] = []
    for ticker in sorted(compliance_states):
        record = compliance_states[ticker]
        flip = record.flip_date.isoformat() if record.flip_date is not None else ""
        divest = record.divest_date.isoformat() if record.divest_date is not None else ""
        rows.append(
            "<tr>"
            f"<td>{_escape(ticker)}</td>"
            f"<td>{_escape(record.state.value)}</td>"
            f"<td>{_escape(flip)}</td>"
            f"<td>{_escape(divest)}</td>"
            f"<td>{len(record.verdict_history)}</td>"
            "</tr>"
        )
    table_rows = "".join(rows)
    return (
        '<section id="ticker-summary"><h2>Per-Ticker Verdict Summary</h2>'
        "<table><thead><tr><th>Ticker</th><th>State</th><th>Flip Date</th><th>Divest Date</th>"
        "<th>Verdict Observations</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></section>"
    )


def render_purification_detail(ledger: PurificationLedger) -> str:
    """Renders one `<section id="purification-detail">`: the `purification_liability` total, then
    one table row per `DividendPurificationEntry` (ticker, ex_date, ratio_used, purified_amount)
    and one table row per `DivestmentPurificationEntry` (ticker, flip_date, divest_date,
    purified_amount) — every ledger entry Phase 6 computed, none summarized away.
    """
    dividend_rows = "".join(
        "<tr>"
        f"<td>{_escape(entry.ticker)}</td>"
        f"<td>{entry.ex_date.isoformat()}</td>"
        f"<td>{entry.ratio_used:.6f}</td>"
        f"<td>{entry.purified_amount:.2f}</td>"
        "</tr>"
        for entry in ledger.dividend_entries
    )
    divestment_rows = "".join(
        "<tr>"
        f"<td>{_escape(entry.ticker)}</td>"
        f"<td>{entry.flip_date.isoformat()}</td>"
        f"<td>{entry.divest_date.isoformat()}</td>"
        f"<td>{entry.purified_amount:.2f}</td>"
        "</tr>"
        for entry in ledger.divestment_entries
    )
    return (
        '<section id="purification-detail"><h2>Purification Ledger Detail</h2>'
        f"<p>Purification liability: {ledger.purification_liability:.2f}</p>"
        "<h3>Dividend Purification Entries</h3>"
        "<table><thead><tr><th>Ticker</th><th>Ex-Date</th><th>Ratio Used</th>"
        "<th>Purified Amount</th></tr></thead>"
        f"<tbody>{dividend_rows}</tbody></table>"
        "<h3>Divestment Purification Entries</h3>"
        "<table><thead><tr><th>Ticker</th><th>Flip Date</th><th>Divest Date</th>"
        "<th>Purified Amount</th></tr></thead>"
        f"<tbody>{divestment_rows}</tbody></table>"
        "</section>"
    )


def _render_plots_section(equity_curve_png: bytes, purification_by_ticker_png: bytes) -> str:
    """One `<section id="plots">` with both plots inline, base64-encoded, never referenced by
    external file path (§6e, §7 guard G-R9, §8 AC9)."""
    equity_b64 = base64.b64encode(equity_curve_png).decode("ascii")
    purification_b64 = base64.b64encode(purification_by_ticker_png).decode("ascii")
    return (
        '<section id="plots"><h2>Plots</h2>'
        '<figure id="equity-curve-plot">'
        "<figcaption>Gross vs Net-of-Purification Portfolio Value</figcaption>"
        f'<img src="data:image/png;base64,{equity_b64}" '
        'alt="Equity curve: gross vs net-of-purification portfolio value"></figure>'
        '<figure id="purification-by-ticker-plot">'
        "<figcaption>Purification Liability by Ticker</figcaption>"
        f'<img src="data:image/png;base64,{purification_b64}" '
        'alt="Purification liability by ticker"></figure>'
        "</section>"
    )


def render_report(data: ReportInput, *, active_caveats: tuple[Caveat, ...]) -> str:
    """THE canonical, singular Phase 7 entry point. Returns a complete, self-contained HTML
    document as a `str` (UTF-8-encodable, no external file references — §6e).

    `active_caveats` is **keyword-only and carries no default** (note the bare `*` before it in the
    signature). This is the mechanism, stated precisely rather than left to convention:
    `render_report(data)` — omitting the keyword entirely — raises `TypeError: render_report()
    missing 1 required keyword-only argument: 'active_caveats'` at the CALL SITE, before this
    function's own body ever executes, and `mypy --strict` flags any call site missing it as a
    static error too (§7 guard G-R1, §8 AC2). `render_report(data, active_caveats=())` — an
    explicit empty tuple — is a valid, if unusual, call.

    Builds the document in the fixed section order §6a specifies (caveats banner first, before any
    numeric figure appears anywhere in the output): the caveat banner (§6a), the full 11-row fiqh
    judgment-call register (§6b), the two distinctly-labelled return figures (§6c), the per-ticker
    compliance/verdict summary (§6d), the full purification-ledger entry detail, and both embedded
    plots (§6c/§6d, base64-inlined per §6e). Every interpolated dynamic string passes through
    `html.escape()` (§6e).
    """
    ledger = PurificationLedger.model_validate(data.backtest_result.purification_ledger)

    caveats_html = render_caveats_banner(active_caveats)
    fiqh_html = render_fiqh_register(data.fiqh_params)
    returns_html = render_return_summary(ledger)
    ticker_html = render_ticker_summary(data.backtest_result.compliance_states)
    purification_html = render_purification_detail(ledger)
    plots_html = _render_plots_section(
        plots.render_equity_curve_plot(data.backtest_result.daily_snapshots, ledger),
        plots.render_purification_by_ticker_plot(ledger),
    )

    body = caveats_html + fiqh_html + returns_html + ticker_html + purification_html + plots_html
    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8"><title>Mizan Backtest Report</title></head>'
        f"<body><h1>Mizan Backtest Report</h1>{body}</body></html>"
    )
