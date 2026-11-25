"""mizan/crypto/report.py — the crypto report's render primitives.

Implements ``docs/crypto/PHASE_6_SPEC.md`` §A4 (Part A). A new, parallel module rather than a
reuse of ``mizan.reporting.report.ReportInput``/``render_report``: ``ReportInput`` requires an
equity ``FiqhParams`` (11 fields) and a ``BacktestResult`` whose ``purification_ledger`` is
non-``None``, while ``CryptoFiqhParams`` has exactly 4 fields and ``CryptoBacktestResult`` carries
no ``purification_ledger`` field at all.
"""

from __future__ import annotations

import html

from mizan.core.base import MizanBaseModel
from mizan.crypto.backtest import CryptoBacktestResult
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS, CryptoFiqhParams
from mizan.crypto.screening import CryptoTokenVerdict


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
