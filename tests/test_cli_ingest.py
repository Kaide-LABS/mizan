"""Tests for mizan/cli/main.py and mizan/cli/ingest.py.

Implements PHASE_2_SPEC.md §8 acceptance criterion 12 (boot gate runs first) and the `run()`
per-ticker HALT-but-continue / non-zero-exit contract of §4.4.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from mizan.cli import ingest, main
from mizan.config.boot_check import InvariantViolationError
from mizan.data.ingest_edgar import CikResolutionError, MissingCompanyFactsError

# ── CLI argument wiring ──────────────────────────────────────────────────────────────────────────


def test_ticker_flag_may_be_repeated(tmp_path: Path) -> None:
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "ingest",
            "--ticker",
            "AAPL",
            "--ticker",
            "MSFT",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert args.tickers == ["AAPL", "MSFT"]
    assert args.start_date == date(2020, 1, 1)
    assert args.end_date == date(2020, 1, 2)
    assert args.cache_dir == tmp_path
    assert args.force_refetch is False


def test_tiingo_token_defaults_from_environment_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TIINGO_API_TOKEN", "env-token-value")
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "ingest",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert args.tiingo_token == "env-token-value"


def test_tiingo_token_flag_overrides_environment_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TIINGO_API_TOKEN", "env-token-value")
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "ingest",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path),
            "--tiingo-token",
            "flag-token-value",
        ]
    )

    assert args.tiingo_token == "flag-token-value"


def test_tiingo_token_is_none_when_flag_and_env_var_both_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TIINGO_API_TOKEN", raising=False)
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "ingest",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert args.tiingo_token is None


# ── Boot gate runs first (AC12, G-CLI1) ─────────────────────────────────────────────────────────


def test_main_halts_on_invariant_violation_before_any_subcommand_runs(
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

    monkeypatch.setattr("mizan.cli.ingest.run", _spy_run)

    exit_code = main.main(
        [
            "ingest",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "BOOT FAILED" in captured.err
    assert handler_was_called is False


def test_main_dispatches_to_ingest_run_when_boot_check_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the real (passing) boot check, `main()` reaches and calls the `ingest` handler."""
    received: dict[str, object] = {}

    def _spy_run(args: argparse.Namespace) -> int:
        received["tickers"] = args.tickers
        return 0

    monkeypatch.setattr("mizan.cli.ingest.run", _spy_run)

    exit_code = main.main(
        [
            "ingest",
            "--ticker",
            "AAPL",
            "--start-date",
            "2020-01-01",
            "--end-date",
            "2020-01-02",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert received["tickers"] == ["AAPL"]


# ── run(): per-ticker HALT-but-continue, non-zero exit on any halt (§4.4) ───────────────────────


def _base_args(
    tmp_path: Path, tickers: list[str], *, tiingo_token: str | None = "tok"
) -> argparse.Namespace:
    return argparse.Namespace(
        tickers=tickers,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),
        cache_dir=tmp_path,
        tiingo_token=tiingo_token,
        force_refetch=False,
    )


def test_run_returns_zero_when_every_ticker_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ingest, "resolve_cik", lambda ticker, *, cache_dir, client: "0000000001")
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_submissions",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "sub.json",
    )
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_companyfacts",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "facts.json",
    )
    monkeypatch.setattr(
        ingest,
        "ingest_tiingo_eod",
        lambda ticker, start, end, *, cache_dir, token, client, force_refetch=False: (
            cache_dir / "eod.json"
        ),
    )

    assert ingest.run(_base_args(tmp_path, ["AAPL"])) == 0


def test_run_continues_past_a_halted_ticker_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _resolve_cik(ticker: str, *, cache_dir: Path, client: object) -> str:
        if ticker == "BAD":
            raise CikResolutionError("bad ticker")
        return "0000000001"

    monkeypatch.setattr(ingest, "resolve_cik", _resolve_cik)
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_submissions",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "sub.json",
    )
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_companyfacts",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "facts.json",
    )
    processed: list[str] = []

    def _tiingo(
        ticker: str,
        start: date,
        end: date,
        *,
        cache_dir: Path,
        token: str,
        client: object,
        force_refetch: bool = False,
    ) -> Path:
        processed.append(ticker)
        return cache_dir / "eod.json"

    monkeypatch.setattr(ingest, "ingest_tiingo_eod", _tiingo)

    exit_code = ingest.run(_base_args(tmp_path, ["BAD", "GOOD"]))

    assert exit_code == 1
    assert processed == ["GOOD"]


def test_run_does_not_reach_tiingo_when_the_edgar_leg_halts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ingest, "resolve_cik", lambda ticker, *, cache_dir, client: "0000000001")
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_submissions",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "sub.json",
    )

    def _facts(cik: str, *, cache_dir: Path, client: object, force_refetch: bool = False) -> Path:
        raise MissingCompanyFactsError("no facts")

    monkeypatch.setattr(ingest, "ingest_edgar_companyfacts", _facts)
    tiingo_called = False

    def _tiingo(*_args: object, **_kwargs: object) -> Path:
        nonlocal tiingo_called
        tiingo_called = True
        return tmp_path / "eod.json"

    monkeypatch.setattr(ingest, "ingest_tiingo_eod", _tiingo)

    exit_code = ingest.run(_base_args(tmp_path, ["AAPL"]))

    assert exit_code == 1
    assert tiingo_called is False


def test_run_halts_a_ticker_when_no_tiingo_token_is_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ingest, "resolve_cik", lambda ticker, *, cache_dir, client: "0000000001")
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_submissions",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "sub.json",
    )
    monkeypatch.setattr(
        ingest,
        "ingest_edgar_companyfacts",
        lambda cik, *, cache_dir, client, force_refetch=False: cache_dir / "facts.json",
    )
    tiingo_called = False

    def _tiingo(*_args: object, **_kwargs: object) -> Path:
        nonlocal tiingo_called
        tiingo_called = True
        return tmp_path / "eod.json"

    monkeypatch.setattr(ingest, "ingest_tiingo_eod", _tiingo)

    exit_code = ingest.run(_base_args(tmp_path, ["AAPL"], tiingo_token=None))

    assert exit_code == 1
    assert tiingo_called is False
