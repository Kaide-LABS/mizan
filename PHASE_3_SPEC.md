# PHASE_3_SPEC.md — Mizan: Normalization & DuckDB Store

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), the same document `PHASE_1_SPEC.md` and `PHASE_2_SPEC.md` were built from.
> Every dependency promotion, every schema decision, and every guard below traces to a section of
> that document, cited inline, cross-checked against `MASTER_PRD.md` where `ULTIMATE_PRD.md` is
> silent and against the committed Phase 1 code (`mizan/config/`, `mizan/core/`) and Phase 2 code
> (`mizan/data/`, `mizan/cli/`) for integration fidelity.

**Generated:** 2026-08-30 · **Dispatch type:** phase advancement (Phase 2 review-approved,
comprehension pass complete; no code review or fix loop runs in this dispatch) · **Canonical
references:** `ULTIMATE_PRD.md` (governs), `MASTER_PRD.md` (governs where ULTIMATE is silent),
`docs/modernization_log.md` (pinned external reality — §3 runtime dependency pins, §5.4 DuckDB
Python API), `COMPREHENSION.md` (what Phase 1–2 actually shipped, including open items — §6 below),
`PHASE_1_SPEC.md` §5 (the forward-declared DuckDB uniqueness key this document must honor),
`PHASE_2_SPEC.md` (format and rigor precedent, and the public surface — `mizan.data.models`,
`mizan.data.raw_cache`, `mizan.data.ingest_edgar`, `mizan.data.ingest_tiingo`, `mizan.cli.main` —
Phase 3 must consume without reshaping).

**No citation re-verification gate applies to this document.** Confirmed already for this project
(`PHASE_2_SPEC.md`'s own confirmation, unchanged): Mizan's arXiv citations are background
corroboration for design choices already settled by primary sources (AAOIFI methodology, SEC/Tiingo
API contracts, DuckDB's own reference docs), not phase-anchoring technical claims. This file carries
no §0.5.

---

## §0 Phase Plan Header

# **Phase 3 of 7: Normalization & DuckDB Store**

Phase sequence, unchanged from `PHASE_2_SPEC.md` §0 / `ULTIMATE_PRD.md` §6 (re-derived there, not
re-derived again here — nothing in the Phase 3 build changes the count or the ordering):

| # | Phase | Ships |
|---|---|---|
| 1 | Foundation & Config (done, approved) | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| 2 | Ingestion & raw cache (done, approved) | EDGAR (`companyfacts` + `companyconcept` + `submissions`) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| **3** | **Normalization & DuckDB store** ← *this document* | raw → typed tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine | business-activity (tiered), financial ratios (30/30/5, two-axis denominator), verdict + reason trace, temporal-non-interference confinement check |
| 5 | Backtest engine + compliance-flip state machine | daily clock, portfolio, strategy interface, flip→grace→divest |
| 6 | Purification | side-ledger, `divCash`-driven, Forks A/B/C from config |
| 7 | Reporting | static HTML + matplotlib, caveats non-optional, gross vs net-of-purification |

This spec covers **Phase 3 only**. It is the contract the Phase 3 execution agent builds against and
the Phase 3 review agent (next round of Step 12) verifies against. Phase 3 **consumes** Phase 1's
public surface (`mizan.config.invariants.INVARIANTS`, `mizan.config.fiqh_params.FIQH_PARAMS`,
`mizan.core.base.MizanBaseModel`, `mizan.config.boot_check.check_all`) and Phase 2's public surface
(`mizan.data.models.*`, `mizan.data.raw_cache.*`, `mizan.data.ingest_edgar.CikResolutionError`,
`mizan.cli.main.build_parser`) and **must not reshape either**. Phase 3 may only extend that surface
additively. Every new symbol Phase 3 introduces (`mizan.data.normalize`, `mizan.data.db`,
`mizan.cli.normalize`) is itself now locked for Phases 4–7 the same way.

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`.** Same flat layout `PHASE_1_SPEC.md` §1 established and
`PHASE_2_SPEC.md` §1 preserved — no nesting directory. Every file below is new except
`pyproject.toml`, `docs/modernization_log.md`, `.gitignore`, and `mizan/cli/main.py`, which Phase 3
**modifies**.

```
C:\Users\hp\HMS\
├── pyproject.toml                       # MODIFIED — duckdb + pyarrow promoted to real deps (§2)
├── .gitignore                           # MODIFIED — *.duckdb, *.duckdb.wal added (§5, §8 AC5)
├── docs/
│   └── modernization_log.md             # MODIFIED — §3 duckdb/pyarrow re-check entry dated (§2.1)
├── mizan/
│   ├── data/
│   │   ├── db.py                        # NEW — DuckDB connection + idempotent schema creation (§4.1, §5)
│   │   └── normalize.py                 # NEW — raw cache → typed DuckDB rows (§3, §4.2, §6)
│   └── cli/
│       ├── main.py                      # MODIFIED — registers the `normalize` subparser (one line, §1 precedent)
│       └── normalize.py                 # NEW — the `normalize` subcommand (§4.3)
└── tests/
    ├── test_data_db.py                  # NEW — schema idempotency, constraint enforcement, lock behaviour
    ├── test_data_normalize.py           # NEW — unit-rejection, duplicate-guard, idempotent replay, column contract
    └── test_cli_normalize.py            # NEW — boot-gate-first behaviour, offline-only (zero network capability), exit codes
```

**Files explicitly NOT created in Phase 3:** `mizan/screening/`, `mizan/backtest/`,
`mizan/reporting/`, and no `screen`/`backtest`/`report` subcommands under `mizan/cli/`. These are
named in `MASTER_PRD.md` §9.4 and `ULTIMATE_PRD.md` §6 for Phases 4–7. See §9.

**`mizan/data/db.py` justification (it is not named directly in `MASTER_PRD.md` §9.4's module tree,
which lists only `ingest_edgar.py` / `ingest_tiingo.py` / `normalize.py` under `data/`):**
`PHASE_1_SPEC.md` §5's own forward note put DuckDB connection/schema-creation squarely in Phase 3's
lap ("DuckDB permits one writer per database file... The Phase 3 uniqueness constraint for XBRL
facts is..."), but it does not say that logic must live inside `normalize.py` itself. Splitting
connection-management/schema-DDL (`db.py`) from row-mapping/business logic (`normalize.py`) follows
the exact precedent `PHASE_2_SPEC.md` §1 set for `raw_cache.py` vs `ingest_edgar.py`/
`ingest_tiingo.py`: the mechanics that are identical in shape regardless of *which* table is being
written (open-or-create the file, run idempotent `CREATE TABLE IF NOT EXISTS`, expose one
`DuckDBPyConnection`) are one canonical, narrow module, so `normalize_edgar_facts` and
`normalize_tiingo_bars` cannot drift on schema-creation the way `raw_cache.py`'s justification says
the two ingestion legs must not drift on cache mechanics. It is also the one file Phase 4's
screening layer and Phase 5/6/7's backtest/purification/reporting layers will import from to obtain
a read connection — `mizan/core/` was justified the same way in `PHASE_1_SPEC.md` §1 ("one canonical
home, decided now").

**`mizan/cli/normalize.py`, following the `main.py` + one-file-per-verb pattern `PHASE_2_SPEC.md`
§1 established for `ingest.py`:** `mizan/cli/main.py` gains exactly one new line
(`normalize_cli.add_subparser(subparsers)`) — the single touch-point later phases also use, per
Phase 2's additive-extension convention. `mizan/cli/ingest.py` is untouched.

**Confirmed: this phase does not touch `mizan/screening/`, `mizan/backtest/`, or
`mizan/reporting/`** — none of those directories exist yet (§9), and no file Phase 3 adds imports
from a path under any of them (there is nothing to import from).

---

## §2 Dependencies

### 2.1 `duckdb` and `pyarrow` promoted from optional to required

`PHASE_1_SPEC.md` §2.1 declared `duckdb==1.5.5` and `pyarrow==25.0.1` under
`[project.optional-dependencies].data`, explicitly for forward-stability only — "installing them
in Phase 1 is harmless; importing them in Phase 1 is a review-blocking finding" (`PHASE_1_SPEC.md`
§9, restated unchanged by `PHASE_2_SPEC.md` §7 guard G-DEP1 through Phase 2). Phase 3 is the phase
`ULTIMATE_PRD.md` §6 names as the one that actually builds the DuckDB store, so both are promoted to
core runtime dependencies. `pandas` and `matplotlib` are **not** promoted (§2.2) — the `data` extra
is narrowed to `pandas` alone, and `duckdb`/`pyarrow` move up:

```toml
[project]
dependencies = [
    "pydantic==2.13.5",
    "httpx==0.28.1",
    "duckdb==1.5.5",
    "pyarrow==25.0.1",
]

[project.optional-dependencies]
# `data` extra NARROWED in Phase 3 (PHASE_3_SPEC.md §2.1) — duckdb/pyarrow are no longer
# forward-declared, they are real Phase 3 dependencies. `pandas` remains forward-declared and
# unused (§2.2) for whichever of Phases 5/7 first imports it.
data = [
    "pandas==3.0.5",
]
report = [
    "matplotlib==3.11.1",
]

[project.scripts]
mizan-boot-check = "mizan.config.boot_check:main"
mizan = "mizan.cli.main:main"
```

**Why `pyarrow` is genuinely needed now, not merely along for the ride with `duckdb`:**
`docs/modernization_log.md` §5.4 documents `con.register(view_name: str, python_object: object)` as
a real DuckDB 1.5 API — the idiomatic bulk-load path is to build a `pyarrow.Table` from the
validated, normalized Pydantic rows in one pass, `register()` it as a queryable view, then run one
`INSERT ... SELECT ... WHERE NOT EXISTS (...)` statement against it (§6.2) rather than looping a
Python-level `INSERT` per row. This is the concrete Phase 3 call site for `pyarrow` — it is not a
Parquet-file feature (Phase 3 still writes no Parquet, §5) but the Arrow-interchange feature
`docs/modernization_log.md` §5.4 and `ULTIMATE_PRD.md` §2.1's dependency table already named
(`pyarrow` role: "Parquet raw cache + DuckDB↔Arrow interchange" — Phase 3 uses the second half of
that role, not the first).

**Pin re-verification — action performed, not assumed.** `docs/modernization_log.md` §3 already
carries `duckdb==1.5.5` and `pyarrow==25.0.1` dated 2026-08-30 from the Step 10 modernization pass,
and this phase's own build date is also 2026-08-30. **A same-calendar-date log entry is not proof
that no time has passed between the Phase 2 build and this one** — Phase 2's own re-check of `httpx`
(§2.1 of `PHASE_2_SPEC.md`, logged in `docs/modernization_log.md` §3) was performed for exactly this
reason even though it, too, landed on the same nominal date as the original verification. Per
`docs/modernization_log.md` §1's own governing rule ("no version number appears in this file without
a verification date and a source URL"), the Phase 3 build agent must run a live `pip index versions
duckdb` / `pip index versions pyarrow` (or equivalent PyPI check) at build time and log the result in
§3 with a fresh dated line — **even if the result is "unchanged"** — rather than silently carrying
the Step 10 entry forward as if it already covered this phase's own promotion event. This is a
mechanical, blocking-but-not-judgment-call action item (§7 G-DEP3), not a design decision.

### 2.2 `pandas` — deliberately NOT promoted in Phase 3

`ULTIMATE_PRD.md` §2.1's dependency table states `pandas`'s role verbatim: **"tabular glue for
strategy/report layers."** `MASTER_PRD.md` §9.1's pipeline diagram places `pandas`-shaped work (the
`strategy`/`portfolio` boxes reading screened tickers into a rebalancing loop, and the `report`
box's plot inputs) downstream of NORMALIZE, inside BACKTEST and REPORT — not inside NORMALIZE
itself. Phase 3's own data-movement need (raw JSON → validated Pydantic rows → a `pyarrow.Table` →
one `INSERT ... SELECT` per source, §2.1 above, §6.2) has no step that benefits from a DataFrame:
there is no filtering, joining, or resampling of tabular data happening in this phase, only
row-shape validation and a bulk load. Importing `pandas` here would be exactly the "premature
import" failure mode `PHASE_1_SPEC.md` §7 guard G13 and `PHASE_2_SPEC.md` §7 guard G-DEP1 already
established for `duckdb`/`pyarrow` in Phases 1–2, now applied to `pandas` in Phase 3. **Decision:
`pandas` remains in `[project.optional-dependencies].data`, forward-declared and unused, until
whichever of Phase 5 (backtest/strategy) or Phase 7 (reporting) is built first** — that phase's own
spec is the one that promotes it and must re-verify its pin at that time, per the same discipline
§2.1 applies here.

### 2.3 No new dependency for the DuckDB bulk-load path

**Decision: no ORM, no `sqlalchemy`, no migration framework.** DuckDB's own Python API (`connect`,
`execute`, `register`, per `docs/modernization_log.md` §5.4) is sufficient for two tables and one
idempotent `CREATE TABLE IF NOT EXISTS` each (§5). Introducing a migration library (`alembic`,
`yoyo`, etc.) for a single-developer, single-schema-version, locally-owned DuckDB file would add a
dependency and a versioned-migration mental model this project does not need yet (§5's own reasoning
for why V1 has no migration framework) — the same "hand-written, inspectable logic over a generic
library" rationale `PHASE_2_SPEC.md` §2.2 gave for hand-rolling the two rate limiters instead of
pulling in `tenacity`.

### 2.4 Forbidden-dependency list unchanged

`PHASE_1_SPEC.md` §2.5's permanently forbidden list (`openai`, `anthropic`, every other LLM/model
SDK, `yfinance`) still applies, unmodified, to every file this phase adds. Restated, not re-derived,
per `PHASE_2_SPEC.md` §2.3's own restatement convention.

### 2.5 Modernization-log reconciliation (a Phase 3 deliverable)

Same discipline as `PHASE_1_SPEC.md` §2.4 and `PHASE_2_SPEC.md` §2.4: every version string in
`pyproject.toml` must appear identically in `docs/modernization_log.md` §3–§4. A mismatch is a
review-blocking finding. §2.1's live re-check above is the specific action this reconciliation
requires for this phase's two promoted dependencies.

---

## §3 Pydantic Schemas

Every new model inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no Phase 3 module subclasses `pydantic.BaseModel` directly, same as
Phase 1's guard G8 and Phase 2's restatement. Both models below live in `mizan/data/normalize.py`
(not a new `mizan/data/models.py` addition — that file is Phase 2's raw row-shape surface and is
**not modified**, per §1; these are a distinct, Phase-3-owned typed-table row shape, so they get
their own home in the module that produces them).

**These are normalized, typed row shapes — the DuckDB table row, one Python object per row —
not the raw wire-format schemas `PHASE_2_SPEC.md` §3 defined.** Unlike Phase 2's row-shape models,
snake_case renaming is explicitly correct here: `PHASE_2_SPEC.md` §3 itself deferred exactly this
renaming to "Phase 3's normalizer," which maps `val`→`value`, `adjClose`→`adj_close`, etc. A build
agent must still never invent a rename Phase 2's docstrings didn't already anticipate — every rename
below is one `PHASE_2_SPEC.md` §3 or `PHASE_2_SPEC.md` §7 guard G-T3 already named.

```python
"""mizan/data/normalize.py — normalized, typed row shapes + raw-cache-to-DuckDB mapping functions.

Grounded in ULTIMATE_PRD.md §4.3 (Normalization failure-mode table): silent unit-scale coercion and
duplicate/overlapping filing periods are the two named HALT-for-human failure modes this module's
row shapes and load logic must structurally prevent, not just document.
"""

from __future__ import annotations

from datetime import date as _Date

from mizan.core.base import MizanBaseModel

#: The XBRL unit strings Mizan's Phase 4 financial-ratio screen (30/30/5, MASTER_PRD.md §6.2) will
#: actually consume: interest-bearing-debt/deposits/revenue figures are USD; the market-cap
#: denominator's other factor (shares outstanding) is `shares`. Any other unit key
#: (`"USD/shares"` EPS-type concepts, `"pure"` ratio concepts, or anything else SEC's XBRL taxonomy
#: uses) is out of V1's scope and its appearance under a tag Mizan ingests is a signal to look, not
#: guess — ULTIMATE_PRD.md §4.3's "reject rather than guess a scale," applied as a closed allow-list
#: rather than an attempted scale-conversion. Extending this set is a deliberate, reviewed change
#: (a later phase's spec revision), never a silent widening inside normalize.py.
RECOGNIZED_XBRL_UNITS: frozenset[str] = frozenset({"USD", "shares"})


class FundamentalsFactRow(MizanBaseModel):
    """One normalized XBRL fact row, as it will be loaded into DuckDB's `fundamentals_facts` table.

    `cik` is the zero-padded 10-digit string form (matches `ingest_edgar.resolve_cik`'s return type
    and every EDGAR raw-cache key, PHASE_2_SPEC.md §6.3) — never the bare int `EdgarSubmissionRecord
    .cik` carries at the raw layer; Phase 3 is where that canonicalization is finalized for every
    downstream consumer.

    `taxonomy`, `tag`, and `unit` are NOT present on `mizan.data.models.EdgarFactRow` itself — they
    are the nesting keys (`facts.{taxonomy}.{tag}.units.{unit}`) the raw companyfacts JSON stores
    each fact object under (docs/modernization_log.md §6.1). `normalize_edgar_facts` (§6.1) carries
    them from the traversal into this row explicitly; losing them here would make the
    (cik, taxonomy, tag, unit, period_start, period_end, accn) uniqueness key (PHASE_1_SPEC.md §5's
    forward note) impossible to enforce.

    `period_start`/`period_end`/`is_instantaneous` replace the raw model's optional `start`/required
    `end`: DuckDB's PRIMARY KEY columns are NOT NULL by construction (verify against DuckDB 1.5.5's
    actual enforcement semantics before finalizing the DDL, §5), and a nullable key column is
    exactly the kind of engine-specific ambiguity (does NULL collide with NULL in a UNIQUE/PRIMARY
    KEY index, or not — SQLite and Postgres disagree with each other on this) this project's
    "verify, don't recall" discipline (docs/modernization_log.md §0) exists to catch. Rather than
    depend on that ambiguity, an instantaneous concept's raw `start=None` is normalized to
    `period_start = period_end` (a single-point period's start IS its end) with `is_instantaneous
    = True` preserving the original signal losslessly — no information is discarded, only
    re-expressed in a form with no nullable key column. `is_instantaneous = False` alongside a
    `period_start != period_end` marks an ordinary duration concept.

    `value` (not `val`) is a deliberate rename — PHASE_2_SPEC.md §3 named this exact rename as
    Phase 3's job ("Phase 3's normalizer maps these to ... typed DuckDB columns"); it is not a
    drift, it is the one place in the whole codebase where wire-format naming is intentionally left
    behind for a typed table's own naming convention.
    """

    cik: str
    taxonomy: str
    tag: str
    unit: str
    period_start: _Date
    period_end: _Date
    is_instantaneous: bool
    value: float
    accn: str
    fy: int
    fp: str
    form: str
    filed: _Date


class PriceBarRow(MizanBaseModel):
    """One normalized Tiingo EOD bar row, as it will be loaded into DuckDB's `price_bars` table.

    `raw_*`/`adj_*` naming is the exact typed-column contract `mizan.data.models.TiingoEodBar`'s own
    docstring already promised downstream ("Phase 3's normalizer maps these to `raw_close`/
    `adj_close` typed DuckDB columns") and `PHASE_2_SPEC.md` §7 guard G-T3 protects at the raw layer.
    `raw_close`/`adj_close` (and every other raw/adj pair) remain two independently-populated
    columns here — no function in this module, or any later phase, may derive one from the other or
    read one and call it "the close" (ULTIMATE_PRD.md §4.2 guard G-T3, carried through unbroken).
    """

    ticker: str
    trade_date: _Date
    raw_open: float
    raw_high: float
    raw_low: float
    raw_close: float
    volume: int
    adj_open: float
    adj_high: float
    adj_low: float
    adj_close: float
    adj_volume: int
    div_cash: float
    split_factor: float
```

**No 12th fiqh-register entry, no `Invariants` change.** Phase 3 introduces zero new `FiqhParam`
rows and zero new `Invariants` fields — normalization has no judgment call of its own (unit
allow-listing and the instantaneous-concept substitution above are engineering defaults stated as
code, not honesty-surface entries), same posture `PHASE_2_SPEC.md` §3 held for ingestion.

---

## §4 Public Interfaces / Function Signatures

### 4.1 `mizan/data/db.py` — DuckDB connection + idempotent schema

```python
class SchemaError(RuntimeError):
    """Raised when `ensure_schema` detects that an already-existing table's column set disagrees
    with what this module expects to create (a defensive check — see §5; V1 has no migration path,
    so a disagreement here means the DuckDB file was created by an incompatible earlier/later
    version of this module and must be regenerated from the raw cache, not silently altered)."""


def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open (creating if absent, per DuckDB's own `connect()` semantics, docs/modernization_log.md
    §5.4) the DuckDB database file at `db_path`, creating parent directories first. When
    `read_only=False` (the default, used by every Phase 3 write path), calls `ensure_schema(con)`
    before returning, so no caller can obtain a writable connection to a database missing either
    table. `read_only=True` (for Phase 4+ read-only consumers) skips schema creation — DuckDB's own
    read-only mode does not permit DDL anyway.
    """


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Idempotently `CREATE TABLE IF NOT EXISTS` both `fundamentals_facts` and `price_bars` (§5's
    DDL), including their PRIMARY KEY constraints. Never drops, alters, or re-creates an existing
    table. Safe to call on every `connect()` — the second and subsequent calls in a process (or
    across processes against the same file) are no-ops.
    """
```

### 4.2 `mizan/data/normalize.py`

```python
class UnrecognizedUnitError(RuntimeError):
    """Raised when an XBRL fact's unit key is outside `RECOGNIZED_XBRL_UNITS` (§3) —
    ULTIMATE_PRD.md §4.3's "reject rather than guess a scale," applied as a closed allow-list."""


class DuplicateFactRowError(RuntimeError):
    """Raised when a fact row's (cik, taxonomy, tag, unit, period_start, period_end, accn) key
    already exists in `fundamentals_facts` with a DIFFERENT `value`/`fy`/`fp`/`form`/`filed` than
    the incoming row — ULTIMATE_PRD.md §4.3's "duplicate/overlapping filing periods loaded twice ...
    violation raises, not upserts silently." An incoming row that is byte-identical to the existing
    row at the same key is NOT an error (§6.2's idempotent-replay dedup) — this exception fires only
    on a genuine value conflict at an existing key, surfaced from the DuckDB PRIMARY KEY constraint
    violation this indicates a bug in the dedup logic allowed through (§5, §7 G-N2/G-N3)."""


class DuplicatePriceBarError(RuntimeError):
    """Same contract as `DuplicateFactRowError`, for `price_bars`' (ticker, trade_date) key."""


def normalize_edgar_facts(
    cik: str, *, cache_dir: Path, con: duckdb.DuckDBPyConnection
) -> int:
    """Read the already-cached `edgar/companyfacts/{cik}.json` raw file (PHASE_2_SPEC.md §4.1,
    §6.2 — does NOT fetch; raises `NotIngestedError` if the file is absent, §7 G-N7), validate and
    flatten every fact object into a `FundamentalsFactRow` (rejecting via `UnrecognizedUnitError`
    on any unit outside `RECOGNIZED_XBRL_UNITS`), and bulk-load the rows that are new into
    `fundamentals_facts` (§6.1's dedup-then-insert logic). Returns the count of rows newly
    inserted — 0 on a fully-idempotent re-run over an already-normalized CIK.

    Scoped to `companyfacts` only for V1: `companyfacts` is a strict superset of any single
    `companyconcept` call for the same CIK (PHASE_2_SPEC.md §4.2's own docstring — companyconcept
    exists as a narrower *alternative* fetch, not additional data), and every ticker `mizan ingest`
    processes always fetches `companyfacts` (PHASE_2_SPEC.md §4.4's `run()` — companyconcept is
    never called from the CLI). Normalizing a companyconcept-only cache entry is out of scope (§9).
    """


def normalize_tiingo_bars(
    ticker: str, start_date: date, end_date: date, *, cache_dir: Path,
    con: duckdb.DuckDBPyConnection,
) -> int:
    """Read the already-cached `tiingo/eod/{ticker}_{start_date}_{end_date}.json` raw file
    (raises `NotIngestedError` if absent), validate every bar as `TiingoEodBar` (already done once
    at ingest time, PHASE_2_SPEC.md §6.2 — re-validated here since normalize treats the raw cache,
    not the ingest process's memory, as its only input), map each to a `PriceBarRow` preserving
    `raw_*`/`adj_*` as distinct columns (§3, §6.3), and bulk-load new rows into `price_bars`.
    Returns the count of rows newly inserted.
    """


class NotIngestedError(RuntimeError):
    """Raised by `normalize_edgar_facts`/`normalize_tiingo_bars` when the raw cache file they need
    does not exist — normalize.py never fetches; a missing raw file is a HALT (§7 G-N7), never a
    silent skip or an implicit live network call."""
```

**Offline CIK resolution — reused from Phase 2, not duplicated:**

```python
def resolve_cik_offline(ticker: str, *, cache_dir: Path) -> str:
    """Resolve `ticker` to its zero-padded CIK using ONLY the already-cached
    `edgar/company_tickers/company_tickers.json` file — no `httpx.Client` parameter exists on this
    function, structurally guaranteeing zero network capability (§7 G-N8).

    Raises `mizan.data.ingest_edgar.CikResolutionError` (Phase 2's own exception type, imported and
    reused, not redefined — this is the same *kind* of failure, just reached via a cache-only code
    path) if `company_tickers.json` is not cached at all, or if `ticker` is not found in it. Does
    NOT perform Phase 2's `resolve_cik`'s submissions-name cross-check (that check requires the
    submissions file, which `normalize_edgar_facts` reads independently and which the CLI, §4.3,
    already required `mizan ingest` to have populated first) — this function's only job is the
    ticker→CIK lookup Phase 3's CLI needs to locate the right cache files, not to re-run Phase 2's
    own drift detection a second time.
    """
```

### 4.3 `mizan/cli/main.py`, `mizan/cli/normalize.py`

```python
# mizan/cli/main.py — ONE new line added to build_parser(), no other change:
#     normalize_cli.add_subparser(subparsers)


# mizan/cli/normalize.py
def add_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Registers `normalize --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --cache-dir PATH --db-path PATH`. `--start-date`/`--end-date` must match
    the range originally passed to `mizan ingest` for that ticker (they select the Tiingo raw-cache
    file's key, PHASE_2_SPEC.md §6.2 — normalize does not scan the cache directory for "whatever
    range happens to be there"). `--db-path` has no default (same posture as `--cache-dir` in
    PHASE_2_SPEC.md §4.4: an operator must be explicit about where derived, regenerable analytical
    data lives, never a hidden default path).
    """


def run(args: argparse.Namespace) -> int:
    """Opens one DuckDB connection via `db.connect(args.db_path)` (schema ensured once, §4.1), then
    for each `--ticker`: `resolve_cik_offline`, then `normalize_edgar_facts`, then
    `normalize_tiingo_bars`, in that order. Catches `CikResolutionError` / `NotIngestedError` /
    `UnrecognizedUnitError` / `DuplicateFactRowError` / `DuplicatePriceBarError` per-ticker, prints a
    HALT message to stderr naming the ticker and the failure, and continues to the next ticker
    rather than aborting the whole batch — but returns a non-zero exit code if ANY ticker halted,
    mirroring `mizan.cli.ingest.run`'s exit-code contract (PHASE_2_SPEC.md §4.4) exactly. The
    DuckDB connection is closed (context-managed) before `run()` returns, on every exit path,
    including a halted one — never left open across the process boundary (§7 G-DB1).
    """
```

**Confirmed: no `httpx` import anywhere under `mizan/data/normalize.py`, `mizan/data/db.py`, or
`mizan/cli/normalize.py`.** Normalize is a pure cache-to-DuckDB transform with zero network
capability, structurally — not merely by convention (§7 G-N8, §8 AC's grep check).

---

## §5 Migrations

**This is the phase `PHASE_1_SPEC.md` §5 explicitly deferred DuckDB schema design to** ("DuckDB
schema design, table creation, and any migration tooling belong to Phase 3"). It also forward-
declared the fundamentals-fact uniqueness key: `(cik, taxonomy, tag, unit, start, end, accn)`.

**Divergence from the outer dispatch's own loosely-stated key, flagged rather than silently
resolved:** this dispatch's own framing described the target key informally as "(CIK, concept,
period, filed date)." The actual, already-locked key from `PHASE_1_SPEC.md` §5 and
`ULTIMATE_PRD.md` §4.3 is more precise and is what this document implements: `taxonomy` + `tag`
together are "concept" (SEC's XBRL splits a concept into a taxonomy namespace and a tag, e.g.
`us-gaap:Revenues`); `unit` is a necessary fourth axis the informal framing omitted (the same
`(cik, tag, period)` triple can legitimately appear under two different units, e.g. a per-share
concept vs its aggregate); and the discriminator for "same period reported in two filings" is
`accn` (the filing's own accession number), not `filed` — `filed` is deliberately excluded from the
key because the *same* `accn` is by definition filed on one date, so `accn` alone already captures
"which filing" without needing `filed` as a separate key column (see `PHASE_1_SPEC.md` §5: "`accn`
is required because the same reporting period is legitimately re-reported across filings"). This
document implements the `PHASE_1_SPEC.md` §5 key, not the dispatch's informal restatement of it,
because the former is the one Phase 1's own review already approved as the forward commitment.

### 5.1 `fundamentals_facts` DDL

```sql
CREATE TABLE IF NOT EXISTS fundamentals_facts (
    cik              VARCHAR NOT NULL,
    taxonomy         VARCHAR NOT NULL,
    tag              VARCHAR NOT NULL,
    unit             VARCHAR NOT NULL,
    period_start     DATE    NOT NULL,
    period_end       DATE    NOT NULL,
    is_instantaneous BOOLEAN NOT NULL,
    value            DOUBLE  NOT NULL,
    accn             VARCHAR NOT NULL,
    fy               INTEGER NOT NULL,
    fp               VARCHAR NOT NULL,
    form             VARCHAR NOT NULL,
    filed            DATE    NOT NULL,
    PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn)
);
```

### 5.2 `price_bars` DDL

```sql
CREATE TABLE IF NOT EXISTS price_bars (
    ticker       VARCHAR NOT NULL,
    trade_date   DATE    NOT NULL,
    raw_open     DOUBLE  NOT NULL,
    raw_high     DOUBLE  NOT NULL,
    raw_low      DOUBLE  NOT NULL,
    raw_close    DOUBLE  NOT NULL,
    volume       BIGINT  NOT NULL,
    adj_open     DOUBLE  NOT NULL,
    adj_high     DOUBLE  NOT NULL,
    adj_low      DOUBLE  NOT NULL,
    adj_close    DOUBLE  NOT NULL,
    adj_volume   BIGINT  NOT NULL,
    div_cash     DOUBLE  NOT NULL,
    split_factor DOUBLE  NOT NULL,
    PRIMARY KEY (ticker, trade_date)
);
```

**Build-time verification item (mechanical, not a judgment call):** `docs/modernization_log.md`
§5.4 documents DuckDB 1.5's connection/relation API surface but does not document PRIMARY KEY
constraint-violation behavior (does `INSERT` raise `duckdb.ConstraintException` on a PK collision,
by default, with no additional pragma?). Every column in both DDLs above is declared `NOT NULL`
specifically so this is a plain PK-collision question with no nullable-column ambiguity layered on
top — but the build agent must still verify DuckDB 1.5.5's actual raise-on-violation behavior
live (a one-line test: insert two rows with an identical PK and differing non-key values, assert an
exception is raised) before treating §7 G-N2/G-N3's "backstop" framing as load-bearing, and log the
confirmation in `docs/modernization_log.md` §5.4 rather than assuming Postgres/SQLite-familiar
semantics carry over unverified.

### 5.3 No versioned migration framework — a deliberate, stated V1 scope decision

Mizan's DuckDB file is a **derived, regenerable artifact** (`MASTER_PRD.md` §9.3, §5.3 — "raw file
cache upstream of DuckDB, for replayable/auditable ingestion"; the raw JSON cache is the source of
truth). For a single-developer, single-schema-version, locally-owned file, an in-place `ALTER
TABLE`-based migration framework (alembic-style versioned migrations) would add machinery this
project does not need: a schema change during V1 development is handled by deleting the (gitignored,
§8 AC5) DuckDB file and re-running `mizan normalize` from the still-intact, still-cached raw JSON —
`ensure_schema`'s idempotent `CREATE TABLE IF NOT EXISTS` is the entire migration story. This mirrors
`PHASE_2_SPEC.md` §2.2's "hand-written, inspectable logic over a generic library" reasoning, applied
to schema evolution instead of rate-limiting.

Any Phase 3 code that writes a Parquet file, or that alters/drops an existing table, is out of scope
and must be rejected by the review agent (§7, §9) — Parquet remains deferred (Phase 2's raw cache is
JSON, and Phase 3 reads that JSON directly into DuckDB rows; no intermediate Parquet stage exists in
V1).

---

## §6 Implementation Logic Flow

Function by function, deterministic anchors named explicitly, per the loop's audit requirement
(`PHASE_1_SPEC.md` §6.4's convention, restated by `PHASE_2_SPEC.md` §6).

### 6.1 `normalize_edgar_facts` — extraction, unit rejection, row construction

```
normalize_edgar_facts(cik, cache_dir, con):
    path = cache_path(cache_dir=cache_dir, source="edgar/companyfacts", key=cik)
    if not is_cached(path):
        raise NotIngestedError(f"CIK {cik}: no cached companyfacts — run `mizan ingest` first")
    data = read_raw_json(path)   # already validated once at ingest time; re-validated here (§9's
                                  # own "raw cache, not process memory, is the only input" posture)
    facts = data["facts"]
    rows: list[FundamentalsFactRow] = []
    for taxonomy, tags in facts.items():
        for tag, tag_body in tags.items():
            for unit, fact_list in tag_body.get("units", {}).items():
                if unit not in RECOGNIZED_XBRL_UNITS:
                    raise UnrecognizedUnitError(
                        f"CIK {cik} {taxonomy}:{tag}: unit {unit!r} is not in "
                        f"RECOGNIZED_XBRL_UNITS {sorted(RECOGNIZED_XBRL_UNITS)} — refusing to guess"
                    )
                for raw_fact in fact_list:
                    fact = EdgarFactRow.model_validate(raw_fact)   # Phase 2's model, reused verbatim
                    period_end = fact.end
                    is_instantaneous = fact.start is None
                    period_start = fact.end if is_instantaneous else fact.start
                    rows.append(FundamentalsFactRow(
                        cik=cik, taxonomy=taxonomy, tag=tag, unit=unit,
                        period_start=period_start, period_end=period_end,
                        is_instantaneous=is_instantaneous, value=fact.val, accn=fact.accn,
                        fy=fact.fy, fp=fact.fp, form=fact.form, filed=fact.filed,
                    ))
    return _bulk_load(con, table="fundamentals_facts", rows=rows,
                       key_columns=("cik", "taxonomy", "tag", "unit", "period_start",
                                    "period_end", "accn"))
```

The unit check runs **before** any row for that `(taxonomy, tag, unit)` triple is constructed —
consistent with EDGAR ingestion's own "validate before proceeding, HALT is immediate" posture
(`ULTIMATE_PRD.md` §4.1), and unlike Tiingo's anomaly scan (`PHASE_2_SPEC.md` §6.4), there is no
"write first, then raise" ordering question here: the raw file is already safely on disk from Phase
2's ingest (§9 — normalize never writes to the raw cache), so there is nothing at risk of being lost
by raising immediately.

### 6.2 `_bulk_load` — the dedup-then-insert-with-backstop pattern shared by both normalize functions

```
_bulk_load(con, table, rows, key_columns):
    if not rows:
        return 0
    table_arrow = pyarrow.Table.from_pylist([row.model_dump() for row in rows])
    con.register("_staging", table_arrow)
    key_match = " AND ".join(f"t.{c} = s.{c}" for c in key_columns)
    before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    con.execute(f"""
        INSERT INTO {table}
        SELECT s.* FROM _staging s
        WHERE NOT EXISTS (SELECT 1 FROM {table} t WHERE {key_match})
    """)
    after = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    con.unregister("_staging")
    return after - before
```

This is Phase 3's structural analogue of `PHASE_2_SPEC.md` §6.2's cache-hit-before-network-call
idempotency: **re-running `normalize_edgar_facts`/`normalize_tiingo_bars` over an already-fully-
normalized source inserts zero new rows** (§8 AC4) — the `WHERE NOT EXISTS` clause is evaluated per
incoming row against the table's actual current contents, so a byte-identical re-run is silently
(and correctly) a no-op. **This is deliberately not the same thing as tolerating a genuine
duplicate:** if the incoming staging row's key matches an existing row but the *non-key* columns
differ (a real anomaly — e.g. a bug upstream produced two different `value`s for what should be one
immutable historical fact), the `WHERE NOT EXISTS` clause as written would still skip it silently,
which is wrong per ULTIMATE_PRD.md §4.3. `_bulk_load` therefore additionally runs a pre-insert
conflict check restricted to key-column matches with a differing hash of the full row, raising
`DuplicateFactRowError`/`DuplicatePriceBarError` (naming the conflicting key and both values) before
the `INSERT` runs, whenever that narrower query finds any hit — the DDL's `PRIMARY KEY` constraint
(§5) is the last-resort backstop if this application-level check is ever itself wrong, not the
primary mechanism (a raised `duckdb.ConstraintException` at that point indicates a bug in this
function, and should be treated as one, not routed around).

### 6.3 `normalize_tiingo_bars` — raw/adjusted column-contract mapping

```
normalize_tiingo_bars(ticker, start_date, end_date, cache_dir, con):
    path = cache_path(cache_dir=cache_dir, source="tiingo/eod",
                       key=f"{ticker}_{start_date.isoformat()}_{end_date.isoformat()}")
    if not is_cached(path):
        raise NotIngestedError(f"{ticker} {start_date}..{end_date}: no cached Tiingo EOD data")
    bars_raw = read_raw_json(path)
    bars = [TiingoEodBar.model_validate(row) for row in bars_raw]   # Phase 2's model, reused
    rows = [
        PriceBarRow(
            ticker=ticker, trade_date=bar.date,
            raw_open=bar.open, raw_high=bar.high, raw_low=bar.low, raw_close=bar.close,
            volume=bar.volume,
            adj_open=bar.adjOpen, adj_high=bar.adjHigh, adj_low=bar.adjLow,
            adj_close=bar.adjClose, adj_volume=bar.adjVolume,
            div_cash=bar.divCash, split_factor=bar.splitFactor,
        )
        for bar in bars
    ]
    return _bulk_load(con, table="price_bars", rows=rows, key_columns=("ticker", "trade_date"))
```

Every `raw_*`/`adj_*` field is assigned from its own, distinctly-named `TiingoEodBar` attribute on
its own line — no shared local variable named `close` or `open` anywhere in this function body, so
there is no code path where a reviewer could mistake which one is being read (`ULTIMATE_PRD.md`
§4.2 guard G-T3, carried through into Phase 3 unbroken; `PHASE_2_SPEC.md` §7's own grep for this
already covers `mizan/data/`, so it now also covers this file for free — no new grep needed, §7).

### 6.4 Deterministic anchors this phase establishes

```
normalize_edgar_facts / normalize_tiingo_bars     Pure functions of the raw cache directory's
                                                    existing contents PLUS the DuckDB file's existing
                                                    contents at call time — no network, no clock, no
                                                    randomness. Given the same cache dir and the same
                                                    starting DuckDB state, always produce the same
                                                    resulting DuckDB state and the same return count.
resolve_cik_offline                                Pure function of the cached company_tickers.json
                                                    file's contents — no network (§7 G-N8).
db.ensure_schema                                   Idempotent: any number of calls against the same
                                                    connection produce the same schema as one call.
```

Normalization, unlike ingestion, touches **zero** non-deterministic external systems (§9 — no live
network call anywhere in this phase's new code) — it is closer in spirit to Phase 1's pure
config-validation determinism than to Phase 2's necessarily-network-touching cache-miss path. The
only mutable state is the DuckDB file itself, and every write to it is idempotent by construction
(§6.2).

---

## §7 Failure-Mode Guards

Pulled directly from `ULTIMATE_PRD.md` §4.3 (Normalization) and §4.5 (Storage/DuckDB).

| # | Failure mode (`ULTIMATE_PRD.md` source row) | Guard Phase 3's code implements | What the review agent checks |
|---|---|---|---|
| G-N1 | Silent type/unit-scale coercion across XBRL filings | `RECOGNIZED_XBRL_UNITS` closed allow-list (§3); `normalize_edgar_facts` raises `UnrecognizedUnitError` on any other unit key, before constructing a row | Test with a synthetic companyfacts fixture carrying a fact under unit `"USD/shares"` (or any string outside `{"USD","shares"}`), assert `UnrecognizedUnitError`. `grep -n "RECOGNIZED_XBRL_UNITS" mizan/data/normalize.py` — must be the single point of truth, no second ad-hoc unit check elsewhere |
| G-N2 | Duplicate/overlapping filing periods loaded twice, with conflicting values | `_bulk_load`'s pre-insert conflict check (§6.2) raises `DuplicateFactRowError`/`DuplicatePriceBarError` naming both values; the DuckDB `PRIMARY KEY` (§5) is the backstop | Test seeding `fundamentals_facts` with one row, then calling `normalize_edgar_facts` against a synthetic cache whose fact at the same key has a different `value`, assert the exception fires and the table's row count is unchanged (no silent overwrite) |
| G-N3 | A legitimate idempotent re-run mistaken for a duplicate error | `_bulk_load`'s `WHERE NOT EXISTS` dedup treats a byte-identical incoming row as a no-op, not an error | Test calling `normalize_edgar_facts` twice in a row against the same unchanged fixture and DB; assert the second call returns `0` and raises nothing (§8 AC4) |
| G-N4 | Adjusted-close / raw-close conflation surviving into the typed table | `PriceBarRow` keeps `raw_close`/`adj_close` (and every raw/adj pair) as independently-assigned fields (§6.3); no shared intermediate variable | `grep -rn "adj_close\|raw_close" mizan/data/normalize.py mizan/data/db.py` and manually confirm no call site aliases one to the other; extends `PHASE_2_SPEC.md` guard G-T3's grep scope |
| G-N5 | Datetime resolution mismatch across sources (pandas 3.0's `datetime64[us]` inference, `ULTIMATE_PRD.md` §4.3 NEW row) | Does not arise structurally in Phase 3: `pandas` is not imported anywhere in this phase (§2.2); both `EdgarFactRow`'s and `TiingoEodBar`'s date fields are already `datetime.date` (Pydantic-parsed at Phase 2's own layer) and are stored as DuckDB `DATE` columns directly, with no string or pandas round-trip in between | `grep -rn "^\s*(import\|from)\s+pandas" mizan/data/normalize.py mizan/data/db.py mizan/cli/normalize.py` — any hit is blocking. Inspect `fundamentals_facts`/`price_bars` DDL (§5) — every temporal column is `DATE`, never `VARCHAR`/`TIMESTAMP` |
| G-N6 | The `start=None` (instantaneous-concept) signal silently dropped by the `period_start=period_end` substitution (§3) | `is_instantaneous: bool` column preserves the original signal losslessly alongside the substitution | Test constructing a `FundamentalsFactRow` from a fact with `start=None`, assert `period_start == period_end` AND `is_instantaneous is True`; a duration fact asserts `is_instantaneous is False` and `period_start != period_end` (for any fixture where they differ) |
| G-N7 | `normalize_*` called for a CIK/ticker never ingested | `NotIngestedError` raised immediately, before any DuckDB write | Test calling `normalize_edgar_facts`/`normalize_tiingo_bars` against an empty cache dir, assert `NotIngestedError`, assert the DuckDB table row count is unchanged |
| G-N8 | Normalize silently gaining live network capability (e.g. a future edit reintroducing `resolve_cik`'s network path) | `resolve_cik_offline` has no `client`/`httpx` parameter at all; no file under this phase imports `httpx` | `grep -rn "httpx" mizan/data/normalize.py mizan/data/db.py mizan/cli/normalize.py` — any hit is blocking |
| G-DB1 | Concurrent-write conflict (DuckDB's one-writer-per-file lock) | `mizan/cli/normalize.py`'s `run()` holds exactly one connection for the whole batch, closed on every exit path; no retry loop around a lock failure | Test opening a second `db.connect()` against a DuckDB file already held open (not read-only) by a first connection in the same process, assert the underlying lock exception propagates and is not caught/retried anywhere in `mizan/data/db.py` or `mizan/cli/normalize.py` |
| G-DB2 | DuckDB file (or its `.wal` file) committed to git | `.gitignore` carries `*.duckdb` and `*.duckdb.wal` (§1, §5) | `git status --porcelain` after a test run producing a real DuckDB file shows it as ignored, not untracked-but-stageable; `git log --all --name-only` for this phase's commits contains no `*.duckdb`/`*.duckdb.wal` path |
| G-CLI2 | `mizan normalize` runs against an unverified foundation | `mizan/cli/main.py`'s `main()` (unchanged from Phase 2) calls `check_all()` before dispatching to ANY subcommand, `normalize` included — no per-subcommand duplication needed since the check already runs centrally | Run `mizan normalize ...` with a monkeypatched `INVARIANTS` violation, assert exit code 1 with the boot-check failure message, before any DuckDB file is created (assert the `--db-path` target does not exist afterward) |
| G-DEP3 | `duckdb`/`pyarrow` imported outside `mizan/data/{db,normalize}.py`; `pandas`/`matplotlib` imported anywhere at all | Only `mizan/data/db.py` and `mizan/data/normalize.py` import `duckdb`/`pyarrow` | `grep -rnE "^\s*(import\|from)\s+(duckdb\|pyarrow)" mizan/` — every hit must be in one of those two files. `grep -rnE "^\s*(import\|from)\s+(pandas\|matplotlib)" mizan/` — any hit anywhere is blocking, same as `PHASE_1_SPEC.md` G13/`PHASE_2_SPEC.md` G-DEP1, now re-run over the Phase 3 tree |
| G-LLM | LLM/model SDK or `yfinance` reachback | Forbidden-dependency list unchanged (§2.4) | `ULTIMATE_PRD.md` §5 checks 5 and 6, re-run over the expanded `mizan/` tree and `pyproject.toml` |
| G-AI | AI attribution in commit messages | Same neutral-commit convention as Phases 1–2 | `git log --format=%B` for this phase's commits — no `Co-Authored-By`, no "Generated with," no model/assistant name |

**Categorisation, mirroring `PHASE_1_SPEC.md` §7 / `PHASE_2_SPEC.md` §7:** G-N1, G-N2, G-N6, G-DB1,
G-DB2, G-LLM, G-AI are **HALT-for-human** (data-integrity, permissibility-adjacent, or honesty-surface
touching). G-N3, G-N4, G-N5, G-N7, G-N8, G-CLI2, G-DEP3 are blocking-but-mechanical: fix and re-run.

---

## §8 Phase Acceptance Criteria

Each concrete, independently checkable by a third party, same standard `PHASE_1_SPEC.md` §8 /
`PHASE_2_SPEC.md` §8 applied.

1. **Fixture normalization produces the expected typed rows.** Given a small fixture companyfacts
   JSON and a fixture Tiingo EOD JSON (both valid per Phase 2's own models), `normalize_edgar_facts`
   and `normalize_tiingo_bars` populate `fundamentals_facts`/`price_bars` with exactly the expected
   row count and spot-checked values (including at least one instantaneous and one duration
   concept, and at least one bar with a nonzero `div_cash`).
2. **A genuine duplicate-with-conflicting-values raises, never silently upserts.** Seeding one row
   then normalizing a synthetic fact at the identical key with a different `value` raises
   `DuplicateFactRowError`; the table's row count and the original row's value are both unchanged
   afterward.
3. **An unrecognized XBRL unit is rejected, not coerced.** A fact under a unit outside
   `{"USD", "shares"}` raises `UnrecognizedUnitError` before any row for that unit is constructed.
4. **Re-normalization is idempotent.** Calling `normalize_edgar_facts`/`normalize_tiingo_bars` a
   second time against an unchanged cache and an already-populated DuckDB file inserts zero new
   rows and raises nothing.
5. **The DuckDB file is never committed.** `.gitignore` covers `*.duckdb` and `*.duckdb.wal`;
   `git log --all --name-only` for this phase's commits contains no such path; `git status
   --porcelain` after a local test run producing a real DuckDB file under a project-relative path
   shows it ignored.
6. **`raw_close`/`adj_close` (and every other raw/adj pair) remain independently populated** in
   `price_bars` — no function anywhere in `mizan/data/` derives one from the other.
7. **`is_instantaneous` correctly reflects the raw model's `start` optionality**, and
   `period_start == period_end` exactly when `is_instantaneous is True`.
8. **Normalize has zero network capability.** No file under `mizan/data/normalize.py`,
   `mizan/data/db.py`, or `mizan/cli/normalize.py` imports `httpx`; `resolve_cik_offline` takes no
   client/network parameter.
9. **`normalize` on a never-ingested ticker/CIK halts, not silently skips.** `NotIngestedError` is
   raised, and the DuckDB table row counts are unchanged, when the cache directory holds no matching
   raw file.
10. **DuckDB single-writer contention surfaces as a raised error, not a retry loop.** A second
    connection attempt against a file already held open (non-read-only) by a first connection
    propagates the underlying lock exception; no `except`/retry wraps it in `mizan/data/db.py` or
    `mizan/cli/normalize.py`.
11. **Boot gate runs first.** `mizan normalize ...` under a deliberately-violated `Invariants`/
    `FiqhParams` instance (test-injected) exits 1 with the boot-check failure message before any
    DuckDB file is created.
12. **`ensure_schema` is idempotent.** Calling it twice against the same connection does not raise
    and leaves the schema (both tables, both PRIMARY KEY constraints) unchanged.
13. **Every new model inherits `MizanBaseModel`.** No file under `mizan/data/` or `mizan/cli/`
    imports or subclasses `pydantic.BaseModel` directly (same grep as Phases 1–2, re-run over the
    expanded tree).
14. **`mypy --strict mizan` exits 0.** `mypy --strict mizan tests` is also run and recorded; the
    already-documented, environment-specific global-numpy-stub/`pytest` interaction
    (`COMPREHENSION.md` §6) is not phase-blocking if re-confirmed isolated to that cause, same
    standard `PHASE_2_SPEC.md` AC14 applied. Building and verifying inside the project's `.venv`
    (already confirmed present and used as of the Phase 2 comprehension pass) is required, not
    merely encouraged, now that this phase adds a second real third-party runtime dependency
    (`duckdb`) with native extension components.
15. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5`.
16. **`pytest` passes in full**, all three new test files plus the full existing Phase 1 + Phase 2
    suite (no regression).
17. **No forbidden dependency anywhere**, including `duckdb==1.5.5` and `pyarrow==25.0.1` appearing
    nowhere else under a different name/alias; `ULTIMATE_PRD.md` §5 checks 5 and 6 clean over the
    expanded `mizan/` tree and `pyproject.toml`.
18. **No premature imports.** `pandas`/`matplotlib` are imported by no module under `mizan/`;
    `duckdb`/`pyarrow` are imported only by `mizan/data/db.py` and `mizan/data/normalize.py`.
19. **No Parquet, no schema alteration.** No `to_parquet`/`read_parquet` call anywhere under
    `mizan/data/`; no `ALTER TABLE`/`DROP TABLE` anywhere under `mizan/data/db.py`.
20. **Pins reconcile, with a fresh dated re-check logged.** `duckdb==1.5.5` and `pyarrow==25.0.1`
    (and every other pin) appear identically in `pyproject.toml` and `docs/modernization_log.md` §3,
    and §2.1's live re-check for this phase is logged there with today's date and the actual
    command/output used — not silently copied from the Step 10 entry.
21. **Commits are neutral.** No AI attribution in `git log` for this phase's commits.
22. **Boundary greps are clean**, re-run from repo root against the full tree including
    `mizan/data/normalize.py`, `mizan/data/db.py`, and `mizan/cli/normalize.py`
    (`ULTIMATE_PRD.md` §5 checks 1–8).

**Any single failing criterion is a phase-loop HALT, not a partial pass** — same standard
Phases 1–2 state, applied here.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 3)

- **No screening logic.** Nothing in Phase 3 computes a business-activity tier, a financial ratio,
  or a `Verdict`. `fundamentals_facts`/`price_bars` are queryable typed tables; nothing reads them
  yet. Phase 4's `screening/business_activity.py` and `screening/financial_ratios.py` are the first
  consumers.
- **No backtest engine, no compliance-flip state machine, no portfolio or strategy code, no
  `pandas` import.** → Phase 5. Per §2.2's reasoning, `pandas` is deferred to whichever of Phase 5
  or Phase 7 needs it first, not promoted speculatively here.
- **No purification logic.** `price_bars.div_cash` is stored, unchanged from Tiingo's own field, for
  Phase 6's `backtest/purification.py` to consume later; nothing in Phase 3 computes a purification
  amount.
- **No reporting, no `matplotlib` import.** → Phase 7.
- **No `screen | backtest | report` CLI subcommands.** `mizan/cli/` in Phase 3 registers `ingest`
  (unchanged) and `normalize` only.
- **No companyconcept-sourced normalization path.** `normalize_edgar_facts` reads `companyfacts`
  only (§4.2's own reasoning: it is a strict superset of any single companyconcept response for the
  same CIK, and the CLI never fetches companyconcept). A future phase needing the narrower
  companyconcept cache entries normalized would be an additive extension to this file, not a Phase 3
  deliverable.
- **No versioned migration framework.** §5.3's own stated V1 decision: idempotent
  `CREATE TABLE IF NOT EXISTS` is the entire migration story; a schema change is handled by
  regenerating the (gitignored, derived) DuckDB file from the raw cache, not by an in-place `ALTER`.
- **No Parquet, anywhere.** Phase 2's raw cache is JSON; Phase 3 reads that JSON directly into
  DuckDB rows with no intermediate Parquet stage.
- **No actual full historical normalization run as part of this automated build/review loop beyond
  small fixture-based tests.** Consistent with `PHASE_2_SPEC.md` §9's own precedent for the real
  ~100-ticker ingestion backfill: normalizing the real backfilled cache (once an operator has
  actually run one, with a real `TIINGO_API_TOKEN`, per Phase 2's own deferred operator action) is a
  one-time operator action to take after Phase 3 is reviewed and approved, not something this
  phase's automated acceptance criteria (§8) require.
- **No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3).** Unchanged from Phases 1–2 —
  these remain escalated to the human and are unrelated to normalization.
- **No LLM, ever, in any phase.** Restated per Phases 1–2's own restatement convention — a build
  agent might otherwise reach for "an LLM to guess a fact's likely correct unit scale" when a fact's
  unit is unrecognized. That instinct is wrong here specifically: an unrecognized unit is a
  **HALT-for-human** condition (§7 G-N1), never a guess, by the same reasoning `PHASE_2_SPEC.md` §9
  gave for malformed ingest data.
- **No change to the rebalance cadence surface, no HTTP API/service/dashboard.** Unchanged from
  Phases 1–2; normalization touches neither.

---
