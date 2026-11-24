# What OSA got done before it stopped

## In short
- Mizan is being switched from a stock-market research tool to a crypto one, following strict Islamic finance rules, for research and backtesting only -- no real money is ever spent or traded.
- It will pull free daily price history for 14 named coins, screen each coin against written religious-compliance reasons, and run a simple equal-weight buy-and-hold test with realistic trading fees.
- It produces one HTML report, readable by a non-technical grant judge, showing the compliance citations, per-coin verdicts, warnings about survivorship and exchange-custody risk, and the backtest result.
- Built-in 'hard rules' (spot only, no leverage, no gambling-style fake orders, zero cash yield) are locked on and backed by tests proving they cannot be switched off.
- You will know it works when one command does the whole run end-to-end, the report appears with all required sections, and the test suite passes -- including the locked-rule and no-fake-order tests.

## It did not finish
One AI tool's hand-over note to the next could not be read, so the build was stopped rather than carry on from a possibly wrong state.

## Stage by stage

### Stage 1 (did not complete)
#### What was built

Nothing yet. This first stage did not finish, so none of the new crypto features exist or work at this point.

#### What was decided

No choices about the product were made here. The stage stopped before any real work on the coin price history, compliance screening, or backtest could begin.

#### What is uncertain

This stage did not complete — it failed right at the start. The automated system that carries out the work hit an internal error about a missing or malformed record of the project's starting point, and stopped before building anything. This is a setup or plumbing problem, not a sign that the plan itself is wrong. It needs attention before anything can move forward: the run has to be restarted once that startup error is sorted out. Until then, there is no report, no screening, and no test results to show.

## Choices made for you
- (you confirmed this risky one) 'Periodic rebalance' for the baseline defaults to monthly, exposed as a config parameter.
- (you confirmed this risky one) Equal weighting is computed over only the tokens that pass the screen (rejected tokens excluded from the portfolio), not all 14.
- (you confirmed this risky one) 'Maximum free history' means fetching from the earliest date each public endpoint offers per token, with no fixed start date imposed.
- (you confirmed this risky one) Backtest accounting is in USD with USDC treated as the 1:1 cash leg (no stablecoin depeg modelled).
- (you confirmed this risky one) I cannot open the cited links (islamqa.info Q504160/Q106094/Q125758/Q310956 and the GitHub repos gods-eye-view, Agent-Reach, MiroFish, TimesFM); I relied solely on the descriptions given in the prompt and recorded their URLs verbatim as citations without verifying their contents.
- (you confirmed this risky one) Kraken is used only when Coinbase lacks a token or sufficient history; where both have data, Coinbase candles are authoritative and sources are not blended within a single series.
- The project will be built in six stages, starting with the core safety rules and crypto setup, then adding price data, screening, testing against history, and finally a readable report — all run by a single command.
- It works only with a fixed list of 14 crypto tokens, judged against Islamic finance rules, with four adjustable settings (around stablecoins, staking, custody, and excluding meme coins).
- Trading runs around the clock, every day, matching how crypto markets actually work rather than stock-market hours.
- By design, an order can only ever either go through immediately or be turned down with a stated reason — there's no way to place an order you don't intend to complete, and no way to leave one sitting or cancel it. This enforces a key fairness rule.
- An order with no real quantity or price is automatically refused, so empty or fake orders can't exist.
- The older stock-market version of the tool is set aside, untouched; this is a fresh crypto-focused build alongside it, so nothing existing breaks.
- Every time the tool starts, it checks all its safety rules up front, so nothing can run unless those rules hold.
- It assumes tokens are held through the exchange for now; holding them yourself is named as a future goal but won't be available in this first version.

## How it was checked
- Research: 37 official documentation source(s), 3 academic paper(s) and 0 existing project(s) were consulted.
- A second, different AI checked the research against its sources.
- Every build stage was written by one AI and reviewed by a different one, and every change was recorded in git.

## What to look at
- This run was carried on from its saved spec: intake, research and spec were not repeated.
- The build was carried on from phase 1: phases 1 to 0 were already finished and kept. 2 commit(s) from the interrupted attempt were folded back into the working tree so the reviewer still sees that work.

## For engineers (technical detail)

_Everything above is written for non-engineers; this is the raw detail behind it._

- `Phase 1's own runDispatch() call did not complete successfully: ✖ Invalid string: must match pattern /^([0-9a-f]{40}|[0-9a-f]{64})$/ → at repo.head_before ✖ Invalid string: must match pattern /^([0-9a-f]{40}|[0-9a-f]{64})$/ → at repo.head_after.`
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
- `tokens (estimated): 32015 total -- file_exploration 78%, research_input 0%, handoffs 2%, spec_prd 4%, tool_output 10%, model_output 6%`
