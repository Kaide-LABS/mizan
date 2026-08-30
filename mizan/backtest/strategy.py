"""mizan/backtest/strategy.py — the pluggable, structurally-confined strategy interface.

Implements PHASE_5_SPEC.md §3.2, §4.2, §6c.

**The precise structural argument for "cannot select a Non-compliant ticker," stated once here,
referenced everywhere else (PHASE_5_SPEC.md §4.2):** a `Strategy.select()` implementation's
signature is `(*, as_of_date, compliant_tickers: frozenset[str], portfolio: Portfolio) ->
AllocationInstruction`. Every ticker-typed value reachable inside `select()`'s own body is either a
member of `compliant_tickers` (which `mizan.backtest.clock.rebalance` populates ONLY with tickers
whose freshly-computed `Verdict` this rebalance is `PURE` or `MIXED` — never `NON_COMPLIANT`) or a
key of `portfolio.holdings` (which can only ever contain tickers a PRIOR call to
`mizan.backtest.portfolio.apply_allocation` put there, themselves sourced from a prior
`compliant_tickers` set, recursively — a ticker is force-divested, never silently retained, the
rebalance its verdict flips). There is no third source of a ticker name inside `Strategy.select()`'s
scope. This makes selecting a `NON_COMPLIANT` ticker not merely "checked and rejected" but literally
**unnameable** from inside a conforming implementation — the interface itself carries no channel
through which such a ticker could be referenced. `StrategyContractViolationError` (below) is the
assertion that fires only if a `Strategy` implementation manufactures a ticker string from OUTSIDE
that scope (e.g. a hardcoded literal) — an implementation bug the type system cannot itself prevent,
which is exactly why the backstop exists.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol

from pydantic import model_validator

from mizan.core.base import MizanBaseModel

if TYPE_CHECKING:
    from mizan.backtest.portfolio import Portfolio


class AllocationInstruction(MizanBaseModel):
    """A strategy's rebalance decision: target PORTFOLIO-VALUE WEIGHTS for a subset of the
    tickers it was given. This is the one model in Phase 5 that makes leverage and shorting
    structurally impossible BY CONSTRUCTION, independent of `INVARIANTS` — every weight is
    validated in `[0.0, 1.0]` and the weights must sum to at most `1.0`; any residual
    (`1.0 - sum(weights)`) is left as cash, which is exactly `MASTER_PRD.md` §7's `hold-cash`
    action. A strategy attempting to over-allocate (implying borrowed capital) or under-specify
    a negative weight (implying a short) cannot construct this object at all —
    `pydantic.ValidationError`, not a downstream check.
    """

    target_weights: dict[str, float]

    @model_validator(mode="after")
    def _weights_are_long_only_and_fully_funded(self) -> AllocationInstruction:
        """Every weight in `[0.0, 1.0]`; sum at most `1.0` (with a `1e-9` float tolerance)."""
        for ticker, weight in self.target_weights.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(
                    f"{ticker}: weight {weight!r} outside [0.0, 1.0] — a negative weight is a "
                    "short position, a weight above 1.0 is leverage; both are permanently forbidden"
                )
        total = sum(self.target_weights.values())
        if total > 1.0 + 1e-9:
            raise ValueError(
                f"target_weights sum to {total!r} > 1.0 — implies borrowed capital (margin), "
                "permanently forbidden (mizan.config.invariants.INVARIANTS.margin_allowed)"
            )
        return self


class Strategy(Protocol):
    """The pluggable long-only strategy interface (`MASTER_PRD.md` §7). See this module's own
    top-of-file docstring for the exact structural argument for why a conforming `Strategy` cannot
    select a `Verdict.NON_COMPLIANT` ticker even if it tried."""

    def select(
        self, *, as_of_date: date, compliant_tickers: frozenset[str], portfolio: Portfolio
    ) -> AllocationInstruction:
        """Return this rebalance's target allocation. `compliant_tickers` is the ONLY source of
        tickers this method may name in its returned `AllocationInstruction` — see this module's
        docstring."""
        ...


class StrategyContractViolationError(RuntimeError):
    """Raised by `mizan.backtest.clock.rebalance` if a `Strategy.select()` implementation returns
    an `AllocationInstruction` naming a ticker OUTSIDE the `compliant_tickers` frozenset it was
    given.

    This should be UNREACHABLE for any conforming `Strategy` — `compliant_tickers` is the only
    source of tickers a `select()` implementation is ever handed (it receives no database
    connection, no raw-cache directory path, no access to `screen()`, and no reference to the
    full requested universe — only the pre-filtered compliant subset), so it has no way to even
    NAME a `NON_COMPLIANT` ticker.
    This exception exists as the defense-in-depth backstop for a broken or adversarial `Strategy`
    implementation, exactly the same "structural design + an assertion backstop that should never
    fire" pattern
    `PHASE_1_SPEC.md` §6.1 used for `check_invariants()`'s seven hand-written checks — never routed
    around, never caught-and-continued.
    """


class EqualWeightStrategy:
    """Reference `Strategy` implementation (§3.2): `select()` returns `AllocationInstruction(
    target_weights={ticker: 1.0 / len(compliant_tickers) for ticker in compliant_tickers})` — or
    `AllocationInstruction(target_weights={})` (all cash) if `compliant_tickers` is empty. Used by
    this phase's own tests and by `mizan backtest`'s CLI; not presented as a real research strategy
    (§3.2) — building an actual research strategy is explicitly the project owner's own future work
    over this substrate, same posture Phase 4 §9 gave the real activity map.
    """

    def select(
        self, *, as_of_date: date, compliant_tickers: frozenset[str], portfolio: Portfolio
    ) -> AllocationInstruction:
        """Equal-weight every ticker in `compliant_tickers`; all cash if it is empty."""
        if not compliant_tickers:
            return AllocationInstruction(target_weights={})
        weight = 1.0 / len(compliant_tickers)
        return AllocationInstruction(target_weights=dict.fromkeys(compliant_tickers, weight))
