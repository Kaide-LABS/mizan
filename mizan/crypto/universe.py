"""The locked crypto universe; see ``docs/crypto/PHASE_1_SPEC.md`` §A3."""

from __future__ import annotations

CRYPTO_UNIVERSE: tuple[str, ...] = (
    "BTC", "LTC", "BCH", "ETH", "SOL", "ADA", "AVAX",
    "DOT", "NEAR", "ATOM", "ALGO", "XRP", "XLM", "LINK",
)
CRYPTO_UNIVERSE_SET: frozenset[str] = frozenset(CRYPTO_UNIVERSE)

assert len(CRYPTO_UNIVERSE) == 14
assert len(CRYPTO_UNIVERSE_SET) == 14
