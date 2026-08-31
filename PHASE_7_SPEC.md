# PHASE_7_SPEC.md — Mizan: Reporting (static HTML + plots)

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), the same document `PHASE_1_SPEC.md`–`PHASE_6_SPEC.md` were built from. Every
> schema decision, every function signature, and every guard below traces to a section of that
> document, cited inline, cross-checked against `MASTER_PRD.md` where `ULTIMATE_PRD.md` is silent,
> and against the committed Phase 1 code (`mizan/core/caveats.py`, `mizan/config/fiqh_params.py`),
> Phase 4 code (`mizan/screening/verdict.py` — `ScreeningVerdict`, `ReasonTraceEntry`), Phase 5 code
> (`mizan/backtest/clock.py` — `BacktestResult`, `DailySnapshot`; `mizan/backtest/compliance_state.py`
> — `ComplianceStateRecord`, `VerdictObservation`, `DivestmentEvent`, `DividendEvent`), and Phase 6
> code (`mizan/purification/ledger.py` — `PurificationLedger`, `DividendPurificationEntry`,
> `purify_backtest_result`; `mizan/purification/attribution.py` — `DivestmentPurificationEntry`) for
> integration fidelity. Every field name below was read from the actual committed files this pass —
> `PurificationLedger.gross_return`/`net_of_purification_return`/`purification_liability`,
> `DividendPurificationEntry.{ticker,ex_date,ratio_used,dividend_cash_received,purified_amount}`,
> `DivestmentPurificationEntry.{ticker,flip_date,divest_date,purified_amount}`,
> `Caveat.{LOOK_AHEAD_BIAS,SURVIVORSHIP_BIAS,PENDING_SCHOLARLY_VERIFICATION}`,
> `ResultEnvelope.active_caveats` (no default) — none recalled from `PHASE_6_SPEC.md`'s own
> illustrative blocks. `matplotlib`'s pin (`3.11.1`) was re-verified live against pypi.org/project/
> matplotlib/ on **2026-08-31** (this pass) — still the latest release, `Jul 18, 2026`, unchanged from
> the version `docs/modernization_log.md` §6.2c and `ULTIMATE_PRD.md` §2.1 already recorded on
> 2026-08-30 — see §2.1 below for the reconciliation.

**Generated:** 2026-08-31 · **Dispatch type:** phase advancement (Phase 6 review-approved 2026-08-30,
comprehension pass complete 2026-08-31; no code review or fix loop runs in this dispatch — this
document is the deliverable) · **Canonical references:** `ULTIMATE_PRD.md` (governs, esp. §1's own
"every result carries its caveats structurally... a reporter that can render an un-caveated number is
a bug", §2.2's two load-bearing seams — "a backtest result is `(returns, purification_ledger,
active_caveats: list[Caveat])`. The reporter takes this tuple as its only render input — there is no
code path that renders a number without its caveat set attached." — §4.8 Reporting failure modes, §6
the execution spec naming Phase 7 "Reporting"), `MASTER_PRD.md` (governs where `ULTIMATE_PRD.md` is
silent, principally §9 the batch-pipeline architecture — notebook/CLI-first, static HTML+plots, no
dashboard — §9.4's module boundary diagram naming `mizan/reporting/report.py` and the `cli/` verb set
`ingest | screen | backtest | report`, and §11 V1 Definition of Done items 4/5), `docs/
modernization_log.md` (§6.2c, `matplotlib` pin history — re-verified this pass, §2.1 below),
`COMPREHENSION.md` (what Phases 1–6 actually shipped, including the thirteen-plus carried-forward open
items — §6 below is where the two most load-bearing for this phase, the nonexistent real universe and
the eleven pending-verification register entries, are surfaced structurally rather than merely
mentioned), `PHASE_1_SPEC.md` (`MizanBaseModel`, `Caveat`/`ResultEnvelope`, `FIQH_PARAMS` — Phase 7
**consumes** all of these, redefines none), `PHASE_4_SPEC.md`/`PHASE_5_SPEC.md`/`PHASE_6_SPEC.md`
(format/rigor precedent, and the public surface — `mizan.screening.verdict.ScreeningVerdict`,
`mizan.backtest.clock.BacktestResult`/`DailySnapshot`, `mizan.backtest.compliance_state.
ComplianceStateRecord`, `mizan.purification.ledger.PurificationLedger`/`purify_backtest_result`,
`mizan.cli.backtest.run` — Phase 7 must consume without reshaping, restated in full at §1), and
`tests/fixtures/synthetic_universe.py` (the sixteen synthetic tickers Phases 4–6 already built — §6/§8
below reuse them, adding none).

**No citation re-verification gate applies to this document's fiqh/domain content**, unchanged from
`PHASE_2/3/4/5/6_SPEC.md`'s own confirmation — Phase 7 introduces no new arXiv citation and no new
fiqh judgment call. **One live re-verification WAS performed this pass, narrowly**: `matplotlib`'s
pinned version (§2.1), since this is the first phase that actually imports it, and a stale pin
promoted from "forward-declared, unused" to "real runtime dependency" without a fresh check would be
exactly the kind of silent staleness every prior phase's dependency-promotion step (Phase 2's `httpx`,
Phase 3's `duckdb`/`pyarrow`) re-verified before promoting. Confirmed current — see §2.1.

---

## §0 Phase Plan Header

# **Phase 7 of 7 (FINAL): Reporting (static HTML + plots)**

Phase sequence, unchanged from `PHASE_6_SPEC.md` §0 / `ULTIMATE_PRD.md` §6 (re-derived there, not
re-derived again here):

| # | Phase | Ships |
|---|---|---|
| 1 | Foundation & Config (done, approved) | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| 2 | Ingestion & raw cache (done, approved) | EDGAR (`companyfacts` + `companyconcept` + `submissions`) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store (done, approved) | `data/normalize.py`, `data/db.py`, typed `fundamentals_facts`/`price_bars` tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine (done, approved) | `screening/business_activity.py`, `screening/financial_ratios.py` (30/30/5, two-axis denominator from config), `screening/verdict.py` (combines both into a three-state `Verdict` + reason trace — the `screen()` entry point), `mizan/cli/screen.py` |
| 5 | Backtest engine + compliance-flip state machine (done, approved) | `backtest/clock.py` (quarterly-rebalance event loop, `run_backtest()`), `backtest/portfolio.py`, `backtest/strategy.py`, `backtest/compliance_state.py` (flip→grace→divest state machine), `mizan/cli/backtest.py` |
| 6 | Purification engine (done, approved) | `mizan/purification/ledger.py` (Fork B — side-ledger accrual, gross/net-of-purification return), `mizan/purification/attribution.py` (Fork C — forced-divestment price-appreciation attribution), `mizan/cli/backtest.py` MODIFIED (purification wired in as a post-processing pass) |
| **7** | **Reporting (FINAL)** ← *this document* | `mizan/reporting/report.py` (static-HTML generation, caveat-mandatory render function), `mizan/reporting/plots.py` (matplotlib plots), `mizan/cli/report.py` (completes the `ingest \| screen \| backtest \| report` verb set) |

This spec covers **Phase 7 only**. It is the contract the Phase 7 execution agent builds against and
the Phase 7 review agent (next round of Step 12) verifies against. Phase 7 **consumes** Phase 1's
public surface (`mizan.core.base.MizanBaseModel`, `mizan.core.caveats.Caveat`, `mizan.config.
fiqh_params.FIQH_PARAMS`/`FiqhParams`/`FiqhParam`), Phase 4's public surface (`mizan.screening.verdict.
ScreeningVerdict`, indirectly — Phase 7 does not re-invoke `screen()`, §6a), Phase 5's public surface
(`mizan.backtest.clock.BacktestResult`/`DailySnapshot`, `mizan.backtest.compliance_state.
ComplianceStateRecord`/`VerdictObservation`/`DivestmentEvent`/`DividendEvent`), and Phase 6's public
surface (`mizan.purification.ledger.PurificationLedger`/`DividendPurificationEntry`/
`purify_backtest_result`, `mizan.purification.attribution.DivestmentPurificationEntry`,
`mizan.cli.backtest.run`'s own established CLI pattern) and **must not reshape any of them**. Phase 7
introduces exactly one new top-level package (`mizan/reporting/`) and one new CLI subcommand
(`mizan/cli/report.py`); it modifies no earlier phase's file at all (a stricter posture than Phase 6's
own one-file additive modification of `mizan/cli/backtest.py` — Phase 7 needs no equivalent
modification, since `mizan report` is a fully independent entry point that calls `run_backtest`/
`purify_backtest_result` itself rather than piggy-backing on `mizan backtest`'s own CLI file, §1
below).

**This is confirmed, explicitly, as the LAST phase of Mizan V1.** No `mizan/` subpackage remains
undefined after this phase — `config/`, `core/`, `data/`, `screening/`, `backtest/`, `purification/`,
`reporting/` is the complete set `MASTER_PRD.md` §9.4's own module-boundary diagram names, and the
`cli/` verb set (`ingest | screen | backtest | report`) that same diagram names is complete once
`mizan/cli/report.py` ships. The dispatch that follows this phase's own review-approval and
comprehension pass will write `BUILD_COMPLETE.md`, not `PHASE_8_SPEC.md` — there is no Phase 8.

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`.** Same flat layout `PHASE_1_SPEC.md`–`PHASE_6_SPEC.md` §1
preserved — no nesting directory. Every file below is new; **no earlier phase's file is modified by
this phase, at all** (a stricter posture than every prior phase since Phase 3, each of which modified
at least one earlier file additively — see the header note above for why `mizan/cli/backtest.py` in
particular does not need touching this time).

```
C:\Users\hp\HMS\
├── mizan/
│   ├── reporting/
│   │   ├── __init__.py            # NEW — empty, package marker only (mizan/purification/__init__.py precedent)
│   │   ├── report.py              # NEW — CAVEAT_DESCRIPTIONS, ReportInput, render_report()
│   │   │                          #        (§3, §4.1, §6a-§6d)
│   │   └── plots.py               # NEW — render_equity_curve_plot(), render_purification_by_ticker_plot()
│   │                               #        (§4.2, §6c, §6d)
│   └── cli/
│       └── report.py              # NEW — the `report` subcommand, completing ingest|screen|backtest|report
│                                   #        (§4.3)
└── tests/
    ├── test_reporting_report.py   # NEW
    ├── test_reporting_plots.py    # NEW
    └── test_cli_report.py         # NEW
```

`mizan/cli/main.py` is modified — but only by the same one-line-plus-one-line additive pattern every
prior phase's own CLI verb registration already used (`PHASE_5_SPEC.md` §4.5 for `backtest`,
unmodified since): one new import (`from mizan.cli import report as report_cli`), one new registration
line (`report_cli.add_subparser(subparsers)`) inside `build_parser()`. Every existing line in
`main.py` stays byte-for-byte in place — `main()`'s boot-check-first dispatch, unchanged since Phase 2,
still runs before `mizan report` (or any subcommand) does anything else.

**Confirmed: this phase does not touch `mizan/backtest/`, `mizan/screening/`, `mizan/purification/`,
`mizan/config/`, `mizan/core/`, `mizan/data/`, or `mizan/cli/backtest.py`/`screen.py`/`ingest.py`/
`normalize.py`.** `mizan/reporting/report.py` and `plots.py` import and call `mizan.backtest.clock.
BacktestResult`/`DailySnapshot`, `mizan.backtest.compliance_state.ComplianceStateRecord`, `mizan.
purification.ledger.PurificationLedger`, `mizan.config.fiqh_params.FiqhParams`, and `mizan.core.
caveats.Caveat` — they never edit any of those modules' own files. `mizan/cli/report.py` calls `mizan.
backtest.clock.run_backtest` and `mizan.purification.ledger.purify_backtest_result` directly, the same
two functions `mizan/cli/backtest.py`'s own `run()` already calls, in the same order, with the same
argument-threading discipline (§4.3, §7 guard G-R8, mirroring Phase 6's own G-P7) — but as its own,
independent CLI entry point, not as a modification of `backtest.py`.

---

## §2 Dependencies

### 2.1 `matplotlib` promoted from forward-declared to a real runtime dependency

`pyproject.toml`'s `[project.optional-dependencies].report` group has carried `matplotlib==3.11.1`,
unused, since Phase 1 (`PHASE_1_SPEC.md` §2, restated unchanged through every intervening phase's own
§2 "no premature imports" guard). Phase 7 is the first phase that actually imports it
(`mizan/reporting/plots.py`, §4.2) — per the same promotion discipline Phase 2 gave `httpx` and Phase 3
gave `duckdb`/`pyarrow` (`PHASE_3_SPEC.md` §2.1), this phase moves `matplotlib==3.11.1` from
`[project.optional-dependencies].report` into `[project.dependencies]` in `pyproject.toml`, and removes
the now-empty `report` optional-dependency group entirely (mirroring how Phase 3 removed `duckdb`/
`pyarrow` from `data`'s own forward-declaration rather than leaving a stale empty-in-spirit group
behind).

**Re-verification, performed live this pass (2026-08-31), not merely carried forward:** fetched
`https://pypi.org/project/matplotlib/` directly. Latest published release remains **3.11.1**, uploaded
**2026-07-18** — unchanged from what `ULTIMATE_PRD.md` §2.1 and `docs/modernization_log.md` already
recorded as of 2026-08-30. **Decision: pin stays exactly `matplotlib==3.11.1`, no change.** One new
dated entry is added to `docs/modernization_log.md`, §6.2c: "`matplotlib` re-verified 2026-08-31 ahead
of Phase 7's promotion to a real dependency — still 3.11.1, no newer release since the 2026-08-30
Step-10 pass" — logged because this is the pin's first *load-bearing* verification (the prior two
entries recorded it as forward-declared and unused; this is the first phase where a stale pin would
actually matter to a real import), not because anything changed.

**The `Agg` backend, stated explicitly because it is load-bearing and easy to get wrong in a batch
context (§6c):** `mizan/reporting/plots.py` calls `matplotlib.use("Agg")` before importing `pyplot`,
at module import time. Mizan is a headless, single-user batch/CLI tool (`MASTER_PRD.md` §9 — no
service, no display) — matplotlib's default backend selection can, on some platforms/environments,
attempt to bind an interactive GUI toolkit (Tk, Qt) that is not installed or not available in a
non-interactive process, which would turn `mizan report` into an environment-dependent crash rather
than a deterministic batch job. `Agg` is matplotlib's own non-interactive, pure-raster PNG backend —
setting it explicitly, at import time, before any `pyplot` figure is created, removes this failure
mode structurally rather than hoping the ambient environment never has an interactive backend
installed.

### 2.2 No HTML-templating dependency — plain Python string formatting is sufficient

`MASTER_PRD.md` does not mandate a templating engine anywhere in its Reporting scope (§9.4: `reporting/
report.py — static HTML + plots; refuses to render without caveat set` — no framework named). Per
every prior phase's "no new dependency without justification" discipline (`PHASE_5_SPEC.md` §2.2 on
`pandas`, `PHASE_6_SPEC.md` §2.1 on adding zero new dependencies), the question is asked and answered
explicitly rather than defaulted past: **does Phase 7 need Jinja2 (or any templating library), or do
Python f-strings / `str.format` suffice?**

**Decision: no new dependency. Plain Python string building (f-strings and a handful of small private
formatting helper functions in `mizan/reporting/report.py`) is sufficient**, for three concrete
reasons specific to this phase's own scope: (1) the report is a **single, static, generated-once**
document — there is no live re-render, no user-supplied template file, no conditional-inheritance
layout hierarchy a templating engine's real value proposition (template reuse, autoescaping,
sandboxing untrusted authors) is designed for; (2) every dynamic value Phase 7 interpolates comes from
already-typed, already-validated Pydantic models (`BacktestResult`, `PurificationLedger`, `FiqhParams`)
under this codebase's own control — there is no untrusted external template source Jinja2's sandboxing
would meaningfully protect against; (3) the one genuine risk a hand-rolled string-builder must guard
against that a templating engine would give for free — HTML-escaping of interpolated values so the
output stays well-formed markup — is fully covered by Python's own standard-library `html.escape()`,
called at every interpolation site (§6e), with zero new dependency. A hand-rolled f-string template,
disciplined about escaping, is the smaller, more auditable surface for a document this
structurally simple, and keeps `mizan/reporting/` free of a dependency whose main value (reusable,
inheritable, user-authorable templates) this phase's own single generated-document scope does not
need.

### 2.3 `pandas`/`pyarrow` — still not imported by `mizan/reporting/`

Same posture `PHASE_5_SPEC.md` §2.2/`PHASE_6_SPEC.md` §2.2 already took, re-examined rather than
copied: every arithmetic operation Phase 7 performs (summing `purified_amount` per ticker, walking a
sorted list of dated ledger entries for the equity-curve series, formatting floats into HTML strings)
is a small, explicit Python loop over already-typed Pydantic/`float`/`date` values, exactly the shape
Phase 5 and Phase 6 both already declined to promote `pandas` for. **Decision: still no** — `pandas`
remains forward-declared and unused in `[project.optional-dependencies].data`, now the sole remaining
forward-declared, never-imported dependency in `pyproject.toml` (matplotlib's own forward-declaration
is discharged by §2.1 above). `pyarrow` is not imported anywhere under `mizan/reporting/` either — this
phase does no Parquet or DuckDB↔Arrow work, matching Phase 5/6's own precedent.

### 2.4 Forbidden-dependency list unchanged, and load-bearing for this phase specifically

`PHASE_1_SPEC.md` §2.5's permanently forbidden list (`openai`, `anthropic`, every other LLM/model SDK,
`yfinance`) still applies, unmodified. Reporting is a deterministic render of already-computed values
— there is no decision-under-uncertainty step here, and specifically **no narrative-generation step**,
an LLM could plausibly be reached for; `ULTIMATE_PRD.md` §4.8's own first-listed Reporting failure mode
is exactly a render that could omit its caveats, not a narrative-quality concern, and this phase's own
§9 states the no-LLM-narrative posture as an explicit non-goal, not merely an absence. The grep-based
guard (§7) is restated at this phase's own new path, `mizan/reporting/`.

---

## §3 Pydantic Schemas

Every new model inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no Phase 7 module subclasses `pydantic.BaseModel` directly, same guard
every prior phase has held.

### 3.1 `mizan/reporting/report.py` — `ReportInput`

```python
from __future__ import annotations

from pydantic import model_validator

from mizan.backtest.clock import BacktestResult
from mizan.config.fiqh_params import FiqhParams
from mizan.core.base import MizanBaseModel


class ReportInput(MizanBaseModel):
    """Everything `render_report` (§4.1) needs to render one report, bundled into one typed value —
    the concrete answer to the outer dispatch's own question of what a "report-input model" should
    wrap. Deliberately **not** wrapped in a `mizan.core.caveats.ResultEnvelope`: `active_caveats`
    lives as its own required, keyword-only parameter on `render_report` itself (§4.1), not as a
    field on this model or on an enclosing envelope — see §6a for why that placement, not this one,
    is the mechanism that makes ULTIMATE_PRD.md §2.2's "no code path renders a number without its
    caveat set" a call-time (TypeError-raising), not merely a construction-time
    (pydantic.ValidationError-raising), guarantee.
    """

    backtest_result: BacktestResult
    """The already-purified result — `purification_ledger` MUST be populated (i.e. not `None`), the
    output of `mizan.purification.ledger.purify_backtest_result`, never a raw, pre-purification
    `run_backtest()` result. Enforced below, not merely hoped for."""
    fiqh_params: FiqhParams
    """The register actually used to produce `backtest_result` — rendered in full (§6b) as the
    honesty-surface requirement `MASTER_PRD.md` §10 and `ULTIMATE_PRD.md` §1 both name. No default:
    a caller must state which register configuration governed this run, the same "no silent default"
    posture `mizan.purification.ledger.purify_backtest_result`'s own `fiqh_params` parameter takes
    (its default is `FIQH_PARAMS`, but that default is itself always an explicit, named singleton,
    never an implicit "whatever config happens to be active")."""

    @model_validator(mode="after")
    def _purification_ledger_is_populated(self) -> "ReportInput":
        """`backtest_result.purification_ledger is None` means `purify_backtest_result` was never
        called — a Phase-5-only, pre-Phase-6 result. Rendering a report from one would silently omit
        the gross-vs-net-of-purification distinction §6c requires to be structurally present; this
        is caught here, at construction, rather than left for `render_report`'s own body to discover
        via a `None`-shaped `PurificationLedger.model_validate` failure with a less specific message."""
        if self.backtest_result.purification_ledger is None:
            raise ValueError(
                "ReportInput.backtest_result.purification_ledger is None — pass the output of "
                "purify_backtest_result(), never a raw run_backtest() result"
            )
        return self
```

### 3.2 `CAVEAT_DESCRIPTIONS` — the honesty-surface text registry, completeness-checked at import time

```python
from mizan.core.caveats import Caveat

CAVEAT_DESCRIPTIONS: dict[Caveat, str] = {
    Caveat.LOOK_AHEAD_BIAS: (
        "Look-ahead bias: screen(ticker, as_of_date) uses the most-recently-filed fact as of "
        "as_of_date rather than true filing-lag-corrected point-in-time data. EDGAR facts routinely "
        "carry a multi-year gap between a reporting period's end date and its actual filing date — "
        "this backtest's verdicts may be more favorable than a strictly point-in-time reconstruction "
        "would produce."
    ),
    Caveat.SURVIVORSHIP_BIAS: (
        "Survivorship bias: the ticker universe supplied to this run is \"companies that exist "
        "today\", which silently excludes anything delisted or gone to zero over the backtest "
        "window. This backtest cannot see, and does not account for, any company that failed or was "
        "delisted during the period it covers."
    ),
    Caveat.PENDING_SCHOLARLY_VERIFICATION: (
        "Pending scholarly verification: at least one fiqh judgment call governing this run's "
        "screening, backtest, and purification logic is an engineering-team default, not a "
        "scholar-ratified ruling. The full register, with every entry's current status, is rendered "
        "below."
    ),
}
assert set(CAVEAT_DESCRIPTIONS) == set(Caveat), (
    "CAVEAT_DESCRIPTIONS must cover every mizan.core.caveats.Caveat member exactly — a caveat with "
    "no rendered description would be a silent gap in the exact honesty surface this module exists "
    "to guarantee"
)
```

This mirrors `mizan/config/fiqh_params.py`'s own `_register_ids_are_exactly_one_to_eleven` completeness
validator (§3.3, `FiqhParams`) — a structural assertion that a future `Caveat` member added to
`mizan/core/caveats.py` without a matching entry here fails LOUD, at import time (an
`AssertionError` on `import mizan.reporting.report`, before any report is ever rendered), rather than
silently rendering an incomplete caveat banner.

### 3.3 No new model in `mizan/reporting/plots.py`

`plots.py` (§4.2) takes already-typed Phase 5/6 values (`tuple[DailySnapshot, ...]`,
`PurificationLedger`) as plain function arguments and returns raw `bytes` (a PNG image) — it defines no
Pydantic model of its own. There is nothing in a rendered PNG's own shape that benefits from a typed
wrapper Python's own `bytes` doesn't already give exactly.

---

## §4 Public Interfaces / Function Signatures

### 4.1 `mizan/reporting/report.py`

```python
def render_report(data: ReportInput, *, active_caveats: tuple[Caveat, ...]) -> str:
    """THE canonical, singular Phase 7 entry point — this phase's analogue of `screen()`/
    `run_backtest()`/`purify_backtest_result()`. Returns a complete, self-contained HTML document as
    a `str` (UTF-8-encodable, no external file references — §6e).

    `active_caveats` is **keyword-only and carries no default** (note the bare `*` before it in the
    signature above). This is the mechanism, stated precisely rather than left to convention:
    `render_report(data)` — omitting the keyword entirely — raises `TypeError: render_report()
    missing 1 required keyword-only argument: 'active_caveats'` at the CALL SITE, before this
    function's own body ever executes, and mypy --strict flags any call site missing it as a
    static error too (§7 guard G-R1, §8 AC2). `render_report(data, active_caveats=())` — an
    explicit empty tuple — is a valid, if unusual, call: exactly the same "empty tuple is a stated
    choice, omission is not" distinction `mizan.core.caveats.ResultEnvelope.active_caveats` (Phase 1)
    already establishes for its own field, deliberately reproduced here at the FUNCTION-SIGNATURE
    layer rather than the pydantic-model layer (§6a explains why that placement, specifically, is
    required to get a `TypeError` rather than a `pydantic.ValidationError`).

    Builds the document in the fixed section order §6a specifies (caveats banner first, before any
    numeric figure appears anywhere in the output — a literal, testable string-order property, §8
    AC1), rendering: the caveat banner (§6a, every member of `active_caveats` via
    `CAVEAT_DESCRIPTIONS`, §3.2), the full 11-row fiqh judgment-call register (§6b), the two
    distinctly-labelled return figures (§6c), the per-ticker compliance/verdict summary (§6d), the
    full purification-ledger entry detail (dividend and divestment entries), and both embedded plots
    (§6c/§6d, `mizan.reporting.plots.render_equity_curve_plot`/`render_purification_by_ticker_plot`,
    base64-inlined per §6e). Every interpolated dynamic string passes through `html.escape()` (§6e).
    """


def render_caveats_banner(active_caveats: tuple[Caveat, ...]) -> str:
    """Private-in-spirit but exported for direct unit testing (§8 AC1/AC3): renders one `<section
    id="caveats">` block, one `<p>` per caveat in `active_caveats`, each containing
    `CAVEAT_DESCRIPTIONS[caveat]` verbatim, `html.escape()`-d. An empty `active_caveats` tuple
    renders the section with an explicit "No caveats declared for this run." line rather than an
    empty, ambiguous-looking `<section>` — the empty case is a genuine, valid input (§4.1) and must
    render honestly, not silently disappear.
    """


def render_fiqh_register(fiqh_params: FiqhParams) -> str:
    """Renders one `<section id="fiqh-register">` table, one row per `FiqhParams` field, in
    `register_id` order (1–11 — sorted, since `type(fiqh_params).model_fields` iterates in
    declaration order, which already happens to match `register_id` order in `mizan/config/
    fiqh_params.py`, but this function sorts explicitly by `.register_id` rather than relying on
    that coincidence, §6b), each row showing `register_id`, the field's own attribute name, `value`
    (`str()`-formatted), `source`, `primary_source_gap` (omitted from the row, not rendered as an
    empty cell, when it is the empty string — §6b), and `status.value`. Asserts exactly 11 rows are
    produced (`AssertionError` otherwise) — a second, render-time instance of the same completeness
    guarantee `FiqhParams._register_ids_are_exactly_one_to_eleven` already gives at construction
    time (§3.2's own precedent).
    """


def render_return_summary(ledger: PurificationLedger) -> str:
    """Renders one `<section id="returns">` containing two SEPARATE, distinctly-`id`'d `<div>`
    elements — `id="gross-return"` and `id="net-of-purification-return"` — each showing its own
    label and its own `.6f`-formatted value (matching `mizan/cli/backtest.py`'s own established
    `.6f` precedent for these two fields), never combined into one figure or one sentence (§6c, §7
    guard G-R3).
    """


def render_ticker_summary(compliance_states: dict[str, "ComplianceStateRecord"]) -> str:
    """Renders one `<section id="ticker-summary">` table, one row per ticker in `compliance_states`
    (sorted by ticker for determinism), showing final `state`, `flip_date`/`divest_date` (blank if
    `None`), and the number of `verdict_history` observations recorded — the per-ticker verdict
    summary the outer dispatch asks for, built entirely from Phase 5's own already-computed
    `ComplianceStateRecord` values (§6d) — no re-invocation of `screen()`, no new computation.
    """


def render_purification_detail(ledger: PurificationLedger) -> str:
    """Renders one `<section id="purification-detail">`: the `purification_liability` total, then
    one table row per `DividendPurificationEntry` (ticker, ex_date, ratio_used, purified_amount) and
    one table row per `DivestmentPurificationEntry` (ticker, flip_date, divest_date, purified_amount)
    — every ledger entry Phase 6 computed, none summarized away.
    """
```

### 4.2 `mizan/reporting/plots.py`

```python
def render_equity_curve_plot(
    daily_snapshots: tuple[DailySnapshot, ...], ledger: PurificationLedger
) -> bytes:
    """Renders one PNG (via the `Agg` backend, §2.1): gross portfolio value (`daily_snapshots[i].
    portfolio_value` at each `as_of_date`) plotted against net-of-purification portfolio value (the
    same series, minus the CUMULATIVE purification liability accrued as of each date — §6c: `sum(
    entry.purified_amount for entry in ledger.dividend_entries if entry.ex_date <= as_of_date) +
    sum(entry.purified_amount for entry in ledger.divestment_entries if entry.divest_date <=
    as_of_date)`, a day-by-day running series reconstructed exactly the way `PHASE_6_SPEC.md` §6d's
    own docstring anticipated: "trivially reconstructible by a later phase from each entry's own
    date field... squarely Phase 7's reporting concern"). Two labelled lines on one figure, `x` axis
    = `as_of_date`, `y` axis = portfolio value.

    `daily_snapshots == ()` (Phase 6's own documented empty-backtest edge case, §6 below): renders a
    single-panel figure with an explicit "No trading days in this backtest window." annotation
    instead of raising — §7 guard G-R9, §8 AC7's own end-to-end-must-not-crash requirement depends
    on this not being a code path that can throw.
    """


def render_purification_by_ticker_plot(ledger: PurificationLedger) -> bytes:
    """Renders one PNG: one bar per ticker with any nonzero purification contribution, `y` = `sum(
    entry.purified_amount for entry in ledger.dividend_entries if entry.ticker == t) + sum(entry.
    purified_amount for entry in ledger.divestment_entries if entry.ticker == t)`, tickers sorted
    alphabetically for determinism. `ledger.dividend_entries == () and ledger.divestment_entries ==
    ()` (an all-Pure-verdict run, or `purify_capital_gains` off with no Mixed dividends either):
    renders a single-panel figure with an explicit "No purification liability in this run."
    annotation instead of raising or rendering an empty axes with no explanation.
    """
```

Both functions return raw PNG `bytes` (`io.BytesIO()` + `figure.savefig(buf, format="png")` +
`buf.getvalue()`, `plt.close(figure)` called before returning to avoid matplotlib's own
figure-object accumulation across repeated calls within one process — relevant because `mizan report`
calls both functions exactly once per invocation, but a test suite calling them dozens of times across
one `pytest` process must not leak figures).

### 4.3 `mizan/cli/report.py`

```python
def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Registers `report --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --initial-cash FLOAT --db-path PATH --cache-dir PATH
    [--overrides-path PATH] --output-path PATH`. Every flag through `--overrides-path` is identical,
    flag-for-flag, to `mizan backtest`'s own `add_subparser` (`mizan/cli/backtest.py`, unmodified by
    this phase) — same candidate-universe semantics, same optional-overrides posture. `--output-path`
    is the one new flag: where the generated, self-contained HTML file is written. No `--no-plots` or
    similar suppression flag — a report that silently omits its own plots on request is not a
    reporting concern this phase's own scope needs (§9).
    """


def run(args: argparse.Namespace) -> int:
    """Opens one READ-ONLY DuckDB connection (`db.connect(args.db_path, read_only=True)` — `report`
    never writes to DuckDB, same posture as every other subcommand), loads the override map, calls
    `run_backtest(...)` then `purify_backtest_result(...)` — the exact same two-call sequence, same
    argument-threading discipline (same `con`/`cache_dir`/`overrides` local variables reused across
    both calls, never re-opened or re-loaded in between), `mizan/cli/backtest.py`'s own `run()`
    already established (§7 guard G-R8, mirroring Phase 6's G-P7) — then, still inside the `with
    db.connect(...)` block exactly as Phase 6's connection-lifetime fix requires (`COMPREHENSION.md`
    §3's own carried-forward note that a Phase 8-equivalent spec must get this right, heeded here),
    constructs `ReportInput(backtest_result=result, fiqh_params=FIQH_PARAMS)` and calls
    `render_report(report_input, active_caveats=envelope.active_caveats)` — reusing `run_backtest`'s
    own returned `envelope.active_caveats` tuple verbatim, never a freshly-invented caveat set.
    Writes the returned HTML `str` to `args.output_path` (UTF-8, `Path.write_text`). Catches the
    same per-ticker/whole-backtest-shaped exceptions `mizan backtest` catches (`CikResolutionError`/
    `SicResolutionError`/`NotNormalizedError`/`InsufficientDataError`), printing a `HALT: ...` message
    to stderr and returning exit code 1 — identical contract to `mizan/cli/backtest.py`'s own `run()`.
    Prints the output path and the final portfolio value to stdout on success, returns 0.
    """
```

---

## §5 Migrations

**N/A, confirmed explicitly**, same posture `PHASE_5_SPEC.md` §5/`PHASE_6_SPEC.md` §5 already
established, re-derived for this phase's own different scope: Phase 7 adds no DuckDB table, column, or
index, and issues no `CREATE`/`ALTER`/`DROP`/`INSERT` anywhere in its own code. `mizan/reporting/`
reads only already-in-memory `BacktestResult`/`PurificationLedger` Pydantic values handed to it by
`mizan/cli/report.py` — neither `report.py` nor `plots.py` opens a DuckDB connection or accepts one as
a parameter; the one open connection in this phase's own code lives entirely inside `mizan/cli/
report.py`'s `run()`, used only for the `run_backtest`/`purify_backtest_result` calls it delegates to,
exactly as `mizan/cli/backtest.py`'s own `run()` already does. Phase 7's only disk write is the
generated HTML file at `--output-path`, a plain UTF-8 text file, not a DuckDB artifact — no migration
concept applies to it any more than one applies to a rendered `mizan backtest` stdout summary.

---

## §6 Implementation Logic Flow

### 6a. The caveat-stamping mechanism — why a required keyword parameter, not a wrapped model

`ULTIMATE_PRD.md` §2.2 states the seam this phase makes real: "the reporter takes this tuple as its
only render input — there is no code path that renders a number without its caveat set attached."
`ULTIMATE_PRD.md` §4.8's own Reporting failure-mode table adds the precise enforcement bar: "the
render function requires `active_caveats` as a non-optional argument... type-level enforcement —
there is no render call signature that omits caveats" — and names the detection mechanism explicitly:
"should be a type error, caught before runtime."

Two designs were weighed, both legitimate readings of the outer dispatch's own "`active_caveats` (or
a `ResultEnvelope` wrapping the whole report payload)" phrasing:

1. **Wrap the whole payload in a `ResultEnvelope`** (`render_report(envelope: ResultEnvelope) -> str`,
   reading `envelope.active_caveats` internally). This reuses Phase 1's own type verbatim and is the
   more literal reading of `ULTIMATE_PRD.md` §2.2's "the reporter takes this tuple as its only render
   input." But under this design, omitting `active_caveats` fails at **`ResultEnvelope` construction
   time** — a `pydantic.ValidationError` raised wherever the envelope is built, not at `render_report`'s
   own call site. A test asserting the render function itself refuses an omitted caveat set would have
   to construct an envelope first and would never actually exercise `render_report`'s own signature.
2. **`active_caveats` as `render_report`'s own required, keyword-only parameter** (this document's
   choice, §4.1). Omitting it raises `TypeError` at the exact call site, catchable by `mypy --strict`
   as a missing-argument error at that call site specifically, and testable directly via `pytest.raises
   (TypeError): render_report(data)` (§8 AC2) — a strictly stronger, more literal satisfaction of
   `ULTIMATE_PRD.md` §4.8's own stated bar ("should be a type error, caught before runtime") than a
   pydantic validation error one function-call layer removed.

**Decision: design 2.** `ReportInput` (§3.1) therefore carries no `active_caveats` field of its own —
the caveat set lives at exactly one place, `render_report`'s own signature, matching `ResultEnvelope.
active_caveats`'s "no default, explicit-empty-tuple-is-valid" precedent (Phase 1) at the layer where
the outer dispatch's stated acceptance bar (a `TypeError`) actually requires it to live.

**`mizan/cli/report.py` never invents its own caveat set (§4.3).** `run_backtest`'s own `ResultEnvelope`
already carries the correct, canonical set — `(Caveat.LOOK_AHEAD_BIAS, Caveat.SURVIVORSHIP_BIAS,
Caveat.PENDING_SCHOLARLY_VERIFICATION)`, unconditionally, per `mizan/backtest/clock.py`'s own `run_
backtest` body (confirmed by direct read, §4.3's docstring quotes it) — and `run()` reuses that same
`envelope.active_caveats` tuple, verbatim, as the argument to `render_report`. Phase 7 is a consumer of
the caveat set Phase 5 already established, not a second, independent source of truth for what a
backtest's caveats are.

**The structural-ordering guarantee, beyond the signature itself.** `render_report`'s own body (§4.1)
renders the caveats banner (`render_caveats_banner`) FIRST — before the fiqh register, before either
return figure, before anything numeric appears anywhere in the returned HTML string. This is a second,
independent enforcement of the same "no number without its caveats" property, at the level of the
actual rendered bytes a human reads, not merely the function signature that produced them: even a
reader who never inspects the Python source, only the generated HTML, encounters the caveat banner
before any figure in reading order. §8 AC1 makes this a literal, checkable string-index assertion.

### 6b. The fiqh register as honesty surface — every entry, unconditionally

`MASTER_PRD.md` §10's own framing — "the honesty surface" — and `ULTIMATE_PRD.md` §1's "every fiqh
judgment call is a placeholder for a scholar's ruling, never a silent hardcode... this is the honesty
surface" together set this phase's own core promise: a reader of the generated report can see every
judgment call the system embeds, not just be told one exists. `render_fiqh_register` (§4.1) is the
single function that makes this literally true — it iterates all 11 `FiqhParams` fields (via
`type(fiqh_params).model_fields`, the same introspection technique `mizan/config/fiqh_params.py`'s own
`_register_ids_are_exactly_one_to_eleven` validator already uses, reused here rather than
re-invented), sorts by `register_id`, and renders `register_id`, `value`, `source`, and `status.value`
(`"pending_scholarly_verification"` for all 11, currently — `VerificationStatus` has exactly one
member, `mizan/config/fiqh_params.py`'s own docstring) for every single row — never a filtered or
"most important 5" subset. `primary_source_gap`, when non-empty (entries #1, #2, #5, and several
others carry one, confirmed by direct read of `mizan/config/fiqh_params.py`), is rendered as its own
labelled line within that entry's row — the "what the primary source does NOT settle" honesty note,
not silently dropped for space.

### 6c. Gross vs net-of-purification — two figures, never one, and the equity-curve reconstruction

`MASTER_PRD.md` §8 Fork B's own requirement, now finally reaching a human reader: "report two
numbers... so the drag is its own visible figure, not a silent NAV distortion." `render_return_summary`
(§4.1) renders `ledger.gross_return` and `ledger.net_of_purification_return` into two SEPARATE,
independently-`id`'d HTML elements (`id="gross-return"`, `id="net-of-purification-return"`) — never
concatenated into one sentence, never computed as a single "net" figure with the gross figure omitted.
§8 AC4 restates Phase 6's own §8 AC5 at the rendered-output layer: the two figures must be textually
distinct in the generated HTML whenever `ledger.purification_liability > 0.0`, and are permitted to
coincide only when the ledger is genuinely empty.

**The equity-curve plot is where Phase 6's own deferred day-by-day liability series finally gets
built** — `PHASE_6_SPEC.md` §6d explicitly named this as Phase 7's job, quoted here because it is
binding: "a day-by-day running series, if ever wanted, is trivially reconstructible by a later phase
from each entry's own date field... squarely Phase 7's reporting concern." `render_equity_curve_plot`
(§4.2) does exactly that reconstruction, privately, inside itself: for each `DailySnapshot.as_of_date`,
sums every `DividendPurificationEntry.purified_amount` whose `ex_date <= as_of_date` and every
`DivestmentPurificationEntry.purified_amount` whose `divest_date <= as_of_date` — a plain filtered
running sum over already-computed, already-dated Phase 6 values, no new computation invented, no
persisted intermediate series, computed fresh every time this function runs (mirroring `mizan.
purification.ledger._compute_returns`'s own "computed once, at render/report time, never persisted"
posture). The resulting net-of-purification curve, plotted alongside the gross curve on one figure, is
the visual form of the same two-figures-never-collapsed guarantee §8 AC4 checks textually.

### 6d. Per-ticker verdict summary and the purification-by-ticker plot — grounded in what Phases 4–6 actually produce

The outer dispatch asks for "a per-ticker verdict summary chart... grounded in what Phase 4-6 actually
produce, not invented from nothing." Two candidates were considered against `BacktestResult`'s and
`PurificationLedger`'s own real, already-computed fields (confirmed by direct read, not assumed):

- **A full per-ticker `verdict_history` timeline chart** (one row per ticker, a colored segment per
  `VerdictObservation`, PURE/MIXED/NON_COMPLIANT over time) — genuinely richer, but `ComplianceState
  Record.verdict_history` carries only `(as_of_date, verdict)` pairs at REBALANCE granularity (quarterly
  — `mizan.backtest.clock._REBALANCE_MONTHS`), and a timeline chart's own visual value depends on a
  cadence dense enough to look like a continuous timeline rather than 2–4 discrete points per ticker
  over a typical synthetic-fixture backtest window. Rejected for THIS phase's own plot slot as a
  poor visual fit for the data's actual granularity, though `render_ticker_summary`'s own HTML table
  (§4.1) still renders every `verdict_history` observation count per ticker — the data is not lost,
  only not charted.
- **A purification-liability-by-ticker bar chart** (this document's choice, §4.2) — directly, cleanly
  derivable from `PurificationLedger.dividend_entries`/`divestment_entries`' own `ticker` field (a
  groupby-sum, the same shape of aggregation `mizan.purification.ledger.purify_backtest_result` itself
  already performs to compute `purification_liability`, §3.2 of `PHASE_6_SPEC.md`), and directly
  answers a question a reader of THIS report specifically cares about: which holdings are actually
  responsible for how much of the total purification liability just rendered above it (§6c). No new
  computation beyond a per-ticker sum of an already-typed field; no invented metric.

**Decision: `render_purification_by_ticker_plot` (§4.2) is Phase 7's second plot**, chosen over the
full-timeline alternative for the reason above; `render_ticker_summary`'s own table (§4.1) is where the
per-ticker verdict-history detail the rejected chart would have shown instead lives, in tabular rather
than charted form.

### 6e. Self-contained portability — inline base64, never a separate image directory

`MASTER_PRD.md` §9's own phrase — "static HTML + plots" as the V1 output shape — and this phase's own
outer dispatch both name the risk directly: a report that references sibling PNG files by relative path
breaks the moment the HTML file is copied, emailed, or opened from a different working directory than
the one it was generated into, without its image siblings coming along. **Decision: every plot is
embedded inline, as a base64-encoded `data:image/png;base64,...` URI inside an `<img src="...">` tag,
directly in the HTML document `render_report` returns.** `mizan/cli/report.py`'s `run()` writes exactly
ONE file to `--output-path` — no sibling `_files/` or `assets/` directory, no second write call
anywhere in this phase's own code. This is the genuinely portable reading of "static HTML + plots":
the deliverable is one file, openable by double-click from anywhere, matching this phase's own
single-user, no-ops-surface posture (`MASTER_PRD.md` §9) more closely than a multi-file bundle would.
The one real cost, named rather than hidden: base64 inflates binary size by roughly a third versus a raw
PNG file reference, and a very image-heavy report could grow the HTML file substantially — an accepted
tradeoff at this phase's own scope (two plots, a handful of KB each against a synthetic fixture), not a
concern this phase's own acceptance criteria need to bound numerically.

**Escaping discipline, stated once here because it applies to every rendering function in §4.1:** every
dynamic string value interpolated into the HTML output — ticker symbols, fiqh `source`/
`primary_source_gap` strings, caveat description text — passes through Python's standard-library
`html.escape()` before interpolation. This is the mechanism `render_report`'s own §8 AC6 (a
well-formed-HTML parse check) depends on: a `source` string containing a literal `&` or `<` character
(plausible in a citation string quoting a percentage or an inequality) would otherwise produce malformed
markup a naive `html.parser` pass would choke on.

---

## §7 Failure-Mode Guards

Pulled from `ULTIMATE_PRD.md` §4.8 (Reporting) specifically, plus this phase's own new surface.

| # | Failure mode | Guard Phase 7's code implements | What the review agent checks |
|---|---|---|---|
| G-R1 | A result renders without its caveat set (`ULTIMATE_PRD.md` §4.8's named failure mode) | `render_report`'s `active_caveats` parameter is keyword-only with no default (§4.1, §6a) — there is no call signature that omits it | `render_report(data)` (positional-only call, `active_caveats` omitted) raises `TypeError` at the call site, tested via `pytest.raises(TypeError)`; a static grep of every call site in `mizan/` (`mizan/cli/report.py`'s own `run()`) confirms `active_caveats=` is always passed explicitly |
| G-R2 | Survivorship/look-ahead/pending-verification caveat text present in code but missing from the rendered output | `CAVEAT_DESCRIPTIONS` (§3.2) is completeness-asserted against `Caveat` at import time; `render_caveats_banner` renders every member of `active_caveats` via that dict, verbatim | A snapshot/substring test: `render_report(...)`'s returned HTML contains `CAVEAT_DESCRIPTIONS[Caveat.LOOK_AHEAD_BIAS]`, `...[Caveat.SURVIVORSHIP_BIAS]`, `...[Caveat.PENDING_SCHOLARLY_VERIFICATION]`, each verbatim, when `active_caveats` contains all three (§8 AC3) |
| G-R3 | Gross and net-of-purification returns not both shown, or collapsed into one figure | `render_return_summary` (§4.1, §6c) renders two separately-`id`'d elements, never one | `id="gross-return"` and `id="net-of-purification-return"` both present in the output; their rendered numeric text differs whenever `ledger.purification_liability > 0.0` (reusing Phase 6's own nonzero-liability fixture, §8 AC4) |
| G-R4 | Fiqh register partially rendered (e.g. only the "most important" entries) | `render_fiqh_register` iterates all `type(fiqh_params).model_fields`, no filtering; an internal `AssertionError` fires if fewer than 11 rows are produced (§6b) | The rendered HTML contains exactly 11 `register_id` values, `1` through `11`, each exactly once (§8 AC5) |
| G-R5 | Generated HTML is malformed (unescaped `&`/`<` from an interpolated dynamic string breaks the markup) | Every dynamic interpolation site passes through `html.escape()` (§6e) | `html.parser.HTMLParser().feed(generated_html)` raises no exception for a real generated report (§8 AC6) |
| G-R6 | LLM/model SDK reachback, or LLM-authored narrative prose anywhere in the report | Forbidden-dependency list unchanged (§2.4); every string in the rendered output is either a fixed template fragment or a direct, `html.escape()`-d formatting of an already-computed typed value — no free-text generation step exists anywhere in `mizan/reporting/` | `grep -rniE "openai\|anthropic\|gemini\|vertex\|langchain\|\bllm\b\|chat_completion\|completion\(" mizan/reporting/` — no hit |
| G-R7 | `mizan/reporting/` gains accidental DuckDB write or read capability of its own | Neither `report.py` nor `plots.py` imports `duckdb` or accepts a connection parameter anywhere; both take only already-in-memory typed values | `grep -rn "duckdb" mizan/reporting/` — no hit; `grep -rniE "INSERT INTO\|CREATE TABLE\|ALTER TABLE\|DROP TABLE" mizan/reporting/` — no hit |
| G-R8 | `mizan/cli/report.py` re-derives against a DIFFERENT `con`/`cache_dir`/`overrides` than the `run_backtest()` call used (mirrors Phase 6's G-P7) | `run()` threads the exact same local `con`/`args.cache_dir`/`overrides` variables into both `run_backtest(...)` and `purify_backtest_result(...)`, never re-opening a connection or re-loading the override map between them | Code inspection of `mizan/cli/report.py`'s `run()`: exactly one `db.connect(...)` call and one `load_override_map(...)` call, both variables reused, not reassigned |
| G-R9 | An empty-`daily_snapshots`/empty-ledger backtest crashes `render_equity_curve_plot`/`render_purification_by_ticker_plot` instead of rendering an honest "nothing to show" state | Both functions branch explicitly on the empty case and render an annotated placeholder figure rather than indexing into an empty sequence or dividing by zero (§4.2) | A test constructing a `BacktestResult` with `daily_snapshots=()` and an empty `PurificationLedger` calls both plot functions and asserts they return valid, non-empty PNG `bytes` without raising |
| G-BOUND3 | Any of `short/borrow/margin/leverage/option/future/swap/derivative` naming anywhere under `mizan/reporting/` | None of these words appears anywhere in this phase's code, comments, or identifiers | `grep -rniE "\b(short\|shorts\|shorting\|borrow\|borrowed\|borrowing\|margin\|leverage\|leveraged\|levered\|option\|options\|future\|futures\|swap\|swaps\|derivative\|derivatives)\b" mizan/reporting/` — no hit |
| G-AI | AI attribution in commit messages | Same neutral-commit convention as Phases 1–6 | `git log --format=%B` for this phase's commits — no `Co-Authored-By`, no "Generated with," no model/assistant name |

**Categorisation, mirroring Phases 1–6:** G-R1, G-R2, G-R3, G-R6, G-BOUND3, G-AI are **HALT-for-human**
(`ULTIMATE_PRD.md` §4.8's own three named Reporting failure modes are G-R1/G-R2/G-R3 verbatim, all
three categorized HALT-for-human there already). G-R4, G-R5, G-R7, G-R8, G-R9 are blocking-but-
mechanical.

---

## §8 Phase Acceptance Criteria

Each concrete, independently checkable by a third party, same standard Phases 1–6 applied, reusing
Phase 4/5/6's synthetic fixture set (sixteen tickers, `tests/fixtures/synthetic_universe.py`,
unmodified by this phase — Phase 7 adds no new fixture ticker, needing none: every plot/table this
phase renders is a presentation of data the existing fixture set already exercises).

1. **Caveats render before any numeric figure, in the literal generated HTML string.** For a report
   generated with a nonempty `active_caveats`, `generated_html.index('id="caveats"') <
   generated_html.index('id="gross-return"')` — and likewise `< index('id="fiqh-register"')`,
   `< index('id="ticker-summary"')` — proving the caveat banner is structurally first, not merely
   documented as intended to be first (§6a).
2. **Calling `render_report` without `active_caveats` raises `TypeError`, not a silent default.**
   `pytest.raises(TypeError): render_report(some_report_input)` (positional call, keyword omitted)
   passes; `render_report(some_report_input, active_caveats=())` — an explicit empty tuple — does NOT
   raise (§6a, §7 guard G-R1). `mypy --strict` flags any call site in `mizan/` that omits the keyword
   (there is exactly one call site, `mizan/cli/report.py`, which always supplies it).
3. **Every one of the three `Caveat` members' description text appears verbatim in the generated
   HTML** when `active_caveats` contains all three — `CAVEAT_DESCRIPTIONS[Caveat.LOOK_AHEAD_BIAS]`,
   `[Caveat.SURVIVORSHIP_BIAS]`, `[Caveat.PENDING_SCHOLARLY_VERIFICATION]`, each a verbatim substring
   of the returned HTML `str` (§6a, §7 guard G-R2).
4. **Gross and net-of-purification returns are both present, distinctly labelled, and differ whenever
   the ledger is nonzero.** For a fixture backtest whose `purification_liability > 0.0` (reusing Phase
   6's own `ZZDIVEST_APPREC01`/`ZZMIXED_RATIODRIFT01`-driven nonzero fixture), the rendered numeric
   text under `id="gross-return"` and `id="net-of-purification-return"` differ; for a fixture with an
   empty ledger (`purification_liability == 0.0`), the two figures coincide — the one case they may
   (§6c, §7 guard G-R3, mirroring `PHASE_6_SPEC.md` §8 AC5 at the rendered-output layer).
5. **All 11 `FiqhParams` register entries appear in the rendered output**, each with its `register_id`
   (1 through 11, each exactly once), `value`, `source`, and `status` — a genuinely complete
   honesty-surface rendering, not a partial one (§6b, §7 guard G-R4).
6. **The generated HTML file is well-formed / parseable.** `html.parser.HTMLParser().feed(...)` (or
   equivalent) run against a real report generated by `mizan report` over the synthetic fixture raises
   no exception (§6e, §7 guard G-R5).
7. **The full pipeline runs end-to-end against the synthetic fixture with no crash.** `mizan report
   --ticker ... --start-date ... --end-date ... --initial-cash ... --db-path ... --cache-dir ...
   --output-path out.html` (ingest is skipped/pre-seeded, same posture every prior phase's own
   end-to-end acceptance criterion takes, since it needs real network access) against the synthetic
   fixture set produces a real, nonempty HTML file at `out.html`, exit code 0, no traceback — including
   at least one run over a fixture combination that reaches BOTH plot functions' own empty-input
   branches (§7 guard G-R9) without crashing, proving §4.2's placeholder-rendering paths are real, not
   theoretical.
8. **Both plot functions return valid PNG bytes.** `render_equity_curve_plot(...)` and `render_
   purification_by_ticker_plot(...)`, called directly in a unit test against fixture data, each return
   `bytes` beginning with the PNG magic number (`b"\x89PNG\r\n\x1a\n"`) — proving the `Agg`-backend
   render path actually produces a decodable image, not merely "does not raise."
9. **Plots are embedded inline, never referenced by external path.** The generated HTML contains no
   `<img src="...">` whose `src` is a relative or absolute filesystem path — every `<img>` `src` begins
   with `data:image/png;base64,` (§6e); `mizan/cli/report.py`'s `run()` writes exactly one file to disk
   per invocation (a test asserting the output directory's file count is unchanged apart from the one
   `--output-path` file).
10. **`ReportInput` rejects a non-purified `BacktestResult`.** `ReportInput(backtest_result=<a
    BacktestResult with purification_ledger=None>, fiqh_params=FIQH_PARAMS)` raises
    `pydantic.ValidationError` (§3.1's own `model_validator`).
11. **`mizan/cli/report.py` reuses the caller's own `con`/`cache_dir`/`overrides`, never re-loading
    them, mirroring Phase 6's own guard.** Code inspection confirms exactly one `db.connect`/
    `load_override_map` call site each, both variables threaded unmodified into both the
    `run_backtest` and `purify_backtest_result` calls (§7 guard G-R8).
12. **`mizan/reporting/` never touches DuckDB.** No `import duckdb`, no `INSERT`/`CREATE`/`ALTER`/
    `DROP`, anywhere under `mizan/reporting/` (§5, §7 guard G-R7).
13. **Every new Pydantic model inherits `MizanBaseModel`.** `ReportInput` is the only new model this
    phase defines (§3.1); confirmed it subclasses `MizanBaseModel`, not `pydantic.BaseModel` directly.
14. **`mizan report` completes the four-verb CLI set.** `mizan --help` lists `ingest`, `screen`,
    `backtest`, and `report` as subcommands (`mizan/cli/main.py`'s `build_parser()`, §1); `mizan report
    --help` shows the flag set §4.3 specifies, including the one new `--output-path` flag.
15. **No LLM/model-client SDK import, no LLM-authored narrative prose, and no boundary-crossing
    primitive naming, anywhere in `mizan/reporting/`.** `ULTIMATE_PRD.md` §5 checks 1–8 (re-run over
    the expanded tree, §7's corrected-path convention continued for `mizan/reporting/`), plus a direct
    read confirming every string literal in `mizan/reporting/report.py` is either a fixed template
    fragment or a direct format of an already-typed value — no free-text-generation call of any kind.
16. **`matplotlib` is a real, non-optional runtime dependency after this phase, pinned at exactly
    `3.11.1`.** `pyproject.toml`'s `[project.dependencies]` list contains `"matplotlib==3.11.1"`; the
    `[project.optional-dependencies].report` group no longer exists (§2.1).
17. **No new dependency beyond `matplotlib`'s promotion.** `pyproject.toml`'s dependency set otherwise
    matches Phase 6's own, unmodified — no Jinja2 or other templating library added (§2.2); `pandas`
    remains forward-declared and unused (§2.3).
18. **mypy --strict mizan tests exits 0.** Built and verified inside the project's `.venv`, per
    `PHASE_3_SPEC.md` AC14's established requirement.
19. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5`.
20. **`pytest` passes in full**, all three new test files plus the entire existing Phase 1–6 suite (no
    regression) — including `tests/fixtures/synthetic_universe.py` remaining byte-for-byte unmodified
    by this phase's own diff (confirmed by direct diff inspection, not merely by tests passing).
21. **Commits are neutral.** No AI attribution in `git log` for this phase's commits.
22. **Boundary greps are clean**, re-run from repo root against the full tree including
    `mizan/reporting/*.py` and `mizan/cli/report.py` (`ULTIMATE_PRD.md` §5 checks 1–8).

**Any single failing criterion is a phase-loop HALT, not a partial pass** — same standard Phases 1–6
state, applied here.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 7)

- **No dashboard, no live UI, no FastAPI, no Next.js, no web server of any kind.** Unchanged, permanent
  boundary, restated here specifically because Phase 7 is the "output" layer where the temptation to
  build a real web UI is highest (`MASTER_PRD.md` §9's own "notebook/CLI-first, static HTML+plots...
  No Next.js dashboard in V1" — `ULTIMATE_PRD.md` §1's "no FastAPI, no dashboard, no concurrency-ops
  surface this tool doesn't need"). `mizan report`'s own output is a single static file a human opens
  in a browser by double-click — nothing in this phase serves it, watches it, or makes it interactive.
- **No LLM-generated narrative, summary, or interpretive prose anywhere in the report.** Every string
  the report renders is either a fixed template fragment (this phase's own code) or a direct,
  `html.escape()`-d formatting of an already-computed value from an earlier phase (§6e, §7 guard G-R6,
  §8 AC15). Reports are **deterministic renders of already-computed data**, never LLM-authored — this
  is a permanent posture, not a "for now" (mirrors `ULTIMATE_PRD.md` §5's own "no LLM in the V1 core...
  permanent, not a for now" framing for the deterministic core, extended here to the output layer that
  consumes it).
- **No real report generated against the real ~100-ticker universe.** Unchanged from every prior
  phase's own honesty posture (`PHASE_4/5/6_SPEC.md` §9): the real curated universe still does not
  exist (`COMPREHENSION.md` §6's single most prominent carried-forward open item). Phase 7's own
  acceptance criteria (§8) run only against the synthetic fixture set — never against a named real
  company — and the generated report's own honesty-surface content (§6a/§6b) is exactly the mechanism
  that would make this limitation visible to a human reader if this software were ever pointed at real
  tickers before that universe exists.
- **No day-by-day PERSISTED liability time series, no new `PurificationLedger` field.** §6c's own
  reconstruction (the equity-curve plot's internal running sum) is computed fresh, privately, inside
  `render_equity_curve_plot` every time the report is generated — it is not written back into
  `PurificationLedger` or any other Phase 5/6-owned model, and Phase 7 adds no new field to either.
- **No PDF, no interactive/JS-charting library (Plotly, D3, Chart.js), no client-side script of any
  kind in the generated HTML.** The deliverable is exactly "static HTML + plots" (`MASTER_PRD.md` §9's
  own literal phrase) — static raster images (`matplotlib`-rendered PNGs, §2.1/§6e), not an interactive
  or scripted document. Nothing in this phase's own scope calls for more.
- **No CLI flag to override which plots render, or to suppress the fiqh register / caveat banner.**
  Every section §4.1 defines always renders, unconditionally — a report that could be configured to
  omit its own honesty surface would defeat this whole phase's purpose (§6a/§6b). `--output-path` is
  the only new flag this phase adds (§4.3).
- **No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3), and no change to any `FiqhParam`
  register value or the register's own field set.** Unchanged from Phases 1–6 — Phase 7 reads
  `FiqhParams` and renders it; it does not touch `mizan/config/fiqh_params.py` at all.
- **This is genuinely the LAST phase of Mizan V1** (§0). No `mizan/reporting/` subpackage split, no
  Phase 8. The dispatch immediately following this phase's own review-approval and comprehension pass
  writes `BUILD_COMPLETE.md`, not `PHASE_8_SPEC.md` — there is no further phase spec to draft after
  this one.

---

## VERSION CONTROL

Commit: `docs: Phase 7 technical blueprint (mizan)`. No push (no remote configured; local commit only,
per this dispatch's own instruction).
