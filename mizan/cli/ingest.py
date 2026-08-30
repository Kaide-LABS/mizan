"""mizan/cli/ingest.py — the `ingest` subcommand.

Implements PHASE_2_SPEC.md §4.4.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import httpx

from mizan.data.ingest_edgar import (
    CikResolutionError,
    EdgarBlockedError,
    MissingCompanyFactsError,
    MissingSicError,
    ingest_edgar_companyfacts,
    ingest_edgar_submissions,
    resolve_cik,
)
from mizan.data.ingest_tiingo import (
    SuspectedCorporateActionAnomalyError,
    TiingoUniverseDriftError,
    ingest_tiingo_eod,
)

#: Environment variable `--tiingo-token` falls back to when the flag is omitted (PHASE_2_SPEC.md
#: §4.4). Never hardcoded, never logged.
TIINGO_TOKEN_ENV_VAR = "TIINGO_API_TOKEN"

#: Per-ticker exceptions that HALT that ticker's ingestion without aborting the whole batch
#: (PHASE_2_SPEC.md §4.4's `run()` contract).
_HALTING_ERRORS = (
    CikResolutionError,
    MissingCompanyFactsError,
    MissingSicError,
    EdgarBlockedError,
    TiingoUniverseDriftError,
    SuspectedCorporateActionAnomalyError,
)


def _parse_iso_date(value: str) -> date:
    """argparse `type=` callback: parse a `YYYY-MM-DD` string into a `date`."""
    return date.fromisoformat(value)


def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register `ingest --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --cache-dir PATH [--tiingo-token TOKEN] [--force-refetch]`.

    `--tiingo-token` defaults to reading the `TIINGO_API_TOKEN` environment variable if omitted —
    never a hardcoded default, never logged.
    """
    parser = subparsers.add_parser(
        "ingest", help="Ingest EDGAR + Tiingo raw data for one or more tickers."
    )
    parser.add_argument(
        "--ticker",
        action="append",
        required=True,
        dest="tickers",
        metavar="TICKER",
        help="Ticker symbol to ingest. May be repeated.",
    )
    parser.add_argument(
        "--start-date", required=True, type=_parse_iso_date, help="Start date, YYYY-MM-DD."
    )
    parser.add_argument(
        "--end-date", required=True, type=_parse_iso_date, help="End date, YYYY-MM-DD."
    )
    parser.add_argument("--cache-dir", required=True, type=Path, help="Raw cache root directory.")
    parser.add_argument(
        "--tiingo-token",
        default=os.environ.get(TIINGO_TOKEN_ENV_VAR),
        help=f"Tiingo API token. Defaults to the {TIINGO_TOKEN_ENV_VAR} environment variable.",
    )
    parser.add_argument(
        "--force-refetch",
        action="store_true",
        help="Bypass the cache-hit short-circuit for every ingest call made this run.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """For each `--ticker`: `resolve_cik`, then `ingest_edgar_submissions`,
    `ingest_edgar_companyfacts`, and `ingest_tiingo_eod`, in that order (SIC/companyfacts before
    prices, so a HALT on the EDGAR leg is caught before spending Tiingo request budget on a ticker
    that will end up unanalyzed anyway).

    Catches `CikResolutionError` / `MissingCompanyFactsError` / `MissingSicError` /
    `EdgarBlockedError` / `TiingoUniverseDriftError` / `SuspectedCorporateActionAnomalyError`
    per-ticker, prints a HALT message to stderr naming the ticker and the failure, and continues to
    the next ticker rather than aborting the whole batch — but returns a non-zero exit code if ANY
    ticker halted, so the CLI's own exit code is the machine-readable "not every ticker ingested
    cleanly" signal, exactly mirroring `mizan-boot-check`'s exit-code contract (`PHASE_1_SPEC.md`
    §4.1).
    """
    any_halted = False

    with httpx.Client() as client:
        for ticker in args.tickers:
            try:
                cik = resolve_cik(ticker, cache_dir=args.cache_dir, client=client)
                ingest_edgar_submissions(
                    cik,
                    cache_dir=args.cache_dir,
                    client=client,
                    force_refetch=args.force_refetch,
                )
                ingest_edgar_companyfacts(
                    cik,
                    cache_dir=args.cache_dir,
                    client=client,
                    force_refetch=args.force_refetch,
                )
            except _HALTING_ERRORS as exc:
                any_halted = True
                print(f"HALT [{ticker}]: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue

            token: str | None = args.tiingo_token
            if token is None:
                any_halted = True
                print(
                    f"HALT [{ticker}]: no Tiingo API token provided "
                    f"(set {TIINGO_TOKEN_ENV_VAR} or pass --tiingo-token)",
                    file=sys.stderr,
                )
                continue

            try:
                ingest_tiingo_eod(
                    ticker,
                    args.start_date,
                    args.end_date,
                    cache_dir=args.cache_dir,
                    token=token,
                    client=client,
                    force_refetch=args.force_refetch,
                )
            except _HALTING_ERRORS as exc:
                any_halted = True
                print(f"HALT [{ticker}]: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue

    return 1 if any_halted else 0
