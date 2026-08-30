"""Tests for mizan/cli/normalize.py and its wiring into mizan/cli/main.py.

Implements PHASE_3_SPEC.md §8 acceptance criterion 11 (boot gate runs first, before any DuckDB file
is created) and the `run()` per-ticker HALT-but-continue / non-zero-exit contract of §4.3.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from mizan.cli import main
from mizan.cli import normalize as normalize_cli
from mizan.config.boot_check import InvariantViolationError
from mizan.data.ingest_edgar import CikResolutionError
from mizan.data.normalize import NotIngestedError

# ── CLI argument wiring ──────────────────────────────────────────────────────────────────────────


def test_ticker_flag_may_be_repeated(tmp_path: Path) -> None:
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "normalize",
            "--ticker",
            "AAPL",
            "--ticker",
            "MSFT",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
        ]
    )

    assert args.tickers == ["AAPL", "MSFT"]
    assert args.start_date == date(2020, 1, 1)
    assert args.end_date == date(2020, 1, 2)
    assert args.cache_dir == tmp_path / "cache"
    assert args.db_path == tmp_path / "mizan.duckdb"


def test_db_path_has_no_default_and_is_required(tmp_path: Path) -> None:
    parser = main.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "normalize",
                "--ticker",
                "AAPL",
                "--start-date",
                "2020-01-01",
                "--end-date",
                "2020-01-02",
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )


# ── Boot gate runs first (AC11, G-CLI2) ─────────────────────────────────────────────────────────


def test_main_halts_on_invariant_violation_before_any_duckdb_file_is_created(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def _raise() -> None:
        raise InvariantViolationError("fake violation for coverage")

    monkeypatch.setattr("mizan.cli.main.check_all", _raise)

    handler_was_called = False

    def _spy_run(args: argparse.Namespace) -> int:
        nonlocal handler_was_called
        handler_was_called = True
        return 0

    monkeypatch.setattr("mizan.cli.normalize.run", _spy_run)

    db_path = tmp_path / "mizan.duckdb"
    exit_code = main.main(
        [
            "normalize",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--db-path",
            str(db_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "BOOT FAILED" in captured.err
    assert handler_was_called is False
    assert not db_path.exists()


def test_main_dispatches_to_normalize_run_when_boot_check_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the real (passing) boot check, `main()` reaches and calls the `normalize` handler."""
    received: dict[str, object] = {}

    def _spy_run(args: argparse.Namespace) -> int:
        received["tickers"] = args.tickers
        return 0

    monkeypatch.setattr("mizan.cli.normalize.run", _spy_run)

    exit_code = main.main(
        [
            "normalize",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
        ]
    )

    assert exit_code == 0
    assert received["tickers"] == ["AAPL"]


# ── run(): per-ticker HALT-but-continue, non-zero exit on any halt (§4.3) ───────────────────────


def _base_args(tmp_path: Path, tickers: list[str]) -> argparse.Namespace:
    return argparse.Namespace(
        tickers=tickers,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "mizan.duckdb",
    )


def test_run_returns_zero_when_every_ticker_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        normalize_cli, "resolve_cik_offline", lambda ticker, *, cache_dir: "0000000001"
    )
    monkeypatch.setattr(normalize_cli, "normalize_edgar_facts", lambda cik, *, cache_dir, con: 1)
    monkeypatch.setattr(
        normalize_cli,
        "normalize_tiingo_bars",
        lambda ticker, start, end, *, cache_dir, con: 1,
    )

    assert normalize_cli.run(_base_args(tmp_path, ["AAPL"])) == 0


def test_run_continues_past_a_halted_ticker_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _resolve(ticker: str, *, cache_dir: Path) -> str:
        if ticker == "BAD":
            raise CikResolutionError("bad ticker")
        return "0000000001"

    monkeypatch.setattr(normalize_cli, "resolve_cik_offline", _resolve)
    monkeypatch.setattr(normalize_cli, "normalize_edgar_facts", lambda cik, *, cache_dir, con: 1)
    processed: list[str] = []

    def _tiingo(ticker: str, start: date, end: date, *, cache_dir: Path, con: object) -> int:
        processed.append(ticker)
        return 1

    monkeypatch.setattr(normalize_cli, "normalize_tiingo_bars", _tiingo)

    exit_code = normalize_cli.run(_base_args(tmp_path, ["BAD", "GOOD"]))

    assert exit_code == 1
    assert processed == ["GOOD"]


def test_run_does_not_reach_tiingo_when_the_edgar_leg_halts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        normalize_cli, "resolve_cik_offline", lambda ticker, *, cache_dir: "0000000001"
    )

    def _facts(cik: str, *, cache_dir: Path, con: object) -> int:
        raise NotIngestedError("no facts cached")

    monkeypatch.setattr(normalize_cli, "normalize_edgar_facts", _facts)
    tiingo_called = False

    def _tiingo(*_args: object, **_kwargs: object) -> int:
        nonlocal tiingo_called
        tiingo_called = True
        return 1

    monkeypatch.setattr(normalize_cli, "normalize_tiingo_bars", _tiingo)

    exit_code = normalize_cli.run(_base_args(tmp_path, ["AAPL"]))

    assert exit_code == 1
    assert tiingo_called is False


def test_run_closes_the_connection_even_on_a_halted_ticker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The DuckDB connection must be closed on every exit path (G-DB1) — proven here by opening a
    second writable connection to the same file immediately after `run()` returns and confirming it
    does not hit a stale lock."""
    from mizan.data import db

    def _resolve(ticker: str, *, cache_dir: Path) -> str:
        raise CikResolutionError("always halts")

    monkeypatch.setattr(normalize_cli, "resolve_cik_offline", _resolve)

    args = _base_args(tmp_path, ["AAPL"])
    exit_code = normalize_cli.run(args)
    assert exit_code == 1

    con = db.connect(args.db_path)
    con.close()
