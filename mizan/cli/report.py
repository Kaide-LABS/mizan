"""mizan/cli/report.py — the `report` subcommand, completing ingest|screen|backtest|report.

Implements PHASE_7_SPEC.md §4.3.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from mizan.backtest.clock import BacktestResult, run_backtest
from mizan.backtest.strategy import EqualWeightStrategy
from mizan.config.fiqh_params import FIQH_PARAMS
from mizan.data import db
from mizan.data.ingest_edgar import CikResolutionError
from mizan.purification.ledger import purify_backtest_result
from mizan.reporting.report import ReportInput, render_report
from mizan.screening.business_activity import SicResolutionError, load_override_map
from mizan.screening.verdict import InsufficientDataError, NotNormalizedError

#: Per-ticker-shaped exceptions `mizan screen`/`mizan backtest` catch, reused at the same
#: whole-backtest level `mizan/cli/backtest.py`'s own `run()` already established (§4.3).
_HALTING_ERRORS = (
    CikResolutionError,
    SicResolutionError,
    NotNormalizedError,
    InsufficientDataError,
)


def _parse_iso_date(value: str) -> date:
    """argparse `type=` callback: parse a `YYYY-MM-DD` string into a `date`."""
    return date.fromisoformat(value)


def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Registers `report --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --initial-cash FLOAT --db-path PATH --cache-dir PATH
    [--overrides-path PATH] --output-path PATH`. Every flag through `--overrides-path` is
    identical, flag-for-flag, to `mizan backtest`'s own `add_subparser` (`mizan/cli/backtest.py`,
    unmodified by this phase) — same candidate-universe semantics, same optional-overrides
    posture. `--output-path` is the one new flag: where the generated, self-contained HTML file is
    written. No `--no-plots` or similar suppression flag — a report that silently omits its own
    plots on request is not a reporting concern this phase's own scope needs (§9).
    """
    parser = subparsers.add_parser(
        "report", help="Run a backtest and render a self-contained static HTML report."
    )
    parser.add_argument(
        "--ticker",
        action="append",
        required=True,
        dest="tickers",
        metavar="TICKER",
        help="Candidate ticker symbol. May be repeated.",
    )
    parser.add_argument(
        "--start-date", required=True, type=_parse_iso_date, help="Start date, YYYY-MM-DD."
    )
    parser.add_argument(
        "--end-date", required=True, type=_parse_iso_date, help="End date, YYYY-MM-DD."
    )
    parser.add_argument(
        "--initial-cash", required=True, type=float, help="Starting cash for the backtest."
    )
    parser.add_argument("--db-path", required=True, type=Path, help="DuckDB database file path.")
    parser.add_argument("--cache-dir", required=True, type=Path, help="Raw cache root directory.")
    parser.add_argument(
        "--overrides-path",
        required=False,
        default=None,
        type=Path,
        help="Optional path to a JSON BusinessActivityOverrideMap. Omit for no overrides.",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        type=Path,
        help="Where to write the generated, self-contained HTML report file.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Opens one READ-ONLY DuckDB connection (`db.connect(args.db_path, read_only=True)` —
    `report` never writes to DuckDB), loads the override map, calls `run_backtest(...)` then
    `purify_backtest_result(...)` — the exact same two-call sequence, same argument-threading
    discipline `mizan/cli/backtest.py`'s own `run()` already established (§7 guard G-R8) — then,
    still inside the `with db.connect(...)` block, constructs `ReportInput(backtest_result=result,
    fiqh_params=FIQH_PARAMS)` and calls `render_report(report_input,
    active_caveats=envelope.active_caveats)`, reusing `run_backtest`'s own returned
    `envelope.active_caveats` tuple verbatim, never a freshly-invented caveat set. Writes the
    returned HTML `str` to `args.output_path` (UTF-8, `Path.write_text`). Catches the same
    per-ticker/whole-backtest-shaped exceptions `mizan backtest` catches, printing a `HALT: ...`
    message to stderr and returning exit code 1. Prints the output path and the final portfolio
    value to stdout on success, returns 0.
    """
    overrides = load_override_map(args.overrides_path)
    strategy = EqualWeightStrategy()

    with db.connect(args.db_path, read_only=True) as con:
        try:
            envelope = run_backtest(
                tickers=frozenset(args.tickers),
                start_date=args.start_date,
                end_date=args.end_date,
                initial_cash=args.initial_cash,
                strategy=strategy,
                con=con,
                cache_dir=args.cache_dir,
                overrides=overrides,
            )
            result = BacktestResult.model_validate(envelope.payload)
            result = purify_backtest_result(
                result,
                con=con,
                cache_dir=args.cache_dir,
                overrides=overrides,
                fiqh_params=FIQH_PARAMS,
            )
            report_input = ReportInput(backtest_result=result, fiqh_params=FIQH_PARAMS)
            html_document = render_report(report_input, active_caveats=envelope.active_caveats)
        except _HALTING_ERRORS as exc:
            print(f"HALT: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    args.output_path.write_text(html_document, encoding="utf-8")

    final_value = (
        result.daily_snapshots[-1].portfolio_value if result.daily_snapshots else args.initial_cash
    )
    print(f"Report written to: {args.output_path}")
    print(f"Final portfolio value: {final_value:.2f}")
    return 0
