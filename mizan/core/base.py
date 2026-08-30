"""Shared Pydantic base model for every Mizan model.

Implements PHASE_1_SPEC.md §3.1.
"""

from pydantic import BaseModel, ConfigDict


class MizanBaseModel(BaseModel):
    """Shared base for every Mizan Pydantic model.

    Three non-default settings, each load-bearing:

    * ``extra="forbid"`` — Pydantic's default is ``"ignore"``, which silently discards unknown
      keys. Forbidding is the mechanism that makes ``invariants.py`` and ``fiqh_params.py`` fail
      loudly on a typo or a drifted key rather than quietly ignoring it.
      (ULTIMATE_PRD.md §3.4; https://pydantic.dev/docs/validation/latest/api/pydantic/config/)
    * ``frozen=True`` — loaded config must not be mutated in place by any downstream module. A
      later phase needing a modified copy constructs one with ``model_copy(update=...)``; it must
      never flip ``frozen`` off on this shared base.
    * ``validate_default=True`` — in this project, defaults are where every fiqh value actually
      lives. An unvalidated default is an unchecked value.

    No other module in ``mizan/`` may subclass ``pydantic.BaseModel`` directly. Every model
    inherits ``MizanBaseModel`` (PHASE_1_SPEC.md §7 guard G8).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
