# Baby PRD -- Pivoting a halal-constrained equity research sandbox to a crypto-first spot-only screening + long-only backtesting pipeline

## TL;DR
- Mizan is being re-pointed from stocks to crypto: it will download real daily price history for about 14 hand-picked coins, check each one against Islamic-finance rules, and simulate buying-and-holding the allowed ones over time.
- No real money, no live trading — it's a local practice sandbox, same as the stock version.
- It only ever buys coins outright with cash on hand: no borrowing, no leverage, no futures or other side-bets, and idle cash earns nothing.
- The old stock features stay in place and keep working — nothing is deleted.
- You'll know it works when all 406 existing tests still pass, the new coin screening gives a clear allowed/rejected answer with a written reason for each coin, and it produces one self-contained HTML report that leads with its own warnings and limitations.

## Scope
narrow

## Baby PRD

### Problem
Mizan V1 is a complete local sandbox for halal-constrained US-equity screening and long-only backtesting. The owner now wants crypto to be the primary focus: a sandbox that ingests real historical spot OHLCV for a small curated token universe, screens each token for Shariah compliance, backtests long-only spot strategies, and emits the same honesty-first HTML report — while the existing equity pipeline remains intact and fully tested.

### Users / who it's for
A single researcher (the project owner) exploring halal-constrained crypto investing mechanics in a local, no-real-capital research sandbox; not a trading or production system.

### In scope
- Keep all existing equity modules (EDGAR ingestion, AAOIFI ratio screening, dividend purification) untouched and their tests passing; equities are parked, not deleted.
- Ingest free, keyless, real historical daily spot OHLCV candles for a curated crypto universe from a public spot-exchange market-data endpoint (Coinbase Exchange and/or Kraken), reusing the replayable raw cache + DuckDB store pattern.
- Deterministic per-token business-activity screen keyed by symbol, each entry requiring a non-empty rationale, reusing the PURE / NON_COMPLIANT verdicts.
- Reject categories: lending/borrowing protocols, exchange tokens whose issuers derive revenue from margin/derivatives, gambling tokens, and memecoins (when exclude_memecoins is on).
- Initial universe (~14): BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK; USDC as cash/quote leg.
- Seeded exclusions with rationales: AAVE, COMP, MKR (lending); BNB, OKB, CRO (exchange tokens); DOGE, SHIB, PEPE (memecoins).
- New fiqh register entries, each visible/configurable and PENDING_SCHOLARLY_VERIFICATION: crypto_asset_permissible (default True, cite Q504160), stablecoin_as_cash (default True, USDC earns zero), staking_rewards_enabled (default False), custody_possession (register entry, no math impact), exclude_memecoins (default True, parameter not invariant).
- 24/7 daily clock using every UTC calendar day (close), not trading days.
- Reuse backtest engine, quarterly rebalance, flip -> grace -> forced-divest state machine (triggered by as-of-date changes to a token's activity-map entry), and EqualWeightStrategy as the reference strategy.
- Same self-contained static HTML report: caveats first, full fiqh register including new crypto entries, with new caveats for survivorship bias (universe = coins alive today) and un-modelled exchange counterparty/insolvency risk.
- Report must state plainly that, with staking off and no dividends, the purification ledger is effectively dormant for crypto — not hide it.
- CLI support for crypto (crypto verbs or an --asset-class flag) with equity CLI behaviour unchanged.
- Tests for every invariant, using synthetic fixtures with no network access.

### Out of scope
- Perps, futures, options, swaps, CFDs, 'dealing in differences', or any synthetic price exposure.
- Margin, leverage, borrowing, shorting; any non-fully-funded position.
- Any non-zero cash yield: lending, 'earn'/rewards products, USDC rewards.
- Staking / staking rewards (staking_rewards_enabled default False, out of V1 scope).
- Any LLM in a compliance decision path.
- Real capital, live execution, or order routing.
- Deleting or altering the existing equity modules.
- Intraday / sub-daily candle granularity.
- Modelling exchange counterparty/insolvency risk (surfaced as a caveat only, no math impact).
- Paid-for or leaked/redistributed data sources.

### Acceptance criteria
1. Running the full existing equity test suite yields 406 passing tests with zero failures and zero errors.
2. A git diff of the change shows no file under the existing equity packages (EDGAR ingestion, AAOIFI ratio screening, dividend purification) modified.
3. Running the crypto ingest command fetches real daily OHLCV from the chosen public exchange endpoint and writes it to the raw cache and DuckDB store.
4. The entire test suite runs to completion with no outbound network connection, using synthetic fixtures only.
5. Screening each of the ~14 universe tokens returns a deterministic verdict, and every per-token activity-map entry has a non-empty rationale string.
6. Each seeded exclusion (AAVE, COMP, MKR, BNB, OKB, CRO, DOGE, SHIB, PEPE) screens as NON_COMPLIANT with a stated rationale.
7. The crypto backtest clock iterates over every UTC calendar day in the window (including weekends), not only weekdays/trading days.
8. The boot check fails to start if CASH_YIELD is set to any value other than 0.0.
9. No code path in the crypto pipeline references perps, futures, options, swaps, CFDs, margin, leverage, shorting, borrowing, lending, or earn/rewards products.
10. No compliance-verdict code path invokes an LLM.
11. The generated HTML report renders the caveats banner before any number, and that banner includes the survivorship-bias caveat and the exchange-counterparty-risk caveat.
12. The generated HTML report renders the full fiqh register including the new crypto entries, each marked PENDING_SCHOLARLY_VERIFICATION.
13. The report explicitly states that the purification ledger is dormant for crypto under V1 settings (staking off, no dividends).
14. mypy --strict passes clean and ruff reports no issues on the changed code (inside .venv).
15. At least one test asserts each hardcoded crypto invariant.
16. Running the existing equity CLI verbs produces output identical to pre-pivot behaviour.

### Constraints
- Python, using the existing toolchain: .venv, pytest, mypy --strict, ruff clean.
- All 406 existing tests must keep passing.
- Tests must not hit the network; synthetic fixtures only (as in V1).
- Data must be free, keyless, public spot-exchange market data; no leaked or paid-for sources; no ToS-gray redistribution.
- Daily candles only; no intraday granularity.
- Compliance verdicts must be deterministic with no LLM anywhere in the decision.
- Equity CLI behaviour must not change.

### Research plan
- Topic: Pivoting a halal-constrained equity research sandbox to a crypto-first spot-only screening + long-only backtesting pipeline
- Time range: last 2 years (prioritise current, live API documentation)
- Items:
  1. coinbase-exchange-candles | Coinbase Exchange public candles endpoint | Current public (keyless) historical OHLCV endpoint, supported daily granularity, maximum history depth per request and overall, pagination, and rate limits. | modules: general-web, stackoverflow, github-debug
  2. kraken-public-ohlc | Kraken public OHLC endpoint | Current public (keyless) OHLC endpoint, daily interval support, how far back history is returned, result-size limits, and rate limits — to compare against Coinbase for the data leg. | modules: general-web, stackoverflow, github-debug
  3. usdc-quote-pairs-coverage | USDC quote-pair availability for the universe | Which of the ~14 universe tokens have a liquid USDC (or USD) spot pair with sufficient daily history on the chosen exchange, and how to handle tokens lacking a direct USDC pair. | modules: general-web
  4. crypto-token-business-activity | Per-token business-activity classification | Primary-source basis for classifying each token/issuer's core business (lending/borrowing protocol, exchange token with margin/derivatives revenue, gambling, memecoin) to justify each curated activity-map rationale deterministically. | modules: general-web, academic-papers
  5. fiqh-crypto-spot-basis | Fiqh basis for spot crypto permissibility | Exact conditions and supporting references in islamqa.info Q504160 (and cited Q106094, Q125758, Q310956) to word the crypto fiqh register entries and the qabd hukmi (constructive possession) caveat faithfully, without overstating settledness. | modules: general-web
  6. 24-7-utc-daily-clock | 24/7 calendar-day clock mechanics | How to adapt the existing trading-day clock to iterate every UTC calendar day at close, and how daily candle timestamps are defined/aligned across Coinbase/Kraken (UTC day boundary). | modules: general-web, github-debug
  7. crypto-survivorship-bias | Crypto survivorship bias framing | How to state the survivorship-bias caveat for a live-coins-only universe (dead/delisted tokens absent) in a way consistent with Mizan's existing honesty-surface conventions. | modules: general-web, academic-papers
- Official docs to read:
  - Coinbase Exchange API
  - Kraken REST API
  - DuckDB
  - pytest
  - mypy
  - ruff
  - matplotlib
  - Pydantic
  - islamqa.info
- Academic searches:
  - Shariah compliance screening cryptocurrency tokens methodology
  - Islamic finance permissibility digital assets spot trading
  - cryptocurrency backtesting survivorship bias dead coins universe
- Prior-art searches:
  - Coinbase Exchange historical daily candles Python client
  - Kraken public OHLC daily download Python
  - crypto long-only backtest DuckDB OHLCV cache
  - halal crypto screening token classification repository

## Assumptions
- [risky] Coinbase Exchange is chosen as the primary data source for the OHLCV leg (with Kraken as fallback), since the prompt says 'and/or' and leaves the choice to the spec. The wrong choice would change the ingestion client and history/rate-limit handling.
- [risky] MIXED is unused for crypto: because tokens have no balance sheet and there is no incidental dividend income, verdicts resolve to PURE or NON_COMPLIANT only, with MIXED remaining defined (for equities) but never emitted on the crypto path.
- [risky] The fiqh judgment-call register is expanded beyond its current 11 rows to include the new crypto entries, and the existing 'register_id exactly 1..11' validator and boot check are generalised to match the new count rather than left asserting 11.
- [safe] The links in the prompt (SEC, Tiingo, oicexchanges AAOIFI slides, amanahadvisors, arxiv, pypi, pydantic, islamqa) could not be opened during intake; their current contents are not verified here and must be checked against primary sources during the research phase.
- [safe] CLI exposes the crypto path via an --asset-class flag on the existing verbs rather than a parallel set of new crypto verbs, keeping the equity default behaviour unchanged.
- [safe] The USDC cash/quote leg carries no price series of its own (treated as a constant 1.0 peg, yield exactly 0); no OHLCV is ingested for USDC.
- [safe] No specific backtest date window is mandated, so the default crypto backtest window is driven by CLI start/end arguments (as in the equity path), with history depth bounded by what the chosen exchange's daily candles actually provide.
- [safe] The new crypto modules live in a crypto-specific package/namespace parallel to the equity packages (rather than editing equity files in place), so the 'equity modules untouched' requirement is satisfied structurally.
- [safe] Quarterly rebalance cadence is retained unchanged for crypto; only the daily clock's calendar basis (24/7 UTC days) changes, not the rebalance period.
- [safe] The crypto activity-map entries are versioned as-of a date (like equity overrides) so that a verdict flip can be driven by a map-entry change at a given date, feeding the existing flip -> grace -> forced-divest state machine.

## Recommended questions
- (none)

## Original request (authoritative)

The person's own words, unedited. Where anything above differs from this, this request wins.

> Pivot Mizan (this repo: a completed, 406-test, local Python CLI for halal-constrained equity screening + long-only backtesting) to CRYPTO-FIRST. Equities are parked, not deleted: the existing equity modules (EDGAR ingestion, AAOIFI financial-ratio screening, dividend purification) stay in the repo untouched and their tests keep passing.
>
> GOAL
> A local research sandbox (no real capital, no live execution, no order routing) that ingests real historical spot price data for a small curated crypto universe, screens each token, backtests long-only spot strategies, and emits the same caveats-first static HTML report. Value = pipeline correctness and screening honesty, same as V1.
>
> FIQH BASIS (cited, not invented)
> islamqa.info Question 504160 (26 July 2024): "It is permissible to deal in crypto currency, if the exchange takes place immediately and the transaction is free of any infractions of Islamic teachings, such as using financial leverages and dealing in differences, futures and so on." Supporting refs cited in that answer: islamqa.info Q106094, Q125758, Q310956. Register entry "crypto permissible as an asset class" cites Q504160 and, per Mizan's standing rule, remains PENDING_SCHOLARLY_VERIFICATION.
>
> INVARIANTS (hardcoded, no config knob) -- derived from the fatwa's conditions plus existing Mizan invariants
> - Spot only, immediate settlement. No perps, futures, options, swaps, CFDs / "dealing in differences", or any synthetic price exposure.
> - Long-only, fully funded. No margin, no leverage, no borrowing, no shorting.
> - Cash leg yield = 0.0 (CASH_YIELD stays 0). No lending, no "earn"/rewards products, no USDC rewards.
> - Compliance verdicts deterministic; no LLM anywhere in a compliance decision.
>
> PARAMETERS (fiqh register entries, visible, configurable, each PENDING_SCHOLARLY_VERIFICATION)
> - crypto_asset_permissible: default True, citation islamqa.info Q504160.
> - stablecoin_as_cash: default True; USDC is the cash/quote leg, earning exactly zero.
> - staking_rewards_enabled: default False (out of V1 scope; scholars differ -- service fee vs lending-like exchange products).
> - custody_possession: exchange spot settlement treated as constructive possession (qabd hukmi); record as register entry; no math impact. Add caveat: exchange counterparty/insolvency risk is not modelled.
> - exclude_memecoins: default True (maysir/gharar concern), parameter not invariant.
>
> TOKEN SCREEN (replaces AAOIFI ratio screen for crypto; tokens have no balance sheet)
> Deterministic, hand-curated per-token business-activity map, keyed by symbol, each entry requires a non-empty rationale. Verdicts reuse PURE / NON_COMPLIANT (MIXED may be unused for crypto -- spec should decide). Reject categories: lending/borrowing protocols (riba core business), exchange tokens whose issuers derive revenue from margin/derivatives, gambling tokens, memecoins (when exclude_memecoins is on).
> Initial universe (~14): BTC, LTC, BCH, ETH, SOL, ADA, AVAX, DOT, NEAR, ATOM, ALGO, XRP, XLM, LINK. Seeded exclusions with rationales: AAVE, COMP, MKR (lending), BNB, OKB, CRO (exchange tokens), DOGE, SHIB, PEPE (memecoins). Cash: USDC.
>
> DATA
> Free, keyless public historical OHLCV candles from a spot exchange (Coinbase Exchange and/or Kraken public market-data endpoints) -- research must verify current endpoints, granularity, history depth and rate limits from primary docs. Daily candles are sufficient. Reuse the replayable raw cache + DuckDB store pattern. No leaked or paid-for data sources.
>
> ENGINE CHANGES
> - Clock: crypto trades 24/7 -- daily clock must use every calendar day (UTC close), not trading days.
> - Reuse backtest engine, quarterly rebalance, flip -> grace -> forced-divest state machine (a token's verdict can flip if its map entry changes as-of a date), EqualWeightStrategy as reference.
> - Purification: no dividends in crypto; with staking off, purification ledger is effectively dormant for crypto -- report must state this, not hide it.
> - Reporting: same self-contained HTML, caveats first, fiqh register shown in full including the new crypto entries. New caveats: survivorship bias (universe = coins alive today; dead coins absent) stated loudly; exchange counterparty risk not modelled.
> - CLI: crypto verbs or an --asset-class flag; spec decides, but equity CLI behaviour must not change.
>
> CONSTRAINTS
> Python, existing toolchain (.venv, pytest, mypy --strict, ruff clean). All existing 406 tests keep passing. Tests must not hit the network (synthetic fixtures, like V1). Tests for every invariant.
