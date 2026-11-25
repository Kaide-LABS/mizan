"""Tests for mizan/crypto/backtest.py Part A/B; see docs/crypto/PHASE_4_SPEC.md A7, B2, B3."""

from __future__ import annotations

import inspect
from datetime import date
from itertools import pairwise

import pydantic
import pytest

from mizan.backtest.portfolio import Holding, Portfolio
from mizan.backtest.strategy import AllocationInstruction
from mizan.core.verdict import Verdict
from mizan.crypto import backtest as crypto_backtest
from mizan.crypto.backtest import (
    BacktestCostParams,
    apply_allocation_with_costs,
    generate_crypto_rebalance_dates,
    run_crypto_backtest,
)


def test_generate_crypto_rebalance_dates_default_interval_over_95_days() -> None:
    start = date(2026, 1, 1)
    end = date(2026, 4, 6)  # 95 days later
    dates = generate_crypto_rebalance_dates(start, end)
    assert dates[0] == start
    for prior, nxt in pairwise(dates):
        assert nxt - prior == __import__("datetime").timedelta(days=30)
    assert dates[-1] <= end


def test_generate_crypto_rebalance_dates_single_day_window_is_one_element() -> None:
    start = date(2026, 1, 1)
    assert generate_crypto_rebalance_dates(start, start) == (start,)


@pytest.mark.parametrize("interval_days", [0, -1])
def test_generate_crypto_rebalance_dates_rejects_non_positive_interval(
    interval_days: int,
) -> None:
    with pytest.raises(ValueError, match="interval_days"):
        generate_crypto_rebalance_dates(
            date(2026, 1, 1), date(2026, 2, 1), interval_days=interval_days
        )


def test_backtest_cost_params_defaults() -> None:
    params = BacktestCostParams()
    assert params.taker_fee_rate == 0.006
    assert params.slippage_rate == 0.0005


def test_backtest_cost_params_taker_fee_rate_cannot_be_zero() -> None:
    with pytest.raises(pydantic.ValidationError):
        BacktestCostParams(taker_fee_rate=0.0)


def test_backtest_cost_params_slippage_rate_cannot_be_zero() -> None:
    with pytest.raises(pydantic.ValidationError):
        BacktestCostParams(slippage_rate=0.0)


def test_apply_allocation_with_costs_one_ticker_buy_known_numbers() -> None:
    portfolio = Portfolio(cash=1000.0, holdings={})
    instruction = AllocationInstruction(target_weights={"BTC": 1.0})
    result = apply_allocation_with_costs(portfolio, instruction, {"BTC": 100.0})
    expected_quantity = 1000.0 / (100.0 * 1.0005 * 1.006)
    assert result.holdings["BTC"].quantity == pytest.approx(expected_quantity)
    assert result.cash == pytest.approx(0.0, abs=1e-6)


def test_apply_allocation_with_costs_one_ticker_sell_receives_less_than_frictionless() -> None:
    portfolio = Portfolio(cash=0.0, holdings={"BTC": Holding(ticker="BTC", quantity=10.0)})
    instruction = AllocationInstruction(target_weights={})
    result = apply_allocation_with_costs(portfolio, instruction, {"BTC": 100.0})
    assert result.cash < 10.0 * 100.0


def test_apply_allocation_with_costs_produces_strictly_lower_value_than_frictionless() -> None:
    from mizan.backtest.portfolio import apply_allocation, mark_to_market

    portfolio = Portfolio(cash=1000.0, holdings={})
    instruction = AllocationInstruction(target_weights={"BTC": 1.0})
    prices = {"BTC": 100.0}
    with_costs = apply_allocation_with_costs(portfolio, instruction, prices)
    frictionless = apply_allocation(portfolio, instruction, prices)
    assert mark_to_market(with_costs, prices) < mark_to_market(frictionless, prices)


def test_apply_allocation_with_costs_fully_invested_never_goes_negative_cash() -> None:
    """§Red-team R1: a fully-invested (sum == 1.0) allocation must still land at cash == 0.0, never
    negative, even after fees/slippage are baked into the execution price."""
    portfolio = Portfolio(cash=1000.0, holdings={})
    instruction = AllocationInstruction(target_weights={"BTC": 0.5, "ETH": 0.5})
    result = apply_allocation_with_costs(portfolio, instruction, {"BTC": 100.0, "ETH": 50.0})
    assert result.cash >= 0.0


def test_apply_allocation_with_costs_leaves_untraded_ticker_price_unchanged() -> None:
    """§A4: "an untraded ticker's quoted price is unchanged, since no leg means no cost" -- a
    ticker already at its target weight (within the 1e-9 tolerance) must trade at its raw quoted
    price, not a cost-adjusted one."""
    portfolio = Portfolio(
        cash=0.0,
        holdings={
            "BTC": Holding(ticker="BTC", quantity=10.0),
            "ETH": Holding(ticker="ETH", quantity=0.0),
        },
    )
    instruction = AllocationInstruction(target_weights={"BTC": 1.0, "ETH": 0.0})
    result = apply_allocation_with_costs(portfolio, instruction, {"BTC": 100.0, "ETH": 50.0})
    # BTC is already fully at its target weight (no leg); its quantity and the portfolio's cash
    # must be exactly as a zero-cost allocation would leave them, proving the raw price was used.
    assert result.holdings["BTC"].quantity == pytest.approx(10.0)
    assert result.cash == pytest.approx(0.0)


def test_a_non_compliant_universe_ticker_is_never_purchasable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    from datetime import UTC, datetime

    import duckdb

    from mizan.crypto import screening as crypto_screening
    from mizan.crypto.models import CandleBar
    from mizan.crypto.universe import CRYPTO_UNIVERSE
    from mizan.data.db import ensure_schema, upsert_candles

    class _Stub:
        def __init__(self, verdict: str) -> None:
            self.payload = {"verdict": verdict}

    def _stub_screen_universe(*, fiqh_params: object = None) -> dict[str, object]:
        # Only BTC/ETH (the seeded, compliant tickers) are PURE; LTC is forced NON_COMPLIANT and
        # every other locked-universe ticker is also NON_COMPLIANT since no candle data for them
        # was seeded in this test.
        out: dict[str, object] = {}
        for ticker in CRYPTO_UNIVERSE:
            is_compliant = ticker in ("BTC", "ETH")
            verdict = Verdict.PURE.value if is_compliant else Verdict.NON_COMPLIANT.value
            out[ticker] = _Stub(verdict)
        return out

    monkeypatch.setattr(crypto_screening, "screen_universe", _stub_screen_universe)

    con = duckdb.connect(":memory:")
    ensure_schema(con)
    tickers = ("BTC", "ETH", "LTC")
    bars = []
    for day in range(3):
        ts = datetime(2026, 1, 1 + day, tzinfo=UTC)
        for ticker in tickers:
            bars.append(
                CandleBar(
                    exchange="coinbase", symbol=ticker, granularity="1d", ts=ts,
                    open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0, source="coinbase",
                )
            )
    upsert_candles(con, tuple(bars))

    envelope = run_crypto_backtest(
        con=con, start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), initial_cash=1000.0,
        interval_days=30,
    )
    payload = envelope.payload
    assert "LTC" in payload["excluded_tickers"]
    for snapshot in payload["daily_snapshots"]:
        assert "LTC" not in snapshot["holdings"]


def test_compliant_universe_is_read_fresh_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    from mizan.crypto import screening as crypto_screening
    from mizan.crypto.backtest import _compliant_universe_tickers
    from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS

    calls = {"n": 0}

    def _stub(*, fiqh_params: object = None) -> dict[str, object]:
        calls["n"] += 1
        verdict = Verdict.PURE if calls["n"] == 1 else Verdict.NON_COMPLIANT

        class _Stub:
            def __init__(self) -> None:
                self.payload = {"verdict": verdict.value}

        from mizan.crypto.universe import CRYPTO_UNIVERSE

        return {ticker: _Stub() for ticker in CRYPTO_UNIVERSE}

    monkeypatch.setattr(crypto_screening, "screen_universe", _stub)

    first = _compliant_universe_tickers(fiqh_params=CRYPTO_FIQH_PARAMS)
    second = _compliant_universe_tickers(fiqh_params=CRYPTO_FIQH_PARAMS)
    assert first != second


def test_run_crypto_backtest_has_no_caller_supplied_universe_parameter() -> None:
    params = inspect.signature(run_crypto_backtest).parameters
    assert "tickers" not in params
    assert "universe" not in params


def test_apply_allocation_referenced_only_inside_apply_allocation_with_costs() -> None:
    """§Implications S6: no second call site in this module bypasses the cost wrapper."""
    source = crypto_backtest.__file__
    import pathlib

    text = pathlib.Path(source).read_text(encoding="utf-8")
    lines = text.splitlines()
    call_lines = [
        i for i, line in enumerate(lines)
        if "apply_allocation(" in line and "apply_allocation_with_costs(" not in line
    ]
    assert len(call_lines) == 1
    body_start = next(
        i for i, line in enumerate(lines)
        if line.startswith("def apply_allocation_with_costs")
    )
    body_end = next(
        i for i, line in enumerate(lines)
        if i > body_start and line.startswith("def ")
    )
    assert body_start <= call_lines[0] < body_end
