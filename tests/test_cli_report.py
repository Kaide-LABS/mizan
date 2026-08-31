"""Tests for mizan/cli/report.py and its wiring into mizan/cli/main.py.

Implements PHASE_7_SPEC.md §8 acceptance criteria 7 (end-to-end pipeline, including both plot
empty-input branches), 11 (con/cache_dir/overrides reused, never re-loaded), 12 (never touches
DuckDB beyond the one read-only connection), 14 (`mizan report` completes the four-verb CLI set),
22 (boundary greps), plus guard G-R8.
"""

from __future__ import annotations

import argparse
import base64
import inspect
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mizan.backtest.clock import BacktestResult, DailySnapshot, run_backtest
from mizan.backtest.compliance_state import (
    ComplianceStateRecord,
    DivestmentEvent,
    DividendEvent,
    HoldingComplianceState,
    VerdictObservation,
)
from mizan.backtest.strategy import EqualWeightStrategy
from mizan.cli import main
from mizan.cli import report as report_cli
from mizan.config.boot_check import InvariantViolationError
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict
from mizan.data import db
from mizan.purification.ledger import PurificationLedger, purify_backtest_result
from mizan.screening.business_activity import BusinessActivityOverrideMap
from mizan.screening.verdict import InsufficientDataError
from tests.fixtures import synthetic_universe as fx

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

# ── CLI argument wiring ──────────────────────────────────────────────────────────────────────────


def test_tickers_dates_paths_cash_and_output_path_are_parsed(tmp_path: Path) -> None:
    parser = main.build_parser()
    args = parser.parse_args(
        [
            "report",
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
            "--output-path",
            str(tmp_path / "out.html"),
        ]
    )
    assert args.tickers == ["ZZPURE01", "ZZMIXED01"]
    assert args.start_date == date(2026, 1, 1)
    assert args.end_date == date(2026, 10, 15)
    assert args.initial_cash == pytest.approx(1_000_000.0)
    assert args.db_path == tmp_path / "mizan.duckdb"
    assert args.cache_dir == tmp_path / "cache"
    assert args.overrides_path is None
    assert args.output_path == tmp_path / "out.html"


def test_output_path_is_required(tmp_path: Path) -> None:
    parser = main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "report",
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


def test_db_path_has_no_default_and_is_required(tmp_path: Path) -> None:
    parser = main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "report",
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
                "--output-path",
                str(tmp_path / "out.html"),
            ]
        )


# ── §8 AC14: `mizan report` completes the four-verb CLI set ───────────────────────────────────────


def test_main_help_lists_all_four_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    parser = main.build_parser()
    help_text = parser.format_help()
    for verb in ("ingest", "screen", "backtest", "report"):
        assert verb in help_text


def test_report_help_shows_output_path_flag(capsys: pytest.CaptureFixture[str]) -> None:
    parser = main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["report", "--help"])
    help_text = capsys.readouterr().out
    assert "--output-path" in help_text


# ── Boot gate runs first ────────────────────────────────────────────────────────────────────────


def test_main_halts_on_invariant_violation_before_report_handler_runs(
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

    monkeypatch.setattr("mizan.cli.report.run", _spy_run)

    db_path = tmp_path / "mizan.duckdb"
    exit_code = main.main(
        [
            "report",
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
            "--output-path",
            str(tmp_path / "out.html"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "BOOT FAILED" in captured.err
    assert handler_was_called is False
    assert not db_path.exists()


def test_main_dispatches_to_report_run_when_boot_check_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: dict[str, object] = {}

    def _spy_run(args: argparse.Namespace) -> int:
        received["tickers"] = args.tickers
        received["output_path"] = args.output_path
        return 0

    monkeypatch.setattr("mizan.cli.report.run", _spy_run)

    exit_code = main.main(
        [
            "report",
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
            "--output-path",
            str(tmp_path / "out.html"),
        ]
    )

    assert exit_code == 0
    assert received["tickers"] == ["ZZPURE01"]
    assert received["output_path"] == tmp_path / "out.html"


# ── run(): read-only connection, HALT contract, con/cache_dir/overrides reuse ─────────────────────


def _base_args(tmp_path: Path, tickers: list[str], *, start: date, end: date) -> argparse.Namespace:
    return argparse.Namespace(
        tickers=tickers,
        start_date=start,
        end_date=end,
        initial_cash=1_000_000.0,
        db_path=tmp_path / "mizan.duckdb",
        cache_dir=tmp_path / "cache",
        overrides_path=None,
        output_path=tmp_path / "out.html",
    )


def _no_overrides(path: Path | None) -> BusinessActivityOverrideMap:
    return BusinessActivityOverrideMap(overrides={})


def _make_result_envelope() -> ResultEnvelope:
    """Mirrors `tests/test_cli_backtest.py`'s own `_make_result_envelope` exactly: enough real
    data for `purify_backtest_result` to succeed with no cache/DB setup of its own (the one
    dividend is pinned `Verdict.PURE`, so `purify_dividend` short-circuits without re-invoking
    `screen()`; the one divestment is left ungated by the default `purify_capital_gains.value ==
    False`)."""
    result = BacktestResult(
        daily_snapshots=(
            DailySnapshot(
                as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1_000_000.0
            ),
            DailySnapshot(
                as_of_date=date(2026, 10, 15), cash=0.0, holdings={}, portfolio_value=1_000_000.0
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


def test_run_opens_a_read_only_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db.connect(tmp_path / "mizan.duckdb").close()

    captured_con: dict[str, object] = {}

    def _run_backtest(*, con: object, **kwargs: object) -> object:
        captured_con["con"] = con
        return _make_result_envelope()

    monkeypatch.setattr(report_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(report_cli, "load_override_map", _no_overrides)

    report_cli.run(
        _base_args(
            tmp_path, ["ZZFLIP01", "ZZSTABLE01"], start=date(2026, 1, 1), end=date(2026, 10, 15)
        )
    )

    con = captured_con["con"]
    with pytest.raises(Exception):  # noqa: B017, PT011 -- duckdb raises its own exception type
        con.execute("CREATE TABLE should_fail (x INTEGER)")  # type: ignore[attr-defined]


def test_run_halts_on_insufficient_data_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db.connect(tmp_path / "mizan.duckdb").close()

    def _run_backtest(**kwargs: object) -> object:
        raise InsufficientDataError("no denominator")

    monkeypatch.setattr(report_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(report_cli, "load_override_map", _no_overrides)

    exit_code = report_cli.run(
        _base_args(tmp_path, ["ZZPURE01"], start=date(2026, 1, 1), end=date(2026, 10, 15))
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "HALT" in captured.err


def test_run_reuses_caller_supplied_con_cache_dir_and_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """§8 AC11 / §7 G-R8: run_backtest and purify_backtest_result must be threaded the exact same
    con/cache_dir/overrides, never a freshly-opened connection or re-loaded override map."""
    db.connect(tmp_path / "mizan.duckdb").close()

    run_backtest_kwargs: dict[str, object] = {}
    purify_kwargs: dict[str, object] = {}

    empty_ledger = PurificationLedger(
        dividend_entries=(),
        divestment_entries=(),
        purification_liability=0.0,
        gross_return=0.0,
        net_of_purification_return=0.0,
    )

    def _fake_result() -> BacktestResult:
        return BacktestResult(
            daily_snapshots=(
                DailySnapshot(
                    as_of_date=date(2026, 1, 1), cash=0.0, holdings={}, portfolio_value=1_000.0
                ),
            ),
            divestment_events=(),
            dividend_events=(),
            compliance_states={},
        )

    def _run_backtest(**kwargs: object) -> object:
        from mizan.core.caveats import Caveat, ResultEnvelope

        run_backtest_kwargs.update(kwargs)
        return ResultEnvelope(
            active_caveats=(
                Caveat.LOOK_AHEAD_BIAS,
                Caveat.SURVIVORSHIP_BIAS,
                Caveat.PENDING_SCHOLARLY_VERIFICATION,
            ),
            payload=_fake_result().model_dump(),
        )

    def _purify_backtest_result(result: BacktestResult, **kwargs: object) -> BacktestResult:
        purify_kwargs.update(kwargs)
        return result.model_copy(update={"purification_ledger": empty_ledger.model_dump()})

    monkeypatch.setattr(report_cli, "run_backtest", _run_backtest)
    monkeypatch.setattr(report_cli, "purify_backtest_result", _purify_backtest_result)
    monkeypatch.setattr(report_cli, "load_override_map", _no_overrides)

    exit_code = report_cli.run(
        _base_args(tmp_path, ["ZZPURE01"], start=date(2026, 1, 1), end=date(2026, 10, 15))
    )

    assert exit_code == 0
    assert run_backtest_kwargs["con"] is purify_kwargs["con"]
    assert run_backtest_kwargs["cache_dir"] is purify_kwargs["cache_dir"]
    assert run_backtest_kwargs["overrides"] is purify_kwargs["overrides"]


# ── §8 AC7: the full pipeline runs end-to-end against the synthetic fixture, no crash ─────────────


def _build_db(tmp_path: Path, tickers: Sequence[fx.SyntheticTicker]) -> duckdb.DuckDBPyConnection:
    fx.write_universe_cache(tmp_path, tickers)
    con = db.connect(tmp_path / "test.duckdb")
    for ticker in tickers:
        fx.load_into_duckdb(con, ticker)
    return con


def test_report_end_to_end_produces_a_nonempty_html_file_with_nonzero_purification(
    tmp_path: Path,
) -> None:
    con = _build_db(tmp_path, (fx.ZZMIXED_RATIODRIFT01,))
    con.close()

    output_path = tmp_path / "report.html"
    args = argparse.Namespace(
        tickers=["ZZMIXED_RATIODRIFT01"],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 7, 1),
        initial_cash=1_000_000.0,
        db_path=tmp_path / "test.duckdb",
        cache_dir=tmp_path,
        overrides_path=None,
        output_path=output_path,
    )

    exit_code = report_cli.run(args)

    assert exit_code == 0
    assert output_path.exists()
    generated_html = output_path.read_text(encoding="utf-8")
    assert len(generated_html) > 0
    assert 'id="caveats"' in generated_html
    assert 'id="gross-return"' in generated_html
    assert 'id="net-of-purification-return"' in generated_html
    # A real, non-empty purification liability -- proving the reporter actually reached a nonzero
    # ledger through the real screen()/run_backtest()/purify_backtest_result() pipeline.
    assert "Purification liability: 0.00" not in generated_html
    # Exactly one file written to disk -- no sibling image files (§6e, §8 AC9).
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".html") == ["report.html"]


def test_report_end_to_end_handles_an_empty_backtest_window_reaching_both_plot_empty_branches(
    tmp_path: Path,
) -> None:
    """A window with zero trading days for the given ticker set produces empty daily_snapshots,
    which (per mizan.purification.ledger._compute_returns's own documented posture) implies an
    empty PurificationLedger too -- reaching BOTH render_equity_curve_plot's and
    render_purification_by_ticker_plot's own empty-input branches in the same run, proving those
    placeholder-rendering paths are real, not theoretical (§7 guard G-R9, §8 AC7)."""
    con = _build_db(tmp_path, (fx.ZZPURE01,))
    con.close()

    output_path = tmp_path / "empty_report.html"
    args = argparse.Namespace(
        tickers=["ZZPURE01"],
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 2),
        initial_cash=1_000_000.0,
        db_path=tmp_path / "test.duckdb",
        cache_dir=tmp_path,
        overrides_path=None,
        output_path=output_path,
    )

    exit_code = report_cli.run(args)

    assert exit_code == 0
    assert output_path.exists()
    generated_html = output_path.read_text(encoding="utf-8")
    # §4.2's "No trading days..."/"No purification liability..." annotations are drawn INSIDE the
    # rendered PNG raster, not as literal HTML text -- what an end-to-end HTML-side check can
    # confirm is that both plots still embed as valid, non-empty, inline-base64 PNGs rather than
    # the run crashing or silently omitting a plot.
    img_srcs = re.findall(r'<img src="data:image/png;base64,([^"]+)"', generated_html)
    assert len(img_srcs) == 2
    for encoded in img_srcs:
        decoded = base64.b64decode(encoded)
        assert decoded.startswith(b"\x89PNG\r\n\x1a\n")
    assert "Purification liability: 0.00" in generated_html
    assert 'id="gross-return"' in generated_html


# ── §7 guard G-R8 / §8 AC12: cross-check against the real run_backtest/purify_backtest_result ─────


def test_run_uses_the_same_run_backtest_and_purify_backtest_result_functions_as_backtest_cli() -> (
    None
):
    """Confirms `mizan/cli/report.py` calls the SAME two Phase 5/6 entry points
    `mizan/cli/backtest.py` already established, not a re-implementation of its own. Uses
    `getattr` (rather than static dotted access) so `--strict`'s `no_implicit_reexport` does not
    treat this as a typed public-API assertion about `mizan.cli.report`'s own export surface."""
    assert getattr(report_cli, "run_backtest") is run_backtest  # noqa: B009
    assert getattr(report_cli, "purify_backtest_result") is purify_backtest_result  # noqa: B009
    assert getattr(report_cli, "EqualWeightStrategy") is EqualWeightStrategy  # noqa: B009


# ── §7 guards: package-wide greps, re-run as tests (§8 AC22) ──────────────────────────────────────


def test_no_llm_import_in_cli_report() -> None:
    source = inspect.getsource(report_cli).lower()
    for forbidden in (
        "openai",
        "anthropic",
        "gemini",
        "vertex",
        "langchain",
        "chat_completion",
        "completion(",
    ):
        assert forbidden not in source


_BOUNDARY_WORDS = (
    "short",
    "shorts",
    "shorting",
    "borrow",
    "borrowed",
    "borrowing",
    "margin",
    "leverage",
    "leveraged",
    "levered",
    "option",
    "options",
    "future",
    "futures",
    "swap",
    "swaps",
    "derivative",
    "derivatives",
)


def test_no_boundary_crossing_primitive_named_in_cli_report() -> None:
    source = inspect.getsource(report_cli).lower()
    for word in _BOUNDARY_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b")
        assert not pattern.search(source), f"cli/report.py names forbidden concept {word!r}"


def test_render_report_call_site_always_supplies_active_caveats() -> None:
    """§7 guard G-R1: the one call site to render_report in mizan/ always passes
    active_caveats= explicitly."""
    source = inspect.getsource(report_cli)
    assert "render_report(report_input, active_caveats=envelope.active_caveats)" in source
