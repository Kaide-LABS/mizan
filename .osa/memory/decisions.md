# Decisions

Choices made on this project and why. One fact per line. Written by OSA from each run's record; safe to edit by hand.

- Accepted risky assumption: 'Periodic rebalance' for the baseline defaults to monthly, exposed as a config parameter. _(run 42cd206f, 2026-11-24)_
- Accepted risky assumption: Equal weighting is computed over only the tokens that pass the screen (rejected tokens excluded from the portfolio), not all 14. _(run 42cd206f, 2026-11-24)_
- Accepted risky assumption: 'Maximum free history' means fetching from the earliest date each public endpoint offers per token, with no fixed start date imposed. _(run 42cd206f, 2026-11-24)_
- Accepted risky assumption: Backtest accounting is in USD with USDC treated as the 1:1 cash leg (no stablecoin depeg modelled). _(run 42cd206f, 2026-11-24)_
- Accepted risky assumption: I cannot open the cited links (islamqa.info Q504160/Q106094/Q125758/Q310956 and the GitHub repos gods-eye-view, Agent-Reach, MiroFish, TimesFM); I relied solely on the descriptions given in the prompt and recorded their URLs verbatim as citations... _(run 42cd206f, 2026-11-24)_
- Accepted risky assumption: Kraken is used only when Coinbase lacks a token or sufficient history; where both have data, Coinbase candles are authoritative and sources are not blended within a single series. _(run 42cd206f, 2026-11-24)_
- Architecture: kept the planned architecture -- The locked PRD scopes a narrow V1 whose single acceptance gate is "one command runs fetch→screen→backtest→report," and which mandates reusing the shipped in-process modules as-is — the Artifact-Gated Pipeline's value (replayable... _(run 42cd206f, 2026-11-24)_
- Spec decision: The whole pivot is 6 build phases (P1 invariant+intent foundations & crypto config; P2 crypto ingestion + 24/7 clock + candles store; P3 token screening; P4 baseline backtest with fees/slippage; P5 signal-adapter seam; P6 HTML report + single pipeline command). _(run 42cd206f, 2026-11-24)_
- Spec decision: "Reuse as-is: invariants module" is read as reuse-and-extend under the module's own documented rule ("adding a field requires adding its check to boot_check in the same diff"): Phase 1 adds three crypto hard-invariant fields and three hand-written checks; no... _(run 42cd206f, 2026-11-24)_
- Spec decision: The crypto fiqh register is a NEW model (`CryptoFiqhParams`) separate from the parked equity `FiqhParams`, reusing the existing `FiqhParam[T]` generic and `VerificationStatus` enum. The equity AAOIFI register stays unchanged and parked. _(run 42cd206f, 2026-11-24)_
- Spec decision: No-najsh is enforced structurally with a frozen Pydantic "smart-constructor" order type (`ResolvedOrder`) whose only outcome is a terminal fill OR a reasoned rejection (a discriminated union, mandatory, no default); there is no pending/resting/cancelable order... _(run 42cd206f, 2026-11-24)_
- Spec decision: A fill requires strictly positive filled quantity and fill price; a zero-quantity "fill" is not intent to fill and is rejected at construction. _(run 42cd206f, 2026-11-24)_
- Spec decision: Phase 1 locks the 14-token universe constant and the four configurable crypto register parameters (stablecoins, staking, custody, memecoin-exclusion); the per-token business-activity verdict map and the default-reject reasons (AAVE/COMP/MKR, BNB/OKB/CRO,... _(run 42cd206f, 2026-11-24)_
- Spec decision: The 24/7 market clock and moving the equity trading-day calendar off the default path (AC 13) are Phase 2; equity modules already import, so AC 14 is satisfied progressively and verified end-to-end in Phase 6. _(run 42cd206f, 2026-11-24)_
- Spec decision: New crypto code lives under `mizan/crypto/` and `mizan/execution/`; new crypto docs under `docs/crypto/`; new tests are added flat in `tests/` to match repo convention (`testpaths = ["tests"]`). _(run 42cd206f, 2026-11-24)_
- Out of scope: HFT execution. _(run 42cd206f, 2026-11-24)_
- Out of scope: Live trading and real-money order placement. _(run 42cd206f, 2026-11-24)_
- Out of scope: Exchange API keys / authenticated endpoints. _(run 42cd206f, 2026-11-24)_
- Out of scope: Implementing any signal adapter (gods-eye-view, Agent-Reach, MiroFish, TimesFM, Inkling 2 Small). _(run 42cd206f, 2026-11-24)_
- Out of scope: Modelling any yield, staking, lending, or USDC rewards. _(run 42cd206f, 2026-11-24)_
