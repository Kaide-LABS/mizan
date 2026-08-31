"""Tests for mizan/cli/backtest.py and its wiring into mizan/cli/main.py.

Implements PHASE_5_SPEC.md §8 acceptance criteria 16 (boot gate runs first) and 14 (backtest never
writes to DuckDB), and the `run()` whole-backtest-level HALT contract of §4.5.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from mizan.backtest.clock import BacktestResult, DailySnapshot
from mizan.backtest.compliance_state import (
    ComplianceStateRecord,
    DivestmentEvent,
    DividendEvent,
    HoldingComplianceState,
    VerdictObservation,
)
from mizan.cli import backtest as backtest_cli
from mizan.cli import main
from mizan.config.boot_check import InvariantViolationError
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict
from mizan.data.ingest_edgar import CikResolutionError
from mizan.screening.business_activity import BusinessActivityOverrideMap
from mizan.screening.verdict import InsufficientDataError
from tests.fixtures import synthetic_universe as fx

# ── CLI argument wiring ──────────────────────────────────────────────────────────────────────────


def test_tickers_and_dates_and_paths_and_cash_are_parsed(tmp_path: Path) -> None:
    parser = main.build_parser()
    args = parser.parse_args(
        [
            "backtest",
            "--ticker",
            "ZZPURE01",
            "--ticker",
            "ZZMIXED01",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-10-15",
            "--initial-cash",
            "1000000.0",
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )
    assert args.tickers == ["ZZPURE01", "ZZMIXED01"]
    assert args.start_date == date(2026, 1, 1)
    assert args.end_date == date(2026, 10, 15)
    assert args.initial_cash == pytest.approx(1_000_000.0)
    assert args.db_path == tmp_path / "mizan.duckdb"
    assert args.cache_dir == tmp_path / "cache"
    assert args.overrides_path is None


def test_overrides_path_is_optional_with_no_hidden_default(tmp_path: Path) -> None:
    parser = main.build_parser()
    args = parser.parse_args(
        [
            "backtest",
            "--ticker",
            "ZZPURE01",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-10-15",
            "--initial-cash",
            "1000.0",
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
                "backtest",
                "--ticker",
                "ZZPURE01",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-10-15",
                "--initial-cash",
                "1000.0",
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )


def test_no_rebalance_frequency_flag_exists(tmp_path: Path) -> None:
    """§9 / §7 guard G-VB1: there is deliberately no --rebalance-frequency (or similarly-named)
    flag anywhere on this subcommand."""
    parser = main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "backtest",
                "--ticker",
                "ZZPURE01",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-10-15",
                "--initial-cash",
                "1000.0",
                "--db-path",
                str(tmp_path / "mizan.duckdb"),
                "--cache-dir",
                str(tmp_path / "cache"),
                "--rebalance-frequency",
                "daily",
            ]
        )


# ── Boot gate runs first (§8 AC16) ──────────────────────────────────────────────────────────────


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

    monkeypatch.setattr("mizan.cli.backtest.run", _spy_run)

    db_path = tmp_path / "mizan.duckdb"
    exit_code = main.main(
        [
            "backtest",
            "--ticker",
            "ZZPURE01",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-10-15",
            "--initial-cash",
            "1000.0",
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


def test_main_dispatches_to_backtest_run_when_boot_check_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: dict[str, object] = {}

    def _spy_run(args: argparse.Namespace) -> int:
        received["tickers"] = args.tickers
        return 0

    monkeypatch.setattr("mizan.cli.backtest.run", _spy_run)

    exit_code = main.main(
        [
            "backtest",
            "--ticker",
            "ZZPURE01",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-10-15",
            "--initial-cash",
            "1000.0",
            "--db-path",
            str(tmp_path / "mizan.duckdb"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    assert exit_code == 0
    assert received["tickers"] == ["ZZPURE01"]


# ── run(): whole-backtest HALT, read-only connection, stdout summary ────────────────────────────


def _base_args(tmp_path: Path, tickers: list[str]) -> argparse.Namespace:
    return argparse.Namespace(
        tickers=tickers,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 10, 15),
        initial_cash=1_000_000.0,
        db_path=tmp_path / "mizan.duckdb",
        cache_dir=tmp_path / "cache",
        overrides_path=None,
    )


def _no_overrides(path: Path | None) -> BusinessActivityOverrideMap:
    """Stand-in for `load_override_map`, monkeypatched into every `run()` test below so none of
    them depend on a real cache/file layout."""
    return BusinessActivityOverrideMap(overrides={})


def _make_result_envelope() -> ResultEnvelope:
    """PHASE_6_SPEC.md §4.3: `run()` now also calls `purify_backtest_result` on the real,
    caller-supplied `con`/`cache_dir` before printing its summary, so this fixture must carry
    enough real data for that call to succeed with no cache/DB setup of its own: `daily_snapshots`
    non-empty (§3.2's `gross_return`/`net_of_purification_return` need a start/end
    `portfolio_value`) and a `ComplianceStateRecord` for the one dividend-paying ticker, pinned
    `Verdict.PURE` at `verdict_at_ex_date` so `purify_dividend` (`mizan/purification/ledger.py`)
    short-circuits to `None` without ever needing to re-invoke `screen()` (§6a) — the
    `ZZFLIP01` divestment is left ungated (the default `purify_capital_gains.value == False`, §6c),
    so `compute_divestment_attribution` is never called either, and no `compliance_states` entry is
    needed for it.
    """
    result = BacktestResult(
        daily_snapshots=(
            DailySnapshot(
                as_of_date=date(2026, 1, 1),
                cash=0.0,
                holdings={},
                portfolio_value=1_000_000.0,
            ),
            DailySnapshot(
                as_of_date=date(2026, 10, 15),
                cash=0.0,
                holdings={},
                portfolio_value=1_000_000.0,
            ),
        ),
        divestment_events=(
            DivestmentEvent(
                ticker="ZZFLIP01",
                cik="9990000013",
                flip_date=date(2026, 4, 1),
                divest_date=date(2026, 7, 1),
            ),
        ),
        dividend_events=(
            DividendEvent(
                ticker="ZZSTABLE01",
                cik="9990000201",
                ex_date=date(2026, 2, 15),
                div_cash_per_share=2.0,
                quantity_held=100.0,
                cash_received=200.0,
                verdict_at_ex_date=Verdict.PURE,
            ),
        ),
        compliance_states={
            "ZZSTABLE01": ComplianceStateRecord(
                ticker="ZZSTABLE01",
                cik="9990000201",
                state=HoldingComplianceState.HELD_COMPLIANT,
                flip_date=None,
                divest_date=None,
                grace_rebalances_remaining=None,
                verdict_history=(
                    VerdictObservation(as_of_date=date(2026, 1, 1), verdict=Verdict.PURE),
                ),
            ),
        },
    )
    return ResultEnvelope(
        active_caveats=(
            Caveat.LOOK_AHEAD_BIAS,
            Caveat.SURVIVORSHIP_BIAS,
            Caveat.PENDING_SCHOLARLY_VERIFICATION,
        ),
        payload=result.model_dump(),
    )


def test_run_prints_a_summary_and_returns_zero_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    def _run_backtest(**kwargs: object) -> ResultEnvelope:
        return _make_result_envelope()

    monkeypatch.setattr(backtest_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(backtest_cli, "load_override_map", _no_overrides)

    exit_code = backtest_cli.run(_base_args(tmp_path, ["ZZFLIP01", "ZZSTABLE01"]))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Final portfolio value: 1000000.00" in captured.out
    assert "DIVESTED ZZFLIP01" in captured.out
    assert "flip_date=2026-04-01" in captured.out
    assert "divest_date=2026-07-01" in captured.out
    assert "DIVIDENDS ZZSTABLE01" in captured.out
    assert "total_cash_received=200.00" in captured.out
    # PHASE_6_SPEC.md §4.3: the purification summary. ZZSTABLE01's dividend is pinned PURE (no
    # entry) and ZZFLIP01's divestment is left ungated (purify_capital_gains defaults False, no
    # entry either) -> an EMPTY ledger: liability 0.00, gross == net exactly.
    assert "Purification liability: 0.00" in captured.out
    assert "Gross return: 0.000000" in captured.out
    assert "Net-of-purification return: 0.000000" in captured.out
    assert "PURIFIED DIVIDEND" not in captured.out
    assert "PURIFIED DIVESTMENT" not in captured.out


def test_run_prints_a_purified_dividend_line_for_a_mixed_dividend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PHASE_6_SPEC.md §4.3: a nonzero purification liability -- and the `PURIFIED DIVIDEND` line
    it produces -- actually reaches stdout, not just the empty-ledger case above. Real fixture data
    (`ZZMIXED_RATIODRIFT01`) is loaded into `args.db_path`/`args.cache_dir` so `purify_dividend`'s
    own re-invocation of `screen()` (§6a) has something real to resolve.
    """
    from mizan.data import db

    args = _base_args(tmp_path, ["ZZMIXED_RATIODRIFT01"])
    fx.write_universe_cache(args.cache_dir, (fx.ZZMIXED_RATIODRIFT01,))
    con = db.connect(args.db_path)
    fx.load_into_duckdb(con, fx.ZZMIXED_RATIODRIFT01)
    con.close()

    result = BacktestResult(
        daily_snapshots=(
            DailySnapshot(
                as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1_000_000.0
            ),
            DailySnapshot(
                as_of_date=date(2026, 7, 1), cash=0.0, holdings={}, portfolio_value=1_000_000.0
            ),
        ),
        divestment_events=(),
        dividend_events=(
            DividendEvent(
                ticker="ZZMIXED_RATIODRIFT01",
                cik="9990000014",
                ex_date=date(2026, 2, 15),
                div_cash_per_share=5.0,
                quantity_held=10_000.0,
                cash_received=50_000.0,
                verdict_at_ex_date=Verdict.MIXED,
            ),
        ),
        compliance_states={
            "ZZMIXED_RATIODRIFT01": ComplianceStateRecord(
                ticker="ZZMIXED_RATIODRIFT01",
                cik="9990000014",
                state=HoldingComplianceState.HELD_COMPLIANT,
                flip_date=None,
                divest_date=None,
                grace_rebalances_remaining=None,
                verdict_history=(
                    VerdictObservation(as_of_date=date(2026, 1, 1), verdict=Verdict.MIXED),
                ),
            ),
        },
    )
    envelope = ResultEnvelope(
        active_caveats=(
            Caveat.LOOK_AHEAD_BIAS,
            Caveat.SURVIVORSHIP_BIAS,
            Caveat.PENDING_SCHOLARLY_VERIFICATION,
        ),
        payload=result.model_dump(),
    )

    def _run_backtest(**kwargs: object) -> ResultEnvelope:
        return envelope

    monkeypatch.setattr(backtest_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(backtest_cli, "load_override_map", _no_overrides)

    exit_code = backtest_cli.run(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    # 50,000.00 cash received x the 2% ratio pinned as of the ticker's only VerdictObservation.
    assert "Purification liability: 1000.00" in captured.out
    assert "Gross return: 0.000000" in captured.out
    assert "Net-of-purification return: -0.001000" in captured.out
    assert "PURIFIED DIVIDEND ZZMIXED_RATIODRIFT01 ex_date=2026-02-15" in captured.out
    assert "ratio=0.020000" in captured.out
    assert "amount=1000.00" in captured.out


def test_run_halts_on_insufficient_data_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    def _run_backtest(**kwargs: object) -> ResultEnvelope:
        raise InsufficientDataError("no denominator")

    monkeypatch.setattr(backtest_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(backtest_cli, "load_override_map", _no_overrides)

    exit_code = backtest_cli.run(_base_args(tmp_path, ["ZZPURE01"]))
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "HALT" in captured.err


def test_run_halts_on_cik_resolution_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    def _run_backtest(**kwargs: object) -> ResultEnvelope:
        raise CikResolutionError("bad ticker")

    monkeypatch.setattr(backtest_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(backtest_cli, "load_override_map", _no_overrides)

    exit_code = backtest_cli.run(_base_args(tmp_path, ["BAD"]))
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "HALT" in captured.err


def test_run_opens_a_read_only_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """§8 AC14 / G-DB4: `mizan backtest` must never write to DuckDB — proven here by confirming the
    connection `run()` opens is read-only (an INSERT attempted against it would raise)."""
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    captured_con: dict[str, object] = {}

    def _run_backtest(*, con: object, **kwargs: object) -> ResultEnvelope:
        captured_con["con"] = con
        return _make_result_envelope()

    monkeypatch.setattr(backtest_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(backtest_cli, "load_override_map", _no_overrides)

    backtest_cli.run(_base_args(tmp_path, ["ZZPURE01"]))

    con = captured_con["con"]
    with pytest.raises(Exception):  # noqa: B017, PT011 -- duckdb raises its own exception type
        con.execute("CREATE TABLE should_fail (x INTEGER)")  # type: ignore[attr-defined]


def test_run_closes_the_connection_even_on_a_halted_backtest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mizan.data import db

    db.connect(tmp_path / "mizan.duckdb").close()

    def _run_backtest(**kwargs: object) -> ResultEnvelope:
        raise CikResolutionError("always halts")

    monkeypatch.setattr(backtest_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(backtest_cli, "load_override_map", _no_overrides)

    exit_code = backtest_cli.run(_base_args(tmp_path, ["ZZPURE01"]))
    assert exit_code == 1

    con = db.connect(tmp_path / "mizan.duckdb")
    con.close()
