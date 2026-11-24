from mizan.crypto.universe import CRYPTO_UNIVERSE, CRYPTO_UNIVERSE_SET


def test_crypto_universe_is_locked() -> None:
    assert CRYPTO_UNIVERSE == (
        "BTC", "LTC", "BCH", "ETH", "SOL", "ADA", "AVAX", "DOT",
        "NEAR", "ATOM", "ALGO", "XRP", "XLM", "LINK",
    )
    assert len(CRYPTO_UNIVERSE) == len(CRYPTO_UNIVERSE_SET) == 14
