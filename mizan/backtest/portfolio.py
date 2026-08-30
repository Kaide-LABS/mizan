"""mizan/backtest/portfolio.py — holdings and cash bookkeeping.

Implements PHASE_5_SPEC.md §3.1, §4.1, §6a.

Every model here inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no model in this module subclasses Pydantic's own shared base model
directly. Because every model is frozen, a `Portfolio` is an immutable snapshot: every function
below returns a *new* `Portfolio`/`Holding` rather than mutating one in place (PHASE_5_SPEC.md §3's
own governing design note).

**`raw_close`, never `adj_close`, governs every valuation/trade-sizing computation in this module**
(PHASE_5_SPEC.md §6a): Tiingo's `adj_close` already bakes in an assumption that every dividend was
reinvested at the time it was paid, but Mizan's own architecture credits a dividend to `cash`
explicitly (`credit_dividend`) so Phase 6 can later purify it — valuing a held position with
`adj_close` while ALSO crediting `div_cash` to cash would double-count every dividend. Splits and
dividends are therefore handled explicitly and separately here (`apply_split`, `credit_dividend`)
rather than implicitly via an adjusted price series. Every caller-supplied `prices`/`price` value in
this module is always `raw_close`; no function here queries DuckDB itself.
"""

from __future__ import annotations

from pydantic import Field

from mizan.backtest.strategy import AllocationInstruction
from mizan.config.invariants import INVARIANTS
from mizan.core.base import MizanBaseModel


class Holding(MizanBaseModel):
    """One position. `quantity` is constrained NON-NEGATIVE at the type level — `Field(ge=0.0)`, not
    a runtime `if quantity < 0: raise` check a caller could route around. Constructing
    `Holding(ticker="X", quantity=-1.0)` raises `pydantic.ValidationError` immediately, before the
    value can reach a `Portfolio`, `AllocationInstruction`, or anywhere else (`ULTIMATE_PRD.md` §5
    check 3: "negative position quantities" are a short position in disguise — permanently
    forbidden, `mizan.config.invariants.INVARIANTS.long_only`). Fractional (non-integer)
    quantities are permitted — a backtest weight-targeting strategy naturally produces
    fractional shares; V1 does not model whole-share/lot-size trading constraints
    (PHASE_5_SPEC.md §9).
    """

    ticker: str
    quantity: float = Field(ge=0.0)


class Portfolio(MizanBaseModel):
    """One immutable snapshot of the whole book: cash plus every currently-held position.

    `cash` is constrained NON-NEGATIVE at the type level (`Field(ge=0.0)`) —
    `mizan.config.invariants.INVARIANTS.fully_funded` means the portfolio can never spend more cash
    than it has; constructing a `Portfolio` with negative cash (an implicit margin loan) raises
    `pydantic.ValidationError` immediately, the same type-level guard `Holding.quantity` gives
    shorting. `holdings` omits a ticker entirely once its position reaches exactly `0.0` — an
    explicit `Holding(ticker=..., quantity=0.0)` entry is never retained (§6a), so `len(holdings)`
    always equals the number of tickers ACTUALLY held, not the number ever held.
    """

    cash: float = Field(ge=0.0)
    holdings: dict[str, Holding]


def apply_cash_yield(portfolio: Portfolio) -> Portfolio:
    """Return a new `Portfolio` with cash multiplied by `(1.0 + INVARIANTS.cash_yield)` — imported
    and read DIRECTLY from `mizan.config.invariants.INVARIANTS` inside this function body, never
    accepted as a parameter, never re-declared as a bare `0.0` literal a second time (§7 guard
    G-B1). Since `INVARIANTS.cash_yield` is permanently `0.0` (boot-gated, §7 guard G-B1a), this is
    a structural no-op today — cash after this call is bit-for-bit identical to cash before it —
    but it is expressed as a genuine read of config rather than an assumption, so a future
    accidental change to `Invariants.cash_yield`'s default (which `mizan-boot-check`/`mizan`'s own
    centralized `check_all()` would already HALT on before any simulation starts, §7 guard G-B1a)
    is caught by TWO independent mechanisms, not silently trusted to only one.
    """
    new_cash = portfolio.cash * (1.0 + INVARIANTS.cash_yield)
    return portfolio.model_copy(update={"cash": new_cash})


def apply_split(holding: Holding, split_factor: float) -> Holding:
    """Return a new `Holding` with `quantity` adjusted for one day's `price_bars.split_factor`.

    **Multiplication direction, verified live 2026-08-31 (not recalled), logged in
    `docs/modernization_log.md` §6.2b:** Tiingo's own documentation states `splitFactor =
    splitTo/splitFrom` — a 2-for-1 split carries `splitFactor = 2.0`, and 100 held shares become
    `100 * 2.0 = 200` shares. `quantity` is therefore MULTIPLIED by `split_factor`, never divided.
    """
    new_quantity = holding.quantity * split_factor
    return holding.model_copy(update={"quantity": new_quantity})


def mark_to_market(portfolio: Portfolio, prices: dict[str, float]) -> float:
    """Portfolio value = `portfolio.cash + sum(holding.quantity * prices[holding.ticker] for holding
    in portfolio.holdings.values())`. `prices` is caller-supplied (always `raw_close`, §6a) — this
    function does no DB I/O itself, keeping it a pure, trivially-testable arithmetic function.
    """
    holdings_value = sum(
        holding.quantity * prices[ticker] for ticker, holding in portfolio.holdings.items()
    )
    return portfolio.cash + holdings_value


def credit_dividend(portfolio: Portfolio, ticker: str, div_cash_per_share: float) -> Portfolio:
    """Return a new `Portfolio` with `cash` increased by `div_cash_per_share * portfolio.holdings[
    ticker].quantity` (`0.0` if `ticker` is not currently held — a no-op, not an error, since
    `price_bars` covers every ticker in the requested universe, held or not). This is a REALIZED
    distribution credited to cash, not "yield on cash" — it does not touch, and is unaffected by,
    `INVARIANTS.cash_yield` (§3.1's own clarifying note).
    """
    holding = portfolio.holdings.get(ticker)
    if holding is None:
        return portfolio
    new_cash = portfolio.cash + div_cash_per_share * holding.quantity
    return portfolio.model_copy(update={"cash": new_cash})


def apply_allocation(
    portfolio: Portfolio, instruction: AllocationInstruction, prices: dict[str, float]
) -> Portfolio:
    """Rebalance `portfolio` to `instruction.target_weights` at `prices` (`raw_close`, §6a). For
    each ticker in `instruction.target_weights`, computes `target_value = weight *
    mark_to_market(portfolio, prices)`, converts to a target `quantity = target_value /
    prices[ticker]`, and adjusts cash by the value delta traded. A ticker currently held but
    ABSENT from `instruction.target_weights` is fully liquidated (target quantity `0.0`, removed
    from `holdings`, §3.1). Every resulting `Holding.quantity` and `Portfolio.cash` is
    non-negative BY CONSTRUCTION (§3.1, §3.2) — this function cannot itself produce a shorted or
    over-drawn `Portfolio`; a `target_weights` sum exceeding what current + newly-freed cash can
    fund is impossible by construction too, since `AllocationInstruction`'s own validator (§3.2)
    already forbids a sum above `1.0` of portfolio value, and portfolio value is computed BEFORE
    any trade in this same call.

    `cash` is floored at `0.0` immediately before the returned `Portfolio` is constructed — a
    defensive guard against sub-cent floating-point noise from `AllocationInstruction`'s own
    declared `1e-9` sum-tolerance (§3.2), not a relaxation of the non-negative-cash invariant: the
    true mathematical floor for `cash` after this function, given
    `sum(target_weights.values()) <= 1.0 + 1e-9`, is `-1e-9 * total_value`, which can exceed
    ordinary `float` rounding noise for a large-enough portfolio. Clamping only ever moves a value
    that would otherwise fail validation by a razor-thin, tolerance-induced margin back to exactly
    `0.0`; it can never mask a genuine over-allocation, which the validator already rejects at
    construction time, upstream of this call.
    """
    total_value = mark_to_market(portfolio, prices)
    cash = portfolio.cash

    for ticker, holding in portfolio.holdings.items():
        if ticker not in instruction.target_weights:
            cash += holding.quantity * prices[ticker]

    new_holdings: dict[str, Holding] = {}
    for ticker, weight in instruction.target_weights.items():
        price = prices[ticker]
        target_value = weight * total_value
        target_quantity = target_value / price
        current_holding = portfolio.holdings.get(ticker)
        current_value = current_holding.quantity * price if current_holding is not None else 0.0
        cash -= target_value - current_value
        if target_quantity > 0.0:
            new_holdings[ticker] = Holding(ticker=ticker, quantity=target_quantity)

    cash = max(cash, 0.0)
    return Portfolio(cash=cash, holdings=new_holdings)
