# Baby PRD -- Pivoting an equity Shariah-research/backtest sandbox to a crypto-first, spot-only halal research and backtesting rig with a future-proof signal-adapter seam

## TL;DR
- Mizan is being switched from a stock-market research tool to a crypto one, following strict Islamic finance rules, for research and backtesting only -- no real money is ever spent or traded.
- It will pull free daily price history for 14 named coins, screen each coin against written religious-compliance reasons, and run a simple equal-weight buy-and-hold test with realistic trading fees.
- It produces one HTML report, readable by a non-technical grant judge, showing the compliance citations, per-coin verdicts, warnings about survivorship and exchange-custody risk, and the backtest result.
- Built-in 'hard rules' (spot only, no leverage, no gambling-style fake orders, zero cash yield) are locked on and backed by tests proving they cannot be switched off.
- You will know it works when one command does the whole run end-to-end, the report appears with all required sections, and the test suite passes -- including the locked-rule and no-fake-order tests.

## Scope
narrow

## Baby PRD

### Problem
Mizan's completed equity (stock) research sandbox must be repurposed into a crypto-first, spot-only, Shariah-compliant research and backtesting sandbox. It needs to prove that a halal crypto universe can be screened and backtested under strict fiqh invariants, while leaving clean extension points (a signal-adapter seam) for a future two-speed prediction-plus-execution system, all without touching real money or live markets.

### Users / who it's for
The repo owner / researcher building the halal crypto system, and -- via the HTML report as demo artefact -- a non-technical grant-application judge who must be able to read and understand the compliance reasoning and results.

### In scope
- Keep equity V1 modules importable but off the default path (parked, not deleted).
- Reuse as-is: invariants module, Caveat/ResultEnvelope, raw cache, DuckDB store, backtest engine, flip->grace->divest state machine, HTML reporting.
- Rebuild: ingestion, screening, market clock, purification (near-empty in V1: no dividends, staking off).
- Park: EDGAR ingestion, AAOIFI ratio screen, SIC screening.
- Fetch free, keyless, public OHLCV daily candles with Coinbase primary and Kraken fallback for tokens/history Coinbase lacks, pulling maximum free history into the raw cache + DuckDB.
- Make ingestion granularity-agnostic (daily now, intraday later).
- Replace the trading-day calendar with a 24/7 market clock.
- Universe of exactly 14 tokens: BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK.
- Per-token business-activity verdict map with written reasons replacing the AAOIFI ratio screen, with default documented rejections and their reasons: AAVE/COMP/MKR (lending/riba), BNB/OKB/CRO (exchange tokens earning from margin/futures), DOGE/SHIB/PEPE (maysir/gharar, parameter).
- Enforce hard invariants with no config switch and a test per invariant proving it cannot be disabled: spot only with immediate settlement; fully funded, no margin/leverage; no perps/futures/options; no CFDs or synthetic price exposure; no lending or yield products; CASH_YIELD = 0; NO NAJSH (no spoofing/layering/order without intent to fill, enforced at the order/intent model level).
- Configurable fiqh-register parameters with citation/rationale: stablecoins allowed (USDC as cash leg, yield 0, Coinbase 'USDC rewards' never modelled); staking rewards OFF by default; exchange custody accepted as qabd hukmi for V1 with report caveat about FTX-type failure and freeze risk unmodelled and self-custody as long-term target; memecoin exclusion parameter defaulting to excluded.
- Keep the fiqh register entry labelled PENDING_SCHOLARLY_VERIFICATION per Mizan's standing rule.
- Baseline strategy: equal-weight long-only buy-and-hold over the screened universe with periodic rebalance, explicitly labelled a baseline until validated signals exist.
- Costs: configurable taker fee defaulting to 0.6% per side and configurable slippage defaulting to 0.05%, never zero by default.
- Flag survivorship bias loudly in every report.
- Signal-adapter seam: interface + contract ONLY (no implementations) for a pluggable 'external signal' that the backtest consumes.
- Contract requirements: every adapter declares data provenance/licence; every signal carries calibrated probability/uncertainty and may abstain; a validation gate (out-of-sample vs realised price, calibration, per-token and per-regime error reporting, and must beat the TimesFM/naive baseline) must pass before a signal can drive allocations.
- Document the two-speed ROADMAP (slow layer: gods-eye-view + Agent-Reach + MiroFish + Inkling 2 Small; fast layer: spot-only HFT execution with TimesFM) in the plan/architecture without building it.
- Emit a single HTML report with fiqh-register citations, token verdicts with reasons, survivorship warning, and custody/freeze caveats, readable by a non-technical judge.
- Provide a single command that runs the full pipeline: fetch candles for the 14 tokens, apply screen + invariants, run the baseline backtest with fees/slippage, and emit the report.

### Out of scope
- HFT execution.
- Live trading and real-money order placement.
- Exchange API keys / authenticated endpoints.
- Implementing any signal adapter (gods-eye-view, Agent-Reach, MiroFish, TimesFM, Inkling 2 Small).
- Modelling any yield, staking, lending, or USDC rewards.
- Modelling exchange-failure or asset-freeze risk (caveated, not modelled).
- Deleting equity modules or their parked EDGAR/AAOIFI/SIC code.
- Contesting or re-deriving the fiqh basis (cited, not contested).

### Acceptance criteria
1. Running the single documented command completes end-to-end and fetches real OHLCV daily candles for all 14 named tokens, using Kraken for any token/history Coinbase lacks.
2. The run writes the fetched candles into both the raw cache and the DuckDB store.
3. The ingestion layer accepts a granularity parameter and can be invoked for a non-daily granularity without code changes (interface present even though only daily data is fetched now).
4. The screening step produces a per-token verdict with a written reason for every one of the 14 tokens, and the default-reject list (AAVE, COMP, MKR, BNB, OKB, CRO, DOGE, SHIB, PEPE) each carries its stated reason.
5. The baseline backtest runs equal-weight long-only buy-and-hold with periodic rebalance and is labelled 'baseline' in output.
6. The backtest applies a taker fee of 0.6% per side and 0.05% slippage by default, and both are overridable via config; a test confirms neither defaults to zero.
7. A single HTML report file is produced containing: fiqh-register citations, per-token verdicts with reasons, a loud survivorship-bias warning, and the exchange-custody/freeze-risk caveat.
8. The fiqh register entry is labelled PENDING_SCHOLARLY_VERIFICATION.
9. There is one test per hard invariant (spot-only/immediate settlement, no margin/leverage, no perps/futures/options, no CFDs/synthetic exposure, no lending/yield, CASH_YIELD=0, no-najsh) that asserts the invariant cannot be disabled via config or flag, and all pass.
10. The no-najsh invariant is enforced at the order/intent model level, verified by a test that rejects an order created without intent to fill.
11. A signal-adapter interface/contract exists (type/abstract definition, no implementation) requiring each adapter to declare data provenance/licence, emit a calibrated probability/uncertainty, support abstention, and pass a validation gate before driving allocations.
12. The validation-gate specification requires out-of-sample comparison against realised price, calibration, per-token and per-regime error reporting, and beating the TimesFM/naive baseline.
13. The market clock operates 24/7 (no trading-day/holiday gaps) and the equity trading-day calendar is no longer on the default path.
14. Equity V1 modules still import successfully but are not invoked by the default command path.
15. The two-speed roadmap (slow layer, fast layer, later phases) is documented in the plan/architecture files and no HFT/live/adapter code is built.

### Constraints
- Existing repo: must reuse the named modules as-is and preserve equity code (parked, importable).
- Data must be free, keyless, and public (no API keys); Coinbase primary, Kraken fallback.
- Every data source must be public or licensed for this use (fatwa part 2: no leaked paid signals/data).
- Research/backtest only: no real money, no live order placement.
- Hard invariants have no config switch and must each be test-proven undisablable.
- Costs never zero by default.
- The HTML report must be understandable by a non-technical grant judge.
- Fiqh basis is fixed and cited (islamqa.info Q504160 plus Q106094, Q125758, Q310956), not to be contested.

### Research plan
- Topic: Pivoting an equity Shariah-research/backtest sandbox to a crypto-first, spot-only halal research and backtesting rig with a future-proof signal-adapter seam
- Time range: last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters]
- Items:
  1. coinbase-public-candles | Coinbase public OHLCV candle retrieval | Which free, keyless Coinbase endpoint returns daily OHLCV candles for these tokens, what are its granularity options, rate limits, pagination and maximum available history? | modules: general-web, stackoverflow
  2. kraken-public-candles | Kraken public OHLCV fallback | Which free, keyless Kraken endpoint returns daily OHLCV, how do its pair symbols map to the 14 tokens, and how far back does free history go for tokens Coinbase lacks? | modules: general-web, stackoverflow
  3. duckdb-granularity-agnostic-store | Granularity-agnostic candle storage in DuckDB | How to schema and ingest OHLCV in DuckDB so the same path serves daily now and intraday/order-book later without migration? | modules: general-web, github-debug
  4. equal-weight-rebalance-backtest | Equal-weight buy-and-hold with periodic rebalance and realistic costs | Standard conventions for periodic-rebalance equal-weight long-only backtests and correct application of per-side taker fees plus slippage over a 24/7 market clock? | modules: general-web, stackoverflow
  5. signal-adapter-contract-design | Pluggable forecasting-signal interface with provenance, calibration and abstention | How to design a plugin/adapter contract that mandates licence/provenance metadata, calibrated probabilistic output, abstention, and a pass/fail validation gate before a signal can drive allocations? | modules: general-web, github-debug
  6. forecast-validation-gate | Out-of-sample calibration, per-subgroup error and baseline-beating validation | What calibration metrics, proper scoring rules, regime/subgroup breakdowns and out-of-sample comparisons are required to show a signal beats a naive/TimesFM baseline rather than just fitting aggregate data? | modules: academic-papers, general-web
  7. timesfm-baseline | TimesFM as zero-shot numeric baseline | What interface, input format and forecast outputs does TimesFM provide so it can be specified (not implemented) as the baseline every signal must beat? | modules: general-web, github-debug, academic-papers
  8. no-najsh-order-intent-model | Enforcing no-najsh at the order/intent model level | How to model an order/intent type whose construction mandates genuine intent-to-fill so spoofing/layering is structurally impossible for the current and future HFT layers to introduce? | modules: general-web
- Official docs to read:
  - Coinbase (Advanced Trade / Exchange public market data API)
  - Kraken (public REST market data API)
  - DuckDB
  - TimesFM
  - Inkling 2 Small (Thinking Machines)
  - gods-eye-view
  - Agent-Reach
  - MiroFish
- Academic searches:
  - Kutzner 2026 calibration forecasting evaluation
  - Chidichimo 2026 out-of-sample forecast validation subgroup error
  - Krastev 2025 prompt-framing fragility LLM forecasting
  - proper scoring rules calibrated probabilistic forecasting abstention
  - financial time-series forecast evaluation beating naive baseline regime
- Prior-art searches:
  - crypto OHLCV backtest equal-weight buy-and-hold python duckdb
  - halal shariah crypto screening token business activity
  - pluggable signal adapter backtest interface calibration abstention
  - spot-only no-leverage order intent model anti-spoofing

## Assumptions
- [risky] 'Periodic rebalance' for the baseline defaults to monthly, exposed as a config parameter.
- [risky] Equal weighting is computed over only the tokens that pass the screen (rejected tokens excluded from the portfolio), not all 14.
- [risky] 'Maximum free history' means fetching from the earliest date each public endpoint offers per token, with no fixed start date imposed.
- [risky] Backtest accounting is in USD with USDC treated as the 1:1 cash leg (no stablecoin depeg modelled).
- [risky] I cannot open the cited links (islamqa.info Q504160/Q106094/Q125758/Q310956 and the GitHub repos gods-eye-view, Agent-Reach, MiroFish, TimesFM); I relied solely on the descriptions given in the prompt and recorded their URLs verbatim as citations without verifying their contents.
- [risky] Kraken is used only when Coinbase lacks a token or sufficient history; where both have data, Coinbase candles are authoritative and sources are not blended within a single series.
- [safe] The implementation language and ecosystem are Python (inferred from the reused DuckDB/backtest/HTML-reporting stack of the existing repo).
- [safe] The single pipeline command is a CLI entry point in the existing repo's convention (e.g. a make/console script), not a new web UI or service.
- [safe] The HTML report is a single self-contained static file (no server required) to serve as a portable grant demo artefact.
- [safe] Fees/slippage apply per executed trade leg at rebalance events; initial buy-in and any rebalance both incur the taker fee and slippage.
- [safe] The 24/7 clock uses UTC daily bars with no gap/holiday handling.
- [safe] Validation-gate and adapter-contract definitions are specified as interfaces/abstract types plus documented requirements only, with no runtime enforcement wired to a live signal in V1 (since no adapters are implemented).

## Recommended questions
- (none)

## Original request (authoritative)

The person's own words, unedited. Where anything above differs from this, this request wins.

> Pivot Mizan (existing repo, equity V1 complete, 7 phases shipped) to a crypto-first, spot-only halal research sandbox. Equities are PARKED, not deleted. This build is research/backtest only: no real money, no live order placement. It is V1 (the "rails") of a larger two-speed system described in the ROADMAP section; V1 must leave clean seams for it.
>
> FIQH BASIS (cited, not contested): islamqa.info Q504160 (26 Jul 2024) permits dealing in crypto if the exchange is immediate and free of leverage, "dealing in differences" (CFDs), futures and similar. Supporting refs Q106094, Q125758, Q310956. Entry stays labelled PENDING_SCHOLARLY_VERIFICATION per Mizan's standing rule. Part 2 of the same fatwa: using leaked paid signals/data violates owners' rights -> every data source must be public/licensed for our use.
>
> HARD INVARIANTS (no config switch, each with a test proving it cannot be disabled): spot only with immediate settlement; fully funded, no margin/leverage; no perps/futures/options; no CFDs or synthetic price exposure; no lending or yield products; CASH_YIELD = 0; NO NAJSH: no spoofing, layering or any order placed without intent to fill (enforced at the order/intent model level now so the future HFT layer inherits it).
>
> FIQH REGISTER PARAMETERS (configurable, each with citation/rationale): stablecoins ALLOWED (USDC is the cash leg, yield still 0, Coinbase "USDC rewards" never modelled); staking rewards OFF by default (disputed); custody = exchange custody accepted as qabd hukmi (constructive possession) for V1, with a report caveat that exchange failure (FTX-type) and freeze risk are not modelled, and self-custody recorded as the long-term target; memecoin exclusion = parameter defaulting to excluded.
>
> UNIVERSE: exactly these 14 tokens: BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK. Token screen is a per-token business-activity verdict map with written reasons, replacing the AAOIFI ratio screen. Default rejects with reasons: AAVE, COMP, MKR (lending/riba), BNB, OKB, CRO (exchange tokens earning from margin/futures), DOGE, SHIB, PEPE (maysir/gharar, parameter). Survivorship bias flagged loudly in every report.
>
> DATA: free, keyless public OHLCV candles. Coinbase primary, Kraken fallback for tokens/history Coinbase lacks. Daily granularity, maximum free history, into the existing raw cache + DuckDB store. Ingestion must be granularity-agnostic (daily now, intraday later). 24/7 market clock replaces the trading-day calendar.
>
> BACKTEST: baseline strategy = equal-weight long-only buy-and-hold over the screened universe, with periodic rebalance, explicitly labelled a baseline until validated signals exist. Costs: configurable taker fee defaulting to 0.6% per side and configurable slippage defaulting to 0.05%; never zero by default.
>
> REUSE AS-IS: invariants module, Caveat/ResultEnvelope, raw cache, DuckDB, backtest engine and flip->grace->divest state machine, HTML reporting. REBUILD: ingestion, screening, clock, purification (near-empty in V1: no dividends, staking off). PARK: EDGAR ingestion, AAOIFI ratios, SIC screening.
>
> SIGNAL ADAPTER SEAM (interface + contract only in V1, no implementations): a pluggable "external signal" interface that the backtest consumes. Named future adapters: (1) gods-eye-view (github.com/bilawalsidhu/gods-eye-view) world-event/OSINT data; (2) Agent-Reach (github.com/Panniantong/Agent-Reach) web/social data access; (3) MiroFish (github.com/666ghj/MiroFish) multi-agent simulation of how people AND the market will react to predicted events; (4) TimesFM (github.com/google-research/timesfm) zero-shot price time-series forecasting, also the numeric baseline other signals must beat; (5) Inkling 2 Small (Thinking Machines; trained with proper scoring rules for calibrated forecasting and abstention) as the reasoning/BS-check model, supporting both hosted and local backends (weights may be pending; Inkling-2-Mini GGUF as local fallback). Contract requirements: every adapter declares data provenance/licence (fatwa part 2); every signal carries a calibrated probability/uncertainty and may abstain; a validation gate must be passed before a signal can drive allocations: out-of-sample comparison against realised price behaviour, calibration, per-subgroup (per-token and per-regime) error reporting, and must beat the TimesFM/naive baseline -- aggregate fit alone is insufficient (Kutzner et al. 2026; Chidichimo et al. 2026; Krastev et al. 2025 on prompt-framing fragility).
>
> ROADMAP (document in the plan/architecture, do NOT build now): two-speed system. Slow layer = gods-eye-view + Agent-Reach + MiroFish + Inkling 2 Small: predicts events and reactions, sets which tokens, direction (long/flat only) and size limits. Fast layer = spot-only HFT execution on intraday/order-book data with TimesFM short-horizon forecasts, acting only within slow-layer limits and all hard invariants (incl. no najsh). Later phases: intraday ingestion, order-book data, adapter implementations, paper trading, then self-custody/live.
>
> OUT OF SCOPE for this build: HFT execution, live trading, exchange API keys, implementing any adapter.
>
> ACCEPTANCE: a single command fetches real candles for the 14 tokens, applies the token screen and invariants, runs the baseline backtest with fees/slippage, and emits the HTML report with fiqh-register citations, token verdicts with reasons, survivorship, custody/freeze caveats; tests prove each hard invariant (including no-najsh) cannot be disabled; the signal-adapter contract exists with provenance, calibration/abstention and validation-gate requirements; equity modules still import but are not on the default path. The report doubles as the demo artefact for a grant application, so it must be readable by a non-technical judge.
