"""Full equal-weight baseline integration test; see docs/crypto/PHASE_4_SPEC.md B4."""

from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from mizan.config import boot_check
from mizan.crypto.backtest import (
    DEFAULT_BACKTEST_COST_PARAMS,
    generate_crypto_rebalance_dates,
    run_crypto_backtest,
)
from mizan.crypto.models import CandleBar
from mizan.data.db import ensure_schema, upsert_candles

_TICKERS = ("BTC", "ETH", "LTC")
_PRICES = {"BTC": 100.0, "ETH": 50.0, "LTC": 10.0}
_START = date(2026, 1, 1)
_END = date(2026, 3, 6)  # 65 days later


@pytest.fixture(autouse=True)
def _restrict_compliant_universe_to_seeded_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    """This B4 test seeds candles for only three of the locked 14 `CRYPTO_UNIVERSE` tickers
    (§B4's own "e.g. BTC, ETH, LTC"); under the real classification map all 14 are `PURE`
    (docs/crypto/PHASE_3_SPEC.md B2's own finding), so the compliant set must be narrowed to the
    three actually-ingested tickers here, the same monkeypatch technique B2's own
    `test_a_non_compliant_universe_ticker_is_never_purchasable` uses, rather than this test
    asserting anything about real-world screening."""
    monkeypatch.setattr(
        "mizan.crypto.backtest._compliant_universe_tickers",
        lambda *, fiqh_params=None: frozenset(_TICKERS),
    )


def _seed_db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    ensure_schema(con)
    bars = []
    for day_offset in range(65):
        ts = datetime(2026, 1, 1, tzinfo=UTC) + __import__("datetime").timedelta(days=day_offset)
        for ticker in _TICKERS:
            bars.append(
                CandleBar(
                    exchange="coinbase", symbol=ticker, granularity="1d", ts=ts,
                    open=_PRICES[ticker], high=_PRICES[ticker], low=_PRICES[ticker],
                    close=_PRICES[ticker], volume=1.0, source="coinbase",
                )
            )
    upsert_candles(con, tuple(bars))
    return con


def test_baseline_run_is_labelled_and_rebalances_on_schedule() -> None:
    con = _seed_db()
    envelope = run_crypto_backtest(
        con=con, start_date=_START, end_date=_END, initial_cash=1000.0, interval_days=30,
    )
    payload = envelope.payload
    assert payload["strategy_label"] == "baseline"
    expected_rebalances = generate_crypto_rebalance_dates(_START, _END, interval_days=30)
    assert len(payload["rebalance_dates"]) == len(expected_rebalances) == 3
    assert len(payload["daily_snapshots"]) == 65


def test_baseline_run_ends_up_equal_weighted_across_the_three_tickers() -> None:
    con = _seed_db()
    envelope = run_crypto_backtest(
        con=con, start_date=_START, end_date=_END, initial_cash=1000.0, interval_days=30,
    )
    final = envelope.payload["daily_snapshots"][-1]
    total_value = final["portfolio_value"]
    for ticker in _TICKERS:
        quantity = final["holdings"][ticker]
        share = (quantity * _PRICES[ticker]) / total_value
        assert share == pytest.approx(1.0 / 3.0, abs=0.02)


def test_costs_make_the_baseline_run_strictly_worse_than_a_frictionless_equivalent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mizan.backtest.portfolio import apply_allocation

    con_with_costs = _seed_db()
    with_costs = run_crypto_backtest(
        con=con_with_costs, start_date=_START, end_date=_END, initial_cash=1000.0,
        interval_days=30, cost_params=DEFAULT_BACKTEST_COST_PARAMS,
    )

    con_frictionless = _seed_db()
    monkeypatch.setattr(
        "mizan.crypto.backtest.apply_allocation_with_costs",
        lambda portfolio, instruction, prices, *, cost_params=DEFAULT_BACKTEST_COST_PARAMS: (
            apply_allocation(portfolio, instruction, prices)
        ),
    )
    import mizan.crypto.backtest as crypto_backtest_module

    frictionless = crypto_backtest_module.run_crypto_backtest(
        con=con_frictionless, start_date=_START, end_date=_END, initial_cash=1000.0,
        interval_days=30,
    )

    final_with_costs = with_costs.payload["daily_snapshots"][-1]["portfolio_value"]
    final_frictionless = frictionless.payload["daily_snapshots"][-1]["portfolio_value"]
    assert final_with_costs < final_frictionless


def test_boot_check_still_passes_after_a_full_baseline_run() -> None:
    con = _seed_db()
    run_crypto_backtest(
        con=con, start_date=_START, end_date=_END, initial_cash=1000.0, interval_days=30,
    )
    boot_check.check_all()
