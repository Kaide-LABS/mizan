"""Terminal order intent models; see ``docs/crypto/PHASE_1_SPEC.md`` §A2.

Because an order can only be held with a terminal fill or explicit rejection, and
no resting or cancelable state exists, an order placed without intent to fill has
no representation for the current backtest or any future HFT layer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from mizan.core.base import MizanBaseModel


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class RejectionReason(StrEnum):
    SCREEN_REJECTED = "screen_rejected"
    NOT_IN_UNIVERSE = "not_in_universe"
    INSUFFICIENT_CASH = "insufficient_cash"
    NO_LIQUIDITY = "no_liquidity"


class FillResult(MizanBaseModel):
    kind: Literal["fill"] = "fill"
    filled_quantity: float = Field(gt=0.0)
    fill_price: float = Field(gt=0.0)


class OrderRejection(MizanBaseModel):
    kind: Literal["rejection"] = "rejection"
    reason: RejectionReason
    detail: str = Field(min_length=1)


class ResolvedOrder(MizanBaseModel):
    side: OrderSide
    ticker: str
    requested_quantity: float = Field(gt=0.0)
    outcome: FillResult | OrderRejection = Field(discriminator="kind")


class NoIntentToFillError(RuntimeError):
    """Raised when an order lacks exactly one terminal outcome."""


def place_order(
    *,
    side: OrderSide,
    ticker: str,
    requested_quantity: float,
    fill: FillResult | None = None,
    rejection: OrderRejection | None = None,
) -> ResolvedOrder:
    """Construct an order only when it has exactly one terminal outcome."""
    if (fill is None) == (rejection is None):
        raise NoIntentToFillError("exactly one of fill or rejection must be provided")
    if fill is not None:
        outcome: FillResult | OrderRejection = fill
    else:
        assert rejection is not None
        outcome = rejection
    if isinstance(outcome, FillResult) and outcome.filled_quantity > requested_quantity:
        raise NoIntentToFillError(
            f"fill quantity {outcome.filled_quantity} exceeds requested quantity "
            f"{requested_quantity}"
        )
    return ResolvedOrder(
        side=side,
        ticker=ticker,
        requested_quantity=requested_quantity,
        outcome=outcome,
    )
