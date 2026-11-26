# Mizan

Halal, spot-only research and backtest sandbox for ethical investing. Islamic finance rules are enforced in code rather than promised, every asset is screened with a written reason, backtests always include real costs, and an AI signal has to pass a validation gate before it can drive a single allocation.

Crypto is the first asset class. The rules, the screen and the gate are meant to carry over to other capital assets.

**Read the manifesto:** https://kaide-labs.github.io/mizan/

Mizan is research and backtesting only. It places no live orders and spends no real money.

## Why

Institutions have the information, the speed and the protection that ordinary people lack. Mizan is an attempt to put that kind of tooling in the open, with the ethics built in and the claims checkable. Islamic finance is the first rule set because it is precise enough to turn into tests. The principle underneath it is not specific to one faith.

## What it does

- **Locked rules.** Spot only. No leverage, no margin, no interest, no futures or options, no synthetic exposure. These are constants in `mizan/config/invariants.py`, checked at startup, and the tests prove each one cannot be switched off.
- **No fake orders.** An order resolves to a fill or a rejection. There is no pending, resting or cancelable order type (`mizan/execution/intent.py`).
- **Token screening.** A fixed 14-token universe plus a default-reject list (lending, exchange-margin and speculative tokens). Every verdict carries a written reason and a citation. The fiqh register cites islamqa.info Q504160, and every entry is marked `PENDING_SCHOLARLY_VERIFICATION` until a scholar has reviewed it.
- **Data ingestion.** Public Coinbase candles, with Kraken as the fallback. No API keys. Raw responses are cached on disk and candles are stored in DuckDB, on a 24/7 UTC clock.
- **Fee-aware backtest.** Equal-weight, long-only, periodically rebalanced baseline. Fees and slippage apply to every trade and can never be zero.
- **Signal seam.** `mizan/signal/` defines the contract a signal adapter must meet (provenance and licence, and either a calibrated probability or an explicit abstention) and the gate it must pass before use. See [docs/crypto/VALIDATION_GATE.md](docs/crypto/VALIDATION_GATE.md).
- **One command, one report.** `mizan crypto-pipeline` fetches, screens, backtests and writes a self-contained HTML report, including a survivorship-bias warning and an exchange-custody caveat.

## Run it

Requires Python 3.11 or newer.

```
python -m venv .venv
.venv/Scripts/activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e . pytest mypy ruff

mizan-boot-check                # proves the invariants and fiqh boundaries hold

mizan crypto-pipeline \
  --start-date 2024-01-01 --end-date 2024-12-31 \
  --initial-cash 10000 \
  --db-path data/mizan.duckdb --cache-dir data/cache \
  --output-path report.html
```

Optional flags: `--interval-days` (rebalance interval, default 30), `--granularity` (default `1d`), `--taker-fee-rate` (default 0.006), `--slippage-rate` (default 0.0005).

Checks:

```
pytest
mypy --strict mizan
ruff check .
```

## What is not built

- The validation gate is a typed specification and a prose spec. Its measurements (out-of-sample testing, calibration, per-token and per-regime error, significance tests against baselines) are not implemented yet, and no signal adapter exists.
- The two-speed design (a slow layer that reads world events and a fast layer that trades on short-horizon forecasts) is documented in [docs/crypto/ROADMAP.md](docs/crypto/ROADMAP.md), not built.
- The pipeline has been tested end to end against simulated prices and mocked exchange responses. Results on real market data are still to come.
- The fiqh register has not been reviewed by a scholar.

## Layout

```
mizan/config/      locked invariants, fiqh parameters, boot check
mizan/execution/   order intent model (fill or rejection only)
mizan/crypto/      universe, register, screening, ingestion, backtest, report
mizan/signal/      signal-adapter contract and validation-gate spec
mizan/data/        DuckDB storage and raw cache
docs/crypto/       architecture, roadmap, validation-gate spec, phase specs
tests/
```

The earlier equity-era modules (`mizan/screening/`, `mizan/purification/`, `mizan/backtest/` and others) are kept, importable, and off the default path.

## Built with

Planned, specified, built and reviewed with [OSA](https://github.com/Kaide-LABS/osa), an open-source tool by the same author.
