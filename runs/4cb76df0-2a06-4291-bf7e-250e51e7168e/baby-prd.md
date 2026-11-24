# Baby PRD -- Crypto-first spot-only halal backtesting sandbox: keyless public OHLCV ingestion, per-token business-activity screening, 24/7 clock, and a validation-gated external-signal adapter seam

## TL;DR
- Mizan already has an equities research tool; this build pivots it to a crypto-first, halal, spot-only research sandbox while keeping the equity code parked but still working.
- It fetches real free price-history candles for about 15 hand-picked coins, screens each coin for halal business activity, and runs a pretend (no real money) buy-and-hold-style backtest.
- It produces an HTML report showing the religious (fiqh) reasoning, per-coin verdicts, and loud warnings about survivorship bias and exchange-custody risk.
- It bakes in hard religious rules (spot only, no leverage, no interest/yield) that are proven by tests to be impossible to switch off.
- You'll know it works when one command does all of the above end-to-end and the tests pass.

## Scope
narrow

## Baby PRD

### Problem
Mizan's existing equity-focused halal research engine needs to support crypto, but under strict Islamic-finance (fiqh) constraints: spot-only, fully funded, no leverage/derivatives/yield, using only public or licensed data. There is no crypto ingestion, crypto screening, 24/7 clock, or crypto-appropriate purification today, and future AI/agent signal sources must be pluggable but rigorously validated before they can influence allocations.

### Users / who it's for
Mizan's maintainers and halal-finance researchers who want to backtest crypto strategies within sharia constraints; not end investors (no real trading in this build).

### In scope
- Crypto-first, spot-only, research/backtest-only sandbox; no real money and no live order placement in this build
- Equity modules are PARKED (retained and still importable), not deleted; they are off the default path
- Fiqh basis cited (not contested): islamqa.info Q504160 dated 26 Jul 2024 with supporting refs Q106094, Q125758, Q310956; fatwa entry labelled PENDING_SCHOLARLY_VERIFICATION per Mizan's standing rule
- Fatwa Part 2 enforced: every data source must be public or licensed for our use (no leaked paid signals/data)
- HARD INVARIANTS with no config switch: spot only with immediate settlement; fully funded with no margin/leverage; no perps/futures/options; no CFDs or synthetic price exposure; no lending or yield products; CASH_YIELD = 0
- Configurable fiqh register parameters, each with citation/rationale: stablecoins ALLOWED (USDC as cash leg, yield still 0, Coinbase 'USDC rewards' never modelled); staking rewards OFF by default (disputed); custody = exchange custody accepted as qabd hukmi (constructive possession) with report caveat that FTX-type exchange failure is not modelled; [OSA: truncated, the planner wrote 401 characters]
- Hand-screened universe of ~15 tokens: BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK
- Token screen implemented as a per-token business-activity verdict map with written reasons, replacing the AAOIFI ratio screen
- Default rejects with reasons: AAVE, COMP, MKR (lending/riba); BNB, OKB, CRO (exchange tokens earning from margin/futures); DOGE, SHIB, PEPE (maysir/gharar, parameter)
- Survivorship bias flagged loudly in every report
- DATA: free, keyless, public OHLCV candles from Coinbase and/or Kraken ingested into the existing raw cache + DuckDB store
- 24/7 market clock replacing the trading-day calendar
- REUSE AS-IS: invariants module, Caveat/ResultEnvelope, raw cache, DuckDB, backtest engine and flip->grace->divest state machine, HTML reporting
- REBUILD: ingestion, screening, clock, purification (near-empty in V1: no dividends, staking off)
- PARK: EDGAR ingestion, AAOIFI ratios, SIC screening
- Signal adapter seam: a pluggable 'external signal' interface, INTERFACE ONLY in V1 with no implementations, designed to later feed the backtest from gods-eye-view, Agent-Reach, MiroFish, and an LLM reasoning model (Thinking Machines 'Inkling', to be confirmed)
- Every adapter must declare data provenance/licence (fatwa Part 2)
- Every predictive signal must pass a validation gate before it can drive allocations: out-of-sample comparison against realised price behaviour, calibration, and per-subgroup (per-token/regime) error reporting -- not just aggregate fit
- Long-only spot backtest driven by a single command that fetches candles, applies token screen + invariants, runs the backtest, and emits the HTML report

### Out of scope
- HFT / sub-minute execution
- Live trading
- Exchange API keys
- Implementing the four external integrations (gods-eye-view, Agent-Reach, MiroFish, LLM reasoning model)
- Deleting equity modules
- Modelling Coinbase 'USDC rewards' or any cash yield
- Modelling exchange-failure (FTX-type) custody loss

### Acceptance criteria
1. Running the single documented command fetches real OHLCV candles for the full ~15-token universe from Coinbase and/or Kraken into the raw cache and DuckDB store without API keys
2. The command applies the per-token business-activity screen and the hard invariants, then runs a long-only spot backtest, and writes an HTML report file
3. The HTML report contains the fiqh-register citations (including Q504160 and supporting refs), per-token verdicts with written reasons, a survivorship-bias caveat, and a custody caveat noting exchange failure is not modelled
4. Each hard invariant (spot-only/immediate settlement, no margin/leverage, no perps/futures/options, no CFDs/synthetic exposure, no lending/yield, CASH_YIELD=0) has a test proving it cannot be enabled or disabled via configuration
5. Default-reject tokens (AAVE, COMP, MKR, BNB, OKB, CRO, DOGE, SHIB, PEPE) do not appear in the backtested universe, and the report records their rejection reasons
6. The backtest uses a 24/7 market clock (no weekend/holiday gaps) rather than the equity trading-day calendar
7. Equity modules still import successfully in the test suite but are not exercised on the default run path
8. The signal-adapter interface exists with no concrete implementations, defines a required data-provenance/licence declaration, and defines a validation gate requiring out-of-sample, calibration, and per-subgroup error reporting before a signal can drive allocations
9. The fatwa register entry is present and labelled PENDING_SCHOLARLY_VERIFICATION
10. The configurable fiqh register parameters (stablecoins, staking, custody, memecoin exclusion) each carry a citation/rationale, with staking OFF and memecoins excluded by default

### Constraints
- Existing Mizan repo; must reuse invariants module, Caveat/ResultEnvelope, raw cache, DuckDB, backtest engine, flip->grace->divest state machine, and HTML reporting as-is
- Data must be free, keyless, public OHLCV from Coinbase and/or Kraken only
- All data sources must be public or licensed for our use (fatwa Part 2)
- Hard invariants must be non-configurable in code
- No real money, no live order placement, no exchange API keys in this build

### Research plan
- Topic: Crypto-first spot-only halal backtesting sandbox: keyless public OHLCV ingestion, per-token business-activity screening, 24/7 clock, and a validation-gated external-signal adapter seam
- Time range: last 3 years (plus the cited 2024 fatwa and 2026 benchmark papers)
- Items:
  1. coinbase-kraken-public-ohlcv | Keyless public OHLCV endpoints for Coinbase and Kraken | Which free, keyless public candle endpoints exist, their granularities, pagination/rate limits, symbol naming, and historical depth for the universe tokens | modules: general-web, github-debug
  2. duckdb-raw-cache-ingestion | Ingesting candles into raw cache + DuckDB | How to persist and query OHLCV time-series efficiently in DuckDB alongside the existing raw-cache pattern, including schema and idempotent upserts | modules: general-web, stackoverflow
  3. 24-7-market-clock | 24/7 crypto market clock design | How to replace a trading-day calendar with a continuous 24/7 clock (bar alignment, resampling, gap handling) compatible with the existing backtest engine | modules: general-web, github-debug
  4. token-business-activity-screen | Per-token halal business-activity verdicts | Evidence for classifying each universe/reject token's core business activity (lending/riba, exchange margin/futures revenue, maysir/gharar) to justify written verdicts | modules: general-web
  5. fiqh-crypto-spot-fatwa | IslamQA fatwa Q504160 and supporting refs | The precise rulings and conditions in Q504160, Q106094, Q125758, Q310956 to encode citations, invariants, and the provenance rule (Part 2) | modules: general-web
  6. stablecoin-staking-custody-fiqh | Fiqh of stablecoins, staking, and exchange custody (qabd hukmi) | Scholarly basis/dispute for USDC as cash leg, staking rewards, and constructive possession to support configurable register parameters and caveats | modules: general-web, academic-papers
  7. signal-adapter-validation-gate | Validation-gate design for predictive signals | How to design out-of-sample, calibration, and per-subgroup (per-token/regime) error evaluation so agent/LLM predictions cannot drive allocations on aggregate fit alone | modules: academic-papers, general-web
  8. external-signal-sources-provenance | External signal source projects and provenance | What gods-eye-view, Agent-Reach, MiroFish, and Thinking Machines 'Inkling' provide and their data licences, to shape the adapter interface and provenance declarations | modules: github-debug, general-web
- Official docs to read:
  - Coinbase (Exchange/Advanced Trade public market data API)
  - Kraken (public REST market data API)
  - DuckDB
  - gods-eye-view
  - Agent-Reach
  - MiroFish
  - Thinking Machines Inkling
  - USDC (Circle)
- Academic searches:
  - out-of-sample calibration evaluation of agent-based and LLM price predictions subgroup error
  - Kutzner 2026 synthetic prediction calibration subgroup failure
  - Chidichimo 2026 benchmark agent prediction financial time series
  - per-regime backtest validation cryptocurrency forecasting
- Prior-art searches:
  - keyless Coinbase Kraken OHLCV fetcher python DuckDB
  - crypto backtest engine long-only spot DuckDB
  - halal crypto screening token business activity python
  - pluggable signal adapter interface backtesting provenance

## Assumptions
- [risky] Default backtest history uses the maximum free depth available from the chosen exchange at daily candle granularity, since no explicit date range or timeframe was specified.
- [risky] Coinbase is the primary OHLCV source with Kraken as fallback/secondary for tokens or history Coinbase does not serve keylessly.
- [risky] The long-only spot backtest uses a simple default allocation (e.g. equal-weight buy-and-hold across the screened universe) in V1, since no specific strategy was specified and no external signals are implemented.
- [risky] The universe list is treated as exactly the 14 named tokens (BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK); '~15' is approximate and no additional token is invented.
- [risky] The validation gate is defined as an enforceable interface contract/spec in V1 (interface-only seam), not a running validator, since no signal implementations exist yet.
- [risky] Transaction costs/fees and slippage are modelled with the existing backtest engine's defaults (or zero if none exist) since none were specified.
- [safe] The 'single command' is a CLI entrypoint in the existing Mizan repo (e.g. a make target or module command) rather than a new UI or service.
- [safe] USDC is the sole stablecoin cash leg modelled; other stablecoins are not added to the universe in V1.
- [safe] Purification module is retained but effectively a no-op in V1 (no dividends, staking off), rather than removed.
- [safe] The external GitHub repos and the IslamQA fatwa pages cannot be opened by this intake stage and will be read during the research phase; their exact contents are not assumed here.
- [safe] 'Thinking Machines Inkling' is treated as unconfirmed (to-be-confirmed) and only a placeholder adapter target, not a built integration.
- [safe] Report output is a static HTML file written to the existing reporting output location, consistent with the reused HTML reporting module.

## Recommended questions
- (none)

## Original request (authoritative)

The person's own words, unedited. Where anything above differs from this, this request wins.

> Pivot Mizan (existing repo, equity V1 complete, 7 phases shipped) to a crypto-first, spot-only halal research sandbox. Equities are PARKED, not deleted. Research/backtest only: no real money, no live order placement in this build.
>
> FIQH BASIS (cited, not contested): islamqa.info Q504160 (26 Jul 2024) permits dealing in crypto if the exchange is immediate and free of leverage, "dealing in differences" (CFDs), futures and similar. Supporting refs Q106094, Q125758, Q310956. Entry stays labelled PENDING_SCHOLARLY_VERIFICATION per Mizan's standing rule. Part 2 of the same fatwa: using leaked paid signals/data violates owners' rights -> every data source must be public/licensed for our use.
>
> HARD INVARIANTS (no config switch): spot only with immediate settlement; fully funded, no margin/leverage; no perps/futures/options; no CFDs or synthetic price exposure; no lending or yield products; CASH_YIELD = 0.
>
> FIQH REGISTER PARAMETERS (configurable, each with citation/rationale): stablecoins ALLOWED (USDC is the cash leg, yield still 0, Coinbase "USDC rewards" never modelled); staking rewards OFF by default (disputed); custody = exchange custody accepted as qabd hukmi (constructive possession), with a report caveat that exchange failure (FTX-type) is not modelled; memecoin exclusion = parameter defaulting to excluded.
>
> UNIVERSE (hand-screened, ~15): BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK. Token screen is a per-token business-activity verdict map with written reasons, replacing the AAOIFI ratio screen. Default rejects: AAVE, COMP, MKR (lending/riba), BNB, OKB, CRO (exchange tokens earning from margin/futures), DOGE, SHIB, PEPE (maysir/gharar, parameter). Survivorship bias flagged loudly in every report.
>
> DATA: free, keyless public OHLCV candles from Coinbase and/or Kraken into the existing raw cache + DuckDB store. 24/7 market clock replaces the trading-day calendar.
>
> REUSE AS-IS: invariants module, Caveat/ResultEnvelope, raw cache, DuckDB, backtest engine and flip->grace->divest state machine, HTML reporting. REBUILD: ingestion, screening, clock, purification (near-empty in V1: no dividends, staking off). PARK: EDGAR ingestion, AAOIFI ratios, SIC screening.
>
> SIGNAL ADAPTER SEAM (interface only in V1, no implementations): a pluggable "external signal" interface so later layers can feed the backtest: gods-eye-view (github.com/bilawalsidhu/gods-eye-view, data aggregation), Agent-Reach (github.com/Panniantong/Agent-Reach, web/social data access), MiroFish (github.com/666ghj/MiroFish, multi-agent swarm prediction), and an LLM reasoning model (Thinking Machines "Inkling", to be confirmed). Every adapter must declare data provenance/licence (fatwa part 2), and every predictive signal must pass a validation gate before it can drive allocations: out-of-sample comparison against realised price behaviour, calibration, and per-subgroup (per-token/regime) error reporting, not just aggregate fit. Rationale: synthetic/agent predictions can match averages while failing on behaviour and subgroups (Kutzner et al. 2026; Chidichimo et al. 2026 benchmark).
>
> OUT OF SCOPE for this build: HFT/sub-minute execution, live trading, exchange API keys, implementing the four external integrations.
>
> ACCEPTANCE: a single command fetches real candles for the universe, applies the token screen and invariants, runs a long-only spot backtest, and emits the HTML report with fiqh-register citations, token verdicts, survivorship and custody caveats; tests prove each hard invariant cannot be disabled; equity modules still import but are not on the default path.
