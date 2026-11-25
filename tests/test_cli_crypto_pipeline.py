"""Tests for mizan/cli/crypto.py's `crypto-pipeline` verb.

Implements PHASE_6_SPEC.md §B4. Monkeypatches `mizan.crypto.ingest.ingest_universe_candles` to a
no-op (the real Coinbase/Kraken network calls stay covered by Phase 2's own ingestion tests and
tests/test_crypto_backtest_integration.py's existing seeded-DB boundary).
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import mizan.cli.crypto as crypto_cli
from mizan.crypto.models import CandleBar
from mizan.crypto.universe import CRYPTO_UNIVERSE
from mizan.data.db import ensure_schema, upsert_candles

_START = date(2026, 1, 1)
_END = date(2026, 3, 6)


def _seed_db(db_path: str) -> None:
    con = duckdb.connect(db_path)
    ensure_schema(con)
    bars = []
    for day_offset in range((_END - _START).days + 1):
        ts = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day_offset)
        for ticker in CRYPTO_UNIVERSE:
            bars.append(
                CandleBar(
                    exchange="coinbase", symbol=ticker, granularity="1d", ts=ts,
                    open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0,
                    source="coinbase",
                )
            )
    upsert_candles(con, tuple(bars))
    con.close()


def test_crypto_pipeline_handler_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mizan.duckdb"
    _seed_db(str(db_path))

    monkeypatch.setattr(
        crypto_cli,
        "ingest_universe_candles",
        lambda **kwargs: dict.fromkeys(CRYPTO_UNIVERSE, "coinbase"),
    )

    output_path = tmp_path / "report.html"
    args = argparse.Namespace(
        start_date=_START,
        end_date=_END,
        initial_cash=1000.0,
        db_path=db_path,
        cache_dir=tmp_path / "cache",
        output_path=output_path,
        interval_days=30,
        granularity="1d",
        taker_fee_rate=0.006,
        slippage_rate=0.0005,
    )

    exit_code = crypto_cli.run(args)

    assert exit_code == 0
    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    assert "AAVE" in text
    assert "custody_freeze_risk" not in text


def test_crypto_pipeline_registered_parser_has_no_ticker_flag() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    crypto_cli.add_subparser(subparsers)
    crypto_parser = subparsers.choices["crypto-pipeline"]
    option_strings = {
        option
        for action in crypto_parser._actions
        for option in action.option_strings
    }
    assert "--ticker" not in option_strings
    assert "--tickers" not in option_strings
    assert "--symbol" not in option_strings
