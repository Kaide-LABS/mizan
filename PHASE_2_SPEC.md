# PHASE_2_SPEC.md — Mizan: Ingestion & Raw Cache (EDGAR + Tiingo)

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), the same document `PHASE_1_SPEC.md` was built from. Every dependency
> promotion, every schema decision, and every guard below traces to a section of that document,
> cited inline, cross-checked against `MASTER_PRD.md` where `ULTIMATE_PRD.md` is silent and against
> the committed Phase 1 code (`mizan/config/`, `mizan/core/`) for integration fidelity.

**Generated:** 2026-08-30 · **Dispatch type:** phase advancement (Phase 1 review-approved,
comprehension pass complete; no code review or fix loop runs in this dispatch) · **Canonical
references:** `ULTIMATE_PRD.md` (governs), `MASTER_PRD.md` (governs where ULTIMATE is silent),
`docs/modernization_log.md` (pinned external reality — §6.1 EDGAR, §6.2 Tiingo), `COMPREHENSION.md`
(what Phase 1 actually shipped, including its one open item — §6 below), `PHASE_1_SPEC.md` (format
and rigor precedent, and the public surface Phase 2 must not reshape).

**No citation re-verification gate applies to this document.** Mizan's arXiv citations are
background corroboration for design choices already settled by primary sources (AAOIFI methodology,
SEC/Tiingo API contracts), not phase-anchoring technical claims. This file carries no §0.5.

---

## §0 Phase Plan Header

# **Phase 2 of 7: Ingestion & Raw Cache (EDGAR + Tiingo)**

Phase sequence, unchanged from `PHASE_1_SPEC.md` §0 / `ULTIMATE_PRD.md` §6 (re-derived there, not
re-derived again here — nothing in the Phase 2 build changes the count or the ordering):

| # | Phase | Ships |
|---|---|---|
| 1 | Foundation & Config (done, approved) | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| **2** | **Ingestion & raw cache** ← *this document* | EDGAR (`companyfacts` + `companyconcept` + **`submissions`**) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store | raw → typed tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine | business-activity (tiered), financial ratios (30/30/5, two-axis denominator), verdict + reason trace, temporal-non-interference confinement check |
| 5 | Backtest engine + compliance-flip state machine | daily clock, portfolio, strategy interface, flip→grace→divest |
| 6 | Purification | side-ledger, `divCash`-driven, Forks A/B/C from config |
| 7 | Reporting | static HTML + matplotlib, caveats non-optional, gross vs net-of-purification |

This spec covers **Phase 2 only**. It is the contract the Phase 2 execution agent builds against and
the Phase 2 review agent (next round of Step 12) verifies against. Phase 2 **consumes** Phase 1's
public surface (`mizan.config.invariants.INVARIANTS`, `mizan.config.fiqh_params.FIQH_PARAMS`,
`mizan.core.base.MizanBaseModel`, `mizan.core.boot_check.check_all` — via
`mizan.config.boot_check.check_all`) and **must not reshape it**. Phase 2 may only extend Phase 1's
surface additively (it does not need to — no Phase 1 symbol requires a Phase 2 change). Every new
symbol Phase 2 introduces (`mizan.data.*`, `mizan.cli.*`) is itself now locked for Phases 3–7 the
same way.

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`.** Same flat layout `PHASE_1_SPEC.md` §1 established — no
nesting directory. The repo currently contains the Phase 1 tree plus `COMPREHENSION.md`; every file
below is new except `pyproject.toml` and `docs/modernization_log.md`, which Phase 2 **modifies**.

```
C:\Users\hp\HMS\
├── pyproject.toml                       # MODIFIED — httpx promoted to a real dependency (§2)
├── docs/
│   └── modernization_log.md             # MODIFIED — §6.1 httpx note (§2.3) gets its "re-check
│                                        #   at the start of Phase 2" line resolved and dated
├── mizan/
│   ├── data/
│   │   ├── __init__.py                  # NEW — empty
│   │   ├── models.py                    # NEW — raw row-shape Pydantic models (§3)
│   │   ├── raw_cache.py                 # NEW — shared replayable-cache helpers (§4.1, §6.2)
│   │   ├── ingest_edgar.py              # NEW — EDGAR client, rate limiter, CIK resolution (§4.2)
│   │   └── ingest_tiingo.py             # NEW — Tiingo client, request-budget limiter (§4.3)
│   └── cli/
│       ├── __init__.py                  # NEW — empty
│       ├── main.py                      # NEW — `mizan` console-script entrypoint + subparsers (§4.4)
│       └── ingest.py                    # NEW — the `ingest` subcommand (§4.4)
└── tests/
    ├── test_data_models.py              # NEW — row-shape schema validation, extra="forbid" drift
    ├── test_raw_cache.py                # NEW — idempotency/replayability (AC1), path determinism
    ├── test_ingest_edgar.py             # NEW — rate limiter timing, CIK resolution, HALT paths
    ├── test_ingest_tiingo.py            # NEW — budget limiter, corporate-action anomaly flagging
    └── test_cli_ingest.py               # NEW — boot-gate-first behaviour, exit codes
```

**Files explicitly NOT created in Phase 2:** `mizan/data/normalize.py`, `mizan/screening/`,
`mizan/backtest/`, `mizan/reporting/`, and no `screen`/`backtest`/`report` subcommands under
`mizan/cli/`. These are named in `MASTER_PRD.md` §9.4 and `ULTIMATE_PRD.md` §6 for Phases 3–7. See
§9.

**`mizan/data/raw_cache.py` justification (it is not named directly in `MASTER_PRD.md` §9.4's module
tree, which lists only `ingest_edgar.py` / `ingest_tiingo.py` / `normalize.py`):** the replayable
cache mechanics — path construction, cache-hit detection, atomic write — are identical in shape for
both ingestion legs even though their *rate-limiting* mechanics are deliberately different
(`ULTIMATE_PRD.md` §6, "the two ingestion jobs must not share one rate-limiter implementation").
Duplicating the cache-hit/write logic into both `ingest_edgar.py` and `ingest_tiingo.py` would let
the two copies drift on exactly the property (idempotent replay) that AC1 tests. One shared,
narrow, rate-limiter-agnostic module is the Phase-1-consistent choice (`mizan/core/` was justified
in `PHASE_1_SPEC.md` §1 on the same "one canonical home, decided now" reasoning).

**`mizan/cli/main.py` + `mizan/cli/ingest.py` as two files, not one:** `MASTER_PRD.md` §9.4 shows
`cli/` as a package holding `ingest | screen | backtest | report` — four verbs arriving over four
phases. `main.py` owns the top-level parser and is the one file every later phase's CLI addition
edits (to register its subparser); `ingest.py` owns only Phase 2's verb. This is additive-extension
by construction: Phase 3 adds `mizan/cli/screen.py` and one new line in `main.py`, never touches
`ingest.py`.

---

## §2 Dependencies

### 2.1 `httpx` promoted from optional to required

`PHASE_1_SPEC.md` §2.1 declared `httpx==0.28.1` under `[project.optional-dependencies].ingest`,
explicitly "NOT imported by any Phase 1 module... installing them in Phase 1 is harmless; importing
them in Phase 1 is a review-blocking finding." Phase 2 is the phase that imports it
(`mizan/data/ingest_edgar.py`, `mizan/data/ingest_tiingo.py`), so it is promoted to a core runtime
dependency, and the now-vestigial `ingest` extra is **removed** rather than left as a dead empty
group:

```toml
[project]
dependencies = [
    "pydantic==2.13.5",
    "httpx==0.28.1",
]

[project.optional-dependencies]
# `ingest` extra REMOVED — httpx is no longer forward-declared, it is a real Phase 2 dependency.
data = [
    "duckdb==1.5.5",
    "pyarrow==25.0.1",
    "pandas==3.0.5",
]
report = [
    "matplotlib==3.11.1",
]

[project.scripts]
mizan-boot-check = "mizan.config.boot_check:main"
mizan = "mizan.cli.main:main"
```

Version unchanged: `httpx==0.28.1` remains the pin. `docs/modernization_log.md` §3's note ("Re-check
at the start of Phase 2 — the first phase that actually imports `httpx`; if 1.0 has gone stable by
then, evaluate and log the decision here rather than silently bumping") is the action item this
phase's build agent must actually perform: re-check PyPI for `httpx` on the Phase 2 build date, and
either confirm `0.28.1` is still latest-stable or log a deliberate, dated re-pin decision in
`docs/modernization_log.md` §3 — **never a silent bump**, per that file's own governing rule (§1: "no
version number appears in this file without a verification date and a source URL").

`docs/modernization_log.md`'s §6.1/§6.2 external-contract tables (EDGAR rate limit, required
headers, endpoint shapes; Tiingo endpoint, auth, rate-limit metrics, free-tier caps) are already
verified and dated 2026-08-30 — Phase 2 reads them as settled inputs and does not re-verify them
again unless the build agent's own live testing contradicts them, in which case the contradiction
is logged there per that file's own reconciliation rule (§0 of that file), not silently absorbed.

### 2.2 No new dependency for rate-limiting/backoff

**Decision: stdlib suffices, no new dependency.** Both rate-limiting mechanisms Phase 2 needs are
simple enough that a dedicated library (`tenacity`, `ratelimit`, etc.) would add a dependency for a
handful of lines of `time.monotonic()`/`time.sleep()` bookkeeping, and — more importantly — would
put a third-party retry/backoff *policy* underneath a project whose failure-mode analysis
(`ULTIMATE_PRD.md` §4.1–§4.2) is explicit and unusual on exactly this point: EDGAR's correct
recovery is **not** exponential backoff (a generic retry library's default), it is a flat ≥600s
wait at zero request rate; Tiingo needs **no** per-request backoff at all, only a request-budget
counter. A generic retry decorator's defaults are the wrong shape for both legs. Hand-written,
inspectable timing logic (§6.1, §6.2) keeps the actual policy readable in the diff, the same
rationale `PHASE_1_SPEC.md` §6.1 gave for hand-written invariant checks over a generic loop.

### 2.3 Forbidden-dependency list unchanged

`PHASE_1_SPEC.md` §2.5's permanently forbidden list (`openai`, `anthropic`, every other LLM/model
SDK, `yfinance`) still applies, unmodified, to every file this phase adds. It is re-stated, not
re-derived, because it is permanent (`ULTIMATE_PRD.md` §5).

### 2.4 Modernization-log reconciliation (a Phase 2 deliverable)

Same discipline as `PHASE_1_SPEC.md` §2.4: every version string in `pyproject.toml` must appear
identically in `docs/modernization_log.md` §3–§4 (already true for `httpx==0.28.1`, no change
needed there beyond the re-check note in §2.1 above). A mismatch is a review-blocking finding.

---

## §3 Pydantic Schemas

Every new model inherits `mizan.core.base.MizanBaseModel` (`extra="forbid"`, `frozen=True`,
`validate_default=True`) — no Phase 2 module subclasses `pydantic.BaseModel` directly, same as
Phase 1's guard G8. All four models below live in `mizan/data/models.py`.

**These are raw row-shape schemas, not normalized typed tables.** They validate the *shape* of data
as it arrives from EDGAR/Tiingo — rejecting upstream drift loudly instead of caching garbage
silently — and they are what gets written to and read back from the replayable cache. Mapping raw
wire fields to Phase 3's normalized, unit-scaled, snake_case DuckDB columns is explicitly **not**
this phase's job (`ULTIMATE_PRD.md` §6, `data/normalize.py`).

**Wire-format field names are kept verbatim** (camelCase where SEC/Tiingo use camelCase), not
renamed to snake_case at this layer. A renamed field here is exactly the kind of silent reshaping
that breaks "prove what the data said" (`MASTER_PRD.md` §5.3) — if a build agent ever wants to
rename a field in `models.py` "for consistency," that is itself a review-blocking finding. This
means `ruff`'s `N815` (mixed-case attribute in class scope) and, for one Tiingo field, `A003`
(class attribute shadows a builtin: `open`) fire on these models **by design**; suppress with a
targeted `# noqa: N815` / `# noqa: A003` on each affected line, never by relaxing the ruleset.

```python
"""mizan/data/models.py — raw row-shape schemas for Phase 2 ingestion.

Field-shape sources: docs/modernization_log.md §6.1 (EDGAR, verified live 2026-08-30 against CIK
0000320193) and §6.2 (Tiingo, verified against public docs 2026-08-30).
"""

from __future__ import annotations

from datetime import date as _Date

from mizan.core.base import MizanBaseModel


class CompanyTickerEntry(MizanBaseModel):
    """One row of https://www.sec.gov/files/company_tickers.json.

    The wire format is a JSON OBJECT keyed by stringified index (`{"0": {...}, "1": {...}, ...}`),
    NOT an array — `ingest_edgar.py` iterates `.values()` when parsing; this model describes one
    value, not the envelope. `cik_str` is an int despite the name (verified: 10,391 entries, all
    int) — this model does not zero-pad it; that happens at the call site (§6.3), not in the schema,
    so the raw cache stores exactly what SEC sent, unmodified.
    """

    cik_str: int
    ticker: str
    title: str


class EdgarFactRow(MizanBaseModel):
    """One fact object from an XBRL `companyfacts` or `companyconcept` response.

    Field set verified live 2026-08-30: `{start?, end, val, accn, fy, fp, form, filed, frame?}`.
    `start` is present on duration concepts (e.g. revenue-over-a-period), absent on instantaneous
    ones (e.g. total-assets-at-a-point). `frame` is optional and often absent.

    `extra="forbid"` (inherited) is the concrete mechanism behind guard G-E7 (§7): if SEC adds,
    removes, or renames a fact-object key, parsing raises `pydantic.ValidationError` instead of the
    key being silently dropped or `None`-filled.

    `filed` is the point-in-time key Phase 4's temporal-non-interference confinement check
    (`ULTIMATE_PRD.md` §3.3, §4.4) depends on existing, byte-for-byte, on every cached fact — Phase 2
    must never drop or reformat it beyond ISO-date parsing.
    """

    start: _Date | None = None
    end: _Date
    val: float
    accn: str
    fy: int
    fp: str
    form: str
    filed: _Date
    frame: str | None = None


class EdgarSubmissionRecord(MizanBaseModel):
    """The subset of https://data.sec.gov/submissions/CIK##########.json Phase 2 reads.

    Deliberately NOT a full mirror of the submissions payload, which carries dozens of fields Mizan
    never uses (addresses, former names, filing history, ...). Modeling only the fields Phase 2
    consumes keeps `extra="forbid"` meaningful here rather than forcing every unrelated SEC field to
    be declared. The on-disk raw cache file still stores SEC's full JSON response verbatim (§6.2) —
    this model validates the slice `ingest_edgar.py` actually reads out of it (principally `sic`,
    for the business-activity first-pass signal Phase 4 will use), not the cache file's contents.
    """

    cik: int
    entityType: str  # noqa: N815 — wire-format verbatim, see module docstring
    sic: str
    sicDescription: str  # noqa: N815
    name: str
    tickers: tuple[str, ...]
    exchanges: tuple[str | None, ...]


class TiingoEodBar(MizanBaseModel):
    """One daily bar from Tiingo's EOD endpoint.

    Field set verified 2026-08-30: `{date, open, high, low, close, volume, adjOpen, adjHigh,
    adjLow, adjClose, adjVolume, divCash, splitFactor}`.

    `close` and `adjClose` are two DISTINCT required fields, never collapsed into one ambiguous
    `close` — this is the schema-level guard against the adjusted/raw-close conflation failure mode
    (`ULTIMATE_PRD.md` §4.2, guard G-T3, §7). Phase 3's normalizer maps these to `raw_close`/
    `adj_close` typed DuckDB columns; Phase 2's job is only to guarantee both survive, distinctly,
    from the moment of ingest — no code path in this phase may read one and call it "the close."
    """

    date: _Date
    open: float  # noqa: A003 — wire-format verbatim, shadows the builtin `open()` by design
    high: float
    low: float
    close: float
    volume: int
    adjOpen: float  # noqa: N815
    adjHigh: float  # noqa: N815
    adjLow: float  # noqa: N815
    adjClose: float  # noqa: N815
    adjVolume: int  # noqa: N815
    divCash: float  # noqa: N815
    splitFactor: float  # noqa: N815


class TiingoCorporateActionEvent(MizanBaseModel):
    """A DERIVED view of one `TiingoEodBar`'s corporate-action fields, used only by the anomaly
    flagging check in §6.4 (`ULTIMATE_PRD.md` §4.2, "missing divCash on a known ex-dividend date").

    Not independently fetched and not written to the raw cache on its own — the raw cache stores
    `TiingoEodBar` rows (the full response, §6.2). This model exists so the anomaly detector has a
    small, explicit, unit-testable shape to operate over instead of reaching into `TiingoEodBar`'s
    full field set ad hoc. Constructed only via `from_bar`.
    """

    trade_date: _Date
    div_cash: float
    split_factor: float

    @classmethod
    def from_bar(cls, bar: "TiingoEodBar") -> "TiingoCorporateActionEvent":
        return cls(trade_date=bar.date, div_cash=bar.divCash, split_factor=bar.splitFactor)
```

**No 12th-entry, no fiqh-register change.** Phase 2 introduces zero new `FiqhParam` rows and zero
new `Invariants` fields — ingestion has no judgment calls of its own; it is a mechanical data-fetch
layer. Any attempt to encode a "which data source to trust" or "how many years to backfill" choice
as a fiqh-register entry is out of scope (§9) — those are engineering defaults, stated as plain
function-default arguments (§4), not honesty-surface entries.

---

## §4 Public Interfaces / Function Signatures

### 4.1 `mizan/data/raw_cache.py` — shared replayable-cache helpers

```python
class RawCacheError(RuntimeError):
    """Raised on a cache-layer inconsistency (e.g. a cached file that fails to parse as JSON)."""


def cache_path(*, cache_dir: Path, source: str, key: str, ext: str = "json") -> Path:
    """Deterministic path for one cached artifact.

    Args:
        cache_dir: the ingestion job's cache root (CLI-supplied, §4.4).
        source: one of "edgar/company_tickers", "edgar/companyfacts", "edgar/companyconcept",
            "edgar/submissions", "tiingo/eod" — a fixed, closed set (§6.2); not free-form, so the
            directory layout is predictable and grep-able for a review agent.
        key: the cache key proper — e.g. a zero-padded CIK for EDGAR legs, or
            f"{ticker}_{start_date.isoformat()}_{end_date.isoformat()}" for Tiingo — NEVER the raw
            request URL and NEVER including any token/credential (ULTIMATE_PRD.md §4.2 NEW row:
            "API token leaked into the on-disk raw cache").
        ext: file extension, "json" for every Phase 2 artifact (no Parquet yet — see §9).

    Returns: cache_dir / source / f"{key}.{ext}", constructed with pathlib only (no string
    concatenation), so the same (source, key) always yields the same Path across processes and OSes.
    """


def is_cached(path: Path) -> bool:
    """True iff `path` exists and is non-empty. The sole idempotency check every ingest function
    calls before making any HTTP request (§6.2) — this function performs no I/O beyond `stat()`."""


def write_raw_json(path: Path, payload: bytes) -> None:
    """Write `payload` to `path` atomically (write to `path.with_suffix(path.suffix + ".tmp")`,
    then `os.replace`), creating parent directories as needed. `payload` is the raw response body
    exactly as received — no re-serialization, no key reordering, no pretty-printing that could
    diverge from what the source actually sent (MASTER_PRD.md §5.3, "I can prove what the data
    said"). Row-shape validation (§3) happens on READ, not on write, so the cache is a faithful
    record even in the rare case a row-shape model needs a fix later (ULTIMATE_PRD.md §6, "later
    phases must reprocess raw, not re-fetch").
    """


def read_raw_json(path: Path) -> dict[str, object]:
    """Read and `json.loads` the cached file. Raises RawCacheError (wrapping the underlying
    JSONDecodeError) on a corrupt cache file — never returns a partial/best-effort parse."""
```

### 4.2 `mizan/data/ingest_edgar.py`

```python
class CikResolutionError(RuntimeError):
    """Raised when a ticker cannot be resolved to a CIK, or the resolved CIK's submissions `name`
    does not match company_tickers.json's `title` for that ticker (ULTIMATE_PRD.md §4.1)."""


class MissingCompanyFactsError(RuntimeError):
    """Raised when a CIK's companyfacts response is empty or has no `facts` key at all."""


class MissingSicError(RuntimeError):
    """Raised when a CIK's submissions record is missing or carries no `sic` key."""


class EdgarBlockedError(RuntimeError):
    """Raised on an HTTP 403 received with a well-formed, fully-declared request. Per
    ULTIMATE_PRD.md §4.1, a 403 on a correct request means the header contract itself broke — this
    is NOT retried into a longer block; it halts immediately."""


def fetch_company_tickers(*, cache_dir: Path, client: httpx.Client) -> Path:
    """Fetch (or return the cached copy of) https://www.sec.gov/files/company_tickers.json.
    Cache-hit short-circuits with zero HTTP requests (AC1). Returns the cache path."""


def resolve_cik(ticker: str, *, cache_dir: Path, client: httpx.Client) -> str:
    """Resolve `ticker` to a zero-padded 10-digit CIK string (e.g. "0000320193").

    Calls fetch_company_tickers() first (cache-aware), looks up `ticker` case-insensitively among
    the parsed CompanyTickerEntry rows, zero-pads via f"{cik_str:010d}", then cross-checks: fetches
    (cache-aware) that CIK's submissions record and compares its `name` against the matched entry's
    `title`. A normalized-string mismatch raises CikResolutionError (ULTIMATE_PRD.md §4.1's
    "ticker→CIK drift, e.g. post-merger" guard). A ticker absent from company_tickers.json also
    raises CikResolutionError.
    """


def ingest_edgar_submissions(cik: str, *, cache_dir: Path, client: httpx.Client,
                              force_refetch: bool = False) -> Path:
    """Fetch (or return cached) https://data.sec.gov/submissions/CIK{cik}.json.

    Raises MissingSicError if the parsed EdgarSubmissionRecord's `sic` is empty/absent. Returns
    the cache Path on success. `force_refetch=True` bypasses the cache-hit short-circuit — the one
    parameter this function has purely for operator-driven re-pulls; no production call site
    (§4.4's CLI) sets it True by default.
    """


def ingest_edgar_companyfacts(cik: str, *, cache_dir: Path, client: httpx.Client,
                               force_refetch: bool = False) -> Path:
    """Fetch (or return cached) https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json.

    Raises MissingCompanyFactsError if the response has no `facts` key or `facts` is empty.
    Every fact object under `facts.{taxonomy}.{tag}.units.{unit}` is validated against
    EdgarFactRow on read (not on write, §4.1) — a shape drift raises pydantic.ValidationError,
    surfaced to the caller unwrapped (this is the "malformed/undocumented XBRL tag drift" guard,
    ULTIMATE_PRD.md §4.1).
    """


def ingest_edgar_companyconcept(cik: str, taxonomy: str, tag: str, *, cache_dir: Path,
                                 client: httpx.Client, force_refetch: bool = False) -> Path:
    """Fetch (or return cached) https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/
    {tag}.json. Same validation/HALT contract as ingest_edgar_companyfacts. Named separately per
    ULTIMATE_PRD.md §6's phase-ships line ("companyfacts + companyconcept + submissions") — Phase 4
    may prefer the narrower companyconcept call for a single tag rather than the full companyfacts
    dump; both are cached identically.
    """
```

**EDGAR rate limiter** (module-private, no public API — an implementation detail of the four
functions above, all of which route their HTTP calls through it):

```python
class _EdgarRateLimiter:
    """Enforces ULTIMATE_PRD.md §4.1's EDGAR policy: >=0.12s spacing between requests; on a 429 (or
    a 403 that is NOT a well-formed-request case, i.e. any 403 the caller has not already ruled out
    via EdgarBlockedError's immediate-halt path), sleep >=600s at zero request rate before the next
    attempt, flooring any Retry-After header at 600 rather than trusting a shorter value."""

    def wait_for_slot(self) -> None: ...
    def note_block(self, retry_after_seconds: float | None) -> None: ...
```

### 4.3 `mizan/data/ingest_tiingo.py`

```python
class TiingoUniverseDriftError(RuntimeError):
    """Raised when the running ticker universe for the current calendar month would exceed the
    500-unique-symbols/month cap (ULTIMATE_PRD.md §4.2) — indicates universe drift, not transient
    load, per that section's categorization; never auto-retried."""


class SuspectedCorporateActionAnomalyError(RuntimeError):
    """Raised when ingest_tiingo_eod's anomaly scan (§6.4) finds a splitFactor discontinuity with
    no matching divCash on the same date — ULTIMATE_PRD.md §4.2's "missing divCash on a known
    ex-dividend date" guard, deliberately conservative (some flagged rows will be ordinary splits,
    not missed dividends; a false-positive flag is cheap, a silently-missed dividend is not)."""


def ingest_tiingo_eod(ticker: str, start_date: date, end_date: date, *, cache_dir: Path,
                       token: str, client: httpx.Client, force_refetch: bool = False) -> Path:
    """Fetch (or return cached) one ranged GET to
    https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate=...&endDate=....

    Sends `token` via the `Authorization: Token {token}` header, never `?token=` in the URL
    (ULTIMATE_PRD.md §4.2 NEW row) — the cache key (§4.1) is (ticker, start_date, end_date), which
    never contains the token, so grepping the cache directory or any logged URL for the token value
    finds nothing by construction.

    Before issuing the request, consumes one unit from the module-level `_TiingoBudget` (§6.3) and
    registers `ticker` against the current calendar month's unique-symbol log (raising
    TiingoUniverseDriftError if this ticker is new to the month and the running count would exceed
    500). After a successful fetch, parses every bar as TiingoEodBar (§3) and runs the anomaly scan
    (§6.4), raising SuspectedCorporateActionAnomalyError if any bar is flagged — the response is
    still written to the raw cache first (a flagged anomaly is a "look at this," not "discard
    this"), then the exception is raised so the caller (the CLI, §4.4) surfaces it rather than
    silently proceeding.
    """
```

**Tiingo request-budget limiter** (module-private):

```python
class _TiingoBudget:
    """Tracks hourly (reset on the hour) and daily (reset at UTC-adjusted midnight EST) request
    counts, per ULTIMATE_PRD.md §4.2: the binding limits are 50 requests/hour and 1,000/day — NOT
    a per-symbol or per-second limit; Tiingo explicitly does not rate-limit to the second."""

    def consume(self) -> None:
        """Blocks (sleeps) until a slot is available if the hourly or daily budget is currently
        exhausted, sleeping to the next hour boundary — matches ULTIMATE_PRD.md §4.2's
        categorization of budget exhaustion as Auto-retryable, in contrast to EDGAR's HALT-style
        403 case."""
```

### 4.4 `mizan/cli/main.py`, `mizan/cli/ingest.py`

```python
# mizan/cli/main.py
def build_parser() -> argparse.ArgumentParser:
    """Top-level `mizan` parser. Registers one subparser per verb; Phase 2 registers only
    `ingest` (mizan.cli.ingest.add_subparser). Phases 3-7 each add one line here for their verb —
    this file is the one place later phases touch in mizan/cli/, per §1's additive-extension note.
    """


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entrypoint (`mizan`, registered in pyproject.toml). Parses argv, dispatches
    to the selected subcommand's run_*(args) function, returns its exit code. Per PHASE_1_SPEC.md
    §4.1's own stated requirement for every later phase's CLI entrypoint: calls
    `mizan.config.boot_check.check_all()` FIRST, before dispatching to any subcommand, and exits 1
    immediately (printing to stderr, same format as mizan-boot-check) if it raises — no subcommand
    ever runs against an unverified foundation.
    """


# mizan/cli/ingest.py
def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Registers `ingest --ticker TICKER [--ticker TICKER ...] --start-date YYYY-MM-DD
    --end-date YYYY-MM-DD --cache-dir PATH [--tiingo-token TOKEN] [--force-refetch]`.
    `--tiingo-token` defaults to reading the `TIINGO_API_TOKEN` environment variable if omitted —
    never a hardcoded default, never logged.
    """


def run(args: argparse.Namespace) -> int:
    """For each --ticker: resolve_cik, then ingest_edgar_submissions, ingest_edgar_companyfacts,
    and ingest_tiingo_eod, in that order (SIC/companyfacts before prices, so a HALT on the EDGAR leg
    is caught before spending Tiingo request budget on a ticker that will end up `unanalyzed`
    anyway). Catches CikResolutionError / MissingCompanyFactsError / MissingSicError /
    EdgarBlockedError / TiingoUniverseDriftError / SuspectedCorporateActionAnomalyError per-ticker,
    prints a HALT message to stderr naming the ticker and the failure, and continues to the next
    ticker rather than aborting the whole batch — but returns a non-zero exit code if ANY ticker
    halted, so the CLI's own exit code is the machine-readable "not every ticker ingested cleanly"
    signal, exactly mirroring `mizan-boot-check`'s exit-code contract (PHASE_1_SPEC.md §4.1).
    """
```

**Is Phase 2 where the first real CLI entrypoint appears? Yes, deliberately, per the plan already
committed in `PHASE_1_SPEC.md` §0 and `ULTIMATE_PRD.md` §6**: "Phase 2 creates `mizan/cli/` with
`mizan ingest`." The alternative (deferring all CLI to a later orchestration phase) was already
considered and rejected in Phase 1's own spec — re-litigating it here would contradict a decision
Phase 1's review already approved. `mizan-boot-check` remains a separate, standalone console script
(not folded into `mizan boot-check`) — it is a low-level fail-fast primitive useful before any
phase-specific verb exists, and `PHASE_1_SPEC.md` locked its name; renaming it is out of scope.

---

## §5 Migrations

**N/A in Phase 2**, confirmed explicitly, same as `PHASE_1_SPEC.md` §5's own confirmation for
Phase 1.

DuckDB schema design, table creation, and any migration tooling belong to **Phase 3**
(Normalization & DuckDB store), per `ULTIMATE_PRD.md` §6. Phase 2 introduces no database and no
schema of any kind — its only persistent artifact is the flat-file replayable raw cache (§4.1),
which is JSON, not a database, and carries no migration concept (a cache file is either present,
absent, or corrupt — there is no schema version to migrate between).

Any Phase 2 code that opens a DuckDB connection, imports `duckdb`, or writes a Parquet file is out
of scope and must be rejected by the review agent (§7, §9) — Parquet specifically is deferred: Phase
2's raw cache is JSON-only (§4.1's `cache_path` fixes `ext="json"`), even though `pyarrow` is already
an installed `data` extra; using it in Phase 2 would be exactly the "premature import" failure mode
`PHASE_1_SPEC.md` §7 guard G13 named for Phase 1, restated here for Phase 2's own forward-declared
extras (`duckdb`, `pyarrow`, `pandas`, `matplotlib` remain untouched by this phase).

---

## §6 Implementation Logic Flow

Function by function, deterministic anchors named explicitly, per the loop's audit requirement
(`PHASE_1_SPEC.md` §6.4's own convention).

### 6.1 EDGAR rate limiting / backoff (`_EdgarRateLimiter`)

```
wait_for_slot():
    now = time.monotonic()
    elapsed = now - self._last_request_at
    if elapsed < 0.12:
        time.sleep(0.12 - elapsed)
    self._last_request_at = time.monotonic()

note_block(retry_after_seconds):
    wait = max(retry_after_seconds or 0, 600)
    time.sleep(wait)
    self._last_request_at = time.monotonic()
```

Every EDGAR HTTP call in `ingest_edgar.py` calls `wait_for_slot()` immediately before the request
and, on receiving a 429, calls `note_block()` and retries **once** — a second consecutive block
after an already-served 600s cooldown is treated as `EdgarBlockedError` (HALT), not an infinite
retry loop, per `ULTIMATE_PRD.md` §4.5's general principle ("a retry loop against a lock held by a
stuck job is an infinite hang, not a recovery") applied here to a still-blocked remote endpoint. A
plain 403 on a request already carrying all three required headers (§6.3) is never retried — it
raises `EdgarBlockedError` immediately, because a 403 there means the header contract itself is
broken, not that the request rate was too high (`ULTIMATE_PRD.md` §4.1).

### 6.2 Replayable raw-cache write logic (`raw_cache.py`, consumed by both ingestion legs)

```
for each ingest_* function:
    path = cache_path(cache_dir=..., source=..., key=...)
    if is_cached(path) and not force_refetch:
        return path                      # zero HTTP requests issued — the idempotency property AC1 tests
    response = <rate-limited HTTP GET>
    <row-shape validation, if this leg validates on fetch (EDGAR: yes; Tiingo: yes)>
    write_raw_json(path, response.content)
    return path
```

This is the single shape every one of `fetch_company_tickers`, `resolve_cik` (via its two internal
fetches), `ingest_edgar_submissions`, `ingest_edgar_companyfacts`, `ingest_edgar_companyconcept`,
and `ingest_tiingo_eod` follows. **Re-running ingestion for an already-cached ticker/CIK must not
silently re-fetch** — the `is_cached` check runs *before* the rate limiter is touched at all, so a
fully-cached batch run issues literally zero HTTP requests and completes in well under a second,
independent of network conditions. This is Phase 2's provable idempotency property (§8 AC1).

### 6.3 CIK-resolution logic (`resolve_cik`)

```
resolve_cik(ticker):
    tickers_path = fetch_company_tickers(...)                 # cache-aware
    entries = [CompanyTickerEntry(**v) for v in json.loads(read)['values-or-dict-values']]
    match = next((e for e in entries if e.ticker.upper() == ticker.upper()), None)
    if match is None:
        raise CikResolutionError(f"{ticker!r} not found in company_tickers.json")
    cik10 = f"{match.cik_str:010d}"                            # zero-padded to 10 digits, per
                                                                # docs/modernization_log.md §6.1
    submissions_path = ingest_edgar_submissions(cik10, ...)    # cache-aware
    record = EdgarSubmissionRecord(**json.loads(read))
    if not _names_match(record.name, match.title):
        raise CikResolutionError(
            f"{ticker!r}: company_tickers.json title {match.title!r} vs "
            f"submissions name {record.name!r} — possible CIK drift (merger/rename)"
        )
    return cik10
```

`_names_match` is a simple, explicit, case/whitespace/legal-suffix-insensitive comparator (e.g.
uppercase, strip, collapse "CORP"/"CORPORATION"/"INC"/"INC." variants) — written out by hand, not
via a fuzzy-match library, because a false-negative here (a real mismatch waved through) is exactly
the drift `ULTIMATE_PRD.md` §4.1 wants caught, and a fuzzy-match library's tunable threshold would
hide the actual comparison rule the review agent needs to be able to read.

### 6.4 Tiingo corporate-action anomaly scan (`ingest_tiingo_eod`, post-fetch)

```
events = [TiingoCorporateActionEvent.from_bar(b) for b in parsed_bars]
flagged = [e for e in events if e.split_factor != 1.0 and e.div_cash == 0.0]
if flagged:
    raise SuspectedCorporateActionAnomalyError(
        f"{ticker}: {len(flagged)} date(s) with a splitFactor discontinuity and no matching "
        f"divCash: {[e.trade_date.isoformat() for e in flagged]}"
    )
```

The raw response is written to cache (§6.2) **before** this check runs, so a flagged run's data is
still on disk for a human to inspect — the exception halts the *ingestion job's* success signal, not
the cache write. This is deliberately conservative per `SuspectedCorporateActionAnomalyError`'s own
docstring (§4.3): an ordinary stock split with no accompanying dividend will also flag. Phase 2 does
not attempt to distinguish "expected split" from "suspected missed dividend" — that requires a
reference corporate-actions signal Phase 2 has no access to; it surfaces every candidate to a human,
per `ULTIMATE_PRD.md` §4.2's HALT-for-human categorization, rather than guessing.

### 6.5 Deterministic anchors this phase establishes

Ingestion is, by its nature, **not** a pure function of fixed inputs the way Phase 1's config
singletons are — it reads the network. `PHASE_1_SPEC.md` §6.4 named the absence of anything to
anchor as itself the point for Phase 1; Phase 2's analogous discipline is **replayability**, not
purity:

| Anchor | Determinism guarantee |
|---|---|
| Every `ingest_*` function's **cache-hit path** | A pure function of the cache directory's existing contents: given `is_cached(path) is True` and `force_refetch=False`, the function returns `path` with **zero** network calls, zero clock reads beyond none, and zero randomness. Always identical across runs. |
| `mizan.data.models.*` (row-shape schemas) | Pure validation functions of their input dict — no I/O, no network, no clock. |
| `mizan.data.raw_cache.cache_path` | Pure function of `(cache_dir, source, key, ext)` — always the same `Path` for the same inputs. |

Only the **cache-miss** path touches the network, the clock (for rate limiting), and an external,
non-deterministic system (EDGAR/Tiingo's live state) — and it is confined to the bodies of the six
`ingest_*`/`resolve_cik` functions named in §4.2/§4.3, the same "confined to one function body"
discipline `PHASE_1_SPEC.md` §6.4 and `Caveat.LOOK_AHEAD_BIAS`'s docstring both use for Mizan's one
other deliberately-scoped non-determinism.

---

## §7 Failure-Mode Guards

Pulled directly from `ULTIMATE_PRD.md` §4.1 (Ingestion/EDGAR) and §4.2 (Ingestion/Tiingo).

| # | Failure mode (`ULTIMATE_PRD.md` source row) | Guard Phase 2's code implements | What the review agent checks |
|---|---|---|---|
| G-E1 | 429 / rate-limit block | `_EdgarRateLimiter.wait_for_slot()` enforces >=0.12s spacing before every request; `note_block()` floors any wait at 600s regardless of a shorter `Retry-After` | Unit test with a fake clock: assert consecutive calls to `wait_for_slot()` are never spaced <0.12s apart; assert `note_block(retry_after_seconds=5)` still sleeps >=600s (mock `time.sleep`, assert call arg >= 600) |
| G-E2 | Missing/declared-bot-header rejection (403) | Every EDGAR request sends `User-Agent: <app name> <contact email>`, `Accept-Encoding: gzip, deflate`, `Host: www.sec.gov`/`data.sec.gov`; a 403 on a fully-headered request raises `EdgarBlockedError` immediately, no retry | `grep -n "User-Agent" mizan/data/ingest_edgar.py` — must be a literal header-construction site, not conditional/optional. Inspect an actual outgoing `httpx.Request` in a test (via a mock transport) and assert all three headers are present with a real contact email, not a placeholder |
| G-E3 | Missing/incomplete `companyfacts` for a CIK | `ingest_edgar_companyfacts` raises `MissingCompanyFactsError` on an empty/absent `facts` key; caller marks the ticker halted, never "screened anyway" | Test with a synthetic `{}` and `{"facts": {}}` response body, assert `MissingCompanyFactsError` in both cases |
| G-E4 | Missing `submissions` record / no SIC | `ingest_edgar_submissions` raises `MissingSicError` when `sic` is absent/empty | Test with a synthetic submissions body lacking `sic`, assert `MissingSicError` |
| G-E5 | CIK resolution mismatch (ticker→CIK drift) | `resolve_cik`'s `_names_match` cross-check (§6.3); zero-padding via `f"{cik:010d}"` everywhere a CIK is formatted into a URL | Test with a synthetic company_tickers entry whose `title` disagrees with a synthetic submissions `name`, assert `CikResolutionError`. `grep -nE "CIK\{.*\}" mizan/data/ingest_edgar.py` — every URL-building site must use the zero-padded form, not a bare `cik_str` |
| G-E6 | Malformed/undocumented XBRL tag drift | `EdgarFactRow` (`extra="forbid"`, inherited from `MizanBaseModel`) rejects any fact object carrying an unrecognized key | Test constructing `EdgarFactRow(**{...known fields..., "unexpectedNewKey": 1})`, assert `pydantic.ValidationError` |
| G-T1 | Hourly/daily request-budget exhaustion | `_TiingoBudget.consume()` sleeps to the next hour boundary rather than raising, when the hourly/daily counter is exhausted; no per-request spacing is added (Tiingo explicitly does not rate-limit to the second) | Test with a fake clock and a budget pre-set to 50/hour consumed: assert the 51st `consume()` call sleeps rather than issuing a request, and sleeps until (at least) the next hour boundary, not a fixed short delay |
| G-T2 | Monthly unique-symbol cap (500) exceeded | A persisted per-calendar-month unique-symbol log (stored under the cache directory, e.g. `<cache_dir>/tiingo/symbol_log/<YYYY-MM>.json`) that `ingest_tiingo_eod` checks/updates before issuing a request for a ticker new to the month | Test seeding a symbol log with 500 entries for the current month and calling `ingest_tiingo_eod` with a 501st distinct ticker, assert `TiingoUniverseDriftError`; assert a ticker already in the month's log does NOT count twice |
| G-T3 | Adjusted-close / raw-close conflation | `TiingoEodBar` declares `close` and `adjClose` as two distinct required fields (§3); no function anywhere in `mizan/data/` reads a field literally named `close` and treats it as adjusted, or vice versa | `grep -rn "adj_close\|adjClose\|raw_close" mizan/data/` and manually confirm no call site aliases one to the other under a single ambiguous name |
| G-T4 | Missing `divCash` on a known ex-dividend date | The anomaly scan (§6.4): any bar with `splitFactor != 1.0` and `divCash == 0.0` raises `SuspectedCorporateActionAnomalyError` after the raw response is cached | Test with a synthetic bar list containing one such bar among otherwise-clean bars, assert the exception fires and names the correct date; assert the raw cache file was still written before the exception propagated |
| G-T5 | API token leaked into the on-disk raw cache | Token sent via `Authorization: Token {token}` header only, never `?token=` in the URL; cache key is `(ticker, start_date, end_date)`, never derived from the request URL | `grep -rn "token=" mizan/data/ingest_tiingo.py` — any occurrence outside the header-construction line is blocking. `grep -r "<the test token value>" <cache_dir>` after a test run against a mock transport — must find zero hits in any cached file |
| G-CLI1 | A subcommand runs against an unverified foundation | `mizan/cli/main.py`'s `main()` calls `check_all()` before dispatching to any subcommand | Run `mizan ingest ...` with a monkeypatched `INVARIANTS` violation (or a broken fiqh register) and assert exit code 1 with the boot-check failure message, before any HTTP call is attempted (assert zero calls on a mock transport) |
| G-DEP1 | `duckdb`/`pyarrow`/`pandas`/`matplotlib` imported prematurely | Phase 2 imports only `pydantic` and `httpx` beyond the stdlib | `grep -rnE "^\s*(import\|from)\s+(duckdb\|pyarrow\|pandas\|matplotlib)" mizan/` — any hit is blocking, same as `PHASE_1_SPEC.md` guard G13, now re-run over the expanded tree |
| G-DEP2 | Persistent storage beyond the flat JSON raw cache (a DuckDB connection, a Parquet write) | `raw_cache.py`'s `ext` is fixed to `"json"`; no module opens a DuckDB connection | `grep -rnE "duckdb\.connect|to_parquet|read_parquet" mizan/data/` — any hit is blocking |
| G-LLM | LLM/model SDK or `yfinance` reachback | Forbidden-dependency list unchanged (§2.3) | `ULTIMATE_PRD.md` §5 checks 5 and 6, re-run over the expanded `mizan/` tree and `pyproject.toml` |
| G-AI | AI attribution in commit messages | Same neutral-commit convention as Phase 1 | `git log --format=%B` for this phase's commits — no `Co-Authored-By`, no "Generated with," no model/assistant name |

**Categorisation, mirroring `PHASE_1_SPEC.md` §7:** G-E2, G-E5, G-E6, G-T2, G-T4, G-T5, G-LLM, G-AI
are **HALT-for-human** (permissibility boundary, honesty-surface, or data-integrity touching).
G-E1, G-E3, G-E4, G-T1, G-T3, G-CLI1, G-DEP1, G-DEP2 are blocking-but-mechanical: fix and re-run.

---

## §8 Phase Acceptance Criteria

Each concrete, independently checkable by a third party, same standard `PHASE_1_SPEC.md` §8 applied.

1. **Replayability.** Given a fully-populated cache directory for a ticker/CIK, calling any of
   `fetch_company_tickers`, `ingest_edgar_submissions`, `ingest_edgar_companyfacts`,
   `ingest_edgar_companyconcept`, or `ingest_tiingo_eod` again (with `force_refetch=False`, the
   default) issues **zero** HTTP requests. Verified via a mock `httpx` transport that raises if
   called, or a request-count assertion of 0, on the second call in a two-call test sequence.
2. **Cache files are valid, model-readable JSON.** Every file `raw_cache.write_raw_json` produces
   is valid JSON, and the relevant §3 model (`EdgarFactRow`, `EdgarSubmissionRecord`,
   `CompanyTickerEntry`, or `TiingoEodBar`) parses every row/record in it without error, for at
   least one real or recorded fixture per source.
3. **EDGAR requests carry the required header triple.** `User-Agent` (with a real, non-placeholder
   contact email), `Accept-Encoding: gzip, deflate`, and `Host` are present on every EDGAR request,
   asserted by inspecting the outgoing request in a mock-transport test.
4. **EDGAR rate limiting actually sleeps.** A fake-clock/mocked-`time.sleep` test asserts
   `_EdgarRateLimiter.wait_for_slot()` enforces >=0.12s spacing across consecutive calls, and
   `note_block()` sleeps >=600s regardless of a shorter `Retry-After` value.
5. **Tiingo budget limiting actually throttles.** A fake-clock test asserts the 51st `consume()`
   call within a fake hour blocks/sleeps rather than issuing a request unthrottled.
6. **CIK resolution zero-pads and cross-checks.** `resolve_cik` returns a 10-character, zero-padded
   string for a known ticker; a synthetic name/title mismatch raises `CikResolutionError`.
7. **Adjusted/raw close never conflate.** `TiingoEodBar` has both `close` and `adjClose` as
   independently required fields; no function under `mizan/data/` derives one from the other or
   substitutes one for the other.
8. **Token never touches the cache or the URL.** Grepping the entire cache directory produced by a
   test run (against a mock transport using a known dummy token) for that token value returns zero
   hits; grepping `mizan/data/ingest_tiingo.py` for `token=` finds it only in the
   `Authorization` header construction line.
9. **`extra="forbid"` catches XBRL drift.** Constructing `EdgarFactRow` with an extra, undeclared
   key raises `pydantic.ValidationError`.
10. **Corporate-action anomalies are flagged, not dropped.** A synthetic bar set containing one
    `splitFactor != 1.0` / `divCash == 0.0` row raises `SuspectedCorporateActionAnomalyError` after
    (not instead of) writing the raw cache file.
11. **Monthly universe drift is caught.** A synthetic symbol log pre-seeded to 500 entries for the
    current month raises `TiingoUniverseDriftError` on a 501st distinct ticker.
12. **Boot gate runs first.** `mizan ingest ...` under a deliberately-violated `Invariants`/
    `FiqhParams` instance (test-injected) exits 1 with the boot-check failure message and issues
    zero HTTP requests, before any subcommand logic runs.
13. **Every new model inherits `MizanBaseModel`.** No file under `mizan/data/` or `mizan/cli/`
    imports or subclasses `pydantic.BaseModel` directly (same grep as `PHASE_1_SPEC.md` guard G8,
    re-run over the expanded tree).
14. **`mypy --strict mizan` exits 0**, scoped to the package itself (this is the environment-
    independent gate). `mypy --strict mizan tests` is also run and recorded; per `COMPREHENSION.md`
    §5's already-documented open item, a failure there caused solely by the global-numpy-stub/
    `pytest` interaction (not by any Mizan code) is not phase-blocking, but must be re-confirmed as
    still isolated to that cause (re-run `mypy --strict mizan` alone and confirm it is clean) rather
    than assumed unchanged from Phase 1. Building Phase 2 inside a project-scoped virtual
    environment (`COMPREHENSION.md` §6's own recommendation) is strongly encouraged here, since this
    is the first phase with a real third-party runtime import (`httpx`) to keep isolated.
15. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5`, including the deliberate
    `# noqa: N815` / `# noqa: A003` suppressions in `mizan/data/models.py` being the *only* such
    suppressions in the new tree (no other file gets a blanket noqa).
16. **`pytest` passes in full**, all five new test files plus the full existing Phase 1 suite (no
    regression).
17. **No forbidden dependency anywhere**, including the newly-required `httpx` itself being exactly
    `0.28.1` and appearing nowhere else under a different name/alias; `ULTIMATE_PRD.md` §5 checks 5
    and 6 clean over the expanded `mizan/` tree and `pyproject.toml`.
18. **No premature imports.** No module under `mizan/` imports `duckdb`, `pyarrow`, `pandas`, or
    `matplotlib`.
19. **No persistent storage beyond the flat JSON raw cache.** No DuckDB connection opened, no
    Parquet file written, anywhere under `mizan/data/`.
20. **Pins reconcile.** `httpx==0.28.1` (and every other pin) appears identically in
    `pyproject.toml` and `docs/modernization_log.md` §3, and §2.1's httpx re-check for this phase is
    logged there with a date, not silently skipped.
21. **Commits are neutral.** No AI attribution in `git log` for this phase's commits.
22. **Boundary greps are clean**, re-run from repo root against the full tree including
    `mizan/data/` and `mizan/cli/` (`ULTIMATE_PRD.md` §5 checks 1–8).

**Any single failing criterion is a phase-loop HALT, not a partial pass** — same standard
`PHASE_1_SPEC.md` §8 states for Phase 1, applied here.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 2)

- **No normalization, no DuckDB, no Parquet.** Raw JSON only, cached verbatim (§4.1, §5). Mapping
  raw wire-format rows to typed, unit-scaled, snake_case DuckDB tables is **Phase 3**'s
  `data/normalize.py`, per `ULTIMATE_PRD.md` §6. Phase 2's row-shape models (§3) validate *shape*
  on ingest; they are explicitly not the normalized schema.
- **No screening logic.** Nothing in Phase 2 computes a business-activity tier, a financial ratio,
  or a `Verdict`. SIC is fetched and cached (`ingest_edgar_submissions`) purely as raw data; Phase
  4's `screening/business_activity.py` is what actually uses it as a first-pass signal.
- **No backtest engine, no compliance-flip state machine, no portfolio or strategy code.** →
  Phase 5.
- **No purification logic.** The corporate-action anomaly scan (§6.4) flags a raw-data quality
  issue at ingest time; it does not compute a purification amount, reconcile a side-ledger, or apply
  any of Fork A/B/C. That reconciliation is **Phase 6**'s `backtest/purification.py`, which consumes
  the `divCash` values Phase 2 cached, unchanged.
- **No reporting.** No HTML, no plots, no `ResultEnvelope` producers. → Phase 7.
- **No `screen | backtest | report` CLI subcommands.** `mizan/cli/` in Phase 2 registers only
  `ingest`. Each later phase adds exactly one verb, per §1/§4.4's additive-extension convention.
- **No actual full historical backfill run as part of this automated build/review loop.** The
  ~100-ticker × ~10-year backfill `MASTER_PRD.md` §5.2 describes (~2 hours at Tiingo's request-per-
  hour cap, plus the EDGAR leg) is a one-time, real-network, real-API-key operation with genuine
  external rate-limit exposure. Phase 2's acceptance criteria (§8) verify the ingestion **code** is
  correct — replayability, header contracts, rate-limit timing, schema validation, HALT paths — via
  a small number of real-or-recorded calls (fixtures, a mock transport, or a handful of live calls
  against one or two tickers), **not** that a full production backfill was actually executed during
  this automated phase. Running the real backfill against the actual ~100-ticker universe is an
  operator action to take after Phase 2 is reviewed and approved, using a real `TIINGO_API_TOKEN`
  the automated loop does not have and should not need.
- **No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3).** Unchanged from
  `PHASE_1_SPEC.md` §9 — these remain escalated to the human and are unrelated to ingestion.
- **No LLM, ever, in any phase.** Restated per `PHASE_1_SPEC.md` §9's own restatement convention —
  ingestion is exactly the kind of layer where a build agent might reach for "an LLM to guess a
  malformed field's intended value" when a fetch returns something odd. That instinct is wrong here
  specifically: a malformed/unexpected shape is a **HALT-for-human** condition (§7), never a guess.
- **No change to the rebalance cadence surface, no HTTP API/service/dashboard.** Unchanged from
  `PHASE_1_SPEC.md` §9; ingestion touches neither.

---
