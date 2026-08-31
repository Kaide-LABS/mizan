# COMPREHENSION.md — Mizan

Written after Phase 6 ("Purification Engine — side-ledger") was reviewed and approved.
Sections 1–6 below describe the repository as it exists right now — Phase 1 ("Foundation & Config"),
Phase 2 ("Ingestion & Raw Cache"), Phase 3 ("Normalization & DuckDB Store"), Phase 4 ("Screening
Engine"), Phase 5 ("Backtest Engine & Compliance-Flip State Machine"), and Phase 6 combined —
grounded in the code read directly this pass, not in what any spec or prior handoff claimed. The
Phase Log at the bottom is append-only; Phase 1's through Phase 5's entries are preserved untouched
below the new Phase 6 entry.

---

## 1. Plain-language walkthrough

Mizan is a personal research tool for a single person who wants to test long-only stock-trading
strategies that follow Islamic finance rules ("halal" or "Shariah-compliant" investing), using real
historical US stock data. It is not a live trading system — no real money ever moves through it. It
is a sandbox for learning whether a rule-respecting strategy would have worked.

The core tension the whole project is built around: which Islamic finance rules are truly settled
(no company may profit mainly from things like alcohol, gambling, conventional interest-based
banking, and so on), and which rules are genuinely disputed even among qualified scholars (exactly
how do you measure "how much debt is too much debt," expressed as a percentage of what?). The
project's design insists on keeping these two categories visibly separate at all times: settled
rules are locked in stone and cannot be changed by anyone running the software; disputed rules are
left as clearly labeled, adjustable settings, each one stamped "not yet confirmed by a scholar,"
with an honest note about exactly what is uncertain.

Phase 1 built the foundation everything else stands on: the list of seven settled rules, the list of
eleven disputed judgment calls (each with its best current guess, a citation, and an honest note
about what's unclear), a "boot check" that refuses to even start the program if any of that
foundation looks wrong, and a handful of shared building-block definitions.

Phase 2 taught Mizan how to go out and pull real financial data for a given stock ticker from two
sources — the US government's own company-filings database (SEC EDGAR, for company fundamentals
like revenue and debt) and a commercial market-data provider (Tiingo, for daily stock prices and
dividends) — and to save every single response it gets to a local folder on disk before doing
anything else with it.

Phase 3 turned those saved-but-still-raw files into something a computer program can actually query
and trust — one table for company financial facts, one table for daily stock prices, both loaded
into a real local database (DuckDB) with a duplicate guard and a closed unit-of-measurement
allow-list built directly into the loading step.

Phase 4 gave Mizan its first working compliance verdict. Given a ticker symbol and a date, `mizan
screen` runs a business-activity check (does the company's registered industry code fall into a
disqualifying bucket?) followed, if that passes, by a financial-ratio check (how much interest-
bearing debt/investment does the company carry, how much of its revenue is non-halal income —
each against a configurable percentage threshold). The result is one of three verdicts — Pure,
Mixed, or Non-compliant — always with a full, human-readable trace of exactly which check drove it.

**Phase 5 is where Mizan stops answering "is this company halal right now?" and starts answering
"what would have happened if I'd actually held a portfolio of halal stocks over time?"** Given a
starting cash amount and a strategy (a rule for picking which
compliant stocks to hold, out of a candidate list the operator supplies), the new backtest engine
steps through calendar time one quarter at a time. At every quarterly boundary it does the same
thing `mizan screen` would do for a single ticker on a single day — it re-runs the real screening
engine, fresh, against every currently-held stock and every candidate stock in the universe. If a
held stock's fresh verdict comes back non-compliant when it was compliant before, the engine does
NOT sell it immediately. This is the project's signature mechanic, the whole reason Phase 5 exists
rather than a generic backtester: a stock that flips out of compliance enters a one-rebalance-long
"grace period" — it is held, completely untouched (same share count, no trades against it, no cash
movement), through exactly one more quarterly rebalance, and only forced out of the portfolio
("divested") at the rebalance after that. This mirrors how a real Islamic fund manager would
actually behave — not panic-selling the instant a company's numbers drift, but giving a fixed,
short, config-controlled grace window before acting. Along the way, the engine also tracks real
stock splits (adjusting share counts, never prices) and real cash dividends (credited straight to
cash, never reinvested automatically) day by day. Cash itself never earns interest, ever, by
design — a permanent Phase 1 rule, not a Phase 5 choice, and Phase 5's own portfolio math reads that
rule from the same single source of truth rather than re-asserting it.

Two things worth being explicit about, in the same honesty register every prior phase's walkthrough
used. First, the only "strategy" that ships is the simplest possible one — split money equally
across every compliant stock, all cash otherwise — presented explicitly as a reference
implementation and testing vehicle, not as real investment advice; building an actual research
strategy on top of this substrate is the owner's own future work. Second, and most importantly:
**this still only runs against the same small set of invented, clearly-fake test tickers (`ZZPURE01`,
`ZZFLIP01`, etc.) Phase 4 and 5 built — the real ~100-ticker universe of actual companies a person
would want to backtest against still does not exist anywhere in this repository.** Phase 5 proves the
mechanism (the quarterly clock, the grace period, the re-screening) works correctly against
synthetic data engineered to exercise it; it does not, and was never supposed to, produce a
trustworthy backtest result for any real stock.

**Phase 6 is where Mizan stops just tracking gross portfolio value and
starts honestly tracking the money that was never really "clean" in the first place.** Some of the
stocks the backtest holds get a "compliant, but with a little non-halal income mixed in" verdict —
Mixed, not Pure. When a Mixed stock pays a dividend, part of that dividend cash came from the
non-halal sliver of the company's business. Phase 6 does not remove that money from the investor's
returns — it never touches the portfolio's actual cash or value at all — instead it calculates
exactly how much of each dividend is impure (the company's own non-halal-income percentage, applied
to that specific dividend payment) and adds it to a separate running total, a "purification
liability," tracked entirely off to the side. In real Islamic-finance practice this liability is the
amount a person would be expected to donate to charity, since AAOIFI's own rule is that non-halal
income must never be counted as part of an investor's real return. **Mizan computes and tracks this
number; it does not, and was never meant to, actually donate anything anywhere — there is no
charity-transfer feature, no payment integration, nothing beyond an honest, auditable running total.**

Because the liability is tracked separately rather than subtracted from the real numbers, the
backtest can now report two different bottom lines instead of one: the "gross return" (what you'd
have earned, full stop, ignoring purification entirely) and the "net-of-purification return" (gross
return minus the running liability) — so the cost of staying religiously honest is a visible number
of its own, never a silent haircut baked invisibly into the portfolio's reported value.

There is also a second, less obvious case Phase 6 handles: what about a stock that gets kicked out of
the portfolio entirely because it stopped being halal (a "divestment")? Recall from Phase 5 that a
flipped stock isn't sold immediately — it survives one more full rebalance period, untouched, before
being forced out. During that grace window, the stock's price can move, and any price gain it made
while it was already known to be non-compliant is itself something a scrupulous investor might not
want to keep. Phase 6, when this feature is explicitly turned on (it ships switched off by default,
since there's no settled scholarly formula for exactly how to handle this), tracks that price gain —
from the day the stock flipped to the day it was finally sold — as a second kind of amount that would
need to be purified, using the simplest defensible rule available: whatever the price went up by
during that exact window, floored at zero (a price decline produces nothing to purify, since there's
no income in a loss).

What exists after Phase 6: the settled/disputed rule registry from Phase 1; the data-pulling
pipeline from Phase 2; the typed local database from Phase 3; the working compliance screen from
Phase 4; the working portfolio simulator with its flip-grace-divest discipline from Phase 5; and now,
new this phase, a purification side-ledger that turns every Mixed-verdict dividend and (optionally)
every forced divestment's price gain into an honestly-tracked liability, reported alongside — never
folded silently into — the backtest's own gross portfolio value. Still no report or chart (that
remains Phase 7's job) — Phase 6 only computes the numbers and prints a plain-text summary to the
terminal.

## 2. Architecture walkthrough

Everything below is a real file in the repository, read directly this pass.

```
mizan/
├── __init__.py                  # empty — marks mizan as a Python package
├── py.typed                     # empty marker file so type-checkers treat the package as typed
├── config/
│   ├── __init__.py               # empty
│   ├── invariants.py             # the 7 settled, non-negotiable rules (Invariants class + INVARIANTS singleton)
│   ├── fiqh_params.py            # the 11-row disputed-judgment-call register (FiqhParams + FIQH_PARAMS singleton)
│   └── boot_check.py             # startup checks that refuse to run if invariants.py or fiqh_params.py are broken
├── core/
│   ├── __init__.py               # empty
│   ├── base.py                   # MizanBaseModel — the one shared base every data model in the project must use
│   ├── verdict.py                # Verdict — the three-state pass/partial/fail screening outcome (definition ONLY)
│   └── caveats.py                # Caveat enum + ResultEnvelope — the mandatory warning-label wrapper for results
├── data/
│   ├── __init__.py                # empty
│   ├── models.py                  # raw wire-format row-shape schemas for EDGAR + Tiingo payloads (Phase 2)
│   ├── raw_cache.py               # shared cache-path / cache-hit / atomic-write / read helpers, both legs (Phase 2)
│   ├── ingest_edgar.py            # EDGAR client: rate limiter, header construction, CIK resolution, fetch fns (Phase 2)
│   ├── ingest_tiingo.py           # Tiingo client: request/symbol budget limiter, EOD fetch, anomaly scan (Phase 2)
│   ├── db.py                      # DuckDB connection + idempotent schema creation (Phase 3)
│   └── normalize.py               # typed row shapes + raw-cache-to-DuckDB mapping functions, incl. resolve_cik_offline (Phase 3)
├── screening/                      # the whole package is Phase 4's, untouched by Phase 5's or Phase 6's diff
│   ├── __init__.py                 # empty, package marker only
│   ├── business_activity.py        # SIC-code first-pass tier classifier + pluggable, ships-empty override map
│   ├── financial_ratios.py         # the 30/30/5 ratio arithmetic, pure functions over already-resolved floats
│   └── verdict.py                  # screen(), the canonical entry point — Phase 5/6 both import and call this, neither edits it
├── backtest/                       # Phase 5's package — untouched by Phase 6's diff (confirmed: none of
│   │                                #  these five files appears in `git diff 9e989eb..9750a18 --stat`)
│   ├── __init__.py                 # empty, package marker only
│   ├── portfolio.py                # Holding/Portfolio models, valuation, split/dividend bookkeeping,
│   │                                #  INVARIANTS.cash_yield read site (Phase 5)
│   ├── strategy.py                 # Strategy Protocol + AllocationInstruction (Phase 5)
│   ├── compliance_state.py         # the flip→grace→divest state machine + DivestmentEvent/DividendEvent —
│   │                                #  Phase 6 imports ComplianceStateRecord/DividendEvent from here, never edits it (Phase 5)
│   └── clock.py                    # generate_rebalance_dates, step(), rebalance(), run_backtest() — Phase 6
│                                    #  imports BacktestResult/DailySnapshot from here, never edits it (Phase 5);
│                                    #  `purification_ledger: dict[str, object] | None = None` field declaration
│                                    #  is byte-for-byte unchanged this phase, confirmed by direct diff read
├── purification/                   # NEW this phase — the whole package is new
│   ├── __init__.py                 # NEW — empty, package marker only (mizan/backtest/__init__.py precedent)
│   ├── ledger.py                   # NEW — DividendPurificationEntry/PurificationLedger models,
│   │                                #        purify_dividend, purify_backtest_result — Fork A trigger +
│   │                                #        Fork B side-ledger accrual (§3.1/§3.2/§4.1/§6a/§6c/§6d)
│   └── attribution.py              # NEW — DivestmentPurificationEntry model,
│                                    #        compute_divestment_attribution — Fork C forced-divestment
│                                    #        price-appreciation attribution (§3.3/§4.2/§6b/§6c)
└── cli/
    ├── __init__.py                # empty
    ├── main.py                    # `mizan` console-script entrypoint — boot-check-first dispatcher
    │                               #  (untouched by Phase 6's diff — confirmed absent from the diff stat)
    ├── ingest.py                  # the `ingest` subcommand (Phase 2, untouched this phase)
    ├── normalize.py               # the `normalize` subcommand (Phase 3, untouched this phase)
    ├── screen.py                  # the `screen` subcommand (Phase 4, untouched this phase)
    └── backtest.py                # the `backtest` subcommand (Phase 5) — MODIFIED this phase, additively:
                                    #  purification wired in as a post-processing pass (§4.3 below)
tests/
├── __init__.py                   # empty
├── test_invariants.py            # proves the boot check actually rejects a broken settled-rule config
├── test_fiqh_params.py           # proves the 11-row register is complete, honest, and structurally sound
├── test_core_types.py            # proves the shared base model, Verdict, and Caveat/ResultEnvelope behave as documented
├── test_data_models.py           # proves every mizan/data/models.py schema parses/rejects as documented
├── test_raw_cache.py             # proves cache_path/is_cached/write_raw_json/read_raw_json behave as documented
├── test_ingest_edgar.py          # rate limiter timing, header contract, CIK resolution, HALT paths
├── test_ingest_tiingo.py         # budget throttling, symbol-log drift, anomaly scan, token handling
├── test_cli_ingest.py            # CLI arg parsing, boot-gate-first dispatch, per-ticker HALT/continue behaviour
├── test_data_db.py               # schema idempotency, PRIMARY KEY enforcement, single-writer lock behaviour
├── test_data_normalize.py        # unit-rejection, duplicate-guard, idempotent replay, column contract
├── test_cli_normalize.py         # boot-gate-first behaviour, offline-only dispatch, exit codes
├── fixtures/
│   ├── __init__.py                 # package marker
│   └── synthetic_universe.py       # MODIFIED this phase (additive only) — Phase 5's thirteen SYNTHETIC
│                                    #  fixture tickers PLUS three new tickers added this phase:
│                                    #  `ZZMIXED_RATIODRIFT01`, `ZZPURE_DIV01`, `ZZDIVEST_APPREC01` (§3/§4 below)
├── test_screening_business_activity.py  # Phase 4, untouched
├── test_screening_financial_ratios.py   # Phase 4, untouched
├── test_screening_verdict.py             # Phase 4, untouched
├── test_cli_screen.py                    # Phase 4, untouched
├── test_backtest_portfolio.py            # Phase 5, untouched
├── test_backtest_strategy.py             # Phase 5, untouched
├── test_backtest_compliance_state.py     # Phase 5, untouched
├── test_backtest_clock.py                # Phase 5, untouched
├── test_cli_backtest.py                  # Phase 5's file — MODIFIED this phase (additive only): one new
│                                          #  case, `test_run_prints_a_purified_dividend_line_for_a_mixed_
│                                          #  dividend`, proving the CLI's new purification-summary stdout lines
├── test_purification_ledger.py           # NEW this phase — 17 tests: the ratio-drift anti-undercount
│                                          #  property, Pure-verdict zero-entry behaviour, the grace-window
│                                          #  last-Mixed-ratio fallback, the Fork A/C `purify_capital_gains`
│                                          #  gate, gross-vs-net-of-purification distinctness, lossless
│                                          #  round-trip, "only purification_ledger changes" isolation, the
│                                          #  dividend reconciliation pass, caller-`con`/`cache_dir` reuse,
│                                          #  MizanBaseModel inheritance, and the four boundary/import greps
│                                          #  restated as tests (no LLM import, no DB write, no `duckdb.connect`,
│                                          #  no boundary-crossing word, no pandas/matplotlib/pyarrow import)
└── test_purification_attribution.py      # NEW this phase — 7 tests: purified-amount arithmetic, the
                                           #  price-decline-floors-at-zero rule, a flat-price zero-amount
                                           #  entry (recorded, not omitted), the mismatched-dates
                                           #  AssertionError guard, the flip<=divest model_validator in both
                                           #  directions, MizanBaseModel inheritance
.env.example                       # TIINGO_API_TOKEN placeholder template, never a real credential
pyproject.toml                    # project metadata, exact dependency version pins, mypy/ruff/pytest config, CLI entry points (UNCHANGED this phase — confirmed absent from the diff stat)
docs/modernization_log.md         # a running log of exactly which external tool/library versions and API contracts were verified and when (UNCHANGED this phase — Phase 6 verifies no new external-API field, per PHASE_6_SPEC.md §2.4)
.gitignore                        # unchanged this phase
PHASE_5_SPEC.md                   # the Phase 5 build contract (1070 lines), untouched this phase
PHASE_6_SPEC.md                   # NEW this phase — the Phase 6 build contract (886 lines)
```

**How the Phase 6 pieces connect, confirmed by direct read of every file this pass:**

- **`mizan/purification/ledger.py`** (382 lines) defines two frozen `MizanBaseModel` subclasses —
  `DividendPurificationEntry` (`ticker`, `cik`, `ex_date`, `ratio_used: float = Field(ge=0.0)`,
  `ratio_as_of_date`, `dividend_cash_received: float = Field(ge=0.0)`, `purified_amount: float =
  Field(ge=0.0)`) and `PurificationLedger` (`dividend_entries`, `divestment_entries` — the latter
  imported from `attribution.py`, a one-way, non-circular import — `purification_liability: float =
  Field(ge=0.0)`, `gross_return: float`, `net_of_purification_return: float`) — plus the module's
  three private helpers (`_pinned_verdict_observation`, `_most_recent_prior_mixed_observation`,
  `_ratio_from_screen`, `_compute_returns`) and its two public functions. `purify_dividend` (lines
  187–282) pins the `VerdictObservation` in `compliance_state.verdict_history` with the largest
  `as_of_date <= ex_date`, asserts it matches `DividendEvent.verdict_at_ex_date` (an `AssertionError`
  otherwise — a Phase-6-mis-derived-the-pin guard, not a Phase-5-correctness check), and branches
  three ways on the pinned verdict: `PURE` returns `None` (no entry at all); `MIXED` re-invokes
  `mizan.screening.verdict.screen(ticker, ratio_as_of_date, ...)`, reads `non_permissible_income_
  ratio.actual_value` off the returned `ScreeningVerdict.reason_trace`, and returns an entry with
  `purified_amount = ratio_used * dividend_event.cash_received`; `NON_COMPLIANT` (a dividend paid
  during a ticker's grace window) walks `verdict_history` backwards to the most recent strictly-prior
  `MIXED` observation and re-derives its ratio instead, or returns `None` if that prior observation
  was `PURE`. `purify_backtest_result` (lines 306–382) is the module's canonical entry point: loops
  `result.dividend_events` calling `purify_dividend`, loops `result.divestment_events` calling
  `compute_divestment_attribution` only `if fiqh_params.purify_capital_gains.value`, sums both entry
  sets into `purification_liability`, computes `gross_return`/`net_of_purification_return` via
  `_compute_returns` (which returns `(0.0, 0.0)` for an empty `daily_snapshots`, §6 below), and
  returns `result.model_copy(update={"purification_ledger": ledger.model_dump()})` — the original
  `BacktestResult` is never mutated in place.
- **`mizan/purification/attribution.py`** (160 lines) defines `DivestmentPurificationEntry` (`ticker`,
  `cik`, `flip_date`, `divest_date`, `quantity_liquidated: float = Field(ge=0.0)`, `price_at_flip:
  float = Field(ge=0.0)`, `price_at_divest: float = Field(ge=0.0)`, `purified_amount: float =
  Field(ge=0.0)`), whose `model_validator(mode="after")` raises `ValueError` if `flip_date >
  divest_date`. `compute_divestment_attribution` (lines 95–160) asserts `compliance_states[event.
  ticker].flip_date == event.flip_date and .divest_date == event.divest_date` (`AssertionError`
  otherwise), finds the `DailySnapshot` with `as_of_date == event.flip_date` and reads
  `holdings[event.ticker]` as `quantity_liquidated` (never re-queried from a live `Portfolio`, which
  this module never holds a reference to), queries `price_bars.raw_close` for both `flip_date` and
  `divest_date` via a private `_raw_close_on` helper (one `SELECT ... WHERE ticker = ? AND
  trade_date = ?` per call, raising a plain `LookupError` — not defaulting to `0.0` — if no row
  exists), and computes `purified_amount = max(0.0, quantity_liquidated * (price_at_divest -
  price_at_flip))`.
- **`mizan/cli/backtest.py`** gained two new imports (`from mizan.config.fiqh_params import
  FIQH_PARAMS`; `from mizan.purification.ledger import PurificationLedger, purify_backtest_result`)
  and, inside `run()`'s existing `try` block (still inside the `with db.connect(...) as con:`
  context manager, `con` still open and still read-only), the `BacktestResult.model_validate(...)`
  call PLUS a new `purify_backtest_result(result, con=con, cache_dir=args.cache_dir,
  overrides=overrides, fiqh_params=FIQH_PARAMS)` call — reusing the exact same `con`/`args.cache_dir`/
  `overrides` local variables `run_backtest(...)` was already called with a few lines above. After
  the `with` block exits, six new `print(...)` lines are appended after the existing
  DIVESTED/DIVIDENDS summary loops: purification liability, gross return, net-of-purification return,
  one `PURIFIED DIVIDEND` line per `ledger.dividend_entries`, and one `PURIFIED DIVIDEND` line per
  `ledger.divestment_entries`. Every pre-existing line in the file is byte-for-byte unchanged
  (confirmed by direct diff read) — this is a strictly additive modification, exactly as
  `PHASE_6_SPEC.md` §1 specified.
- **`tests/fixtures/synthetic_universe.py`** gained one new defaulted field on `PriceBarFixture`
  (`div_cash: float = 0.0`) and three new tickers appended to `ALL_SYNTHETIC_TICKERS`:
  `ZZMIXED_RATIODRIFT01` (CIK `9990000014` — a Mixed-verdict ticker whose
  `non_permissible_income_ratio` drifts 2% → 4% between rebalance 1 and rebalance 2 via the same
  two-facts-same-tag-different-`filed`-dates mechanism `ZZLOOKAHEAD01`/`ZZFLIP01` already established,
  now applied to `InvestmentIncomeInterest`; carries two nonzero `div_cash` price-bar days straddling
  the ratio-drift boundary, one purified at 2%, one at 4%), `ZZPURE_DIV01` (CIK `9990000016` — a
  Pure-verdict ticker distinct from the existing, unmodified `ZZPURE01`, that pays one dividend, used
  to prove a Pure dividend produces zero ledger entries, not a zero-amount one), and
  `ZZDIVEST_APPREC01` (CIK `9990000015` — structurally identical to `ZZFLIP01`'s debt-fact-drift flip/
  divest mechanism, but with `raw_close` rising `100.0 → 130.0` across the non-compliant window,
  giving Fork C a genuine nonzero appreciation to attribute; `ZZFLIP01` itself is untouched, its own
  four price bars still flat at `100.0`). The one line inside `load_into_duckdb` that previously
  hardcoded `div_cash` as a literal `0.0` in every inserted `price_bars` row now reads `bar.div_cash`
  instead — the single, minimal, additive change needed for the new fixtures' nonzero dividend days to
  actually reach the database Phase 4/5's own already-approved fixture rows are otherwise untouched by
  (confirmed: every Phase 4/5 fixture's `div_cash` stays `0.0`, since `PriceBarFixture`'s new field
  defaults to `0.0` and none of their own definitions sets it).
- `pyproject.toml`, `docs/modernization_log.md`, and `.gitignore` are all unmodified by this phase —
  confirmed absent from the diff stat; Phase 6 adds zero new third-party dependencies and verifies no
  new external-API field beyond what Phase 5's own `docs/modernization_log.md` §6.2/§6.2b already
  logged (`price_bars.div_cash`/Tiingo's `divCash`, `price_bars.raw_close`).

**Phase 1–5 architecture, carried forward unchanged (re-confirmed this pass by diff, not re-read file
by file since the owning code is untouched):** `mizan/config/`, `mizan/core/`, `mizan/data/`,
`mizan/screening/`, and every file under `mizan/backtest/` do not appear in `git diff
9e989eb..9750a18 --stat` at all — Phase 6 is a read-only consumer of `screen()`, `BacktestResult`,
`ComplianceStateRecord`, and the Phase 1 config singletons, exactly the same posture Phase 5 held
toward Phase 4's `screen()` and Phase 3's `db.connect()`.

**Phase 5 architecture detail, carried forward for reference below (files untouched this phase, so
the description Phase 5's own comprehension pass gave remains accurate):**

- **`mizan/backtest/portfolio.py`** (159 lines) defines `Holding` (`ticker: str`, `quantity: float =
  Field(ge=0.0)` — negative quantity, i.e. a short position, is rejected at construction, not by a
  runtime `if`) and `Portfolio` (`cash: float = Field(ge=0.0)`, `holdings: dict[str, Holding]`), both
  `MizanBaseModel` subclasses (frozen — every function returns a new object rather than mutating).
  `apply_cash_yield` multiplies cash by `(1.0 + INVARIANTS.cash_yield)`, reading `INVARIANTS`
  directly inside the function body rather than accepting it as a parameter or hardcoding `0.0` a
  second time — a structural no-op today (`cash_yield` is permanently `0.0`) expressed as a genuine
  config read rather than an assumption. `apply_split(holding, split_factor)` multiplies `quantity`
  by `split_factor` (see §4 below for the verified direction). `mark_to_market` sums
  `cash + Σ(quantity × prices[ticker])` over caller-supplied `prices`, doing no DB I/O itself.
  `credit_dividend` adds `div_cash_per_share × quantity` to cash, a no-op (not an error) if the
  ticker isn't currently held. `apply_allocation(portfolio, instruction, prices)` computes each
  target ticker's `target_value = weight × mark_to_market(...)`, converts to a target quantity,
  liquidates any currently-held ticker absent from `instruction.target_weights`, and floors the
  resulting cash at `0.0` as a defensive guard against sub-cent floating-point noise (see §3 below).
- **`mizan/backtest/strategy.py`** (116 lines) defines `AllocationInstruction` (`target_weights:
  dict[str, float]`), whose own `model_validator` rejects any weight outside `[0.0, 1.0]` and any
  weight-sum above `1.0 + 1e-9` — making leverage and shorting structurally impossible at
  construction time, independent of `INVARIANTS`. `Strategy` is a `Protocol` with one method,
  `select(*, as_of_date, compliant_tickers: frozenset[str], portfolio: Portfolio) ->
  AllocationInstruction`. `StrategyContractViolationError` is the backstop raised if a `select()`
  implementation names a ticker outside `compliant_tickers`. `EqualWeightStrategy` is the one
  concrete, shipped implementation — equal-weights every compliant ticker, or all-cash if none are
  compliant — used by both this phase's own tests and the `backtest` CLI, explicitly not presented
  as a real research strategy.
- **`mizan/backtest/compliance_state.py`** (220 lines) defines `HoldingComplianceState` (a `StrEnum`:
  `HELD_COMPLIANT`, `HELD_NONCOMPLIANT_GRACE`, `DIVESTED`), `VerdictObservation`,
  `ComplianceStateRecord` (per-ticker: `state`, `flip_date`, `divest_date`,
  `grace_rebalances_remaining`, and the append-only `verdict_history`), `DivestmentEvent`, and
  `DividendEvent`. The pure function `transition(record, *, ticker, cik, as_of_date, new_verdict,
  fiqh_params=FIQH_PARAMS)` implements the state table (see §4 below) and is the single place the
  grace countdown and the "no un-flip edge" rule live.
- **`mizan/backtest/clock.py`** (422 lines) defines `DailySnapshot` and `BacktestResult` (the
  latter's `purification_ledger: dict[str, object] | None = None` field is a deliberate loose
  placeholder for Phase 6, always left `None` by Phase 5 itself). `generate_rebalance_dates(start,
  end)` is a pure function returning `start_date` plus the first day of every subsequent calendar-
  quarter-boundary month (`_REBALANCE_MONTHS = (1, 4, 7, 10)`, a module-level hardcoded tuple — see
  §3/§4 below for why this can never be made configurable). `step()` advances a portfolio one
  trading day with no trading and no re-screening (split adjustment + the cash-yield no-op only).
  `rebalance()` is where the flip/grace/divest mechanic and the strategy call actually happen (see
  §3 below for the frozen/workable partition this function implements). `run_backtest(*, tickers,
  start_date, end_date, initial_cash, strategy, con, cache_dir, overrides=None,
  fiqh_params=FIQH_PARAMS)` is the canonical entry point: iterates every real trading day present in
  `price_bars` for the given tickers, applying `step()` and dividend crediting every day and
  `rebalance()` on rebalance dates, and returns `ResultEnvelope(active_caveats=(Caveat.
  LOOK_AHEAD_BIAS, Caveat.SURVIVORSHIP_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION),
  payload=BacktestResult(...).model_dump())`. It imports `mizan.screening.verdict` as a module
  (`from mizan.screening import verdict as screening_verdict`), not as a bare `screen` name — see §3
  below for why this specific import shape is load-bearing, not stylistic.
- **`mizan/cli/backtest.py`** (130 lines) registers `backtest --ticker TICKER [--ticker TICKER ...]
  --start-date --end-date --initial-cash --db-path --cache-dir [--overrides-path]`. There is
  deliberately no `--rebalance-frequency` flag anywhere on this subcommand, mirroring
  `clock.py`'s own hardcoded `_REBALANCE_MONTHS`. `run()` opens one read-only DuckDB connection
  (`backtest` never writes to DuckDB), loads the override map, constructs `EqualWeightStrategy()`,
  calls `run_backtest`, and prints final portfolio value, every `DivestmentEvent`, and every
  ticker's total dividend cash received to stdout — catching the same per-ticker-shaped exceptions
  `mizan screen` catches (`CikResolutionError`/`SicResolutionError`/`NotNormalizedError`/
  `InsufficientDataError`), but at the whole-backtest level: one halting exception anywhere aborts
  the entire run rather than continuing with a partial universe, since a backtest's tickers are not
  independent of each other the way a screening batch's are.
- **`mizan/cli/main.py`** gained one new import (`from mizan.cli import backtest as backtest_cli`)
  and one new registration line (`backtest_cli.add_subparser(subparsers)`) — confirmed by reading the
  diff; `main()`'s boot-check-first dispatch is otherwise unchanged, so `mizan backtest` also halts
  before any simulation logic runs if the Phase 1 foundation is broken. `run_backtest` itself does
  not re-run the boot check — it relies on this centralized, already-existing gate running before
  any subcommand dispatches.
- **`tests/fixtures/synthetic_universe.py`** gained one new ticker, `ZZFLIP01` (CIK `9990000013`),
  appended to `ALL_SYNTHETIC_TICKERS` — nothing existing in the file was changed (confirmed: every
  Phase 4 ticker definition is byte-identical in this pass's read). `ZZFLIP01` carries two
  `LongTermDebtNoncurrent` facts under the same tag, filed on different dates (`0.0` debt filed
  2025-06-01; `50,000,000.0` debt filed 2026-02-01) plus four price bars on each 2026 calendar-
  quarter boundary — engineered so `screen(..., as_of_date=date(2026,1,1))` sees only the early
  (0.0-debt) fact and returns `Verdict.PURE`, while `screen()` at `2026-04-01` or any later date sees
  the second fact and returns `Verdict.NON_COMPLIANT` — a real, time-varying `screen()` result, not a
  fixture rigged to a single permanent verdict. This is the worked example `test_backtest_clock.py`
  runs its end-to-end flip→grace→divest assertions against.
- `pyproject.toml` is unmodified by this phase — confirmed absent from the diff stat; Phase 5 adds
  zero new third-party dependencies.
- `docs/modernization_log.md` gained one new dated (2026-08-31) entry, §6.2b, read in full this pass:
  a live re-fetch of Tiingo's own splits documentation resolving the one build-time verification item
  `PHASE_5_SPEC.md` §0.1 flagged rather than guessed — see §4 below.
- `.gitignore` gained one line (`.coverage`), added in the small standalone housekeeping commit
  `4559e0e` between Phase 4's comprehension pass and Phase 5's technical blueprint — not part of
  Phase 5's own implementation diff, noted here only for completeness since it appears in the
  `d70b29d..3f9ccc6` diff range this pass was asked to read.

## 3. Decisions and tradeoffs

**Carried forward from Phase 1 (still shipped, not overturned by any later phase):**

- `FiqhParam` remains generic (`FiqhParam[T]`), not a `bool | float | str` union.
- `check_invariants()` / `check_fiqh_register()` remain hand-written, field-by-field checks.
- `StrEnum` remains the pattern for every enum in the project, including Phase 5's new
  `HoldingComplianceState` — confirmed by direct read of its definition.

**Carried forward from Phase 2/3/4 (still shipped, not overturned by Phase 5 or Phase 6):**

- DuckDB's single-writer lock, the dedup-then-insert-with-backstop pattern, and the closed
  `RECOGNIZED_XBRL_UNITS` allow-list are all unaffected — `mizan/data/db.py` and
  `mizan/data/normalize.py` are both untouched by Phase 5's or Phase 6's diff.
- The Phase 2/3 `# noqa: N812` findings on the `_Date` alias remain exactly two files
  (`mizan/data/models.py`, `mizan/data/normalize.py`), plus the one Phase 4 added
  (`mizan/screening/verdict.py`) — confirmed this run: `grep -rn "noqa" mizan/` still surfaces
  exactly these three `# noqa: N812` hits (plus `models.py`'s unrelated `N815` wire-format
  suppressions). Neither Phase 5's nor Phase 6's new code (`mizan/backtest/`, `mizan/purification/`,
  `mizan/cli/backtest.py`) introduces **any** new `noqa` suppression anywhere.
- The real ~100-ticker universe and its hand-verified activity map still do not exist — restated
  prominently in §6 below, carried unchanged from Phase 4's own open item.

**Carried forward from Phase 5 (still shipped, not overturned by Phase 6 — re-confirmed this run
since no file under `mizan/backtest/` appears in `git diff 9e989eb..9750a18 --stat`):**

- **The frozen/workable portfolio partition — the mechanism that actually makes the grace period
  work, and the single most important design decision in this phase.** A naive implementation of
  "re-screen everything, then just hand the whole portfolio to the strategy and apply whatever it
  returns" would silently defeat the grace-period mechanic on its very first non-compliant
  rebalance: `Strategy.select()`'s own structural contract (§3.2) makes it *impossible* to name a
  non-compliant ticker in `AllocationInstruction.target_weights` (a conforming strategy is only ever
  handed `compliant_tickers`, which never includes a `NON_COMPLIANT` verdict), and
  `apply_allocation` fully liquidates any currently-held ticker that is *absent* from
  `target_weights`. Put those two true, individually-correct rules together naively and a stock that
  just flipped to non-compliant is both un-nameable by the strategy AND therefore immediately sold —
  at the very rebalance the flip is detected, one full grace period too early. `rebalance()`
  (`mizan/backtest/clock.py` lines 269–277, read directly this pass) avoids this by partitioning the
  post-divestment portfolio in two before ever consulting the strategy: every ticker currently in
  `HELD_NONCOMPLIANT_GRACE` goes into a **frozen** dict, held back entirely; everything else (cash +
  every other holding) becomes the **workable** portfolio actually shown to `strategy.select()` and
  passed through `apply_allocation`. The frozen holdings are merged back into the final portfolio
  completely untouched — same quantity, no cash flow — after the strategy has acted. **Tradeoff:**
  this makes `rebalance()` itself noticeably more complex than "screen, then delegate to strategy,
  then apply" would have been, and it means a grace-period holding is invisible to the strategy even
  as a candidate for the strategy's own risk logic (a strategy cannot, for example, choose to shrink
  a grace holding early) — but the alternative is a silent, structural violation of the state
  machine `MASTER_PRD.md` §7.3 itself specifies (a state diagram with no edge back out of
  `HELD_NONCOMPLIANT_GRACE` except via the grace countdown), which the shipped design gets right
  without weakening `apply_allocation`'s own liquidate-if-absent contract for any other ticker.
- **`mizan.screening.verdict` is imported as a module (`from mizan.screening import verdict as
  screening_verdict`), never as `from mizan.screening.verdict import screen`.** Confirmed by direct
  read of `clock.py`'s own top-of-file docstring and import block, and confirmed the reason is real
  by reading `test_backtest_clock.py`'s own call-counting test
  (`test_every_holding_is_rescreened_every_rebalance`, lines ~326–353): the test wraps
  `screening_verdict_module.screen` via `monkeypatch.setattr(screening_verdict_module, "screen",
  _counting_screen)` and asserts `call_count == len(universe) * len(rebalance_dates)`. Had
  `clock.py` imported the bare name `screen` at module load time, its own local reference would be
  bound to the original function object permanently — a later `monkeypatch.setattr` on the module's
  own attribute would never be visible to code that already holds the original object, and the test
  would silently under-count (or not detect a regression where re-screening is accidentally skipped
  for some holdings). **Tradeoff:** every call site inside `clock.py` is one token longer
  (`screening_verdict.screen(...)` vs. `screen(...)`) purely to keep this specific test meaningful —
  a small, deliberate verbosity cost paid for testability of the re-screen-everything guarantee,
  which is itself the guarantee arXiv:2608.12634's already-logged finding (boundary proximity
  predicts screen transitions) motivates.
- **`PHASE_5_SPEC.md` itself has a genuine, real gap this run found: it references "§6e" nine times
  (lines 31, 67, 97, 116, 307, 537, 945, 947, 1035) but the document contains no actual `## 6e` or
  `### 6e` section anywhere** (confirmed: `grep -n "^#.*6e"` against the full 1070-line file returns
  nothing). Every one of those nine references reads naturally as "see §6e for the worked
  fixture-ticker example," but there is nothing at that anchor to see. The executor therefore had to
  design the `ZZFLIP01` fixture (two same-tag facts filed on different dates, engineered to flip
  verdicts across a real `screen()` call at different `as_of_date`s — see §2/§4) from the spec's
  surrounding prose and cross-references alone, without a literal table or worked-example block to
  copy. **How the design was verified sound despite the missing section:** the fixture reuses,
  verbatim, the *same* mechanism `ZZLOOKAHEAD01` (a Phase 4 fixture, unmodified) already
  established and already had passing tests for — two facts under one tag, filed on different dates,
  with `screen()`'s own point-in-time resolution ("most-recently-filed fact with `filed <=
  as_of_date`") picking whichever one is visible as of a given date. Because that resolution
  mechanism was already proven correct by Phase 4's own approved tests, extending it to a second,
  later `as_of_date` boundary (rather than a single look-ahead boundary) required no new,
  unverified assumption about `screen()`'s own behavior — only a new arrangement of already-trusted
  primitives. `test_backtest_clock.py`'s own end-to-end assertions (PURE at 2026-01-01,
  NON_COMPLIANT at 2026-04-01 and every later rebalance date) then closed the loop empirically.
  **Tradeoff/finding, stated plainly:** this is a real spec-completeness gap (see §5 below) — a
  future reader skimming `PHASE_5_SPEC.md` for "§6e" will hit nine dead cross-references — but it did
  not block or degrade this phase's own build, because the executor had a sound, already-verified
  fallback pattern to build from rather than needing to invent one from scratch.
- **`apply_allocation`'s cash floor (`cash = max(cash, 0.0)`, `mizan/backtest/portfolio.py` line
  157) is a floating-point-noise guard, not a relaxation of the non-negative-cash invariant.**
  `AllocationInstruction`'s own validator already forbids `target_weights` summing above `1.0 +
  1e-9` at construction time — upstream of, and independent from, this function. Given that
  tolerance, the true mathematical floor for `cash` after `apply_allocation` is `-1e-9 ×
  total_value`, which for a large enough portfolio can exceed ordinary `float` rounding noise even
  though the allocation itself was legitimate. The floor clamps only that razor-thin,
  tolerance-induced negative residue back to exactly `0.0` — it can never mask a genuine
  over-allocation, because the validator already rejects any instruction that could produce a real
  (non-tolerance-sized) cash deficit before `apply_allocation` is ever called. **Tradeoff:** a
  defensive `max()` call that is dead code for every realistic portfolio size is still one more
  line a reader has to reason about to convince themselves it is not silently hiding a bug — the
  shipped code's own docstring carries the exact reasoning above precisely so a future reader does
  not have to re-derive it.

**New this phase — Phase 6's own real decisions/resolutions, each verified directly against the code
this run:**

- **The date-pinned-ratio discipline — the single most important design decision in this phase, and
  the reason `purify_dividend` re-invokes `screen()` instead of reading a cached number.**
  `ComplianceStateRecord.verdict_history` and `DividendEvent.verdict_at_ex_date` (both Phase-5-owned,
  confirmed by direct read of `mizan/backtest/compliance_state.py`) record only the three-state
  `Verdict` enum at each rebalance — never the actual `non_permissible_income_ratio` float that
  produced it. A naive "just use whatever ratio the ticker's *current* screen reports" implementation
  would silently apply the WRONG period's ratio to a dividend paid earlier in the backtest, for any
  ticker whose ratio drifts over time — a genuine purification undercount (or overcount)
  `ULTIMATE_PRD.md` §4.7 names by exact wording ("the ratio must be pinned to the screen *active at
  the dividend date*, not the current screen"). `purify_dividend` (`mizan/purification/ledger.py`
  lines 117–147, 187–282, read directly this pass) avoids this by finding the `VerdictObservation`
  with the LARGEST `as_of_date <= dividend_event.ex_date` in the ticker's own `verdict_history`, then
  re-invoking `mizan.screening.verdict.screen(ticker, ratio_as_of_date, con=con, cache_dir=cache_dir,
  overrides=overrides, fiqh_params=fiqh_params)` — the exact same `con`/`cache_dir`/`overrides`/
  `fiqh_params` the original backtest ran with — and reading the ratio off THAT call's own
  `ScreeningVerdict.reason_trace`. Because `screen()` is a pure function of `(ticker, as_of_date, con,
  cache_dir, overrides, fiqh_params)` plus already-frozen DuckDB/cache state (no write happens to
  either between the original backtest and Phase 6's re-derivation — the read-only connection never
  closes in between, see the connection-lifetime item below), this re-invocation is bit-for-bit
  identical to the call `rebalance()` already made at that exact rebalance, not an approximation.
  **Tradeoff:** every Mixed-verdict dividend costs one extra `screen()` call (itself potentially
  several DuckDB queries) at purification time, which a cached-ratio design would have avoided — but
  the cached-ratio design was never actually available, since Phase 5 never persisted the ratio in
  the first place, and re-deriving via the same deterministic function the backtest already trusted
  is a materially safer choice than inventing a new persisted-ratio schema this late, untested against
  the same guarantee `screen()`'s own approved tests already give it.
- **The Fork A/Fork C gating resolution — `fiqh_params.purify_capital_gains.value` gates BOTH Fork A
  (dividend purification, obviously) AND Fork C (forced-divestment price-appreciation attribution),
  even though `MASTER_PRD.md` §8's own prose never says this in one explicit sentence.** Confirmed by
  direct read of `mizan/purification/ledger.py`'s `purify_backtest_result` (lines 355–366):
  `divestment_entries` stays `[]` — never populated, not even with zero-amount placeholders — unless
  `fiqh_params.purify_capital_gains.value` is `True`; when `True`, `compute_divestment_attribution` is
  called once per `DivestmentEvent`. The reasoning, read directly from `MASTER_PRD.md` §8 this pass:
  Fork A's own scope note is "dividends only for V1; capital-gains purification is a configurable,
  default-OFF... flag," and Fork C's own subject — "price appreciation during the non-compliant
  window" — is a capital gain by ordinary definition, not a dividend. `mizan/config/fiqh_params.py`'s
  own register entry #9 source string makes the SAME toggle explicit rather than requiring a cross-
  section inference: `purify_capital_gains` is documented there as "**Fork A**: dividends-only for V1;
  capital-gains purification default OFF" — i.e. register #9 already names itself as the gate for
  capital-gains purification generally, of which Fork C's mechanism is one instance. **Tradeoff:**
  this reading was not 100% explicit in `MASTER_PRD.md`'s own Fork C paragraph taken in isolation — a
  different, equally defensible reading (Fork C always runs, since it has its own register entry #10
  for its *method*) was available and was not chosen. The shipped code commits to the gated reading,
  test-verified (`test_divestment_attribution_gated_by_purify_capital_gains_config`,
  `tests/test_purification_ledger.py`): toggling `purify_capital_gains` from `False` to `True` via
  `model_copy` over the same `ZZDIVEST_APPREC01` backtest changes `divestment_entries` from `()` to a
  nonempty tuple, proving the value is read from config, not hardcoded either way — but a future
  reader who disagrees with the gating reading has a real, cited textual basis to reopen the question,
  not just a code choice to accept on faith.
- **The connection-lifetime bug the executor caught and fixed relative to the spec's own pseudocode.**
  `PHASE_6_SPEC.md` §4.3 (read in full this pass) instructs the purify call to be "inserted between
  `result = BacktestResult.model_validate(envelope.payload)` and the existing `print(f"Final
  portfolio value: ...")` block" — a literal reading of Phase 5's own shipped `mizan/cli/backtest.py`
  (confirmed by reading `git show 9e989eb:mizan/cli/backtest.py` directly this pass) places that
  `result = BacktestResult.model_validate(...)` assignment at 4-space (function-body) indentation,
  i.e. AFTER the `with db.connect(args.db_path, read_only=True) as con:` block has already exited and
  closed `con`. Following the spec's insertion point literally would have called
  `purify_backtest_result(result, con=con, ...)` — which internally re-invokes `screen()`, which reads
  DuckDB through `con` — against an already-closed connection. The shipped code (confirmed by direct
  diff read, `git diff 9e989eb..9750a18 -- mizan/cli/backtest.py`) instead moves BOTH the
  `BacktestResult.model_validate(...)` line AND the new `purify_backtest_result(...)` call inside the
  existing `try:` block, still nested inside the `with` statement, so `con` is provably still open
  when purification runs; only the summary `print(...)` calls stay after the `with` block exits, since
  they need no further DB access. **Tradeoff:** none, really — this is a straightforward correctness
  fix over a spec pseudocode sample that did not account for exactly where Phase 5's own assignment
  line sat relative to the connection's scope; it is flagged here specifically because it is the kind
  of small, easy-to-miss discrepancy between "the spec's illustrative code" and "the actual file it is
  a patch against" that a mechanical patch-apply (rather than a read-the-actual-file-first approach)
  would have shipped broken.
- **The module-layout deviation — `mizan/purification/` (a two-file package) instead of the single
  `mizan/backtest/purification.py` `MASTER_PRD.md` §9.4's diagram and `PHASE_5_SPEC.md` §1/§9 both
  named.** Confirmed: `mizan/purification/` is a real, top-level package (`ls mizan/purification/`
  shows `__init__.py`, `ledger.py`, `attribution.py`); no file named `mizan/backtest/purification.py`
  exists anywhere in the repository. `PHASE_6_SPEC.md` §1 names this deviation explicitly and gives
  three reasons (Fork B/Fork C are as cleanly separable as `business_activity.py`/`financial_ratios.py`
  already are; `MASTER_PRD.md` §9.1's own pipeline diagram draws purification as a distinct box, not a
  `backtest/` sub-component; Phase 6 is a pure post-processing consumer of a completed `BacktestResult`,
  not a participant in the daily event loop). **Tradeoff:** the deviation makes `ULTIMATE_PRD.md` §5
  check 5's own literal grep line (naming `mizan/backtest/purification.py`) stale — it no longer
  resolves to a real file — and `PHASE_6_SPEC.md` §1/§7 restate the corrected grep path
  (`mizan/purification/`) explicitly rather than leaving a future reviewer to rediscover the mismatch;
  the honesty cost is one more place a stale primary-source path needs a human to know it has been
  superseded by a spec-level correction rather than a document edit.

## 4. Domain mechanics

**Fiqh register — carried forward from Phase 1, unchanged (`mizan/config/fiqh_params.py` is
untouched by Phase 5's or Phase 6's diff, confirmed by re-reading it this pass), now shown with
Phase 5's and Phase 6's own new readers added:**

| # | Figure / default | Value in code | Code's own source citation | Read by |
|---|---|---|---|---|
| 1–5 | Ratio denominator basis/smoothing, debt/interest-investments/non-permissible-income thresholds | unchanged | unchanged | Still only `mizan/screening/verdict.py`/`financial_ratios.py` (Phase 4) directly — Phase 5/6 both read these only indirectly, via `screen()`'s own output |
| 6–7 | Business-activity Tier 0.5 / Tier 1 toggles | unchanged | unchanged | Still only `classify_business_activity` (Phase 4), reached transitively via `screen()` |
| 8 | Grace period length | 1 whole rebalance period | unchanged from Phase 5's own citation (`mizan/config/fiqh_params.py` register entry #8) — **`[UNVERIFIED / INFERENCE]`**, no AAOIFI primary-source citation | `mizan.backtest.compliance_state.transition` (Phase 5); Phase 6 reads it only indirectly, through the already-resolved `ComplianceStateRecord.flip_date`/`divest_date` fields it consumes |
| **9** | **Purify capital gains (Fork A/C gate)** | **`False`** (V1 default) | `mizan/config/fiqh_params.py` register entry #9, `purify_capital_gains: FiqhParam[bool](value=False, source="Fork A: dividends-only for V1; capital-gains purification default OFF.", primary_source_gap="The primary source establishes THAT non-halal income must be purified (Merah slides 24-25) but gives no formula for capital gains. Genuinely underdetermined.")` — **`[UNVERIFIED / INFERENCE]`** on the OFF default itself (a scholarly-ruling-pending policy choice, not an AAOIFI-mandated value) | **NEW this phase** — `mizan.purification.ledger.purify_backtest_result`, read fresh on every call (`fiqh_params.purify_capital_gains.value`), gating both Fork A's own capital-gains scope AND Fork C's divestment attribution (§3 above) |
| **10** | **Divestment attribution method** | **`DivestmentAttributionMethod.TIME_BOUNDED_PRICE_APPRECIATION`** (the only defined member) | register entry #10, `source="Fork C: price appreciation over the flip-date to divestment-date window.", primary_source_gap="No settled formula exists. The Step 10 literature sweep (2024-2026) found no proposed alternative either — an explicit null result, not an unsearched gap."` — **`[UNVERIFIED / INFERENCE]`** | **NEW this phase** — `mizan.purification.attribution.compute_divestment_attribution`, read fresh (`fiqh_params.divestment_attribution_method.value`) though there is exactly one branch to dispatch to |
| **11** | **Purification accounting method** | **`PurificationAccountingMethod.SIDE_LEDGER`** (the only defined member) | register entry #11, `source="Fork B, now PRIMARY-SOURCE VERBATIM (Merah slide 25): purification means non-halal income 'will have to be donated to Charity and cannot be included in the investors P&L accounts'. A side-ledger is the only faithful reading."` — this one entry is NOT flagged `[UNVERIFIED]` in the register's own source string, since it quotes the primary source directly rather than inferring from it | Not read by name anywhere in `mizan/purification/` this phase (confirmed: `grep -rn "purification_accounting_method" mizan/purification/` finds no hit) — the side-ledger DESIGN it names is what `PurificationLedger`'s own existence as a value separate from `BacktestResult`'s own return figures implements structurally, not a runtime branch on the enum's value |

**Purification formula, new this phase (`mizan/purification/ledger.py`, `attribution.py`):** Fork A —
for a dividend paid by a Mixed-verdict holding, `purified_amount = non_permissible_income_ratio ×
dividend_amount`, where the ratio is the one active AT the dividend's own `ex_date` (§3 above), never
the ratio active at any other date — cites `MASTER_PRD.md` §8's own trigger sentence verbatim
("purify `non_compliant_income_ratio × dividend_amount`... the ratio comes from that holding's
most-recent screen and the dividend cash comes from Tiingo's per-day divCash field"). Fork C — for a
forced divestment, `purified_amount = max(0.0, quantity_liquidated × (price_at_divest -
price_at_flip))`, cites `MASTER_PRD.md` §8 Fork C's own wording ("price appreciation during the
non-compliant window, time-bounded flip-date → divestment-date"). Both formulas are confirmed present,
exactly as described, by direct read of `purify_dividend`/`compute_divestment_attribution` this pass
(§2 above).

**AAOIFI's underlying rule, and the honest limit of what Mizan actually does with it (`MASTER_PRD.md`
§8, read in full this pass):** "non-halal income must be donated to charity and cannot be included in
the investor's P&L" — a side-ledger by definition, purification carried outside the return, never
netted into NAV. **Mizan computes and tracks `purification_liability` as a number; it does not
transfer, donate, or move any money anywhere.** Confirmed by direct read of every line under
`mizan/purification/`: no HTTP client, no payment/charity API, no file write beyond the in-memory
`PurificationLedger` object itself. `PHASE_6_SPEC.md` §9 states this non-goal explicitly ("It does NOT
mean any cash, wire transfer, ledger entry in an external system, or API call to an actual charity is
made") and the shipped code matches that claim exactly — this is not a gap the code silently leaves
open, it is a boundary the spec named and the code respects.

**Carried forward from Phase 5 — the compliance-flip state machine (`MASTER_PRD.md` §7.3's own
diagram, implemented in `mizan/backtest/compliance_state.py`, untouched by Phase 6's diff):**

`HELD_COMPLIANT` → (fresh verdict `NON_COMPLIANT`) → `HELD_NONCOMPLIANT_GRACE` → (grace countdown
reaches 0) → `DIVESTED`. Confirmed by direct read of `transition()`'s own transition table: a
`HELD_COMPLIANT` record whose fresh verdict stays `PURE`/`MIXED` just appends a `VerdictObservation`
and stays put; a flip to `NON_COMPLIANT` sets `flip_date` and seeds
`grace_rebalances_remaining = fiqh_params.grace_period_rebalances.value` (currently `1`, per the
register entry above); every subsequent rebalance while `HELD_NONCOMPLIANT_GRACE` decrements that
counter by exactly 1 regardless of what the new verdict says — **there is no edge back to
`HELD_COMPLIANT`** — and a decrement to `0` fires `DIVESTED`, stamping `divest_date` and returning a
`DivestmentEvent`. A `DIVESTED` ticker is asserted (via `AssertionError`, not silently tolerated)
never to be re-screened as a holding again — enforced upstream by `rebalance()` liquidating a
divested position the same rebalance it fires, before the ticker could ever reach `transition()`
again. With the register's current value of `1`, "grace period" in practice means: a ticker flips at
rebalance N, survives rebalance N (frozen, untouched), and is forced out exactly at rebalance N+1
regardless of its verdict at N+1.

**Carried forward from Phase 5 — the quarterly rebalance cadence, and why it is fixed, not
configurable:**
`mizan/backtest/clock.py`'s own module-level `_REBALANCE_MONTHS: tuple[int, ...] = (1, 4, 7, 10)` is
the *only* rebalance-date generator anywhere under `mizan/backtest/` — there is no CLI flag, function
parameter, or config value anywhere in this phase's code that can make a backtest rebalance faster
than quarterly (confirmed: `mizan/cli/backtest.py`'s `add_subparser` has no
`--rebalance-frequency`-shaped flag, and `run_backtest`'s own signature carries no such parameter).
This is a deliberate, cited engineering choice, not an oversight: `ULTIMATE_PRD.md` §1.1 states that
"a proposal to shorten the rebalance cadence below quarterly... is crossing a values boundary, not
tuning a parameter... must be escalated to the human, never absorbed as an enhancement" — i.e. this
is a scope boundary the project has already confirmed and closed, not an open question Phase 5
reopened.

**Carried forward from Phase 5 — Tiingo's `splitFactor` arithmetic direction, verified live that
phase (`docs/modernization_log.md` §6.2b, read in full):** Tiingo's own splits documentation
(https://www.tiingo.com/documentation/corporate-actions/splits, fetched 2026-08-31) states verbatim
"the ratio of splitTo from splitFrom... splitFactor = splitTo/splitFrom," confirmed against a real
worked example (Realty Income, 2021-11-15, a 1-to-1.0327 split, `splitFactor: 1.0327`). This
resolves a genuine, previously-unverified gap `PHASE_5_SPEC.md` §0.1 explicitly named rather than
guessed at (no prior phase's data-source verification pass had checked this direction).
**Consequence, confirmed by direct read of `apply_split`:** `split_factor` is the multiplier applied
to a held share count, never its reciprocal — `mizan/backtest/portfolio.py`'s `apply_split` computes
`new_quantity = holding.quantity * split_factor` (a 2-for-1 split, `splitFactor=2.0`, turns 100
shares into 200), and price is deliberately never adjusted by this function at all (valuation stays
governed by `raw_close`, per Phase 5's own §6a decision carried in `portfolio.py`'s module
docstring — splits and dividends are handled explicitly and separately, never via an
adjusted-price series, so a dividend credited to cash is never double-counted against an
already-dividend-adjusted price).

**Ingestion, normalization, and screening domain mechanics — carried forward from Phase 2/3/4,
unchanged (none of `ingest_edgar.py`, `ingest_tiingo.py`, `db.py`, `normalize.py`,
`business_activity.py`, `financial_ratios.py`, or `mizan/screening/verdict.py` is touched by Phase
5's or Phase 6's diff):** SEC EDGAR's 10 req/s rate limit, Tiingo's 50/hour–1,000/day request budget
and 500-ticker/month cap, the `fundamentals_facts`/`price_bars` uniqueness keys, the 21-SIC-code
three-tier business-activity map, and the 30/30/5 AAOIFI ratio thresholds all remain exactly as the
Phase 4 comprehension pass described — re-confirmed present and untouched via `git diff
9e989eb..9750a18 --stat`, which lists none of those files.

## 5. Honesty audit

Ran the same class of verification `PHASE_6_SPEC.md` §7 (guards)/§8 (acceptance criteria) specify,
against the code as it exists in the repository right now, this run — not trusting the spec's or the
approval commit's claim that they pass. No adversarial re-review was performed (Phase 6 is already
approved); this is an independent comprehension-grade honesty pass, run fresh this session rather
than restating the review's own verdict.

**Everything below was re-run and passed as claimed, this run, inside the project's `.venv`:**
- `pytest tests/` — **365 passed** (340 carried from Phase 1–5 + 25 new this phase: 17 in
  `tests/test_purification_ledger.py`, 7 in `tests/test_purification_attribution.py`, 1 new case
  appended to `tests/test_cli_backtest.py`), no regressions, 127s wall time.
- `ruff check mizan tests` — "All checks passed!", exit 0, under the pinned `ruff==0.16.5`.
- `mypy --strict mizan tests` — "Success: no issues found in 59 source files" (up from 54 in the
  Phase 5 pass — exactly 5 new files: `mizan/purification/__init__.py`, `ledger.py`, `attribution.py`,
  `tests/test_purification_ledger.py`, `tests/test_purification_attribution.py`), inside `.venv`.
- `grep -rn "noqa" mizan/` — exactly the same three `# noqa: N812` hits Phase 4's comprehension pass
  already found (`mizan/data/models.py`, `mizan/data/normalize.py`, `mizan/screening/verdict.py`),
  plus `models.py`'s unrelated `N815` wire-format suppressions — zero new suppressions anywhere
  under `mizan/purification/`.
- `git log --format=%B f5b8132..9750a18` — no `Co-Authored-By`, no "Generated with," no
  model/assistant name anywhere in Phase 6's technical-blueprint or implementation commit history
  (G-AI clean).
- The five failure-mode greps `PHASE_6_SPEC.md` §7 specifies for the corrected `mizan/purification/`
  path — all re-run directly this pass, all clean: `grep -rniE
  "openai|anthropic|gemini|vertex|langchain|\bllm\b|chat_completion|completion\(" mizan/purification/`
  (no hit, G-LLM6); `grep -rniE
  "\b(short|shorts|shorting|borrow|borrowed|borrowing|margin|leverage|leveraged|levered|option|options|future|futures|swap|swaps|derivative|derivatives)\b"
  mizan/purification/` (no hit, G-BOUND2); `grep -rniE "INSERT INTO|CREATE TABLE|ALTER TABLE|DROP TABLE"
  mizan/purification/` (no hit, G-P5/G-DB6); `grep -rn "duckdb.connect" mizan/purification/` (no hit,
  G-DB6); `grep -rn "daily_snapshots\s*=" mizan/purification/` (no hit — nothing under
  `mizan/purification/` ever reassigns a `daily_snapshots` value, confirming `net_of_purification_
  return` is the only site `purification_liability` is ever subtracted from anything, G-P3).
- `BacktestResult.purification_ledger`'s declared type — confirmed byte-for-byte unchanged
  (`dict[str, object] | None = None`) by direct diff read of `mizan/backtest/clock.py` across
  `9e989eb..9750a18` (the file does not appear in the diff stat at all), matching `PHASE_6_SPEC.md`
  §3.1's own binding decision and §8 AC13.

**The connection-lifetime finding, found independently this pass by comparing the spec's own §4.3
pseudocode against Phase 5's actual, already-committed `mizan/cli/backtest.py` (not merely trusting
that the shipped diff "looks right"):** `PHASE_6_SPEC.md` §4.3 instructs the purify call to be
inserted "between `result = BacktestResult.model_validate(envelope.payload)` and the existing
`print(...)` block." Reading Phase 5's actual committed file (`git show
9e989eb:mizan/cli/backtest.py`) shows that assignment sitting OUTSIDE the `with db.connect(...) as
con:` block, at function-body indentation — meaning a literal application of the spec's insertion
point would have called `purify_backtest_result` (which internally calls `screen()`, which reads
DuckDB through `con`) after `con` was already closed. The shipped diff does NOT do this: both the
`BacktestResult.model_validate(...)` line and the new `purify_backtest_result(...)` call were moved
inside the existing `try:` block, still nested inside the `with` statement (confirmed directly, `git
diff 9e989eb..9750a18 -- mizan/cli/backtest.py`, lines 39–53 of that hunk). This is a genuine,
correctly-executed deviation from the spec's own literal illustrative code — flagged here as the
single most consequential thing this honesty pass found, since a mechanical "patch the file exactly
where the spec says" approach would have shipped a `mizan backtest` that halts on a closed-connection
error every time purification actually has work to do (any Mixed-verdict dividend, or any divestment
with `purify_capital_gains=True`). See §3 above for the decision writeup.

**`PHASE_6_SPEC.md`'s own claims, checked directly against the code rather than assumed, this run:**
- §1's claim that only `mizan/cli/backtest.py` is modified under an earlier phase's ownership, and
  only additively — confirmed: `git diff 9e989eb..9750a18 --stat` shows exactly one earlier-phase
  file touched (`mizan/cli/backtest.py`, +36/−7 lines per `git diff --numstat`; the 7 deleted lines
  are the docstring's own old wording plus the `result = BacktestResult.model_validate(...)` line at
  its old location, relocated rather than deleted outright — confirmed line-by-line no existing
  runtime behaviour was removed, only reworded/relocated, by the diff read above), plus one
  additive-only fixture file (`tests/fixtures/synthetic_universe.py`) and one additive-only test file
  (`tests/test_cli_backtest.py`); every other changed file is entirely new.
- §1's claim that the module-boundary deviation (`mizan/purification/` vs. the diagrammed
  `mizan/backtest/purification.py`) is real and the corrected grep path is restated — confirmed: no
  `mizan/backtest/purification.py` file exists anywhere in the repository; `mizan/purification/`
  does (§2/§3 above).
- §6c's own textual argument for gating Fork C by `purify_capital_gains` — checked directly against
  `MASTER_PRD.md` §8's actual prose this run (not merely trusting the spec's paraphrase): the
  spec's quoted excerpts ("dividends only for V1... capital-gains purification is a configurable,
  default-OFF... flag" and Fork C's "price appreciation... time-bounded") are accurate, verbatim
  quotes of the real document, confirmed by direct read of `MASTER_PRD.md` lines 251–269 this pass.
  The gating conclusion itself is a reasoned inference, not a verbatim instruction — named honestly
  as such in §3 above, not overstated as settled by this pass either.
- §8's 21 acceptance criteria — spot-checked three directly against the test suite rather than all
  21: AC1 (ratio-drift anti-undercount) maps to
  `test_two_dividends_same_ticker_different_ratios_purified_at_own_period_ratio`; AC3 (gated Fork C)
  maps to `test_divestment_attribution_gated_by_purify_capital_gains_config`; AC5 (gross/net
  distinctness) maps to `test_gross_and_net_of_purification_return_distinct_when_liability_nonzero`
  and `test_gross_and_net_of_purification_return_equal_when_ledger_empty` — all three present in
  `tests/test_purification_ledger.py`, all passing per the full-suite run above.

**No new spec-completeness gap found this pass** of the kind Phase 5's own §6e finding was (a
referenced-but-never-written section) — `grep -n "§6[a-e]"` and a header-pattern check against the
full 886-line `PHASE_6_SPEC.md` this run found every cross-referenced subsection (§6a/§6b/§6c/§6d)
actually present and written.

**Phase 1's documented mypy/numpy environment gap, and Phase 3/4/5's related duckdb-import gap —
both still real, the duckdb gap now touching two more files this phase:**

- **Inside `.venv`**: clean, 0 errors, 59 files (confirmed above).
- **Outside `.venv`**: the original numpy stub failure (`numpy/__init__.pyi:737: error: Type
  statement is only supported in Python 3.12 and greater`) is environment-specific and unrelated to
  Phase 6's own code — not independently re-verified this pass (Phase 6 does not touch numpy usage in
  any way), carried forward on the strength of Phase 1's own original finding. The duckdb-import gap
  Phase 3's comprehension pass first found, and Phase 4/5 extended, now also reaches
  `mizan/purification/ledger.py` and `mizan/purification/attribution.py` (confirmed this run: both
  files carry `import duckdb` under `TYPE_CHECKING`, read directly at the top of each file) — two more
  consumers of the same already-flagged, already-documented, environment-specific limitation. Neither
  new test file (`test_purification_ledger.py`/`test_purification_attribution.py`) imports `duckdb`
  directly at module scope in a way this pass's grep needs to separately track, since both are
  exercised inside `.venv` where the limitation does not manifest. `PHASE_3_SPEC.md`'s "build and
  verify inside `.venv`" instruction remains the correct, unchanged mitigation.

**Phase 2's AC15 noqa-enumeration finding, and Phase 4's LongTermInvestments/gambling-SIC-code open
items — re-checked this run, all still accurate, none touched by Phase 5 or Phase 6:**

- The Phase 2 AC15 file-enumeration mismatch (`A003` absent from `mizan/data/models.py`'s own noqa
  enumeration) remains present and unaffected — `models.py` is untouched by Phase 5 or Phase 6.
- `LongTermInvestments` (`INTEREST_BEARING_INVESTMENT_TAGS`) remains `[UNVERIFIED]` in
  `docs/modernization_log.md` §6.3 — Phase 6 does not touch `financial_ratios.py` and performed no
  new XBRL-tag verification pass; the ratio-drift fixture (`ZZMIXED_RATIODRIFT01`) uses
  `InvestmentIncomeInterest`, a tag already `[VERIFIED]` from Phase 4's own pass, not
  `LongTermInvestments`.
- The `SIC_TIER_MAP` gambling/casino gap (no dedicated Tier-0 SIC 7993, since it is not a real
  SEC-assigned code; real gambling issuers file under SIC 7011/Tier 1) remains present and
  unaffected — `business_activity.py` is untouched by Phase 5 or Phase 6.

**No new gap this pass otherwise found beyond what §3 above already surfaces as deliberate, logged
decisions** (the date-pinned-ratio re-derivation cost, the Fork A/C gating's textually-inferred-not-
verbatim status, the connection-lifetime fix, the module-layout deviation) and what §6 below restates
as still-open carried-forward items.

## 6. Open items

**The single most important open item, carried forward from Phase 4 and restated prominently
because Phase 6, exactly like Phase 4 and Phase 5 before it, only proves the mechanism works on
synthetic data:**

- **The real ~100-ticker curated universe and its hand-verified business-activity override map still
  do not exist anywhere in this repository.** Phase 6 built and proved out the generic purification
  MECHANISM — the date-pinned ratio lookup, the Fork A/B/C gating, the side-ledger accrual — verified
  only against the sixteen synthetic fixture tickers now in `tests/fixtures/synthetic_universe.py`
  (Phase 4's original set, plus Phase 5's `ZZFLIP01`, plus this phase's three additions:
  `ZZMIXED_RATIODRIFT01`, `ZZPURE_DIV01`, `ZZDIVEST_APPREC01` — never real issuers, CIK prefix
  `999...`). It did **not** build, and was never supposed to build, the real hand-researched activity
  map. Running `mizan backtest` against real tickers today would deploy real purification arithmetic
  against whatever generic SIC-first-pass verdict `screen()` produces for those tickers — not a
  trustworthy, hand-verified real-world compliance-and-purification answer, exactly the same caveat
  Phase 4's own open item already stated for `mizan screen` alone and Phase 5's carried forward for
  the backtest engine.

**New this phase:**

- **The gross/net-of-purification accounting is a plain point-to-point return over the whole backtest
  window, not annualized, risk-adjusted, or time-weighted — worth a future human's attention before
  it is presented to a real user.** Confirmed by direct read of `PurificationLedger.gross_return`'s
  own docstring and `_compute_returns`'s implementation (`mizan/purification/ledger.py`): `gross_return
  = (end_value - start_value) / start_value`. This is an honest, deliberate scope limit
  (`PHASE_6_SPEC.md` §3.2 states Phase 7's reporter is free to compute richer figures from
  `daily_snapshots` and `purification_liability` directly), not a defect — but a future reader of
  Phase 7's report should not mistake this field for an annualized or CAGR-style return.
- **The empty-`daily_snapshots` edge case is handled, but is worth a future human noticing rather than
  assuming away.** `_compute_returns` returns `(0.0, 0.0)` when `daily_snapshots` is empty (e.g. a
  `start_date`/`end_date` window with zero resolvable `price_bars` rows) — confirmed by direct read
  of its docstring's own reasoning (an empty snapshot series implies zero dividend/divestment events
  too, so `purification_liability` is provably `0.0` in that case, keeping the "the two return figures
  are equal iff the ledger is empty" invariant intact even at this boundary). This is correctly reasoned,
  not a gap — flagged here only because it is exactly the kind of quiet edge-case handling a future
  refactor could accidentally break without a dedicated test asserting it (no test in
  `tests/test_purification_ledger.py` explicitly constructs an empty-`daily_snapshots` `BacktestResult`
  and asserts `(0.0, 0.0)` — this pass did not find one; every purification test exercises a backtest
  with at least one trading day).
- **The Fork A/Fork C gating decision (§3 above) rests on a reasoned textual inference from
  `MASTER_PRD.md` §8, not a verbatim, unambiguous instruction — a future scholarly-verification pass
  could reasonably reopen it.** Named honestly in §3/§5 above rather than presented as settled; a
  future human revisiting the eleven-entry fiqh register's scholarly review should know register #9's
  scope (Fork A capital-gains toggle) is doing double duty as Fork C's own gate, by inference, not by
  the primary source stating so in one sentence.
- **`mizan/purification/` deviates from `MASTER_PRD.md` §9.4's and `PHASE_5_SPEC.md`'s own diagrammed
  module path (`mizan/backtest/purification.py`)** — a real, cited, reasoned deviation (§3 above), but
  it means `ULTIMATE_PRD.md` §5 check 5's own literal grep line is now stale unless a future reader
  knows to substitute `mizan/purification/` for it. `PHASE_6_SPEC.md` §1/§7 already restate the
  corrected path, but `ULTIMATE_PRD.md` itself is not corrected in place — worth a documentation fix
  in a future pass rather than leaving every subsequent reader to rediscover the substitution, the
  same category of "spec cross-reference has silently drifted from the code" item Phase 5's own §6e
  finding was.
- **The connection-lifetime bug the executor caught (§3/§5 above) is exactly the kind of thing a
  literal, non-reading patch-apply would have shipped broken** — worth a standing note for whoever
  authors Phase 7's own spec pseudocode: any illustrative code sample referencing an earlier phase's
  file by "insert after line X" should be checked against the ACTUAL committed file's scoping, not
  assumed from the surrounding prose, since Phase 5's file structure had already shifted where that
  insertion point actually sat relative to the open connection.

**Carried forward, status re-checked this pass:**

- **The mypy/numpy-outside-.venv gap, and the duckdb-import gap it travels with** — still open, still
  environment-specific, still not phase-blocking; now also reaches `mizan/purification/ledger.py` and
  `mizan/purification/attribution.py` in addition to `mizan/backtest/clock.py` and
  `tests/test_backtest_clock.py`. See §5.
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** — still open by
  design; Phase 6 touches none of them.
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged; Phase 6
  does not touch `mizan/config/fiqh_params.py`, only reads register entries #9/#10/#11 (and,
  indirectly, #8) at runtime.
- **`PHASE_5_SPEC.md`'s own missing §6e section** — referenced nine times, never written (Phase 5's
  own honesty audit finding, re-confirmed not yet fixed this pass: `grep -n "§6e" PHASE_5_SPEC.md`
  still returns the same nine lines, and the file still contains no `## 6e`/`### 6e` header). Still
  worth fixing directly in the spec file.
- **The frozen/workable partition adds real complexity to `rebalance()`** that a reviewer or future
  maintainer needs to understand correctly to avoid accidentally reintroducing the exact bug it
  prevents (force-selling a grace holding one rebalance early) during a future refactor — flagged
  here as a maintenance-risk item, not a defect in the current code, unaffected by Phase 6 since
  `mizan/backtest/clock.py` is untouched.
- **The grace period's value (`1` rebalance) carries no AAOIFI primary-source citation** — unchanged
  from Phase 5's own honestly-flagged inference.
- **The Phase 2 AC15 noqa-enumeration mismatch** — still present, unaffected by Phase 5 or Phase 6.
- **`LongTermInvestments` remains `[UNVERIFIED]`, and `SIC_TIER_MAP` still has no dedicated
  gambling/casino Tier-0 code** — both unaffected by Phase 5 or Phase 6, since neither
  `financial_ratios.py` nor `business_activity.py` is touched.
- **Corporate-action anomaly scan is deliberately conservative and will produce false positives** —
  unchanged, still an accepted tradeoff, not a defect.
- **No real backfill has been run, and no real backtest or purification pass has been run against real
  market data** — unchanged and, this phase, extended further: everything verified in Phases 1–6 (and
  their own reviews) is against fixtures and synthetic data, not a full live ~100-ticker run and not a
  real historical backtest-plus-purification result for any actual strategy.
- **The DuckDB file remains a local, derived, regenerable artifact with no versioned migration
  path** — unchanged; Phase 6 adds no new table, column, or index (confirmed: `mizan/data/db.py` is
  untouched by this phase's diff, and `PHASE_6_SPEC.md` §5 confirms N/A explicitly).
- **No report or chart exists yet.** `mizan backtest` now prints a purification summary to stdout
  (`Purification liability: ...`, `Gross return: ...`, `Net-of-purification return: ...`, plus one
  line per dividend/divestment entry), but there is still no HTML output, no chart, and no `matplotlib`
  import anywhere in `mizan/` (confirmed by this pass's own grep of `mizan/purification/`, and
  `PHASE_6_SPEC.md` §9's own explicit non-goal). That remains entirely Phase 7's job.

---

## Phase Log

**Phase 1 — Foundation & Config** (2026-08-30)

Phase 1 established Mizan's foundation before any ingestion, screening, or backtest logic exists.
It shipped: the seven-field `Invariants` model and its single `INVARIANTS` singleton, encoding the
permissibility boundary (long-only, fully-funded, zero cash yield, no derivatives, no margin, no
riba modeling, no LLM in the compliance path) as fixed constants with no override mechanism; the
eleven-row `FiqhParams` register and its `FIQH_PARAMS` singleton, encoding every genuinely disputed
Islamic-finance judgment call (ratio denominator basis and smoothing, the 30/30/5 thresholds,
business-activity tiering, grace period, and the three purification forks) as visible, sourced,
`pending_scholarly_verification`-stamped configuration rather than silent hardcoding; a fail-fast
`mizan-boot-check` CLI entry point that refuses to let the program start if either the invariants or
the register is structurally broken; and the shared cross-cutting types every later phase will
import — `MizanBaseModel` (the strict/frozen/validated Pydantic base every model must use),
`Verdict` (the three-state screening outcome enum), and `Caveat`/`ResultEnvelope` (the mandatory
warning-label wrapper for every future result). `pyproject.toml` was written with exact,
externally-verified dependency pins, and `docs/modernization_log.md` was updated with the actual
build-machine Python version (3.14.4). 63 tests were added covering boot-gate rejection behaviour,
register completeness and honesty, and the shared type contracts; all 63 pass, `ruff` is clean, and
`mypy --strict` is clean when scoped to `mizan/` itself. No screening, ingestion, backtest, or
purification logic was written — those remain Phases 2 through 7.

**Phase 2 — Ingestion & Raw Cache (EDGAR + Tiingo)** (2026-08-30)

Phase 2 gave Mizan its first two working connections to the outside world, built entirely on top of
Phase 1's untouched foundation. It shipped `mizan/data/models.py` (five raw wire-format row-shape
schemas covering EDGAR's company-tickers, XBRL fact, and submissions payloads, plus Tiingo's daily
price-bar and a derived corporate-action-event view — all `extra="forbid"` via `MizanBaseModel`, so
upstream schema drift raises loudly instead of being silently dropped); `mizan/data/raw_cache.py`
(one shared, source-agnostic replayable-cache implementation — deterministic path construction,
existence-based cache-hit detection, atomic writes, and a permissively-typed reader shared by both
ingestion legs); `mizan/data/ingest_edgar.py` (a rate limiter enforcing SEC's ≥0.12s spacing and
≥600s block cooldown, required-header construction, and `resolve_cik`'s ticker→CIK resolution with
a name/title cross-check against post-merger drift); `mizan/data/ingest_tiingo.py` (a distinct
budget-based limiter tracking hourly/daily request counts and a persisted monthly unique-symbol log
capped at 500, plus a deliberately conservative corporate-action anomaly scan flagging any
split-without-matching-dividend bar); and `mizan/cli/` (a `mizan` console-script entrypoint that
runs Phase 1's boot check before any subcommand, with one `ingest` subcommand orchestrating
per-ticker EDGAR-then-Tiingo fetches and continuing past individual ticker failures while still
signaling overall failure via exit code). `httpx==0.28.1` was promoted from a forward-declared,
unused optional extra to a real core dependency — the first phase to actually import it. Five new
test files added 83 tests (146 total, all passing) covering cache idempotency, rate-limiter/budget
timing via fake clocks, CIK cross-check logic, HALT-vs-continue CLI behaviour, and token-never-
leaks-to-disk guarantees. `ruff check mizan tests` is clean under the pinned `ruff==0.16.5` (with two
real, empirically-driven noqa corrections against the spec's illustrative code — see §3), and
`mypy --strict mizan tests` is fully clean inside the project's `.venv` (26 files), resolving in
practice — for anyone building inside that environment — the numpy-stub interaction Phase 1's
comprehension pass had flagged as an open item. No normalization, DuckDB storage, screening,
backtest, or purification logic was written — those remain Phases 3 through 7, and no production
backfill against the real ~100-ticker universe was run as part of this automated phase.

**Phase 3 — Normalization & DuckDB Store** (2026-08-30)

Phase 3 turned Phase 2's raw, wire-format-verbatim JSON cache into a real, typed, queryable local
database, built entirely on top of Phase 1's and Phase 2's untouched foundations. It shipped
`mizan/data/db.py` (a single canonical `connect()`/`ensure_schema()` pair that idempotently
`CREATE TABLE IF NOT EXISTS`-creates two DuckDB tables — `fundamentals_facts` and `price_bars` —
each guarded by a `PRIMARY KEY` constraint, plus a defensive `_verify_columns` check that raises
`SchemaError` rather than silently trusting `CREATE TABLE IF NOT EXISTS`'s own no-op-on-mismatch
behaviour); `mizan/data/normalize.py` (two new typed Pydantic row shapes, `FundamentalsFactRow` and
`PriceBarRow`; `normalize_edgar_facts` and `normalize_tiingo_bars`, which read Phase 2's cached raw
JSON — never fetching — validate every row, and bulk-load only the genuinely new ones via a shared
dedup-then-insert-with-backstop helper, `_bulk_load`; a closed `RECOGNIZED_XBRL_UNITS` allow-list
that rejects any XBRL fact reported in a unit outside `{"USD", "shares"}` rather than guessing a
scale conversion; and an `is_instantaneous` boolean that losslessly preserves an XBRL fact's
`start=None` signal after substituting `period_start = period_end` for it); and `mizan/cli/normalize.py`
(the `normalize` subcommand, wired into `mizan/cli/main.py` with one added line, following Phase
2's HALT-per-ticker-but-continue, non-zero-exit-code-on-any-halt contract exactly). `duckdb==1.5.5`
and `pyarrow==25.0.1` were promoted from Phase 1's forward-declared, unused optional extra to real
core dependencies — the first phase to actually import either. During the build, the spec's planned
same-process DuckDB single-writer-lock test was found not to exercise the real guarantee — DuckDB
1.5.5's Python API shares one database instance per file path within a process, so the actual
OS-level, cross-process file lock was verified and tested with a real subprocess instead, and
`docs/modernization_log.md` was corrected accordingly. Three new test files added 32 tests (178
total, all passing) covering schema idempotency, PRIMARY KEY enforcement, single-writer contention
across real processes, unit rejection, genuine-duplicate rejection, idempotent re-normalization, and
boot-gate-first CLI dispatch. `ruff check mizan tests` is clean under the pinned `ruff==0.16.5`
(with one additional, empirically-driven `# noqa: N812` suppression in the new `normalize.py`, the
same real reason `models.py` already carries one), and `mypy --strict mizan tests` is fully clean
inside the project's `.venv` (32 files). No screening, backtest, or purification logic was written —
those remain Phases 4 through 7 — and no normalization run against a real, operator-backfilled cache
was performed as part of this automated phase.

**Phase 4 — Screening Engine** (2026-08-30)

Phase 4 gave Mizan its first working compliance verdict, built entirely on top of Phases 1–3's
untouched foundations, and consuming Phase 3's `fundamentals_facts`/`price_bars` tables for the
first time since they were built. It shipped `mizan/screening/business_activity.py` (a SIC-code
first-pass classifier across 21 real, SEC-verified codes spanning `MASTER_PRD.md` §6.1's three
tiers, plus a pluggable, ships-empty `BusinessActivityOverrideMap` that takes precedence over the
SIC pass in both directions, keyed by CIK with a mandatory, non-empty `rationale` field);
`mizan/screening/financial_ratios.py` (pure-arithmetic implementations of AAOIFI's 30/30/5 debt,
interest-investment, and non-permissible-income ratios, each numerator a closed, summed-as-available
XBRL tag allow-list, with a numerator-side miss treated as a legitimate `0.0`); `mizan/screening/verdict.py`
(the `screen(ticker, as_of_date)` entry point — the only function body in `mizan/` permitted to
resolve "most-recently-filed fact with `filed <= as_of_date`" per concept, combining both layers via
fail-fast Layer-1-then-Layer-2 ordering into a `Verdict.PURE`/`MIXED`/`NON_COMPLIANT` result with a
full reason trace, wrapped in `ResultEnvelope`); and `mizan/cli/screen.py` (the `screen` subcommand,
opening DuckDB strictly read-only, wired into `mizan/cli/main.py` with one added line, following the
same per-ticker HALT-but-continue exit-code contract every prior CLI verb established). Two live
external-fact verifications were performed and logged in `docs/modernization_log.md`: one confirmed
13 of 14 candidate XBRL concept tags against six real companies' EDGAR `companyfacts` responses
(one, `LongTermInvestments`, logged `[UNVERIFIED]` rather than silently assumed); the other
confirmed every `SIC_TIER_MAP` code against SEC's own published SIC list and found that
`PHASE_4_SPEC.md` §4.1's own illustrative "7993 (gambling)" example is not a real, assigned SEC SIC
code at all — it was omitted from the shipped map rather than shipped as fabricated precision, with
the finding documented rather than silently corrected. `pyproject.toml` was not modified — Phase 4
introduces zero new third-party dependencies. Four new test files plus a new
`tests/fixtures/synthetic_universe.py` module (~12 explicitly-synthetic, clearly-labeled fixture
tickers, never real issuers) added 81 tests (259 total, all passing) covering every §6e fixture's
expected verdict, fail-fast structural correctness, config-toggle-driven verdict changes via
`model_copy`, look-ahead temporal non-interference, override-map precedence in both directions,
boundary-inclusive (`<=`) threshold semantics, and missing-denominator halting. `ruff check mizan
tests` is clean under the pinned `ruff==0.16.5` with no new noqa suppressions, and `mypy --strict
mizan tests` is fully clean inside the project's `.venv` (43 files). The real ~100-ticker curated
universe and its hand-verified business-activity override map were deliberately not built this
phase — that remains the project owner's own future research effort, explicitly out of scope for
this automated build (`PHASE_4_SPEC.md` §9's first, most prominent non-goal) — and no purification,
backtest, or reporting logic was written; those remain Phases 5 through 7.

**Phase 5 — Backtest Engine & Compliance-Flip State Machine** (2026-08-31)

Phase 5 gave Mizan its first working portfolio simulator, built entirely on top of Phases 1–4's
untouched foundations and calling Phase 4's `screen()` for the first time from outside a
single-ticker CLI context. It shipped `mizan/backtest/portfolio.py` (immutable `Holding`/`Portfolio`
models with type-level non-negative-quantity/non-negative-cash guards, valuation, split adjustment,
dividend crediting, and rebalance application — all governed by `raw_close`, never `adj_close`, to
avoid double-counting a dividend already credited explicitly to cash); `mizan/backtest/strategy.py`
(a `Strategy` `Protocol` and `AllocationInstruction` whose own validator makes leverage and shorting
structurally impossible at construction time, plus the one shipped reference implementation,
`EqualWeightStrategy`); `mizan/backtest/compliance_state.py` (the `HELD_COMPLIANT` →
`HELD_NONCOMPLIANT_GRACE` → `DIVESTED` state machine and its `DivestmentEvent`/`DividendEvent`
record types, reading the fiqh register's grace-period-length entry fresh at every flip); and
`mizan/backtest/clock.py` (`generate_rebalance_dates`, a no-trade daily `step()`, and `rebalance()` +
`run_backtest()` — the engine that re-screens every held-or-candidate ticker via `screen()` at every
quarterly boundary, force-liquidates any ticker whose grace countdown reaches zero, and — this
phase's central design decision — partitions the portfolio into frozen (in-grace) and workable
holdings before ever consulting the strategy, so a flipped ticker survives its grace period
untouched instead of being force-sold one rebalance too early). `mizan/cli/backtest.py` added the
`backtest` subcommand, wired into `mizan/cli/main.py` with the same one-line registration convention
every prior phase used. One live external-fact verification was performed and logged in
`docs/modernization_log.md` §6.2b: Tiingo's `splitFactor` arithmetic direction (multiplier applied
to held share count, confirmed against Tiingo's own documentation and a real worked example),
resolving the one build-time verification item `PHASE_5_SPEC.md` §0.1 explicitly flagged rather than
assumed. `tests/fixtures/synthetic_universe.py` gained one additive fixture ticker, `ZZFLIP01`,
engineered to flip verdicts across a real `screen()` call at different `as_of_date`s using the same
multiple-facts-under-one-tag mechanism Phase 4's `ZZLOOKAHEAD01` had already established and proven
— filling in, via a sound already-verified pattern, for `PHASE_5_SPEC.md`'s own "§6e" section, which
this phase's comprehension pass found is referenced nine times in the spec but was never actually
written. `pyproject.toml` was not modified — Phase 5 introduces zero new third-party dependencies.
Five new test files added 81 tests (340 total, all passing) covering portfolio arithmetic and
validation, strategy contract enforcement, the full compliance-state transition table including the
no-un-flip-edge rule, the frozen/workable partition, a call-counting guard proving every holding is
re-screened every rebalance, an end-to-end `ZZFLIP01` flip→grace→divest run, and CLI dispatch/HALT
behaviour. `ruff check mizan tests` is clean under the pinned `ruff==0.16.5` with no new noqa
suppressions, and `mypy --strict mizan tests` is fully clean inside the project's `.venv` (54 files).
The real ~100-ticker curated universe still does not exist — Phase 5, like Phase 4, only proves its
mechanism works against synthetic fixture data — and no purification arithmetic or reporting logic
was written; those remain Phases 6 and 7.

**Phase 6 — Purification Engine (side-ledger)** (2026-08-31)

Phase 6 gave Mizan its first working purification arithmetic, built entirely on top of Phases 1–5's
untouched foundations and consuming a completed `BacktestResult` for the first time as a
post-processing pass rather than participating in the daily event loop. It shipped a new top-level
package, `mizan/purification/` (a deliberate, cited deviation from `MASTER_PRD.md` §9.4's/
`PHASE_5_SPEC.md`'s own diagrammed single-file `mizan/backtest/purification.py`), with
`mizan/purification/ledger.py` (Fork A trigger + Fork B side-ledger accrual — `DividendPurification
Entry`/`PurificationLedger` models, `purify_dividend`'s date-pinned ratio re-derivation via a fresh
`screen()` call at the `VerdictObservation` active on each dividend's own `ex_date` — never the
backtest's most-recent screen — including a documented last-Mixed-ratio fallback for a dividend paid
during a ticker's grace window, and `purify_backtest_result`, the phase's canonical entry point) and
`mizan/purification/attribution.py` (Fork C — `DivestmentPurificationEntry` and
`compute_divestment_attribution`, computing `max(0.0, quantity_liquidated * (price_at_divest -
price_at_flip))` over a forced divestment's exact flip-to-divest window, gated entirely by
`fiqh_params.purify_capital_gains.value`). `mizan/cli/backtest.py` was modified additively: purified
results feed a new stdout summary (purification liability, gross return, net-of-purification return,
and one line per purified dividend/divestment) — and, during the build, the executor found and fixed
a genuine connection-lifetime bug in the spec's own illustrative insertion point (`PHASE_6_SPEC.md`
§4.3's literal instruction would have called `purify_backtest_result` after Phase 5's own
`with db.connect(...) as con:` block had already closed `con`; the shipped code instead moved the
purify call inside the still-open connection's scope). `tests/fixtures/synthetic_universe.py` gained
one additive field (`PriceBarFixture.div_cash`, defaulting `0.0`) and three additive tickers
(`ZZMIXED_RATIODRIFT01`, a Mixed-verdict ticker whose ratio drifts 2%→4% between two dividends,
isolating the date-pinning anti-undercount property; `ZZPURE_DIV01`, proving a Pure-verdict dividend
produces zero ledger entries, not a zero-amount one; `ZZDIVEST_APPREC01`, structurally identical to
`ZZFLIP01`'s flip/divest mechanism but with genuine `100.0→130.0` price appreciation over the
non-compliant window for Fork C to attribute) — no existing fixture ticker's own fields were changed.
`pyproject.toml` was not modified — Phase 6 introduces zero new third-party dependencies. Two new test
files plus one additive case in `tests/test_cli_backtest.py` added 25 tests (365 total, all passing)
covering the ratio-drift anti-undercount property, Pure-verdict zero-entry behaviour, the grace-window
ratio fallback, the Fork A/C `purify_capital_gains` gate (toggled via `model_copy`, proving the gate
is read from config rather than hardcoded), gross-vs-net-of-purification distinctness (and their
required equality when the ledger is empty), lossless `.model_dump()`/`.model_validate()` round-
tripping, an "only `purification_ledger` changes" isolation check against every other `BacktestResult`
field, a dividend-cash reconciliation pass, caller-supplied `con`/`cache_dir` reuse, `MizanBaseModel`
inheritance, and every LLM/DB-write/boundary-crossing/premature-import boundary grep restated as a
test. `ruff check mizan tests` is clean under the pinned `ruff==0.16.5` with no new noqa suppressions,
and `mypy --strict mizan tests` is fully clean inside the project's `.venv` (59 files, up from 54).
`BacktestResult.purification_ledger`'s own declared type (`dict[str, object] | None = None`) is
confirmed byte-for-byte unchanged — Phase 6 populates the placeholder via a typed model's
`.model_dump()` round trip rather than narrowing its type, exactly as Phase 5's own spec had already
decided on Phase 6's behalf. The real ~100-ticker curated universe still does not exist — Phase 6,
like every phase before it, only proves its mechanism works against synthetic fixture data — and
Mizan still implements no actual charitable-donation mechanism of any kind; `purification_liability`
is a computed, tracked number only. No reporting or chart logic was written; that remains Phase 7's
job.
