# Baby PRD -- Pivoting a halal equity research/backtest sandbox to crypto-first, spot-only, with free public OHLCV ingestion, per-token fiqh screening, invariant e [OSA: truncated, the planner wrote 207 characters]

## TL;DR
- Mizan, an existing halal-investing research tool, gets refocused from stocks to crypto -- the stock code stays parked, nothing is deleted.
- It only studies the past (backtests): no real money, no live trading, just a sandbox to see how a simple, religiously-compliant crypto strategy would have performed.
- It covers exactly 14 named coins, screening each one against Islamic rules with written reasons, and refuses coins tied to lending, gambling or leverage.
- Running one command downloads real daily price history, screens the coins, runs a plain equal-weight buy-and-hold test with trading fees, and produces an HTML report.
- You'll know it works when that report opens cleanly for a non-technical grant judge -- showing citations, per-coin verdicts, warnings -- and automated tests prove the religious 'hard rules' literally cannot be switched off.

## Scope
narrow

## Baby PRD

### Problem
Mizan currently supports halal equity research, but the person wants a crypto-focused, spot-only, religiously-compliant research sandbox that can backtest a baseline strategy over a fixed crypto universe and produce an auditable report -- without touching real money or live markets, and leaving clean seams for a larger future two-speed (slow-prediction + fast-execution) system.

### Users / who it's for
The repo owner / halal-investing researcher building Mizan, plus a non-technical grant-application judge who must be able to read the generated HTML report.

### In scope
- Pivot the existing Mizan repo to crypto-first, spot-only; equities PARKED (still import, not on default path, not deleted)
- Research/backtest only: no real money, no live order placement
- Fiqh register entry labelled PENDING_SCHOLARLY_VERIFICATION, citing islamqa.info Q504160 (26 Jul 2024) with supporting refs Q106094, Q125758, Q310956
- HARD INVARIANTS (no config switch, each with a test proving it cannot be disabled): spot only with immediate settlement; fully funded, no margin/leverage; no perps/futures/options; no CFDs or synthetic price exposure; no lending or yield products; CASH_YIELD = 0; NO NAJSH (no spoofing, layering, or any order placed without intent to fill, enforced at the order/intent model level)
- FIQH REGISTER PARAMETERS (configurable, each with citation/rationale): stablecoins ALLOWED (USDC as cash leg, yield still 0, Coinbase 'USDC rewards' never modelled); staking rewards OFF by default; custody = exchange custody accepted as qabd hukmi for V1 with report caveat on FTX-type failure and freeze risk not modelled and self-custody as long-t [OSA: truncated, the planner wrote 412 characters]
- UNIVERSE of exactly 14 tokens: BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK
- Token screen as a per-token business-activity verdict map with written reasons, replacing the AAOIFI ratio screen
- Default rejects with reasons: AAVE, COMP, MKR (lending/riba); BNB, OKB, CRO (exchange tokens earning from margin/futures); DOGE, SHIB, PEPE (maysir/gharar, parameter)
- Survivorship bias flagged loudly in every report
- DATA: free, keyless public OHLCV candles; Coinbase primary, Kraken fallback for tokens/history Coinbase lacks; daily granularity, maximum free history, into existing raw cache + DuckDB store; ingestion granularity-agnostic (daily now, intraday later)
- 24/7 market clock replacing the trading-day calendar
- BACKTEST baseline: equal-weight long-only buy-and-hold over screened universe with periodic rebalance, explicitly labelled a baseline until validated signals exist
- Costs: configurable taker fee defaulting to 0.6% per side and configurable slippage defaulting to 0.05%; never zero by default
- REUSE AS-IS: invariants module, Caveat/ResultEnvelope, raw cache, DuckDB, backtest engine and flip->grace->divest state machine, HTML reporting
- REBUILD: ingestion, screening, clock, purification (near-empty in V1: no dividends, staking off)
- PARK: EDGAR ingestion, AAOIFI ratios, SIC screening
- SIGNAL ADAPTER SEAM: pluggable 'external signal' interface + contract only (no implementations) that the backtest consumes; named future adapters gods-eye-view, Agent-Reach, MiroFish, TimesFM (also numeric baseline), Inkling 2 Small (hosted + local, Inkling-2-Mini GGUF fallback)
- Adapter contract requirements: every adapter declares data provenance/licence (fatwa part 2); every signal carries a calibrated probability/uncertainty and may abstain; a validation gate must be passed before a signal drives allocations (out-of-sample vs realised price behaviour, calibration, per-token and per-regime error reporting, must beat Tim [OSA: truncated, the planner wrote 403 characters]
- Document the two-speed ROADMAP (slow layer + fast layer) in plan/architecture with clean seams, but do NOT build it now
- Single-command acceptance flow producing the HTML report readable by a non-technical grant judge
- Every data source must be public/licensed for our use (fatwa part 2)

### Out of scope
- HFT execution
- Live trading / live order placement
- Exchange API keys
- Implementing any signal adapter
- Intraday ingestion and order-book data (future phases)
- Paper trading and self-custody/live phases
- Modelling CASH_YIELD, Coinbase 'USDC rewards', staking rewards (off by default), or exchange-failure/freeze risk
- Deleting equity modules

### Acceptance criteria
1. A single documented command fetches real OHLCV candles for all 14 named tokens (Coinbase primary, Kraken fallback) into the raw cache and DuckDB store
2. The command applies the per-token business-activity screen and the hard invariants, then runs the equal-weight long-only buy-and-hold baseline backtest with the configured taker fee (default 0.6%/side) and slippage (default 0.05%)
3. The run emits an HTML report containing fiqh-register citations, per-token verdicts with written reasons, a prominent survivorship-bias warning, and custody/freeze caveats
4. The HTML report opens and is comprehensible to a non-technical reader (no code/jargon required to understand verdicts, warnings and results)
5. Automated tests exist and pass that prove each hard invariant -- spot-only/immediate settlement, no margin/leverage, no perps/futures/options, no CFDs/synthetic exposure, no lending/yield, CASH_YIELD = 0, and NO NAJSH at the order/intent model level -- cannot be disabled via any config switch
6. The default reject tokens (AAVE, COMP, MKR, BNB, OKB, CRO, DOGE, SHIB, PEPE) are rejected by the screen with their stated reasons recorded
7. Fees and slippage are never zero by default (a run with defaults applies non-zero costs)
8. The signal-adapter interface and contract exist in code, requiring data provenance/licence, calibrated probability/uncertainty with abstention, and a validation gate (out-of-sample, calibration, per-token and per-regime error, beats TimesFM/naive baseline), with no adapter implementations present
9. The fiqh register entry is labelled PENDING_SCHOLARLY_VERIFICATION and cites Q504160 plus supporting refs
10. Equity modules still import successfully but are not reached on the default crypto execution path
11. The 24/7 market clock is used in place of the trading-day calendar, and ingestion is granularity-agnostic (daily configured now, intraday pluggable later)
12. The two-speed ROADMAP (slow and fast layers) is documented in the plan/architecture without being implemented

### Constraints
- Existing Mizan repo: equity V1 complete, 7 phases shipped; this is V1 ('rails') of a larger system
- Reuse existing invariants module, Caveat/ResultEnvelope, raw cache, DuckDB, backtest engine, flip->grace->divest state machine, HTML reporting
- Data must be free, keyless, public/licensed-for-our-use OHLCV (fatwa part 2 forbids leaked paid signals/data)
- No real money, no live orders, no exchange API keys
- Hard invariants must be non-configurable and test-protected
- Report must serve as the demo artefact for a grant application (readable by a non-technical judge)
- Platform: Windows (win32), PowerShell shell

### Research plan
- Topic: Pivoting a halal equity research/backtest sandbox to crypto-first, spot-only, with free public OHLCV ingestion, per-token fiqh screening, invariant e [OSA: truncated, the planner wrote 207 characters]
- Time range: last 3 years
- Items:
  1. coinbase-public-ohlcv | Coinbase public candle API | How to fetch keyless daily OHLCV candles and maximum free history per product, including granularity parameters and rate limits, for the primary data source | modules: general-web, stackoverflow
  2. kraken-public-ohlcv | Kraken public OHLC API fallback | How to fetch keyless daily OHLC data and history depth for tokens/pairs Coinbase lacks, including pair naming and limits | modules: general-web, stackoverflow
  3. token-availability-mapping | Availability of the 14 tokens across Coinbase/Kraken | Which of the 14 tokens and how much history are available on Coinbase vs Kraken in USD/USDC pairs, to design the primary/fallback routing | modules: general-web
  4. granularity-agnostic-ingestion | Granularity-agnostic ingestion design | Patterns for an ingestion layer that handles daily now and intraday later against a raw cache + DuckDB store with a 24/7 clock | modules: github-debug, general-web
  5. crypto-fiqh-screening | Crypto business-activity fiqh screening | Basis for per-token business-activity verdicts (lending/riba, exchange-token margin/futures income, maysir/gharar memecoins) consistent with islamqa Q504160 and supporting refs | modules: general-web, academic-papers
  6. crypto-backtest-costs | Spot crypto backtest cost modelling | Conventions for taker-fee and slippage modelling in equal-weight buy-and-hold crypto backtests with periodic rebalance, and survivorship-bias handling | modules: general-web, academic-papers
  7. calibrated-forecast-validation | Calibrated forecasting, abstention and validation gates | How to specify a validation gate using proper scoring rules, calibration, out-of-sample and per-subgroup error, and baseline-beating (per Kutzner 2026, Chidichimo 2026, Krastev 2025) for the signal-adapter contract | modules: academic-papers, general-web
  8. named-adapter-repos | Named future-adapter repositories and TimesFM | Interfaces, inputs/outputs, data provenance and licences of gods-eye-view, Agent-Reach, MiroFish, TimesFM, and Inkling 2 to shape the adapter interface/contract (no implementation) | modules: github-debug, general-web
- Official docs to read:
  - Coinbase (Exchange/Advanced Trade public market data API)
  - Kraken (public REST API)
  - DuckDB
  - TimesFM
  - gods-eye-view
  - Agent-Reach
  - MiroFish
  - Inkling 2 (Thinking Machines)
  - islamqa.info (Q504160, Q106094, Q125758, Q310956)
- Academic searches:
  - LLM probabilistic forecasting calibration proper scoring rules abstention
  - prompt framing fragility LLM forecasting Krastev 2025
  - out-of-sample subgroup error forecasting evaluation beating naive baseline Kutzner 2026 Chidichimo 2026
  - survivorship bias cryptocurrency backtesting
  - time series foundation model zero-shot forecasting TimesFM evaluation
- Prior-art searches:
  - crypto OHLCV ingestion Coinbase Kraken DuckDB python
  - cryptocurrency backtest engine equal weight buy and hold rebalance fees slippage
  - pluggable signal adapter interface backtest python
  - halal crypto screening business activity ruleset

## Assumptions
- [risky] The quote/cash leg and candle pairs are USD or USDC (USDC named as the cash leg), and token candles are fetched against a USD/USDC pair rather than crypto-crypto pairs.
- [risky] 'Periodic rebalance' for the baseline defaults to a monthly rebalance cadence (configurable) since no cadence was specified.
- [risky] 'Maximum free history' means fetching from each token's earliest available candle on the chosen source up to the most recent completed daily candle, paginating as needed.
- [risky] When Coinbase lacks a token or sufficient history, Kraken data is used for the missing portion and the source per token is recorded in the report rather than merged silently.
- [risky] The token screen's 14 accepted tokens are all given an ACCEPTED verdict by default with written per-token reasons, and only the listed 9 are rejected; no additional tokens are screened.
- [safe] The existing Mizan repo is implemented in Python (DuckDB store, backtest engine, HTML reporting imply a Python stack); the crypto rebuild continues in the same language and tooling.
- [safe] Linked GitHub repos (gods-eye-view, Agent-Reach, MiroFish, TimesFM) and the islamqa fatwa pages cannot be opened/verified by this intake stage; their exact interfaces, licences and fatwa wording are taken from the prompt's description only.
- [safe] The single acceptance command is a CLI entrypoint (e.g. a console script / python -m invocation) runnable on the user's Windows/PowerShell environment.
- [safe] The backtest starts from an equal-weight allocation of a notional starting capital (e.g. a fixed base currency amount) since no portfolio size was given.
- [safe] The signal-adapter seam is defined via language-level interfaces/abstract contracts (e.g. abstract base classes/protocols) with contract-enforcing tests but no concrete adapter code.
- [safe] Taker fee default of 0.6% per side is applied on both buy and sell legs of each rebalance trade, and slippage of 0.05% is applied per trade on top of fees.
- [safe] The HTML report is a static self-contained file (viewable in a browser offline) suitable to attach to a grant application.

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
