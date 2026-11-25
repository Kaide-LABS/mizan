"""Honesty caveats and the result-envelope contract.

Implements PHASE_1_SPEC.md §3.5.
"""

from enum import StrEnum

from mizan.core.base import MizanBaseModel


class Caveat(StrEnum):
    """Honesty caveats that must be stamped on every result that reaches a human.

    LOOK_AHEAD_BIAS
        The V1 Fork-1 simplification: ``screen(ticker, as_of_date)`` uses the most-recent-available
        filing rather than true filing-lag-corrected point-in-time data. Stated precisely
        (ULTIMATE_PRD.md §3.3, after arXiv:2607.04958): this is a SINGLE DECLARED VIOLATION OF
        TEMPORAL NON-INTERFERENCE, CONFINED TO ONE FUNCTION BODY. The V2 work item is therefore a
        checkable property - "restore temporal non-interference in screen()" - not a vague "fix the
        look-ahead thing". Observed magnitude: EDGAR facts routinely carry a >2-year gap between
        the reporting period's ``end`` date and its filing date (ULTIMATE_PRD.md §3.3).

    SURVIVORSHIP_BIAS
        The universe is "companies that exist today", which silently excludes anything delisted or
        gone to zero. Accepted and loudly flagged for V1; V2 freezes a historical as-of snapshot.

    PENDING_SCHOLARLY_VERIFICATION
        At least one fiqh judgment call in the run's configuration is unratified. Given
        ``FiqhParams``' Phase 1 shape, this is true of every run: all 11 register entries carry
        ``VerificationStatus.PENDING_SCHOLARLY_VERIFICATION``.

    CUSTODY_FREEZE_RISK
        Exchange custody is accepted as qabd hukmi (constructive possession) for crypto V1
        (``CryptoFiqhParams.custody_model``, register #3). FTX-type exchange failure and
        asset-freeze risk are NOT modelled anywhere in this backtest; self-custody is the
        long-term target. Applies whenever a run's ``CryptoFiqhParams.custody_model`` is
        ``EXCHANGE_QABD_HUKMI``.
    """

    LOOK_AHEAD_BIAS = "look_ahead_bias"
    SURVIVORSHIP_BIAS = "survivorship_bias"
    PENDING_SCHOLARLY_VERIFICATION = "pending_scholarly_verification"
    CUSTODY_FREEZE_RISK = "custody_freeze_risk"


class ResultEnvelope(MizanBaseModel):
    """Every backtest/screening result that reaches a human MUST be wrapped in this envelope.

    ``active_caveats`` has NO default. Omitting it at construction raises ``ValidationError``; it
    is not silently an empty tuple. An empty tuple ``()`` is a valid, explicit choice a caller can
    make; an *omitted* argument is not. This is the Phase 1 mechanism that makes
    ULTIMATE_PRD.md §2.2's "no code path renders a number without its caveat set" a type-level fact
    from Phase 7 onward.

    NOTE: this model inherits ``frozen=True``, so Pydantic generates ``__hash__()``, but
    ``payload`` is a dict and therefore unhashable - ``hash(envelope)`` raises ``TypeError``. Do
    not place a ``ResultEnvelope`` in a set or use it as a dict key, in this or any later phase.
    """

    active_caveats: tuple[Caveat, ...]
    payload: dict[str, object]
