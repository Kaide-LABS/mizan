"""Tests for ``mizan/signal/contract.py``; see ``docs/crypto/PHASE_5_SPEC.md`` §A5.

``isinstance(obj, SignalAdapter)`` verifies method/attribute *names* only (PEP 544) — it is
not a full signature/behaviour check; only ``mypy --strict`` catches a wrong-shaped ``predict``.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from mizan.signal.contract import (
    Abstention,
    Prediction,
    Signal,
    SignalAdapter,
    SignalProvenance,
)


def _provenance() -> SignalProvenance:
    return SignalProvenance(
        source="test-source",
        licence="Apache-2.0",
        data_provenance="synthetic test fixture",
    )


def test_signal_provenance_all_fields_succeeds() -> None:
    _provenance()


@pytest.mark.parametrize("missing", ["source", "licence", "data_provenance"])
def test_signal_provenance_missing_required_field_raises(missing: str) -> None:
    kwargs = {
        "source": "test-source",
        "licence": "Apache-2.0",
        "data_provenance": "synthetic test fixture",
    }
    del kwargs[missing]
    with pytest.raises(ValidationError):
        SignalProvenance(**kwargs)


@pytest.mark.parametrize("empty", ["source", "licence", "data_provenance"])
def test_signal_provenance_empty_required_field_raises(empty: str) -> None:
    kwargs = {
        "source": "test-source",
        "licence": "Apache-2.0",
        "data_provenance": "synthetic test fixture",
    }
    kwargs[empty] = ""
    with pytest.raises(ValidationError):
        SignalProvenance(**kwargs)


def test_prediction_boundary_zero_and_one_succeed() -> None:
    Prediction(probability=0.0, uncertainty=0.0)
    Prediction(probability=1.0, uncertainty=0.0)


def test_prediction_probability_below_zero_raises() -> None:
    with pytest.raises(ValidationError):
        Prediction(probability=-1e-9, uncertainty=0.0)


def test_prediction_probability_above_one_raises() -> None:
    with pytest.raises(ValidationError):
        Prediction(probability=1.0 + 1e-9, uncertainty=0.0)


def test_prediction_negative_uncertainty_raises() -> None:
    with pytest.raises(ValidationError):
        Prediction(probability=0.5, uncertainty=-0.01)


def test_abstention_empty_reason_raises() -> None:
    with pytest.raises(ValidationError):
        Abstention(reason="")


def test_abstention_nonempty_reason_succeeds() -> None:
    Abstention(reason="no edge detected")


def test_signal_round_trips_prediction_outcome() -> None:
    signal = Signal(
        ticker="BTC",
        as_of_date=date(2026, 1, 1),
        provenance=_provenance(),
        outcome=Prediction(probability=0.6, uncertainty=0.1),
    )
    assert signal.outcome.kind == "prediction"


def test_signal_round_trips_abstention_outcome() -> None:
    signal = Signal(
        ticker="BTC",
        as_of_date=date(2026, 1, 1),
        provenance=_provenance(),
        outcome=Abstention(reason="no edge detected"),
    )
    assert signal.outcome.kind == "abstention"


def test_conforming_object_satisfies_signal_adapter_protocol() -> None:
    class ConformingAdapter:
        @property
        def provenance(self) -> SignalProvenance:
            return _provenance()

        def predict(
            self, *, as_of_date: date, ticker: str, context: tuple[float, ...]
        ) -> Signal:
            return Signal(
                ticker=ticker,
                as_of_date=as_of_date,
                provenance=self.provenance,
                outcome=Abstention(reason="stub"),
            )

    assert isinstance(ConformingAdapter(), SignalAdapter)


def test_object_missing_predict_does_not_satisfy_signal_adapter_protocol() -> None:
    class ProvenanceOnly:
        @property
        def provenance(self) -> SignalProvenance:
            return _provenance()

    assert not isinstance(ProvenanceOnly(), SignalAdapter)
