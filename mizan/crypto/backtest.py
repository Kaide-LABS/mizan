"""mizan/crypto/backtest.py — the crypto baseline backtest engine.

Implements ``docs/crypto/PHASE_4_SPEC.md`` Part A and Part B.

A new, parallel module rather than an extension of ``mizan/backtest/``: ``mizan.backtest.portfolio``
(``Portfolio``, ``Holding``, ``apply_allocation``, ``mark_to_market``) and
``mizan.backtest.strategy`` (``AllocationInstruction``, ``Strategy``, ``EqualWeightStrategy``,
``StrategyContractViolationError``) are already fully equity-agnostic and are reused here **as-is,
with zero modification** (§A1).
The equity rebalance clock and compliance-state machine are **not** reused — they are
deeply equity-coupled (hardcoded quarterly cadence, ``price_bars`` SQL, a flip->grace->divest state
machine crypto's static classification map gives nothing to observe) — so this module builds its own
parallel rebalance-date generator, candle-reading helpers, and entry point instead (§A1).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from mizan.backtest.portfolio import Portfolio, apply_allocation, mark_to_market
from mizan.backtest.strategy import (
    AllocationInstruction,
    EqualWeightStrategy,
    Strategy,
    StrategyContractViolationError,
)
from mizan.core.base import MizanBaseModel
from mizan.core.caveats import Caveat, ResultEnvelope
from mizan.core.verdict import Verdict
from mizan.crypto import screening as crypto_screening
from mizan.crypto.fiqh_register import CRYPTO_FIQH_PARAMS, CryptoFiqhParams
from mizan.crypto.universe import CRYPTO_UNIVERSE

if TYPE_CHECKING:
    import duckdb


class BacktestCostParams(MizanBaseModel):
    """Per-side taker fee and slippage, both structurally forbidden from being exactly zero
    (``Field(gt=0.0)``) — PRD "costs never zero by default" read as a construction-time fact, not
    merely a non-zero default a caller could override away (§A2, §Spec assumptions)."""

    taker_fee_rate: float = Field(default=0.006, gt=0.0)
    slippage_rate: float = Field(default=0.0005, gt=0.0)


DEFAULT_BACKTEST_COST_PARAMS = BacktestCostParams()
_DEFAULT_STRATEGY = EqualWeightStrategy()


class DailySnapshot(MizanBaseModel):
    """One trading day's mark-to-market state for the crypto backtest. A new, parallel type
    rather than a reuse of the equity backtest clock's own snapshot type — that module is not
    reused by this phase at all (§A1); the scope guard in `tests/test_phase1_scope.py` enforces
    that `mizan/crypto/` never names the equity rebalance clock module."""

    as_of_date: date
    cash: float
    holdings: dict[str, float]
    portfolio_value: float


def generate_crypto_rebalance_dates(
    start_date: date, end_date: date, *, interval_days: int = 30
) -> tuple[date, ...]:
    """Pure function. ``start_date`` is always the first rebalance (matches
    the equity backtest clock's own analogous generator's own "deploy capital on day one"
    convention); every subsequent rebalance is exactly ``interval_days`` calendar days after the
    previous one, continuing while the candidate date is ``<= end_date``. Unlike the equity
    function, there is no calendar-month snapping (§A3).
    """
    if interval_days <= 0:
        raise ValueError(f"interval_days must be > 0; got {interval_days!r}")
    dates: list[date] = [start_date]
    candidate = start_date + timedelta(days=interval_days)
    while candidate <= end_date:
        dates.append(candidate)
        candidate += timedelta(days=interval_days)
    return tuple(dates)


def apply_allocation_with_costs(
    portfolio: Portfolio,
    instruction: AllocationInstruction,
    prices: dict[str, float],
    *,
    cost_params: BacktestCostParams = DEFAULT_BACKTEST_COST_PARAMS,
) -> Portfolio:
    """Rebalance ``portfolio`` to ``instruction.target_weights`` at ``prices`` (always the
    unadjusted candle ``close``), with a per-side taker fee and slippage baked into the execution
    price of every TRADED ticker only (§A4). Costs are baked into the per-unit execution price
    rather than deducted from cash in a second step, so every one of the reused, unmodified
    ``apply_allocation``'s own non-negativity guarantees (``Holding.quantity``/``Portfolio.cash``
    ``Field(ge=0.0)``) carry over to the cost-aware path completely unmodified (§A4, §Red-team R1).
    """
    total_value = mark_to_market(portfolio, prices)
    tolerance = 1e-9
    adjusted_prices = dict(prices)
    tickers = set(instruction.target_weights) | set(portfolio.holdings)
    for ticker in tickers:
        price = prices[ticker]
        target_value = instruction.target_weights.get(ticker, 0.0) * total_value
        current_holding = portfolio.holdings.get(ticker)
        current_value = current_holding.quantity * price if current_holding is not None else 0.0
        if target_value > current_value + tolerance:
            adjusted_prices[ticker] = price * (1.0 + cost_params.slippage_rate) * (
                1.0 + cost_params.taker_fee_rate
            )
        elif target_value < current_value - tolerance:
            adjusted_prices[ticker] = price * (1.0 - cost_params.slippage_rate) * (
                1.0 - cost_params.taker_fee_rate
            )
    return apply_allocation(portfolio, instruction, adjusted_prices)


def _compliant_universe_tickers(
    *, fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS
) -> frozenset[str]:
    """The subset of the locked 14-token ``CRYPTO_UNIVERSE`` whose fresh
    ``mizan.crypto.screening.screen_universe`` verdict is ``Verdict.PURE``. Imported and called via
    the module path (``mizan.crypto.screening``), never a bare-name import, and read fresh on every
    call — never cached at import time (§A6, §Red-team R2)."""
    verdicts = crypto_screening.screen_universe(fiqh_params=fiqh_params)
    return frozenset(
        ticker
        for ticker in CRYPTO_UNIVERSE
        if Verdict(str(verdicts[ticker].payload["verdict"])) is Verdict.PURE
    )


def _resolve_candle_dates(
    con: duckdb.DuckDBPyConnection,
    symbols: frozenset[str],
    granularity: str,
    start_date: date,
    end_date: date,
) -> tuple[date, ...]:
    """Every distinct ``DATE(ts)`` present in ``candles`` for ``symbols``/``granularity``, between
    ``start_date`` and ``end_date`` inclusive, ascending (§A5)."""
    if not symbols:
        return ()
    placeholders = ",".join("?" for _ in symbols)
    rows = con.execute(
        f"SELECT DISTINCT DATE(ts) FROM candles WHERE symbol IN ({placeholders}) "
        "AND granularity = ? AND DATE(ts) BETWEEN ? AND ? ORDER BY DATE(ts)",
        [*sorted(symbols), granularity, start_date, end_date],
    ).fetchall()
    return tuple(row[0] for row in rows)


def _resolve_day_closes(
    con: duckdb.DuckDBPyConnection,
    symbols: frozenset[str],
    granularity: str,
    as_of_date: date,
) -> dict[str, float]:
    """``{symbol: close}`` for every symbol with a ``candles`` row at ``as_of_date``'s UTC
    00:00:00 timestamp (§A5)."""
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    rows = con.execute(
        f"SELECT symbol, close FROM candles WHERE symbol IN ({placeholders}) "
        "AND granularity = ? AND DATE(ts) = ?",
        [*sorted(symbols), granularity, as_of_date],
    ).fetchall()
    return {str(symbol): float(close) for symbol, close in rows}


class CryptoBacktestResult(MizanBaseModel):
    """The Phase 4 result payload, wrapped in ``ResultEnvelope`` by ``run_crypto_backtest``."""

    strategy_label: Literal["baseline"] = "baseline"
    daily_snapshots: tuple[DailySnapshot, ...]
    rebalance_dates: tuple[date, ...]
    excluded_tickers: tuple[str, ...]
    cost_params: BacktestCostParams


def run_crypto_backtest(
    *,
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    initial_cash: float,
    strategy: Strategy = _DEFAULT_STRATEGY,
    interval_days: int = 30,
    cost_params: BacktestCostParams = DEFAULT_BACKTEST_COST_PARAMS,
    fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS,
    granularity: str = "1d",
) -> ResultEnvelope:
    """The canonical Phase 4 entry point: equal-weight long-only buy-and-hold over the
    screened/compliant subset of the locked 14-token ``CRYPTO_UNIVERSE``, with a configurable
    periodic rebalance cadence over the 24/7 clock, explicitly labelled ``"baseline"`` (§B1).

    Takes no ``tickers``/``universe`` parameter — the locked 14-token universe cannot be widened or
    narrowed by a caller (§B1, §Spec assumptions).
    """
    compliant = _compliant_universe_tickers(fiqh_params=fiqh_params)
    excluded_tickers = tuple(sorted(frozenset(CRYPTO_UNIVERSE) - compliant))
    rebalance_dates = generate_crypto_rebalance_dates(
        start_date, end_date, interval_days=interval_days
    )
    rebalance_date_set = frozenset(rebalance_dates)
    trading_dates = _resolve_candle_dates(con, compliant, granularity, start_date, end_date)

    portfolio = Portfolio(cash=initial_cash, holdings={})
    snapshots: list[DailySnapshot] = []

    for as_of_date in trading_dates:
        closes = _resolve_day_closes(con, compliant, granularity, as_of_date)
        if as_of_date in rebalance_date_set:
            instruction = strategy.select(
                as_of_date=as_of_date, compliant_tickers=compliant, portfolio=portfolio
            )
            offending = frozenset(instruction.target_weights) - compliant
            if offending:
                raise StrategyContractViolationError(
                    f"strategy {strategy!r} returned target_weights naming ticker(s) "
                    f"{sorted(offending)} outside compliant_tickers {sorted(compliant)}"
                )
            portfolio = apply_allocation_with_costs(
                portfolio, instruction, closes, cost_params=cost_params
            )
        snapshots.append(
            DailySnapshot(
                as_of_date=as_of_date,
                cash=portfolio.cash,
                holdings={t: h.quantity for t, h in portfolio.holdings.items()},
                portfolio_value=mark_to_market(portfolio, closes),
            )
        )

    result = CryptoBacktestResult(
        strategy_label="baseline",
        daily_snapshots=tuple(snapshots),
        rebalance_dates=rebalance_dates,
        excluded_tickers=excluded_tickers,
        cost_params=cost_params,
    )
    return ResultEnvelope(
        active_caveats=(Caveat.SURVIVORSHIP_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION),
        payload=result.model_dump(),
    )
