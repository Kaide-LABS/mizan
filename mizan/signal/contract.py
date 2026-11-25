"""Signal-adapter contract; see ``docs/crypto/PHASE_5_SPEC.md`` §A2-A4.

``SignalAdapter`` is a ``typing.Protocol``, not an ABC, so a future third-party adapter
satisfies this contract structurally without being forced into this repo's class hierarchy
(§A1). ``@runtime_checkable`` lets a test ``isinstance()``-check a conforming object, but per
PEP 544 that check verifies method/attribute *names* only, never signatures or return types —
a class with a wrong-shaped ``predict`` would still pass ``isinstance()``; only
``mypy --strict`` catches that mismatch (§Red-team R5).
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Protocol, runtime_checkable

from pydantic import Field

from mizan.core.base import MizanBaseModel


class SignalProvenance(MizanBaseModel):
    source: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    licence_url: str | None = None
    data_provenance: str = Field(min_length=1)


class Prediction(MizanBaseModel):
    kind: Literal["prediction"] = "prediction"
    probability: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0)


class Abstention(MizanBaseModel):
    kind: Literal["abstention"] = "abstention"
    reason: str = Field(min_length=1)


class Signal(MizanBaseModel):
    ticker: str
    as_of_date: date
    provenance: SignalProvenance
    outcome: Prediction | Abstention = Field(discriminator="kind")


@runtime_checkable
class SignalAdapter(Protocol):
    """Structural contract for a pluggable external forecasting signal.

    ``isinstance(obj, SignalAdapter)`` verifies that ``provenance`` and ``predict`` exist by
    name only — it is not a full signature/behaviour check (PEP 544).
    """

    @property
    def provenance(self) -> SignalProvenance: ...

    def predict(
        self, *, as_of_date: date, ticker: str, context: tuple[float, ...]
    ) -> Signal: ...
