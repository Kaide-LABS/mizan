# Crypto two-speed roadmap

Phase 1 builds the rails only. The slow layer combines gods-eye-view, Agent-Reach, MiroFish, and Inkling 2 Small to predict events and reactions, choose tokens, set long/flat-only direction, and impose size limits.

The fast layer is future spot-only HFT execution over intraday and order-book data, using TimesFM short-horizon forecasts. It may act only within the slow layer's limits and the hard invariants, including no-najsh.

Later phases cover intraday ingestion, order-book data, signal-adapter implementations, paper trading, and eventually self-custody/live operation. None of this is built in V1: this release is research/backtest-only, has no live trading, and spends no real money.
