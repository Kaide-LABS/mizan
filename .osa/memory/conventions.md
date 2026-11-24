# Conventions

Stack, tools and conventions this project uses. One fact per line.

- Technologies/libraries this project documents and relies on: Coinbase (Advanced Trade / Exchange public market data API), Kraken (public REST market data API), DuckDB, TimesFM, Inkling 2 Small (Thinking Machines), gods-eye-view, Agent-Reach, MiroFish _(run 42cd206f, 2026-11-24)_
- Constraint: Existing repo: must reuse the named modules as-is and preserve equity code (parked, importable). _(run 42cd206f, 2026-11-24)_
- Constraint: Data must be free, keyless, and public (no API keys); Coinbase primary, Kraken fallback. _(run 42cd206f, 2026-11-24)_
- Constraint: Every data source must be public or licensed for this use (fatwa part 2: no leaked paid signals/data). _(run 42cd206f, 2026-11-24)_
- Constraint: Research/backtest only: no real money, no live order placement. _(run 42cd206f, 2026-11-24)_
- Constraint: Hard invariants have no config switch and must each be test-proven undisablable. _(run 42cd206f, 2026-11-24)_
