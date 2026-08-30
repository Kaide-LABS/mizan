# PHASE_5_SPEC.md — Mizan: Backtest Engine & Compliance-Flip State Machine

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), the same document `PHASE_1_SPEC.md`–`PHASE_4_SPEC.md` were built from. Every
> schema decision, every function signature, and every guard below traces to a section of that
> document, cited inline, cross-checked against `MASTER_PRD.md` where `ULTIMATE_PRD.md` is silent,
> and against the committed Phase 1 code (`mizan/config/invariants.py`, `mizan/config/fiqh_params.py`,
> `mizan/core/verdict.py`, `mizan/core/caveats.py`), Phase 3 code (`mizan/data/db.py`,
> `mizan/data/normalize.py`), and Phase 4 code (`mizan/screening/verdict.py`,
> `mizan/screening/business_activity.py`, `tests/fixtures/synthetic_universe.py`) for integration
> fidelity. Every code excerpt below was read from the actual committed files this pass, not
> recalled from `PHASE_4_SPEC.md`'s own illustrative blocks — see §0's data-availability finding and
> §3.4's raw-vs-adjusted-close decision, both of which required reading Phase 3's real DDL and Phase
> 4's real `screen()` signature directly, not assuming either.

**Generated:** 2026-08-31 · **Dispatch type:** phase advancement (Phase 4 review-approved 2026-08-30,
comprehension pass complete; no code review or fix loop runs in this dispatch — this document is the
deliverable) · **Canonical references:** `ULTIMATE_PRD.md` (governs, esp. §2.1's two load-bearing
seams, §4.6 Backtest failure modes, §5 the grep-able Hard Boundary, §6 the execution spec naming
Phase 5), `MASTER_PRD.md` (governs where `ULTIMATE_PRD.md` is silent, principally §2 the INVARIANTS
table, §7 the Backtest Engine section and its state-machine diagram, §8 Fork C's divestment-
attribution default, §10 register entry #8), `docs/modernization_log.md` (pinned external reality —
§5.4 DuckDB API, §6.2 Tiingo field contract), `COMPREHENSION.md` (what Phases 1–4 actually shipped,
including the open item that nothing yet consumes `screen()`'s output over time — §6 below is where
that closes), `PHASE_1_SPEC.md` (`INVARIANTS`, `FIQH_PARAMS`, `MizanBaseModel`, `Verdict`,
`Caveat`/`ResultEnvelope` — all Phase 5 **consumes**, none of which it may redefine), `PHASE_4_SPEC.md`
(format/rigor precedent, and the public surface — `mizan.screening.verdict.screen`,
`ScreeningVerdict`, `ReasonTraceEntry`/`ScreenName`, `mizan.screening.business_activity.
BusinessActivityOverrideMap`/`load_override_map`, `mizan.cli.main.build_parser` — Phase 5 must
consume without reshaping), and `tests/fixtures/synthetic_universe.py` (the ~12 synthetic tickers
Phase 4 already built, extended additively by this phase — §6e).

**No citation re-verification gate applies to this document**, unchanged from `PHASE_2/3/4_SPEC.md`'s
own confirmation. Phase 5 introduces no new arXiv citation of its own; it reuses arXiv:2608.12634's
already-logged finding (`docs/modernization_log.md` §8, "boundary proximity predicts screen-implied
transitions") as the standing justification for re-screening every current holding at every
rebalance (§6c, §7 guard G-B3) — a restatement, not a new literature claim. This file carries no §0.5.

---

## §0 Phase Plan Header

# **Phase 5 of 7: Backtest Engine + Compliance-Flip State Machine**

Phase sequence, unchanged from `PHASE_4_SPEC.md` §0 / `ULTIMATE_PRD.md` §6 (re-derived there, not
re-derived again here):

| # | Phase | Ships |
|---|---|---|
| 1 | Foundation & Config (done, approved) | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| 2 | Ingestion & raw cache (done, approved) | EDGAR (`companyfacts` + `companyconcept` + `submissions`) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store (done, approved) | `data/normalize.py`, `data/db.py`, typed `fundamentals_facts`/`price_bars` tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine (done, approved) | `screening/business_activity.py` (SIC first-pass + pluggable override map, tiered), `screening/financial_ratios.py` (30/30/5, two-axis denominator from config), `screening/verdict.py` (combines both into a three-state `Verdict` + reason trace — the `screen()` entry point), temporal-non-interference discipline, `mizan/cli/screen.py` |
| **5** | **Backtest engine + compliance-flip state machine** ← *this document* | `backtest/clock.py` (quarterly-rebalance event loop over a daily price series), `backtest/portfolio.py` (holdings + cash, reads `INVARIANTS.cash_yield`), `backtest/strategy.py` (pluggable long-only strategy interface, structurally confined to compliant tickers), `backtest/compliance_state.py` (flip→grace→divest state machine, calling Phase 4's `screen()` every rebalance), `mizan/cli/backtest.py` |
| 6 | Purification | side-ledger, `divCash`-driven, Forks A/B/C from config |
| 7 | Reporting | static HTML + matplotlib, caveats non-optional, gross vs net-of-purification |

This spec covers **Phase 5 only**. It is the contract the Phase 5 execution agent builds against and
the Phase 5 review agent (next round of Step 12) verifies against. Phase 5 **consumes** Phase 1's
public surface (`mizan.config.invariants.INVARIANTS`, `mizan.config.fiqh_params.FIQH_PARAMS`,
`mizan.core.base.MizanBaseModel`, `mizan.core.verdict.Verdict`, `mizan.core.caveats.Caveat`/
`ResultEnvelope`, `mizan.config.boot_check.check_all`), Phase 3's public surface (`mizan.data.db.connect`),
and Phase 4's public surface (`mizan.screening.verdict.screen`, `ScreeningVerdict`,
`ReasonTraceEntry`/`ScreenName`, `mizan.screening.business_activity.BusinessActivityOverrideMap`/
`load_override_map`, `mizan.cli.main.build_parser`) and **must not reshape any of them**. Phase 5 may
only extend that surface additively — including one additive extension to Phase 4's own
`tests/fixtures/synthetic_universe.py` (§6e: one new synthetic ticker appended to
`ALL_SYNTHETIC_TICKERS`, nothing existing changed). Every new symbol Phase 5 introduces
(`mizan.backtest.*`, `mizan.cli.backtest`) is itself now locked for Phases 6–7 the same way.

### 0.1 Confirmed: Phase 3's schema is sufficient for a daily total-return backtest — no data gap

Read directly this pass (`mizan/data/db.py` §5.1–§5.2, `mizan/data/normalize.py` §3): `price_bars` is
keyed `(ticker, trade_date)` and carries `raw_open/high/low/close`, `adj_open/high/low/close`,
`volume`, `div_cash`, `split_factor` — every field Tiingo's EOD endpoint returns
(`docs/modernization_log.md` §6.2), normalized and typed, with `raw_*`/`adj_*` kept as
independently-populated columns (Phase 2/3's guard G-T3). **This is sufficient for a daily clock and
a portfolio marked to market every trading day, with corporate actions (splits, dividends) handled
explicitly — no new Phase 3 column, table, or migration is needed.** The one genuine gap named here
rather than silently assumed: **Tiingo's exact `splitFactor` convention (whether it is the multiplier
applied to a *held share count* across a split, or its reciprocal) has never been live-verified by
any prior phase** — `docs/modernization_log.md` §6.2 records the field's existence and role
(dividend/split adjustment) but not its arithmetic direction. §3.4 and §6b below name this explicitly
as a build-time verification item, per this project's "verify, don't recall" discipline
(`docs/modernization_log.md` §0/§1), the same category `PHASE_4_SPEC.md` §2.2 gave the XBRL tag
allow-lists. This is the only data-availability gap this phase found; everything else Phase 5 needs
(daily prices for marking to market, `Assets`/shares/ratio facts for re-screening via `screen()`,
per-day dividend cash for crediting the portfolio) is already queryable exactly as Phase 3 built it.

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`.** Same flat layout `PHASE_1_SPEC.md`–`PHASE_4_SPEC.md` §1
preserved — no nesting directory. Every file below is new except `mizan/cli/main.py` (one line,
Phase 2–4's own established registration convention) and `tests/fixtures/synthetic_universe.py`
(one additive ticker, §6e).

```
C:\Users\hp\HMS\
├── mizan/
│   ├── backtest/
│   │   ├── __init__.py                  # NEW — empty, package marker only (mizan/screening/__init__.py precedent)
│   │   ├── portfolio.py                 # NEW — Holding/Portfolio models, valuation, split/dividend
│   │   │                                 #        bookkeeping, INVARIANTS.cash_yield read site (§3, §4, §6a)
│   │   ├── strategy.py                  # NEW — Strategy protocol + AllocationInstruction, structurally
│   │   │                                 #        confined to compliant tickers (§3, §4, §6c)
│   │   ├── compliance_state.py          # NEW — the flip→grace→divest state machine (§3, §4, §6c)
│   │   └── clock.py                     # NEW — daily event loop + quarterly rebalance trigger +
│   │                                     #        run_backtest() entry point (§3, §4, §6b, §6c)
│   └── cli/
│       ├── main.py                      # MODIFIED — registers the `backtest` subparser (one line, §1 precedent)
│       └── backtest.py                  # NEW — the `backtest` subcommand (§4.5)
└── tests/
    ├── fixtures/
    │   └── synthetic_universe.py        # MODIFIED (additive only) — one new ticker, `ZZFLIP01` (§6e)
    ├── test_backtest_portfolio.py       # NEW
    ├── test_backtest_strategy.py        # NEW
    ├── test_backtest_compliance_state.py # NEW
    ├── test_backtest_clock.py           # NEW
    └── test_cli_backtest.py             # NEW
```

**Files explicitly NOT created or touched in Phase 5:** `mizan/purification/` (there is no such
package yet — Phase 6's own module is `mizan/backtest/purification.py`, per `MASTER_PRD.md` §9.4;
Phase 5 does not create it), `mizan/reporting/`, no `purification`/`report` subcommands under
`mizan/cli/`. Confirmed by direct read of `mizan/backtest/` (does not exist prior to this phase),
`mizan/screening/` (Phase 4's, entirely untouched — no file under it is modified or imported *from*
in a way that reshapes it; `screen()` is imported and called, never edited), `mizan/data/db.py` /
`mizan/data/normalize.py` (untouched — Phase 5 is, like Phase 4, a read-only consumer of
`fundamentals_facts`/`price_bars`; see §5).

**Confirmed: this phase does not touch `mizan/purification/` or `mizan/reporting/`, and computes no
purification amount** — restated because the outer dispatch names this explicitly. Phase 5 records,
per divested/dividend-paying holding, the raw event data Phase 6 will need (flip date, divest date,
the holding's verdict history, and a per-dividend-event record of cash received and the verdict
active at that date, §3.3/§6c) — it does not compute a `non_compliant_income_ratio × dividend_amount`
purification figure, does not touch Fork A/B/C (register #9/#10/#11) beyond *reading* register #8
(`grace_period_rebalances`), and defines no side-ledger. That arithmetic is entirely Phase 6's.

---

## §2 Dependencies

### 2.1 No new dependency

**Decision: Phase 5 adds zero new third-party dependencies.** `pydantic` (schemas) and `duckdb`
(reading `fundamentals_facts`/`price_bars`, and indirectly via `screen()`) already cover everything
this phase needs. `pyarrow` is not imported by any Phase 5 module — Phase 5, like Phase 4, only ever
reads rows back out of DuckDB via `con.execute(...).fetchall()`; it never bulk-loads (§5 — no writes
at all).

### 2.2 `pandas` — still deliberately NOT promoted

`ULTIMATE_PRD.md` §2.1 names `pandas`'s role as "tabular glue for **strategy/report** layers," and
`PHASE_3_SPEC.md` §2.2 explicitly deferred its promotion to "whichever of Phase 5 (backtest/strategy)
or Phase 7 (reporting) is built first." Phase 5 **is** that first candidate — and this document's
decision, stated explicitly rather than assumed, is: **still no.** Every data-movement step this
phase needs (iterating sorted trading dates, computing a portfolio's mark-to-market value on one day,
applying one rebalance's target weights) is a small, explicit Python loop over already-typed
Pydantic/`float` values — there is no filtering, joining, or resampling of *tabular* data anywhere in
this phase's own logic (all such work already happened inside `screen()`'s SQL, Phase 4). Introducing
`pandas` here would be exactly the "premature import" failure mode `PHASE_1_SPEC.md` guard G13 /
`PHASE_2_SPEC.md` G-DEP1 / `PHASE_3_SPEC.md` G-DEP3 already established, now applied a third time.
**Decision: `pandas` remains forward-declared and unused in `[project.optional-dependencies].data`
until Phase 7** (reporting's own plot-input tabulation is the more natural first real consumer);
`pyproject.toml` is therefore **unmodified** by this phase.

### 2.3 No new dependency for the daily-clock loop or split/dividend bookkeeping

**Decision: hand-written, inspectable logic, no backtesting-library dependency.** `MASTER_PRD.md` §7's
own framing is explicit and is restated here as this phase's own governing rationale, not
re-litigated: "Not vectorbt/backtrader/zipline. The halal mechanics are a custom state machine no
off-the-shelf engine models, and an explicit daily loop is legible for learning." Same "hand-written
over a generic library" posture `PHASE_2_SPEC.md` §2.2 gave the two rate limiters and
`PHASE_3_SPEC.md` §2.3 gave the absence of a migration framework.

### 2.4 Forbidden-dependency list unchanged, and load-bearing for this phase specifically

`PHASE_1_SPEC.md` §2.5's permanently forbidden list (`openai`, `anthropic`, every other LLM/model SDK,
`yfinance`) still applies, unmodified. Per `ULTIMATE_PRD.md` §4.6/§5, this phase — alongside
screening — is where the permissibility boundary is most structurally at risk: a "strategy" module is
exactly the kind of place a build agent might reach for a leverage/margin/shorting primitive "to make
the backtest more realistic," or for an LLM "to decide which stock to pick." Neither may appear
anywhere under `mizan/backtest/`. See §7's restated grep set.

### 2.5 Modernization-log reconciliation

Same discipline as Phases 1–4: the `splitFactor`-direction verification item named in §0.1/§3.4 must
be logged in `docs/modernization_log.md` with a dated entry once the build agent confirms it live
(against a real, cached Tiingo response for a ticker with a known historical split, or against
Tiingo's own documentation page directly) — before `portfolio.py`'s split-adjustment arithmetic
direction is treated as settled.

---

## §3 Pydantic Schemas

Every new model inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no Phase 5 module subclasses `pydantic.BaseModel` directly, same guard as
every prior phase. Because every model is frozen, **portfolio state is a series of immutable
snapshots, not an in-place-mutated object** — `clock.py`'s loop threads a `Portfolio` value through
each day/rebalance, producing a *new* `Portfolio` each time rather than mutating one in place. This is
a deliberate design choice, not an artifact of the base class: it means the entire simulation history
is, by construction, a plain tuple of immutable values a test can inspect at any point, and it is
exactly the same "loaded config/results must not be mutated in place" posture `PHASE_1_SPEC.md` §3.1
already established for `Invariants`/`FiqhParams`, now applied to *simulation state* rather than
config.

### 3.1 `mizan/backtest/portfolio.py` — holdings and cash

```python
from pydantic import Field

from mizan.core.base import MizanBaseModel


class Holding(MizanBaseModel):
    """One position. `quantity` is constrained NON-NEGATIVE at the type level — `Field(ge=0.0)`, not
    a runtime `if quantity < 0: raise` check a caller could route around. Constructing
    `Holding(ticker="X", quantity=-1.0)` raises `pydantic.ValidationError` immediately, before the
    value can reach a `Portfolio`, `AllocationInstruction`, or anywhere else (`ULTIMATE_PRD.md` §5
    check 3: "negative position quantities" are a short position in disguise — permanently forbidden,
    `mizan.config.invariants.INVARIANTS.long_only`). Fractional (non-integer) quantities are
    permitted — a backtest weight-targeting strategy naturally produces fractional shares; V1 does
    not model whole-share/lot-size trading constraints (§9)."""

    ticker: str
    quantity: float = Field(ge=0.0)


class Portfolio(MizanBaseModel):
    """One immutable snapshot of the whole book: cash plus every currently-held position.

    `cash` is constrained NON-NEGATIVE at the type level (`Field(ge=0.0)`) — `mizan.config.
    invariants.INVARIANTS.fully_funded` means the portfolio can never spend more cash than it has;
    constructing a `Portfolio` with negative cash (an implicit margin loan) raises
    `pydantic.ValidationError` immediately, the same type-level guard `Holding.quantity` gives
    shorting. `holdings` omits a ticker entirely once its position reaches exactly `0.0` — an
    explicit `Holding(ticker=..., quantity=0.0)` entry is never retained (§6a), so `len(holdings)`
    always equals the number of tickers ACTUALLY held, not the number ever held.
    """

    cash: float = Field(ge=0.0)
    holdings: dict[str, Holding]
```

**`INVARIANTS.cash_yield` is read directly from `mizan.config.invariants.INVARIANTS` at the one call
site that ever applies it (`apply_cash_yield`, §4.1/§6a) — never passed in as a function parameter,
never re-declared as a local `0.0` literal.** Unlike `fiqh_params` (deliberately parameterized
throughout this codebase for testability — a config-drift test *needs* to be able to `model_copy` a
different value in), `INVARIANTS` is never accepted as a parameter anywhere in `mizan/backtest/` —
doing so would visually suggest it is a tunable knob, which `PHASE_1_SPEC.md` §3.2 already forbids
structurally. The one test-only exception (`tests/test_invariants.py` constructing a
deliberately-violating `Invariants` instance) belongs to Phase 1 and is not reopened here.

### 3.2 `mizan/backtest/strategy.py` — the pluggable, structurally-confined strategy interface

```python
from typing import Protocol

from pydantic import model_validator

from mizan.core.base import MizanBaseModel


class AllocationInstruction(MizanBaseModel):
    """A strategy's rebalance decision: target PORTFOLIO-VALUE WEIGHTS for a subset of the tickers it
    was given. This is the one model in Phase 5 that makes leverage and shorting structurally
    impossible BY CONSTRUCTION, independent of `INVARIANTS` — every weight is validated in
    `[0.0, 1.0]` and the weights must sum to at most `1.0`; any residual (`1.0 - sum(weights)`) is
    left as cash, which is exactly `MASTER_PRD.md` §7's `hold-cash` action. A strategy attempting to
    over-allocate (implying borrowed capital) or under-specify a negative weight (implying a short)
    cannot construct this object at all — `pydantic.ValidationError`, not a downstream check.
    """

    target_weights: dict[str, float]

    @model_validator(mode="after")
    def _weights_are_long_only_and_fully_funded(self) -> "AllocationInstruction":
        for ticker, weight in self.target_weights.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(
                    f"{ticker}: weight {weight!r} outside [0.0, 1.0] — a negative weight is a "
                    "short position, a weight above 1.0 is leverage; both are permanently forbidden"
                )
        total = sum(self.target_weights.values())
        if total > 1.0 + 1e-9:
            raise ValueError(
                f"target_weights sum to {total!r} > 1.0 — implies borrowed capital (margin), "
                "permanently forbidden (mizan.config.invariants.INVARIANTS.margin_allowed)"
            )
        return self


class Strategy(Protocol):
    """The pluggable long-only strategy interface (`MASTER_PRD.md` §7). See §4.2 for the exact
    structural argument for why a conforming `Strategy` cannot select a `Verdict.NON_COMPLIANT`
    ticker even if it tried."""

    def select(
        self, *, as_of_date: "date", compliant_tickers: frozenset[str], portfolio: Portfolio
    ) -> AllocationInstruction: ...
```

**No `Strategy` implementation ships in `mizan/backtest/` beyond one reference implementation used by
this phase's own tests (§6e), `EqualWeightStrategy`** (equal-weights every ticker in
`compliant_tickers`, per rebalance) — a minimal, honest example proving the interface is usable, not
a claim of a real trading strategy. Building an actual research strategy is explicitly the project
owner's own future work over this substrate, same posture Phase 4 §9 gave the real activity map.

### 3.3 `mizan/backtest/compliance_state.py` — the state-machine and event models

```python
from datetime import date as _Date
from enum import StrEnum

from mizan.core.base import MizanBaseModel
from mizan.core.verdict import Verdict  # imported by full path, mirrors mizan/screening/verdict.py's
                                          # own convention (PHASE_4_SPEC.md §0) — a grep for "Verdict"
                                          # in this module unambiguously means "the enum"


class HoldingComplianceState(StrEnum):
    """`MASTER_PRD.md` §7.3's state-machine diagram, transcribed as an enum. A newly-selected
    holding always starts `HELD_COMPLIANT` — the strategy interface (§3.2/§4.2) makes it structurally
    impossible for a holding to ever be FIRST established while `NON_COMPLIANT`."""

    HELD_COMPLIANT = "held_compliant"
    HELD_NONCOMPLIANT_GRACE = "held_noncompliant_grace"
    DIVESTED = "divested"


class VerdictObservation(MizanBaseModel):
    """One rebalance's re-screen result for one holding — the "verdict history" the outer dispatch
    asks Phase 5 to record for Phase 6's future purification-attribution use (`MASTER_PRD.md` §8:
    "the ratio comes from that holding's most-recent screen")."""

    as_of_date: _Date
    verdict: Verdict


class ComplianceStateRecord(MizanBaseModel):
    """The full compliance-tracking record for one ticker across the life of a backtest. One record
    per ticker ever held; `state`/`flip_date`/`divest_date`/`grace_rebalances_remaining` describe
    ONLY the state machine (`MASTER_PRD.md` §7.3); `verdict_history` is the append-only audit trail
    (§6c) — every rebalance's `screen()` result for this ticker, in order, for as long as it is held.
    """

    ticker: str
    cik: str
    state: HoldingComplianceState
    flip_date: _Date | None
    """Set the rebalance a HELD_COMPLIANT -> HELD_NONCOMPLIANT_GRACE transition first fires for this
    ticker. Never cleared or overwritten once set — a ticker flips at most once per backtest (§6c: the
    state machine has no HELD_NONCOMPLIANT_GRACE -> HELD_COMPLIANT edge, per MASTER_PRD.md §7.3's own
    diagram, which draws no "un-flip" branch)."""
    divest_date: _Date | None
    """Set the rebalance a HELD_NONCOMPLIANT_GRACE -> DIVESTED transition fires. `flip_date` and
    `divest_date`, together, are MASTER_PRD.md §8 Fork C's "time-bounded flip-date to
    divestment-date" window — the exact pair Phase 6's forced-divestment purification attribution
    will read, unchanged from how this record leaves them."""
    grace_rebalances_remaining: int | None
    """`None` outside HELD_NONCOMPLIANT_GRACE. Set to `fiqh_params.grace_period_rebalances.value`
    (read fresh at the flip, §7 guard G-B4) the rebalance the flip fires, and decremented by exactly
    1 at every SUBSEQUT rebalance (§6c) until it reaches 0, at which point DIVESTED fires."""
    verdict_history: tuple[VerdictObservation, ...]


class DivestmentEvent(MizanBaseModel):
    """One completed forced-divestment, as a standalone record — the minimum Phase 6 needs without
    having to re-derive it from a full `ComplianceStateRecord` (`MASTER_PRD.md` §8 Fork C)."""

    ticker: str
    cik: str
    flip_date: _Date
    divest_date: _Date


class DividendEvent(MizanBaseModel):
    """One dividend cash credit received while a ticker was held — Phase 6's other required input
    (`MASTER_PRD.md` §8: "the dividend cash comes from Tiingo's per-day divCash field" and "the ratio
    comes from that holding's most-recent screen"). `verdict_at_ex_date` is the MOST RECENT
    REBALANCE's verdict for this ticker as of `ex_date` — screening only happens at rebalances
    (§6b), so a dividend paid between rebalances is attributed to whichever verdict was most recently
    established, exactly matching MASTER_PRD.md §8's own wording.
    """

    ticker: str
    cik: str
    ex_date: _Date
    div_cash_per_share: float
    quantity_held: float
    cash_received: float
    verdict_at_ex_date: Verdict
```

### 3.4 The daily/per-rebalance result type, and the `(returns, purification_ledger, active_caveats)` contract

`ULTIMATE_PRD.md` §2.1's two load-bearing seams name the target shape verbatim: "a backtest result is
`(returns, purification_ledger, active_caveats: list[Caveat])`." Purification does not exist yet
(Phase 6). **Decision, stated explicitly per the "additive extension only" rule every phase spec has
followed:**

```python
class DailySnapshot(MizanBaseModel):
    """One trading day's mark-to-market state — the `returns` element of the tuple above, in its
    raw (not-yet-return-computed) form; Phase 7's reporter is where a snapshot series becomes an
    actual return series (ULTIMATE_PRD.md §4.8 belongs to the reporting layer, not this one)."""

    as_of_date: _Date
    cash: float
    holdings: dict[str, float]  # ticker -> quantity, a snapshot copy (never the live Portfolio object)
    portfolio_value: float      # cash + sum(quantity * raw_close) that day — see §6a for why raw_close


class BacktestResult(MizanBaseModel):
    """The Phase-5-scoped result type `screen()`'s own `ScreeningVerdict` precedent is followed for:
    a fully-typed value every internal function/test works with, wrapped in `ResultEnvelope` only at
    the final return (§4.4), never exposed unwrapped to a human-facing caller.

    `purification_ledger` is a deliberate, loose placeholder — `dict[str, object] | None`, defaulting
    to `None` — for EXACTLY the same reason `mizan.core.caveats.ResultEnvelope.payload` is
    `dict[str, object]` rather than a phase-specific type (PHASE_1_SPEC.md §3.5, PHASE_4_SPEC.md
    §3.4): Phase 6 needs to attach a real, typed ledger here WITHOUT Phase 5 having to guess its
    shape, and WITHOUT this field's own type ever changing (a type change would violate every prior
    phase's "additive extension only, never a renamed/removed symbol" rule). Phase 6 populates this
    dict (via its own typed model's `.model_dump()`, the same round-trip pattern
    `ScreeningVerdict.model_validate(envelope.payload)` already establishes) rather than replacing the
    field's type. Phase 5 always leaves it `None` — it computes no purification amount (§1, §9).
    """

    daily_snapshots: tuple[DailySnapshot, ...]
    divestment_events: tuple[DivestmentEvent, ...]
    dividend_events: tuple[DividendEvent, ...]
    compliance_states: dict[str, ComplianceStateRecord]  # every ticker ever held, final state
    purification_ledger: dict[str, object] | None = None
```

**Which caveats `run_backtest()` stamps on the outer `ResultEnvelope`, always:** `Caveat.
LOOK_AHEAD_BIAS` and `Caveat.PENDING_SCHOLARLY_VERIFICATION` — inherited from every underlying
`screen()` call the backtest makes (Phase 4's own caveats are a property of *that* call, but the
backtest as a whole is equally subject to the same Fork-1 simplification and the same "every fiqh
param is unratified" fact, so restamping them at this outer layer is not redundant, it is the
`ResultEnvelope` contract applied at the correct altitude). **New this phase:** `Caveat.
SURVIVORSHIP_BIAS` — `mizan/core/caveats.py`'s own Phase 1 docstring names this exactly: "a
Phase 5 backtest-level concern about which tickers are even considered," and `PHASE_4_SPEC.md` §3.4
explicitly deferred it here. `run_backtest()` is the first, and only, function in `mizan/` that
stamps it, because it is the first function whose own INPUT is a fixed ticker universe (§4.4's
`tickers` parameter) rather than one ticker screened in isolation.

### 3.5 No 12th fiqh-register entry, no `Invariants` change

Phase 5 introduces zero new `FiqhParam` rows and zero new `Invariants` fields. Register #8
(`grace_period_rebalances`) already exists and is the only fiqh param this phase directly consumes
(§6c); the rebalance cadence itself is **not** a register entry and Phase 5 does not make it one
(§0.1 of `ULTIMATE_PRD.md`'s Hard Boundary reinforcement — see §4.3/§9 below).

---

## §4 Public Interfaces / Function Signatures

### 4.1 `mizan/backtest/portfolio.py`

```python
def apply_cash_yield(portfolio: Portfolio) -> Portfolio:
    """Return a new `Portfolio` with cash multiplied by `(1.0 + INVARIANTS.cash_yield)` — imported
    and read DIRECTLY from `mizan.config.invariants.INVARIANTS` inside this function body, never
    accepted as a parameter, never re-declared as a bare `0.0` literal a second time (§7 guard G-B1).
    Since `INVARIANTS.cash_yield` is permanently `0.0` (boot-gated, §7 guard G-B1a), this is a
    structural no-op today — cash after this call is bit-for-bit identical to cash before it — but it
    is expressed as a genuine read of config rather than an assumption, so a future accidental change
    to `Invariants.cash_yield`'s default (which `mizan-boot-check`/`mizan`'s own centralized
    `check_all()` would already HALT on before any simulation starts, §7 guard G-B1a) is caught by
    TWO independent mechanisms, not silently trusted to only one.
    """


def apply_split(holding: Holding, split_factor: float) -> Holding:
    """Return a new `Holding` with `quantity` adjusted for one day's `price_bars.split_factor`.
    **The exact multiplication direction (`quantity * split_factor` vs `quantity / split_factor`)
    is a build-time verification item, not assumed** — see §3.4/§6b's own "verify, don't recall" note.
    """


def mark_to_market(portfolio: Portfolio, prices: dict[str, float]) -> float:
    """Portfolio value = `portfolio.cash + sum(holding.quantity * prices[holding.ticker] for holding
    in portfolio.holdings.values())`. `prices` is caller-supplied (always `raw_close`, §6a) — this
    function does no DB I/O itself, keeping it a pure, trivially-testable arithmetic function."""


def credit_dividend(portfolio: Portfolio, ticker: str, div_cash_per_share: float) -> Portfolio:
    """Return a new `Portfolio` with `cash` increased by `div_cash_per_share * portfolio.holdings[
    ticker].quantity` (0.0 if `ticker` is not currently held — a no-op, not an error, since
    `price_bars` covers every ticker in the requested universe, held or not). This is a REALIZED
    distribution credited to cash, not "yield on cash" — it does not touch, and is unaffected by,
    `INVARIANTS.cash_yield` (§3.1's own clarifying note)."""


def apply_allocation(
    portfolio: Portfolio, instruction: AllocationInstruction, prices: dict[str, float]
) -> Portfolio:
    """Rebalance `portfolio` to `instruction.target_weights` at `prices` (`raw_close`, §6a). For each
    ticker in `instruction.target_weights`, computes `target_value = weight * mark_to_market(
    portfolio, prices)`, converts to a target `quantity = target_value / prices[ticker]`, and adjusts
    cash by the value delta traded. A ticker currently held but ABSENT from `instruction.
    target_weights` is fully liquidated (target quantity `0.0`, removed from `holdings`, §3.1). Every
    resulting `Holding.quantity` and `Portfolio.cash` is non-negative BY CONSTRUCTION (§3.1, §3.2) —
    this function cannot itself produce a shorted or over-drawn `Portfolio`; a `target_weights` sum
    exceeding what current + newly-freed cash can fund is impossible by construction too, since
    `AllocationInstruction`'s own validator (§3.2) already forbids a sum above `1.0` of portfolio
    value, and portfolio value is computed BEFORE any trade in this same call.
    """
```

### 4.2 `mizan/backtest/strategy.py`

```python
class StrategyContractViolationError(RuntimeError):
    """Raised by `clock.py`'s `rebalance()` (§4.4) if a `Strategy.select()` implementation returns an
    `AllocationInstruction` naming a ticker OUTSIDE the `compliant_tickers` frozenset it was given.
    This should be UNREACHABLE for any conforming `Strategy` — `compliant_tickers` is the only source
    of tickers a `select()` implementation is ever handed (it receives no `con`, no `cache_dir`, no
    access to `screen()`, and no reference to the full requested universe — only the pre-filtered
    compliant subset), so it has no way to even NAME a `NON_COMPLIANT` ticker. This exception exists
    as the defense-in-depth backstop for a broken or adversarial `Strategy` implementation, exactly
    the same "structural design + an assertion backstop that should never fire" pattern
    `PHASE_1_SPEC.md` §6.1 used for `check_invariants()`'s seven hand-written checks — never routed
    around, never caught-and-continued.
    """


class EqualWeightStrategy:
    """Reference `Strategy` implementation (§3.2): `select()` returns `AllocationInstruction(
    target_weights={ticker: 1.0 / len(compliant_tickers) for ticker in compliant_tickers})` — or
    `AllocationInstruction(target_weights={})` (all cash) if `compliant_tickers` is empty. Used by
    this phase's own tests (§6e); not presented as a real research strategy (§3.2)."""

    def select(
        self, *, as_of_date: date, compliant_tickers: frozenset[str], portfolio: Portfolio
    ) -> AllocationInstruction: ...
```

**The precise structural argument for "cannot select a Non-compliant ticker," stated once, referenced
everywhere else:** a `Strategy.select()` implementation's signature is
`(*, as_of_date, compliant_tickers: frozenset[str], portfolio: Portfolio) -> AllocationInstruction`.
Every ticker-typed value reachable inside `select()`'s own body is either a member of
`compliant_tickers` (which `clock.py`'s `rebalance()`, §4.4, populates ONLY with tickers whose
freshly-computed `Verdict` this rebalance is `PURE` or `MIXED` — never `NON_COMPLIANT`, §6b) or a key
of `portfolio.holdings` (which can only ever contain tickers a PRIOR call to `apply_allocation` put
there, themselves sourced from a prior `compliant_tickers` set, recursively — §6c's own invariant
that a ticker is force-divested, never silently retained, the rebalance its verdict flips). There is
no third source of a ticker name inside `Strategy.select()`'s scope. This makes selecting a
`NON_COMPLIANT` ticker not merely "checked and rejected" but literally **unnameable** from inside a
conforming implementation — the interface itself carries no channel through which such a ticker could
be referenced. `StrategyContractViolationError` (above) is the assertion that fires only if a
`Strategy` implementation manufactures a ticker string from OUTSIDE that scope (e.g. a hardcoded
literal) — an implementation bug the type system cannot itself prevent, which is exactly why the
backstop exists.

### 4.3 `mizan/backtest/clock.py` — the daily loop, the rebalance trigger, and `run_backtest()`

```python
#: The rebalance cadence. HARDCODED — not a `FiqhParams` register entry, not a CLI flag, not a
#: function parameter anywhere in this module. `ULTIMATE_PRD.md` §1.1: "a proposal to shorten the
#: rebalance cadence below quarterly... is crossing a values boundary, not tuning a parameter... must
#: be escalated to the human, never absorbed as an enhancement." This phase implements that as the
#: simplest possible guarantee — there is no code path, flag, or config value anywhere under
#: `mizan/backtest/` that can make a backtest rebalance faster than quarterly, because the calendar-
#: quarter-boundary months below are the ONLY rebalance-date generator this module contains.
_REBALANCE_MONTHS: tuple[int, ...] = (1, 4, 7, 10)


def generate_rebalance_dates(start_date: date, end_date: date) -> tuple[date, ...]:
    """Deterministic, pure function of its two arguments: `start_date` itself, plus the first
    calendar day of every `_REBALANCE_MONTHS` month strictly between `start_date` and `end_date`
    (inclusive of `end_date` if it happens to land exactly on one). `start_date` is always included
    as the FIRST rebalance — a backtest must deploy its initial capital on day one, not wait for the
    next calendar-quarter boundary; this is a scheduling convenience, not a cadence change (the
    SECOND rebalance is still governed by `_REBALANCE_MONTHS`, so the cadence between rebalances 2..N
    is always exactly quarterly).
    """


def step(portfolio: Portfolio, prices: dict[str, float], splits: dict[str, float]) -> Portfolio:
    """Advance `portfolio` by exactly one trading day with NO trading and NO re-screening: applies
    `apply_split` (§4.1) to every currently-held ticker with a `splits[ticker] != 1.0` entry that
    day, then `apply_cash_yield` (§4.1, a structural no-op). Dividend crediting is NOT done here —
    see `run_backtest`'s own per-day loop body (§6b) for why dividend crediting and marking-to-market
    happen at the orchestration level, not inside this single-responsibility step function.
    """


def rebalance(
    portfolio: Portfolio,
    as_of_date: date,
    *,
    universe: frozenset[str],
    strategy: Strategy,
    compliance_states: dict[str, ComplianceStateRecord],
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> tuple[Portfolio, dict[str, ComplianceStateRecord], tuple[DivestmentEvent, ...]]:
    """One quarterly rebalance boundary (§6c). Re-screens (via `mizan.screening.verdict.screen`)
    EVERY ticker in `universe` (the full requested candidate set, not just currently-held tickers —
    a strategy must be able to newly ENTER a ticker that only just started passing) plus every
    ticker currently held that has since fallen out of `universe` (should not normally occur, since
    `universe` is fixed for the whole backtest, §4.5 — defensive completeness only). Runs
    `compliance_state.transition` (§4.4) for every currently-held ticker using this rebalance's fresh
    `Verdict`, force-liquidates any ticker whose transition produces `HoldingComplianceState.DIVESTED`
    THIS rebalance (selling it out of the portfolio entirely, at this rebalance's price, BEFORE the
    strategy is consulted — a divested ticker is never offered to `strategy.select()` even if its
    fresh verdict happened to be compliant again, §6c's own "no un-flip" note), computes
    `compliant_tickers = frozenset of every universe ticker whose fresh Verdict is PURE or MIXED`,
    calls `strategy.select(as_of_date=as_of_date, compliant_tickers=compliant_tickers, portfolio=...)`,
    validates the returned `AllocationInstruction` names only tickers in `compliant_tickers`
    (`StrategyContractViolationError` otherwise, §4.2), and applies it via `apply_allocation` (§4.1).
    """


def run_backtest(
    *,
    tickers: frozenset[str],
    start_date: date,
    end_date: date,
    initial_cash: float,
    strategy: Strategy,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap | None = None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ResultEnvelope:
    """THE canonical, singular backtest entry point — this phase's analogue of `screen()`. Boot-check
    is NOT re-run here (§7 guard G-B1a: `mizan/cli/main.py`'s centralized `check_all()`, unmodified,
    already runs before ANY subcommand — including `backtest` — dispatches, and
    `mizan.config.invariants.INVARIANTS` is a frozen singleton that cannot change value between that
    check and this call within one process).

    Builds `generate_rebalance_dates(start_date, end_date)` (§4.3), then iterates every trading day
    present in `price_bars` for `tickers`, from `start_date` to `end_date` inclusive, in order. On
    every day: applies `step()` (§4.3, split adjustment), credits any dividends via `credit_dividend`
    for tickers with a nonzero `price_bars.div_cash` that day (recording a `DividendEvent` per credit,
    §3.3, stamped with the most-recently-established verdict for that ticker), and appends one
    `DailySnapshot`. On a day that is ALSO a rebalance date (§4.3): calls `rebalance()` (§4.3) instead
    of the plain no-trade path, threading its updated portfolio/compliance-state/divestment-event
    outputs forward.

    Returns `ResultEnvelope(active_caveats=(Caveat.LOOK_AHEAD_BIAS, Caveat.SURVIVORSHIP_BIAS,
    Caveat.PENDING_SCHOLARLY_VERIFICATION), payload=BacktestResult(...).model_dump())` (§3.4).
    """
```

### 4.4 `mizan/backtest/compliance_state.py`

```python
def transition(
    record: ComplianceStateRecord | None,
    *,
    ticker: str,
    cik: str,
    as_of_date: date,
    new_verdict: Verdict,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> tuple[ComplianceStateRecord, DivestmentEvent | None]:
    """Pure function — no DB, no cache, no network (§7 guard G-B5, mirroring Phase 4's own
    `classify_business_activity` purity). `record=None` means this is the FIRST rebalance this
    ticker has ever been screened as a holding: initializes a new `HELD_COMPLIANT` record (asserting
    `new_verdict != Verdict.NON_COMPLIANT` — a newly-selected holding can never itself be
    `NON_COMPLIANT`, by the strategy interface's own structural guarantee, §4.2; a violation here
    indicates a `StrategyContractViolationError`-class bug upstream, not a normal state to handle
    gracefully).

    Transition table (§6c), read from `record.state`:
      * `HELD_COMPLIANT`, `new_verdict` in `{PURE, MIXED}`: stays `HELD_COMPLIANT`; append a
        `VerdictObservation` to `verdict_history`; no other field changes.
      * `HELD_COMPLIANT`, `new_verdict == NON_COMPLIANT`: **flip detected.** Transitions to
        `HELD_NONCOMPLIANT_GRACE`, `flip_date=as_of_date`, `grace_rebalances_remaining=
        fiqh_params.grace_period_rebalances.value` (read fresh from `fiqh_params` on every call,
        never hardcoded — §7 guard G-B4).
      * `HELD_NONCOMPLIANT_GRACE`, any `new_verdict`: decrements `grace_rebalances_remaining` by
        exactly 1 (append the `VerdictObservation` regardless of what `new_verdict` says — the grace
        countdown, once started, runs to completion irrespective of a later, incidental return to
        compliance; `MASTER_PRD.md` §7.3's own diagram draws no un-flip edge, and this is where that
        absence is implemented, not merely documented). If the decremented value reaches `0`:
        transitions to `DIVESTED`, `divest_date=as_of_date`, and returns a populated `DivestmentEvent`
        as the second tuple element. Otherwise stays `HELD_NONCOMPLIANT_GRACE`.
      * `DIVESTED`: **must never be called again for this ticker.** `rebalance()` (§4.3) never
        re-screens a ticker once it force-liquidates it this same rebalance, so this branch is
        asserted unreachable (`AssertionError`, not a silently-tolerated no-op) rather than handled.

    Returns `(updated_record, divestment_event_or_none)` — the caller (`rebalance()`, §4.3) is
    responsible for actually liquidating the position in the SAME rebalance a `DivestmentEvent` is
    returned; this function only updates bookkeeping, it never touches a `Portfolio`.
    """
```

### 4.5 `mizan/cli/main.py`, `mizan/cli/backtest.py`

```python
# mizan/cli/main.py — ONE new line added to build_parser(), no other change:
#     backtest_cli.add_subparser(subparsers)


# mizan/cli/backtest.py
def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Registers `backtest --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --initial-cash FLOAT --db-path PATH --cache-dir PATH
    [--overrides-path PATH]`. `--ticker` (repeated) is the CANDIDATE universe `EqualWeightStrategy`
    (the only built-in `Strategy`, §3.2/§7's own restated non-goal on a plugin-loading mechanism) may
    select from — NOT a claim that these are the real ~100-ticker universe (§9). `--overrides-path`
    is optional, same honest-empty-default posture as `mizan screen` (`PHASE_4_SPEC.md` §4.4). There
    is deliberately NO `--rebalance-frequency` (or similarly-named) flag anywhere on this subcommand
    — see §4.3's own note and §9.
    """


def run(args: argparse.Namespace) -> int:
    """Opens one READ-ONLY DuckDB connection (`db.connect(args.db_path, read_only=True)` — `backtest`
    never writes to DuckDB, §5, same posture as `mizan screen`), loads the override map once via
    `load_override_map(args.overrides_path)`, constructs `EqualWeightStrategy()`, calls
    `run_backtest(...)`, and prints a human-readable summary to stdout: final portfolio value, every
    `DivestmentEvent` (ticker, flip date, divest date), and every `DividendEvent`'s total credited
    cash per ticker. Catches the same per-ticker-shaped exceptions `mizan screen` catches
    (`CikResolutionError`/`SicResolutionError`/`NotNormalizedError`/`InsufficientDataError`, all
    reachable via `run_backtest`'s internal `screen()` calls) at the WHOLE-BACKTEST level (a halt on
    any single ticker's re-screen aborts the entire run rather than continuing with a partial
    universe, unlike `mizan screen`'s own per-ticker-continue posture — a backtest's tickers are not
    independent of each other the way a screening batch's are: a mid-run halt on one ticker leaves
    the portfolio's own state, and every OTHER ticker's fair comparison against it, undefined). Prints
    a `HALT: ...` message to stderr and returns exit code 1 on any such exception.
    """
```

---

## §5 Migrations

**N/A, confirmed explicitly.** Phase 5 adds no DuckDB table, column, index, and issues no
`CREATE`/`ALTER`/`DROP`/`INSERT` anywhere in its own code. It opens `fundamentals_facts`/`price_bars`
strictly read-only (`db.connect(..., read_only=True)`, the same Phase 3-established mode Phase 4's
`mizan screen` already uses) and writes nothing new to DuckDB.

**Why no `backtest_results` table, stated explicitly since this is the first phase whose output is a
multi-day time series large enough that persisting it might seem natural:** `BacktestResult` (§3.4) is
returned to the CLI's `run()` (§4.5) as an in-memory object for that single process invocation to
summarize and print; nothing in this phase's own scope needs a SECOND process to later read a
PRIOR backtest's results back out of storage. Phase 6 (purification) and Phase 7 (reporting) are
expected to invoke `run_backtest()` themselves, in-process, as part of their own pipeline (`MASTER_PRD.
md` §9.1's own pipeline diagram shows BACKTEST feeding directly into REPORT with no persistence stage
drawn between them) — not to read a Phase-5-persisted result file. Introducing a `backtest_results`
DuckDB table now, with no concrete consumer needing cross-process persistence, would be exactly the
premature-schema-surface `PHASE_3_SPEC.md` §5.3 already declined for a versioned migration framework,
applied here to a table rather than a framework. If a future phase genuinely needs to persist and
re-load backtest results across separate process invocations, that is a new, reviewed schema decision
for that phase's own spec — not something Phase 5 should silently anticipate.

---

## §6 Implementation Logic Flow

### 6a. `portfolio.py` — why `raw_close` (never `adj_close`) governs the backtest's own valuation and trading

Stated explicitly because it is easy to get backwards, and because it is a genuinely different
question from Phase 4's own `raw_close`-vs-`adj_close` decision (`PHASE_4_SPEC.md` §6b) even though
the answer happens to be the same field name — the reasoning must not be assumed to transfer silently.

Tiingo's `adj_close` is a back-adjusted price series constructed so that a return computed directly
from it already reflects total return **assuming every dividend was reinvested at the time it was
paid** (`docs/modernization_log.md` §6.2, `ULTIMATE_PRD.md` §5.2's own "clean total-return series"
framing). Mizan's own backtest architecture does **not** reinvest dividends automatically — a dividend
is a realized cash distribution that lands in the portfolio's `cash` balance (§4.1's `credit_dividend`)
precisely so that Phase 6 can later apply the AAOIFI side-ledger purification ratio to it
(`MASTER_PRD.md` §8), and `INVARIANTS.cash_yield = 0.0` means that cash then sits idle, earning
nothing, until the next rebalance redeploys it. **Valuing a held position using `adj_close` while
ALSO crediting `div_cash` to cash would double-count every dividend** — once as an implicit uplift
baked into the adjusted price, once as an explicit cash credit. `raw_close` — the actual traded price
on that date — is therefore the correct field for every position-valuation and trade-sizing
computation in `mizan/backtest/portfolio.py` (`mark_to_market`, `apply_allocation`), with dividends and
splits handled EXPLICITLY and separately (`credit_dividend`, `apply_split`) rather than implicitly
via an adjusted price series. This is the same `raw_*`/`adj_*` non-conflation discipline
(`ULTIMATE_PRD.md` §4.2 guard G-T3) Phase 2/3/4 already established, correctly re-derived for this
phase's own, different consumption context — not a copy-paste of Phase 4's reasoning.

**The one remaining open item, named rather than guessed (§0.1, §2.5, §3.4):** `price_bars.
split_factor`'s exact multiplication convention. The build agent must verify, live, whether Tiingo's
`splitFactor` on the ex-split date should MULTIPLY or DIVIDE a held share count to keep
`quantity * raw_close` continuous across the split (i.e., whether a 2-for-1 split is represented as
`splitFactor = 2.0` applied as a multiplier to shares, or as a divisor) — against Tiingo's own
documentation, or against a real cached response for a ticker with a known historical split — and log
the confirmed direction in `docs/modernization_log.md` before `apply_split`'s arithmetic is finalized.
This is a mechanical, blocking-but-not-judgment-call verification item, the same category
`PHASE_4_SPEC.md` §2.2 gave the XBRL tag allow-lists.

### 6b. `clock.py`'s daily loop and the quarterly rebalance trigger

```
run_backtest(tickers, start_date, end_date, initial_cash, strategy, con, cache_dir, overrides,
             fiqh_params):
    rebalance_dates = generate_rebalance_dates(start_date, end_date)     # §4.3, hardcoded quarterly
    trading_dates = sorted distinct price_bars.trade_date WHERE ticker IN tickers
                    AND trade_date BETWEEN start_date AND end_date
    portfolio = Portfolio(cash=initial_cash, holdings={})
    compliance_states: dict[str, ComplianceStateRecord] = {}
    snapshots = []
    divestment_events = []
    dividend_events = []

    for as_of_date in trading_dates:
        day_rows = price_bars rows for `tickers` WHERE trade_date == as_of_date   # one query, or one
                                                                                    # per ticker — the
                                                                                    # build agent's own
                                                                                    # choice, both are
                                                                                    # equivalent here
        prices  = {ticker: row.raw_close for row in day_rows}
        splits  = {ticker: row.split_factor for row in day_rows}
        divs    = {ticker: row.div_cash for row in day_rows if row.div_cash != 0.0}

        portfolio = step(portfolio, prices, splits)                       # §4.3 — split adjustment only

        for ticker, div_cash_per_share in divs.items():
            if ticker in portfolio.holdings:
                quantity_held = portfolio.holdings[ticker].quantity
                portfolio = credit_dividend(portfolio, ticker, div_cash_per_share)
                dividend_events.append(DividendEvent(
                    ticker=ticker, cik=<from compliance_states[ticker].cik>,
                    ex_date=as_of_date, div_cash_per_share=div_cash_per_share,
                    quantity_held=quantity_held,
                    cash_received=div_cash_per_share * quantity_held,
                    verdict_at_ex_date=compliance_states[ticker].verdict_history[-1].verdict,
                ))

        if as_of_date in rebalance_dates:
            portfolio, compliance_states, new_divestments = rebalance(
                portfolio, as_of_date, universe=tickers, strategy=strategy,
                compliance_states=compliance_states, con=con, cache_dir=cache_dir,
                overrides=overrides, fiqh_params=fiqh_params,
            )
            divestment_events.extend(new_divestments)

        snapshots.append(DailySnapshot(
            as_of_date=as_of_date, cash=portfolio.cash,
            holdings={t: h.quantity for t, h in portfolio.holdings.items()},
            portfolio_value=mark_to_market(portfolio, prices),
        ))

    result = BacktestResult(
        daily_snapshots=tuple(snapshots), divestment_events=tuple(divestment_events),
        dividend_events=tuple(dividend_events), compliance_states=compliance_states,
    )
    return ResultEnvelope(
        active_caveats=(Caveat.LOOK_AHEAD_BIAS, Caveat.SURVIVORSHIP_BIAS,
                        Caveat.PENDING_SCHOLARLY_VERIFICATION),
        payload=result.model_dump(),
    )
```

**Why dividend crediting is a plain loop inside `run_backtest` rather than a `step()`
responsibility (§4.3's own forward-reference):** `step()` is deliberately kept to the one
single-day, no-side-information transformation every day shares (split adjustment, cash-yield
no-op); dividend crediting additionally needs to *record* a `DividendEvent` referencing the
CURRENT compliance state, which only the orchestrating loop has in scope. Keeping `step()` free of
that responsibility keeps it a pure, two-argument, trivially-testable function.

### 6c. `compliance_state.transition` — the flip → grace → divest sequence, worked through concretely

Using the default `fiqh_params.grace_period_rebalances.value == 1` (`mizan/config/fiqh_params.py`
register #8, unchanged this phase):

```
Rebalance N   : screen() returns MIXED.       record=None -> HELD_COMPLIANT, verdict_history=[N:MIXED]
Rebalance N+1 : screen() returns NON_COMPLIANT. HELD_COMPLIANT -> HELD_NONCOMPLIANT_GRACE,
                flip_date=N+1, grace_rebalances_remaining=1, verdict_history += [N+1:NON_COMPLIANT]
Rebalance N+2 : screen() returns NON_COMPLIANT (or anything — irrelevant, §6c transition table).
                grace_rebalances_remaining: 1 -> 0 -> HELD_NONCOMPLIANT_GRACE -> DIVESTED,
                divest_date=N+2, DivestmentEvent(flip_date=N+1, divest_date=N+2) returned.
                rebalance() (§4.3) force-liquidates the holding THIS rebalance, before consulting
                the strategy.
```

With `fiqh_params.grace_period_rebalances` changed (via `model_copy`, since `FiqhParams` is frozen)
to `value=2`: the SAME flip at rebalance N+1 sets `grace_rebalances_remaining=2`; rebalance N+2
decrements to `1` (stays `HELD_NONCOMPLIANT_GRACE`); rebalance N+3 decrements to `0` and DIVESTS —
one full extra rebalance later than the default, proving the timing is READ from `fiqh_params`, not
hardcoded (§7 guard G-B4, §8 AC2).

### 6d. Failure-mode categorization, restated for this phase specifically

Per `ULTIMATE_PRD.md` §4.6's own table, transcribed here with each row's Phase-5-specific
implementation named (§7 gives the full guard table; this is the narrative walkthrough):

- **`CASH_YIELD != 0.0` at runtime** — already caught by `mizan/cli/main.py`'s centralized
  `check_all()`, which every subcommand (including the new `backtest` one) runs before dispatch;
  Phase 5 adds NO second pre-simulation check, because `INVARIANTS` is a frozen, module-level
  singleton that cannot change value between that check and `run_backtest()`'s own execution within
  the same process (§4.3's own note, §7 guard G-B1a).
- **A strategy attempts to hold/select a Non-compliant ticker** — structurally impossible by the
  `Strategy.select()` interface's own scope (§4.2), backstopped by `StrategyContractViolationError`.
- **Compliance-flip missed at a rebalance boundary** — `rebalance()` (§4.3) re-screens every ticker in
  `universe` unconditionally, every rebalance, with no early-exit/skip path; §7 guard G-B3's own test
  asserts this via a call-count check against a wrapped `screen()`.
- **Grace-period misconfiguration** — a review-gate concern (`fiqh_params.py`'s own diff review), same
  posture `PHASE_4_SPEC.md` §7 G-S6 gave threshold-string honesty; §6c's `model_copy` test proves the
  VALUE is read correctly, not that a wrong value is impossible to configure (that remains a human
  review responsibility, by design — register #8 is explicitly `configurable: True`).
- **Rebalance cadence shortened below quarterly** — structurally impossible: `_REBALANCE_MONTHS` is a
  module-level constant with no parameter, CLI flag, or config-register path to override it anywhere
  under `mizan/backtest/` (§4.3, §9).

---

## §7 Failure-Mode Guards

Pulled from `ULTIMATE_PRD.md` §4.6 (Backtest engine) specifically, plus this phase's own new surface.

| # | Failure mode | Guard Phase 5's code implements | What the review agent checks |
|---|---|---|---|
| G-B1a | `CASH_YIELD != 0.0` at runtime | `mizan/cli/main.py`'s existing, unmodified `check_all()` runs before `backtest` dispatches, same as every other subcommand; `INVARIANTS` is frozen so no second check is needed mid-simulation | Run `mizan backtest ...` with a monkeypatched `INVARIANTS` violation, assert exit 1 with the boot-check message, zero DuckDB reads attempted |
| G-B1b | `Invariants.cash_yield` re-hardcoded as a bare `0.0` a second time somewhere under `mizan/backtest/`, drifting silently from `INVARIANTS` if the latter ever changed | `apply_cash_yield` (§4.1) imports and reads `mizan.config.invariants.INVARIANTS.cash_yield` directly, never accepts it as a parameter, never assigns a literal `0.0` to a variable that stands in for it | `grep -rn "cash_yield" mizan/backtest/` — the only read site is `apply_cash_yield`'s own `INVARIANTS.cash_yield` reference; `grep -rnE "cash_yield\s*=\s*0" mizan/backtest/` (a re-declaration) finds nothing |
| G-B2a | A strategy attempts to hold/select a Non-compliant ticker | `Strategy.select()`'s own signature scope (§4.2) makes this unnameable; `AllocationInstruction`'s validator (§3.2) forbids negative/over-1.0 weights independent of compliance; `rebalance()` validates the returned instruction's tickers against `compliant_tickers` before applying it | `EqualWeightStrategy` over a fixture universe containing a `NON_COMPLIANT` ticker never receives that ticker in `compliant_tickers` (assert by inspecting the argument `select()` was called with, via a spy); a deliberately-broken test `Strategy` that returns a hardcoded non-compliant ticker name raises `StrategyContractViolationError` |
| G-B2b | Negative position quantity (a short in disguise) | `Holding.quantity: float = Field(ge=0.0)` (§3.1) | `Holding(ticker="X", quantity=-1.0)` raises `pydantic.ValidationError` |
| G-B2c | Leverage (borrowed capital) via an over-allocated instruction | `AllocationInstruction`'s validator forbids `sum(target_weights.values()) > 1.0` (§3.2) | `AllocationInstruction(target_weights={"A": 0.6, "B": 0.6})` raises `pydantic.ValidationError` |
| G-B2d | Negative portfolio cash (an implicit margin loan) | `Portfolio.cash: float = Field(ge=0.0)` (§3.1) | `Portfolio(cash=-1.0, holdings={})` raises `pydantic.ValidationError` |
| G-B3 | Compliance-flip missed at a rebalance boundary (an opportunistic skip) | `rebalance()` re-screens every ticker in `universe` unconditionally, every rebalance, with no conditional/early-exit path (§6d) | Wrap `mizan.screening.verdict.screen` with a call-counting spy across a multi-rebalance fixture backtest; assert the call count equals `len(universe) * len(rebalance_dates)` exactly (or `>=`, accounting for Layer-1 fail-fast tickers that still count as one call) — no rebalance is silently skipped for any ticker |
| G-B4 | Grace-period misconfiguration silently ignored (hardcoded instead of read from config) | `compliance_state.transition` reads `fiqh_params.grace_period_rebalances.value` fresh on every flip, never a module-level cached int (§4.4, §6c) | The §6c `model_copy` test: changing `grace_period_rebalances.value` from `1` to `2` changes the resulting `divest_date` by exactly one rebalance period, proving the value is read, not hardcoded (§8 AC2) |
| G-B5 | `compliance_state.transition` or `strategy.py`'s models gain accidental network/DB capability | Neither module imports `duckdb`, `httpx`, or takes a `con`/`cache_dir`/`client` parameter (§4.4's own pure-function contract, mirroring Phase 4's `classify_business_activity`) | `grep -rn "duckdb\|httpx\|cache_dir" mizan/backtest/compliance_state.py mizan/backtest/strategy.py` — no hit |
| G-B6 | `screen()`'s temporal-non-interference confinement silently broken by a Phase 5 caller passing the wrong `as_of_date` | `rebalance()` (§4.3) always passes the CURRENT rebalance's own `as_of_date` to every `screen()` call — never a cached/stale date, never `date.today()` | `grep -rn "date.today\|datetime.now" mizan/backtest/` — no hit (§7 restates `ULTIMATE_PRD.md` §5 check 7's own "every `filed` reference sits inside a function taking `as_of_date`" discipline is unaffected — Phase 5 never itself queries `filed`, it only calls `screen()`, so the confinement stays entirely inside `mizan/screening/verdict.py`, unmoved) |
| G-DB4 | `backtest`/`mizan backtest` writes to DuckDB | `db.connect(..., read_only=True)` used by the CLI (§4.5); no `INSERT`/`CREATE`/`ALTER` anywhere under `mizan/backtest/` | `grep -rniE "INSERT INTO\|CREATE TABLE\|ALTER TABLE" mizan/backtest/` — no hit |
| G-VB1 | Rebalance cadence shortened below quarterly (`ULTIMATE_PRD.md` §1.1's values boundary) | `_REBALANCE_MONTHS` is the ONLY rebalance-date generator anywhere under `mizan/backtest/`; no CLI flag, function parameter, or `FiqhParams` register entry can change it (§4.3, §9) | `grep -rniE "\b(daily|intraday|hourly|minute|tick)[-_ ]?(rebalance|rebalancing|signal)\b" mizan/backtest/` — no hit (`ULTIMATE_PRD.md` §5 check 8, re-run over the new tree); `grep -rn "rebalance.frequency\|rebalance_frequency\|--rebalance" mizan/backtest/ mizan/cli/backtest.py` — no hit |
| G-LLM5 | LLM/model SDK reachback | Forbidden-dependency list unchanged (§2.4) | `ULTIMATE_PRD.md` §5 checks 5 and 6, re-run over the full `mizan/` tree including `mizan/backtest/`; `grep -rniE "openai\|anthropic\|gemini\|vertex\|langchain\|\bllm\b\|chat_completion\|completion\(" mizan/backtest/` — no hit |
| G-BOUND1 | Any of `short/borrow/margin/leverage/option/future/swap/derivative` naming anywhere under `mizan/backtest/` | None of these words appears anywhere in this phase's code, comments, or identifiers except inside a docstring EXPLAINING why the concept is forbidden | `grep -rniE "\b(short\|shorts\|shorting\|borrow\|borrowed\|borrowing\|margin\|leverage\|leveraged\|levered\|option\|options\|future\|futures\|swap\|swaps\|derivative\|derivatives)\b" mizan/backtest/` — every hit is inside a docstring/comment naming the forbidden concept explicitly, never inside executable logic that implements it (`ULTIMATE_PRD.md` §5 check 2) |
| G-AI | AI attribution in commit messages | Same neutral-commit convention as Phases 1–4 | `git log --format=%B` for this phase's commits — no `Co-Authored-By`, no "Generated with," no model/assistant name |

**Categorisation, mirroring Phases 1–4:** G-B1a, G-B1b, G-B2a, G-B2b, G-B2c, G-B2d, G-B3, G-B4, G-VB1,
G-LLM5, G-BOUND1, G-AI are **HALT-for-human** (permissibility-boundary or values-boundary touching,
`MASTER_PRD.md` §13's own categorization restated for this phase). G-B5, G-B6, G-DB4 are
blocking-but-mechanical.

---

## §8 Phase Acceptance Criteria

Each concrete, independently checkable by a third party, same standard Phases 1–4 applied, reusing
Phase 4's synthetic fixture set (§6e) plus this phase's one additive ticker.

1. **The flip → grace → divest sequence is exact.** A backtest run over `ZZFLIP01` (§6e) — a ticker
   whose fixture facts make it compliant at the first rebalance and `NON_COMPLIANT` at the second —
   shows the exact state sequence `HELD_COMPLIANT` (rebalance 1) → `HELD_NONCOMPLIANT_GRACE`
   (rebalance 2, `flip_date` = rebalance 2's date) → `DIVESTED` (rebalance 3, `divest_date` =
   rebalance 3's date, using the default `grace_period_rebalances.value == 1`) — not immediate at
   rebalance 2, not skipped at rebalance 3.
2. **Divestment timing is read from config, proven not hardcoded.** The same `ZZFLIP01` scenario
   re-run with `FIQH_PARAMS.grace_period_rebalances` `model_copy`'d to `value=2` divests exactly one
   rebalance later (rebalance 4) than the default-value run — a direct, testable proof the timing
   comes from `fiqh_params`, per §6c/§7 guard G-B4.
3. **`Holding`/`Portfolio` cannot be constructed with a negative quantity or negative cash.** A
   type/validation-level test (not a runtime-logic test): `Holding(ticker=..., quantity=-1.0)` and
   `Portfolio(cash=-1.0, holdings={})` both raise `pydantic.ValidationError` immediately.
4. **A strategy cannot select a Non-compliant ticker.** Tested both ways: (a) `EqualWeightStrategy`
   over a universe including a fixture ticker whose fresh verdict is `NON_COMPLIANT` never receives
   that ticker inside `compliant_tickers` (a spy on `select()`'s own call arguments confirms this);
   (b) a deliberately-broken test `Strategy` that manufactures a hardcoded non-compliant ticker name
   in its returned `AllocationInstruction` causes `rebalance()` to raise
   `StrategyContractViolationError`, not silently drop or ignore it.
5. **Portfolio cash never accrues yield.** Over a multi-day fixture window in which the portfolio
   holds idle cash and no trade or dividend occurs, `Portfolio.cash` is bit-for-bit identical (`==`
   on the `float`, since no arithmetic altering it ever runs) at the end of the window as at the
   start.
6. **Every holding is re-screened at every rebalance — no silent skip.** A call-counting spy on
   `mizan.screening.verdict.screen` across a multi-rebalance, multi-ticker fixture backtest confirms
   every ticker in `universe` is screened at every rebalance date, with no rebalance/ticker pair
   omitted.
7. **Leverage and shorting are structurally rejected, not merely unused.** `AllocationInstruction(
   target_weights={"ZZPURE01": 0.6, "ZZMIXED01": 0.6})` (sum `1.2 > 1.0`) and
   `AllocationInstruction(target_weights={"ZZPURE01": -0.1})` both raise `pydantic.ValidationError`.
8. **The rebalance cadence is exactly quarterly and cannot be changed.** `generate_rebalance_dates`
   over a multi-year window produces dates falling only on the four `_REBALANCE_MONTHS` boundaries
   (plus the initial `start_date`); no CLI flag, environment variable, or function parameter anywhere
   under `mizan/backtest/`/`mizan/cli/backtest.py` can alter `_REBALANCE_MONTHS` (§7 guard G-VB1's
   grep is clean).
9. **`INVARIANTS.cash_yield` is read, never re-hardcoded.** §7 guard G-B1b's grep is clean;
   `apply_cash_yield`'s own body reads `INVARIANTS.cash_yield` and nowhere else under `mizan/backtest/`
   assigns a bare `0.0` standing in for it.
10. **A completed divestment records the flip date and the divest date.** `DivestmentEvent.flip_date`
    and `.divest_date` are both populated (never `None`) on every entry in
    `BacktestResult.divestment_events`, and `flip_date <= divest_date` holds for every one.
11. **A dividend event records the verdict active at its ex-date.** `DividendEvent.
    verdict_at_ex_date` matches the most-recently-established `VerdictObservation` for that ticker as
    of the ex-date, across a fixture with at least one dividend paid between two rebalances.
12. **`purification_ledger` is always `None` after a Phase 5 run.** Confirmed on every
    `BacktestResult` this phase's own tests produce — Phase 5 computes no purification amount (§1,
    §9).
13. **No LLM/model-client SDK import, and no boundary-crossing primitive naming, anywhere in
    `mizan/backtest/`.** `ULTIMATE_PRD.md` §5 checks 1–8, clean over the expanded tree (§7 guards
    G-LLM5, G-BOUND1, G-VB1).
14. **`backtest` never writes to DuckDB.** `mizan backtest` opens its connection `read_only=True`;
    no `INSERT`/`CREATE`/`ALTER` anywhere under `mizan/backtest/` (§7 guard G-DB4).
15. **Every new Pydantic model inherits `MizanBaseModel`.** No file under `mizan/backtest/` or
    `mizan/cli/backtest.py` imports or subclasses `pydantic.BaseModel` directly.
16. **Boot gate runs first.** `mizan backtest ...` under a deliberately-violated `Invariants`/
    `FiqhParams` instance exits 1 with the boot-check failure message before any DuckDB read or
    simulation step runs (§7 guard G-B1a).
17. **`mypy --strict mizan tests` exits 0.** Built and verified inside the project's `.venv`, per
    `PHASE_3_SPEC.md` AC14's established requirement.
18. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5`.
19. **`pytest` passes in full**, all five new test files plus the extended
    `tests/fixtures/synthetic_universe.py` plus the full existing Phase 1–4 suite (no regression).
20. **No forbidden dependency anywhere; `pyproject.toml` is unmodified by this phase** (§2.1/§2.2).
21. **No premature imports.** `pandas`/`matplotlib` imported by no module under `mizan/`; `pyarrow`
    imported by no module under `mizan/backtest/`.
22. **`docs/modernization_log.md` carries a dated entry resolving §0.1/§2.5/§6a's `splitFactor`-
    direction verification item** before `apply_split`'s arithmetic is treated as settled.
23. **Commits are neutral.** No AI attribution in `git log` for this phase's commits.
24. **Boundary greps are clean**, re-run from repo root against the full tree including
    `mizan/backtest/*.py` and `mizan/cli/backtest.py` (`ULTIMATE_PRD.md` §5 checks 1–8).

**Any single failing criterion is a phase-loop HALT, not a partial pass** — same standard Phases 1–4
state, applied here.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 5)

- **No purification computation.** `BacktestResult.purification_ledger` is always `None` after a
  Phase 5 run (§3.4, §8 AC12) — Phase 5 records only the flip/divest event data and the per-dividend
  event data (`DivestmentEvent`, `DividendEvent`, §3.3) that Phase 6's `mizan/backtest/purification.py`
  will need; it computes no `non_compliant_income_ratio × dividend_amount` figure, implements none of
  Fork A/B/C (register #9/#10/#11), and defines no side-ledger.
- **No reporting, no HTML output, no `matplotlib` import.** → Phase 7. `mizan backtest`'s own CLI
  output (§4.5) is a plain stdout summary for operator sanity-checking, not a generated report.
- **No real backtest run against real market data.** The real ~100-ticker curated universe still does
  not exist (`COMPREHENSION.md` §6's own carried-forward open item, unchanged by Phase 4 or this
  phase). Phase 5's acceptance criteria (§8) run only against Phase 4's synthetic fixture set plus
  this phase's one additive `ZZFLIP01` ticker (§6e) — never against a named real company, exactly
  the same honesty posture `PHASE_4_SPEC.md` §9's first, most prominent non-goal established.
- **No sub-quarterly, daily, or intraday rebalancing capability, of any kind, under any name.**
  `ULTIMATE_PRD.md` §1.1's values boundary is restated here as a permanent, structural fact of this
  phase's own code, not merely a documentation note: `_REBALANCE_MONTHS` (§4.3) is the sole
  rebalance-date generator anywhere under `mizan/backtest/`, there is no CLI flag, environment
  variable, or `FiqhParams` register entry that can shorten it, and this phase deliberately does
  **not** introduce a configurable rebalance-frequency parameter of any shape — not even one gated
  behind a "loud override" flag. The simpler, safer choice (omit the knob entirely) was taken over the
  alternative the outer dispatch also permitted (a flag with a quarterly floor requiring an explicit
  opt-in), because Phase 5 has no genuine V1 use case for a faster cadence to opt into, and adding the
  flag's own plumbing would be surface area serving a capability this project's own confirmed values
  position (`ULTIMATE_PRD.md` §1.1) has not authorized building at all. A future phase wanting such a
  flag is a new, explicitly-escalated, human-approved scope decision — not something this spec
  pre-wires.
- **No short-selling, derivatives, margin, or leverage — restated because this phase is the second
  place (after screening) the outer dispatch names as highest-risk for the permissibility boundary.**
  `Holding.quantity`/`Portfolio.cash`'s `Field(ge=0.0)` constraints and `AllocationInstruction`'s
  `sum(target_weights) <= 1.0` validator (§3.1, §3.2) make all four structurally unconstructable, not
  merely unused by this phase's own reference strategy.
- **No pluggable strategy-loading mechanism (entry points, dynamic imports, a strategy registry).**
  `Strategy` (§3.2) is a `typing.Protocol` any Python callable object satisfying its shape can
  implement; `mizan backtest`'s own CLI (§4.5) wires in exactly one reference implementation,
  `EqualWeightStrategy`. A real plugin-loading system, if ever wanted, is future work over this
  substrate — the same posture Phase 4 §9 gave the real business-activity override map.
- **No change to `mizan/screening/`, `mizan/data/`, or any Phase 1–4 public symbol.** Phase 5 imports
  and calls `screen()`, `resolve_cik_offline` (indirectly, via `screen()`), `db.connect`,
  `load_override_map`, and the Phase 1 config/core singletons — it reshapes none of them (§0).
- **No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3).** Unchanged from Phases 1–4 —
  these remain escalated to the human and are unrelated to the backtest engine.
- **No LLM, ever, in any phase.** Restated per Phases 1–4's own restatement convention — a "strategy"
  module is exactly the kind of place a build agent might reach for "an LLM to decide which stock
  looks promising." That instinct is wrong here specifically: `Strategy.select()` must remain a
  deterministic function of `(as_of_date, compliant_tickers, portfolio)`, full stop (§7 guard G-LLM5).

---
