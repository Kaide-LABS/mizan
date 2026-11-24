# What OSA got done before it stopped

## In short
- Mizan is being switched from a stock-market research tool to a crypto one, following strict Islamic finance rules, for research and backtesting only -- no real money is ever spent or traded.
- It will pull free daily price history for 14 named coins, screen each coin against written religious-compliance reasons, and run a simple equal-weight buy-and-hold test with realistic trading fees.
- It produces one HTML report, readable by a non-technical grant judge, showing the compliance citations, per-coin verdicts, warnings about survivorship and exchange-custody risk, and the backtest result.
- Built-in 'hard rules' (spot only, no leverage, no gambling-style fake orders, zero cash yield) are locked on and backed by tests proving they cannot be switched off.
- You will know it works when one command does the whole run end-to-end, the report appears with all required sections, and the test suite passes -- including the locked-rule and no-fake-order tests.

## It did not finish
One of the AI tools stopped the build on purpose and said it should not continue.

## Stage by stage

### Stage 1
#### What was built

The project's foundation was laid for its switch from a stock tool to a crypto one. The core safety rules are now in place and switched permanently on: research only, never trading with real money, no borrowing, no gambling-style fake orders, and no cash interest. The list of 14 coins to study and the written religious-compliance reasons behind the screening are set up. Automated tests were written and pass, including tests that prove the safety rules cannot be turned off.

#### What was decided

The next stage of work was planned and written down in detail, so pricing data for the coins can be pulled from free sources later. One free data source was chosen as the main one with a second as backup, because it covers what this stage needs. These choices keep the build simple and within free tools.

#### What is uncertain

Five extra safety-related checks raised during review were not done yet and were deliberately pushed to the next stage. One technical tool may need updating, but that check hasn't been run. The team also couldn't save their finished work in the usual way due to a file-permission block, which needs attention.

### Stage 2
#### What was built

The groundwork for getting price history now exists. Mizan can reach out to a free public source to download daily coin prices, with a backup source if the first one is unavailable, and store them neatly without creating duplicates. It also now has a calendar that treats crypto as trading every day of the year, since coins never close for weekends or holidays. The programs that handle this were checked for quality and passed those checks.

#### What was decided

Prices come from one main free provider, with a second as backup, so a single outage doesn't stop the research. An older, stable version of one storage tool was kept rather than upgraded, to avoid surprises. These choices favour reliability over novelty.

#### What is uncertain

This stage did its building but did not finish its safety net. The specific tests meant to prove this stage's work behaves correctly were never written, and a required summary document for this stage was never created — both have been pushed into the next stage. The work also could not be saved properly at the time because the system blocked it. One minor reliability fix for saving prices is still outstanding. The next stage must close all of these gaps first.

### Stage 3 (did not complete)
#### What was built

The coin-screening part of the tool now works. It can take each of the named coins and sort it into a religious-compliance category with a clear accept-or-reject verdict, covering all the coins on the list plus a set of coins that are always turned down. A safety fix was also made so that saving price data either fully succeeds or fully undoes itself, never leaving half-saved data. New automated checks were added to prove the screening behaves correctly, and all current checks — 452 of them — pass.

#### What was decided

The work built on an earlier unfinished draft rather than starting over, to save time. Reusing it was double-checked first by confirming every existing check still passed before anything was touched.

#### What is uncertain

This stage did not finish. A large batch of planned safety checks — especially around pulling in the daily price data and confirming the locked rules truly cannot be switched off — was not written, because there wasn't enough time. By the project's own standard, this stage cannot count as done until those checks exist and pass. That work still needs to be completed and re-verified before moving on.

## Choices made for you
- (you confirmed this risky one) 'Periodic rebalance' for the baseline defaults to monthly, exposed as a config parameter.
- (you confirmed this risky one) Equal weighting is computed over only the tokens that pass the screen (rejected tokens excluded from the portfolio), not all 14.
- (you confirmed this risky one) 'Maximum free history' means fetching from the earliest date each public endpoint offers per token, with no fixed start date imposed.
- (you confirmed this risky one) Backtest accounting is in USD with USDC treated as the 1:1 cash leg (no stablecoin depeg modelled).
- (you confirmed this risky one) I cannot open the cited links (islamqa.info Q504160/Q106094/Q125758/Q310956 and the GitHub repos gods-eye-view, Agent-Reach, MiroFish, TimesFM); I relied solely on the descriptions given in the prompt and recorded their URLs verbatim as citations without verifying their contents.
- (you confirmed this risky one) Kraken is used only when Coinbase lacks a token or sufficient history; where both have data, Coinbase candles are authoritative and sources are not blended within a single series.
- The project will be built in six stages, ending with a single command that fetches data, screens tokens, runs a test, and produces a shareable report.
- It focuses only on crypto, covering a fixed list of 14 tokens; the older stock-market setup is kept untouched and set aside, not used.
- Orders can only ever either complete or be turned down with a stated reason — there's no way to place a fake order you never mean to fill, by design, to keep trading honest.
- An order with no real quantity or price is automatically refused, so empty or meaningless trades can't slip through.
- The permissibility (fiqh) rules for crypto are their own fresh set, checked automatically every time the system starts, so nothing runs unless the rules pass.
- It treats crypto as trading around the clock, every day, rather than on stock-market business hours.
- Judging which specific tokens are allowed or rejected (and why) comes in a later stage, building on the fixed token list.
- Long-term, holding your own crypto directly is planned, but this first version only supports holding it through an exchange.

## How it was checked
- Research: 37 official documentation source(s), 3 academic paper(s) and 0 existing project(s) were consulted.
- A second, different AI checked the research against its sources.
- Every build stage was written by one AI and reviewed by a different one, and every change was recorded in git.

## What to look at
- claude-code (opus) reviewed work written by claude-code (sonnet): the same model family but a different capability class.
- This run was carried on from its saved spec: intake, research and spec were not repeated.
- The build was carried on from phase 3: phases 1 to 2 were already finished and kept. 3 commit(s) from the interrupted attempt were folded back into the working tree so the reviewer still sees that work.

## For engineers (technical detail)

_Everything above is written for non-engineers; this is the raw detail behind it._

- `Phase 3's own runDispatch() call did not complete successfully: turn reported status "blocked".`
- `decision: The whole pivot is 6 build phases (P1 invariant+intent foundations & crypto config; P2 crypto ingestion + 24/7 clock + candles store; P3 token screening; P4 baseline backtest with fees/slippage; P5 signal-adapter seam; P6 HTML report + single pipeline command).`
- `decision: "Reuse as-is: invariants module" is read as reuse-and-extend under the module's own documented rule ("adding a field requires adding its check to boot_check in the same diff"): Phase 1 adds three crypto hard-invariant fields and three hand-written checks; no existing field, default, or meaning changes; the existing field-count test is updated in the same change (a surfaced edit, not a silent one).`
- `decision: The crypto fiqh register is a NEW model ('CryptoFiqhParams') separate from the parked equity 'FiqhParams', reusing the existing 'FiqhParam[T]' generic and 'VerificationStatus' enum. The equity AAOIFI register stays unchanged and parked.`
- `decision: No-najsh is enforced structurally with a frozen Pydantic "smart-constructor" order type ('ResolvedOrder') whose only outcome is a terminal fill OR a reasoned rejection (a discriminated union, mandatory, no default); there is no pending/resting/cancelable order type and no 'cancel()' anywhere, so "an order without intent to fill" has no representation. A 'place_order(...)' factory requires exactly one of 'fill'/'rejection'.`
- `decision: A fill requires strictly positive filled quantity and fill price; a zero-quantity "fill" is not intent to fill and is rejected at construction.`
- `decision: Phase 1 locks the 14-token universe constant and the four configurable crypto register parameters (stablecoins, staking, custody, memecoin-exclusion); the per-token business-activity verdict map and the default-reject reasons (AAVE/COMP/MKR, BNB/OKB/CRO, DOGE/SHIB/PEPE) are Phase 3 (screening), which consumes this universe (AC 4 maps to P3).`
- `decision: The 24/7 market clock and moving the equity trading-day calendar off the default path (AC 13) are Phase 2; equity modules already import, so AC 14 is satisfied progressively and verified end-to-end in Phase 6.`
- `decision: New crypto code lives under 'mizan/crypto/' and 'mizan/execution/'; new crypto docs under 'docs/crypto/'; new tests are added flat in 'tests/' to match repo convention ('testpaths = ["tests"]').`
- `decision: New crypto modules cite 'docs/crypto/PHASE_1_SPEC.md §…' in their docstrings to avoid confusion with the parked equity phase-spec references.`
- `decision: 'duckdb' stays pinned at the repo's '1.5.5' (reuse-as-is); any bump is re-verified and logged in Phase 2. The unconfirmed "DuckDB 2.0.1" claim is not relied upon.`
- `decision: 'CustodyModel' defines 'EXCHANGE_QABD_HUKMI' (V1 default) and 'SELF_CUSTODY' (the PRD's declared long-term target); the self-custody path is not implemented in V1.`
- `decision: boot_check reuses 'FiqhRegisterError' for the crypto register; 'check_all()' runs the crypto register check in addition to the existing checks, so every CLI entrypoint already gates on it.`
- `decision: Architecture: kept the original plan after an independent review -- The locked PRD scopes a narrow V1 whose single acceptance gate is "one command runs fetch→screen→backtest→report," and which mandates reusing the shipped in-process modules as-is — the Artifact-Gated Pipeline's value (replayable stages, versioned manifests, cross-process provenance) is bought with orchestration, serialization, and DuckDB-locking code that no acceptance criterion requires and that the "reuse as-is / additive pivot" constraint actively discourages. Its one genuinely relevant benefit, grant-facing prove`
- `tokens (estimated): 35993 total -- file_exploration 20%, research_input 0%, handoffs 16%, spec_prd 26%, tool_output 9%, model_output 30%`
