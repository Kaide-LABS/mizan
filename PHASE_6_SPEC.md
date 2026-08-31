# PHASE_6_SPEC.md — Mizan: Purification Engine (side-ledger)

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), the same document `PHASE_1_SPEC.md`–`PHASE_5_SPEC.md` were built from. Every
> schema decision, every function signature, and every guard below traces to a section of that
> document, cited inline, cross-checked against `MASTER_PRD.md` where `ULTIMATE_PRD.md` is silent,
> and against the committed Phase 1 code (`mizan/config/fiqh_params.py`, `mizan/core/verdict.py`,
> `mizan/core/caveats.py`), Phase 3 code (`mizan/data/db.py`, `mizan/data/models.py`), Phase 4 code
> (`mizan/screening/verdict.py`, `mizan/screening/financial_ratios.py`), and Phase 5 code
> (`mizan/backtest/clock.py`, `mizan/backtest/compliance_state.py`, `mizan/backtest/portfolio.py`,
> `mizan/cli/backtest.py`, `tests/fixtures/synthetic_universe.py`) for integration fidelity. Every
> code excerpt and every field name below was read from the actual committed files this pass, not
> recalled from `PHASE_5_SPEC.md`'s own illustrative blocks — see §3.1's `purification_ledger`
> placeholder-type decision and §6a's ratio-pinning mechanism, both of which required reading Phase
> 5's real `BacktestResult`/`ComplianceStateRecord`/`DividendEvent` field shapes directly, not
> assuming they carry a ratio value Phase 5 never in fact recorded.

**Generated:** 2026-08-31 · **Dispatch type:** phase advancement (Phase 5 review-approved 2026-08-30,
comprehension pass complete 2026-08-31; no code review or fix loop runs in this dispatch — this
document is the deliverable) · **Canonical references:** `ULTIMATE_PRD.md` (governs, esp. §2.1's two
load-bearing seams — "a backtest result is `(returns, purification_ledger, active_caveats)`" — §4.7
Purification failure modes, §5 the grep-able Hard Boundary, §6 the execution spec naming Phase 6
"Purification"), `MASTER_PRD.md` (governs where `ULTIMATE_PRD.md` is silent, principally §8 the
Purification Engine section — Forks A/B/C verbatim — and §10 register entries #9/#10/#11, plus a
re-read of #8 `grace_period_rebalances`, already consumed by Phase 5), `docs/modernization_log.md`
(pinned external reality — §6.2 Tiingo's `divCash` field, §6.2b the `splitFactor` resolution Phase 5
logged), `COMPREHENSION.md` (what Phases 1–5 actually shipped, including the open item that
`BacktestResult.purification_ledger` is always `None` and nothing yet computes a purification
amount — §6 below is where that closes), `PHASE_1_SPEC.md` (`MizanBaseModel`, `Verdict`,
`Caveat`/`ResultEnvelope`, `FIQH_PARAMS` register entries #9/#10/#11 — all Phase 6 **consumes**, none
of which it may redefine), `PHASE_4_SPEC.md` (`mizan.screening.verdict.screen`, `ScreeningVerdict`,
`ReasonTraceEntry`/`ScreenName` — Phase 6's ratio-pinning mechanism, §6a below, is built entirely on
top of this surface, re-invoked rather than re-implemented), `PHASE_5_SPEC.md` (format/rigor
precedent, and the public surface — `mizan.backtest.clock.run_backtest`/`BacktestResult`/
`DailySnapshot`, `mizan.backtest.compliance_state.ComplianceStateRecord`/`DivestmentEvent`/
`DividendEvent`/`VerdictObservation`, `mizan.cli.backtest.run` — Phase 6 must consume without
reshaping, restated in full at §1), and `tests/fixtures/synthetic_universe.py` (the thirteen
synthetic tickers Phases 4–5 already built, extended additively by this phase — §6a/§8).

**No citation re-verification gate applies to this document**, unchanged from
`PHASE_2/3/4/5_SPEC.md`'s own confirmation. Phase 6 introduces no new arXiv citation of its own; it
introduces no new external API contract either (`mizan/purification/` reads only DuckDB tables Phase
3 already normalized and calls only `mizan.screening.verdict.screen`, which Phase 4 already built and
this document does not modify). This file carries no §0.5.

---

## §0 Phase Plan Header

# **Phase 6 of 7: Purification Engine (side-ledger)**

Phase sequence, unchanged from `PHASE_5_SPEC.md` §0 / `ULTIMATE_PRD.md` §6 (re-derived there, not
re-derived again here):

| # | Phase | Ships |
|---|---|---|
| 1 | Foundation & Config (done, approved) | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| 2 | Ingestion & raw cache (done, approved) | EDGAR (`companyfacts` + `companyconcept` + `submissions`) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store (done, approved) | `data/normalize.py`, `data/db.py`, typed `fundamentals_facts`/`price_bars` tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine (done, approved) | `screening/business_activity.py`, `screening/financial_ratios.py` (30/30/5, two-axis denominator from config), `screening/verdict.py` (combines both into a three-state `Verdict` + reason trace — the `screen()` entry point), `mizan/cli/screen.py` |
| 5 | Backtest engine + compliance-flip state machine (done, approved) | `backtest/clock.py` (quarterly-rebalance event loop, `run_backtest()`), `backtest/portfolio.py`, `backtest/strategy.py`, `backtest/compliance_state.py` (flip→grace→divest state machine), `mizan/cli/backtest.py` |
| **6** | **Purification engine** ← *this document* | `mizan/purification/ledger.py` (Fork B — side-ledger accrual, gross/net-of-purification return), `mizan/purification/attribution.py` (Fork C — forced-divestment price-appreciation attribution), `mizan/cli/backtest.py` MODIFIED (purification wired in as a post-processing pass) |
| 7 | Reporting | static HTML + matplotlib, caveats non-optional, gross vs net-of-purification as two distinct figures |

This spec covers **Phase 6 only**. It is the contract the Phase 6 execution agent builds against and
the Phase 6 review agent (next round of Step 12) verifies against. Phase 6 **consumes** Phase 1's
public surface (`mizan.core.base.MizanBaseModel`, `mizan.core.verdict.Verdict`, `mizan.core.caveats.
Caveat`/`ResultEnvelope`, `mizan.config.fiqh_params.FIQH_PARAMS` register entries #9 `purify_capital_
gains`, #10 `divestment_attribution_method`, #11 `purification_accounting_method`), Phase 3's public
surface (`mizan.data.db.connect`, the `price_bars.raw_close`/`div_cash` columns), Phase 4's public
surface (`mizan.screening.verdict.screen`, `ScreeningVerdict`, `ReasonTraceEntry`/`ScreenName`,
`mizan.screening.business_activity.BusinessActivityOverrideMap`), and Phase 5's public surface
(`mizan.backtest.clock.run_backtest`/`BacktestResult`/`DailySnapshot`, `mizan.backtest.
compliance_state.ComplianceStateRecord`/`VerdictObservation`/`DivestmentEvent`/`DividendEvent`,
`mizan.cli.backtest.run`) and **must not reshape any of them** — including `BacktestResult.
purification_ledger`'s own field TYPE (`dict[str, object] | None`), which Phase 5's own docstring
already settled Phase 6 must populate, not replace (§3.1 below, quoting it verbatim). Phase 6 may
only extend that surface additively — including one additive extension to `tests/fixtures/
synthetic_universe.py` (§6a/§8: `PriceBarFixture` gains one new, defaulted field, and three new
synthetic tickers are appended to `ALL_SYNTHETIC_TICKERS`; nothing existing is modified in place).
Every new symbol Phase 6 introduces (`mizan.purification.*`) is itself now locked for Phase 7 the
same way.

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`.** Same flat layout `PHASE_1_SPEC.md`–`PHASE_5_SPEC.md` §1
preserved — no nesting directory. Every file below is new except `mizan/cli/backtest.py` and
`tests/fixtures/synthetic_universe.py` (both additive-only modifications) and `tests/
test_cli_backtest.py` (additive-only new test cases appended).

```
C:\Users\hp\HMS\
├── mizan/
│   └── purification/
│       ├── __init__.py            # NEW — empty, package marker only (mizan/backtest/__init__.py precedent)
│       ├── ledger.py               # NEW — DividendPurificationEntry/PurificationLedger models, purify_dividend,
│       │                           #        purify_backtest_result (Fork A trigger + Fork B accrual, §3, §4, §6a, §6d)
│       └── attribution.py          # NEW — DivestmentPurificationEntry model, compute_divestment_attribution
│                                    #        (Fork C, §3, §4, §6b, §6c)
└── tests/
    ├── fixtures/
    │   └── synthetic_universe.py   # MODIFIED (additive only) — PriceBarFixture.div_cash field (defaulted
    │                               #        0.0, §6a), three new tickers: ZZMIXED_RATIODRIFT01, ZZPURE_DIV01,
    │                               #        ZZDIVEST_APPREC01 (§6a, §6b, §8)
    ├── test_purification_ledger.py       # NEW
    ├── test_purification_attribution.py  # NEW
    └── test_cli_backtest.py              # MODIFIED (additive) — new cases for the purification summary
                                           #        `mizan backtest` now prints (§4.3)
```

**A deliberate deviation from `MASTER_PRD.md` §9.4's module boundaries diagram and `ULTIMATE_PRD.md`
§5 check 5's own grep line, named explicitly rather than silently taken:** both documents name the
future module as a single file, `mizan/backtest/purification.py`, and `PHASE_5_SPEC.md` §1/§9 restate
that expectation verbatim ("Phase 6's own module is `mizan/backtest/purification.py`, per
`MASTER_PRD.md` §9.4"). This document instead ships a top-level `mizan/purification/` package with
two modules. Justification, not a stylistic preference: (1) Fork B (side-ledger accrual — a pure
function of already-computed dividend/divestment events) and Fork C (a genuinely separate
computation — a price-appreciation lookup keyed off the flip/divest window) are as cleanly separable
as Phase 4's own `business_activity.py`/`financial_ratios.py` split, which this phase's package layout
directly mirrors; (2) `MASTER_PRD.md` §9.1's own pipeline diagram already draws purification as a
distinct box fed by two independent edges (`compliance_state` and dividends), not as a sub-component
of `backtest/`, so promoting it to a top-level package is a closer match to that diagram than nesting
it under `backtest/`; (3) Phase 6 is, structurally, a pure post-processing / reporting-adjacent
consumer of a completed `BacktestResult` (§6c below), not a participant in the daily event loop, which
argues against `mizan/backtest/` as its home. **Consequence for `ULTIMATE_PRD.md` §5 check 5's own
grep line** (`grep -rniE "openai|anthropic|..." mizan/screening/ mizan/backtest/compliance_state.py
mizan/backtest/purification.py`): that literal path no longer resolves to a real file after this
phase; the equivalent, corrected check for a Phase 6 reviewer to run is the same pattern extended to
`mizan/purification/` (restated in §7's guard table below, not silently left stale).

**Confirmed: this phase does not touch `mizan/backtest/` or `mizan/screening/`.** `mizan/purification/
ledger.py` and `attribution.py` import and call `mizan.backtest.clock.BacktestResult`, `mizan.backtest.
compliance_state.{ComplianceStateRecord, DivestmentEvent, DividendEvent, VerdictObservation}`, and
`mizan.screening.verdict.screen` — they never edit any of those modules' own files. `mizan/cli/
backtest.py` is the one file under an EARLIER phase's ownership this phase modifies, and only
additively: one new import, one new function call (`purify_backtest_result`) inserted between
`run_backtest()` returning and the CLI's existing summary-printing code, and a handful of new `print(
...)` lines appended after the existing ones — every line `PHASE_5_SPEC.md` §4.5 already specified
stays byte-for-byte in place.

---

## §2 Dependencies

### 2.1 No new dependency

**Decision: Phase 6 adds zero new third-party dependencies**, same posture `PHASE_5_SPEC.md` §2.1
took. `pydantic` (the three new models below) and `duckdb` (one `price_bars.raw_close` read per
`DivestmentEvent`, plus the `screen()` calls Phase 6 re-invokes) already cover everything this phase
needs. `pyarrow` is not imported anywhere under `mizan/purification/` — like Phase 5, this phase only
ever reads rows back out of DuckDB via `con.execute(...).fetchone()`/`.fetchall()`.

### 2.2 `pandas` — still deliberately NOT promoted

Same decision `PHASE_5_SPEC.md` §2.2 took, re-examined rather than copied: Phase 6's own arithmetic
(one dividend-ratio multiplication per `DividendEvent`, one price-appreciation subtraction per
`DivestmentEvent`, one running-sum accrual, two two-point return computations) is exactly the kind of
small, explicit Python loop over already-typed Pydantic/`float` values Phase 5 already declined to
promote `pandas` for. **Decision: still no.** `pandas` remains forward-declared and unused in
`[project.optional-dependencies].data` until Phase 7.

### 2.3 Forbidden-dependency list unchanged, and load-bearing for this phase specifically

`PHASE_1_SPEC.md` §2.5's permanently forbidden list (`openai`, `anthropic`, every other LLM/model SDK,
`yfinance`) still applies, unmodified. Purification is arithmetic over already-decided verdicts and
already-recorded events — there is no decision-under-uncertainty step here an LLM could plausibly be
reached for, but the grep-based guard is restated in §7 regardless, at its corrected path (§1).

### 2.4 Modernization-log reconciliation

Phase 6 introduces no new external-API field this pass has not already verified: `price_bars.div_cash`
(Tiingo's `divCash`, `docs/modernization_log.md` §6.2) and `price_bars.raw_close` (§6.2b's own
`splitFactor` resolution already settled the surrounding valuation discipline) are both read-only
consumption of a Phase-3-normalized column this phase does not re-verify or re-derive. No new dated
entry is required in `docs/modernization_log.md` unless the build agent discovers a live discrepancy.

---

## §3 Pydantic Schemas

Every new model inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no Phase 6 module subclasses `pydantic.BaseModel` directly, same guard
every prior phase has held. Because every model is frozen, a `PurificationLedger` is an immutable,
fully-computed value — Phase 6 never mutates a ledger in place; `purify_backtest_result` (§4.1)
constructs one exactly once and attaches it to a *new* `BacktestResult` via `model_copy`.

### 3.1 The `BacktestResult.purification_ledger` placeholder — populated, not retyped

`PHASE_5_SPEC.md` §3.4 already decided this question, in Phase 5's own words, quoted verbatim because
it is binding rather than merely informative:

> "`purification_ledger` is a deliberate, loose placeholder — `dict[str, object] | None`, defaulting
> to `None`... Phase 6 needs to attach a real, typed ledger here WITHOUT Phase 5 having to guess its
> shape, and WITHOUT this field's own type ever changing (a type change would violate every prior
> phase's 'additive extension only, never a renamed/removed symbol' rule). **Phase 6 populates this
> dict (via its own typed model's `.model_dump()`, the same round-trip pattern
> `ScreeningVerdict.model_validate(envelope.payload)` already establishes) rather than replacing the
> field's type.**"

**This document's own answer to the "is narrowing a placeholder field's type a safe additive change"
question the outer dispatch poses: no, not here, and Phase 5 already settled why.** In the abstract,
narrowing `dict[str, object] | None` to a concrete Pydantic model type IS a defensible reading of
"additive extension" (the field name is unchanged, the `None` default is unchanged, no existing
caller's code that merely checks `is None` would break). But `BacktestResult` is a Phase-5-owned,
review-approved, committed model, and Phase 5's own spec already made an explicit, reasoned decision
on exactly this question, on Phase 6's behalf, with a stated rationale (guarding against a *future*
type change, not merely this one). Overriding that decision would require a `PHASE_5_SPEC.md`
revision — out of scope for this ADVANCEMENT-ONLY dispatch, which drafts `PHASE_6_SPEC.md` and touches
nothing already approved. **Decision: `BacktestResult.purification_ledger`'s type stays exactly
`dict[str, object] | None`, unmodified.** `purify_backtest_result` (§4.1) constructs a fully-typed
`PurificationLedger` (below), calls `.model_dump()` on it, and assigns the resulting dict to a *new*
`BacktestResult` via `model_copy(update={"purification_ledger": ledger.model_dump()})`. Any caller
needing the typed shape back reconstructs it via `PurificationLedger.model_validate(result.
purification_ledger)` — the identical round-trip discipline `ScreeningVerdict.model_validate(envelope.
payload)` already established in Phase 4, now applied one layer deeper.

### 3.2 `mizan/purification/ledger.py` — Fork A trigger + Fork B ledger entries

```python
from __future__ import annotations

from datetime import date

from pydantic import Field

from mizan.core.base import MizanBaseModel


class DividendPurificationEntry(MizanBaseModel):
    """One Fork-A purification event: `non_compliant_income_ratio × dividend_amount` for one
    dividend paid by a Mixed holding (`MASTER_PRD.md` §8's own trigger wording). Produced only for a
    dividend whose PINNED verdict (§6a) is `Verdict.MIXED` — never for a Pure-verdict dividend (ratio
    is definitionally 0, so no entry is produced at all, not a zero-amount one, §6a) — and, for a
    dividend pinned to a Non-compliant grace-window verdict, using §6a's documented last-Mixed-ratio
    fallback, never the Non-compliant verdict's own (frequently absent, §6a) ratio.
    """

    ticker: str
    cik: str
    ex_date: date
    """`DividendEvent.ex_date` this entry purifies — 1:1, never aggregated across dividends."""
    ratio_used: float = Field(ge=0.0)
    """`non_permissible_income_ratio.actual_value` from the re-derived `ScreeningVerdict.reason_trace`
    at `ratio_as_of_date` (§6a) — never the ratio active at any OTHER date, including the backtest's
    own most-recent rebalance if that differs from the verdict active at `ex_date`."""
    ratio_as_of_date: date
    """The rebalance date the pinned `VerdictObservation` was recorded at — the auditable proof this
    is a date-indexed lookup, not a "most recent screen" shortcut (`ULTIMATE_PRD.md` §4.7's own named
    failure mode, guard G-P1, §7). Always `<= ex_date`."""
    dividend_cash_received: float = Field(ge=0.0)
    """`DividendEvent.cash_received` this entry purifies, copied verbatim (never re-derived) so a
    reconciliation pass (§8) can sum this field across every entry and compare against
    `BacktestResult.dividend_events`' own total without re-computing anything."""
    purified_amount: float = Field(ge=0.0)
    """`ratio_used * dividend_cash_received`, exactly."""


class PurificationLedger(MizanBaseModel):
    """The full Phase 6 result: every Fork-A dividend entry, every Fork-C divestment entry (§3.3,
    `mizan/purification/attribution.py`), the Fork-B running liability, and the two Fork-B return
    figures (`MASTER_PRD.md` §8: "report two numbers... so the drag is its own visible figure, not a
    silent NAV distortion"). This is the concrete type `BacktestResult.purification_ledger`'s dict
    placeholder is populated FROM (§3.1) — never the field's own declared type.
    """

    dividend_entries: tuple[DividendPurificationEntry, ...]
    divestment_entries: tuple[DivestmentPurificationEntry, ...]
    """`DivestmentPurificationEntry` is defined in `mizan/purification/attribution.py` (§3.3) and
    imported directly into `ledger.py` (`attribution.py` has no reverse dependency on `ledger.py`, so
    this is a plain one-way import, not a circular one requiring string forward-references or
    `model_rebuild()`). Empty `()` whenever `fiqh_params.purify_capital_gains.value` is `False` (the
    V1 default, §6c) —
    never populated with zero-amount placeholder entries in that case, distinct from an individual
    divestment's own zero-appreciation entry when the gate IS open (§6b)."""
    purification_liability: float = Field(ge=0.0)
    """`sum(e.purified_amount for e in dividend_entries) + sum(e.purified_amount for e in
    divestment_entries)` — the Fork-B "running purification_liability", exactly. A single, final
    aggregate for V1; a day-by-day running series, if ever wanted, is trivially reconstructible by a
    later phase from each entry's own date field and is a Phase-7 reporting concern, not something
    this phase materializes as a second parallel time series alongside `BacktestResult.
    daily_snapshots` (§6d)."""
    gross_return: float
    """`(daily_snapshots[-1].portfolio_value - daily_snapshots[0].portfolio_value) /
    daily_snapshots[0].portfolio_value` — a plain point-to-point total return over the backtest
    window, computed directly from Phase 5's own `daily_snapshots` series, untouched by
    purification (§6d). Deliberately NOT annualized, risk-adjusted, or time-weighted — `MASTER_PRD.md`
    §8 Fork B's literal requirement is "report two numbers... so the drag is its own visible figure",
    which this satisfies without anticipating Phase 7's own, richer return methodology; Phase 7's
    reporter is free to compute additional return figures FROM `daily_snapshots` and
    `purification_liability` directly, and does not need this field to be the final word on return
    methodology (§6d)."""
    net_of_purification_return: float
    """`(daily_snapshots[-1].portfolio_value - purification_liability -
    daily_snapshots[0].portfolio_value) / daily_snapshots[0].portfolio_value` — computed ONLY here,
    at this ledger's own top level, as a reporting-level subtraction. This is the ONLY place in Phase
    6's own code `purification_liability` is subtracted from anything — `daily_snapshots`,
    `Portfolio.cash`, and every other Phase-5-owned value are read but never written by this phase
    (`ULTIMATE_PRD.md` §4.7's "purification silently netted into NAV" failure mode, guard G-P3, §7).
    `gross_return` and `net_of_purification_return` are always both present and are equal to each
    other iff `purification_liability == 0.0` exactly (an empty ledger) — never silently equal
    otherwise (§8 AC)."""
```

### 3.3 `mizan/purification/attribution.py` — Fork C ledger entries

```python
from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from mizan.core.base import MizanBaseModel


class DivestmentPurificationEntry(MizanBaseModel):
    """One Fork-C purification event: the price appreciation of a forced-divested holding over its
    exact non-compliant window (`MASTER_PRD.md` §8 Fork C, `flip_date` → `divest_date`,
    time-bounded). Produced for EVERY `DivestmentEvent` in `BacktestResult.divestment_events` when
    `fiqh_params.purify_capital_gains.value` is `True` (§6c) — including a `purified_amount == 0.0`
    entry when the window's price appreciation is zero or negative (§6b) — never omitted the way a
    Pure-verdict dividend's non-entry is (§3.2): a `DivestmentEvent` is a concrete, already-happened
    event, and recording "the window was checked, nothing to purify" is the auditable choice, not an
    ambiguous absence.
    """

    ticker: str
    cik: str
    flip_date: date
    """Copied verbatim from `DivestmentEvent.flip_date` / `ComplianceStateRecord.flip_date` — never
    re-derived independently (`ULTIMATE_PRD.md` §4.7's second named failure mode, guard G-P2, §7)."""
    divest_date: date
    """Copied verbatim from `DivestmentEvent.divest_date` / `ComplianceStateRecord.divest_date`,
    same non-re-derivation guarantee as `flip_date`."""
    quantity_liquidated: float = Field(ge=0.0)
    """The holding's quantity at the moment of forced liquidation, read from `BacktestResult.
    daily_snapshots` at `as_of_date == flip_date` (§6b) — never re-queried from `Portfolio` (Phase 6
    never holds a live `Portfolio` reference; it only ever reads a completed `BacktestResult`)."""
    price_at_flip: float = Field(ge=0.0)
    """`price_bars.raw_close` for `ticker` on `flip_date`, per §6a's raw-close-governs-valuation
    precedent (`PHASE_5_SPEC.md` §6a) — never `adj_close`."""
    price_at_divest: float = Field(ge=0.0)
    """`price_bars.raw_close` for `ticker` on `divest_date`, same precedent."""
    purified_amount: float = Field(ge=0.0)
    """`max(0.0, quantity_liquidated * (price_at_divest - price_at_flip))` — floored at zero because
    a price DECLINE during the non-compliant window produces no gain to purify; AAOIFI's purification
    concept removes impermissible INCOME, and there is no income, let alone non-halal income, in a
    loss (§6b's own worked reasoning, a named judgment call, not silently assumed)."""

    @model_validator(mode="after")
    def _flip_before_or_equal_divest(self) -> "DivestmentPurificationEntry":
        """`ULTIMATE_PRD.md` §4.7's own guard, restated at the type level: `flip_date <= divest_date`
        is asserted here, not merely hoped for by the function that constructs this entry."""
        if self.flip_date > self.divest_date:
            raise ValueError(
                f"{self.ticker}: flip_date {self.flip_date} must be <= divest_date "
                f"{self.divest_date}"
            )
        return self
```

---

## §4 Public Interfaces / Function Signatures

### 4.1 `mizan/purification/ledger.py`

```python
def purify_dividend(
    dividend_event: DividendEvent,
    compliance_state: ComplianceStateRecord,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> DividendPurificationEntry | None:
    """Fork A for one `DividendEvent`. Looks up the `VerdictObservation` in `compliance_state.
    verdict_history` most recently established as of `dividend_event.ex_date` (`ratio_as_of_date`,
    §6a) — asserting its `.verdict` equals `dividend_event.verdict_at_ex_date`, since Phase 5 already
    computed and stamped that value from this exact lookup (`mizan/backtest/clock.py`'s own
    `run_backtest` loop body) and a mismatch here would mean Phase 6 mis-derived the pin, not that
    Phase 5 was wrong.

    * Pinned verdict is `Verdict.PURE`: returns `None` — no entry (§3.2, ratio is definitionally 0).
    * Pinned verdict is `Verdict.MIXED`: re-invokes `mizan.screening.verdict.screen(dividend_event.
      ticker, ratio_as_of_date, con=con, cache_dir=cache_dir, overrides=overrides,
      fiqh_params=fiqh_params)` (§6a — the SAME `con`/`cache_dir`/`overrides`/`fiqh_params` the
      caller's own backtest run used, never a freshly-loaded or different config, guard G-P7 §7),
      reads `non_permissible_income_ratio.actual_value` off the returned `ScreeningVerdict.
      reason_trace`, and returns a `DividendPurificationEntry` with `purified_amount = ratio_used *
      dividend_event.cash_received`.
    * Pinned verdict is `Verdict.NON_COMPLIANT` (the dividend was received during the grace window,
      between `flip_date` and `divest_date`, before forced-divestment fired): Fork A's own wording
      ("from a **Mixed** holding", `MASTER_PRD.md` §8) does not literally cover this case, and a
      Non-compliant verdict caused by a Layer-1 (business-activity) failure carries NO ratio entries
      in its `reason_trace` at all (`mizan.screening.verdict.screen`'s own short-circuit return, §6a)
      — there may be nothing to read even if the wording were stretched to cover it. §6a's named,
      explicitly-flagged V1 default: walk `compliance_state.verdict_history` backwards from the flip
      to the most recent STRICTLY PRIOR `Verdict.MIXED` observation and re-derive ITS ratio via
      `screen()` at ITS OWN `as_of_date` (never the flip's own date, never zero by default, never the
      Non-compliant verdict's own absent ratio). If the most recent prior observation was `Verdict.
      PURE` instead, returns `None` (the Pure case above, unchanged)."""


def purify_backtest_result(
    result: BacktestResult,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None = None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> BacktestResult:
    """THE canonical, singular Phase 6 entry point — this phase's analogue of `screen()`/
    `run_backtest()`. Takes an already-completed `BacktestResult` (Phase 5's own scoped type,
    `purification_ledger is None`) and returns a NEW `BacktestResult` (§3's own frozen-model
    discipline — never mutates `result` in place) with `purification_ledger` populated.

    Calls `purify_dividend` (above) once per `result.dividend_events` entry, skipping `None`s;
    calls `mizan.purification.attribution.compute_divestment_attribution` (§4.2) once per
    `result.divestment_events` entry IFF `fiqh_params.purify_capital_gains.value` is `True` (§6c) —
    `divestment_entries` is `()` entirely when the gate is closed, never populated with skipped/
    zero-amount placeholders. Sums both entry sets into `purification_liability`, computes
    `gross_return`/`net_of_purification_return` from `result.daily_snapshots` (§3.2), constructs one
    `PurificationLedger`, and returns `result.model_copy(update={"purification_ledger": ledger.
    model_dump()})` (§3.1).

    Raises nothing this function's own body doesn't already document — every exception `screen()`
    can raise (`CikResolutionError`, `SicResolutionError`, `NotNormalizedError`,
    `InsufficientDataError`) can, in principle, propagate from a re-invoked `screen()` call, exactly
    the same halting posture `mizan/cli/backtest.py`'s own `run()` already gives `run_backtest()`
    (§4.3) — a ticker `screen()`-able once during the original backtest is `screen()`-able again here
    against the SAME, unchanged `con`/`cache_dir` (§6a's own determinism argument), so this is a
    defensive re-statement of an already-proven-reachable code path, not a new failure surface.
    """
```

### 4.2 `mizan/purification/attribution.py`

```python
def compute_divestment_attribution(
    event: DivestmentEvent,
    compliance_states: dict[str, ComplianceStateRecord],
    daily_snapshots: tuple[DailySnapshot, ...],
    *,
    con: duckdb.DuckDBPyConnection,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> DivestmentPurificationEntry:
    """Fork C for one `DivestmentEvent`. Asserts `compliance_states[event.ticker].flip_date ==
    event.flip_date and compliance_states[event.ticker].divest_date == event.divest_date`
    (`AssertionError` otherwise — guard G-P2, §7: both dates must come from the SAME
    `compliance_state.py`-owned event log, never re-derived independently). Finds the `DailySnapshot`
    in `daily_snapshots` with `as_of_date == event.flip_date` and reads `holdings[event.ticker]` as
    `quantity_liquidated` (§6b — the frozen-grace-holding property `mizan/backtest/clock.py`'s own
    docstring establishes means this quantity is unchanged all the way through to `event.divest_date`,
    so the flip-date snapshot is the correct, and only, read site). Queries `price_bars.raw_close`
    for `event.ticker` at `event.flip_date` and `event.divest_date` (one or two `con.execute(...)`
    calls, read-only, per §6a's raw-close precedent). Reads `fiqh_params.divestment_attribution_
    method.value` — currently only `DivestmentAttributionMethod.TIME_BOUNDED_PRICE_APPRECIATION`
    is defined (`mizan/config/fiqh_params.py` register #10; a second member would require a phase-spec
    revision, same posture that module's own docstring already states) — and computes
    `purified_amount = max(0.0, quantity_liquidated * (price_at_divest - price_at_flip))` (§6b).
    Returns one `DivestmentPurificationEntry`; its own `model_validator` (§3.3) re-asserts
    `flip_date <= divest_date` at construction, a second, type-level instance of the same guard.
    """
```

### 4.3 `mizan/cli/backtest.py` MODIFIED

```python
# mizan/cli/backtest.py — run(), additive modification only. Every existing line stays; inserted
# between `result = BacktestResult.model_validate(envelope.payload)` and the existing
# `print(f"Final portfolio value: ...")` block:

    from mizan.purification.ledger import purify_backtest_result

    result = purify_backtest_result(
        result, con=con, cache_dir=args.cache_dir, overrides=overrides, fiqh_params=FIQH_PARAMS
    )
    #  ^ the SAME `con`, `args.cache_dir`, `overrides` local variables `run_backtest(...)` above was
    #    already called with — never re-loaded, re-opened, or re-derived (§4.1's own determinism
    #    precondition, guard G-P7 §7). `con` is still open (the `with db.connect(...)` block has not
    #    yet exited) and still read-only.

    envelope = ResultEnvelope(active_caveats=envelope.active_caveats, payload=result.model_dump())

# ... existing DIVESTED / DIVIDENDS print loops, unmodified ...

    ledger = PurificationLedger.model_validate(result.purification_ledger)
    print(f"Purification liability: {ledger.purification_liability:.2f}")
    print(f"Gross return: {ledger.gross_return:.6f}")
    print(f"Net-of-purification return: {ledger.net_of_purification_return:.6f}")
    for entry in ledger.dividend_entries:
        print(
            f"PURIFIED DIVIDEND {entry.ticker} ex_date={entry.ex_date} "
            f"ratio={entry.ratio_used:.6f} amount={entry.purified_amount:.2f}"
        )
    for entry in ledger.divestment_entries:
        print(
            f"PURIFIED DIVESTMENT {entry.ticker} flip_date={entry.flip_date} "
            f"divest_date={entry.divest_date} amount={entry.purified_amount:.2f}"
        )
```

No new CLI flag is added (`--purify-capital-gains` or similar) — `mizan backtest` reads `FIQH_PARAMS`
module-level defaults exactly as `run_backtest()` already does, unmodified from `PHASE_5_SPEC.md`
§4.5's own posture that fiqh-param overrides are a Python-API/testing mechanism (`model_copy`), never
a CLI surface, anywhere in this codebase so far. Introducing one now, for this phase alone, would be
new surface area no other subcommand offers and no acceptance criterion needs (§9).

---

## §5 Migrations

**N/A, confirmed explicitly**, same posture `PHASE_5_SPEC.md` §5 already established for the same
underlying reason, re-derived rather than copied for this phase's own, different scope: Phase 6 adds
no DuckDB table, column, index, and issues no `CREATE`/`ALTER`/`DROP`/`INSERT` anywhere in its own
code. `mizan/purification/attribution.py` opens no new connection — it receives an already-open,
read-only `con` from its caller and only ever executes `SELECT raw_close FROM price_bars WHERE ...`.

**Why no `purification_ledger` DuckDB table, stated explicitly for the same reason Phase 5 stated why
no `backtest_results` table:** a `PurificationLedger` is deterministically re-derivable, in-process,
from an already-persisted `price_bars`/`fundamentals_facts` state plus a `BacktestResult` that is
itself not persisted (`PHASE_5_SPEC.md` §5's own confirmed decision, unchanged by this phase). Nothing
in Phase 6's own scope needs a SECOND process to later read a PRIOR ledger back out of storage — Phase
7 (reporting) is expected to invoke `run_backtest()` then `purify_backtest_result()` itself, in
process, the same way `MASTER_PRD.md` §9.1's pipeline diagram shows BACKTEST feeding PURIFICATION
feeding REPORT with no persistence stage drawn between any of them. If a future phase genuinely needs
cross-process persistence of a computed ledger, that is a new, reviewed schema decision for that
phase's own spec.

---

## §6 Implementation Logic Flow

### 6a. Fork A — the date-pinned ratio lookup, and why it prevents "purification undercount"

`ULTIMATE_PRD.md` §4.7 names the failure mode this whole phase exists to prevent, verbatim: **"missing
a dividend, or applying the wrong period's ratio... the ratio must be pinned to the screen *active at
the dividend date*, not the current screen."** Every design decision in this subsection traces back to
that one sentence.

**The mechanism, concretely.** Phase 5 already recorded everything Phase 6 needs to pin correctly,
without Phase 6 having to re-derive any of it independently:

* `DividendEvent.verdict_at_ex_date` — the enum (`PURE`/`MIXED`/`NON_COMPLIANT`) active when the
  dividend was credited, already correctly pinned by `mizan/backtest/clock.py`'s own `run_backtest`
  loop (`verdict_at_ex_date=record.verdict_history[-1].verdict`, read at the moment of credit — never
  the backtest's own final/most-recent state).
* `ComplianceStateRecord.verdict_history` — the FULL, append-only sequence of `VerdictObservation(
  as_of_date, verdict)` pairs for that ticker, for the ticker's ENTIRE holding lifetime, never
  truncated (`mizan/backtest/compliance_state.py`'s own docstring).

Neither of these carries the actual `non_permissible_income_ratio` VALUE, though — Phase 5 stores only
the three-state verdict enum at each observation, not the reason trace that produced it (confirmed by
direct read of `VerdictObservation`/`DividendEvent`, neither of which has a `float` ratio field). **The
ratio itself is not persisted anywhere Phase 6 can read it back out of; it must be re-derived.**
`purify_dividend` (§4.1) does this by: (1) finding the `VerdictObservation` in `verdict_history` with
the LARGEST `as_of_date <= dividend_event.ex_date` — the rebalance whose screen was "active" at the
dividend's date, precisely `ULTIMATE_PRD.md` §4.7's own phrase — call its `as_of_date` the
`ratio_as_of_date`; (2) re-invoking `mizan.screening.verdict.screen(ticker, ratio_as_of_date, con=con,
cache_dir=cache_dir, overrides=overrides, fiqh_params=fiqh_params)`, the SAME `con`/`cache_dir`/
`overrides`/`fiqh_params` the original backtest ran with (guard G-P7, §7); (3) reading `non_
permissible_income_ratio.actual_value` off the freshly-returned `ScreeningVerdict.reason_trace`.

**Why re-invoking `screen()` reproduces the exact historical ratio, not an approximation of it:**
`screen()` is a pure function of `(ticker, as_of_date, con, cache_dir, overrides, fiqh_params)` plus
DuckDB/cache state (`PHASE_4_SPEC.md` §4.3's own governing contract) — every fact resolution inside it
hard-filters `filed <= as_of_date`. Because Phase 6 runs against the SAME, unchanged `con`/`cache_dir`
within the SAME CLI invocation the original `run_backtest()` call used (no write happens to either
between the two calls — Phase 5's own `db.connect(..., read_only=True)`, §5 above), calling `screen(
ticker, ratio_as_of_date, ...)` a second time is BIT-FOR-BIT identical to the call `rebalance()`
already made at that exact rebalance during the original backtest — not a re-estimate, a re-execution
of the identical deterministic function on identical inputs. This is the reason Phase 6 can be a
post-processing pass at all (§6c) without weakening the ratio-pinning guarantee: re-derivation is only
as safe as this determinism argument, so guard G-P7 (§7) makes the "same config, same cache, same DB"
precondition an explicit, checked thing, not an assumption.

**The anti-undercount test this proves (§8):** a ticker whose `non_permissible_income_ratio` changes
between two dividend dates (two `us-gaap:InvestmentIncomeInterest`-style facts under the same tag,
filed on different dates — the SAME "two facts, two `filed` dates" mechanism `ZZLOOKAHEAD01` and
`ZZFLIP01` already exercise, reused rather than reinvented) must purify each dividend using its OWN
period's ratio. **New fixture ticker, additive only: `ZZMIXED_RATIODRIFT01`** (`tests/fixtures/
synthetic_universe.py`, CIK `9990000014`) — Layer-1-clean, market-cap denominator per the existing
`DENOMINATOR = 100,000,000.0` convention, an early `InvestmentIncomeInterest` fact of `1,000,000.0`
filed `2025-06-01` (2% of the fixture's `50,000,000.0` total-revenue denominator, `compute_non_
permissible_income_ratio`'s own divisor, `mizan/screening/financial_ratios.py`) and a second fact of
`2,000,000.0` filed `2026-02-01` (4%) — both comfortably under the 5% threshold, so the ticker stays
`MIXED` throughout and is never divested, isolating the ratio-drift question from the flip/grace/divest
mechanic entirely. Price bars carry a nonzero `div_cash` on one trading day between rebalance 1
(`2026-01-01`) and rebalance 2 (`2026-04-01`) — pinned ratio 2% — and a second nonzero `div_cash` day
between rebalance 2 and rebalance 3 — pinned ratio 4%. §8 AC states the exact assertion.

**The grace-window edge case, named rather than silently defaulted.** A holding in `HELD_NONCOMPLIANT_
GRACE` is still held, unsold, through its grace window (`mizan/backtest/clock.py`'s own frozen-holding
docstring) and could receive a dividend during that window, before forced-divestment fires — its
`verdict_at_ex_date` would then be `NON_COMPLIANT`, not `MIXED`. `MASTER_PRD.md` §8's trigger wording
— "from a **Mixed** holding" — does not literally reach this case, and a `Verdict.NON_COMPLIANT`
caused by a Layer-1 (business-activity) failure carries `reason_trace = (business_activity_result.
reason,)` ONLY (`mizan/screening/verdict.py`'s own `screen()` body, confirmed by direct read) — no
ratio entries exist to read even if the wording were stretched. This is a genuine primary-source gap,
same category as every other entry in `mizan/config/fiqh_params.py`'s own register, and is resolved
here the same way: **named explicitly, given a concrete V1 default, never silently zeroed.** §4.1's
`purify_dividend` default: walk `verdict_history` backwards from the flip to the most recent STRICTLY
PRIOR `Verdict.MIXED` observation and purify at ITS ratio (re-derived via `screen()` at ITS OWN
`as_of_date`) — the last period the holding was genuinely assessed Mixed, never the flip verdict's own
(usually absent) ratio and never a bare `0.0`. If that prior observation was `Verdict.PURE` instead,
the dividend produces no entry, same as any other Pure-pinned dividend.

### 6b. Fork C — the divestment-attribution computation, worked through concretely

Using `ZZFLIP01`'s own already-shipped, already-relied-upon shape (`PHASE_5_SPEC.md` §6c's worked
example: flip at rebalance 2 = `2026-04-01`, divest at rebalance 3 = `2026-07-01`) as the STRUCTURAL
template, but **not the ticker itself** — `ZZFLIP01`'s existing four price bars are flat at
`raw_close=100.0` throughout, which every Phase 5 acceptance criterion already depends on for its own
portfolio-valuation arithmetic; changing any of those four values now would be an in-place mutation of
already-approved fixture data, exactly the "additive extension only" rule's forbidden move, for a
gain (a nonzero Fork-C appreciation to test against) this phase can get for free by adding a NEW
ticker instead. **New fixture ticker, additive only: `ZZDIVEST_APPREC01`** (CIK `9990000015`),
structurally identical to `ZZFLIP01` (same debt-fact-drift mechanism producing the same flip at
rebalance 2 / divest at rebalance 3 sequence) but with `raw_close = 100.0` at rebalance 1 and 2 (i.e.
at `flip_date`) and `raw_close = 130.0` at rebalance 3 (`divest_date`) — a genuine, nonzero
appreciation over the non-compliant window for `compute_divestment_attribution` to compute.

```
DivestmentEvent(ticker="ZZDIVEST_APPREC01", flip_date=2026-04-01, divest_date=2026-07-01)
  -> assert compliance_states["ZZDIVEST_APPREC01"].flip_date == 2026-04-01  (sourced, not re-derived)
  -> assert compliance_states["ZZDIVEST_APPREC01"].divest_date == 2026-07-01
  -> quantity_liquidated = daily_snapshots[as_of_date == 2026-04-01].holdings["ZZDIVEST_APPREC01"]
  -> price_at_flip   = price_bars.raw_close("ZZDIVEST_APPREC01", 2026-04-01) = 100.0
  -> price_at_divest = price_bars.raw_close("ZZDIVEST_APPREC01", 2026-07-01) = 130.0
  -> purified_amount = max(0.0, quantity_liquidated * (130.0 - 100.0))
```

**Why the flip-date snapshot, not a "quantity at divestment" field that does not exist:** `rebalance()`
(`mizan/backtest/clock.py`) force-liquidates a divesting ticker BEFORE that same rebalance's
`DailySnapshot` is appended, so the divest-date snapshot never shows the ticker at all — and
`DivestmentEvent` itself carries no quantity or proceeds field (confirmed by direct read of `mizan/
backtest/compliance_state.py`; it is a deliberately minimal record, `ticker`/`cik`/`flip_date`/
`divest_date` only). The flip-date snapshot is the correct, and only, read site precisely because a
grace holding is frozen — unchanged quantity, no cash flow — for its entire window (`mizan/backtest/
clock.py`'s own docstring, quoted at length in that module and restated here because Fork C's own
correctness depends on it): the quantity at `flip_date` IS the quantity liquidated at `divest_date`,
by construction, not by assumption.

**Why the appreciation is floored at zero, not left negative.** A price DECLINE during the
non-compliant window produces a negative `(price_at_divest - price_at_flip)`. AAOIFI's purification
concept removes impermissible INCOME from an investor's return — donated to charity precisely because
it should never have reached the investor's P&L. There is no income, non-halal or otherwise, in a
loss; a negative "purified amount" would imply crediting the investor back for a decline, which is not
what purification is. `purified_amount = max(0.0, ...)` is the honest floor, named as a judgment call
here rather than silently baked into the arithmetic.

### 6c. Fork A's gate on Fork C, resolved from the primary source's own text

The outer dispatch names this ambiguity explicitly and asks for it to be resolved by citation, not
guessed: **does `fiqh_params.purify_capital_gains.value == False` (the V1 default) also suppress
Fork C's forced-divestment attribution, or does Fork C run unconditionally regardless of that flag?**

`MASTER_PRD.md` §8's own text, read together, settles this:

> "**Fork A — what gets purified:** **dividends only** for V1. Capital-gains purification is a
> configurable, **default-OFF**, `pending scholarly ruling` flag."
>
> "**Fork C — forced-divestment attribution:** for a holding that flipped and was divested, the
> amount to purify from the non-compliant window is **underdetermined by settled formula**. V1
> default: **price appreciation during the non-compliant window**..."

Fork C's own subject is "price appreciation" — a capital gain by definition, not a dividend. Register
#9's own source string in `mizan/config/fiqh_params.py` makes the link explicit rather than requiring
an inference across the two Fork sections: `purify_capital_gains` is documented there as "**Fork A**:
dividends-only for V1; capital-gains purification default OFF" — i.e. register #9 is not merely "Fork
A's own toggle," it is the SAME toggle Fork A's "dividends only" scope note describes, and Fork C's
subject matter (price appreciation) is a capital gain in every ordinary sense of the term. **Decision,
stated explicitly: Fork C's forced-divestment price-appreciation attribution is a capital-gains-
purification mechanic, gated by `fiqh_params.purify_capital_gains.value`.** When `False` (the V1
default), `purify_backtest_result` computes ZERO `DivestmentPurificationEntry` records — `divestment_
entries` is `()`, not a set of zero-amount entries — for every `DivestmentEvent` in the result,
regardless of how much the price actually moved; dividends remain the only purified income category,
matching Fork A's literal "dividends only for V1" scope exactly. When `True` (an explicit,
scholarly-ruling-pending opt-in, register #9's own `configurable: True`), `compute_divestment_
attribution` (§4.2, §6b) runs for every `DivestmentEvent`, per `divestment_attribution_method`
(register #10). Register #10 is a SEPARATE toggle answering a different question ("which formula,
given that Fork C runs at all") — only `DivestmentAttributionMethod.TIME_BOUNDED_PRICE_APPRECIATION`
is defined, so V1 has exactly one formula once the gate is open, and register #10 does not itself
gate Fork C's firing. §8's own acceptance criterion (`FIQH_PARAMS.purify_capital_gains` via
`model_copy` changes whether Fork-C entries exist at all) is this decision's direct, testable
consequence.

### 6d. Fork B — side-ledger accrual, and the structural guarantee against NAV contamination

`MASTER_PRD.md` §8 Fork B: "Accrue a running `purification_liability` separately; report **two
numbers** — gross return and net-of-purification return — so the drag is its own visible figure, not
a silent NAV distortion." `ULTIMATE_PRD.md` §4.7's third named failure mode is exactly the violation of
this: "purification silently netted into NAV."

**The structural guarantee, stated as a fact about this phase's own code rather than a promise about
it:** `mizan/purification/ledger.py` and `attribution.py` together contain exactly ONE arithmetic
site that subtracts `purification_liability` from anything — `PurificationLedger.net_of_purification_
return`'s own computation, inside `purify_backtest_result` (§4.1). Nowhere under `mizan/purification/`
constructs a `Portfolio`, a `DailySnapshot`, or writes to any field of the `BacktestResult` it is
given other than `purification_ledger` itself (`result.model_copy(update={"purification_ledger":
...})` — every other field of the returned `BacktestResult`, including `daily_snapshots`, is copied
through UNCHANGED). `gross_return` is computed from `daily_snapshots` exactly as it would be with no
purification concept in the codebase at all; `net_of_purification_return` is a second, independently
computed number that happens to read `gross_return`'s own two `portfolio_value`s a second time and
additionally subtract the ledger's own total. The two numbers can never silently collapse into "the
same number under a different name" unless `purification_liability` is genuinely `0.0` — an EMPTY
ledger, not a netting bug (§8's own acceptance criterion states this precisely).

**Why a single final aggregate, not a running day-by-day series, satisfies "accrue a running
liability":** every ledger entry (`DividendPurificationEntry`/`DivestmentPurificationEntry`) already
carries its own date (`ex_date`, or `flip_date`/`divest_date`). A cumulative-over-time liability curve
is `sorted(entries, key=date)` plus a running `sum` away — a presentation transformation, not a new
computation — and is squarely Phase 7's reporting concern (`MASTER_PRD.md` §9.1's pipeline: PURIFICATION
feeds REPORT), the same "a snapshot series becomes an actual return series only in the reporter"
posture `PHASE_5_SPEC.md` §3.4 already gave `DailySnapshot` itself. Phase 6 does not pre-build a
second parallel time series alongside `daily_snapshots` to answer a question only Phase 7 needs
answered.

---

## §7 Failure-Mode Guards

Pulled from `ULTIMATE_PRD.md` §4.7 (Purification) specifically, plus this phase's own new surface.

| # | Failure mode | Guard Phase 6's code implements | What the review agent checks |
|---|---|---|---|
| G-P1 | Purification undercount — a missed dividend, or the wrong period's ratio applied (`ULTIMATE_PRD.md` §4.7's named failure mode) | `purify_dividend` (§4.1, §6a) pins the ratio lookup to the `VerdictObservation` active AT the dividend's own `ex_date`, re-derived via a fresh `screen()` call at that exact `as_of_date` — never "most recent"/"current" | The ratio-drift test (§8 AC, `ZZMIXED_RATIODRIFT01`): two dividends on the same ticker, different pinned ratios, each `DividendPurificationEntry.purified_amount` computed from its OWN `ratio_as_of_date`, not the other's |
| G-P2 | Fork-C attribution window computed against the wrong flip/divest dates | `compute_divestment_attribution` (§4.2) asserts `compliance_states[ticker].flip_date == event.flip_date and .divest_date == event.divest_date` before computing anything; `DivestmentPurificationEntry`'s own `model_validator` (§3.3) re-asserts `flip_date <= divest_date` at construction | A deliberately-mismatched `compliance_states` dict (a different `flip_date` than the `DivestmentEvent` carries) raises `AssertionError`; `DivestmentPurificationEntry(flip_date=..., divest_date=<earlier>, ...)` raises `pydantic.ValidationError` |
| G-P3 | Purification silently netted into NAV | `daily_snapshots`, `Portfolio`, and every `BacktestResult` field other than `purification_ledger` are read-only inputs to `mizan/purification/`, never written; `net_of_purification_return` is computed at exactly one site, inside `PurificationLedger` construction (§6d) | `grep -rn "daily_snapshots\s*=" mizan/purification/` — no hit (nothing reassigns it); a test asserting `gross_return != net_of_purification_return` whenever `purification_liability > 0.0`, and `==` only when the ledger is empty (§8 AC) |
| G-P4 | Fork A/Fork C gate silently hardcoded rather than read from config | `purify_backtest_result` reads `fiqh_params.purify_capital_gains.value` fresh on every call, never a module-level cached bool (mirrors `PHASE_5_SPEC.md` G-B4's own pattern for `grace_period_rebalances`) | The §8 `model_copy` test: toggling `purify_capital_gains` from `False` to `True` changes `divestment_entries` from `()` to a nonempty tuple over the same `ZZDIVEST_APPREC01` backtest, proving the value is read, not hardcoded |
| G-P5 | `mizan/purification/` gains accidental write capability to DuckDB | Neither `ledger.py` nor `attribution.py` issues `INSERT`/`CREATE`/`ALTER`/`DROP` anywhere; both accept an already-open, caller-supplied `con` rather than opening their own connection | `grep -rniE "INSERT INTO\|CREATE TABLE\|ALTER TABLE\|DROP TABLE" mizan/purification/` — no hit; `grep -rn "duckdb.connect" mizan/purification/` — no hit |
| G-P6 | Grace-window dividend (Non-compliant-pinned) silently defaults to a `0.0` ratio instead of §6a's documented last-Mixed-ratio fallback | `purify_dividend` (§4.1) explicitly branches on the pinned verdict being `NON_COMPLIANT` and walks `verdict_history` backwards to the last `MIXED` observation, never falling through to an implicit `0.0` | A fixture backtest where a dividend is paid during a ticker's grace window (`verdict_at_ex_date == NON_COMPLIANT`) produces a `DividendPurificationEntry` whose `ratio_used`/`ratio_as_of_date` match the ticker's LAST Mixed-verdict rebalance, not the flip rebalance and not `0.0` |
| G-P7 | `purify_backtest_result` re-derives a ratio against a DIFFERENT `con`/`cache_dir`/`overrides`/`fiqh_params` than the original `run_backtest()` call used, silently corrupting the re-derivation's determinism (§6a) | `mizan/cli/backtest.py` (§4.3) threads the exact same local `con`/`args.cache_dir`/`overrides` variables into both the `run_backtest(...)` and `purify_backtest_result(...)` calls, never re-opening a connection or re-loading the override map between them | Code inspection of `mizan/cli/backtest.py`'s `run()`: exactly one `db.connect(...)` call and one `load_override_map(...)` call in the whole function body, both variables reused, not reassigned, between the two `run_backtest`/`purify_backtest_result` call sites |
| G-DB6 | `mizan purification` (or any Phase 6 code path) writes to DuckDB | `mizan/purification/` takes `con` read-only from its caller; `mizan/cli/backtest.py`'s own `db.connect(..., read_only=True)` (unchanged from Phase 5) still governs the single connection both `run_backtest` and `purify_backtest_result` share | `grep -rniE "INSERT INTO\|CREATE TABLE\|ALTER TABLE" mizan/purification/ mizan/cli/backtest.py` — no hit |
| G-LLM6 | LLM/model SDK reachback | Forbidden-dependency list unchanged (§2.3) | `grep -rniE "openai\|anthropic\|gemini\|vertex\|langchain\|\bllm\b\|chat_completion\|completion\(" mizan/purification/` — no hit. **Corrected path, replacing `ULTIMATE_PRD.md` §5 check 5's stale `mizan/backtest/purification.py` reference (§1)**: the equivalent check for a Phase 6 reviewer is `grep -rniE "openai\|anthropic\|..." mizan/screening/ mizan/backtest/compliance_state.py mizan/purification/` |
| G-BOUND2 | Any of `short/borrow/margin/leverage/option/future/swap/derivative` naming anywhere under `mizan/purification/` | None of these words appears anywhere in this phase's code, comments, or identifiers | `grep -rniE "\b(short\|shorts\|shorting\|borrow\|borrowed\|borrowing\|margin\|leverage\|leveraged\|levered\|option\|options\|future\|futures\|swap\|swaps\|derivative\|derivatives)\b" mizan/purification/` — no hit |
| G-AI | AI attribution in commit messages | Same neutral-commit convention as Phases 1–5 | `git log --format=%B` for this phase's commits — no `Co-Authored-By`, no "Generated with," no model/assistant name |

**Categorisation, mirroring Phases 1–5:** G-P1, G-P2, G-P3, G-P4, G-LLM6, G-BOUND2, G-AI are
**HALT-for-human** (permissibility-boundary or values-boundary touching, and G-P1/G-P2/G-P3 are the
three `ULTIMATE_PRD.md` §4.7 rows verbatim, all three categorized HALT-for-human there already).
G-P5, G-P6, G-P7, G-DB6 are blocking-but-mechanical.

---

## §8 Phase Acceptance Criteria

Each concrete, independently checkable by a third party, same standard Phases 1–5 applied, reusing
Phase 4/5's synthetic fixture set (thirteen tickers) plus this phase's three additive tickers
(`ZZMIXED_RATIODRIFT01`, `ZZPURE_DIV01`, `ZZDIVEST_APPREC01`, §6a/§6b).

1. **The core anti-undercount property.** A backtest over `ZZMIXED_RATIODRIFT01` (§6a) — whose
   `non_permissible_income_ratio` is 2% as of rebalance 1 and 4% as of rebalance 2 — produces two
   `DividendPurificationEntry` records, one per dividend, whose `purified_amount`s use their OWN
   period's ratio: the dividend paid before rebalance 2 is purified at 2% of its cash, the dividend
   paid after rebalance 2 is purified at 4% of its cash — **never** the same ratio applied to both.
2. **A Pure-verdict ticker's dividends produce zero purification-ledger entries.** A new fixture
   ticker, `ZZPURE_DIV01` (Layer-1-clean, all-zero ratios, one nonzero `div_cash` price bar) —
   distinct from the existing, unmodified `ZZPURE01` (§1's "never touch an existing ticker's fields"
   discipline) — produces exactly zero entries in `PurificationLedger.dividend_entries` after a
   backtest that credits it a dividend, not one entry with `purified_amount == 0.0`.
3. **The Fork-C divestment produces a correctly-bounded attribution entry, gated by config.** A
   backtest over `ZZDIVEST_APPREC01` (§6b: flips at rebalance 2, divests at rebalance 3, price
   `100.0 -> 130.0` over that exact window) with `FIQH_PARAMS.purify_capital_gains` `model_copy`'d to
   `value=True` produces one `DivestmentPurificationEntry` with `flip_date`/`divest_date` matching the
   `DivestmentEvent` exactly, and `purified_amount == quantity_liquidated * 30.0`. The SAME backtest
   run under the DEFAULT `purify_capital_gains.value == False` produces `divestment_entries == ()` —
   proving the gate is read from config (§6c, §7 guard G-P4), not hardcoded either way.
4. **Grace-window dividends fall back correctly, never to zero.** A fixture scenario where a dividend
   is paid to a holding while it is in `HELD_NONCOMPLIANT_GRACE` (between `flip_date` and
   `divest_date`) produces a `DividendPurificationEntry` whose `ratio_used`/`ratio_as_of_date` match
   the ticker's most recent PRIOR `Mixed`-verdict rebalance, never the flip rebalance's own (absent)
   ratio and never a bare `0.0` (§6a, §7 guard G-P6).
5. **`gross_return` and `net_of_purification_return` are both present, distinct, and correctly
   related.** For any backtest whose `purification_liability > 0.0`, `net_of_purification_return ==
   gross_return - purification_liability / daily_snapshots[0].portfolio_value` exactly (floating-point
   tolerance aside), and the two values are never bit-identical. For a backtest with an empty ledger
   (`purification_liability == 0.0`), the two values ARE identical — the one and only case they may
   silently coincide (§6d, §7 guard G-P3).
6. **`BacktestResult.purification_ledger` round-trips losslessly.** `PurificationLedger.model_validate(
   purify_backtest_result(result, ...).purification_ledger)` reconstructs a `PurificationLedger`
   equal, field-for-field, to the one `purify_backtest_result` constructed internally — proving the
   `.model_dump()`/`.model_validate()` round trip (§3.1) is lossless, the same guarantee `ScreeningVerdict.
   model_validate(envelope.payload)` already gives Phase 4's own result type.
7. **Every OTHER field of the returned `BacktestResult` is unchanged.** `purify_backtest_result(
   result, ...).daily_snapshots == result.daily_snapshots` (and likewise for `divestment_events`,
   `dividend_events`, `compliance_states`) — bit-for-bit — proving Phase 6 only ever adds a
   `purification_ledger`, never alters anything Phase 5 already computed (§6d, §7 guard G-P3).
8. **A reconciliation pass accounts for every dividend.** `sum(e.dividend_cash_received for e in
   ledger.dividend_entries)` plus the total cash received by every dividend whose pinned verdict was
   `Verdict.PURE` (necessarily excluded, zero entries) equals `sum(d.cash_received for d in result.
   dividend_events)` exactly, for a fixture backtest mixing Pure- and Mixed-verdict dividend-paying
   tickers — no dividend is silently dropped from the reconciliation (`MASTER_PRD.md` §6's own named
   "reconciliation test" for this phase).
9. **`flip_date <= divest_date` holds for every `DivestmentPurificationEntry`**, both by construction
   (the `model_validator`, §3.3) and by the guard assertion inside `compute_divestment_attribution`
   (§4.2) against `compliance_states`, never independently re-derived (§7 guard G-P2).
10. **`purify_backtest_result` reuses the caller's own `con`/`cache_dir`/`overrides`/`fiqh_params`,
    never re-loading them.** Code inspection of `mizan/cli/backtest.py`'s `run()` confirms exactly one
    `db.connect`/`load_override_map` call site each, both variables threaded unmodified into both the
    `run_backtest` and `purify_backtest_result` calls (§7 guard G-P7).
11. **`mizan/purification/` never writes to DuckDB.** No `INSERT`/`CREATE`/`ALTER`/`DROP` anywhere
    under `mizan/purification/`; every DB touch is a `SELECT` against an already-open, read-only
    connection (§5, §7 guard G-DB6).
12. **Every new Pydantic model inherits `MizanBaseModel`.** No file under `mizan/purification/`
    imports or subclasses `pydantic.BaseModel` directly.
13. **`BacktestResult.purification_ledger`'s declared TYPE is unchanged.** `mizan/backtest/clock.py`'s
    `BacktestResult.purification_ledger: dict[str, object] | None = None` field declaration is
    byte-for-byte unmodified by this phase's diff (§3.1) — confirmed by direct diff inspection, not
    merely by the type-checker passing.
14. **No LLM/model-client SDK import, and no boundary-crossing primitive naming, anywhere in
    `mizan/purification/`.** `ULTIMATE_PRD.md` §5 checks 1–8, re-run over the expanded tree with the
    corrected path (§7 guards G-LLM6, G-BOUND2).
15. **mypy --strict mizan tests exits 0.** Built and verified inside the project's `.venv`, per
    `PHASE_3_SPEC.md` AC14's established requirement.
16. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5`.
17. **`pytest` passes in full**, both new test files plus the extended `tests/fixtures/
    synthetic_universe.py` plus the full existing Phase 1–5 suite (no regression) — including a
    specific check that `PriceBarFixture`'s new `div_cash` field defaulting to `0.0` leaves every
    Phase 4/5 fixture ticker's already-cached `INSERT`-row values byte-for-byte unchanged.
18. **No forbidden dependency anywhere; `pyproject.toml` is unmodified by this phase** (§2.1/§2.2).
19. **No premature imports.** `pandas`/`matplotlib` imported by no module under `mizan/`; `pyarrow`
    imported by no module under `mizan/purification/`.
20. **Commits are neutral.** No AI attribution in `git log` for this phase's commits.
21. **Boundary greps are clean**, re-run from repo root against the full tree including
    `mizan/purification/*.py` (`ULTIMATE_PRD.md` §5 checks 1–8, at the corrected path per §1/§7).

**Any single failing criterion is a phase-loop HALT, not a partial pass** — same standard Phases 1–5
state, applied here.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 6)

- **No reporting, no HTML output, no `matplotlib` import, no chart.** → Phase 7. Phase 6 only
  computes and exposes `gross_return`/`net_of_purification_return`/`purification_liability`/the two
  entry-type ledgers as typed values (plus the plain stdout lines §4.3 adds to `mizan backtest`'s own
  existing summary) — it does not render them as a report. Phase 7's reporter "refuses to render a
  number without stamping its caveat set" (`ULTIMATE_PRD.md` §9.2) is a Phase-7-owned structural
  guarantee this phase does not need to, and does not, implement.
- **No actual charitable-donation mechanism, and this document says so plainly rather than leaving it
  implicit.** "Purification" in this codebase, this phase included, means "computed and tracked as a
  liability in `PurificationLedger.purification_liability`" — a number a human operator could, in
  principle, act on outside this software. It does NOT mean any cash, wire transfer, ledger entry in
  an external system, or API call to an actual charity is made. Mizan is a personal research sandbox
  (`MASTER_PRD.md` §1); building a real donation-execution feature is out of scope for V1 and is not
  implied, hinted at, or half-built by anything in `mizan/purification/`.
- **No real purification run against the real ~100-ticker universe.** Unchanged from every prior
  phase's own honesty posture (`PHASE_4_SPEC.md` §9, `PHASE_5_SPEC.md` §9): the real curated universe
  still does not exist (`COMPREHENSION.md` §6's carried-forward open item). Phase 6's acceptance
  criteria (§8) run only against Phase 4/5's synthetic fixture set plus this phase's three additive
  tickers — never against a named real company.
- **No new `FiqhParam` register entry, no register-value change.** Phase 6 reads register entries
  #9/#10/#11 (already defined, Phase 1) and, structurally, register #8 only indirectly (through
  `ComplianceStateRecord`/`DivestmentEvent`, already resolved by Phase 5) — it introduces zero new
  rows and changes zero existing default values.
- **No second, alternative `DivestmentAttributionMethod` or `PurificationAccountingMethod` member.**
  `mizan/config/fiqh_params.py`'s own docstrings for both enums already state that defining a second
  member "would manufacture a false menu of options" absent a settled formula or a phase-spec
  revision — Phase 6 does not add one, and `compute_divestment_attribution` (§4.2) has exactly one
  branch, not a dispatch table anticipating a member that does not exist.
- **No CLI flag to override `purify_capital_gains`, `divestment_attribution_method`, or
  `purification_accounting_method` at run time.** §4.3's own stated reasoning: no other Phase 1–5
  subcommand exposes a fiqh-register override at the CLI layer either; `model_copy` remains the one,
  Python-API-level override mechanism, consistent across every phase so far.
- **No change to `mizan/backtest/`, `mizan/screening/`, `mizan/data/`, or any earlier phase's public
  symbol other than `mizan/cli/backtest.py`'s additive modification (§1).** Phase 6 imports and calls
  `run_backtest`, `screen`, `db.connect`, and the Phase 1 config/core singletons — it reshapes none of
  them.
- **No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3).** Unchanged from Phases 1–5 —
  these remain escalated to the human and are unrelated to purification.
- **No day-by-day running purification-liability time series.** §6d's own reasoning: every ledger
  entry already carries a date, making a cumulative curve a trivial presentation-layer derivation —
  Phase 6 exposes the entries and the final aggregate, not a second parallel series alongside
  `daily_snapshots`.

---

## VERSION CONTROL

Commit: `docs: Phase 6 technical blueprint (mizan)`. No push (no remote configured; local commit
only, per this dispatch's own instruction).
