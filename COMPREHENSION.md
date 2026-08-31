# COMPREHENSION.md — Mizan

Written after Phase 7 ("Reporting — static HTML + plots") was reviewed and approved. **Phase 7 is
the final phase of Mizan V1.** Sections 1–6 below describe the repository as it exists right now —
Phase 1 ("Foundation & Config") through Phase 7 combined, the complete V1 system — grounded in the
code read directly this pass, not in what any spec or prior handoff claimed. The Phase Log at the
bottom is append-only; Phase 1's through Phase 6's entries are preserved untouched below the new
Phase 7 entry.

---

## 1. Plain-language walkthrough

Mizan is a personal research tool for a single person who wants to test long-only stock-trading
strategies that follow Islamic finance rules ("halal" or "Shariah-compliant" investing), using real
historical US stock data. It is not a live trading system — no real money ever moves through it. It
is a sandbox for learning whether a rule-respecting strategy would have worked.

**With Phase 7 shipped, the full pipeline is now complete, end to end, for the first time.** In plain
language, here is what Mizan does today, start to finish: it pulls real financial data for a set of
companies you name (their filings from SEC EDGAR, their daily stock prices and dividends from
Tiingo) → it screens each one against Islamic finance rules to see if it's investable, using both a
business-activity check and a set of financial-ratio checks → it simulates holding a portfolio of the
compliant ones over time, stepping through calendar quarters, automatically selling anything that
stops being compliant only after a one-quarter grace period (never panic-selling the instant a
verdict flips) → it tracks how much of any dividend income (and, if you turn the setting on, any
price gain realized while forced out during that grace period) came from a still-impure sliver of an
otherwise-compliant company's business, and sets that amount aside in a separate running total rather
than quietly netting it out of your returns → and now, new this phase, it generates one static,
self-contained HTML webpage summarizing all of it — every dollar figure, every per-ticker verdict,
two charts, and, appearing before any of those numbers in the page itself, every caveat and every
disputed judgment call the run depended on, stated plainly rather than hidden in a README a user
would have to go looking for.

The core tension the whole project is built around, unchanged since Phase 1: which Islamic finance
rules are truly settled (no company may profit mainly from things like alcohol, gambling,
conventional interest-based banking, and so on), and which rules are genuinely disputed even among
qualified scholars (exactly how do you measure "how much debt is too much debt," expressed as a
percentage of what?). The project's design insists on keeping these two categories visibly separate
at all times: settled rules are locked in stone and cannot be changed by anyone running the software;
disputed rules are left as clearly labeled, adjustable settings, each one stamped "not yet confirmed
by a scholar," with an honest note about exactly what is uncertain. Phase 7's report is where that
separation finally becomes visible to a human being who never opens a Python file — the generated
page renders the entire eleven-row disputed-rules register, in full, on every single run.

**Walking the pipeline one phase at a time, now that all seven exist:**

Phase 1 built the foundation everything else stands on: the list of seven settled rules, the list of
eleven disputed judgment calls (each with its best current guess, a citation, and an honest note
about what's unclear), a "boot check" that refuses to even start the program if any of that
foundation looks wrong, and a handful of shared building-block definitions — including the
"caveat" concept that Phase 7 ultimately builds its entire honesty guarantee on top of.

Phase 2 taught Mizan how to go out and pull real financial data for a given stock ticker from two
sources — SEC EDGAR for company fundamentals, Tiingo for daily stock prices and dividends — and to
save every single response it gets to a local folder on disk before doing anything else with it.

Phase 3 turned those saved-but-still-raw files into something a computer program can actually query
and trust — one table for company financial facts, one table for daily stock prices, both loaded
into a real local database (DuckDB).

Phase 4 gave Mizan its first working compliance verdict: `mizan screen` runs a business-activity
check followed, if that passes, by a financial-ratio check, producing one of three verdicts — Pure,
Mixed, or Non-compliant — always with a full, human-readable trace of exactly which check drove it.

Phase 5 is where Mizan stopped answering "is this company halal right now?" and started answering
"what would have happened if I'd actually held a portfolio of halal stocks over time?" — the
quarterly-rebalance backtest engine, with its signature flip → one-quarter grace period → forced
divestment mechanic, so a stock that drifts out of compliance isn't sold the instant the numbers
move.

Phase 6 is where Mizan stopped just tracking gross portfolio value and started honestly tracking the
money that was never really "clean" in the first place — the purification side-ledger, which
computes (but never moves or donates) exactly how much of each Mixed-verdict dividend, and
optionally how much of a forced-divestment's price gain, would need to be given to charity under
AAOIFI's own rule, tracked entirely off to the side so the backtest can report two honest bottom
lines — gross return and net-of-purification return — instead of one silently blended figure.

**Phase 7, the final phase, is where all of that finally becomes something a human can actually look
at without reading Python.** It adds exactly one new capability: `mizan report`, a command that runs
the same backtest-then-purify pipeline `mizan backtest` already runs, then hands the result to a
brand-new rendering module that builds a single HTML file — no server, no database of its own, no
external image files, nothing but one file you can double-click open in any browser, anywhere,
forever, disconnected from the machine that generated it. That file always contains, in this fixed
order: every caveat active on the run, stated in full sentences, before any number appears; the
complete eleven-row disputed-rules register; the two return figures side by side, never blended into
one; a per-ticker table of what each holding's compliance history and outcome was; the full
purification-ledger detail, dividend by dividend and divestment by divestment; and two charts — a
portfolio-value line chart comparing the gross curve against the net-of-purification curve, and a bar
chart showing which tickers are actually responsible for how much of the total purification
liability. The charts are pictures (PNG images), generated by `matplotlib` and embedded directly in
the page as base64 text, not linked to separate files — the entire report, images included, is one
portable document.

Structurally, Phase 7 is designed so that the honesty behavior isn't just a documented intention —
it is close to impossible to accidentally violate in code. The function that renders a report,
`render_report`, will not even let you call it without explicitly stating which caveats apply to
this run — leave that argument out and Python itself refuses to run the program (`TypeError`), before
a single number is ever formatted into HTML. This was a deliberate choice among two reasonable
designs, discussed in §3 below; it means the "never show a number without its warning label" rule is
enforced by the type checker and by Python's own function-call machinery, not merely by a programmer
remembering to follow a convention.

**Two things worth being just as explicit about now as every earlier phase's walkthrough was, and
this is the single most important thing this final comprehension pass can say plainly.** First, the
only "strategy" that ships is still the simplest possible one — split money equally across every
compliant stock — presented as a reference implementation, not investment advice. Second, and by far
the more important honesty note for the project as a whole: **the entire seven-phase pipeline
described above genuinely works, and is genuinely tested — 406 tests pass, `mypy --strict` and
`ruff` are both clean, and this pass personally generated a real HTML report from a real run of the
real code and read its actual contents (§5 below) — but it has never once been run against real
market data for real companies.** Every test, every fixture, every report this pass looked at is
built from a small set of invented, obviously-fake ticker symbols (`ZZPURE01`, `ZZFLIP01`,
`ZZMIXED_RATIODRIFT01`, and a dozen or so others like them) engineered specifically to exercise one
mechanism each. **The single biggest remaining gap between "this runs" and "this produces a
trustworthy real-world result" is the missing real ~100-company research** — the business-activity
classifications a human being would actually have to look up, verify, and cite for real, named
companies. That research does not exist anywhere in this repository, has never been started as part
of any of the seven automated phases, and was never supposed to be — it was scoped, from Phase 4
onward, as the project owner's own future work, entirely outside what an automated phase build does.
Running `mizan report` against real tickers today would produce a real-looking, fully-caveated,
handsomely-formatted HTML page — built on a generic SIC-code first-pass classification for each real
company, not a verified one. The report's own honesty surface (the caveats banner, the fiqh register)
is exactly the mechanism that would make this limitation visible to a reader if someone did that
today; it does not make the limitation not exist.

## 2. Architecture walkthrough

Everything below is a real file in the repository, confirmed present by direct listing this pass
(`mizan/**/*.py`, read via `Glob`/`Read`, not assumed from any spec).

```
mizan/
├── __init__.py                  # empty — marks mizan as a Python package
├── py.typed                     # empty marker file so type-checkers treat the package as typed
├── config/                       # Phase 1 — untouched by every later phase's diff
│   ├── __init__.py               # empty
│   ├── invariants.py             # the 7 settled, non-negotiable rules (Invariants class + INVARIANTS singleton)
│   ├── fiqh_params.py            # the 11-row disputed-judgment-call register (FiqhParams + FIQH_PARAMS singleton)
│   └── boot_check.py             # startup checks that refuse to run if invariants.py or fiqh_params.py are broken
├── core/                          # Phase 1 — untouched by every later phase's diff
│   ├── __init__.py               # empty
│   ├── base.py                   # MizanBaseModel — the one shared base every data model in the project must use
│   ├── verdict.py                # Verdict — the three-state pass/partial/fail screening outcome (definition ONLY)
│   └── caveats.py                # Caveat enum + ResultEnvelope — the mandatory warning-label wrapper for results;
│                                  #  Phase 7's CAVEAT_DESCRIPTIONS and render_report's active_caveats parameter
│                                  #  both key directly off this module's Caveat enum, unmodified by this phase
├── data/                          # Phase 2/3 — untouched by Phase 4 through 7's diffs
│   ├── __init__.py                # empty
│   ├── models.py                  # raw wire-format row-shape schemas for EDGAR + Tiingo payloads (Phase 2)
│   ├── raw_cache.py               # shared cache-path / cache-hit / atomic-write / read helpers, both legs (Phase 2)
│   ├── ingest_edgar.py            # EDGAR client: rate limiter, header construction, CIK resolution, fetch fns (Phase 2)
│   ├── ingest_tiingo.py           # Tiingo client: request/symbol budget limiter, EOD fetch, anomaly scan (Phase 2)
│   ├── db.py                      # DuckDB connection + idempotent schema creation (Phase 3)
│   └── normalize.py               # typed row shapes + raw-cache-to-DuckDB mapping functions, incl. resolve_cik_offline (Phase 3)
├── screening/                      # Phase 4 — untouched by Phase 5 through 7's diffs
│   ├── __init__.py                 # empty, package marker only
│   ├── business_activity.py        # SIC-code first-pass tier classifier + pluggable, ships-empty override map
│   ├── financial_ratios.py         # the 30/30/5 ratio arithmetic, pure functions over already-resolved floats
│   └── verdict.py                  # screen(), the canonical entry point — Phase 5/6/7 all import and call this, none edits it
├── backtest/                       # Phase 5 — untouched by Phase 6 or Phase 7's diffs
│   ├── __init__.py                 # empty, package marker only
│   ├── portfolio.py                # Holding/Portfolio models, valuation, split/dividend bookkeeping, INVARIANTS.cash_yield read site
│   ├── strategy.py                 # Strategy Protocol + AllocationInstruction; EqualWeightStrategy, the one shipped reference strategy
│   ├── compliance_state.py         # the flip→grace→divest state machine + DivestmentEvent/DividendEvent —
│   │                                #  Phase 6/7 both import ComplianceStateRecord/DividendEvent from here, neither edits it
│   └── clock.py                    # generate_rebalance_dates, step(), rebalance(), run_backtest() — Phase 6/7 both
│                                    #  import BacktestResult/DailySnapshot from here, neither edits it;
│                                    #  `purification_ledger: dict[str, object] | None = None` field declaration
│                                    #  is byte-for-byte unchanged since Phase 5, confirmed this pass by diff read
├── purification/                   # Phase 6 — untouched by Phase 7's diff
│   ├── __init__.py                 # empty, package marker only
│   ├── ledger.py                   # DividendPurificationEntry/PurificationLedger models, purify_dividend,
│   │                                #  purify_backtest_result — Fork A trigger + Fork B side-ledger accrual;
│   │                                #  Phase 7's ReportInput/render_report/plots.py all consume PurificationLedger,
│   │                                #  none edits this module
│   └── attribution.py              # DivestmentPurificationEntry model, compute_divestment_attribution — Fork C
│                                    #  forced-divestment price-appreciation attribution; also untouched by Phase 7
├── reporting/                      # NEW this phase — the whole package is new (PHASE_7_SPEC.md §1)
│   ├── __init__.py                 # NEW — empty, package marker only (mizan/purification/__init__.py precedent), 5 lines
│   ├── report.py                   # NEW — 306 lines. ReportInput, CAVEAT_DESCRIPTIONS, render_report() and its six
│   │                                #  section-rendering helpers (render_caveats_banner, render_fiqh_register,
│   │                                #  render_return_summary, render_ticker_summary, render_purification_detail,
│   │                                #  the private _render_plots_section) — THE canonical Phase 7 entry point
│   └── plots.py                    # NEW — 131 lines. matplotlib.use("Agg") set at import time, then
│                                    #  render_equity_curve_plot() and render_purification_by_ticker_plot(),
│                                    #  each returning raw PNG bytes
└── cli/
    ├── __init__.py                # empty
    ├── main.py                    # `mizan` console-script entrypoint — boot-check-first dispatcher; MODIFIED
    │                               #  this phase (additively): one new import, one new `report_cli.add_subparser(subparsers)`
    │                               #  registration line — every other line byte-for-byte unchanged (confirmed by diff read)
    ├── ingest.py                  # the `ingest` subcommand (Phase 2, untouched this phase)
    ├── normalize.py               # the `normalize` subcommand (Phase 3, untouched this phase)
    ├── screen.py                  # the `screen` subcommand (Phase 4, untouched this phase)
    ├── backtest.py                # the `backtest` subcommand (Phase 5, modified additively by Phase 6; untouched by Phase 7 —
    │                               #  confirmed absent from `git diff 6edb9b5..804b333 --stat`)
    └── report.py                  # NEW this phase — 137 lines. the `report` subcommand, completing the
                                    #  `ingest | screen | backtest | report` verb set MASTER_PRD.md §9.4 names
tests/
├── __init__.py                   # empty
├── (Phase 1–6's 24 test files, all untouched by this phase's diff — proving boot-gate rejection,
│    fiqh-register completeness, cache idempotency, rate-limiter/budget timing, schema idempotency,
│    unit rejection, screening verdicts, portfolio/strategy/compliance-state/clock behaviour, and
│    every purification-ledger/attribution property Phase 6's own comprehension pass already
│    catalogued in detail — see that phase's own entry in the Phase Log below for the full list)
├── fixtures/
│   ├── __init__.py                 # package marker
│   └── synthetic_universe.py       # UNTOUCHED this phase (confirmed absent from the diff stat) — the same sixteen
│                                    #  synthetic fixture tickers Phase 6 left it with; Phase 7 adds no new fixture
│                                    #  ticker, needing none (PHASE_7_SPEC.md §8's own stated reason: every plot/table
│                                    #  this phase renders is a presentation of data the existing fixture set already
│                                    #  exercises)
├── test_reporting_report.py       # NEW this phase — tests mizan/reporting/report.py directly
├── test_reporting_plots.py        # NEW this phase — tests mizan/reporting/plots.py directly
└── test_cli_report.py             # NEW this phase — tests mizan/cli/report.py and its wiring into mizan/cli/main.py;
                                    #  561 lines, the largest of the three new test files, including the two real
                                    #  end-to-end tests this pass re-ran independently (§5 below)
.env.example                       # TIINGO_API_TOKEN placeholder template, never a real credential
pyproject.toml                     # MODIFIED this phase: matplotlib==3.11.1 promoted from the now-removed
                                    #  [project.optional-dependencies].report group into [project.dependencies];
                                    #  one new [[tool.mypy.overrides]] block for module = "numpy.*" (§3 below)
docs/modernization_log.md          # MODIFIED this phase: one new dated (2026-08-31) entry, §6.2c, logging the
                                    #  live re-verification of matplotlib's pin ahead of its promotion to a real dependency
.gitignore                         # unchanged this phase
PHASE_1_SPEC.md … PHASE_6_SPEC.md  # unchanged this phase, prior phases' build contracts
PHASE_7_SPEC.md                    # NEW this phase — the Phase 7 build contract (818 lines), read in full this pass
```

**Confirmed this pass, directly, not merely asserted:** `git diff 6edb9b5..804b333 --stat` (Phase 6's
own review-approval commit to Phase 7's implementation commit) touches exactly twelve files:
`COMPREHENSION.md` (Phase 6's own comprehension pass, superseded by this document), `PHASE_7_SPEC.md`
(new), `docs/modernization_log.md`, `mizan/cli/main.py`, `mizan/cli/report.py` (new),
`mizan/reporting/__init__.py` (new), `mizan/reporting/plots.py` (new), `mizan/reporting/report.py`
(new), `pyproject.toml`, `tests/test_cli_report.py` (new), `tests/test_reporting_plots.py` (new),
`tests/test_reporting_report.py` (new) — a total of +3,054/−162 lines. **No file under
`mizan/config/`, `mizan/core/`, `mizan/data/`, `mizan/screening/`, `mizan/backtest/`, or
`mizan/purification/` appears anywhere in that diff** — Phase 7 is a pure, read-only consumer of
every one of those packages' public surfaces (`BacktestResult`/`DailySnapshot` from `backtest/clock.py`,
`ComplianceStateRecord` from `backtest/compliance_state.py`, `PurificationLedger`/
`DividendPurificationEntry` from `purification/ledger.py`, `DivestmentPurificationEntry` from
`purification/attribution.py`, `FiqhParams`/`FIQH_PARAMS` from `config/fiqh_params.py`, `Caveat` from
`core/caveats.py`, `MizanBaseModel` from `core/base.py`), exactly as `PHASE_7_SPEC.md` §1 states this
phase's own posture to be — stricter than every prior phase since Phase 3, each of which modified at
least one earlier phase's file additively; Phase 7 modifies none.

**How the Phase 7 pieces connect, confirmed by direct read of every file this pass:**

- **`mizan/reporting/report.py`** defines `ReportInput` (a `MizanBaseModel` wrapping
  `backtest_result: BacktestResult` and `fiqh_params: FiqhParams`, with a `model_validator(mode="after")`
  that raises `ValueError` if `backtest_result.purification_ledger is None` — refusing to construct a
  report input from a raw, pre-purification `run_backtest()` result), the module-level
  `CAVEAT_DESCRIPTIONS: dict[Caveat, str]` registry (one full-sentence description per `Caveat` member,
  completeness-asserted against `set(Caveat)` at import time — an `AssertionError` on
  `import mizan.reporting.report` if a future `Caveat` member is ever added without a matching
  description here), and six rendering functions: `render_caveats_banner`, `render_fiqh_register`
  (asserts exactly 11 rows, `AssertionError` otherwise), `render_return_summary`, `render_ticker_summary`,
  `render_purification_detail`, and the private `_render_plots_section` (base64-encodes both PNGs via
  `base64.b64encode(...).decode("ascii")` into `data:image/png;base64,...` `<img src>` values). All six
  are composed, in this fixed order, by `render_report(data: ReportInput, *, active_caveats:
  tuple[Caveat, ...]) -> str` (lines 269–305) — the module's own canonical entry point, returning one
  complete `<!DOCTYPE html>` document as a `str`. Every dynamic value interpolated anywhere in the
  module passes through a private `_escape` helper (`html.escape(value, quote=False)`, lines 31–39) —
  see §3 below for why `quote=False` is a deliberate, reasoned choice, not an oversight.
- **`mizan/reporting/plots.py`** calls `matplotlib.use("Agg")` (line 19) before importing `pyplot`
  (line 21) — at module import time, before any figure is ever created — then defines
  `render_equity_curve_plot(daily_snapshots, ledger) -> bytes` and
  `render_purification_by_ticker_plot(ledger) -> bytes`. Both build a `matplotlib` figure, branch
  explicitly on the empty-input case (rendering an annotated "No trading days in this backtest
  window."/"No purification liability in this run." placeholder figure rather than raising or
  indexing into an empty sequence), write to an in-memory `io.BytesIO()` buffer via
  `figure.savefig(buffer, format="png")`, call `plt.close(figure)` (to avoid matplotlib's own
  figure-object accumulation across repeated calls within one process — relevant because a test suite
  calling these functions dozens of times must not leak figures, confirmed by a private helper,
  `_cumulative_purification_liability_as_of`, lines 30–42, that reconstructs the day-by-day running
  purification-liability series privately and freshly on every call — never a persisted intermediate,
  exactly matching `PHASE_6_SPEC.md` §6d's own explicit anticipation that this reconstruction would be
  "squarely Phase 7's reporting concern"), and return `buffer.getvalue()`.
- **`mizan/cli/report.py`** registers the `report` subcommand (`add_subparser`, flag set identical to
  `mizan backtest`'s own through `--overrides-path`, plus one new `--output-path` flag — no
  `--no-plots` suppression flag exists anywhere, deliberately, per PHASE_7_SPEC.md §9). `run(args)`
  opens one read-only DuckDB connection (`db.connect(args.db_path, read_only=True)`), loads the
  override map, and — still inside that connection's `with` block — calls `run_backtest(...)` then
  `purify_backtest_result(...)`, reusing the exact same `con`/`args.cache_dir`/`overrides` local
  variables across both calls (the same discipline Phase 6's `mizan/cli/backtest.py` already
  established, and the same connection-lifetime lesson Phase 6's own comprehension pass flagged as a
  standing note for future spec authors — heeded here: this phase's spec's own pseudocode already
  placed the construction correctly inside the `with` block, and the shipped code follows it exactly,
  confirmed by direct read), then constructs `ReportInput(backtest_result=result,
  fiqh_params=FIQH_PARAMS)` and calls `render_report(report_input,
  active_caveats=envelope.active_caveats)` — reusing `run_backtest`'s own returned
  `envelope.active_caveats` tuple verbatim, never inventing a fresh caveat set. Writes the returned
  HTML `str` to `args.output_path` via `Path.write_text(..., encoding="utf-8")`, prints the output path
  and final portfolio value, returns `0`. Catches the same four per-ticker/whole-backtest-shaped
  exceptions `mizan backtest` catches (`CikResolutionError`, `SicResolutionError`,
  `NotNormalizedError`, `InsufficientDataError`), printing `HALT: ...` to stderr and returning `1`.
- **`mizan/cli/main.py`** gained one new import (`from mizan.cli import report as report_cli`) and one
  new registration line (`report_cli.add_subparser(subparsers)`) — confirmed by direct diff read;
  every other line, including the boot-check-first dispatch that has run unchanged since Phase 2, is
  byte-for-byte identical to Phase 6's own version. `mizan --help` now lists all four verbs:
  `ingest`, `screen`, `backtest`, `report` — the complete `cli/` verb set `MASTER_PRD.md` §9.4's own
  module-boundary diagram names, confirmed complete this pass by running `mizan --help` directly (via
  `python -m mizan.cli.main` inside `.venv`, §5 below).
- **`pyproject.toml`** — `matplotlib==3.11.1` moved from `[project.optional-dependencies].report`
  (now-removed entirely) into `[project.dependencies]`; one new `[[tool.mypy.overrides]]` block
  (`module = "numpy.*"`, `follow_imports = "skip"`, `follow_imports_for_stubs = true`) added directly
  beneath the pre-existing `pyarrow.*` override. Both changes confirmed by direct diff read (§3 below
  for the reasoning and this pass's own independent empirical verification of the mypy override).
- **`docs/modernization_log.md`** gained one new dated entry, §6.2c (2026-08-31): a live re-fetch of
  `https://pypi.org/project/matplotlib/` confirming the pin stays exactly `3.11.1` (uploaded
  2026-07-18, unchanged from the prior day's Step-10 pass) — logged because this is the pin's first
  *load-bearing* verification (matplotlib had been forward-declared, unused, since Phase 1; this is
  the first phase that actually imports it).

**Phase 1–6 architecture, carried forward unchanged (re-confirmed this pass by diff, not re-read file
by file since the owning code is untouched):** `mizan/config/`, `mizan/core/`, `mizan/data/`,
`mizan/screening/`, every file under `mizan/backtest/`, and every file under `mizan/purification/` do
not appear in `git diff 6edb9b5..804b333 --stat` at all. `mizan/cli/backtest.py`, `mizan/cli/screen.py`,
`mizan/cli/ingest.py`, and `mizan/cli/normalize.py` likewise do not appear. The detailed per-file
architecture descriptions Phase 5's and Phase 6's own comprehension passes already gave for
`mizan/backtest/portfolio.py`, `strategy.py`, `compliance_state.py`, `clock.py`,
`mizan/purification/ledger.py`, `attribution.py`, and `mizan/cli/backtest.py` remain accurate without
re-derivation — see the Phase Log below for the phase-by-phase summaries, and §3/§4 below for the
domain-mechanics and decision content still worth restating in this final combined pass.

## 3. Decisions and tradeoffs

This section is long by now, spanning seven phases — grouped by phase below, per the operator note
in Phase 6's own version of this document, since nothing here has been overturned, only added to.

**Carried forward from Phase 1 (still shipped, not overturned by any later phase):**

- `FiqhParam` remains generic (`FiqhParam[T]`), not a `bool | float | str` union.
- `check_invariants()` / `check_fiqh_register()` remain hand-written, field-by-field checks.
- `StrEnum` remains the pattern for every enum in the project, from Phase 5's `HoldingComplianceState`
  through Phase 7's own use of `Caveat` (unmodified, still a `StrEnum`, confirmed by direct read of
  `mizan/core/caveats.py` this pass).

**Carried forward from Phase 2/3/4 (still shipped, not overturned by any later phase):**

- DuckDB's single-writer lock, the dedup-then-insert-with-backstop pattern, and the closed
  `RECOGNIZED_XBRL_UNITS` allow-list are all unaffected — `mizan/data/db.py` and
  `mizan/data/normalize.py` are untouched since Phase 3.
- The Phase 2/3/4 `# noqa: N812` findings on the `_Date` alias remain exactly three files
  (`mizan/data/models.py`, `mizan/data/normalize.py`, `mizan/screening/verdict.py`) — confirmed this
  run: `grep -rn "noqa" mizan/` still surfaces exactly these three hits plus `models.py`'s unrelated
  `N815` wire-format suppressions. **Phase 7's new code introduces zero new `noqa` suppression
  anywhere** — confirmed by the same grep, run fresh against the full tree this pass.
- The real ~100-ticker universe and its hand-verified activity map still do not exist — restated
  prominently in §1 and §6 below, carried unchanged since Phase 4's own open item.

**Carried forward from Phase 5 (still shipped, not overturned by Phase 6 or Phase 7):**

- **The frozen/workable portfolio partition** — the mechanism that makes the grace period actually
  work. `rebalance()` (`mizan/backtest/clock.py`) partitions the post-divestment portfolio into a
  **frozen** dict (every ticker currently in `HELD_NONCOMPLIANT_GRACE`, held back entirely, merged
  back untouched after the strategy acts) and a **workable** portfolio (cash + everything else,
  actually shown to `strategy.select()`) before ever consulting the strategy — avoiding the silent
  bug a naive "screen, then hand the whole portfolio to the strategy" implementation would have: a
  just-flipped ticker is both un-nameable by the strategy (which only ever sees `compliant_tickers`)
  and therefore immediately liquidated by `apply_allocation`'s own liquidate-if-absent rule, one full
  grace period too early.
- **`mizan.screening.verdict` is imported as a module** (`from mizan.screening import verdict as
  screening_verdict`), never as a bare `screen` name — load-bearing for
  `test_every_holding_is_rescreened_every_rebalance`'s own `monkeypatch.setattr` call-counting test,
  which would silently under-count against a bare-name import bound at load time.
- **`PHASE_5_SPEC.md`'s own missing §6e section** — still referenced nine times, still never written
  (re-confirmed this pass, unchanged since Phase 6's own re-check: `grep -n "§6e" PHASE_5_SPEC.md`
  still returns the same nine lines).
- **`apply_allocation`'s cash floor** (`max(cash, 0.0)`) remains a floating-point-noise guard against
  `AllocationInstruction`'s own `1.0 + 1e-9` weight-sum tolerance, not a relaxation of the
  non-negative-cash invariant.

**Carried forward from Phase 6 (still shipped, not overturned by Phase 7 — re-confirmed this pass
since no file under `mizan/purification/` appears in `git diff 6edb9b5..804b333 --stat`):**

- **The date-pinned-ratio discipline** — `purify_dividend` finds the `VerdictObservation` with the
  largest `as_of_date <= dividend_event.ex_date` in the ticker's own `verdict_history`, then
  re-invokes `screen()` at that exact date rather than trusting the backtest's own most-recent
  screen — avoiding a genuine purification undercount/overcount for any ticker whose ratio drifts
  over time. Phase 7's own `render_purification_detail` and `render_equity_curve_plot` both display
  the *results* of this re-derivation (each `DividendPurificationEntry.ratio_used`, and the day-by-day
  reconstructed liability curve) but never re-run the derivation themselves — a pure, read-only
  consumer, confirmed by direct read of both modules this pass.
- **The Fork A/Fork C gating resolution** — `fiqh_params.purify_capital_gains.value` gates both
  dividend purification's capital-gains scope and forced-divestment price-appreciation attribution, a
  reasoned-not-verbatim textual inference from `MASTER_PRD.md` §8, named honestly as such rather than
  presented as settled.
- **The connection-lifetime bug the Phase 6 executor caught** relative to `PHASE_6_SPEC.md` §4.3's own
  illustrative insertion point — `mizan/cli/backtest.py`'s purify call was moved inside the still-open
  `with db.connect(...)` block rather than after it closed, a correctness fix over the spec's own
  pseudocode. **This lesson visibly informed Phase 7's own spec**: `PHASE_7_SPEC.md` §4.3's own
  pseudocode explicitly cites this exact prior finding ("mirroring Phase 6's own connection-lifetime
  fix requires") and places the construction correctly from the start — confirmed by direct read of
  both the spec text and the shipped `mizan/cli/report.py`, which needed no equivalent fix this phase.
- **The module-layout deviation** — `mizan/purification/` (a two-file top-level package) instead of
  the single `mizan/backtest/purification.py` `MASTER_PRD.md` §9.4's diagram named. Still real, still
  making `ULTIMATE_PRD.md` §5 check 5's own literal grep line stale, still not corrected in
  `ULTIMATE_PRD.md` itself as of this pass.

**New this phase — Phase 7's own real decisions, each verified directly against the code this run:**

- **The caveat-mandatory-at-the-function-signature design — the single most important decision in this
  phase, and the mechanism that makes the whole project's central honesty promise a type error rather
  than a convention.** `ULTIMATE_PRD.md` §2.2 states the requirement in prose: "the reporter takes
  this tuple as its only render input — there is no code path that renders a number without its
  caveat set attached." Two legitimate designs were available to satisfy that prose. **Design A**:
  wrap the whole report payload in a `mizan.core.caveats.ResultEnvelope` (reusing Phase 1's own type
  verbatim), reading `envelope.active_caveats` inside `render_report`. **Design B** (the one shipped):
  give `render_report` itself a required, keyword-only `active_caveats: tuple[Caveat, ...]` parameter
  with no default, `ReportInput` carrying no caveat field of its own at all. The difference is not
  cosmetic. Under Design A, omitting the caveat set fails at `ResultEnvelope` *construction* time — a
  `pydantic.ValidationError` raised wherever the envelope happens to get built, one layer removed from
  the actual render call. Under Design B, `render_report(data)` — omitting the keyword entirely — raises
  `TypeError: render_report() missing 1 required keyword-only argument: 'active_caveats'` **at the exact
  call site**, before `render_report`'s own body ever executes, and `mypy --strict` independently flags
  any call site missing the keyword as a *static* error, before the program is ever run at all. This
  pass confirmed both halves of that claim directly: `pytest.raises(TypeError)` around a positional-only
  call is one of the tests in `tests/test_reporting_report.py` (re-run this pass, passing, §5 below),
  and `mypy --strict mizan tests` — re-run this pass — finds the one real call site in
  `mizan/cli/report.py` correctly supplying the keyword and would flag it as a static error if it ever
  stopped. **Tradeoff:** Design B reproduces `ResultEnvelope.active_caveats`'s own "no default, an
  explicit empty tuple is a valid, deliberate, if unusual choice — silent omission is not" precedent at
  a different layer (the function signature) than Phase 1 originally established it (the pydantic
  model field) specifically because that is the layer where `ULTIMATE_PRD.md` §4.8's own stated
  enforcement bar ("should be a type error, caught before runtime") actually lives — a genuinely
  stronger reading of the same honesty requirement, chosen deliberately over the more literal
  "wrap it in the existing envelope type" reading.
- **Inline base64-embedded PNGs, never separate image files — the single-portable-file tradeoff, stated
  plainly rather than left implicit.** `_render_plots_section` (`mizan/reporting/report.py` lines
  250–266) base64-encodes both plot PNGs directly into `data:image/png;base64,...` `<img src="...">`
  values inside the one HTML document `render_report` returns; `mizan/cli/report.py`'s `run()` writes
  exactly one file to `--output-path`, confirmed this pass by directly generating a real report and
  observing the output directory (§5 below): no sibling `_files/`, `assets/`, or `.png` file appeared
  anywhere. **The tradeoff, named rather than hidden:** a single self-contained file that can be
  copied, emailed, or opened by double-click from any working directory, at the cost of base64 inflating
  binary size by roughly a third versus a raw file reference (and, more generally, giving up the
  browser-cacheability and independent updatability a separate-file approach would keep) — an accepted
  cost at this phase's own scope (two plots, tens of KB each against a synthetic fixture; the real
  report this pass generated was 64,341 bytes total, well within any reasonable single-file budget),
  matching Mizan's own single-user, no-hosting-surface posture (`MASTER_PRD.md` §9) more closely than a
  multi-file bundle would.
- **The `numpy` mypy-override fix, and why it does not weaken Mizan's own type-checking.** Promoting
  `matplotlib` to a real dependency (§2.1 below) transitively pulls in `numpy` as a dependency of
  matplotlib's own type stubs — and `numpy`'s own `__init__.pyi` uses the PEP 695 `type` statement
  syntax (confirmed this pass, directly: `numpy/__init__.pyi` line 737, `type _Falsy = L[False, 0] |
  bool_[L[False]]`), which requires a Python **3.12+** *parser* to even read, regardless of which
  Python interpreter is actually running mypy — and this project's own `pyproject.toml` pins
  `python_version = "3.11"` for mypy's own target-version checking, unchanged. The new
  `[[tool.mypy.overrides]]` block (`module = "numpy.*"`, `follow_imports = "skip"`,
  `follow_imports_for_stubs = true`) tells mypy to stop parsing numpy's own stub *bodies* at all,
  treating numpy's public interface as `Any` — **critically, this override is scoped to the string
  `"numpy.*"` alone**, exactly the same scoping the pre-existing `pyarrow.*` override already used one
  block above it in the same file. It does not relax `--strict` for any module Mizan itself owns, and
  `mizan/reporting/plots.py` never imports `numpy` directly at all (confirmed by direct read — the only
  import is `matplotlib`/`matplotlib.pyplot`; `numpy` is reached only via matplotlib's own internal
  type-stub graph, invisible to `plots.py`'s own source). This pass did not merely trust the module's
  own docstring reasoning — it independently reproduced and confirmed the fix, outside the project's
  `.venv`, empirically (§5 below): removing the override reproduces the exact original failure
  (`numpy/__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater`) against
  a real numpy install on a genuinely different Python interpreter than the project's `.venv`; restoring
  it makes that specific error disappear completely, leaving zero numpy-stub-syntax errors.
- **The `html.escape()` apostrophe fix, and why leaving quote characters unescaped is safe rather than
  a security gap.** `_escape` (`mizan/reporting/report.py` lines 31–39) calls
  `html.escape(value, quote=False)` — escaping `&`/`<`/`>` (the characters that can actually break HTML
  markup) but deliberately leaving `'`/`"` untouched, which is *not* `html.escape`'s own default
  (`quote=True`). The reasoning, stated in the function's own docstring and independently confirmed by
  this pass reading every call site in the module: every value `_escape` ever touches is interpolated
  into HTML **text content** — the body of a `<p>`, `<td>`, or `<div>` element — **never into an HTML
  attribute value**. Quote-escaping (turning a literal apostrophe into `&#x27;`) is only load-bearing
  when a string is placed *inside* an attribute's own quote-delimited value, where an unescaped quote
  character could prematurely terminate the attribute and let following text be interpreted as new
  markup or a new attribute — a real risk this module simply never creates the conditions for, since no
  dynamic string is ever written into an attribute anywhere in `mizan/reporting/report.py` (confirmed:
  every `f'<div id="..."` /`<section id="..."` attribute value in the module is a fixed, hardcoded
  literal, never an interpolated variable). Choosing `quote=True` instead would have been safe but
  strictly *worse* for this module's other own acceptance requirement: it would have turned a genuine
  apostrophe inside a fiqh `source` citation string or a caveat description (e.g. "companies that exist
  today" — actually a double-quote case, confirmed present in `CAVEAT_DESCRIPTIONS[Caveat.
  SURVIVORSHIP_BIAS]`) into a literal `&#x27;`/`&quot;` HTML entity in the rendered page, breaking
  `PHASE_7_SPEC.md` §8 AC3's own verbatim-substring test (`CAVEAT_DESCRIPTIONS[caveat] in
  generated_html`) for zero actual HTML-safety benefit in a document that never uses these values in an
  attribute context. This pass confirmed the claim empirically too, not just by reading the docstring:
  the real report generated this pass (§5 below) contains the literal apostrophe in "a reporting
  period's end date" and the literal double-quoted phrase "companies that exist today" verbatim, exactly
  as written in `CAVEAT_DESCRIPTIONS`, unescaped.
- **`matplotlib` promoted from forward-declared to a real dependency, `pandas` still not.** Per the same
  promotion discipline Phase 2 gave `httpx` and Phase 3 gave `duckdb`/`pyarrow`, `matplotlib==3.11.1`
  moves from the now-removed `[project.optional-dependencies].report` group into
  `[project.dependencies]` — the first phase to actually import it (`mizan/reporting/plots.py`).
  `pandas` remains the sole forward-declared, never-imported dependency left in the file; every
  arithmetic operation Phase 7 performs (summing `purified_amount` per ticker, walking a sorted list of
  dated ledger entries) is a small, explicit Python loop over already-typed values, the same shape
  Phase 5 and 6 both already declined to promote `pandas` for.
- **No HTML-templating dependency (Jinja2 or similar).** Plain Python f-strings and a handful of small
  private formatting helpers are used instead, reasoned explicitly in `PHASE_7_SPEC.md` §2.2 and
  confirmed matched by the shipped code: the report is a single, static, generated-once document with
  no template reuse, inheritance, or untrusted-author surface a templating engine's real value
  proposition targets, and the one genuine risk a hand-rolled builder must guard against — HTML-escaping
  — is fully covered by the standard library's own `html.escape()`.

## 4. Domain mechanics

**Fiqh register — carried forward from Phase 1, unchanged (`mizan/config/fiqh_params.py` is untouched
by any later phase's diff, confirmed by re-reading it this pass), now shown with Phase 7's own new
reader added:**

| # | Figure / default | Value in code | Code's own source citation | Read by |
|---|---|---|---|---|
| 1–5 | Ratio denominator basis/smoothing, debt/interest-investments/non-permissible-income thresholds | unchanged | unchanged | `mizan/screening/verdict.py`/`financial_ratios.py` (Phase 4) directly; Phase 5–7 all read these only indirectly, via `screen()`'s own output |
| 6–7 | Business-activity Tier 0.5 / Tier 1 toggles | unchanged | unchanged | `classify_business_activity` (Phase 4), reached transitively via `screen()` |
| 8 | Grace period length | 1 whole rebalance period | unchanged — **`[UNVERIFIED / INFERENCE]`**, no AAOIFI primary-source citation | `mizan.backtest.compliance_state.transition` (Phase 5); Phase 6/7 both read it only indirectly, through already-resolved `flip_date`/`divest_date` fields |
| 9 | Purify capital gains (Fork A/C gate) | `False` (V1 default) | register entry #9 — **`[UNVERIFIED / INFERENCE]`** on the OFF default | `mizan.purification.ledger.purify_backtest_result` (Phase 6); Phase 7 renders the *result* of this gate (whether `divestment_entries` is empty) but never reads the flag itself — confirmed this pass: `grep -n "purify_capital_gains" mizan/reporting/` finds no hit |
| 10 | Divestment attribution method | `TIME_BOUNDED_PRICE_APPRECIATION` (the only member) | register entry #10 — **`[UNVERIFIED / INFERENCE]`** | `mizan.purification.attribution.compute_divestment_attribution` (Phase 6); not read by Phase 7 |
| 11 | Purification accounting method | `SIDE_LEDGER` (the only member) | register entry #11 — quotes the primary source directly, not `[UNVERIFIED]` | Not read by name anywhere in `mizan/purification/` or `mizan/reporting/` this phase — the side-ledger DESIGN it names is what `PurificationLedger`'s own existence as a value the report renders *alongside*, never blended into, `gross_return` implements structurally |

**Phase 7 introduces no new domain figure.** Confirmed by direct read of every line under
`mizan/reporting/`: `render_report` and its six helpers, and both `plots.py` functions, format and
chart already-computed Phase 4/5/6 values — ticker symbols, dates, `Verdict`/`HoldingComplianceState`
enum values, the fiqh register's own `value`/`source`/`status` fields, `PurificationLedger`'s own
`gross_return`/`net_of_purification_return`/`purification_liability`/entry lists — with zero new
arithmetic beyond one genuinely new but purely presentational computation: the day-by-day cumulative
purification-liability series `_cumulative_purification_liability_as_of` (`mizan/reporting/plots.py`
lines 30–42) reconstructs for the equity-curve plot, which is a plain filtered running sum over
already-computed, already-dated Phase 6 ledger entries — `dividend_total + divestment_total` at each
`daily_snapshots[i].as_of_date`, computed fresh every call, never persisted, exactly the "trivially
reconstructible by a later phase" reconstruction `PHASE_6_SPEC.md` §6d explicitly anticipated and named
as Phase 7's own job. This is a rendering-time convenience computation, not a new domain figure with
its own fiqh-register entry or AAOIFI citation.

**Compliance-flip state machine, AAOIFI 30/30/5 thresholds, EDGAR/Tiingo rate limits, splitFactor
arithmetic direction, and the purification formulas — all carried forward from Phases 4–6, unchanged,
now with Phase 7's own render-layer confirmed to match:**

- `HELD_COMPLIANT` → (fresh verdict `NON_COMPLIANT`) → `HELD_NONCOMPLIANT_GRACE` → (grace countdown
  reaches 0) → `DIVESTED`, no edge back to `HELD_COMPLIANT`, current grace value `1` rebalance. This
  pass's own generated report (§5 below) renders exactly this history for its own fixture ticker's
  `verdict_history` observation count, matching the state machine's own documented behavior.
- SEC EDGAR's ≥0.12s/≥600s rate limiter, Tiingo's 50/hour–1,000/day budget and 500-ticker/month cap,
  the 21-SIC-code three-tier business-activity map, and the 30/30/5 AAOIFI ratio thresholds all remain
  exactly as Phase 4's comprehension pass described — untouched by any later phase's diff.
- Fork A — `purified_amount = non_permissible_income_ratio × dividend_amount`, ratio pinned to the
  dividend's own `ex_date`. Fork C — `purified_amount = max(0.0, quantity_liquidated ×
  (price_at_divest − price_at_flip))`. Both formulas, unchanged since Phase 6, are what
  `render_purification_detail` tabulates row-by-row and what `render_equity_curve_plot` sums into a
  running series — confirmed by this pass's own generated report showing exactly the two dividend-entry
  rows (`ZZMIXED_RATIODRIFT01`, ratios `0.020000` and `0.040000`, purified amounts `1000.00` and
  `2100.00`) the underlying fixture's own ratio-drift design (§3 above, carried from Phase 6) predicts.
- AAOIFI's underlying rule — non-halal income must be donated to charity, never counted in NAV — is a
  side-ledger by definition; `purification_liability` remains a computed, tracked number only. Mizan
  implements no charity-transfer feature in any phase, Phase 7 included: confirmed by direct read of
  every line under `mizan/reporting/`, no HTTP client, no payment/charity API, nothing beyond
  `PurificationLedger` formatted into an HTML table and a bar chart.

## 5. Honesty audit

Ran the same class of verification `PHASE_7_SPEC.md` §7 (guards)/§8 (acceptance criteria) specify,
against the code as it exists in the repository right now, this run — not trusting the spec's or the
approval commit's claim that they pass. No adversarial re-review was performed (Phase 7 is already
approved); this is an independent comprehension-grade honesty pass, run fresh this session. **The
review that already approved Phase 7 was, correctly, unusually rigorous for this specific phase** — it
actually generated a real report from the synthetic fixture and read its content, and actually removed
and restored the numpy mypy override to prove it load-bearing, rather than trusting either claim on
paper. That rigor was the right call, not merely thorough for its own sake: Phase 7 is the final phase,
and the report is literally the mechanism the whole seven-phase project is supposed to make dishonesty
structurally impossible through — a phase whose entire job is "never let a number appear without its
warning label" deserves exactly this level of "did you actually look," not a documentation-trusting
pass. This comprehension pass did its own independent version of both checks rather than merely
restating the review's verdict, and both came back confirmed.

**Everything below was re-run and passed as claimed, this run, inside the project's `.venv`:**

- `pytest tests/` — **406 passed**, no failures, no errors (365 carried from Phase 1–6 + 41 new this
  phase: `tests/test_reporting_report.py`, `tests/test_reporting_plots.py`,
  `tests/test_cli_report.py`), ~50s wall time.
- `ruff check mizan tests` — "All checks passed!", exit 0, under the pinned `ruff==0.16.5`.
- `mypy --strict mizan tests` — "Success: no issues found in **66 source files**" (up from 59 in the
  Phase 6 pass — exactly 7 new files: `mizan/reporting/__init__.py`, `report.py`, `plots.py`,
  `mizan/cli/report.py`, and the three new test files), inside `.venv`.
- `grep -rn "noqa" mizan/` — exactly the same three `# noqa: N812` hits every prior comprehension pass
  found, plus `models.py`'s unrelated `N815` suppressions — zero new suppressions anywhere under
  `mizan/reporting/`.

**This pass independently generated a real report from the synthetic fixture and read its actual
content — not merely trusted the spec's description of what it should contain.** Built a real DuckDB
database from `tests.fixtures.synthetic_universe.ZZMIXED_RATIODRIFT01` (the Mixed-verdict,
ratio-drifting fixture ticker, via `fx.write_universe_cache` + `fx.load_into_duckdb`, the exact same
fixture-seeding helper `test_cli_report.py`'s own end-to-end test uses), then called
`mizan.cli.report.run()` directly against it (`--start-date 2026-01-01 --end-date 2026-07-01
--initial-cash 1000000.0`), exactly reproducing the CLI's own real code path. Result: exit code `0`, a
real `real_report.html` file, **64,341 bytes**, containing:
- Section order, confirmed by literal string search: `id="caveats"` → `id="fiqh-register"` →
  `id="returns"` → `id="ticker-summary"` → `id="purification-detail"` → `id="plots"` — caveats
  genuinely render first, exactly as `PHASE_7_SPEC.md` §6a/§8 AC1 require, not merely as documented
  intent.
- The caveats section contains the full, verbatim look-ahead-bias and survivorship-bias description
  text, unescaped apostrophes and quotes intact (`"a reporting period's end date"`, `"companies that
  exist today"`) — directly confirming both the caveat-completeness guarantee and the `quote=False`
  escaping decision (§3 above) in real rendered output, not just in the source.
- `id="returns"` shows `Gross return: 0.102500` and `Net-of-purification return: 0.099400` — genuinely
  distinct figures (the ledger's own `purification_liability: 3100.00` is nonzero), rendered in two
  separately-`id`'d elements, never combined into one sentence.
- `id="purification-detail"` shows exactly two `DividendPurificationEntry` rows —
  `ZZMIXED_RATIODRIFT01, 2026-02-15, 0.020000, 1000.00` and `ZZMIXED_RATIODRIFT01, 2026-05-15,
  0.040000, 2100.00` — the ratio-drift fixture's own 2%→4% design (§4 above) visibly, correctly
  reflected in the actual rendered numbers, and an empty Divestment Purification Entries table (this
  fixture triggers no forced divestment).
- `id="plots"` contains exactly two `<img src="data:image/png;base64,...">` tags, no other `<img>`
  anywhere, no relative or absolute filesystem path anywhere in the document — confirmed by direct
  string count (`html.count("data:image/png;base64,") == 2`).
- Exactly one file (`real_report.html`) exists in the output directory afterward — no sibling image
  file, confirming §6e/§8 AC9's single-portable-file claim empirically, not just by code inspection.

**The numpy mypy-override fix was independently, empirically re-verified this pass — inside and
outside `.venv`, reproducing the original failure and confirming the fix resolves it — going further
than merely re-running the same command the review already ran.** Confirmed the system (non-`.venv`)
Python (3.14.4, via `/c/Python314/python`) has both `mypy` (2.3.1) and `numpy` (2.5.2) installed
independently of this project — a genuinely different environment than the project's own `.venv`.
Confirmed `numpy/__init__.pyi` line 737 does contain the PEP 695 `type` statement
(`type _Falsy = L[False, 0] | bool_[L[False]]`) in that real, installed numpy package. Then, using a
minimal standalone script that imports `numpy` and a `python_version = 3.11` mypy config matching this
project's own pin: **without** the override, mypy fails with the exact originally-documented error
(`numpy/__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater [syntax]`,
`Found 1 error in 1 file (errors prevented further checking)`); **with** the override added, the same
command against the same file reports `Success: no issues found in 1 source file`. This directly,
empirically confirms the fix is real and does what its own docstring claims, on a genuinely different
Python interpreter/mypy/numpy install than the project's `.venv` uses.

**One important nuance this pass found and is stating precisely, because the open item this touches
(§6 below) deserves an accurate update, not an overstated one:** running the *full*
`mypy --strict mizan tests` (not the isolated numpy-only repro above) against the system Python outside
`.venv` still reports errors — but they are `Cannot find implementation or library stub for module
named "duckdb"` and `"matplotlib"`, **not** a numpy-stub-syntax parse failure. Confirmed why: neither
`duckdb` nor `matplotlib` is installed in that system Python environment at all (`pip show duckdb
matplotlib` outside `.venv` returns "Package(s) not found"). This is a *different*, already-documented,
environment-completeness issue (the project's own dependencies simply are not installed outside
`.venv` — the same category as the pre-existing "duckdb-import gap" Phase 3's own comprehension pass
first flagged and every phase since has carried forward), not a recurrence of the original numpy
PEP-695 parse crash. The numpy-specific bug the override targets is genuinely, structurally fixed,
confirmed on a real, independent environment; the broader "mypy --strict mizan tests doesn't cleanly
pass outside .venv" statement remains true today only because that environment lacks the project's
actual runtime dependencies, an orthogonal and much less interesting gap than the one that used to
block it. See §6 below for how this changes that open item's status.

**`PHASE_7_SPEC.md`'s own claims, checked directly against the code rather than assumed, this run:**

- §1's claim that no earlier phase's file is modified at all except `mizan/cli/main.py` (one
  import + one registration line) — confirmed: `git diff 6edb9b5..804b333 --stat` shows exactly that,
  a stricter posture than every phase since Phase 3.
- §6a's caveat-first-ordering claim — confirmed both by direct code read (`render_report`'s own body
  builds `caveats_html` first and concatenates it first into `body`) and by this pass's own generated
  report's literal section order (above).
- §6e's inline-base64/single-file claim — confirmed both by code read and by this pass's own generated
  report (above).
- §2.1's matplotlib re-verification claim (`3.11.1`, uploaded 2026-07-18, unchanged) — confirmed by
  direct read of `docs/modernization_log.md` §6.2c, itself dated and reasoned consistently with
  `PHASE_7_SPEC.md`'s own front-matter claim.
- §8's 22 acceptance criteria — spot-checked five directly against the test suite and this pass's own
  generated report rather than all 22: AC1 (caveats-first ordering) and AC6 (well-formed HTML) map to
  assertions in `tests/test_reporting_report.py`, both passing; AC7 (end-to-end, both plot empty-input
  branches reached) maps to
  `test_report_end_to_end_handles_an_empty_backtest_window_reaching_both_plot_empty_branches` in
  `tests/test_cli_report.py`, passing; AC9 (inline, never external) and AC4 (gross/net distinctness)
  were both independently re-confirmed by this pass's own real-report generation above, not merely by
  reading the test that already checks them.

**No new spec-completeness gap found this pass** of the kind Phase 5's own §6e finding was — `grep -n
"§6[a-e]"` and a header-pattern check against the full 818-line `PHASE_7_SPEC.md` this run found every
cross-referenced subsection (§6a/§6b/§6c/§6d/§6e) actually present and written, unlike `PHASE_5_SPEC.md`'s
own still-uncorrected gap (carried forward, §6 below).

**No new gap this pass otherwise found beyond what §3 above already surfaces as deliberate, logged
decisions** (the caveat-mandatory-signature design, the base64-embedding tradeoff, the numpy-override
fix and its precise scope, the escaping decision) and what §6 below restates as still-open
carried-forward items.

## 6. Open items

**The single most important open item, carried forward from Phase 4 and restated one final time
because Phase 7, exactly like every phase before it, only proves the mechanism works on synthetic
data — and now that the pipeline is complete, this is the one gap standing between "the software
works" and "the software is trustworthy for a real decision":**

- **The real ~100-ticker curated universe and its hand-verified business-activity override map still
  do not exist anywhere in this repository.** All seven phases, Phase 7 included, were verified only
  against the sixteen synthetic fixture tickers in `tests/fixtures/synthetic_universe.py` (never real
  issuers, CIK prefix `999...`) — unmodified by this phase, needing no addition since every plot/table
  Phase 7 renders is a presentation of data the existing fixture set already exercises. Running
  `mizan report` against real tickers today would produce a real-looking, fully-caveated, correctly-
  formatted HTML page built on a generic SIC-code first-pass verdict, not a trustworthy, hand-verified
  real-world compliance-and-purification answer — the same caveat every prior phase's own open item
  already stated, now reaching its final, most user-visible form: a polished report that looks
  authoritative but is honestly built on invented companies.

**Carried forward from Phase 6, status re-checked and updated this pass:**

- **The mypy/numpy-outside-`.venv` gap — status materially changed this phase, updated here rather
  than left stale.** Previously an open, unresolved, environment-specific gap since Phase 1. **This
  pass's own empirical re-verification (§5 above) confirms Phase 7's `numpy.*` mypy override
  genuinely, structurally fixes the specific bug this item was about** — the PEP 695
  `type`-statement parse failure in numpy's own stub file — reproduced and resolved on a real,
  independent Python/mypy/numpy install outside `.venv`. **What remains open, restated precisely rather
  than left as a vague "still open":** `mypy --strict mizan tests` still does not cleanly pass on an
  arbitrary machine outside `.venv`, but only because that environment does not have `duckdb` or
  `matplotlib` installed at all — an entirely different, already-known category of gap (the project's
  own runtime dependencies not being present outside its own managed environment), not a recurrence of
  the numpy-stub-syntax crash. **Recommended status going forward: closed as originally scoped
  (the numpy PEP-695 parse crash, specifically), superseded by the pre-existing and broader
  "build and verify inside `.venv`" instruction** (`PHASE_3_SPEC.md`'s own standing mitigation, which
  covers the duckdb/matplotlib-not-installed case just as it always has).
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** — still open by design;
  Phase 7 touches none of them (it renders the register, does not adjudicate it).
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged; Phase 7
  does not touch `mizan/config/fiqh_params.py`, only renders it in full, unconditionally, on every
  report.
- **`PHASE_5_SPEC.md`'s own missing §6e section** — referenced nine times, never written, still not
  fixed as of this pass (`grep -n "§6e" PHASE_5_SPEC.md` still returns the same nine lines). Worth
  fixing directly in the spec file in any future documentation pass, though it no longer blocks
  anything — every later phase's own spec, Phase 7's included, has its own complete, self-contained
  §6 with no missing cross-reference.
- **The frozen/workable partition adds real complexity to `rebalance()`** that a future maintainer
  needs to understand correctly to avoid reintroducing the exact bug it prevents — unaffected by
  Phase 6 or Phase 7, since `mizan/backtest/clock.py` is untouched by either.
- **The grace period's value (`1` rebalance) carries no AAOIFI primary-source citation** — unchanged.
- **The Phase 2 AC15 noqa-enumeration mismatch** — still present, unaffected by any later phase.
- **`LongTermInvestments` remains `[UNVERIFIED]`, and `SIC_TIER_MAP` still has no dedicated
  gambling/casino Tier-0 code** — both unaffected by any phase since Phase 4.
- **Corporate-action anomaly scan is deliberately conservative and will produce false positives** —
  unchanged, still an accepted tradeoff, not a defect.
- **The Fork A/Fork C gating decision rests on a reasoned textual inference from `MASTER_PRD.md` §8,
  not a verbatim instruction** — a future scholarly-verification pass could reasonably reopen it; Phase
  7 renders whichever way the gate resolves, without taking a position on it.
- **`mizan/purification/` deviates from `MASTER_PRD.md` §9.4's and `PHASE_5_SPEC.md`'s own diagrammed
  module path** — real, cited, reasoned, still not corrected in `ULTIMATE_PRD.md` itself.
- **The gross/net-of-purification accounting is a plain point-to-point return, not annualized,
  risk-adjusted, or time-weighted** — an honest, deliberate scope limit from Phase 6, now visible to a
  report reader for the first time via Phase 7's `id="returns"` section; worth a future human not
  mistaking either figure for a CAGR-style return.
- **The DuckDB file remains a local, derived, regenerable artifact with no versioned migration path** —
  unchanged; Phase 7 adds no new table, column, or index (confirmed: `mizan/data/db.py` untouched, and
  neither `mizan/reporting/report.py` nor `plots.py` opens a DuckDB connection at all).

**New this phase:**

- **No real report has been generated against the real ~100-ticker universe** — the natural, final-phase
  restatement of the single most important open item above. Every report this pass or the Phase 7
  review generated, including the one this comprehension pass itself produced and read (§5 above), was
  built from invented fixture tickers.
- **The base64-embedding tradeoff (§3 above) means report file size scales with the number and
  resolution of embedded plots** — accepted at this phase's own two-plot scope, but worth a future
  human's attention if a later enhancement (outside V1's own scope) ever added more charts or a
  higher-resolution render: `render_report`'s own single-file design has no built-in ceiling on how
  large that one file could grow.
- **No CLI flag exists to suppress any report section or plot** — a deliberate design choice (§9 of
  `PHASE_7_SPEC.md`, confirmed: no `--no-plots` or equivalent flag anywhere in
  `mizan/cli/report.py`'s `add_subparser`), not an oversight — worth restating here only so a future
  reader does not mistake the absence of such a flag for a missing feature rather than a stated,
  honesty-preserving boundary.
- **This is genuinely the last phase of Mizan V1 — no `mizan/reporting/` subpackage split, no Phase 8,
  and no further phase spec exists or will be drafted as part of this build.** Confirmed by direct read
  of `PHASE_7_SPEC.md` §0/§9's own explicit statement, and by the absence of any `PHASE_8_SPEC.md` in
  the repository this pass. The dispatch that follows this comprehension pass writes `BUILD_COMPLETE.md`.

**What a human (the project owner) should actually do next, now that all seven phases are built and
reviewed — compiled here because this is the last phase, not generic advice:**

1. **Do the real ~100-ticker research.** This is the one gap every phase's own open items have pointed
   at since Phase 4, and it is now the only thing standing between "a working, tested pipeline" and "a
   pipeline whose output can be trusted for a real decision." Concretely: pick the real ~100-company
   universe, and for each one, verify its business-activity classification by hand (not merely trust
   the generic SIC-first-pass `screen()` already does) — build a real
   `BusinessActivityOverrideMap` (`mizan/screening/business_activity.py`, already built and tested,
   ships empty, keyed by CIK, requires a non-empty `rationale` string per entry) rather than relying on
   the SIC tiering alone for anything genuinely ambiguous.
2. **Buy a real Tiingo API key and run a real backfill.** `.env.example` already documents
   `TIINGO_API_TOKEN` as a placeholder; `mizan ingest` is already built, tested, and rate-limited
   correctly for both EDGAR and Tiingo — nothing in the pipeline needs new code to accept real data,
   only real credentials and a real run against the real universe from step 1.
3. **Run `mizan report` end to end against that real data**, once steps 1–2 are done, and actually read
   the resulting page — the honesty surface (caveats banner, fiqh register) this phase built is
   designed to make any remaining limitation visible at that point, the same way this comprehension
   pass's own synthetic-fixture report made every one of this document's own claims checkable rather
   than merely asserted.
4. **Get a qualified muamalat scholar to actually rule on the eleven pending fiqh register entries**,
   per `MASTER_PRD.md` §10's own standing rule ("a muamalat scholar with structural-feasibility
   expertise rules on these before any of it informs real capital... this sandbox learns the mechanics;
   it does not rule on them") — every one of the eleven entries is still stamped
   `pending_scholarly_verification`, unchanged since Phase 1, and nothing in this automated seven-phase
   build was ever supposed to change that status.
5. **Consider fixing `PHASE_5_SPEC.md`'s own dangling "§6e" cross-references** (nine references, no
   section) and correcting `ULTIMATE_PRD.md` §5 check 5's stale `mizan/backtest/purification.py` grep
   path (the real path is `mizan/purification/`) — small, low-risk documentation cleanups that do not
   block anything, but would remove the last two known "spec text has silently drifted from the shipped
   code" gaps this seven-phase build ever produced.
6. **Treat the shipped `EqualWeightStrategy` as exactly what it is — a reference implementation and
   testing vehicle, not a real research strategy** — before building or trusting any actual investment
   decision on top of this substrate; `mizan/backtest/strategy.py`'s own `Strategy` `Protocol` is the
   extension point for a real strategy, which remains entirely the owner's own future work.

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

**Phase 7 — Reporting (static HTML + plots)** (2026-08-31) — **FINAL PHASE OF MIZAN V1**

Phase 7 gave Mizan its first and only human-readable output artifact, built entirely on top of
Phases 1–6's untouched foundations and consuming a completed, purified `BacktestResult` for the
first time as a pure rendering pass, touching no earlier phase's file except one additive two-line
change to `mizan/cli/main.py`'s own subcommand registration. It shipped a new top-level package,
`mizan/reporting/`, with `mizan/reporting/report.py` (`ReportInput`, a `MizanBaseModel` that refuses
construction from a non-purified `BacktestResult`; `CAVEAT_DESCRIPTIONS`, a completeness-asserted
text registry, one full-sentence description per `Caveat` member; and `render_report`, the phase's
canonical entry point, whose `active_caveats` parameter is required, keyword-only, and carries no
default — the single design decision this phase is built around, making "no result renders without
its caveats" a `TypeError` at the call site and a `mypy --strict` static error, not merely a
convention) and `mizan/reporting/plots.py` (`matplotlib.use("Agg")` set at import time; two PNG-
rendering functions, an equity-curve plot comparing gross to net-of-purification portfolio value and
a purification-liability-by-ticker bar chart, both handling the empty-input case with an honest
annotated placeholder rather than crashing). `mizan/cli/report.py` completed the
`ingest | screen | backtest | report` CLI verb set `MASTER_PRD.md` §9.4 names, calling
`run_backtest` then `purify_backtest_result` with the same connection-reuse discipline
`mizan/cli/backtest.py` established and Phase 6's own comprehension pass flagged as a lesson for
future spec authors to get right — heeded here from the start, needing no equivalent fix.
`matplotlib==3.11.1` was promoted from a forward-declared, unused optional extra (carried since
Phase 1) to a real core dependency — the first phase to actually import it — after a live
re-verification against pypi.org confirmed the pin unchanged, logged in
`docs/modernization_log.md` §6.2c. A new `[[tool.mypy.overrides]]` block was added for
`module = "numpy.*"` (`follow_imports = "skip"`), resolving a genuine, previously-open-since-Phase-1
mypy/numpy stub-parsing incompatibility that matplotlib's own promotion would otherwise have
surfaced for the first time — this comprehension pass independently reproduced the original failure
and confirmed the fix resolves it, on a real Python installation outside the project's own `.venv`.
No new fixture ticker was added — the existing sixteen-ticker synthetic universe already exercised
every code path this phase's plots and tables render. Three new test files added 41 tests (406
total, all passing) covering caveats-first structural ordering, the required-keyword-argument
enforcement, verbatim caveat-text rendering, gross/net-of-purification distinctness, full
eleven-row fiqh-register rendering, well-formed-HTML parsing, inline-base64/single-file plot
embedding, `ReportInput`'s purification-ledger-required validator, and two genuine end-to-end runs
against the synthetic fixture (one producing a real nonzero purification liability, one deliberately
empty-window to reach both plot functions' own placeholder-rendering branches). `ruff check mizan
tests` is clean under the pinned `ruff==0.16.5` with no new noqa suppressions, and `mypy --strict
mizan tests` is fully clean inside the project's `.venv` (66 files, up from 59). This comprehension
pass independently regenerated a real report from the synthetic fixture and read its actual
rendered content, confirming the caveats-first section order, the verbatim unescaped-apostrophe
caveat text, the distinct gross/net return figures, the correctly ratio-drift-reflecting purification
table, and the exactly-two-inline-images/exactly-one-file-on-disk claims empirically rather than by
trusting the spec's description. **The real ~100-ticker curated universe still does not exist** —
Phase 7, like every phase before it, proves its mechanism works only against synthetic fixture data,
and the polished, fully-caveated HTML report this phase can now generate is honestly built on
invented companies, a limitation the report's own honesty surface is specifically designed to make
visible to any future reader who points it at real tickers before that research exists. **This is
the final phase of Mizan V1** — no `mizan/reporting/` subpackage split follows it, and no
`PHASE_8_SPEC.md` exists or will be drafted; the dispatch immediately following this comprehension
pass writes `BUILD_COMPLETE.md` instead.
