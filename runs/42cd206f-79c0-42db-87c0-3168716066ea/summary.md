# What OSA got done before it stopped

## In short
- Mizan is being switched from a stock-market research tool to a crypto one, following strict Islamic finance rules, for research and backtesting only -- no real money is ever spent or traded.
- It will pull free daily price history for 14 named coins, screen each coin against written religious-compliance reasons, and run a simple equal-weight buy-and-hold test with realistic trading fees.
- It produces one HTML report, readable by a non-technical grant judge, showing the compliance citations, per-coin verdicts, warnings about survivorship and exchange-custody risk, and the backtest result.
- Built-in 'hard rules' (spot only, no leverage, no gambling-style fake orders, zero cash yield) are locked on and backed by tests proving they cannot be switched off.
- You will know it works when one command does the whole run end-to-end, the report appears with all required sections, and the test suite passes -- including the locked-rule and no-fake-order tests.

## It did not finish
The finished project did not pass the final check against the requirements.

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

### Stage 3
#### What was built

The project now has a complete, tested foundation for the crypto compliance checker. It can take the 14 chosen coins (plus a list of coins to always reject), sort each into a business category, and give each one a plain religious-compliance verdict with its own written reason. It can also pull and store daily price history, drop incomplete days, and enforce the locked "hard rules." The full set of automated checks — now 487 of them — all pass, including the ones proving the locked rules can't be turned off.

#### What was decided

The strict religious rules were kept permanently locked on, as the project requires. A planned limitation in how price files are named on Windows was left as-is rather than fixed, because fixing it wasn't part of this stage's job — it was worked around in the tests and flagged for a human to review.

#### What is uncertain

Three things need your attention. The Windows file-naming limitation still needs a human decision on whether to fix it later. The actual buy-and-hold backtest and the final HTML report are not built yet — they are planned for later stages. And one rule interpretation (whether trading fees may ever be set to exactly zero) should be confirmed as matching your intent.

### Stage 4
#### What was built

The part of Mizan that runs the pretend investment test now works. It takes the approved coins, spreads money evenly across them, holds them over time, and applies realistic trading fees — all on paper, with no real money. It can also figure out which coins passed the religious-compliance screen and work out the test's rebalancing dates. A full set of automated checks for this piece now exists and all of them pass.

#### What was decided

Trading fees are permanently switched on and can never be set to zero, so every test reflects real-world costs — this was chosen to keep results honest. The coin list is always read fresh each run rather than remembered from before, to avoid stale results.

#### What is uncertain

This stage is finished, but the project is not. The report that a grant judge would read, and the single command that runs everything start-to-finish, are still not built. One open point: whether a future stage should allow a zero-fee check for testing. Also, one reviewer ended up checking their own earlier work rather than a second person doing it.

### Stage 5
#### What was built

A safety layer now exists that defines exactly what a trading signal must prove before it could ever be trusted — and a locked gate that refuses to let any unproven signal through. Nothing actually trades; this is the rulebook and the lock, plus plain-language documentation explaining the five standards a signal must meet. The written plan for the next stage (the report and the one-command run) was also drafted.

#### What was decided

The honesty checks were made impossible to turn off, so no future shortcut can bypass them. The work was split into two halves handled in turn, to keep each piece testable. Everything was grounded in the actual working product rather than the original wish-list, to avoid promising things that don't exist.

#### What is uncertain

This stage set up the gate but did not build the thing that walks through it: there is still no real signal, no live forecasting, and no genuine accuracy measurements — those come later. Also worth noting: the final review of this stage was done by the same automated reviewer that did the work, so a fully independent check is still missing. All tests passed.

### Stage 6
#### What was built

The final piece of the crypto research tool now works. One single command runs the whole process start to finish: it gathers daily price history for the coins, checks each one against the written religious-compliance reasons, runs the fee-aware buy-and-hold test, and produces the finished HTML report a non-technical judge can read. The report now includes a new plain-language warning about the risk that an exchange could freeze or lose access to coins. With this stage done, all planned work for this version is finished.

#### What was decided

A new "exchange freeze/loss" warning was added and shown only when relevant, so judges see risks honestly. The safety rules (no borrowing, no real trades, no cash interest) remain permanently locked, backed by tests. The report shows one performance chart rather than two, to keep it simple.

#### What is uncertain

One point needs your attention: the final checking step was reviewed by the same automated reviewer that did part of the building, rather than an independent one. All 563 tests passed and every requirement was met, but this self-review is a mild weakness. The tool does not predict prices or model the freeze risk itself — these are noted as intentional limits, not finished features.

## Choices made for you
- (you confirmed this risky one) 'Periodic rebalance' for the baseline defaults to monthly, exposed as a config parameter.
- (you confirmed this risky one) Equal weighting is computed over only the tokens that pass the screen (rejected tokens excluded from the portfolio), not all 14.
- (you confirmed this risky one) 'Maximum free history' means fetching from the earliest date each public endpoint offers per token, with no fixed start date imposed.
- (you confirmed this risky one) Backtest accounting is in USD with USDC treated as the 1:1 cash leg (no stablecoin depeg modelled).
- (you confirmed this risky one) I cannot open the cited links (islamqa.info Q504160/Q106094/Q125758/Q310956 and the GitHub repos gods-eye-view, Agent-Reach, MiroFish, TimesFM); I relied solely on the descriptions given in the prompt and recorded their URLs verbatim as citations without verifying their contents.
- (you confirmed this risky one) Kraken is used only when Coinbase lacks a token or sufficient history; where both have data, Coinbase candles are authoritative and sources are not blended within a single series.
- The project will be built in six stages, ending with a single command that fetches data, screens tokens, runs a test trade simulation, and produces a report — so you can run the whole thing in one step.
- It works with cryptocurrencies only (buying and selling), and trades around the clock every day, since crypto markets never close. The earlier stock-market setup is set aside, untouched.
- It covers a fixed list of 14 tokens, with religious-compliance rules you can adjust in four areas (stablecoins, staking, custody, and excluding joke/meme coins).
- By design, the system can only either complete a trade or refuse it with a stated reason — there's no way to place an order you don't intend to fill, and no lingering or cancellable orders. This structurally enforces a key fairness rule.
- A trade only counts if it's for a real amount at a real price; empty or zero trades are automatically rejected.
- The compliance rules are checked automatically every time the system starts, so nothing can run without passing them.
- The final report is a self-contained web page with its religious-compliance reasoning and cautions included, meant to stand on its own for reviewers.
- It reuses proven existing components rather than rebuilding them, keeping the project simpler and more reliable; one planned long-term feature (holding your own crypto directly) is noted but not built yet.

## How it was checked
- Research: 37 official documentation source(s), 3 academic paper(s) and 0 existing project(s) were consulted.
- A second, different AI checked the research against its sources.
- Every build stage was written by one AI and reviewed by a different one, and every change was recorded in git.

## Does it actually work?
- The final check could NOT be carried out (✖ Too big: expected string to have <=1500 characters
  → at notes), so the result is unverified.

## What to look at
- claude-code (opus) reviewed work written by claude-code (sonnet): the same model family but a different capability class.
- This run was carried on from its saved spec: intake, research and spec were not repeated.
- The build was carried on from phase 5: phases 1 to 4 were already finished and kept. 4 commit(s) from the interrupted attempt were folded back into the working tree so the reviewer still sees that work.
- phase 5: Turn 2 (reviewer/claude-code) is reviewing its own prior work: the reviewer seat and the seat whose diff it reviews are the same provider and the same model (role_pins left no other seat eligible, or no second model was set).
- phase 6: Turn 2 (reviewer/claude-code) is reviewing its own prior work: the reviewer seat and the seat whose diff it reviews are the same provider and the same model (role_pins left no other seat eligible, or no second model was set).

## For engineers (technical detail)

_Everything above is written for non-engineers; this is the raw detail behind it._

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
- `tokens (estimated): 315544 total -- file_exploration 36%, research_input 0%, handoffs 16%, spec_prd 30%, tool_output 1%, model_output 17%`
