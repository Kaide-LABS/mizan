# COMPREHENSION.md — Mizan

Written after Phase 5 ("Backtest Engine & Compliance-Flip State Machine") was reviewed and approved.
Sections 1–6 below describe the repository as it exists right now — Phase 1 ("Foundation & Config"),
Phase 2 ("Ingestion & Raw Cache"), Phase 3 ("Normalization & DuckDB Store"), Phase 4 ("Screening
Engine"), and Phase 5 combined — grounded in the code read directly this pass, not in what any spec
or prior handoff claimed. The Phase Log at the bottom is append-only; Phase 1's, Phase 2's, Phase
3's, and Phase 4's entries are preserved untouched below the new Phase 5 entry.

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

**Phase 5, the subject of this update, is where Mizan stops answering "is this company halal
right now?" and starts answering "what would have happened if I'd actually held a portfolio of
halal stocks over time?"** Given a starting cash amount and a strategy (a rule for picking which
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
`ZZFLIP01`, etc.) Phase 4 built — the real ~100-ticker universe of actual companies a person would
want to backtest against still does not exist anywhere in this repository.** Phase 5 proves the
mechanism (the quarterly clock, the grace period, the re-screening) works correctly against
synthetic data engineered to exercise it; it does not, and was never supposed to, produce a
trustworthy backtest result for any real stock.

What exists after Phase 5: the settled/disputed rule registry from Phase 1; the data-pulling
pipeline from Phase 2; the typed local database from Phase 3; the working compliance screen from
Phase 4; and now, new this phase, a working portfolio simulator that can run a multi-year, multi-
ticker backtest end to end — deploying cash, marking a portfolio to market daily, re-screening every
holding every quarter, and enforcing the flip-grace-divest discipline automatically — still with no
purification math (that is Phase 6's job) and no report or chart (Phase 7's job).

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
├── screening/                      # the whole package is Phase 4's, untouched by Phase 5's diff
│   ├── __init__.py                 # empty, package marker only
│   ├── business_activity.py        # SIC-code first-pass tier classifier + pluggable, ships-empty override map
│   ├── financial_ratios.py         # the 30/30/5 ratio arithmetic, pure functions over already-resolved floats
│   └── verdict.py                  # screen(), the canonical entry point — Phase 5 imports and calls this, never edits it
├── backtest/                       # NEW this phase — the whole package is new
│   ├── __init__.py                 # NEW — empty, package marker only (mizan/screening/__init__.py precedent)
│   ├── portfolio.py                # NEW — Holding/Portfolio models, valuation, split/dividend bookkeeping,
│   │                                #        INVARIANTS.cash_yield read site (PHASE_5_SPEC.md §3.1, §4.1, §6a)
│   ├── strategy.py                 # NEW — Strategy Protocol + AllocationInstruction, structurally confined to
│   │                                #        compliant tickers (§3.2, §4.2, §6c)
│   ├── compliance_state.py         # NEW — the flip→grace→divest state machine + DivestmentEvent/DividendEvent
│   │                                #        (§3.3, §4.4, §6c)
│   └── clock.py                    # NEW — generate_rebalance_dates, step(), rebalance(), run_backtest() — the
│                                    #        canonical Phase 5 entry point (§3.4, §4.3, §6b, §6c)
└── cli/
    ├── __init__.py                # empty
    ├── main.py                    # `mizan` console-script entrypoint — boot-check-first dispatcher (MODIFIED this
    │                               #  phase: registers `backtest`, one import + one call-site line)
    ├── ingest.py                  # the `ingest` subcommand (Phase 2, untouched this phase)
    ├── normalize.py               # the `normalize` subcommand (Phase 3, untouched this phase)
    ├── screen.py                  # the `screen` subcommand (Phase 4, untouched this phase)
    └── backtest.py                # NEW this phase — the `backtest` subcommand (§4.5)
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
│   └── synthetic_universe.py       # MODIFIED this phase (additive only) — Phase 4's ~12 SYNTHETIC fixture
│                                    #  tickers PLUS one new ticker, `ZZFLIP01`, added this phase (see §3/§4 below)
├── test_screening_business_activity.py  # Phase 4, untouched
├── test_screening_financial_ratios.py   # Phase 4, untouched
├── test_screening_verdict.py             # Phase 4, untouched
├── test_cli_screen.py                    # Phase 4, untouched
├── test_backtest_portfolio.py            # NEW this phase — Holding/Portfolio validation, apply_split direction,
│                                          #  apply_allocation liquidation/funding math, cash-floor guard
├── test_backtest_strategy.py             # NEW this phase — AllocationInstruction long-only/fully-funded
│                                          #  validation, EqualWeightStrategy behaviour
├── test_backtest_compliance_state.py     # NEW this phase — the transition() state table, grace countdown,
│                                          #  no-un-flip-edge behaviour, DIVESTED-called-again assertion
├── test_backtest_clock.py                # NEW this phase — generate_rebalance_dates, step(), the frozen/workable
│                                          #  partition, the re-screen-every-holding-every-rebalance call-count
│                                          #  guard, ZZFLIP01 end-to-end flip→grace→divest
└── test_cli_backtest.py                  # NEW this phase — CLI arg parsing, boot-gate-first dispatch, HALT
                                           #  behaviour, read-only DuckDB connection
.env.example                       # TIINGO_API_TOKEN placeholder template, never a real credential
pyproject.toml                    # project metadata, exact dependency version pins, mypy/ruff/pytest config, CLI entry points (UNCHANGED this phase)
docs/modernization_log.md         # a running log of exactly which external tool/library versions and API contracts were verified and when (MODIFIED this phase — §6.2b, Tiingo splitFactor direction)
.gitignore                        # MODIFIED this phase — added `.coverage` (housekeeping, commit 4559e0e, not part of Phase 5's own implementation commit)
PHASE_5_SPEC.md                   # NEW this phase — the Phase 5 build contract (1070 lines)
```

**How the Phase 5 pieces connect, confirmed by direct read of every file this pass:**

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

**Phase 1–4 architecture, carried forward unchanged (re-confirmed this pass by diff, not re-read file
by file since the owning code is untouched):** `git diff e9a62c3..0060cfd -- mizan/config/
mizan/core/` remains empty (Phase 1 untouched); `mizan/data/` (Phase 2/3) and `mizan/screening/`
(Phase 4) do not appear in `git diff d70b29d..3f9ccc6 --stat` at all — Phase 5 is a read-only
consumer of `screen()` and `db.connect()`, exactly the same posture Phase 4 held toward Phase 3's
tables.

## 3. Decisions and tradeoffs

**Carried forward from Phase 1 (still shipped, not overturned by any later phase):**

- `FiqhParam` remains generic (`FiqhParam[T]`), not a `bool | float | str` union.
- `check_invariants()` / `check_fiqh_register()` remain hand-written, field-by-field checks.
- `StrEnum` remains the pattern for every enum in the project, including Phase 5's new
  `HoldingComplianceState` — confirmed by direct read of its definition.

**Carried forward from Phase 2/3/4 (still shipped, not overturned by Phase 5):**

- DuckDB's single-writer lock, the dedup-then-insert-with-backstop pattern, and the closed
  `RECOGNIZED_XBRL_UNITS` allow-list are all unaffected — `mizan/data/db.py` and
  `mizan/data/normalize.py` are both untouched by Phase 5's diff.
- The Phase 2/3 `# noqa: N812` findings on the `_Date` alias remain exactly two files
  (`mizan/data/models.py`, `mizan/data/normalize.py`), plus the one Phase 4 added
  (`mizan/screening/verdict.py`) — confirmed this run: `grep -rn "noqa" mizan/` still surfaces
  exactly these three `# noqa: N812` hits (plus `models.py`'s unrelated `N815` wire-format
  suppressions). Phase 5's new code (`mizan/backtest/`, `mizan/cli/backtest.py`) introduces **no**
  new `noqa` suppression anywhere.
- The real ~100-ticker universe and its hand-verified activity map still do not exist — restated
  prominently in §6 below, carried unchanged from Phase 4's own open item.

**New this phase — real decisions/resolutions, each verified directly against the code this run:**

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

## 4. Domain mechanics

**Fiqh register — carried forward from Phase 1, unchanged (`mizan/config/fiqh_params.py` is
untouched by Phase 5's diff, confirmed by re-reading it this pass), now shown with Phase 5's own new
readers added:**

| # | Figure / default | Value in code | Code's own source citation | Read by |
|---|---|---|---|---|
| 1–5 | Ratio denominator basis/smoothing, debt/interest-investments/non-permissible-income thresholds | unchanged | unchanged | Still only `mizan/screening/verdict.py`/`financial_ratios.py` (Phase 4) — Phase 5 never reads these directly, only via `screen()`'s own output |
| 6–7 | Business-activity Tier 0.5 / Tier 1 toggles | unchanged | unchanged | Still only `classify_business_activity` (Phase 4), reached transitively via `screen()` |
| **8** | **Grace period length** | **1 whole rebalance period** | `mizan/config/fiqh_params.py`'s own register entry #8, `grace_period_rebalances: FiqhParam[int](value=1, source="Common Islamic-fund practice: divest at the next rebalance after a compliance flip. Unit is WHOLE REBALANCE PERIODS, not days.", primary_source_gap="No AAOIFI-stated grace period found in the public methodology. This tunes divestment timing WITHIN the quarterly cadence; it is not a licence to change the cadence itself (ULTIMATE_PRD.md §1.1).")` — **`[UNVERIFIED / INFERENCE]`**, no AAOIFI primary-source citation | **NEW this phase** — `mizan.backtest.compliance_state.transition`, read fresh from `fiqh_params.grace_period_rebalances.value` at the moment a flip fires (never hardcoded, never cached) |
| 9–11 | Capital-gains purification, divestment attribution, purification accounting | unchanged | unchanged | Still not read anywhere — Phase 5 records the raw event data (flip/divest dates, verdict history, dividend cash) these will need, but computes no purification amount itself (`BacktestResult.purification_ledger` is always `None` this phase) |

**New this phase — the compliance-flip state machine (`MASTER_PRD.md` §7.3's own diagram,
implemented in `mizan/backtest/compliance_state.py`):**

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

**New this phase — the quarterly rebalance cadence, and why it is fixed, not configurable:**
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

**New this phase — Tiingo's `splitFactor` arithmetic direction, verified live this phase
(`docs/modernization_log.md` §6.2b, read in full):** Tiingo's own splits documentation
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
5's diff):** SEC EDGAR's 10 req/s rate limit, Tiingo's 50/hour–1,000/day request budget and
500-ticker/month cap, the `fundamentals_facts`/`price_bars` uniqueness keys, the 21-SIC-code
three-tier business-activity map, and the 30/30/5 AAOIFI ratio thresholds all remain exactly as the
Phase 4 comprehension pass described — re-confirmed present and untouched via `git diff
d70b29d..3f9ccc6 --stat`, which lists none of those files.

## 5. Honesty audit

Ran the same class of verification `PHASE_5_SPEC.md` §7 (guards)/§8 (acceptance criteria) specify,
against the code as it exists in the repository right now, this run — not trusting the spec's or the
approval commit's claim that they pass. No adversarial re-review was performed (Phase 5 is already
approved); this is a comprehension-grade honesty pass.

**Everything below passed as claimed, verified this run, inside the project's `.venv`:**
- `pytest tests/` — **340 passed** (259 carried from Phase 1–4 + 81 new this phase across the five
  new/modified backtest test files), no regressions.
- `ruff check mizan tests` — "All checks passed!", exit 0, under the pinned `ruff==0.16.5`.
- `mypy --strict mizan tests` — "Success: no issues found in 54 source files" (up from 43 in the
  Phase 4 pass — 11 new files: 5 `mizan/backtest/` modules, `mizan/cli/backtest.py`, and 5 new test
  files), inside `.venv`.
- `grep -rn "noqa" mizan/` — exactly the same three `# noqa: N812` hits Phase 4's comprehension pass
  already found (`mizan/data/models.py`, `mizan/data/normalize.py`, `mizan/screening/verdict.py`),
  plus `models.py`'s unrelated `N815` wire-format suppressions — zero new suppressions anywhere
  under `mizan/backtest/` or `mizan/cli/backtest.py`.
- `git log --format=%B a95af9b..3f9ccc6` — no `Co-Authored-By`, no "Generated with," no
  model/assistant name anywhere in the commit history spanning Phase 1 through Phase 5's
  implementation (G-AI clean).

**The `PHASE_5_SPEC.md` §6e finding, re-stated here as a finding about the SPEC's own honesty and
completeness, not just the code's (per this pass's explicit brief):** the spec references "§6e"
nine separate times (verified this run: `grep -n "§6e" PHASE_5_SPEC.md` returns lines 31, 67, 97,
116, 307, 537, 945, 947, 1035) but never actually contains a `## 6e` or `### 6e` section header
anywhere in its 1070 lines (verified this run: a header-pattern grep for `6e` returns nothing). This
is a genuine spec-completeness gap, not a code defect and not something Phase 5's own review needed
to catch as a build failure — the executor worked around it soundly (see §3 above) by reusing an
already-verified Phase 4 fixture-design pattern rather than inventing an unverified new one. Worth
flagging as a documentation-quality issue in `PHASE_5_SPEC.md` itself, independent of whether the
resulting code is correct (it is, per the passing test suite above).

**Phase 1's documented mypy/numpy environment gap, and Phase 3/4's related duckdb-import gap — both
still real, the duckdb gap now touching one more file this phase:**

- **Inside `.venv`**: clean, 0 errors, 54 files.
- **Outside `.venv`**: the original numpy stub failure (`numpy/__init__.pyi:737: error: Type
  statement is only supported in Python 3.12 and greater`) is environment-specific and unrelated to
  Phase 5's own code. The duckdb-import gap Phase 3's comprehension pass first found, and Phase 4
  extended, now also reaches `mizan/backtest/clock.py` and `tests/test_backtest_clock.py` (confirmed
  this run: both are the only two Phase 5 files that `import duckdb`, whether at module level or
  under `TYPE_CHECKING`) — one more consumer of the same already-flagged, already-documented,
  environment-specific limitation. `mizan/cli/backtest.py` itself does not import `duckdb` directly
  (it goes through `mizan.data.db.connect`), so it does not add to this list. `PHASE_3_SPEC.md`'s
  "build and verify inside `.venv`" instruction remains the correct, unchanged mitigation.

**Phase 2's AC15 noqa-enumeration finding, and Phase 4's LongTermInvestments/gambling-SIC-code open
items — re-checked this run, all still accurate, none touched by Phase 5:**

- The Phase 2 AC15 file-enumeration mismatch (`A003` absent from `mizan/data/models.py`'s own noqa
  enumeration) remains present and unaffected — `models.py` is untouched by Phase 5.
- `LongTermInvestments` (`INTEREST_BEARING_INVESTMENT_TAGS`) remains `[UNVERIFIED]` in
  `docs/modernization_log.md` §6.3 — Phase 5 does not touch `financial_ratios.py` and performed no
  new XBRL-tag verification pass.
- The `SIC_TIER_MAP` gambling/casino gap (no dedicated Tier-0 SIC 7993, since it is not a real
  SEC-assigned code; real gambling issuers file under SIC 7011/Tier 1) remains present and
  unaffected — `business_activity.py` is untouched by Phase 5.

**No new gap this pass otherwise found beyond what §3 above already surfaces as deliberate, logged
decisions** (the frozen/workable partition, the module-style import, the cash-floor guard) and what
this section names as the spec's own §6e completeness gap.

## 6. Open items

**The single most important open item, carried forward from Phase 4 and restated prominently
because Phase 5, exactly like Phase 4, only proves the mechanism works on synthetic data:**

- **The real ~100-ticker curated universe and its hand-verified business-activity override map still
  do not exist anywhere in this repository.** Phase 5 built and proved out the generic backtest
  MECHANISM — the daily clock, the quarterly rebalance trigger, the flip→grace→divest state machine,
  split/dividend bookkeeping — verified only against Phase 4's ~12 synthetic fixture tickers plus
  this phase's one addition, `ZZFLIP01` (never real issuers, CIK prefix `999...`). It did **not**
  build, and was never supposed to build, the real hand-researched activity map. Running `mizan
  backtest` against real tickers today would deploy real cash-flow logic and a real state machine
  against whatever generic SIC-first-pass verdict `screen()` produces for those tickers — not a
  trustworthy, hand-verified real-world compliance answer, exactly the same caveat Phase 4's own
  open item already stated for `mizan screen` alone.

**New this phase:**

- **`PHASE_5_SPEC.md`'s own missing §6e section** — referenced nine times, never written (§5 above).
  Worth fixing directly in the spec file before a future phase's comprehension or review pass hits
  the same nine dead cross-references and has to re-derive, as this pass did, that the gap is
  real and not a search error.
- **The frozen/workable partition adds real complexity to `rebalance()`** that a reviewer or future
  maintainer needs to understand correctly to avoid accidentally reintroducing the exact bug it
  prevents (force-selling a grace holding one rebalance early) during a future refactor — flagged
  here as a maintenance-risk item, not a defect in the current code.
- **The grace period's value (`1` rebalance) carries no AAOIFI primary-source citation** — register
  entry #8's own `primary_source_gap` field says so directly ("No AAOIFI-stated grace period found
  in the public methodology"). This is the same class of honestly-flagged inference Phase 1's
  register already carries for several other entries (e.g. the ratio denominator basis), not a new
  category of gap Phase 5 introduced.

**Carried forward, status re-checked this pass:**

- **The mypy/numpy-outside-.venv gap, and the duckdb-import gap it travels with** — still open, still
  environment-specific, still not phase-blocking; now also reaches `mizan/backtest/clock.py` and
  `tests/test_backtest_clock.py`. See §5.
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** — still open by
  design; Phase 5 touches none of them.
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged; Phase 5
  does not touch `mizan/config/fiqh_params.py`, only reads register entry #8 at runtime.
- **The Phase 2 AC15 noqa-enumeration mismatch** — still present, unaffected by Phase 5.
- **`LongTermInvestments` remains `[UNVERIFIED]`, and `SIC_TIER_MAP` still has no dedicated
  gambling/casino Tier-0 code** — both unaffected by Phase 5, since neither
  `financial_ratios.py` nor `business_activity.py` is touched.
- **Corporate-action anomaly scan is deliberately conservative and will produce false positives** —
  unchanged, still an accepted tradeoff, not a defect.
- **No real backfill has been run, and no real backtest has been run against real market data** —
  unchanged and, this phase, extended: everything verified in Phases 1–5 (and their own reviews) is
  against fixtures and synthetic data, not a full live ~100-ticker run and not a real historical
  backtest result for any actual strategy.
- **The DuckDB file remains a local, derived, regenerable artifact with no versioned migration
  path** — unchanged; Phase 5 adds no new table, column, or index (confirmed: `mizan/data/db.py` is
  untouched by this phase's diff).
- **Nothing yet computes a purification amount, and nothing yet reports or charts a backtest
  result.** `BacktestResult.purification_ledger` is always `None` this phase — Phase 5 records the
  raw event data (flip dates, divest dates, verdict history, per-dividend cash-received-plus-verdict
  records) Phase 6's purification arithmetic will need, but computes nothing from it itself. That is
  explicitly Phase 6's (`mizan/backtest/purification.py`) and Phase 7's (reporting) work, unread and
  untouched by Phase 5.

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
