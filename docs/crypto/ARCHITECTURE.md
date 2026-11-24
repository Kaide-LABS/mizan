# Phase 1 architecture

The single `Invariants` model is the permissibility boundary. `boot_check.check_all()` validates it and both fiqh registers before any later CLI work runs. Crypto adds `spot_only`, `synthetic_exposure_allowed`, and `lending_or_yield_allowed`; the existing fully-funded, margin, derivatives, and zero-cash-yield fields are reused.

`ResolvedOrder` is the no-najsh boundary. It is frozen and must contain a terminal fill or an explicit rejection. There is no pending, resting, open, or cancelable order representation, so an order without intent to fill is unrepresentable.

The crypto universe and fiqh register are new. The shared Pydantic base, invariant gate, caveat/result machinery, raw cache, database, backtest engine, and reporting layers are reused in later phases. Equity ingestion, AAOIFI screening, and EDGAR modules remain parked and importable.

The future signal-adapter seam is contract-only in Phase 1 and is planned for Phase 5. No HFT, live-trading, exchange-API-key, network-order, or signal-adapter implementation module exists under `mizan/`; `mizan/execution/intent.py` only defines terminal in-process value objects.

Phase 2 adds the granularity-agnostic `candles` table and a raw-cached daily OHLCV path. Each ticker is Coinbase-primary and falls back as a whole series to Kraken only when Coinbase returns no data; the two sources are never blended within one ticker. `mizan.crypto.clock.generate_market_days` treats every UTC calendar day as a valid crypto market day, unlike the equity path whose dates arise implicitly from available `price_bars` rows (see `docs/crypto/PHASE_2_SPEC.md` §B2/§B3).
