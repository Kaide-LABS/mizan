# Mizan

## Crypto pivot (V1)

Mizan V1 is a research and backtesting sandbox. It locks a 14-token crypto universe, spot-only hard invariants, a pending scholarly-verification fiqh register, and a structural no-najsh order-intent model. It does not trade real money or place live orders; the equity modules remain parked and importable.

Daily OHLCV ingestion for all 14 tokens now exists with Coinbase-primary/Kraken-fallback selection, raw-cache replay, and DuckDB storage; it is not yet wired to a CLI verb (Phase 6).

Run `mizan-boot-check` to prove the invariant and fiqh boundaries hold before later pipeline phases execute.
The 14-token universe and nine-token default-reject list now each have a documented per-token verdict; screening is not yet wired to a CLI verb (Phase 6).
A baseline equal-weight, periodic-rebalance backtest over the compliant universe now exists, with a per-side taker-fee and slippage cost model that is never zero by default; it is not yet wired to a CLI verb (Phase 6).
A signal-adapter contract and validation-gate specification now exist (mandatory data provenance/licence, calibrated probability-with-abstention output, and a structural out-of-sample/calibration/per-token/per-regime/dual-baseline gate), with no adapter implementation and no wiring to the backtest yet.
