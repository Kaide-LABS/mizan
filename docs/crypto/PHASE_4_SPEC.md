# Phase 4 — Baseline Backtest: Equal-Weight Buy-and-Hold, Periodic Rebalance, Fees & Slippage

## Goal
Build the baseline crypto backtest (AC 5, 6): equal-weight long-only buy-and-hold over the screened
14-token universe, with a configurable periodic rebalance cadence, over the 24/7 clock, explicitly
labelled `"baseline"` in its output; a cost model applying a per-side taker fee (default 0.6%) and
slippage (default 0.05%) to every traded leg, both config-overridable and structurally incapable of
defaulting to or being set to zero. No report, no CLI pipeline verb, no signal-adapter wiring.

## Scope
In scope: a new `mizan/crypto/backtest.py` (the cost model, the configurable-cadence rebalance-date
generator, the cost-aware allocation function, and `run_crypto_backtest` — the canonical entry
point); their tests; `docs/crypto/ARCHITECTURE.md` (additive), `docs/crypto/PHASE_4_SPEC.md` (commit
this spec as the governing document), `README.md` (one sentence); the scope-guard extension. Out of
scope: everything in "Out of scope for this phase" below.

Every new/edited module: `from __future__ import annotations`, full type annotations
(`mypy --strict` clean), ruff-clean, module docstring citing `docs/crypto/PHASE_4_SPEC.md §…`. No new
runtime dependency — `duckdb`, `pydantic` are already pinned and reused as-is.

## Part A (first agent) — the crypto backtest engine

### A1. Why a new parallel module, not an extension of `mizan/backtest/`
`mizan/backtest/portfolio.py` (`Portfolio`, `Holding`, `apply_allocation`, `apply_cash_yield`,
`mark_to_market`) and `mizan/backtest/strategy.py` (`AllocationInstruction`, `Strategy`,
`EqualWeightStrategy`, `StrategyContractViolationError`) are already fully equity-agnostic — neither
module imports `price_bars`, a CIK, or any equity-specific type. These are reused **as-is, with zero
modification**, matching the PRD's "REUSE AS-IS: ... backtest engine" instruction exactly where it
genuinely applies. `mizan/backtest/clock.py` (`run_backtest`, `rebalance`,
`generate_rebalance_dates`, `step`) and `mizan/backtest/compliance_state.py` (`transition`, the
flip→grace→divest state machine) are **not** reused: they are deeply equity-coupled — hardcoded
quarterly-only cadence (`_REBALANCE_MONTHS`), `price_bars` SQL, CIK-keyed records, dividend/split
handling (crypto has none — out of scope per the PRD), and a per-rebalance re-screen that exists only
because equity's AAOIFI ratio screen is time-varying. Crypto's classification map (Phase 3) is a
static, hand-authored constant: under one `fiqh_params` value, `screen_token`'s answer for a given
ticker never changes during a single backtest run, so there is nothing for a flip→grace→divest
machine to ever observe. Building a new, parallel set of functions for the genuinely crypto-specific
parts (rebalance-date generation over the 24/7 clock, cost application, the candle-reading loop) is
the same "new, not reuse" judgment call Phase 3's own A1 made for the classification map — Phase 1's
`CustodyModel`/`CryptoFiqhParams` set the precedent of a parallel model where equity's analogue does
not structurally fit.

### A2. The never-zero cost model
**File:** `mizan/crypto/backtest.py` (new).
```python
class BacktestCostParams(MizanBaseModel):
    taker_fee_rate: float = Field(default=0.006, gt=0.0)
    slippage_rate: float = Field(default=0.0005, gt=0.0)

DEFAULT_BACKTEST_COST_PARAMS = BacktestCostParams()
```
`Field(gt=0.0)` makes "never zero" a construction-time fact, not a runtime check a caller could route
around — the same "illegal states unrepresentable" discipline `AllocationInstruction`'s own validator
and `Holding.quantity`/`Portfolio.cash`'s `Field(ge=0.0)` already use. `BacktestCostParams(
taker_fee_rate=0.0)` and `BacktestCostParams(slippage_rate=0.0)` both raise `pydantic.ValidationError`
— a caller can override either rate to any other positive value, but never to exactly zero (§Spec
assumptions explains why this reads "never zero by default" as a structural ban, not merely a default
value).

### A3. Configurable-cadence rebalance dates over the 24/7 clock
**File:** `mizan/crypto/backtest.py`.
```python
def generate_crypto_rebalance_dates(
    start_date: date, end_date: date, *, interval_days: int = 30
) -> tuple[date, ...]:
```
Pure function. Raises `ValueError` if `interval_days <= 0`. `start_date` is always the first
rebalance (matches `mizan.backtest.clock.generate_rebalance_dates`'s own "deploy capital on day one"
convention); every subsequent rebalance is exactly `interval_days` calendar days after the previous
one, continuing while the candidate date is `<= end_date`. Unlike the equity function, there is no
calendar-month snapping — every date is a plain `timedelta` offset, consistent with
`mizan.crypto.clock.generate_market_days` treating every UTC calendar day identically (§Spec
assumptions resolves "monthly... config parameter" to `interval_days=30`).

### A4. Cost-aware allocation
**File:** `mizan/crypto/backtest.py`.
```python
def apply_allocation_with_costs(
    portfolio: Portfolio,
    instruction: AllocationInstruction,
    prices: dict[str, float],
    *,
    cost_params: BacktestCostParams = DEFAULT_BACKTEST_COST_PARAMS,
) -> Portfolio:
```
For every ticker in `instruction.target_weights | portfolio.holdings.keys()`, computes
`current_value` (0.0 if not currently held) and `target_value = weight * mark_to_market(portfolio,
prices)` (0.0 if absent from `target_weights`) at the caller-supplied, **unadjusted** `prices` (always
the candle `close`, mirroring `mizan.backtest.portfolio`'s own "`raw_close`, never `adj_close`"
discipline — crypto candles carry no split/dividend adjustment at all). A ticker trades BUY if
`target_value > current_value` (by more than the `1e-9` tolerance `AllocationInstruction` already
uses), SELL if `target_value < current_value`, and is left untouched (no cost applied) if the two are
equal within that tolerance. For every traded ticker, builds an execution price —
`price * (1 + slippage_rate) * (1 + taker_fee_rate)` for a BUY, `price * (1 - slippage_rate) *
(1 - taker_fee_rate)` for a SELL — and substitutes it into a copy of `prices` for that ticker only
(an untraded ticker's quoted price is unchanged, since no leg means no cost). Calls the imported,
**unmodified** `mizan.backtest.portfolio.apply_allocation(portfolio, instruction, adjusted_prices)`
and returns its result directly — no second, post-hoc cash deduction anywhere in this function. Baking
both costs into the per-unit execution price this way means every one of `apply_allocation`'s own
non-negativity guarantees (`Holding.quantity: Field(ge=0.0)`, `Portfolio.cash: Field(ge=0.0)`) carry
over to the cost-aware path completely unmodified — there is no new way for this function to produce
a negative cash balance that `apply_allocation`'s own construction-time guarantee does not already
forbid (§Red-team R1 is the test proving this at the boundary case).

### A5. Candle-series read helpers
**File:** `mizan/crypto/backtest.py` (private — mirrors
`mizan.backtest.clock._resolve_trading_dates`/`_resolve_day_rows`'s own shape, reading `candles`
instead of `price_bars`).
```python
def _resolve_candle_dates(
    con: duckdb.DuckDBPyConnection, symbols: frozenset[str], granularity: str,
    start_date: date, end_date: date,
) -> tuple[date, ...]:
```
Every distinct `DATE(ts)` present in `candles` for `symbols`/`granularity`, between `start_date` and
`end_date` inclusive, ascending. Casting the stored `TIMESTAMP` to a `date` is lossless for V1:
Phase 2's daily ingestion always writes `ts` at exactly `00:00:00 UTC` for `granularity="1d"`. Uses
**actual ingested rows**, not `mizan.crypto.clock.generate_market_days`'s theoretical 24/7 calendar —
the same choice equity's `_resolve_trading_dates` already makes against `price_bars`, and for the
same reason: iterating a day with no ingested candle for any ticker would hit a missing-price lookup
with nothing to mark a position to.
```python
def _resolve_day_closes(
    con: duckdb.DuckDBPyConnection, symbols: frozenset[str], granularity: str, as_of_date: date,
) -> dict[str, float]:
```
One query returning `{symbol: close}` for every symbol with a `candles` row at that UTC day's
`00:00:00` timestamp. Only `close` is read — crypto candles carry no adjusted/raw distinction, so
unlike equity's `_resolve_day_rows` there is no `splits`/`divs` triple to decompose.

### A6. The compliant-universe seam (so Part B can test the filter without a second real screen)
**File:** `mizan/crypto/backtest.py`.
```python
def _compliant_universe_tickers(*, fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS) -> frozenset[str]:
```
`frozenset(ticker for ticker in CRYPTO_UNIVERSE if mizan.crypto.screening.screen_universe(
fiqh_params=fiqh_params)[ticker].payload["verdict"] == Verdict.PURE)`. Imports `screen_universe` by
module path (`from mizan.crypto import screening as crypto_screening`), never
`from mizan.crypto.screening import screen_universe` — the same import-order discipline
`mizan.backtest.clock`'s own top-of-file docstring documents for `mizan.screening.verdict`, so a test
wrapping `mizan.crypto.screening.screen_universe` with `monkeypatch.setattr` actually affects every
call this function makes (§B2 needs this). Read fresh on every call — never cached at import time
(§Red-team R2).

### A7. Part-A smoke tests
**File:** `tests/test_crypto_backtest.py` (new).
- `generate_crypto_rebalance_dates` happy path: default `interval_days=30` over a 95-day window;
  assert `start_date` is the first element, every subsequent element is exactly 30 days after the
  previous one, and the last element is `<= end_date`.
- `generate_crypto_rebalance_dates(start_date, start_date)` returns a one-element tuple.
- `generate_crypto_rebalance_dates` raises `ValueError` for `interval_days=0` and `interval_days=-1`.
- `BacktestCostParams()` defaults to `taker_fee_rate=0.006`, `slippage_rate=0.0005`.
- `BacktestCostParams(taker_fee_rate=0.0)` and `BacktestCostParams(slippage_rate=0.0)` each raise
  `pydantic.ValidationError`.
- `apply_allocation_with_costs` one-ticker buy, known numbers: `price=100.0`, defaults
  (`slippage_rate=0.0005`, `taker_fee_rate=0.006`); starting `Portfolio(cash=1000.0, holdings={})`,
  `AllocationInstruction(target_weights={"BTC": 1.0})`; assert the resulting holding's `quantity`
  equals `1000.0 / (100.0 * 1.0005 * 1.006)` (float-tolerance comparison) and `cash` is `0.0` (within
  tolerance).
- `apply_allocation_with_costs` one-ticker sell: starting with a BTC holding, an instruction that
  liquidates it (`target_weights={}`), assert the cash credited is strictly less than
  `quantity * price` (the unadjusted quoted value) — the seller receives less than the frictionless
  amount.
- `apply_allocation_with_costs` produces a strictly lower total `mark_to_market` value (evaluated at
  the **unadjusted** `prices`) than `mizan.backtest.portfolio.apply_allocation` does for the identical
  starting `Portfolio`/`instruction`/`prices` — the one assertion proving costs are a net drag, not a
  wash.

**Part A done when:** the module imports, `mypy --strict`/`ruff` pass, every A7 test passes.

## Part B (second agent)
Depends on Part A's committed module.

### B1. `run_crypto_backtest` — the canonical entry point
**File:** `mizan/crypto/backtest.py`.
```python
class CryptoBacktestResult(MizanBaseModel):
    strategy_label: Literal["baseline"] = "baseline"
    daily_snapshots: tuple[DailySnapshot, ...]
    rebalance_dates: tuple[date, ...]
    excluded_tickers: tuple[str, ...]
    cost_params: BacktestCostParams

def run_crypto_backtest(
    *,
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    initial_cash: float,
    strategy: Strategy = EqualWeightStrategy(),
    interval_days: int = 30,
    cost_params: BacktestCostParams = DEFAULT_BACKTEST_COST_PARAMS,
    fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS,
    granularity: str = "1d",
) -> ResultEnvelope:
```
No `tickers`/`universe` parameter exists anywhere in this signature (§B4 — the locked 14-token
universe cannot be widened or narrowed by a caller). Computes
`compliant = _compliant_universe_tickers(fiqh_params=fiqh_params)` **once**, before the loop starts —
not re-screened at every rebalance (§A1's rationale). `excluded_tickers =
tuple(sorted(frozenset(CRYPTO_UNIVERSE) - compliant))`. Builds
`rebalance_dates = generate_crypto_rebalance_dates(start_date, end_date, interval_days=interval_days)`
and `rebalance_date_set = frozenset(rebalance_dates)`; resolves
`trading_dates = _resolve_candle_dates(con, compliant, granularity, start_date, end_date)`. Starts
`portfolio = Portfolio(cash=initial_cash, holdings={})`. For every `as_of_date` in `trading_dates`,
in order: resolves `closes = _resolve_day_closes(con, compliant, granularity, as_of_date)`; if
`as_of_date in rebalance_date_set`, calls `strategy.select(as_of_date=as_of_date,
compliant_tickers=compliant, portfolio=portfolio)`, validates the returned instruction names only
tickers in `compliant` (raising the imported, unmodified `StrategyContractViolationError` otherwise,
mirroring `mizan.backtest.clock.rebalance`'s own check verbatim), then
`portfolio = apply_allocation_with_costs(portfolio, instruction, closes, cost_params=cost_params)`;
appends one `DailySnapshot(as_of_date=as_of_date, cash=portfolio.cash, holdings={t: h.quantity for
t, h in portfolio.holdings.items()}, portfolio_value=mark_to_market(portfolio, closes))` every day,
traded or not. No dividend crediting, no split adjustment, no `compliance_state` transition anywhere
in this loop (§A1 — crypto has neither). Returns
`ResultEnvelope(active_caveats=(Caveat.SURVIVORSHIP_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION),
payload=CryptoBacktestResult(strategy_label="baseline", daily_snapshots=..., rebalance_dates=
rebalance_dates, excluded_tickers=excluded_tickers, cost_params=cost_params).model_dump())`. Boot
check is not re-run here, matching `mizan.backtest.clock.run_backtest`'s own precedent — `mizan/cli/
main.py`'s centralized `check_all()` already runs before any subcommand dispatches.

### B2. The compliant-universe filter actually drives the backtest
**File:** `tests/test_crypto_backtest.py` (extend).
- `test_a_non_compliant_universe_ticker_is_never_purchasable`: under the real classification map
  every one of the 14 `CRYPTO_UNIVERSE` tokens is `PURE` regardless of `fiqh_params` (none of the 14
  fall in any gated category — only the separate `DEFAULT_REJECT_LIST` memecoins are gated, and they
  are not in `CRYPTO_UNIVERSE`), so this test cannot exercise exclusion against the real map.
  `monkeypatch.setattr("mizan.crypto.screening.screen_universe", <stub forcing "LTC" to
  Verdict.NON_COMPLIANT>)`; run a short `run_crypto_backtest`; assert `"LTC"` appears in
  `excluded_tickers`, is never a key of any `DailySnapshot.holdings`, and
  `EqualWeightStrategy.select`'s own weight (`1.0 / len(compliant_tickers)`) reflects the smaller,
  13-member `compliant_tickers` set it was actually given.
- `test_compliant_universe_is_read_fresh_not_cached`: call `_compliant_universe_tickers` twice with
  two different `fiqh_params` values across which a monkeypatched `screen_universe` returns a
  different result each time; assert the two calls' results differ accordingly (§Red-team R2).

### B3. Universe-lock test
**File:** `tests/test_crypto_backtest.py` (extend).
- `test_run_crypto_backtest_has_no_caller_supplied_universe_parameter`:
  `inspect.signature(run_crypto_backtest).parameters` contains no key named `tickers` or `universe`.

### B4. Full equal-weight baseline integration test
**File:** `tests/test_crypto_backtest_integration.py` (new).
- In-memory DuckDB (`duckdb.connect(":memory:")`), `ensure_schema`; seed synthetic daily
  `CandleBar`s (via `upsert_candles`) for three `CRYPTO_UNIVERSE` tickers (e.g. `BTC`, `ETH`, `LTC`)
  across a 65-day window at a constant, known price per ticker (simplifies the expected-weight
  arithmetic) with `interval_days=30` (so the window covers exactly 3 rebalances: day 0, day 30,
  day 60).
- `test_baseline_run_is_labelled_and_rebalances_on_schedule`: `strategy_label == "baseline"`;
  `rebalance_dates` has exactly 3 elements matching `generate_crypto_rebalance_dates`'s own output for
  the same window; `daily_snapshots` has exactly as many elements as `_resolve_candle_dates` returns.
- `test_baseline_run_ends_up_equal_weighted_across_the_three_tickers`: at the final snapshot, each
  held ticker's value share of `portfolio_value` is within a small tolerance of `1/3`.
- `test_costs_make_the_baseline_run_strictly_worse_than_a_frictionless_equivalent`: run the same
  scenario twice, once with `cost_params=DEFAULT_BACKTEST_COST_PARAMS` and once with a
  test-local monkeypatch forcing `apply_allocation_with_costs` to delegate to the zero-cost
  `mizan.backtest.portfolio.apply_allocation` directly (never constructing a literal
  `BacktestCostParams(taker_fee_rate=0.0, ...)`, which §A2 already forbids); assert the final
  `portfolio_value` with real costs is strictly lower.
- `test_boot_check_still_passes_after_a_full_baseline_run`: call
  `mizan.config.boot_check.check_all()` after a `run_crypto_backtest` call in the same test.

### B5. Documentation
- `docs/crypto/ARCHITECTURE.md` (edit, additive paragraph): the new parallel
  `mizan/crypto/backtest.py` module, why `mizan/backtest/portfolio.py`/`strategy.py` are reused
  as-is while `clock.py`/`compliance_state.py` are not (§A1), and that costs are baked into the
  per-leg execution price rather than deducted separately (§A4).
- `docs/crypto/PHASE_4_SPEC.md`: commit this spec as the governing document, matching the Phase 1/2/3
  precedent — this exact gap (the governing spec copy being forgotten) recurred in both Phase 2 and
  Phase 3 and had to be backfilled; `tests/test_phase1_scope.py` already has a
  `test_phase2_governing_spec_copy_exists_on_disk`-shaped test for Phase 2 — add its Phase 4 sibling
  in this same turn, in Part A's own A7 smoke tests if convenient, not deferred to a future backfill.
- `README.md`: one added sentence noting the baseline equal-weight backtest with its configurable
  fee/slippage cost model now exists, not yet wired to a CLI verb (Phase 6).

### B6. No forbidden code built (continuity of PHASE_1_SPEC.md §A6/B6, PHASE_2_SPEC.md §B7,
PHASE_3_SPEC.md A0.10/B5)
**File:** `tests/test_phase1_scope.py` (extend).
- `test_crypto_backtest_module_has_no_network_capability`: source-grep `mizan/crypto/backtest.py` for
  `httpx`/`socket` — neither appears. **Unlike `mizan/crypto/screening.py`, `duckdb` is explicitly
  permitted** in this file (it reads the local `candles` store) — do not reuse Phase 3's
  no-`duckdb` assertion verbatim here; state the distinction in the test's own docstring so a future
  reader does not mistake the omission for an oversight.
- `test_phase4_governing_spec_copy_exists_on_disk`: mirrors the existing Phase 2 sibling test.

**Part B done when:** all Part-A + Part-B tests pass, `mypy --strict`/`ruff` clean,
`mizan-boot-check` still exits 0, `run_crypto_backtest` produces a `"baseline"`-labelled,
cost-applied, equal-weight result over the compliant subset of the locked 14-token universe, and the
stated `docs/`/README files are updated/committed.

## Acceptance-criteria mapping (Phase 4)
| AC | Satisfied by | Concrete check |
|----|--------------|----------------|
| 5 — equal-weight long-only buy-and-hold, periodic rebalance, labelled "baseline" | A3, A6, B1, B4 | `tests/test_crypto_backtest_integration.py::test_baseline_run_is_labelled_and_rebalances_on_schedule` |
| 6 — 0.6% taker fee / 0.05% slippage defaults, both overridable, never zero | A2, A4, A7, B4 | `tests/test_crypto_backtest.py::test_apply_allocation_with_costs_*`; `BacktestCostParams(taker_fee_rate=0.0)` raising `ValidationError` |
| 1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13, 14, 15 (doc) | Phases 1, 2, 3, 5, 6 | Not in Phase 4 scope. |

## Documentation sources
No new external research was required for this phase. The baseline design (equal-weight, periodic
rebalance, per-leg taker fee plus slippage applied over a continuous clock) follows the conventions
already recorded in this run's own research digest
(`runs/42cd206f-79c0-42db-87c0-3168716066ea/spec/context.md` §"Research digest" and
`runs/42cd206f-79c0-42db-87c0-3168716066ea/research/report.md` §"Equal-weight buy-and-hold with
periodic rebalance and realistic costs"): costs are applied per leg at every rebalance (both the
initial buy-in and every subsequent trade), never only at entry. No new technical-source dependency —
`duckdb`'s transaction/query semantics for this phase are already covered by
`docs/modernization_log.md` and Phase 3's own A0.13 re-verification.

## Out of scope for this phase
- Any CLI verb for the crypto backtest or the single end-to-end pipeline command (Phase 6);
  `run_crypto_backtest` is called directly by tests in this phase, not by `mizan/cli/main.py`.
- The HTML report (Phase 6) — `CryptoBacktestResult` is a typed payload only, not rendered anywhere.
- The signal-adapter seam and validation gate (Phase 5); `Strategy` stays the only pluggable
  interface, and `EqualWeightStrategy` stays the only concrete implementation used by this phase's
  own tests.
- Any yield/staking/lending/dividend/split modelling (permanently out of scope per the locked PRD;
  crypto candles carry no adjustment facts at all, unlike equity's `price_bars`).
- A flip→grace→divest compliance-state machine for crypto holdings — not needed (§A1) because the
  classification map is static within one backtest run; re-litigating this decision is out of scope.
- Re-deriving or contesting any fiqh register value (cited, not contested, matching the project's
  standing rule) — this phase only *spends* `CRYPTO_FIQH_PARAMS`/`screen_universe()`'s outputs.
- Modifying `mizan/backtest/portfolio.py`, `strategy.py`, `clock.py`, or `compliance_state.py` in any
  way — all four stay byte-for-byte as Phase 1–3 (equity-parked or already-crypto-reused) left them.
- Decimal/rounding discipline for fee/slippage accumulation (flagged, not acted on, by Phase 1's own
  "Noted, no action" S-item) — `float` remains the quantity/price type throughout this phase too.

## Spec assumptions
Gaps found while writing this spec were resolved as follows (nobody was asked):
- "Periodic rebalance... defaults to monthly, exposed as a config parameter" (baby-prd's own risky
  assumption) is read as a fixed `interval_days=30` cadence, a plain `timedelta` offset over the
  continuous 24/7 clock — not a calendar-month-boundary snap like equity's hardcoded quarterly months
  — because crypto's clock has no notion of a calendar month being structurally special the way
  equity's `_REBALANCE_MONTHS` constant encodes a quarter boundary.
- "Costs never zero by default" (PRD Constraints) plus AC 6's "a test confirms neither defaults to
  zero" is read as a **structural** ban on a zero rate, not merely a non-zero default a caller could
  still override away: `Field(gt=0.0)` on both `BacktestCostParams` fields. A caller remains free to
  override either rate to any other positive value; only the specific value `0.0` is unrepresentable,
  the same reasoning `AllocationInstruction`'s weight validator and `Portfolio.cash`'s non-negativity
  already apply to "a short position"/"a margin loan" — a strategy or caller cannot construct the one
  forbidden state even by accident.
- `mizan/backtest/portfolio.py` and `mizan/backtest/strategy.py` are reused **unmodified**;
  `mizan/backtest/clock.py` and `mizan/backtest/compliance_state.py` are **not** reused — a new,
  parallel `mizan/crypto/backtest.py` is built instead (§A1's rationale in full).
- `screen_universe()` is called once per `run_crypto_backtest` call, before the loop starts, not
  re-screened at every rebalance — crypto's classification map (Phase 3) and a single call's
  `fiqh_params` value are both fixed for the duration of one backtest run, so there is nothing for a
  per-rebalance re-screen to ever observe changing; a caller wanting to compare two register
  configurations calls `run_crypto_backtest` twice with different `fiqh_params`, exactly as Phase 3's
  own tests already do for `screen_universe`.
- `run_crypto_backtest` always trades the locked `CRYPTO_UNIVERSE`, filtered through
  `screen_universe()` — it takes no `tickers`/`universe` parameter, matching "Universe of exactly 14
  tokens" being a locked constant, not a caller-selectable input (equity's `run_backtest`, by
  contrast, legitimately takes an arbitrary `tickers` set, since equity has no analogous locked
  universe).
- Costs are baked into the per-leg execution price before calling the reused, unmodified
  `apply_allocation`, rather than deducted from cash in a second step afterward — this keeps every
  one of `apply_allocation`'s own non-negativity/no-margin guarantees intact with zero changes to
  that function (§A4's full rationale).
- A traded ticker's buy/sell direction is determined by comparing `target_value` against
  `current_value` at the **unadjusted** quoted price, before the slippage/fee-adjusted execution
  price is computed — a negligible, accepted simplification for the sign-of-trade decision only; it
  cannot itself bias the backtest's realism, since the executed price (where the realism matters) is
  still fully cost-adjusted.
- `mizan/crypto/backtest.py` reads `candles` directly via its own private SQL helpers
  (`_resolve_candle_dates`/`_resolve_day_closes`), the same way equity's `mizan/backtest/clock.py`
  reads `price_bars` directly rather than going through a shared query layer in `mizan/data/db.py` —
  matching established precedent rather than inventing a new indirection.

## Implications
Second-order consequences found by review of this spec. This section only adds to the spec; the
locked PRD is unchanged.

### Additional acceptance criteria
S6. A test (source-grep, same technique as the existing scope guards) asserts
`mizan.backtest.portfolio.apply_allocation` is referenced in `mizan/crypto/backtest.py` **only**
from inside `apply_allocation_with_costs`'s own body — no second call site anywhere in the module
bypasses the cost wrapper. _(correctness: A4 makes `apply_allocation_with_costs` the sole
cost-applying entry point by construction today, but nothing stops a future edit to
`run_crypto_backtest` from calling the bare, zero-cost `apply_allocation` directly for convenience,
silently reintroducing a free-trade path with a fully green test suite.)_

## Red-team findings
Weaknesses found by an adversarial review of this spec before it is built. This section only adds to
the spec; the locked PRD is unchanged.

### Additional acceptance criteria
R1. A test constructs a scenario where `target_weights` sums to exactly `1.0` (fully invested, no
cash buffer) and asserts `apply_allocation_with_costs` still returns a valid `Portfolio` with
`cash == 0.0` (never negative) even after fees/slippage are baked into the execution price.
_(high, correctness: A4's design claims costs-baked-into-price inherits `apply_allocation`'s
non-negativity guarantee "unmodified," but this is only true if the fee-adjusted execution price
always produces a `target_quantity` that costs strictly less than or equal to the cash available —
untested, it is exactly the kind of boundary a 100%-allocated `EqualWeightStrategy` run will hit on
its very first rebalance.)_
R2. A test proves `_compliant_universe_tickers` is read fresh on every `run_crypto_backtest` call,
never memoized at import time or across calls within one process (§B2's second test).
_(medium, maintenance: Phase 3's own R8 finding made exactly this same "read fresh, never cache" point
about `screen_token` reading `.value` rather than `.register_id`; the same discipline needs its own
proof at this phase's new call site, or a future caching "optimization" added for backtest-loop
performance would silently freeze a run's compliant set at whatever `fiqh_params` was first seen.)_
