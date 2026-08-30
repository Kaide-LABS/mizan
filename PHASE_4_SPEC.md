# PHASE_4_SPEC.md — Mizan: Screening Engine

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), the same document `PHASE_1_SPEC.md`, `PHASE_2_SPEC.md` and `PHASE_3_SPEC.md`
> were built from. Every schema decision, every function signature, and every guard below traces to
> a section of that document, cited inline, cross-checked against `MASTER_PRD.md` where
> `ULTIMATE_PRD.md` is silent, against `docs/modernization_log.md` for pinned external reality, and
> against the committed Phase 1 code (`mizan/config/`, `mizan/core/`), Phase 2 code (`mizan/data/`
> ingestion, `mizan/cli/ingest.py`) and Phase 3 code (`mizan/data/db.py`, `mizan/data/normalize.py`,
> `mizan/cli/normalize.py`) for integration fidelity.

**Generated:** 2026-08-30 · **Dispatch type:** phase advancement (Phase 3 review-approved,
comprehension pass complete; no code review or fix loop runs in this dispatch — this document is
the deliverable) · **Canonical references:** `ULTIMATE_PRD.md` (governs), `MASTER_PRD.md` (governs
where `ULTIMATE_PRD.md` is silent, principally §6 Screening Engine and §10 the fiqh register),
`docs/modernization_log.md` (pinned external reality), `COMPREHENSION.md` (what Phases 1–3 actually
shipped, including the open item that nothing yet reads Phase 3's tables — §6 below is where that
closes), `PHASE_1_SPEC.md` (the `Verdict` enum, `Caveat`/`ResultEnvelope`, the fiqh register — all
Phase 4 **consumes**, none of which it may redefine), `PHASE_2_SPEC.md` + `PHASE_3_SPEC.md` (format
and rigor precedent, and the public surface — `mizan.data.db`, `mizan.data.normalize`,
`mizan.data.raw_cache`, `mizan.data.ingest_edgar.CikResolutionError`, `mizan.cli.main` — Phase 4
must consume without reshaping).

**A scoping decision that is the project owner's, not this document's, and is not relitigated
here:** `MASTER_PRD.md` §6.1 names "SIC first-pass + a hand-verified activity map" over a curated
~100-ticker universe as the honest V1 implementation. That curated universe and its hand-verified
map do not exist anywhere in this repository. The owner has decided Phase 4 builds a fully
**generic, configurable** screening engine — a SIC-code first-pass classifier plus a pluggable
activity-override mechanism in the shape that map would eventually be supplied through — verified
in this phase only against a small, explicitly synthetic fixture universe (~10–15 invented tickers,
labeled as such). The real curated universe is out of scope for this automated build; see §9's first
and most prominent entry. This document does not fabricate a large-scale "hand-verified" ticker
classification anywhere — doing so would be dishonest and would defeat the correctness backstop the
real map exists to provide (`MASTER_PRD.md` §0, §13).

**No citation re-verification gate applies to this document's arXiv citations**, unchanged from
`PHASE_2_SPEC.md`/`PHASE_3_SPEC.md`'s own confirmation — Mizan's arXiv citations remain background
corroboration, not phase-anchoring technical claims. This file carries no §0.5. **A different,
narrower verification obligation is new in this phase and is called out explicitly in §2.2 and §6**:
the specific XBRL concept tags (`us-gaap:Assets`, debt/investment/income tag candidates, etc.)
Phase 4's financial-ratio screen reads are asserted here as **candidates grounded in standard SEC
XBRL/US-GAAP taxonomy usage, not yet independently re-verified live against a real companyfacts
response the way `docs/modernization_log.md` §6.1 verified the fact-object shape** — the build agent
must perform that verification (against the synthetic fixtures' companyfacts shape at minimum, and
ideally one real cached CIK) and log it in `docs/modernization_log.md`, per this project's standing
"verify, don't recall" discipline (`docs/modernization_log.md` §0/§1).

---

## §0 Phase Plan Header

# **Phase 4 of 7: Screening Engine**

Phase sequence, unchanged from `PHASE_3_SPEC.md` §0 / `ULTIMATE_PRD.md` §6 (re-derived there, not
re-derived again here):

| # | Phase | Ships |
|---|---|---|
| 1 | Foundation & Config (done, approved) | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| 2 | Ingestion & raw cache (done, approved) | EDGAR (`companyfacts` + `companyconcept` + `submissions`) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store (done, approved) | `data/normalize.py`, `data/db.py`, typed `fundamentals_facts`/`price_bars` tables, uniqueness constraints, unit-scale handling |
| **4** | **Screening engine** ← *this document* | `screening/business_activity.py` (SIC first-pass + pluggable override map, tiered), `screening/financial_ratios.py` (30/30/5, two-axis denominator from config), `screening/verdict.py` (combines both into a three-state `Verdict` + reason trace — the `screen()` entry point), temporal-non-interference discipline, `mizan/cli/screen.py` |
| 5 | Backtest engine + compliance-flip state machine | daily clock, portfolio, strategy interface, flip→grace→divest |
| 6 | Purification | side-ledger, `divCash`-driven, Forks A/B/C from config |
| 7 | Reporting | static HTML + matplotlib, caveats non-optional, gross vs net-of-purification |

This spec covers **Phase 4 only**. It is the contract the Phase 4 execution agent builds against and
the Phase 4 review agent (next round of Step 12) verifies against. Phase 4 **consumes** Phase 1's
public surface (`mizan.config.fiqh_params.FIQH_PARAMS`, `mizan.config.invariants.INVARIANTS`,
`mizan.core.base.MizanBaseModel`, `mizan.core.verdict.Verdict`, `mizan.core.caveats.Caveat` /
`ResultEnvelope`, `mizan.config.boot_check.check_all`), Phase 2's public surface
(`mizan.data.raw_cache.*`, `mizan.data.ingest_edgar.CikResolutionError`), and Phase 3's public
surface (`mizan.data.db.connect`, `mizan.data.normalize.resolve_cik_offline`,
`mizan.cli.main.build_parser`) and **must not reshape any of them**. Phase 4 may only extend that
surface additively. Every new symbol Phase 4 introduces (`mizan.screening.*`, `mizan.cli.screen`) is
itself now locked for Phases 5–7 the same way.

**On the two `verdict.py` files, named explicitly so a future reader is never confused:**
`mizan/core/verdict.py` (Phase 1, unmodified) defines only the three-state `Verdict` **enum** — no
scoring logic, per its own Phase 1 docstring ("Enum definition only... all Phase 4"). `mizan/screening/verdict.py`
(new, this phase) is a **different, larger module**: it is where `screen(ticker, as_of_date)` itself
lives, where the two screening layers are combined, and where the reason trace is assembled. Every
docstring and import in the new module names `mizan.core.verdict.Verdict` by its full path
(`from mizan.core.verdict import Verdict`) rather than a bare `Verdict`, specifically so a `grep -n
"Verdict"` distinguishes "the enum" from "the module that produces it."

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`.** Same flat layout `PHASE_1_SPEC.md`–`PHASE_3_SPEC.md` §1
preserved — no nesting directory. Every file below is new except `mizan/cli/main.py`, which Phase 4
**modifies** (one line, same convention as Phase 3's own one-line `normalize` registration).

```
C:\Users\hp\HMS\
├── mizan/
│   ├── screening/
│   │   ├── __init__.py                  # NEW — empty, package marker only (mizan/data/__init__.py precedent)
│   │   ├── business_activity.py         # NEW — SIC first-pass classifier + pluggable override map (§3, §4, §6a)
│   │   ├── financial_ratios.py          # NEW — 30/30/5 computation, two-axis denominator (§3, §4, §6b)
│   │   └── verdict.py                   # NEW — screen() entry point; combines both layers into Verdict + reason
│   │                                     #        trace (§3, §4, §6c/§6d) — DISTINCT from mizan/core/verdict.py,
│   │                                     #        see §0's naming note
│   └── cli/
│       ├── main.py                      # MODIFIED — registers the `screen` subparser (one line, §1 precedent)
│       └── screen.py                    # NEW — the `screen` subcommand (§4.4)
└── tests/
    ├── fixtures/
    │   ├── __init__.py                  # NEW — package marker
    │   └── synthetic_universe.py        # NEW — ~12 SYNTHETIC, clearly-labeled fixture tickers (§6e, §8)
    ├── test_screening_business_activity.py  # NEW
    ├── test_screening_financial_ratios.py   # NEW
    ├── test_screening_verdict.py             # NEW
    └── test_cli_screen.py                    # NEW
```

**Files explicitly NOT created in Phase 4:** `mizan/backtest/`, `mizan/reporting/`, no
`backtest`/`report` subcommands under `mizan/cli/`, and **no curated real-ticker universe file of
any kind** (e.g. no `mizan/config/universe.py`, no `data/universe_100.json` — see the Provenance
header above and §9's first entry). These are named in `MASTER_PRD.md` §9.4 and `ULTIMATE_PRD.md`
§6 for Phases 5/7 and for the owner's own future, separate, human-verified work respectively.

**Confirmed: this phase does not touch `mizan/backtest/` or `mizan/reporting/`** — neither directory
exists yet, and no file Phase 4 adds imports from a path under either (nothing to import from). It
also does not modify `mizan/data/normalize.py` or `mizan/data/db.py` (§5) — Phase 4 is a read-only
consumer of the tables those modules already built.

**Why `mizan/screening/business_activity.py` also contains a small offline SIC-resolution helper,
flagged as a considered divergence from the outer dispatch's own framing rather than silently
complied with:** the dispatch's context-ingestion instructions describe Phase 4 as reading "the
normalized fundamentals-facts and price-bars tables Phase 3 built... not raw cache files directly."
That is correct for every *financial* fact the ratio screen needs (§6b) — those all live in
`fundamentals_facts`/`price_bars`. It is **not correct for SIC**: `ULTIMATE_PRD.md` §2 (System Map)
and its correction log are explicit that SIC lives *only* in `https://data.sec.gov/submissions/…`,
cached by Phase 2 as `edgar/submissions/{cik}.json` (`mizan/data/ingest_edgar.py`'s
`ingest_edgar_submissions`, verified live 2026-08-30 per `docs/modernization_log.md` §6.1). **Phase 3
never normalized that file into DuckDB — `fundamentals_facts` and `price_bars` are the only two
tables Phase 3 built (`mizan/data/db.py`), and neither has a SIC column.** Reading SIC therefore
means one of two things: (a) Phase 4 adds a third DuckDB table for issuer metadata, which §5 below
forecloses (Phase 4 adds no migrations, writes nothing new to DuckDB — a `PHASE_3_SPEC.md`-style
schema change is out of this phase's scope and would need its own spec revision), or (b) Phase 4
reads the already-cached `edgar/submissions/{cik}.json` raw file directly, exactly the same
offline-only pattern Phase 3's own `resolve_cik_offline` already established for
`company_tickers.json` (`PHASE_3_SPEC.md` §4.2 — "no network capability... `NotIngestedError`" if
absent"). **(b) is what this document specifies.** SIC/issuer metadata is static reference data, the
same *kind* of thing CIK resolution already is — not a normalized, point-in-time, `filed`-tagged
fundamentals fact — so this is not a re-reading of Phase 3's actual scope, it is applying Phase 3's
own established precedent to a data source Phase 3 correctly left untouched. `resolve_sic_offline`
(§4.1) never references `filed` at all (`EdgarSubmissionRecord` has no `filed` field), so it has no
interaction with §6d's temporal-non-interference discipline.

---

## §2 Dependencies

### 2.1 No new dependency

**Decision: Phase 4 adds zero new third-party dependencies.** `ULTIMATE_PRD.md` §2.1's dependency
table already accounts for everything Phase 4 needs: `pydantic` (schemas), `duckdb` (reading
`fundamentals_facts`/`price_bars`, already promoted to a core dependency in Phase 3). Phase 4 is pure
computation over already-normalized data plus already-loaded config — there is no new I/O surface,
no new file format, no new numerical library need (ratio arithmetic is plain Python floats; no
`numpy`/`scipy` is introduced for three division operations). `pyarrow` is **not** imported by any
Phase 4 module — Phase 4 only ever `SELECT`s rows back out of DuckDB via `con.execute(...).fetchone()`/
`.fetchall()`, it never bulk-loads (that is Phase 3's `_bulk_load`, unmodified and unreused here in
the write direction). `pandas`/`matplotlib` remain forward-declared and unused, unchanged from
`PHASE_3_SPEC.md` §2.2 — nothing in Phase 4's ratio math benefits from a DataFrame either.

### 2.2 A verification obligation, not a dependency: XBRL concept tags

Not a new package, but a new external-fact commitment this phase's code makes, so it gets its own
subsection per this project's "verify, don't recall" discipline (`docs/modernization_log.md` §0/§1,
`PHASE_3_SPEC.md` §2.1's live-recheck precedent). `mizan/screening/financial_ratios.py` (§3, §6b)
introduces four **closed, named, sourced allow-lists** of `us-gaap`/`dei` tag strings — the concrete
numerator/denominator concepts the 30/30/5 ratios read out of `fundamentals_facts`. Unlike
`RECOGNIZED_XBRL_UNITS` (`mizan/data/normalize.py`, Phase 3), which rejects on a miss, these are
allow-lists over which tags are *summed as available* (§6b) — a genuinely different, and genuinely
company-specific, kind of uncertainty than a unit-scale mismatch. The candidate tags named in §3/§6b
below (`us-gaap:Assets`, `dei:EntityCommonStockSharesOutstanding`, `us-gaap:LongTermDebtNoncurrent`,
etc.) are standard, widely-used US-GAAP/XBRL concepts, consistent with `docs/modernization_log.md`
§6.1's already-verified companyfacts shape and its own confirmed presence of
`EntityCommonStockSharesOutstanding` under `dei` — **but they have not been independently re-verified
live against a real companyfacts response the way §6.1's fact-object shape was.** The build agent
must run at least one live (or already-cached, if a real backfill exists) companyfacts fetch,
confirm each tag this phase actually reads is present with the expected shape (`units.USD` or
`units.shares`, instantaneous vs duration as declared), and log the result — including any tag this
pass could not confirm — in `docs/modernization_log.md` §6 with today's date, before treating the
allow-lists as settled. This is a mechanical, blocking-but-not-judgment-call action item, the same
category `PHASE_3_SPEC.md` §7 gave G-DEP3/§5's DuckDB PK-behavior check.

### 2.3 Forbidden-dependency list unchanged, and load-bearing for this phase specifically

`PHASE_1_SPEC.md` §2.5's permanently forbidden list (`openai`, `anthropic`, every other LLM/model
SDK, `yfinance`) still applies, unmodified. **This phase is where that boundary is most at risk**
(§6's own restatement, `MASTER_PRD.md` §2/§13, `ULTIMATE_PRD.md` §4.4/§5): a business-activity
classifier is exactly the kind of function a build agent might reach for an LLM to "help" with (e.g.
"summarize this 10-K's business description to guess its industry"). No such call, import, or name
may appear anywhere under `mizan/screening/`. See §7 G-LLM4 for the specific grep.

### 2.4 Modernization-log reconciliation

Same discipline as Phases 1–3: any tag confirmed or corrected per §2.2 is logged in
`docs/modernization_log.md` with a dated entry and, where applicable, a source citation — a
company's own XBRL filing is itself the primary source for "this tag exists and has this shape,"
which is a different (and in this case more directly checkable) kind of citation than a PyPI page or
a vendor doc, and should be cited as such (CIK + accession number of whichever real or fixture
filing was inspected).

---

## §3 Pydantic Schemas

Every new model inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no Phase 4 module subclasses `pydantic.BaseModel` directly, same guard as
every prior phase.

### 3.1 The reason trace (`mizan/screening/verdict.py`)

```python
from enum import StrEnum
from mizan.core.base import MizanBaseModel


class ScreenName(StrEnum):
    """Which of the four screens produced one ReasonTraceEntry. Four, not three, because the
    financial-ratio screen's three checks (MASTER_PRD.md §6.2) are individually distinguishable —
    "which ratio" (the outer dispatch's own §3 requirement) means each ratio gets its own trace
    entry, not one combined "financial_ratios" entry hiding which of the three actually failed."""

    BUSINESS_ACTIVITY = "business_activity"
    DEBT_RATIO = "debt_ratio"
    INTEREST_INVESTMENTS_RATIO = "interest_investments_ratio"
    NON_PERMISSIBLE_INCOME_RATIO = "non_permissible_income_ratio"


class ReasonTraceEntry(MizanBaseModel):
    """One inspectable line of MASTER_PRD.md §6.3's "reason trace... which screen, which ratio, what
    value vs. threshold." Every screen actually EXECUTED produces exactly one entry — including a
    PASSING one; this is what "any pass/fail is inspectable" (not just failures) means in code.

    `threshold`/`actual_value`/`margin` are all `None` for a `BUSINESS_ACTIVITY` entry (a tier match
    is categorical, not a threshold comparison) and all non-`None` for the three ratio entries.
    `margin` is `threshold - actual_value` for a passing ratio check (positive = comfortable margin)
    or `actual_value - threshold` for a failing one (positive = how far over) — surfaced per
    ULTIMATE_PRD.md §3.1's "Applied (see §6, Phase 4)" instruction, following arXiv:2608.12634's
    finding that distance-to-threshold predicts next-period compliance transitions: the ratio
    functions already compute this value to decide pass/fail, so it is retained rather than
    discarded, with zero effect on the verdict itself.
    """

    screen: ScreenName
    passed: bool
    threshold: float | None
    actual_value: float | None
    margin: float | None
    detail: str  # human-readable: which tier/SIC/override, or which XBRL-derived figures, drove this


class ScreeningVerdict(MizanBaseModel):
    """The purpose-built, fully-typed per-ticker screening result. See §3.3 for why this exists
    alongside `ResultEnvelope` rather than instead of it."""

    ticker: str
    cik: str
    as_of_date: _Date
    verdict: Verdict  # mizan.core.verdict.Verdict — imported by full path, see §0
    reason_trace: tuple[ReasonTraceEntry, ...]
```

### 3.2 Business-activity classification and the override-map schema (`mizan/screening/business_activity.py`)

```python
class BusinessActivityTier(StrEnum):
    """MASTER_PRD.md §6.1's three tiers. Values are the tier NAME, not a numeric level — a build
    agent must never compare these with `<`/`>` (there is no ordering; Tier 0.5 is not "between" 0
    and 1 in a numeric sense, it is a distinct AAOIFI-catch-all-derived category, MASTER_PRD.md
    §6.1's own table)."""

    TIER_0 = "tier_0"
    TIER_0_5 = "tier_0_5"
    TIER_1 = "tier_1"


class ClassificationSource(StrEnum):
    """Where a BusinessActivityScreenResult's tier match (or non-match) came from — surfaced in the
    reason trace so a reviewer can immediately tell "the SIC first-pass caught this" apart from "a
    human-supplied override caught this," per the outer dispatch's own emphasis that the override
    mechanism's precedence over SIC must be TESTABLE, not just present."""

    SIC_FIRST_PASS = "sic_first_pass"
    OVERRIDE_MAP = "override_map"


class ActivityOverride(MizanBaseModel):
    """One entry of the pluggable override map — the shape the owner's real, hand-verified ~100-
    ticker activity map (MASTER_PRD.md §6.1, explicitly OUT OF SCOPE for this build, §9) will
    eventually be supplied through. `rationale` is mandatory and non-empty by construction
    (`Field(min_length=1)`) — a bare tier label with no stated reason would be exactly the kind of
    silent judgment call MASTER_PRD.md §0 names as the worst failure mode, and a real hand-verified
    map's whole value IS its stated reasoning, not just its conclusion.

    `tier_override: None` is itself a meaningful, distinct value — "explicitly researched and found
    COMPLIANT despite what the SIC first-pass alone would suggest" (see synthetic ticker
    ZZOVERRIDE_RESCUE01, §6e) — never confused with "no override exists for this CIK at all" (which
    is simply the absence of a key in `BusinessActivityOverrideMap.overrides`).
    """

    cik: str  # zero-padded 10-digit, matching fundamentals_facts.cik and every other Phase 3 key
    ticker: str  # for human readability / audit cross-check only — lookup keys on cik, never ticker
    tier_override: BusinessActivityTier | None
    rationale: str = Field(min_length=1)


class BusinessActivityOverrideMap(MizanBaseModel):
    """The full pluggable override map, keyed by zero-padded CIK. Ships, by default, EMPTY —
    `BusinessActivityOverrideMap(overrides={})` — meaning "no per-ticker research has been supplied
    yet; fall back to the generic SIC first-pass for everything." This is the honest V1 state per the
    Provenance header above: an empty map is not a placeholder bug, it is the correct default for a
    map the owner has not yet populated. `load_override_map` (§4.1) is how an operator supplies a
    populated one later, without any code change to this module.
    """

    overrides: dict[str, ActivityOverride]


class BusinessActivityScreenResult(MizanBaseModel):
    passed: bool
    failed_tier: BusinessActivityTier | None
    source: ClassificationSource
    matched_sic: str
    reason: ReasonTraceEntry
```

**No 12th fiqh-register entry.** The `SIC_TIER_MAP` (§4.1) and the four XBRL tag allow-lists (§2.2)
are engineering data-mapping constants, not fiqh judgment calls — they answer "which SIC codes/XBRL
concepts correspond to which named category," not "which threshold or toggle does AAOIFI leave
underdetermined." Same posture Phase 3 held for `RECOGNIZED_XBRL_UNITS` (`PHASE_3_SPEC.md` §3).
**One exception, flagged rather than silently folded in:** the choice of *which* XBRL tags count as
"non-permissible income" (§6b) is itself a genuine, non-trivial proxy decision — most issuers never
file a line item literally labeled "non-halal income." §6b names this explicitly as a documented,
sourced, `NON_PERMISSIBLE_INCOME_TAGS`-named constant carrying the same "not settled, here is
exactly what it stands in for" honesty treatment the fiqh register gives its own entries, without
itself being promoted into the register (it is a data-mapping proxy for register #5's numerator, not
a new judgment call about a threshold or a toggle — register #5 itself is untouched, still 5%, still
`total_income`-vs-`total_revenue`-flagged per its existing `primary_source_gap`).

### 3.3 Financial-ratio result schema (`mizan/screening/financial_ratios.py`)

```python
class FinancialRatioScreenResult(MizanBaseModel):
    passed: bool  # True iff all three of the below pass
    debt_ratio: ReasonTraceEntry
    interest_investments_ratio: ReasonTraceEntry
    non_permissible_income_ratio: ReasonTraceEntry
```

### 3.4 Why `ScreeningVerdict` is a purpose-built model wrapped INSIDE `ResultEnvelope`, not a
replacement for it

`mizan/core/caveats.py`'s own Phase 1 docstring is explicit and names this exact case: "Every
backtest/**screening** result that reaches a human MUST be wrapped in this envelope." That decision
was already made in Phase 1; Phase 4 is where it is first actually exercised, not re-litigated.
`ResultEnvelope.payload` is `dict[str, object]` — a deliberately loose, least-common-denominator
shape shared across screening (this phase), backtest (Phase 5), and reporting (Phase 7) results,
which do not share a schema. Wrapping a fully-typed `ScreeningVerdict` inside that loose `payload`
would look like a loss of type safety, but is not: `screen()` (§4.3) returns
`ResultEnvelope(active_caveats=(...), payload=screening_verdict.model_dump())`, and any caller
needing the typed shape back reconstructs it via `ScreeningVerdict.model_validate(envelope.payload)`
— a lossless, `extra="forbid"`-checked round trip. This satisfies `ULTIMATE_PRD.md` §2.1's "every
result carries its caveats structurally" (the caveats live on the envelope, not buried in
`ScreeningVerdict` itself, so `ScreeningVerdict` alone is never mistaken for a "safe to render"
result) while still giving every Phase 4 internal function (and every test) a fully-typed value to
work with before that final wrapping step. **Which caveats does `screen()` stamp, always:**
`Caveat.LOOK_AHEAD_BIAS` (§6d's declared Fork-1 simplification lives here) and
`Caveat.PENDING_SCHOLARLY_VERIFICATION` (every one of `FIQH_PARAMS`' 11 entries carries that status
today, unconditionally true of every Phase 4 run). **Not stamped by `screen()`:**
`Caveat.SURVIVORSHIP_BIAS` — that caveat is about the *universe selection* ("companies that exist
today," `mizan/core/caveats.py`'s own docstring), a Phase 5 backtest-level concern about which
tickers are even considered, not something a single `screen(ticker, as_of_date)` call can meaningfully
assert about itself.

---

## §4 Public Interfaces / Function Signatures

### 4.1 `mizan/screening/business_activity.py`

```python
#: The SIC-code first-pass table: a CLOSED, GENERIC, publicly-sourced mapping from 4-digit SIC codes
#: to BusinessActivityTier, grounded in MASTER_PRD.md §6.1's tier definitions and SEC's own published
#: SIC code list (https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany — the SIC list itself,
#: NOT a per-ticker classification; verify live at build time and log in docs/modernization_log.md,
#: §2.2). This is emphatically NOT the owner's curated ~100-ticker hand-verified activity map (§9) —
#: it is the same *kind* of thing RECOGNIZED_XBRL_UNITS is: a small, closed, reviewable constant, not
#: per-ticker research. Illustrative entries (exact codes verified at build time):
#:   Tier 0:   6020-6036 (commercial/savings banks), 6311-6411 (insurance), 2080-2085 (beverages,
#:             i.e. alcohol), 7993 (gambling), 2000-2013 (meat/non-halal-food-adjacent), 2100-2199
#:             (tobacco)
#:   Tier 0.5: 2741/2750-class adult-publishing codes, 3480/3760 (ordnance/guided-missile — weapons)
#:   Tier 1:   7812/7822 (motion picture), 7011 (hotels)
SIC_TIER_MAP: dict[str, BusinessActivityTier] = {...}


class SicResolutionError(RuntimeError):
    """Raised when `resolve_sic_offline` cannot find a cached submissions record for `cik`, or the
    cached record has no usable `sic` key — mirrors `MissingSicError`'s Phase 2 rationale
    (ULTIMATE_PRD.md §4.1: "a ticker with fundamentals but no SIC must be `unanalyzed`") applied to
    the offline read path, exactly as `mizan.data.normalize.resolve_cik_offline` mirrors
    `CikResolutionError` for the analogous company_tickers.json lookup."""


def resolve_sic_offline(cik: str, *, cache_dir: Path) -> str:
    """Read the already-cached `edgar/submissions/{cik}.json` raw file (PHASE_2_SPEC.md §6.1's
    `ingest_edgar_submissions` cache key) and return its `sic` field. No network parameter exists on
    this function — zero network capability, structurally (§7 G-S8, mirroring PHASE_3_SPEC.md's
    G-N8). Does not reference `filed` — SIC has no temporal dimension in this cache (§1's own note);
    this function is exempt from §6d's as_of_date discipline for that reason, not by oversight.
    """


def load_override_map(path: Path | None) -> BusinessActivityOverrideMap:
    """`path is None` returns `BusinessActivityOverrideMap(overrides={})` — the honest empty default
    (§3.2) — with NO file read at all. A given `path` is read and `model_validate`d as JSON; a
    malformed file (bad JSON, or JSON that fails `extra="forbid"`/type validation) raises
    `pydantic.ValidationError` — never partially loaded, never silently ignored.
    """


def classify_business_activity(
    cik: str, sic: str, *, overrides: BusinessActivityOverrideMap, fiqh_params: FiqhParams = FIQH_PARAMS,
) -> BusinessActivityScreenResult:
    """Pure function — no DB, no cache, no dates, no network. Precedence, testable (§7, §8):
      1. If `cik` is a key in `overrides.overrides`: the override WINS outright, regardless of what
         SIC alone would say. `tier_override=None` means "researched, compliant despite SIC" (passed
         True); a set tier means "researched, non-compliant at that tier" (passed False,
         `source=OVERRIDE_MAP`).
      2. Otherwise, look up `sic` in `SIC_TIER_MAP`. A Tier 0 match always fails. A Tier 0.5 match
         fails ONLY if `fiqh_params.business_activity_tier_0_5_enabled.value is True` (default True);
         a Tier 1 match fails ONLY if `fiqh_params.business_activity_tier_1_enabled.value is True`
         (default False) — read from config on every call, never a module-level cached bool (§7 G-S6,
         MASTER_PRD.md §6.1/§10 register #6/#7). No SIC match, or a disabled-tier match, passes.
      3. Either way, `source` on the result names which branch fired, and `reason.detail` names the
         matched SIC/tier or the override's own `rationale` string verbatim, so a human reviewer sees
         a real-map entry's stated reasoning in the output, not just its conclusion.
    """
```

### 4.2 `mizan/screening/financial_ratios.py`

```python
#: Candidate XBRL tags for each ratio's numerator, closed allow-lists, §2.2's verification item.
#: A numerator absent from a company's companyfacts (no matching tag reported at all) is treated as
#: 0.0, not an error — many genuinely debt-free / interest-free firms simply never file these tags
#: (§6b). This is the opposite posture from RECOGNIZED_XBRL_UNITS (Phase 3), which REJECTS a miss —
#: here a miss on the numerator side is a legitimate "this company has none of this," while a miss on
#: the DENOMINATOR side (below) is not, and is handled differently (§6b, InsufficientDataError).
INTEREST_BEARING_DEBT_TAGS: frozenset[str] = frozenset({
    "LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings", "DebtCurrent",
})
INTEREST_BEARING_INVESTMENT_TAGS: frozenset[str] = frozenset({
    "ShortTermInvestments", "LongTermInvestments", "MarketableSecuritiesCurrent",
})
NON_PERMISSIBLE_INCOME_TAGS: frozenset[str] = frozenset({
    "InvestmentIncomeInterest", "InterestIncomeOther", "InterestAndDividendIncomeOperating",
})
#: Register #5's own primary_source_gap ("Phase 4 must pick one explicitly and cite this gap",
#: mizan/config/fiqh_params.py) — Phase 4 picks the "total revenue" reading (MASTER_PRD.md §6.2's own
#: wording), NOT the "Total Income" reading the AAOIFI primary source literally uses (verified
#: verbatim, docs/modernization_log.md §7). This does NOT resolve ULTIMATE_PRD.md Q2 — that remains
#: escalated (§9) — it is Phase 4 making a concrete, transparent, cited choice so the code can run.
TOTAL_REVENUE_TAGS: frozenset[str] = frozenset({
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
})


def compute_debt_ratio(
    interest_bearing_debt: float, denominator: float, *, fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ReasonTraceEntry:
    """Pure arithmetic: `interest_bearing_debt / denominator`, compared against
    `fiqh_params.debt_ratio_threshold.value` using `<=` ("should not EXCEED", AAOIFI's own verbatim
    wording, docs/modernization_log.md §7 — a value AT the threshold passes; see §6b's note
    reconciling this against MASTER_PRD.md §6.2's own "< 30%" phrasing, which is the less precise of
    the two). `denominator` is ALREADY the resolved, config-selected two-axis value (§6b) — this
    function does not know or care whether it is market-cap or total-assets, spot or averaged; that
    resolution happens once, upstream, in `mizan/screening/verdict.py`.
    """


def compute_interest_investments_ratio(
    interest_bearing_investments: float, denominator: float, *, fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ReasonTraceEntry: ...  # identical shape, against fiqh_params.interest_investments_threshold


def compute_non_permissible_income_ratio(
    non_permissible_income: float, total_revenue: float, *, fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ReasonTraceEntry: ...  # against fiqh_params.non_permissible_income_threshold; denominator is
                            # ALWAYS total_revenue (never the two-axis market-cap/assets choice —
                            # §6.2's denominator config applies only to ratios 1 and 2)


def compute_financial_ratio_screen(
    *, interest_bearing_debt: float, interest_bearing_investments: float,
    non_permissible_income: float, total_revenue: float, denominator: float,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> FinancialRatioScreenResult:
    """Runs all three checks above and combines them — `passed` iff all three pass. Every field is a
    plain float already resolved by the caller; no DB access, no dates, anywhere in this module.
    """
```

### 4.3 `mizan/screening/verdict.py` — the canonical entry point

```python
class NotNormalizedError(RuntimeError):
    """Raised when `fundamentals_facts`/`price_bars` has no rows at all for a ticker/CIK that PASSED
    Layer 1 — i.e. `mizan normalize` was never run for it (§6e's fail-fast ordering: a ticker that
    fails Layer 1 never reaches this check at all, since it never needs Phase 3's tables)."""


class InsufficientDataError(RuntimeError):
    """Raised when a REQUIRED denominator-side figure (total assets, OR shares-outstanding-times-
    price for market cap, OR total revenue) has no resolvable value as of `as_of_date`, for a ticker
    that passed Layer 1. Never silently defaulted to 0 or 1 — a missing denominator cannot be guessed
    without either a division-by-zero or a fabricated scale, both of which are "reject rather than
    guess" (ULTIMATE_PRD.md §4.3) violations. Distinct from a numerator-side miss (§4.2), which is a
    legitimate 0.0, not an error.
    """


def screen(
    ticker: str,
    as_of_date: date,
    *,
    con: duckdb.DuckDBPyConnection,
    cache_dir: Path,
    overrides: BusinessActivityOverrideMap = BusinessActivityOverrideMap(overrides={}),
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ResultEnvelope:
    """THE canonical, singular screening entry point (MASTER_PRD.md §11 item 2, ULTIMATE_PRD.md §2.2)
    and the ONLY function in `mizan/` whose own body may treat "most-recently-filed fact with
    `filed <= as_of_date`" as sufficient point-in-time resolution, PER CONCEPT, without additionally
    pinning every numerator/denominator to one single governing filing/accession number (§6d — this
    is the precise, checkable content of the "Fork-1 simplification," not a vaguer "look-ahead is
    allowed here"). Every other function this module calls (`classify_business_activity`,
    `compute_financial_ratio_screen`, and everything in `mizan/screening/financial_ratios.py` /
    `business_activity.py`) receives already-resolved plain values and NEVER references `filed`
    itself — the temporal-non-interference confinement check (ULTIMATE_PRD.md §5 check 7) is
    therefore satisfied vacuously for those modules, not merely satisfied.

    Fail-fast ordering (§6c, §6e): resolves `cik` (`resolve_cik_offline`, reused from Phase 3) and
    `sic` (`resolve_sic_offline`, §4.1) from the cache ONLY — no DuckDB touch yet — then runs
    `classify_business_activity`. If Layer 1 fails: returns immediately with a single-entry reason
    trace and `Verdict.NON_COMPLIANT`, WITHOUT ever opening a query against `fundamentals_facts`/
    `price_bars` — a Layer-1-failing ticker need never even have been normalized (§8 AC2). If Layer 1
    passes: resolves the two-axis denominator and every ratio numerator from `con` (§6b, §6d),
    raising `NotNormalizedError`/`InsufficientDataError` as appropriate, then runs
    `compute_financial_ratio_screen` and combines both layers via the taxonomy in §6c.

    Returns a `ResultEnvelope` per §3.4 — `payload` is `ScreeningVerdict.model_dump()`,
    `active_caveats` is always `(Caveat.LOOK_AHEAD_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION)`.
    """
```

### 4.4 `mizan/cli/main.py`, `mizan/cli/screen.py`

```python
# mizan/cli/main.py — ONE new line added to build_parser(), no other change:
#     screen_cli.add_subparser(subparsers)


# mizan/cli/screen.py
def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Registers `screen --ticker TICKER [--ticker TICKER ...] --as-of-date YYYY-MM-DD
    --db-path PATH --cache-dir PATH [--overrides-path PATH]`. `--overrides-path` is OPTIONAL with no
    hidden default file — omitting it means "no override map," per §3.2's honest-empty-default
    posture; this is deliberately NOT the same "operator must be explicit" posture PHASE_2/3_SPEC.md
    §4.4 gave `--cache-dir`/`--db-path` (those name where REQUIRED, always-present state lives; an
    override map is optional, genuinely-absent-by-default state, so its absence needs no flag at
    all, whereas a wrong/missing cache or DB path would silently mean "the wrong data").
    """


def run(args: argparse.Namespace) -> int:
    """Opens one read-only DuckDB connection via `db.connect(args.db_path, read_only=True)` (Phase
    3's own read-only mode, `PHASE_3_SPEC.md` §4.1 — `screen` never writes to DuckDB, §5), loads the
    override map once via `load_override_map(args.overrides_path)`, then for each `--ticker` calls
    `screen(...)`, printing the resulting `ScreeningVerdict`'s verdict and full reason trace to
    stdout. Catches `CikResolutionError` / `SicResolutionError` / `NotNormalizedError` /
    `InsufficientDataError` per-ticker, prints a HALT message to stderr naming the ticker and the
    failure, and continues to the next ticker — but returns a non-zero exit code if ANY ticker
    halted, mirroring `mizan.cli.ingest.run`/`mizan.cli.normalize.run`'s exit-code contract exactly.
    """
```

---

## §5 Migrations

**N/A, confirmed explicitly.** Phase 4 adds no DuckDB table, no column, no index, and issues no
`CREATE`/`ALTER`/`DROP` anywhere in its own code. It opens `fundamentals_facts`/`price_bars`
strictly read-only (`db.connect(..., read_only=True)`, already part of Phase 3's public interface,
`PHASE_3_SPEC.md` §4.1: "for Phase 4+ read-only consumers"), and reads exactly one additional raw
cache file per ticker (`edgar/submissions/{cik}.json`, already written by Phase 2, §1). No new
Parquet, no new JSON cache shape, no schema versioning question arises because nothing about the
schema changes. `mizan/data/db.py` and `mizan/data/normalize.py` are both untouched by this phase
(§1).

---

## §6 Implementation Logic Flow

### 6a. `classify_business_activity` — the tiered business-activity screen and its fail-fast property

Per §4.1's precedence rule. The load-bearing property, restated because it is MASTER_PRD.md §6.1's
own framing verbatim: **"a fail here cannot be purified."** A Tier 0 or enabled-Tier-0.5/1 match (or
an override asserting non-compliance) is definitionally `Verdict.NON_COMPLIANT` — there is no code
path in which a Layer 1 failure and a Layer 2 pass combine into `Verdict.MIXED`. This is enforced
structurally in `screen()` (§6c) by simply never constructing or calling
`compute_financial_ratio_screen` when Layer 1 fails, not by a downstream check that could be
bypassed.

Every toggle is read from `fiqh_params` on every call (`fiqh_params.business_activity_tier_0_5_enabled.value`,
`fiqh_params.business_activity_tier_1_enabled.value`) — never cached at import time, never a bare
Python `bool` constant duplicating the register's value (§7 G-S6). `SIC_TIER_MAP` itself is NOT
gated by any fiqh param — the register's #6/#7 gate WHICH TIERS COUNT AS FAILURES, not which SIC
codes fall into which tier bucket; the tier-membership mapping is the "generic, configurable"
engineering data from §2.2/§3.2, independent of whether that tier is currently enabled.

### 6b. The financial-ratio screen's two-axis denominator, resolved once in `verdict.py`

`_resolve_denominator(cik, ticker, as_of_date, *, con, fiqh_params) -> float` (private, lives in
`mizan/screening/verdict.py`, called only by `screen()`):

```
if fiqh_params.ratio_denominator_basis.value == RatioDenominatorBasis.TOTAL_ASSETS:
    facts = SELECT value, filed FROM fundamentals_facts
            WHERE cik = ? AND tag = 'Assets' AND unit = 'USD'
              AND is_instantaneous AND filed <= ?           -- as_of_date, hard filter, §6d
    if fiqh_params.ratio_denominator_smoothing.value == SPOT:
        value = most-recently-filed fact's value (period_end <= as_of_date)
    else:  # AVERAGED
        value = mean of one value per distinct period_end within the trailing 12 months of
                as_of_date (most-recently-filed fact per period_end, to avoid double-counting a
                restated period twice)
    if no facts found: raise InsufficientDataError
else:  # MARKET_CAP (default)
    shares = most-recently-filed dei:EntityCommonStockSharesOutstanding fact, filed <= as_of_date
    if shares fact missing: raise InsufficientDataError
    if SPOT:
        price = price_bars.raw_close WHERE ticker = ? AND trade_date <= ? ORDER BY trade_date DESC LIMIT 1
    else:  # AVERAGED
        price = mean(raw_close) over trade_date in (as_of_date - 365 days, as_of_date]
    if no price rows found: raise InsufficientDataError
    value = shares * price
```

**`raw_close`, never `adj_close`, for market cap — a deliberate, explicit choice, not an oversight.**
Market capitalization at a historical date is *actual traded price* × *actual reported shares
outstanding at that date*. `adj_close` is back-adjusted for LATER splits/dividends; pairing a
split-back-adjusted price with a NOT-similarly-adjusted shares-outstanding count (the XBRL fact is
reported as of its own filing, never retroactively re-expressed for a future split) would silently
misstate the dollar figure. This is the same `raw_*`/`adj_*` non-conflation guard Phase 2/3 built
(`ULTIMATE_PRD.md` §4.2 guard G-T3) applied at its first new point of use in Phase 4 — restated here,
not a new invariant.

**The AVERAGED axis's shares-outstanding simplification, stated explicitly:** when averaging price,
shares outstanding is held at its single most-recent (spot) value rather than also being
time-averaged or interpolated day-by-day — a stated engineering simplification (shares-outstanding
history is quarterly-sparse; a full daily interpolation is unwarranted precision for this ratio),
not a fiqh judgment call, and not gated by any register entry.

**Numerator resolution** (`_resolve_ratio_inputs`, same module, same as_of_date-filtered pattern):
for each of `INTEREST_BEARING_DEBT_TAGS`/`INTEREST_BEARING_INVESTMENT_TAGS`/
`NON_PERMISSIBLE_INCOME_TAGS`, sum the most-recently-filed (`filed <= as_of_date`) value per distinct
tag in the set (a company reporting under two of the four debt tags contributes both; a company
reporting under none contributes `0.0` — §4.2's numerator-vs-denominator asymmetry). `total_revenue`
resolves the same way over `TOTAL_REVENUE_TAGS`, but an EMPTY result here is `InsufficientDataError`
(revenue is a denominator for ratio 3, not a numerator — §4.2).

### 6c. Verdict combination — MASTER_PRD.md §6.3's exact three states

```
if not business_activity_result.passed:
    verdict = NON_COMPLIANT
    reason_trace = (business_activity_result.reason,)          # Layer 2 never runs — §6a
else:
    ratio_result = compute_financial_ratio_screen(...)
    reason_trace = (business_activity_result.reason, ratio_result.debt_ratio,
                     ratio_result.interest_investments_ratio,
                     ratio_result.non_permissible_income_ratio)
    if not ratio_result.passed:
        verdict = NON_COMPLIANT       # "if debt and investment ratios exceed the allowed thresholds"
                                       # — extended, consistently, to all three 30/30/5 checks, since
                                       # MASTER_PRD.md §6.2 treats all three as one compliance gate
    elif all three ratio actual_values == 0.0:
        verdict = PURE                # "no interest based deposits or loans" — verbatim (§3.1(c))
    else:
        verdict = MIXED               # "financial ratios that do not exceed the thresholds" —
                                       # purification applies (Phase 6)
```

`<=`, not `<`, at every threshold comparison (§4.2's own note): AAOIFI's own verbatim wording is "should
not EXCEED" (`docs/modernization_log.md` §7, confirmed against slides 32–34), which is inclusive of
the boundary value itself. `MASTER_PRD.md` §6.2's "< 30%" phrasing is the less precise restatement;
Phase 4 implements the primary-source-verbatim reading, and this document records the reconciliation
here rather than silently picking one. The synthetic fixture (§6e, ZZBOUNDARY01) exercises the exact
boundary to make this a tested behavior, not just a documented one.

### 6d. `screen()`'s temporal-filtering discipline — the deterministic anchor

```
screen(ticker, as_of_date, ...)   Deterministic given: the cache directory's existing contents, the
                                    DuckDB file's existing contents, `as_of_date`, `overrides`, and
                                    `fiqh_params` — no clock, no randomness, no network. Every
                                    DuckDB/cache read this function's own body performs (directly, or
                                    via a private helper reachable only from this function) filters
                                    STRICTLY by `filed <= as_of_date` (never `<`, since `filed` is a
                                    date the value plausibly became known ON, not strictly after).
```

**The Fork-1 simplification, stated as the one precise, checkable property it is** (§0's naming
convention, `ULTIMATE_PRD.md` §3.3's "single declared violation... confined to one function body"):
true point-in-time reconstruction would pin every numerator AND the denominator to the single most
recent governing filing (one accession number) whose `filed <= as_of_date`, so that a ratio snapshot
never silently mixes values from two different filings/reporting vintages for the same as-of date.
`screen()`'s helpers instead resolve each concept (assets, shares, each debt/investment/income tag,
revenue) via its OWN independent "most-recently-filed value with `filed <= as_of_date`" query — which
can, in principle, pull one concept from one filing and another concept from a different, later
filing's restated comparative for an overlapping period (the modernization_log.md §6.1 AAPL example:
a FY2017 fact carrying `filed=2019-10-31`, reported as a comparative in the FY2019 10-K). This is
strictly less work than true PIT reconstruction, is confined to these helper functions (all reachable
only from `screen()`, all named and grouped together in `mizan/screening/verdict.py`), and is exactly
what `Caveat.LOOK_AHEAD_BIAS` is stamped for on every `screen()` result (§3.4). The V2 fix
(`ULTIMATE_PRD.md` §3.3) is: change these helpers to resolve one governing accession number first,
then pull every concept from that one filing — a data-slicing change confined to this module, not a
rewrite.

### 6e. The synthetic fixture universe (`tests/fixtures/synthetic_universe.py`)

~12 SYNTHETIC, clearly-labeled tickers (never real issuers, never presented as researched) exercising
every decision above:

| Ticker (synthetic) | SIC / override | Fixture facts | Expected verdict | What it proves |
|---|---|---|---|---|
| `ZZPURE01` | clean SIC (software) | debt=0, investments=0, income=0 | `PURE` | Layer 1 pass + all-zero ratios |
| `ZZMIXED01` | clean SIC | small nonzero debt/investment/income, all under threshold | `MIXED` | Layer 1 pass + nonzero-but-compliant ratios |
| `ZZNONCOMP_ACT01` | Tier 0 SIC (bank) | n/a — never queried | `NON_COMPLIANT` | §8 AC2: fail-fast, zero ratio entries in trace |
| `ZZNONCOMP_RATIO01` | clean SIC | debt ratio 35% | `NON_COMPLIANT` | Layer 2 debt-ratio failure |
| `ZZNONCOMP_RATIO02` | clean SIC | income ratio 7% | `NON_COMPLIANT` | Layer 2 income-ratio failure |
| `ZZTIER05_01` | Tier 0.5 SIC (weapons) | n/a | `NON_COMPLIANT` (default) | register #6 default-ON; toggling it OFF via `model_copy` changes this ticker's verdict (§8 AC3) |
| `ZZTIER1_01` | Tier 1 SIC (hotels) | clean ratios | `MIXED` or `PURE` (Tier 1 default OFF) | register #7 default-OFF — passes Layer 1 despite being on the contested list |
| `ZZOVERRIDE_RESCUE01` | Tier 0 SIC, override `tier_override=None` | clean ratios | `PURE`/`MIXED` | override RESCUES a SIC false positive — precedence, direction 1 |
| `ZZOVERRIDE_FLAG01` | clean SIC, override `tier_override=TIER_0` | n/a | `NON_COMPLIANT` | override FLAGS a SIC false negative — precedence, direction 2 |
| `ZZBOUNDARY01` | clean SIC | debt ratio EXACTLY 30.0% | passes (per §6c's `<=`) | boundary-inclusive threshold semantics |
| `ZZLOOKAHEAD01` | clean SIC | one fact with `filed` AFTER `as_of_date`, an earlier fact with `filed` before it | verdict computed from the EARLIER fact only | §7/§8 temporal-non-interference test |
| `ZZNODATA01` | clean SIC | no `Assets`/shares/price facts at all | `screen()` raises `InsufficientDataError` | denominator-missing HALT, never a guess |

Every ticker's name, in this table and in the fixture module's own top-of-file docstring, is stated
as **invented for testing purposes only** — never a real issuer, never claimed to be researched. No
test or fixture in this file may be mistaken for, or later silently repurposed as, the real curated
universe (§9).

---

## §7 Failure-Mode Guards

Pulled from `ULTIMATE_PRD.md` §4.4 (Screening) specifically, plus this phase's own new surface.

| # | Failure mode | Guard Phase 4's code implements | What the review agent checks |
|---|---|---|---|
| G-S1 | **Wrong compliance verdict (the WORST case, `MASTER_PRD.md` §13)** | No LLM anywhere in `mizan/screening/` (§2.3); every verdict a pure function of already-typed inputs; unit tests against the synthetic reference cases (§6e) — NOT a claim of real-world hand-verification, stated explicitly in every such test's docstring | `grep -rniE "openai\|anthropic\|gemini\|vertex\|langchain\|\bllm\b\|chat_completion\|completion\(" mizan/screening/` clean; every §6e fixture ticker's `screen()` result matches its expected verdict AND has a non-empty reason trace naming which screen drove it |
| G-S2 | Look-ahead beyond the Fork-1 simplification | Every DuckDB/cache query touching `filed` sits inside `mizan/screening/verdict.py`, hard-filtered `filed <= as_of_date` (§6d) | `ZZLOOKAHEAD01` (§6e): assert the later-filed fact never influences the result; `grep -rn "filed" mizan/screening/` — every hit is inside `verdict.py`, and every function containing one takes `as_of_date` |
| G-S3 | SIC-code misclassification | `BusinessActivityOverrideMap` takes precedence over `SIC_TIER_MAP` outright (§4.1, §6a) | `ZZOVERRIDE_RESCUE01`/`ZZOVERRIDE_FLAG01` (§6e) both directions |
| G-S4 | Tier 0.5/Tier 1 silently promoted into a hardcoded, always-on core | Both gates read `fiqh_params.business_activity_tier_0_5_enabled.value`/`.tier_1_enabled.value` on every call, never cached | `ZZTIER05_01` re-screened with `fiqh_params.model_copy(update={"business_activity_tier_0_5_enabled": FIQH_PARAMS.business_activity_tier_0_5_enabled.model_copy(update={"value": False})})` changes the verdict (§8 AC3); `grep -n "business_activity_tier_0_5_enabled\|business_activity_tier_1_enabled" mizan/screening/business_activity.py` — the only two read sites |
| G-S5 | Denominator/threshold config drift silently ignored | Every threshold/basis/smoothing value read from `fiqh_params` at call time, never a module-level constant | Same `model_copy` pattern as G-S4, applied to `debt_ratio_threshold` (§8 AC3) |
| G-S6 | A `fiqh_params` source string, or a Phase-4-introduced constant's own docstring, overstates settledness | Register #5/#6/#7's existing `source`/`primary_source_gap` strings are read, never re-worded by Phase 4; `NON_PERMISSIBLE_INCOME_TAGS`'/`TOTAL_REVENUE_TAGS`' own module docstrings state their proxy/pick status plainly (§3.2, §6b) | Review of every new docstring against §3.1(a)/(b)/(d) of `ULTIMATE_PRD.md` |
| G-S7 | Business-activity or ratio functions gain accidental network/DB capability | `classify_business_activity`/`compute_financial_ratio_screen`/every function in `financial_ratios.py` take no `con`/`cache_dir`/`client` parameter at all — pure functions over already-resolved values (§4.1, §4.2) | `grep -rn "duckdb\|httpx\|cache_dir" mizan/screening/business_activity.py mizan/screening/financial_ratios.py` — no hit outside `resolve_sic_offline`/`load_override_map`'s own declared `cache_dir`/`path` parameters |
| G-S8 | `resolve_sic_offline` gains live network capability | No `client`/`httpx` parameter exists on it (§4.1) | `grep -rn "httpx" mizan/screening/` — no hit anywhere |
| G-DB3 | `screen()`/`mizan screen` writes to DuckDB | `db.connect(..., read_only=True)` used by the CLI (§4.4); no `INSERT`/`CREATE`/`ALTER` anywhere under `mizan/screening/` | `grep -rniE "INSERT INTO\|CREATE TABLE\|ALTER TABLE" mizan/screening/` — no hit |
| G-LLM4 | LLM/model SDK reachback (this phase's own restatement, §2.3) | Forbidden-dependency list unchanged | `ULTIMATE_PRD.md` §5 checks 5 and 6, re-run over the full `mizan/` tree including `mizan/screening/` |
| G-AI | AI attribution in commit messages | Same neutral-commit convention as Phases 1–3 | `git log --format=%B` for this phase's commits |

**Categorisation, mirroring Phases 1–3:** G-S1, G-S2, G-S3, G-S4, G-S5, G-S6, G-LLM4, G-AI are
**HALT-for-human** (compliance-correctness or honesty-surface touching — MASTER_PRD.md §13's own
"nothing in `screening/`... may auto-recover by guessing," restated by `ULTIMATE_PRD.md` §4.4's
categorisation summary). G-S7, G-S8, G-DB3 are blocking-but-mechanical.

---

## §8 Phase Acceptance Criteria

Each concrete, independently checkable by a third party, same standard Phases 1–3 applied.

1. **Every §6e synthetic fixture ticker's `screen()` result matches its expected `Verdict`**, with a
   non-empty `reason_trace` whose entries correctly name which screen (`ScreenName`) drove the
   result.
2. **Fail-fast is structural, not incidental.** `ZZNONCOMP_ACT01`'s `reason_trace` contains EXACTLY
   one entry (`ScreenName.BUSINESS_ACTIVITY`) and zero `DEBT_RATIO`/`INTEREST_INVESTMENTS_RATIO`/
   `NON_PERMISSIBLE_INCOME_RATIO` entries; `screen()` for this ticker never issues a
   `fundamentals_facts`/`price_bars` query at all (verifiable by pointing it at a DuckDB file with no
   normalized rows for that CIK and confirming no `NotNormalizedError` fires — Layer 1 alone is
   sufficient to reach `NON_COMPLIANT`).
3. **Config values are read, not hardcoded — proven, not asserted.** Re-screening `ZZTIER05_01` with
   `FIQH_PARAMS.business_activity_tier_0_5_enabled` copied to `value=False` (via `model_copy`, since
   `FiqhParams` is frozen) changes its verdict from `NON_COMPLIANT` to whatever Layer 2 alone
   produces; separately, re-screening a debt-ratio-boundary fixture with `debt_ratio_threshold`
   copied to a lower `value` changes at least one synthetic ticker's verdict.
4. **Temporal non-interference holds for `ZZLOOKAHEAD01`.** A fact with `filed` strictly after
   `as_of_date` never influences `screen()`'s result — verified by constructing two otherwise-
   identical DuckDB states differing only in whether the later-filed fact is present, and asserting
   identical `screen()` output for a fixed `as_of_date` before that fact's `filed` date.
5. **The override map takes precedence over the SIC first-pass in both directions**
   (`ZZOVERRIDE_RESCUE01`, `ZZOVERRIDE_FLAG01`), testably.
6. **A missing required denominator halts, never guesses.** `ZZNODATA01` raises
   `InsufficientDataError`, not a zero-division, not a fabricated default.
7. **A missing numerator does not halt.** A fixture ticker with clean SIC, valid denominator data,
   but zero rows under every tag in `INTEREST_BEARING_DEBT_TAGS` computes a debt ratio of exactly
   `0.0`, not an error.
8. **Boundary semantics are `<=`.** `ZZBOUNDARY01`'s ratio at exactly the configured threshold
   passes.
9. **No LLM/model-client SDK import anywhere in `mizan/screening/`.** `ULTIMATE_PRD.md` §5 checks 5
   and 6, clean.
10. **`screen()` never writes to DuckDB.** `mizan screen` opens its connection `read_only=True`; no
    `INSERT`/`CREATE`/`ALTER` anywhere under `mizan/screening/`.
11. **Every new Pydantic model inherits `MizanBaseModel`.** No file under `mizan/screening/` or
    `mizan/cli/screen.py` imports or subclasses `pydantic.BaseModel` directly.
12. **Boot gate runs first.** `mizan screen ...` under a deliberately-violated `Invariants`/
    `FiqhParams` instance exits 1 with the boot-check failure message before any screening logic
    runs (`mizan.cli.main.main`'s existing centralized `check_all()`, unmodified, §0).
13. **The override-map format is documented well enough to be filled in without further engineering
    help.** `mizan/screening/business_activity.py`'s module/class docstrings (§3.2, §4.1) state the
    JSON shape, the CIK-keying convention, the meaning of `tier_override=None` vs a set tier, and the
    mandatory-`rationale` requirement, clearly enough that a third party reading only those
    docstrings (not this spec) could hand-author a real override-map JSON file. Reviewed as a
    documentation-quality criterion, not merely a schema-exists criterion.
14. **`mypy --strict mizan tests` exits 0.** Built and verified inside the project's `.venv`, per
    `PHASE_3_SPEC.md` AC14's established requirement.
15. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5`.
16. **`pytest` passes in full**, all four new test files plus `tests/fixtures/synthetic_universe.py`
    plus the full existing Phase 1–3 suite (no regression).
17. **No forbidden dependency anywhere**, `ULTIMATE_PRD.md` §5 checks 5 and 6 clean over the expanded
    `mizan/` tree and `pyproject.toml`; `pyproject.toml` is unmodified by this phase (§2.1).
18. **No premature imports.** `pandas`/`matplotlib` imported by no module under `mizan/`; `pyarrow`
    imported by no module under `mizan/screening/` (§2.1).
19. **§2.2's XBRL tag verification is logged.** `docs/modernization_log.md` carries a dated entry
    confirming (or correcting) each tag in `INTEREST_BEARING_DEBT_TAGS`,
    `INTEREST_BEARING_INVESTMENT_TAGS`, `NON_PERMISSIBLE_INCOME_TAGS`, `TOTAL_REVENUE_TAGS`, and
    `us-gaap:Assets`/`dei:EntityCommonStockSharesOutstanding`, against at least the synthetic
    fixtures' own companyfacts shape.
20. **Commits are neutral.** No AI attribution in `git log` for this phase's commits.
21. **Boundary greps are clean**, re-run from repo root against the full tree including
    `mizan/screening/*.py` and `mizan/cli/screen.py` (`ULTIMATE_PRD.md` §5 checks 1–8).
22. **No fabricated large-scale ticker classification anywhere in this phase's deliverable.** No file
    under `mizan/` or `tests/` contains more than the ~12 explicitly-synthetic §6e tickers presented
    as classified/verified; no docstring, comment, or fixture name implies real-world research was
    performed.

**Any single failing criterion is a phase-loop HALT, not a partial pass** — same standard Phases 1–3
state, applied here.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 4)

- **The real ~100-ticker curated universe and its hand-verified business-activity map are NOT built
  in Phase 4 — the first, most prominent non-goal, stated here deliberately ahead of every other
  item.** `MASTER_PRD.md` §6.1 names "SIC first-pass + a hand-verified activity map" as the honest V1
  implementation for a real, human-facing universe; that hand-verified map requires genuine human
  research — reading actual 10-Ks, actual business-segment disclosures, actual conglomerate
  structures — that no automated build agent can perform honestly. Fabricating one at scale (e.g.
  inventing plausible-sounding "verified" classifications for ~100 real tickers) would be dishonest
  on its face and would destroy the exact correctness backstop the real map exists to provide
  (`MASTER_PRD.md` §0, §13: a confidently-wrong classification presented as researched is a worse
  failure than an admittedly-generic SIC first-pass alone). Phase 4 ships the generic, configurable
  mechanism — `SIC_TIER_MAP` (public, sourced, engineering data, §4.1) plus
  `BusinessActivityOverrideMap` (pluggable, ships empty, §3.2) — verified only against the ~12
  explicitly-synthetic fixture tickers of §6e. The shipped code operates correctly on whatever real
  universe the owner configures later, once that separate, human research effort is done; this phase
  does not simulate, shortcut, or gesture at having done that research.
- **No backtest engine, no compliance-flip state machine, no portfolio/strategy code, no `pandas`
  import.** → Phase 5. `screen()` produces a single verdict for one ticker at one `as_of_date` — it
  does not track state over time, does not know about holdings, and does not decide when a
  previously-compliant ticker's flip should trigger divestment (Phase 5's `compliance_state.py`).
- **No purification logic.** Phase 4 computes `Verdict.MIXED`/`PURE`/`NON_COMPLIANT`; it does not
  compute a purification amount, does not touch `price_bars.div_cash` for that purpose, and does not
  implement any of Forks A/B/C (register #9/#10/#11) — those remain Phase 6's, unread by Phase 4.
- **No reporting, no `matplotlib` import.** → Phase 7.
- **No new DuckDB table, column, or migration.** §5 — Phase 4 is read-only against Phase 3's schema.
- **No `backtest`/`report` CLI subcommands.** `mizan/cli/` in Phase 4 registers `ingest`, `normalize`
  (both unchanged) and `screen` only.
- **No 10-K-text NLP classification, and no LLM anywhere, ever — restated because this phase is the
  one where the temptation is highest.** `MASTER_PRD.md` §6.1's own text names "parsing 10-K business
  description text" as a V2 NLP item that "must not drag an LLM into this deterministic screen" —
  Phase 4 builds only the SIC-code + override-map mechanism; deeper text-based classification of any
  kind, LLM-driven or otherwise, is out of scope for V1 in its entirety, not merely deferred within
  this phase.
- **No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3).** Q1 (denominator basis/
  averaging window) and Q2 (Total Income vs total revenue) are directly touched by this phase's code
  (§6b picks a concrete `total_revenue` reading to compute with) but that pick does NOT resolve Q2 —
  it remains escalated to the human exactly as `COMPREHENSION.md` §6 and `PHASE_1_SPEC.md`/
  `PHASE_2_SPEC.md`/`PHASE_3_SPEC.md` have all carried it forward, unchanged.
- **No change to the rebalance cadence surface, no HTTP API/service/dashboard.** Unchanged from
  Phases 1–3; screening a single ticker at a single date touches neither.
- **No full S&P 500, no universe larger than what the owner explicitly configures.** `ULTIMATE_PRD.md`
  §12/`MASTER_PRD.md` §12's own V2 deferral, restated: genericity is about the MECHANISM (any SIC/
  override map an operator supplies), not about this phase silently attempting to scale to a larger
  universe than the project has ever scoped.

---
