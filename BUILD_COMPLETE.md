# Build complete — Mizan crypto pivot (V1)

This build implemented the baby PRD at `runs/42cd206f-79c0-42db-87c0-3168716066ea/baby-prd.md`:
pivoting Mizan from an equity Shariah-research/backtest sandbox to a crypto-first, spot-only,
Shariah-compliant research and backtesting sandbox — research/backtest only, no real money, no
live orders — while leaving a signal-adapter seam for a future two-speed prediction-plus-execution
system. All six planned phases are shipped, reviewed, and tested at this commit.

## Phases shipped

- **Phase 1 — Invariant & intent foundations + crypto config.** The shared `Invariants` singleton
  grew three crypto-specific locked constants (`spot_only`, `synthetic_exposure_allowed`,
  `lending_or_yield_allowed`); `mizan/execution/intent.py` enforces no-najsh structurally via a
  frozen `ResolvedOrder` whose outcome is a mandatory `FillResult`/`OrderRejection` union (no
  "pending/resting/cancelable" order type exists); the locked 14-token `CRYPTO_UNIVERSE`; the
  crypto fiqh register (stablecoins, staking, custody, memecoin exclusion), each entry labelled
  `VerificationStatus.PENDING_SCHOLARLY_VERIFICATION`; the two-speed `docs/crypto/ROADMAP.md`.
- **Phase 2 — Crypto ingestion + 24/7 clock + candles store.** Keyless Coinbase-primary /
  Kraken-fallback daily OHLCV ingestion; a granularity-agnostic DuckDB `candles` table plus raw
  cache; a 24/7 UTC market clock (`mizan/crypto/clock.py`) replacing the equity trading-day
  calendar on the crypto path.
- **Phase 3 — Token screening.** `mizan/crypto/screening.py`'s `screen_universe()` produces a
  per-token verdict with a written reason for all 23 named tokens (the 14-token universe plus the
  9-token default-reject list: AAVE/COMP/MKR for lending/riba, BNB/OKB/CRO for exchange
  margin/futures income, DOGE/SHIB/PEPE for maysir/gharar).
- **Phase 4 — Baseline backtest.** `mizan/crypto/backtest.py`'s `run_crypto_backtest` runs an
  equal-weight, long-only, periodic-rebalance buy-and-hold strategy over the screened universe on
  the 24/7 clock, labelled `"baseline"`; per-side taker fee (0.6% default) and slippage (0.05%
  default) are applied to every traded leg and are structurally forbidden from being exactly zero.
- **Phase 5 — Signal-adapter seam.** `mizan/signal/contract.py` (a `typing.Protocol`
  `SignalAdapter`, mandatory data-provenance/licence metadata, a calibrated-probability-or-
  abstention `Signal.outcome`) and `mizan/signal/validation_gate.py` (`ValidationGateSpec`,
  `GateCriteria`, `gate_passed`, `require_passing_gate`) specify the contract and the pass/fail
  validation gate (out-of-sample split, calibration, per-token/per-regime error, dual-baseline
  Diebold-Mariano beat requirement) with no adapter implementation and no call site yet.
- **Phase 6 — HTML report + single pipeline command.** `mizan/crypto/report.py` renders a
  self-contained crypto HTML report (fiqh-register citations, all 23 token verdicts with reasons,
  a loud survivorship-bias warning, and the new `Caveat.CUSTODY_FREEZE_RISK` exchange-custody
  caveat); `mizan/cli/crypto.py` registers the single `crypto-pipeline` verb that fetches, screens,
  backtests, and writes that report end-to-end in one command. Equity's four CLI verbs
  (`ingest`/`normalize`/`screen`/`backtest`/`report`) and modules remain unmodified and importable.

## Acceptance criteria — final status

All 15 acceptance criteria from the baby PRD are met:

| AC | Requirement | Where |
|----|-------------|-------|
| 1 | Single command fetches real OHLCV for all 14 tokens, Kraken fallback | `mizan crypto-pipeline` (P6) over P2 ingestion |
| 2 | Candles written to raw cache + DuckDB | P2 |
| 3 | Ingestion accepts a granularity parameter | P2, threaded through `crypto-pipeline --granularity` |
| 4 | Per-token verdict with written reason, 14 + 9-reject list | P3, rendered in full by P6's report |
| 5 | Baseline equal-weight buy-and-hold, periodic rebalance, labelled "baseline" | P4 |
| 6 | Taker fee 0.6% / slippage 0.05% defaults, overridable, never zero | P4 |
| 7 | Single HTML report: fiqh citations, verdicts, survivorship warning, custody/freeze caveat | P6 |
| 8 | Fiqh register entry labelled PENDING_SCHOLARLY_VERIFICATION | P1/P3 |
| 9 | One test per hard invariant proving it cannot be disabled | P1 (`tests/test_invariants.py`, `tests/test_hard_invariants.py`) |
| 10 | No-najsh enforced at the order/intent model level | P1 (`tests/test_execution_intent.py`) |
| 11 | Signal-adapter interface/contract (provenance, calibration, abstention) | P5 (`tests/test_signal_contract.py`) |
| 12 | Validation-gate spec (out-of-sample, calibration, per-subgroup, baseline-beating) | P5 (`tests/test_validation_gate.py`) |
| 13 | 24/7 market clock; equity calendar off the crypto default path | P2 |
| 14 | Equity V1 modules still import, not on the default (crypto) command path | P6 (`tests/test_phase1_scope.py::test_equity_cli_verbs_and_modules_still_import_after_crypto_pipeline_lands`) |
| 15 | Two-speed roadmap documented; no HFT/live/adapter code built | P1 (`docs/crypto/ROADMAP.md`), re-confirmed unchanged through P6 |

## Verification performed this turn

- Read `docs/crypto/PHASE_6_SPEC.md`, the baby PRD, and the context file; re-read the Phase 6
  diff (commits `1203bc4` and `8c6e4e2`) line-for-line against the spec's Part A and Part B code
  blocks and confirmed an exact match, including the three red-team-added acceptance criteria
  (R6: `render_crypto_report(data)` without the keyword raises `TypeError`; R7:
  `resolve_crypto_report_caveats` returns a demonstrably different tuple for
  `CustodyModel.EXCHANGE_QABD_HUKMI` vs. `CustodyModel.SELF_CUSTODY`; R8: the no-`--ticker`-flag
  guard checks the live `argparse` parser object, not only a source grep).
- Ran `mypy --strict` and `ruff check` on every Phase 6 file — clean.
- Ran `./.venv/Scripts/mizan-boot-check` — passed.
- Ran the full test suite: **563 passed**, 0 failed.
- Ran `mizan crypto-pipeline --help` directly and confirmed every flag in spec §B3 is present and
  no `--ticker`/`--tickers`/`--symbol` flag exists.
- Drove `mizan/cli/crypto.py`'s `run()` handler directly end-to-end against a freshly seeded
  on-disk DuckDB database covering all 14 `CRYPTO_UNIVERSE` tickers (with ingestion monkeypatched
  to a no-op, per the spec's own out-of-scope boundary on real-network testing): the handler
  returned 0, wrote a 38KB `<!DOCTYPE html>` report containing all four required sections
  (`fiqh-register`, `token-verdicts`, `backtest-summary`, `plots`) plus `AAVE`'s reject reason and
  the survivorship/custody caveat prose, and printed a final portfolio value of 993.54 for the
  seeded window — a genuine, observed run, not an assumption from the test suite alone.

## What remains deliberately unbuilt (by PRD design, not a gap)

- No concrete `SignalAdapter` implementation, no TimesFM/gods-eye-view/Agent-Reach/MiroFish/
  Inkling integration, and no call site for `require_passing_gate` anywhere in the backtest or
  crypto code — Phase 5's contract and gate are specification-only, exactly as the baby PRD's
  "Out of scope" section requires ("Implementing any signal adapter").
- No modelling of exchange-failure or asset-freeze risk itself — caveated via
  `Caveat.CUSTODY_FREEZE_RISK`, never simulated, per the PRD's explicit "caveated, not modelled."
- No HFT execution, live trading, or exchange API keys/authenticated endpoints anywhere in the
  repo.
- Equity V1 (EDGAR ingestion, AAOIFI ratio screen, SIC screening, and all four original CLI verbs)
  remains parked: importable, untouched, and off the crypto default path.

## Entry point

```
mizan crypto-pipeline --start-date YYYY-MM-DD --end-date YYYY-MM-DD --initial-cash FLOAT \
    --db-path PATH --cache-dir PATH --output-path PATH \
    [--interval-days INT] [--granularity STR] [--taker-fee-rate FLOAT] [--slippage-rate FLOAT]
```

Fetches real Coinbase/Kraken-fallback daily candles for the locked 14-token universe, screens the
full 23-token map, runs the baseline backtest, and writes one self-contained HTML report to
`--output-path`.
