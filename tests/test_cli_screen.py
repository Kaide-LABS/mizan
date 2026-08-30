"""Tests for mizan/cli/screen.py and its wiring into mizan/cli/main.py.

Implements PHASE_4_SPEC.md §8 acceptance criterion 12 (boot gate runs first) and the `run()`
per-ticker HALT-but-continue / non-zero-exit contract of §4.4.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from mizan.cli import main
from mizan.cli import screen as screen_cli
from mizan.config.boot_check import InvariantViolationError
from mizan.core.caveats import Caveat
from mizan.core.verdict import Verdict
from mizan.data.ingest_edgar import CikResolutionError
from mizan.screening.business_activity import BusinessActivityOverrideMap
from mizan.screening.verdict import (
    InsufficientDataError,
    ReasonTraceEntry,
    ScreeningVerdict,
    ScreenName,
)

# ── CLI argument wiring ──────────────────────────────────────────────────────────────────────────


def test_ticker_and_dates_and_paths_are_parsed(tmp_path: Path) -> None:
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "screen",
            "--ticker",
            "AAPL",
            "--ticker",
            "MSFT",
            "--as-of-date",
            "2026-06-30",
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    assert args.tickers == ["AAPL", "MSFT"]
    assert args.as_of_date == date(2026, 6, 30)
    assert args.db_path == tmp_path / "mizan.duckdb"
    assert args.cache_dir == tmp_path / "cache"
    assert args.overrides_path is None


def test_overrides_path_is_optional_with_no_hidden_default(tmp_path: Path) -> None:
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "screen",
            "--ticker",
            "AAPL",
            "--as-of-date",
            "2026-06-30",
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--overrides-path",
            str(tmp_path / "overrides.json"),
        ]
    )

    assert args.overrides_path == tmp_path / "overrides.json"


def test_db_path_has_no_default_and_is_required(tmp_path: Path) -> None:
    parser = main.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "screen",
                "--ticker",
                "AAPL",
                "--as-of-date",
                "2026-06-30",
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )


# ── Boot gate runs first (AC12, G-CLI2) ──────────────────────────────────────────────────────────


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

    monkeypatch.setattr("mizan.cli.screen.run", _spy_run)

    db_path = tmp_path / "mizan.duckdb"
    exit_code = main.main(
        [
            "screen",
            "--ticker",
            "AAPL",
            "--as-of-date",
            "2026-06-30",
            "--db-path",
            str(db_path),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "BOOT FAILED" in captured.err
    assert handler_was_called is False
    assert not db_path.exists()


def test_main_dispatches_to_screen_run_when_boot_check_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: dict[str, object] = {}

    def _spy_run(args: argparse.Namespace) -> int:
        received["tickers"] = args.tickers
        return 0

    monkeypatch.setattr("mizan.cli.screen.run", _spy_run)

    exit_code = main.main(
        [
            "screen",
            "--ticker",
            "AAPL",
            "--as-of-date",
            "2026-06-30",
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    assert exit_code == 0
    assert received["tickers"] == ["AAPL"]


# ── run(): per-ticker HALT-but-continue, non-zero exit on any halt, read-only connection ───────


def _base_args(tmp_path: Path, tickers: list[str]) -> argparse.Namespace:
    return argparse.Namespace(
        tickers=tickers,
        as_of_date=date(2026, 6, 30),
        db_path=tmp_path / "mizan.duckdb",
        cache_dir=tmp_path / "cache",
        overrides_path=None,
    )


def _no_overrides(path: Path | None) -> BusinessActivityOverrideMap:
    """Stand-in for `load_override_map`, monkeypatched into every `run()` test below so none of
    them depend on a real cache/file layout."""
    return BusinessActivityOverrideMap(overrides={})


def _make_envelope(ticker: str) -> object:
    """Builds a `ResultEnvelope` with a full, non-empty reason trace (one `BUSINESS_ACTIVITY` entry
    with all-`None` fields, one ratio entry with every field populated) so `run()`'s stdout-printing
    loop exercises both the categorical and the threshold/actual_value/margin branches."""
    from mizan.core.caveats import ResultEnvelope

    verdict = ScreeningVerdict(
        ticker=ticker,
        cik="0000000001",
        as_of_date=date(2026, 6, 30),
        verdict=Verdict.PURE,
        reason_trace=(
            ReasonTraceEntry(
                screen=ScreenName.BUSINESS_ACTIVITY,
                passed=True,
                threshold=None,
                actual_value=None,
                margin=None,
                detail="clean SIC",
            ),
            ReasonTraceEntry(
                screen=ScreenName.DEBT_RATIO,
                passed=True,
                threshold=0.30,
                actual_value=0.0,
                margin=0.30,
                detail="0.0 / 100000000.0 = 0.0 vs. threshold 0.3",
            ),
        ),
    )
    return ResultEnvelope(
        active_caveats=(Caveat.LOOK_AHEAD_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION),
        payload=verdict.model_dump(),
    )


def test_run_returns_zero_when_every_ticker_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()  # ensure the DB file exists for read_only=True

    def _screen(
        ticker: str, as_of_date: date, *, con: object, cache_dir: Path, overrides: object
    ) -> object:
        return _make_envelope(ticker)

    monkeypatch.setattr(screen_cli, "screen", _screen)
    monkeypatch.setattr(screen_cli, "load_override_map", _no_overrides)

    assert screen_cli.run(_base_args(tmp_path, ["AAPL"])) == 0


def test_run_continues_past_a_halted_ticker_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    processed: list[str] = []

    def _screen(
        ticker: str, as_of_date: date, *, con: object, cache_dir: Path, overrides: object
    ) -> object:
        if ticker == "BAD":
            raise CikResolutionError("bad ticker")
        processed.append(ticker)
        return _make_envelope(ticker)

    monkeypatch.setattr(screen_cli, "screen", _screen)
    monkeypatch.setattr(screen_cli, "load_override_map", _no_overrides)

    exit_code = screen_cli.run(_base_args(tmp_path, ["BAD", "GOOD"]))

    assert exit_code == 1
    assert processed == ["GOOD"]


def test_run_halts_on_insufficient_data_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    def _screen(
        ticker: str, as_of_date: date, *, con: object, cache_dir: Path, overrides: object
    ) -> object:
        raise InsufficientDataError("no denominator")

    monkeypatch.setattr(screen_cli, "screen", _screen)
    monkeypatch.setattr(screen_cli, "load_override_map", _no_overrides)

    exit_code = screen_cli.run(_base_args(tmp_path, ["AAPL"]))

    assert exit_code == 1


def test_run_opens_a_read_only_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """G-DB3: `mizan screen` must never write to DuckDB — proven here by confirming the connection
    `run()` opens is read-only (an INSERT attempted against it would raise)."""
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    captured_con: dict[str, object] = {}

    def _screen(
        ticker: str, as_of_date: date, *, con: object, cache_dir: Path, overrides: object
    ) -> object:
        captured_con["con"] = con
        return _make_envelope(ticker)

    monkeypatch.setattr(screen_cli, "screen", _screen)
    monkeypatch.setattr(screen_cli, "load_override_map", _no_overrides)

    screen_cli.run(_base_args(tmp_path, ["AAPL"]))

    con = captured_con["con"]
    with pytest.raises(Exception):  # noqa: B017, PT011 -- duckdb raises its own exception type for a read-only write attempt
        con.execute("CREATE TABLE should_fail (x INTEGER)")  # type: ignore[attr-defined]


def test_run_closes_the_connection_even_on_a_halted_ticker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    def _screen(
        ticker: str, as_of_date: date, *, con: object, cache_dir: Path, overrides: object
    ) -> object:
        raise CikResolutionError("always halts")

    monkeypatch.setattr(screen_cli, "screen", _screen)
    monkeypatch.setattr(screen_cli, "load_override_map", _no_overrides)

    exit_code = screen_cli.run(_base_args(tmp_path, ["AAPL"]))
    assert exit_code == 1

    con = db.connect(tmp_path / "mizan.duckdb")
    con.close()
