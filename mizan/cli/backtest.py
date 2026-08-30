"""mizan/cli/backtest.py — the `backtest` subcommand.

Implements PHASE_5_SPEC.md §4.5.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from mizan.backtest.clock import BacktestResult, run_backtest
from mizan.backtest.strategy import EqualWeightStrategy
from mizan.data import db
from mizan.data.ingest_edgar import CikResolutionError
from mizan.screening.business_activity import SicResolutionError, load_override_map
from mizan.screening.verdict import InsufficientDataError, NotNormalizedError

#: Per-ticker-shaped exceptions `mizan screen` catches per-ticker; `backtest` catches the SAME set
#: but at the WHOLE-BACKTEST level (§4.5) — a halt on any single ticker's re-screen aborts the
#: entire run rather than continuing with a partial universe, since a backtest's tickers are not
#: independent of each other the way a screening batch's are.
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
    """Registers `backtest --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --initial-cash FLOAT --db-path PATH --cache-dir PATH
    [--overrides-path PATH]`. `--ticker` (repeated) is the CANDIDATE universe `EqualWeightStrategy`
    (the only built-in `Strategy`) may select from — NOT a claim that these are the real
    ~100-ticker universe (PHASE_5_SPEC.md §9). `--overrides-path` is optional, same honest-empty-
    default posture as `mizan screen` (`PHASE_4_SPEC.md` §4.4). There is deliberately NO
    `--rebalance-frequency` (or similarly-named) flag anywhere on this subcommand — see
    `mizan.backtest.clock`'s own `_REBALANCE_MONTHS` note and PHASE_5_SPEC.md §9.
    """
    parser = subparsers.add_parser(
        "backtest", help="Run a quarterly-rebalance backtest over one or more tickers."
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
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Opens one READ-ONLY DuckDB connection (`db.connect(args.db_path, read_only=True)` —
    `backtest` never writes to DuckDB), loads the override map once via
    `load_override_map(args.overrides_path)`, constructs `EqualWeightStrategy()`, calls
    `run_backtest(...)`, and prints a human-readable summary to stdout: final portfolio value,
    every `DivestmentEvent` (ticker, flip date, divest date), and every `DividendEvent`'s total
    credited cash per ticker. Catches the same per-ticker-shaped exceptions `mizan screen` catches
    (`CikResolutionError`/`SicResolutionError`/`NotNormalizedError`/`InsufficientDataError`, all
    reachable via `run_backtest`'s internal `screen()` calls) at the WHOLE-BACKTEST level. Prints
    a `HALT: ...` message to stderr and returns exit code 1 on any such exception.
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
        except _HALTING_ERRORS as exc:
            print(f"HALT: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    result = BacktestResult.model_validate(envelope.payload)

    final_value = (
        result.daily_snapshots[-1].portfolio_value if result.daily_snapshots else args.initial_cash
    )
    print(f"Final portfolio value: {final_value:.2f}")

    for event in result.divestment_events:
        print(
            f"DIVESTED {event.ticker}: flip_date={event.flip_date} divest_date={event.divest_date}"
        )

    totals: dict[str, float] = {}
    for dividend_event in result.dividend_events:
        totals[dividend_event.ticker] = (
            totals.get(dividend_event.ticker, 0.0) + dividend_event.cash_received
        )
    for ticker in sorted(totals):
        print(f"DIVIDENDS {ticker}: total_cash_received={totals[ticker]:.2f}")

    return 0
