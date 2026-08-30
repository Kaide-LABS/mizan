"""mizan/cli/screen.py — the `screen` subcommand.

Implements PHASE_4_SPEC.md §4.4.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from mizan.data import db
from mizan.data.ingest_edgar import CikResolutionError
from mizan.screening.business_activity import SicResolutionError, load_override_map
from mizan.screening.verdict import (
    InsufficientDataError,
    NotNormalizedError,
    ScreeningVerdict,
    screen,
)

#: Per-ticker exceptions that HALT that ticker's screening without aborting the whole batch (§4.4's
#: `run()` contract — mirrors `mizan.cli.ingest.run`/`mizan.cli.normalize.run`'s exit-code contract
#: exactly).
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
    """Register `screen --ticker TICKER [--ticker TICKER ...] --as-of-date YYYY-MM-DD
    --db-path PATH --cache-dir PATH [--overrides-path PATH]`.

    `--overrides-path` is OPTIONAL with no hidden default file — omitting it means "no override
    map," per `BusinessActivityOverrideMap`'s honest-empty-default posture. This is deliberately NOT
    the same "operator must be explicit" posture `PHASE_2_SPEC.md`/`PHASE_3_SPEC.md` §4.4 gave
    `--cache-dir`/`--db-path` (those name where REQUIRED, always-present state lives; an override
    map is optional, genuinely-absent-by-default state, so its absence needs no flag at all, whereas
    a wrong/missing cache or DB path would silently mean "the wrong data").
    """
    parser = subparsers.add_parser(
        "screen", help="Screen one or more tickers for Shari'ah compliance as of a date."
    )
    parser.add_argument(
        "--ticker",
        action="append",
        required=True,
        dest="tickers",
        metavar="TICKER",
        help="Ticker symbol to screen. May be repeated.",
    )
    parser.add_argument(
        "--as-of-date", required=True, type=_parse_iso_date, help="As-of date, YYYY-MM-DD."
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
    """Opens one READ-ONLY DuckDB connection via `db.connect(args.db_path, read_only=True)` (§5 —
    `screen` never writes to DuckDB), loads the override map once via
    `load_override_map(args.overrides_path)`, then for each `--ticker` calls `screen(...)`, printing
    the resulting `ScreeningVerdict`'s verdict and full reason trace to stdout.

    Catches `CikResolutionError` / `SicResolutionError` / `NotNormalizedError` /
    `InsufficientDataError` per-ticker, prints a HALT message to stderr naming the ticker and the
    failure, and continues to the next ticker — but returns a non-zero exit code if ANY ticker
    halted, mirroring `mizan.cli.ingest.run`/`mizan.cli.normalize.run`'s exit-code contract exactly.
    """
    any_halted = False
    overrides = load_override_map(args.overrides_path)

    with db.connect(args.db_path, read_only=True) as con:
        for ticker in args.tickers:
            try:
                envelope = screen(
                    ticker,
                    args.as_of_date,
                    con=con,
                    cache_dir=args.cache_dir,
                    overrides=overrides,
                )
            except _HALTING_ERRORS as exc:
                any_halted = True
                print(f"HALT [{ticker}]: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue

            verdict = ScreeningVerdict.model_validate(envelope.payload)
            print(f"{ticker}: {verdict.verdict.value}")
            for entry in verdict.reason_trace:
                fields = [f"screen={entry.screen.value}", f"passed={entry.passed}"]
                if entry.threshold is not None:
                    fields.append(f"threshold={entry.threshold}")
                if entry.actual_value is not None:
                    fields.append(f"actual_value={entry.actual_value}")
                if entry.margin is not None:
                    fields.append(f"margin={entry.margin}")
                fields.append(f"detail={entry.detail}")
                print("  " + " ".join(fields))

    return 1 if any_halted else 0
