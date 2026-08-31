"""mizan/reporting/plots.py — matplotlib PNG-rendering functions.

Implements PHASE_7_SPEC.md §2.1, §4.2, §6c, §6d.

`matplotlib.use("Agg")` is called before `pyplot` is imported, at module import time (§2.1): Mizan
is a headless, single-user batch/CLI tool — matplotlib's default backend selection can, on some
platforms, attempt to bind an interactive GUI toolkit that is not installed in a non-interactive
process. `Agg` is matplotlib's own non-interactive, pure-raster PNG backend; setting it explicitly
removes this failure mode structurally.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from datetime import date

    from mizan.backtest.clock import DailySnapshot
    from mizan.purification.ledger import PurificationLedger


def _cumulative_purification_liability_as_of(ledger: PurificationLedger, as_of_date: date) -> float:
    """§6c's own day-by-day reconstruction, finally built: the running purification liability
    accrued as of `as_of_date`, summed from already-dated Phase 6 ledger entries. Computed fresh,
    privately, every call — never a persisted intermediate series (§9's own non-goal)."""
    dividend_total = sum(
        entry.purified_amount for entry in ledger.dividend_entries if entry.ex_date <= as_of_date
    )
    divestment_total = sum(
        entry.purified_amount
        for entry in ledger.divestment_entries
        if entry.divest_date <= as_of_date
    )
    return dividend_total + divestment_total


def render_equity_curve_plot(
    daily_snapshots: tuple[DailySnapshot, ...], ledger: PurificationLedger
) -> bytes:
    """Renders one PNG (via the `Agg` backend): gross portfolio value (`daily_snapshots[i].
    portfolio_value` at each `as_of_date`) plotted against net-of-purification portfolio value (the
    same series, minus the cumulative purification liability accrued as of each date, §6c). Two
    labelled lines on one figure, `x` axis = `as_of_date`, `y` axis = portfolio value.

    `daily_snapshots == ()` renders a single-panel figure with an explicit "No trading days in this
    backtest window." annotation instead of raising (§7 guard G-R9).
    """
    figure, axes = plt.subplots()
    if not daily_snapshots:
        axes.text(
            0.5,
            0.5,
            "No trading days in this backtest window.",
            ha="center",
            va="center",
            transform=axes.transAxes,
        )
        axes.set_axis_off()
    else:
        dates = [snapshot.as_of_date for snapshot in daily_snapshots]
        gross_values = [snapshot.portfolio_value for snapshot in daily_snapshots]
        net_values = [
            snapshot.portfolio_value
            - _cumulative_purification_liability_as_of(ledger, snapshot.as_of_date)
            for snapshot in daily_snapshots
        ]
        axes.plot(dates, gross_values, label="Gross portfolio value")
        axes.plot(dates, net_values, label="Net-of-purification portfolio value")
        axes.set_xlabel("Date")
        axes.set_ylabel("Portfolio value")
        axes.legend()
        figure.autofmt_xdate()

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    plt.close(figure)
    return buffer.getvalue()


def render_purification_by_ticker_plot(ledger: PurificationLedger) -> bytes:
    """Renders one PNG: one bar per ticker with any nonzero purification contribution, `y` =
    `sum(entry.purified_amount for entry in ledger.dividend_entries if entry.ticker == t) +
    sum(entry.purified_amount for entry in ledger.divestment_entries if entry.ticker == t)`,
    tickers sorted alphabetically for determinism.

    An empty ledger, or a ledger whose entries are all zero-amount, renders a single-panel figure
    with an explicit "No purification liability in this run." annotation instead of raising or
    rendering an empty axes with no explanation (§7 guard G-R9).
    """
    totals: dict[str, float] = {}
    for dividend_entry in ledger.dividend_entries:
        totals[dividend_entry.ticker] = (
            totals.get(dividend_entry.ticker, 0.0) + dividend_entry.purified_amount
        )
    for divestment_entry in ledger.divestment_entries:
        totals[divestment_entry.ticker] = (
            totals.get(divestment_entry.ticker, 0.0) + divestment_entry.purified_amount
        )
    nonzero_tickers = sorted(ticker for ticker, total in totals.items() if total != 0.0)

    figure, axes = plt.subplots()
    if not nonzero_tickers:
        axes.text(
            0.5,
            0.5,
            "No purification liability in this run.",
            ha="center",
            va="center",
            transform=axes.transAxes,
        )
        axes.set_axis_off()
    else:
        values = [totals[ticker] for ticker in nonzero_tickers]
        axes.bar(nonzero_tickers, values)
        axes.set_xlabel("Ticker")
        axes.set_ylabel("Purification liability")
        axes.tick_params(axis="x", labelrotation=45)

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    plt.close(figure)
    return buffer.getvalue()
