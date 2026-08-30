"""mizan/cli/normalize.py — the `normalize` subcommand.

Implements PHASE_3_SPEC.md §4.3.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from mizan.data import db
from mizan.data.ingest_edgar import CikResolutionError
from mizan.data.normalize import (
    DuplicateFactRowError,
    DuplicatePriceBarError,
    NotIngestedError,
    UnrecognizedUnitError,
    normalize_edgar_facts,
    normalize_tiingo_bars,
    resolve_cik_offline,
)

#: Per-ticker exceptions that HALT that ticker's normalization without aborting the whole batch
#: (§4.3's `run()` contract — mirrors `mizan.cli.ingest.run`'s exit-code contract exactly).
_HALTING_ERRORS = (
    CikResolutionError,
    NotIngestedError,
    UnrecognizedUnitError,
    DuplicateFactRowError,
    DuplicatePriceBarError,
)


def _parse_iso_date(value: str) -> date:
    """argparse `type=` callback: parse a `YYYY-MM-DD` string into a `date`."""
    return date.fromisoformat(value)


def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register `normalize --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --cache-dir PATH --db-path PATH`.

    `--start-date`/`--end-date` must match the range originally passed to `mizan ingest` for that
    ticker (they select the Tiingo raw-cache file's key, PHASE_2_SPEC.md §6.2 — normalize does not
    scan the cache directory for "whatever range happens to be there"). `--db-path` has no default
    (same posture as `--cache-dir` in PHASE_2_SPEC.md §4.4: an operator must be explicit about where
    derived, regenerable analytical data lives, never a hidden default path).
    """
    parser = subparsers.add_parser(
        "normalize", help="Normalize cached EDGAR + Tiingo raw data into the DuckDB store."
    )
    parser.add_argument(
        "--ticker",
        action="append",
        required=True,
        dest="tickers",
        metavar="TICKER",
        help="Ticker symbol to normalize. May be repeated.",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        type=_parse_iso_date,
        help="Start date, YYYY-MM-DD — must match the range `mizan ingest` used for this ticker.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        type=_parse_iso_date,
        help="End date, YYYY-MM-DD — must match the range `mizan ingest` used for this ticker.",
    )
    parser.add_argument("--cache-dir", required=True, type=Path, help="Raw cache root directory.")
    parser.add_argument("--db-path", required=True, type=Path, help="DuckDB database file path.")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Opens one DuckDB connection via `db.connect(args.db_path)` (schema ensured once, §4.1), then
    for each `--ticker`: `resolve_cik_offline`, then `normalize_edgar_facts`, then
    `normalize_tiingo_bars`, in that order.

    Catches `CikResolutionError` / `NotIngestedError` / `UnrecognizedUnitError` /
    `DuplicateFactRowError` / `DuplicatePriceBarError` per-ticker, prints a HALT message to stderr
    naming the ticker and the failure, and continues to the next ticker rather than aborting the
    whole batch — but returns a non-zero exit code if ANY ticker halted, mirroring
    `mizan.cli.ingest.run`'s exit-code contract exactly. The DuckDB connection is closed
    (context-managed) before `run()` returns, on every exit path, including a halted one — never
    left open across the process boundary (§7 G-DB1).
    """
    any_halted = False

    with db.connect(args.db_path) as con:
        for ticker in args.tickers:
            try:
                cik = resolve_cik_offline(ticker, cache_dir=args.cache_dir)
                normalize_edgar_facts(cik, cache_dir=args.cache_dir, con=con)
                normalize_tiingo_bars(
                    ticker,
                    args.start_date,
                    args.end_date,
                    cache_dir=args.cache_dir,
                    con=con,
                )
            except _HALTING_ERRORS as exc:
                any_halted = True
                print(f"HALT [{ticker}]: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue

    return 1 if any_halted else 0
