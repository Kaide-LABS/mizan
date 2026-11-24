# Mizan

## Crypto pivot (V1)

Mizan V1 is a research and backtesting sandbox. It locks a 14-token crypto universe, spot-only hard invariants, a pending scholarly-verification fiqh register, and a structural no-najsh order-intent model. It does not trade real money or place live orders; the equity modules remain parked and importable.

Daily OHLCV ingestion for all 14 tokens now exists with Coinbase-primary/Kraken-fallback selection, raw-cache replay, and DuckDB storage; it is not yet wired to a CLI verb (Phase 6).

Run `mizan-boot-check` to prove the invariant and fiqh boundaries hold before later pipeline phases execute.
