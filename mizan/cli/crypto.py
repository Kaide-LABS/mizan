"""mizan/cli/crypto.py — the `crypto-pipeline` subcommand.

Implements `docs/crypto/PHASE_6_SPEC.md` §B3: one verb, fetch -> screen -> backtest -> report,
end to end, over the locked 14-token `CRYPTO_UNIVERSE`. Deliberately distinct from equity's four
separate `ingest`/`normalize`/`screen`/`backtest`/`report` verbs — the baby PRD's own acceptance
criterion is "a single command that runs the full pipeline", not four composable ones.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time
from pathlib import Path

import httpx

from mizan.crypto.backtest import (
    BacktestCostParams,
    CryptoBacktestResult,
    run_crypto_backtest,
)
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS
from mizan.crypto.ingest import ingest_universe_candles
from mizan.crypto.report import (
    CryptoReportInput,
    render_crypto_report,
    resolve_crypto_report_caveats,
)
from mizan.crypto.screening import CryptoTokenVerdict, screen_universe
from mizan.data import db


def _parse_iso_date(value: str) -> date:
    """argparse `type=` callback: parse a `YYYY-MM-DD` string into a `date`."""
    return date.fromisoformat(value)


def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Registers `crypto-pipeline --start-date YYYY-MM-DD --end-date YYYY-MM-DD --initial-cash
    FLOAT --db-path PATH --cache-dir PATH --output-path PATH [--interval-days INT]
    [--granularity STR] [--taker-fee-rate FLOAT] [--slippage-rate FLOAT]`. Deliberately registers
    no caller-selectable-universe flag of any spelling: `run_crypto_backtest` takes no
    `tickers`/`universe` parameter — the locked 14-token universe cannot be widened or narrowed by
    a caller."""
    parser = subparsers.add_parser(
        "crypto-pipeline",
        help="Fetch, screen, backtest and report the locked 14-token crypto universe, end to end.",
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
        "--output-path",
        required=True,
        type=Path,
        help="Where to write the generated, self-contained crypto HTML report file.",
    )
    parser.add_argument(
        "--interval-days", required=False, type=int, default=30,
        help="Rebalance interval in calendar days.",
    )
    parser.add_argument(
        "--granularity", required=False, default="1d", help="Candle granularity."
    )
    parser.add_argument(
        "--taker-fee-rate", required=False, type=float, default=0.006,
        help="Per-side taker fee rate.",
    )
    parser.add_argument(
        "--slippage-rate", required=False, type=float, default=0.0005, help="Slippage rate."
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Opens one `httpx.Client()` and one **writable** `db.connect(args.db_path,
    read_only=False)` — the one CLI entry point in this repo that performs its own ingestion
    rather than reading an already-populated store. Fetches the 14 tokens' candles (printing
    source per ticker), screens the full 23-token map, runs the baseline backtest, builds and
    writes the crypto HTML report, then prints the output path and final portfolio value."""
    cost_params = BacktestCostParams(
        taker_fee_rate=args.taker_fee_rate, slippage_rate=args.slippage_rate
    )

    with httpx.Client() as client, db.connect(args.db_path, read_only=False) as con:
        sources = ingest_universe_candles(
            granularity=args.granularity,
            start=datetime.combine(args.start_date, time.min, tzinfo=UTC),
            end=datetime.combine(args.end_date, time.min, tzinfo=UTC),
            cache_dir=args.cache_dir,
            con=con,
            client=client,
        )
        for ticker, source in sorted(sources.items()):
            print(f"{ticker}: fetched via {source}")

        verdicts = screen_universe()
        token_verdicts = tuple(
            CryptoTokenVerdict.model_validate(envelope.payload) for envelope in verdicts.values()
        )

        envelope = run_crypto_backtest(
            con=con,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_cash=args.initial_cash,
            interval_days=args.interval_days,
            cost_params=cost_params,
            granularity=args.granularity,
        )
        result = CryptoBacktestResult.model_validate(envelope.payload)

        report_input = CryptoReportInput(backtest_result=result, token_verdicts=token_verdicts)
        active_caveats = resolve_crypto_report_caveats(
            envelope.active_caveats, CRYPTO_FIQH_PARAMS
        )
        html_document = render_crypto_report(report_input, active_caveats=active_caveats)

    args.output_path.write_text(html_document, encoding="utf-8")

    final_value = (
        result.daily_snapshots[-1].portfolio_value if result.daily_snapshots else args.initial_cash
    )
    print(f"Report written to: {args.output_path}")
    print(f"Final portfolio value: {final_value:.2f}")
    return 0
