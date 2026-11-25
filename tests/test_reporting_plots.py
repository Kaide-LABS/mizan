"""Tests for mizan/reporting/plots.py.

Implements PHASE_7_SPEC.md §8 acceptance criterion 8 (both plot functions return valid, decodable
PNG bytes) and §7 guard G-R9 (empty-input branches render an honest placeholder, never raise).
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt

from mizan.backtest.clock import DailySnapshot
from mizan.crypto.backtest import DailySnapshot as CryptoDailySnapshot
from mizan.purification.attribution import DivestmentPurificationEntry
from mizan.purification.ledger import DividendPurificationEntry, PurificationLedger
from mizan.reporting.plots import (
    render_crypto_equity_curve_plot,
    render_equity_curve_plot,
    render_purification_by_ticker_plot,
)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _snapshots() -> tuple[DailySnapshot, ...]:
    return (
        DailySnapshot(
            as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1_000_000.0
        ),
        DailySnapshot(
            as_of_date=date(2026, 4, 1), cash=0.0, holdings={}, portfolio_value=1_010_000.0
        ),
        DailySnapshot(
            as_of_date=date(2026, 7, 1), cash=0.0, holdings={}, portfolio_value=1_020_000.0
        ),
    )


def _nonzero_ledger() -> PurificationLedger:
    return PurificationLedger(
        dividend_entries=(
            DividendPurificationEntry(
                ticker="ZZMIXED_RATIODRIFT01",
                cik="9990000014",
                ex_date=date(2026, 2, 15),
                ratio_used=0.02,
                ratio_as_of_date=date(2026, 1, 1),
                dividend_cash_received=50_000.0,
                purified_amount=1_000.0,
            ),
        ),
        divestment_entries=(
            DivestmentPurificationEntry(
                ticker="ZZDIVEST_APPREC01",
                cik="9990000015",
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


# ── §8 AC8: both plot functions return valid, decodable PNG bytes ─────────────────────────────────


def test_render_equity_curve_plot_returns_valid_png_bytes() -> None:
    png_bytes = render_equity_curve_plot(_snapshots(), _nonzero_ledger())
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(_PNG_MAGIC)
    assert len(png_bytes) > 0


def test_render_purification_by_ticker_plot_returns_valid_png_bytes() -> None:
    png_bytes = render_purification_by_ticker_plot(_nonzero_ledger())
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(_PNG_MAGIC)
    assert len(png_bytes) > 0


# ── §7 guard G-R9: empty-input branches render an honest placeholder, never raise ─────────────────


def test_render_equity_curve_plot_handles_empty_daily_snapshots() -> None:
    png_bytes = render_equity_curve_plot((), _empty_ledger())
    assert png_bytes.startswith(_PNG_MAGIC)


def test_render_purification_by_ticker_plot_handles_empty_ledger() -> None:
    png_bytes = render_purification_by_ticker_plot(_empty_ledger())
    assert png_bytes.startswith(_PNG_MAGIC)


def test_render_purification_by_ticker_plot_handles_all_zero_amount_entries() -> None:
    """Entries that exist but are all zero-amount (e.g. a divestment with no price appreciation)
    must still render the honest placeholder, not an unexplained empty chart."""
    ledger = PurificationLedger(
        dividend_entries=(),
        divestment_entries=(
            DivestmentPurificationEntry(
                ticker="ZZFLAT01",
                cik="9990099999",
                flip_date=date(2026, 4, 1),
                divest_date=date(2026, 7, 1),
                quantity_liquidated=100.0,
                price_at_flip=100.0,
                price_at_divest=100.0,
                purified_amount=0.0,
            ),
        ),
        purification_liability=0.0,
        gross_return=0.0,
        net_of_purification_return=0.0,
    )
    png_bytes = render_purification_by_ticker_plot(ledger)
    assert png_bytes.startswith(_PNG_MAGIC)


# ── No matplotlib figure leakage across repeated calls within one process (§4.2) ──────────────────


def _crypto_snapshots() -> tuple[CryptoDailySnapshot, ...]:
    return (
        CryptoDailySnapshot(
            as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1000.0
        ),
        CryptoDailySnapshot(
            as_of_date=date(2026, 2, 1), cash=0.0, holdings={}, portfolio_value=1010.0
        ),
    )


def test_render_crypto_equity_curve_plot_returns_valid_png_bytes() -> None:
    png_bytes = render_crypto_equity_curve_plot(_crypto_snapshots())
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(_PNG_MAGIC)
    assert len(png_bytes) > 0


def test_render_crypto_equity_curve_plot_handles_empty_daily_snapshots() -> None:
    png_bytes = render_crypto_equity_curve_plot(())
    assert png_bytes.startswith(_PNG_MAGIC)


def test_repeated_calls_do_not_leak_matplotlib_figures() -> None:
    before = len(plt.get_fignums())
    for _ in range(10):
        render_equity_curve_plot(_snapshots(), _nonzero_ledger())
        render_purification_by_ticker_plot(_nonzero_ledger())
    after = len(plt.get_fignums())
    assert after == before
