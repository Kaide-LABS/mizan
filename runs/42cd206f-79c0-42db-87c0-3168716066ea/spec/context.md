# Mizan — Crypto Pivot: Project Context

## What this is
Mizan is an existing, shipped equity Shariah-research/backtest sandbox (Python, `mizan/` package, 7 phases). This project pivots it to a **crypto-first, spot-only, Shariah-compliant research and backtesting sandbox** — research/backtest only, no real money, no live orders. Equity V1 is **parked** (importable, off the default path), never deleted.

## Stack and why
- **Python 3.11+** (floor set by existing deps; build machine runs 3.14.x) — reuse the shipped codebase as-is.
- **Pydantic 2.13.5** — every model inherits `mizan.core.base.MizanBaseModel` (`frozen=True`, `extra="forbid"`, `validate_default=True`). This is the mechanism that makes config typos fail loudly and locked values immutable. The no-najsh order type and the crypto fiqh register are built on it.
- **DuckDB 1.5.5** (pinned, reused) as the embedded candle/analytics store; **pyarrow 25.0.1**; **httpx 0.28.1** for keyless HTTP (Phase 2); **matplotlib 3.11.1** for report plots (Phase 6). Pins live in `pyproject.toml` and are justified in `docs/modernization_log.md`.
- **Tooling:** `mypy --strict`, `ruff` (ruleset `E,F,I,N,UP,B,A,C4,PT,SIM,TID,RUF`), `pytest`. All new code must pass strict typing and lint.

## Repo layout (relevant)
```
mizan/
  config/       invariants.py (REUSE+EXTEND), fiqh_params.py (PARK, equity), boot_check.py (EXTEND)
  core/         base.py, caveats.py (Caveat/ResultEnvelope — REUSE), verdict.py (REUSE)
  data/         raw_cache.py (REUSE), db.py (equity schema; crypto candles added P2), ingest_* (PARK equity)
  screening/    business_activity.py / financial_ratios.py / verdict.py (PARK equity; crypto screen P3)
  backtest/     clock.py, strategy.py, portfolio.py, compliance_state.py (REUSE engine; crypto clock/costs P2/P4)
  purification/ (REUSE; near-empty for crypto)
  reporting/    report.py, plots.py (REUSE; crypto report P6)
  cli/          main.py (dispatch; crypto verb/command added later)
  crypto/       NEW (P1): universe.py, fiqh_register.py
  execution/    NEW (P1): intent.py  (the no-najsh order/intent model)
tests/          flat; one test module per source module
docs/
  modernization_log.md (pinned external reality)
  crypto/       NEW (P1): PHASE_1_SPEC.md, ARCHITECTURE.md, ROADMAP.md
```

## Conventions
- One canonical singleton per locked surface (`INVARIANTS`, `FIQH_PARAMS`, and new `CRYPTO_FIQH_PARAMS`), constructed once at import with zero args; no module builds its own.
- Hard permissibility values are fixed constants with no config switch; `boot_check` hand-writes one check per value and `check_all()` runs before any CLI subcommand dispatches.
- Every result reaching a human is wrapped in `ResultEnvelope` with an explicit `active_caveats` tuple (no default).
- Honesty-surface rule: every fiqh judgment call carries a citation/`source` and `VerificationStatus.PENDING_SCHOLARLY_VERIFICATION`.
- New modules cite their governing spec section in the module docstring.

## Constraints (from PRD, immutable)
- Free, keyless, public data only (Coinbase primary, Kraken fallback); every source public/licensed (fatwa part 2).
- Research/backtest only; no real money, no live orders, no API keys.
- Seven hard invariants, each undisablable and each test-proven: spot-only/immediate settlement; fully funded, no margin/leverage; no perps/futures/options; no CFDs/synthetic exposure; no lending/yield; CASH_YIELD=0; no-najsh.
- Costs never zero by default. Survivorship bias flagged loudly. Report readable by a non-technical judge. Fiqh basis cited (islamqa.info Q504160 + Q106094/Q125758/Q310956), not contested.

## Glossary
- **Najsh** — placing orders with no genuine intent to fill (spoofing/layering); forbidden. **Qabd hukmi** — constructive possession (exchange custody accepted for V1). **Spot-only** — immediate, fully-funded exchange of asset for cash, no derivatives/leverage. **Signal adapter** — pluggable external forecast the backtest may consume (contract only in V1). **Validation gate** — pass/fail requirements a signal must meet (out-of-sample, calibration, per-token/per-regime error, beat TimesFM/naive baseline) before driving allocations.

## Research digest (one paragraph; informs choices, not requirements)
Research indicates the keyless public **Coinbase Exchange API** daily-candle endpoint (`/products/{id}/candles`, `granularity=86400`, ≤300 rows/call, 10 req/s public limit) is the simplest primary source, with the **Kraken public OHLC** endpoint (`interval=1440`, hard ~720-candle recency cap, GET-only since 2024, drop the last still-open candle) as the documented fallback for tokens/history Coinbase lacks — both inform Phase 2, not Phase 1. A single granularity-agnostic DuckDB `candles` table keyed by `(exchange, symbol, granularity, ts)` lets daily now and intraday later share one path. Equal-weight periodic-rebalance backtests apply per-leg taker fee + slippage on every buy and sell over a continuous 24/7 UTC clock; Coinbase's lowest-tier 0.60% taker matches the PRD default. The signal-adapter contract is best expressed as a `typing.Protocol` with mandatory provenance/licence metadata, calibrated-probability + abstain output, and a validation gate using proper scoring rules (CRPS/pinball), calibration curves (not Brier alone), per-slice breakdowns, and a Diebold-Mariano significance test against a last-value naive baseline and zero-shot **TimesFM 2.5** (Apache-2.0) — foundation models rarely beat random-walk on returns, so the bar is genuine. For no-najsh, the typestate / "make illegal states unrepresentable" pattern (frozen value object, private/smart constructor requiring a resolved fill or explicit rejection, no cancelable resting state) mirrors how backtest engines (QuantConnect) assume complete fills and matches the CFTC's intent-to-fill test for spoofing.

## Phase plan (what each phase delivers → acceptance criteria)
- **P1 — Invariant & intent foundations + crypto config (this spec):** extend the hard-invariant surface for crypto; the no-najsh order/intent model; the 14-token universe constant; the crypto fiqh register (stablecoins/staking/custody/memecoin, PENDING_SCHOLARLY_VERIFICATION); the two-speed roadmap docs. → **AC 8, 9, 10, 15 (doc)**.
- **P2 — Crypto ingestion + 24/7 clock + candles store:** keyless Coinbase-primary / Kraken-fallback daily OHLCV; granularity-agnostic DuckDB `candles` table + raw cache; 24/7 UTC market clock; move equity calendar off the default path. → **AC 1 (fetch), 2, 3, 13**.
- **P3 — Token screening:** per-token business-activity verdict map with written reasons over the 14 tokens; default-reject list (AAVE/COMP/MKR, BNB/OKB/CRO, DOGE/SHIB/PEPE) each with its stated reason. → **AC 4**.
- **P4 — Baseline backtest:** equal-weight long-only buy-and-hold with periodic rebalance over the 24/7 clock, labelled "baseline"; per-side taker fee 0.6% + slippage 0.05% defaults, both config-overridable, never zero. → **AC 5, 6**.
- **P5 — Signal-adapter seam:** `typing.Protocol` interface + contract (provenance/licence, calibrated probability/uncertainty, abstention) + written validation-gate spec; no implementations. → **AC 11, 12**.
- **P6 — HTML report + single pipeline command:** one self-contained HTML report (fiqh citations, per-token verdicts with reasons, loud survivorship warning, custody/freeze caveat); one command fetch→screen→backtest→report end-to-end; confirm equity parked. → **AC 1 (end-to-end), 7, 14**.

## Planned architecture
The design keeps Mizan's shipped strength — **one locked permissibility boundary gated at boot before anything runs** — and makes it carry the crypto invariants too. Rather than inventing a parallel crypto invariants object, Phase 1 extends the single `Invariants` singleton with the three crypto-specific locked constants (`spot_only`, `synthetic_exposure_allowed`, `lending_or_yield_allowed`) and adds matching hand-written checks to `boot_check`, exactly the extension the module's own docstring sanctions. The remaining four PRD invariants already map onto existing fields (`cash_yield`, `fully_funded`+`margin_allowed`, `derivatives_allowed`). This means every CLI entrypoint (equity-parked or crypto) continues to run one `check_all()` that now also enforces the crypto boundary — a reviewer gets one place to audit, not two drifting copies.

No-najsh is enforced **structurally, at the type level**, not by a flag or a runtime surveillance heuristic. `mizan/execution/intent.py` defines a frozen `ResolvedOrder` whose `outcome` is a mandatory discriminated union of exactly one terminal state — a `FillResult` (strictly positive quantity and price) or a reasoned `OrderRejection`. There is no "pending/resting/open/cancelable" order type and no `cancel()` method anywhere, so an order placed without intent to fill is literally unrepresentable; the future HFT layer inherits the same type and cannot introduce spoofing without adding a new, review-visible type. The crypto fiqh register reuses the shipped `FiqhParam[T]`/`VerificationStatus` honesty machinery so the judge-facing register and the boot-time honesty check behave identically to equity.

The pivot is additive: equity modules stay importable and parked; new crypto work lands under `mizan/crypto/` and `mizan/execution/`; the shipped backtest engine, `ResultEnvelope`/`Caveat`, raw cache, DuckDB store and HTML reporter are reused by later phases rather than reimplemented. The main architectural risk a reviewer should probe is the decision to grow the shared `Invariants` singleton (field-count change + one updated equity test) instead of a separate crypto invariants model — chosen deliberately so there is exactly one boot-gated permissibility surface, which is the property the whole honesty design depends on.

## Architecture decision

An independent reviewer proposed: Artifact-Gated Pipeline.

**Chosen:** the planned architecture

**Why:** The locked PRD scopes a narrow V1 whose single acceptance gate is "one command runs fetch→screen→backtest→report," and which mandates reusing the shipped in-process modules as-is — the Artifact-Gated Pipeline's value (replayable stages, versioned manifests, cross-process provenance) is bought with orchestration, serialization, and DuckDB-locking code that no acceptance criterion requires and that the "reuse as-is / additive pivot" constraint actively discourages. Its one genuinely relevant benefit, grant-facing provenance, is already met far more cheaply by the self-contained HTML report with fiqh citations and caveats. Critically, it trades *against* the design's load-bearing property: the no-najsh guarantee and the invariant lock are strongest as unforgeable in-process types gated once at boot, and pushing them across serialized subprocess boundaries would weaken exactly the structural impossibility AC 9/10 demand (the reviewer concedes this preservation is "careful" work). For Phase 1 specifically — invariants, the `ResolvedOrder` type, the universe constant, and the fiqh register — the alternative changes nothing and adds pure overhead, since its boundaries only appear in Phases 2–6. The planned single boot-gated permissibility surface remains the better fit.
