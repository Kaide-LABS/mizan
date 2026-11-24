import pytest
from pydantic import ValidationError

from mizan.execution.intent import (
    FillResult,
    NoIntentToFillError,
    OrderRejection,
    OrderSide,
    RejectionReason,
    ResolvedOrder,
    place_order,
)


def test_place_order_with_fill_is_resolved() -> None:
    order = place_order(
        side=OrderSide.BUY, ticker="BTC", requested_quantity=1.0,
        fill=FillResult(filled_quantity=1.0, fill_price=100.0),
    )
    assert isinstance(order, ResolvedOrder)
    assert order.outcome.kind == "fill"


def test_place_order_with_rejection_is_resolved() -> None:
    order = place_order(
        side=OrderSide.SELL, ticker="BTC", requested_quantity=1.0,
        rejection=OrderRejection(reason=RejectionReason.NO_LIQUIDITY, detail="x"),
    )
    assert order.outcome.kind == "rejection"


def test_order_without_intent_to_fill_is_rejected() -> None:
    with pytest.raises(NoIntentToFillError, match="exactly one"):
        place_order(side=OrderSide.BUY, ticker="BTC", requested_quantity=1.0)


def test_order_cannot_be_both_filled_and_rejected() -> None:
    fill = FillResult(filled_quantity=1.0, fill_price=100.0)
    rejection = OrderRejection(reason=RejectionReason.NO_LIQUIDITY, detail="x")
    with pytest.raises(NoIntentToFillError, match="exactly one"):
        place_order(
            side=OrderSide.BUY,
            ticker="BTC",
            requested_quantity=1.0,
            fill=fill,
            rejection=rejection,
        )


def test_resolved_order_requires_an_outcome() -> None:
    with pytest.raises(ValidationError):
        ResolvedOrder(  # type: ignore[call-arg]
            side=OrderSide.BUY, ticker="BTC", requested_quantity=1.0
        )


def test_zero_or_negative_fill_is_not_intent_to_fill() -> None:
    with pytest.raises(ValidationError):
        FillResult(filled_quantity=0.0, fill_price=100.0)
    with pytest.raises(ValidationError):
        FillResult(filled_quantity=1.0, fill_price=0.0)


def test_no_cancelable_or_resting_order_type_exists() -> None:
    assert not hasattr(ResolvedOrder, "cancel")
    assert not {"status", "pending", "open", "resting"} & set(ResolvedOrder.model_fields)
    with pytest.raises(ValidationError):
        ResolvedOrder(
            side=OrderSide.BUY,
            ticker="BTC",
            requested_quantity=1.0,
            outcome=FillResult(filled_quantity=1.0, fill_price=100.0),
        ).side = OrderSide.SELL


def test_rejection_requires_a_reason_detail() -> None:
    with pytest.raises(ValidationError):
        OrderRejection(reason=RejectionReason.NO_LIQUIDITY, detail="")
