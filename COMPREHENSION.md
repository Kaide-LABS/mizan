# COMPREHENSION.md — Mizan

Written after Phase 3 ("Normalization & DuckDB Store") was reviewed and approved. Sections 1–6
below describe the repository as it exists right now — Phase 1 ("Foundation & Config"), Phase 2
("Ingestion & Raw Cache"), and Phase 3 combined — grounded in the code read directly this pass, not
in what any spec or prior handoff claimed. The Phase Log at the bottom is append-only; Phase 1's and
Phase 2's entries are preserved untouched below the new Phase 3 entry.

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

Phase 1 built the foundation everything else stands on: the list of seven settled rules, the list
of eleven disputed judgment calls (each with its best current guess, a citation, and an honest note
about what's unclear), a "boot check" that refuses to even start the program if any of that
foundation looks wrong, and a handful of shared building-block definitions.

Phase 2 taught Mizan how to go out and pull real financial data for a given stock ticker from two
sources — the US government's own company-filings database (SEC EDGAR, for company fundamentals
like revenue and debt) and a commercial market-data provider (Tiingo, for daily stock prices and
dividends) — and to save every single response it gets to a local folder on disk before doing
anything else with it. The point of saving everything first is honesty and reproducibility: if the
program is run again for the same ticker and date range, it re-uses what it already saved instead
of asking the data provider again, and if something ever looks wrong with the saved data, a human
can open the actual file on disk and see exactly what the data source sent, unmodified. Phase 2 also
taught the program to be a polite, rule-following guest of both data providers, respecting SEC's
request-spacing rule and Tiingo's hourly/daily/monthly usage caps, and to flag one specific kind of
suspicious price-history pattern (a share-count-changing "split" with no dividend recorded on the
same day) for a human to look at.

Phase 3, the subject of this update, is the first phase that turns those saved-but-still-raw files
into something a computer program can actually query and trust. Up through Phase 2, "the data" was
just a pile of JSON files on disk, shaped exactly like whatever SEC or Tiingo happened to send. Phase
3 reads that pile, checks every entry against a strict, typed shape, and loads it into a real local
database (DuckDB) — one table for company financial facts (revenue, assets, and so on, pulled from
SEC filings) and one table for daily stock prices. Two kinds of protection are built directly into
this loading step, not left as something a human has to remember to check later: first, if the same
financial fact or the same trading day is loaded twice, the database itself refuses to silently
double up or silently overwrite — a genuine conflict (the same fact reported two different ways)
stops the program and tells the human exactly what disagreed, while re-loading the exact same data
twice in a row is safely treated as a no-op. Second, if SEC's filing data ever reports a number in a
unit of measurement Mizan doesn't already know how to handle (something other than plain US dollars
or a plain share count), the program refuses to guess at a conversion — it stops and asks a human to
look, rather than silently assuming a scale that might be wrong.

Still nothing here screens a stock for compliance or runs a backtest — no money is simulated, no
pass/fail verdict is produced yet. What exists after Phase 3 is: the settled/disputed rule registry
from Phase 1; the working, rate-limit-respecting, replay-safe data-pulling pipeline from Phase 2; and
now, new this phase, a real typed local database that the screening and backtest phases still to
come will actually read from — built with the specific protections needed so that "duplicate data"
and "a number in a unit we don't understand" can never quietly corrupt what those later phases will
trust.

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
│   ├── verdict.py                # Verdict — the three-state pass/partial/fail screening outcome (definition only)
│   └── caveats.py                # Caveat enum + ResultEnvelope — the mandatory warning-label wrapper for results
├── data/
│   ├── __init__.py                # empty
│   ├── models.py                  # raw wire-format row-shape schemas for EDGAR + Tiingo payloads (Phase 2)
│   ├── raw_cache.py               # shared cache-path / cache-hit / atomic-write / read helpers, both legs (Phase 2)
│   ├── ingest_edgar.py            # EDGAR client: rate limiter, header construction, CIK resolution, fetch fns (Phase 2)
│   ├── ingest_tiingo.py           # Tiingo client: request/symbol budget limiter, EOD fetch, anomaly scan (Phase 2)
│   ├── db.py                      # NEW this phase — DuckDB connection + idempotent schema creation
│   └── normalize.py               # NEW this phase — typed row shapes + raw-cache-to-DuckDB mapping functions
└── cli/
    ├── __init__.py                # empty
    ├── main.py                    # `mizan` console-script entrypoint — boot-check-first dispatcher (MODIFIED this phase: registers `normalize`)
    ├── ingest.py                  # the `ingest` subcommand: argument parsing, per-ticker orchestration (Phase 2, untouched this phase)
    └── normalize.py               # NEW this phase — the `normalize` subcommand
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
├── test_data_db.py               # NEW this phase — schema idempotency, PRIMARY KEY enforcement, single-writer lock behaviour
├── test_data_normalize.py        # NEW this phase — unit-rejection, duplicate-guard, idempotent replay, column contract
└── test_cli_normalize.py         # NEW this phase — boot-gate-first behaviour, offline-only dispatch, exit codes
.env.example                       # TIINGO_API_TOKEN placeholder template, never a real credential
pyproject.toml                    # project metadata, exact dependency version pins, mypy/ruff/pytest config, CLI entry points (MODIFIED this phase)
docs/modernization_log.md         # a running log of exactly which external tool/library versions and API contracts were verified and when (MODIFIED this phase)
.gitignore                        # MODIFIED this phase — *.duckdb, *.duckdb.wal added
PHASE_3_SPEC.md                   # NEW this phase — the Phase 3 build contract
```

How the Phase 1 pieces connect (unchanged, still true, re-verified this pass):

- `mizan/core/base.py` defines `MizanBaseModel`, a Pydantic model with three settings turned on that
  Pydantic does not turn on by default: unknown fields are rejected outright rather than silently
  dropped, every instance is immutable once created, and default values are validated the same as
  any user-supplied value. Every other model class in the project — `Invariants`, `FiqhParam`,
  `FiqhParams`, `ResultEnvelope`, every Phase 2 model in `mizan/data/models.py`, and now Phase 3's
  `FundamentalsFactRow`/`PriceBarRow` (`mizan/data/normalize.py`) — inherits from this one base. A
  boundary grep re-run this pass (`grep -rn "BaseModel" mizan/`) confirms the literal string
  `BaseModel` still appears only inside `core/base.py` itself and as an import target elsewhere, not
  as a second base class definition anywhere in the tree.
- `mizan/config/invariants.py`, `mizan/config/fiqh_params.py`, and `mizan/config/boot_check.py`
  behave exactly as Phase 1's comprehension pass described — untouched by Phase 2's or Phase 3's
  diff (`git diff e73e9cc..8e99809` touches none of `mizan/config/`).
- `mizan/core/verdict.py` and `mizan/core/caveats.py` are likewise untouched.

How the Phase 2 pieces connect (unchanged, still true, re-verified this pass):

- `mizan/data/models.py` defines five schemas, all subclassing `MizanBaseModel`: `CompanyTickerEntry`,
  `EdgarFactRow`, `EdgarSubmissionRecord`, `TiingoEodBar`, and `TiingoCorporateActionEvent`. Wire-format
  field names are kept verbatim (camelCase where SEC/Tiingo actually use camelCase) — this phase's
  own new file, `mizan/data/normalize.py`, is where that camelCase is finally translated into
  snake_case, per Phase 2's own docstrings' forward declaration (see §3 below).
- `mizan/data/raw_cache.py` remains the one shared home for cache mechanics both ingestion legs use;
  Phase 3's `normalize.py` reuses `cache_path()`, `is_cached()`, and `read_raw_json()` from this
  module directly rather than re-deriving cache-path logic.
- `mizan/data/ingest_edgar.py` and `mizan/data/ingest_tiingo.py` are untouched by Phase 3's diff.
  Phase 3's `resolve_cik_offline` (below) imports and re-raises `ingest_edgar.CikResolutionError`
  rather than defining a new exception type for the same failure kind.
- `mizan/cli/ingest.py` is untouched.

How the new Phase 3 pieces connect:

- `mizan/data/db.py` is the one canonical home for opening a DuckDB connection and creating Phase
  3's two tables. `connect(db_path, *, read_only=False)` creates `db_path`'s parent directories,
  opens the file via `duckdb.connect()`, and — unless `read_only=True` — calls `ensure_schema(con)`
  before returning, so no caller can obtain a writable connection to a database missing either
  table. `ensure_schema` runs `CREATE TABLE IF NOT EXISTS` for both `fundamentals_facts` and
  `price_bars`, then calls a private `_verify_columns` helper that reads each table's actual column
  set back via `PRAGMA table_info(...)` and raises `SchemaError` if it disagrees with what this
  module would create — a defensive check specifically because `CREATE TABLE IF NOT EXISTS` itself
  silently no-ops against a same-named table with a different column set. `read_only=True` (for
  Phase 4+ read-only consumers) skips schema creation and, verified this pass via
  `tests/test_data_db.py::test_connect_read_only_does_not_create_schema_on_a_new_file`, raises
  rather than creating a new file when none exists.
- `mizan/data/normalize.py` defines two new Pydantic row shapes, `FundamentalsFactRow` and
  `PriceBarRow`, and the functions that populate them: `normalize_edgar_facts(cik, *, cache_dir,
  con)` reads the already-cached `edgar/companyfacts/{cik}.json` file (never fetches; raises
  `NotIngestedError` if it is absent), walks every `facts.{taxonomy}.{tag}.units.{unit}` entry,
  raises `UnrecognizedUnitError` immediately if `unit` is outside the closed
  `RECOGNIZED_XBRL_UNITS = frozenset({"USD", "shares"})` allow-list (checked before any row for that
  unit is built), and otherwise maps each fact object (re-validated via Phase 2's own `EdgarFactRow`
  model) into a `FundamentalsFactRow`, substituting `period_start = period_end` with
  `is_instantaneous = True` whenever the raw fact's `start` is `None`. `normalize_tiingo_bars(ticker,
  start_date, end_date, *, cache_dir, con)` does the equivalent for the cached Tiingo EOD file,
  re-validating each bar via Phase 2's `TiingoEodBar` model and mapping `open`/`high`/`low`/`close`
  to `raw_open`/`raw_high`/`raw_low`/`raw_close` and `adjOpen`/etc. to `adj_open`/etc., with every
  field assigned on its own line from its own named source attribute (no shared local variable
  aliases `raw_close` and `adj_close` to each other, confirmed by direct read of the function body,
  `mizan/data/normalize.py` lines 299–317). Both normalize functions delegate the actual DuckDB
  write to a shared private helper, `_bulk_load` (below). `resolve_cik_offline(ticker, *, cache_dir)`
  is a separate, network-free ticker→CIK lookup reading only the already-cached
  `company_tickers.json` — its signature has no client/network parameter at all (confirmed by
  `inspect.signature`, exercised directly in `tests/test_data_normalize.py`), and it reuses Phase
  2's `CikResolutionError` rather than defining a new one.
- `_bulk_load(con, *, table, rows, key_columns, conflict_error_cls)` (private to
  `mizan/data/normalize.py`) is the shared dedup-then-insert pattern both normalize functions use:
  it converts the validated Pydantic rows to a `pyarrow.Table` via `pyarrow.Table.from_pylist`,
  `register()`s it under DuckDB as a queryable view named `_staging`, runs a pre-insert conflict
  check (`_raise_on_conflict`) that raises `conflict_error_cls` (either `DuplicateFactRowError` or
  `DuplicatePriceBarError`) the moment any staged row's key matches an existing row with a
  *different* non-key value, and — only if no conflict was found — runs one
  `INSERT INTO {table} SELECT s.* FROM _staging s WHERE NOT EXISTS (...)` so that a row whose key
  already exists with byte-identical other-column values is silently skipped as an idempotent
  no-op, never an error. `_bulk_load` always `unregister()`s `_staging` in a `finally` block. The
  table's own `PRIMARY KEY` constraint (§4 below) is a last-resort backstop, not the primary
  mechanism, if `_raise_on_conflict`'s own query is ever itself wrong.
- `mizan/cli/normalize.py` registers `normalize --ticker TICKER [--ticker TICKER ...] --start-date
  YYYY-MM-DD --end-date YYYY-MM-DD --cache-dir PATH --db-path PATH` (`--ticker` repeatable,
  `--db-path` required with no default, mirroring `--cache-dir`'s no-default posture from Phase 2).
  Its `run()` opens exactly one `db.connect(args.db_path)` connection for the whole batch inside a
  `with` block (closed on every exit path, including a halted one), and for each ticker calls
  `resolve_cik_offline` → `normalize_edgar_facts` → `normalize_tiingo_bars` in that order, catching
  `CikResolutionError`/`NotIngestedError`/`UnrecognizedUnitError`/`DuplicateFactRowError`/
  `DuplicatePriceBarError` per ticker, printing `HALT [{ticker}]: {ExceptionType}: {message}` to
  stderr, and continuing to the next ticker — but returning exit code `1` if any ticker halted,
  mirroring `mizan.cli.ingest.run`'s contract exactly (verified line-for-line against
  `mizan/cli/normalize.py` lines 92–111).
- `mizan/cli/main.py`'s `build_parser()` now registers two subparsers — Phase 2's `ingest` and this
  phase's `normalize` (`normalize_cli.add_subparser(subparsers)`, one added line, confirmed by
  reading the diff and the current file) — and `main()`'s boot-check-first dispatch (`check_all()`
  before any subcommand) is otherwise unchanged, so `mizan normalize` also halts before any DuckDB
  file is created if the Phase 1 foundation is broken (verified by
  `tests/test_cli_normalize.py::test_main_halts_on_invariant_violation_before_any_duckdb_file_is_created`,
  which asserts the target `--db-path` file does not exist afterward).
- `pyproject.toml` promotes `duckdb==1.5.5` and `pyarrow==25.0.1` from Phase 1's forward-declared
  `[project.optional-dependencies].data` extra to real `[project.dependencies]` entries — Phase 3 is
  the first phase that imports either. The `data` extra is narrowed to `pandas==3.0.5` alone, still
  forward-declared and unused. A new `[[tool.mypy.overrides]]` block silences mypy's
  import-untyped complaint for `pyarrow.*` specifically (pyarrow ships no inline type stubs), without
  relaxing `--strict` for any Mizan-owned module.
- `docs/modernization_log.md` gained three new entries this phase (all read in full this pass): a
  dated live re-check confirming `duckdb==1.5.5`/`pyarrow==25.0.1` are still PyPI's newest releases;
  a live-verified confirmation that DuckDB's `INSERT` raises `duckdb.ConstraintException` on a
  PRIMARY KEY collision; and a correction to the previously-logged single-writer-lock note (§3
  below) — the file lock is enforced by the OS across processes, not by a second same-process
  `connect()` call.
- `.gitignore` gained `*.duckdb` and `*.duckdb.wal`, confirmed this pass by creating a real,
  throwaway `.duckdb` file at the repo root via `mizan.data.db.connect` and running
  `git check-ignore -v` against it — it reports the file matched by `.gitignore:10:*.duckdb`.

## 3. Decisions and tradeoffs

**Carried forward from Phase 1 (still shipped, not overturned by Phase 2 or Phase 3):**

- `FiqhParam` remains generic (`FiqhParam[T]`), not a `bool | float | str` union. Unaffected by
  either later phase — `mizan/config/fiqh_params.py` is untouched.
- `check_invariants()` / `check_fiqh_register()` remain hand-written, field-by-field checks rather
  than a generic loop. Unaffected.
- `StrEnum` (not `class X(str, Enum)`) remains the pattern for `VerificationStatus`, `Verdict`, and
  `Caveat`. Unaffected.

**Carried forward from Phase 2 (still shipped, not overturned by Phase 3):**

- `read_raw_json`'s return type remains the shipped `object`, not the spec's originally-stated
  `dict[str, object]` — still correct, and still load-bearing for Phase 3: `normalize_edgar_facts`
  narrows the EDGAR object with `isinstance(data, dict)` and `normalize_tiingo_bars` narrows the
  Tiingo array with `isinstance(bars_raw, list)`, both confirmed by direct read of
  `mizan/data/normalize.py` this pass — the same shared, honestly-typed reader Phase 2 built is
  reused by Phase 3 without modification.
- EDGAR's write-cache-before-validate ordering, and the `TIINGO_API_TOKEN` environment variable
  name, are both unaffected by Phase 3 (neither file changed).
- The two ruff-noqa corrections from Phase 2 (`A003` absent, `N812` present on the `_Date` alias in
  `mizan/data/models.py`) still hold as-is in `models.py`; Phase 3 adds a related but distinct
  finding of its own — see §5 below.

**New this phase — real decisions/resolutions, each verified directly against the code and
`docs/modernization_log.md` this pass:**

- **DuckDB's single-writer lock is enforced across OS processes, not within one process — the spec's
  planned same-process test could not have exercised the real guarantee, and the build corrected
  course rather than shipping a test that measured the wrong thing.** `PHASE_3_SPEC.md` §7 (guard
  G-DB1) and §8 (AC10) both described the test as "a second connection attempt ... in the same
  process." The shipped code and `docs/modernization_log.md`'s corrected §5.4 entry (both read this
  pass) establish the actual, empirically-verified behaviour: DuckDB 1.5.5's Python API caches one
  underlying database instance per file path *per process* — a second `db.connect()` call to the
  same path from the same process shares that instance rather than hitting a lock error (proven by
  `tests/test_data_db.py::test_second_same_process_connection_shares_the_instance_and_does_not_raise`,
  which inserts via the second connection and reads the row back via the first). The real
  single-writer file lock only fires when a second, genuinely separate OS process tries to open the
  same file while the first holds it open non-read-only — exercised by
  `tests/test_data_db.py::test_second_writable_connection_to_a_locked_file_raises_across_processes`,
  which spawns a real `subprocess.Popen` holder and asserts the second process's `db.connect()` call
  raises. **The tradeoff, stated plainly:** a same-process caller (e.g. two functions in one script
  both calling `db.connect()` on the same path) cannot accidentally get locked out by DuckDB's own
  design — convenient, and not a safety hole, because `mizan/cli/normalize.py`'s `run()` already
  holds exactly one connection per invocation for its entire batch (verified this pass, §2 above).
  The safety property that actually matters operationally — that two independent, concurrently-run
  `mizan normalize` invocations (or a stray leftover process) cannot both write to the same DuckDB
  file and corrupt it — is still real, still enforced by the OS-level lock, and is now tested against
  the mechanism that actually provides it, rather than against a same-process scenario that would
  have passed even if the real cross-process guard were silently broken.
- **`pyarrow` is a genuine Phase 3 dependency, not merely dragged in by `duckdb`.** Verified directly
  in `_bulk_load` (`mizan/data/normalize.py` line 363): `pyarrow.Table.from_pylist(payload)` builds
  the Arrow table that is `register()`ed with DuckDB as the `_staging` view every bulk-load call
  uses — the Arrow-interchange half of `pyarrow`'s role, not the Parquet half (Phase 3 writes no
  Parquet file anywhere, confirmed by `grep -rn "to_parquet\|read_parquet" mizan/data/` returning no
  hits this pass).
- **The application-level pre-insert conflict check is the primary duplicate guard; the DuckDB
  `PRIMARY KEY` constraint is a backstop, not the mechanism operators should expect to see fire in
  normal operation.** `_bulk_load`'s own docstring (`mizan/data/normalize.py` lines 336–353) states
  this explicitly, and it is structurally true: `_raise_on_conflict` runs and can raise
  `DuplicateFactRowError`/`DuplicatePriceBarError` *before* any `INSERT` statement executes, so a
  `duckdb.ConstraintException` surfacing from the `INSERT` itself would indicate a bug in the
  pre-check, not a normal-path duplicate rejection. The tradeoff: this is two separate mechanisms
  doing conceptually related work (both exist to prevent a silent duplicate), which is more code than
  relying on the constraint alone — but the constraint alone cannot distinguish "genuine conflicting
  value" from "byte-identical idempotent replay" (both would violate a naive `INSERT`), so the
  pre-check's `WHERE NOT EXISTS`/differing-value split is load-bearing, not redundant.
- **No ORM, no migration framework, no `sqlalchemy`.** `mizan/data/db.py` uses DuckDB's own
  `connect`/`execute`/`register` API directly; `ensure_schema`'s idempotent
  `CREATE TABLE IF NOT EXISTS` plus `_verify_columns`'s defensive column-set check is the entire
  migration story for V1 (`PHASE_3_SPEC.md` §5.3's stated decision, matched verbatim by the shipped
  code — no `ALTER TABLE`/`DROP TABLE` anywhere in `mizan/data/db.py`, confirmed by grep this pass).
  The tradeoff: a genuine schema change during development requires deleting the gitignored,
  derived `.duckdb` file and re-running `mizan normalize` from the still-intact raw JSON cache,
  rather than an in-place migration — acceptable for a single-developer, single-schema-version, local
  file, not acceptable if this ever became multi-developer or long-lived-production infrastructure.
- **`normalize_edgar_facts` is scoped to `companyfacts` only, never `companyconcept`.** Verified: no
  function in `mizan/data/normalize.py` reads a `companyconcept`-sourced cache entry.
  `companyfacts` is a strict superset of any single `companyconcept` call for the same CIK, and
  `mizan/cli/ingest.py`'s `run()` (Phase 2, untouched) never calls `ingest_edgar_companyconcept` —
  so there is currently no cached `companyconcept` data for this function to be missing anyway. The
  tradeoff is deferred, not paid: if a future phase needs the narrower `companyconcept` shape
  normalized, that is an additive extension to this file, not a rework.
- **`resolve_cik_offline` deliberately skips Phase 2's `resolve_cik`'s name-cross-check.** It performs
  only the ticker→CIK lookup against the cached `company_tickers.json`, not the
  submissions-record name/title cross-check `ingest_edgar.resolve_cik` also does. This is a
  narrower, cache-only function built for one purpose (locating the right cache files for
  `normalize`'s own read), not a re-run of Phase 2's own drift detection — the tradeoff being that
  `mizan normalize` trusts the CIK Phase 2's `mizan ingest` already resolved and cross-checked for
  that ticker, rather than re-verifying it a second time.

## 4. Domain mechanics

**Fiqh register — carried forward from Phase 1, unchanged (neither Phase 2 nor Phase 3 touches
`mizan/config/fiqh_params.py`):**

| # | Figure / default | Value in code | Code's own source citation | Code's own honesty flag |
|---|---|---|---|---|
| 1 | Ratio denominator basis | `market_cap` | AAOIFI SS21 public methodology (Merah presentation, Oct 2017) | **[UNVERIFIED / INFERENCE]** — denominator basis not stated in the public methodology |
| 2 | Ratio denominator smoothing | `spot` (unsmoothed) | Same Merah presentation, by contrast with index-provider practice | **[UNVERIFIED / INFERENCE]** — averaging window not stated |
| 3 | Debt-ratio threshold | 30% | "Merah presentation slides 32-34" | No gap flagged — verified verbatim against cited slides |
| 4 | Interest-investments threshold | 30% | "Merah presentation slides 33-34" | No gap flagged |
| 5 | Non-permissible income threshold | 5% | "Merah presentation slide 32," quoted "Non Halal Income Should not Exceed 5% of Total Income" | Denominator ambiguity flagged: source says "Total Income," `MASTER_PRD.md` §6.2 says "total revenue" |
| 6 | Business-activity Tier 0.5 (adult content, weapons/defence) | enabled | Reaches AAOIFI only via its catch-all "unlawful activities" clause | Flagged **not directly AAOIFI-enumerated** |
| 7 | Business-activity Tier 1 (media/music/entertainment, hotels) | disabled | "genuinely contested across scholarly bodies" | Flagged **not AAOIFI-enumerated** |
| 8 | Grace period before forced divestment | 1 rebalance period | "common Islamic-fund practice" | Flagged **no AAOIFI-stated grace period found** |
| 9 | Purify capital gains | disabled (dividends-only) | "Fork A" | Flagged: source requires purification but has no capital-gains formula |
| 10 | Divestment-attribution method | time-bounded price appreciation over flip-to-divestment window | "Fork C" | Flagged: **no settled formula exists** |
| 11 | Purification accounting | side-ledger, never netted into NAV | Primary-source verbatim quote (donate to charity, excluded from investor P&L) | No gap flagged |

The seven `Invariants` fields (`mizan/config/invariants.py`) remain settled boundary conditions, not
judgment calls — `cash_yield = 0.0` still encodes that idle cash may never earn interest (riba),
sourced to `MASTER_PRD.md` §2 and `ULTIMATE_PRD.md` §5.

**Ingestion domain mechanics — carried forward from Phase 2, unchanged (neither `ingest_edgar.py`
nor `ingest_tiingo.py` is touched by Phase 3's diff):**

| Figure | Value | Code enforcing it | Citation |
|---|---|---|---|
| SEC EDGAR rate limit | 10 requests/second per IP; Mizan spaces at ≥0.12s | `_EdgarRateLimiter.wait_for_slot`, `mizan/data/ingest_edgar.py` | `docs/modernization_log.md` §6.1 |
| SEC EDGAR block cooldown | ≥600s (10 min) wait, floored even if `Retry-After` is shorter, before one retry; a second consecutive block halts | `_EdgarRateLimiter.note_block`, `_edgar_get` | Same §6.1 |
| SEC EDGAR User-Agent requirement | Descriptive `User-Agent` + real contact email required; a bare/missing UA gets HTTP 403 | `_edgar_headers` | Same §6.1 |
| CIK zero-padding + name cross-check | `cik_str` zero-padded to 10 digits; resolved CIK's submissions `name` cross-checked against `company_tickers.json`'s `title` | `resolve_cik`, `_names_match`, `mizan/data/ingest_edgar.py` | `PHASE_2_SPEC.md` §6.3 |
| Tiingo request budget | 50 requests/hour, 1,000 requests/day — throttled, never raised on its own | `_TiingoBudget.consume`, `mizan/data/ingest_tiingo.py` | `docs/modernization_log.md` §6.2 |
| Tiingo unique-symbol budget | 500 unique tickers/calendar month — a 501st distinct ticker raises `TiingoUniverseDriftError` | `_register_symbol_or_raise` | Same §6.2 |
| Corporate-action anomaly heuristic | A bar with `splitFactor != 1.0` and `divCash == 0.0` on the same date is flagged | `_scan_for_corporate_action_anomalies` | `PHASE_2_SPEC.md` §6.4 |
| Adjusted vs raw close never conflated (raw ingestion layer) | `TiingoEodBar.close` and `.adjClose` are two independently required fields | `mizan/data/models.py` | `PHASE_2_SPEC.md` §7 guard G-T3 |

**New this phase — normalization/storage domain mechanics, every figure cross-checked against
`docs/modernization_log.md` (live-verified 2026-08-30) and the shipped code:**

| Figure | Value | Code enforcing it | Citation |
|---|---|---|---|
| `fundamentals_facts` uniqueness key | `(cik, taxonomy, tag, unit, period_start, period_end, accn)` — `taxonomy`+`tag` together are the XBRL "concept" (e.g. `us-gaap:Revenues`), `unit` is a necessary fourth axis (the same concept can appear under two units), `accn` (not `filed`) is the discriminator for "same period reported in two filings" | DDL `PRIMARY KEY` in `_CREATE_FUNDAMENTALS_FACTS`, `mizan/data/db.py`; dedup key in `_FUNDAMENTALS_FACTS_KEY_COLUMNS`, `mizan/data/normalize.py` | `PHASE_1_SPEC.md` §5's forward declaration; `PHASE_3_SPEC.md` §5; addresses `ULTIMATE_PRD.md` §4.3's named failure mode "Duplicate/overlapping filing periods loaded twice into DuckDB," categorized **HALT-for-human** there |
| `price_bars` uniqueness key | `(ticker, trade_date)` | DDL `PRIMARY KEY` in `_CREATE_PRICE_BARS`; `_PRICE_BARS_KEY_COLUMNS` | `PHASE_3_SPEC.md` §5.2 |
| XBRL units validation | Closed allow-list `RECOGNIZED_XBRL_UNITS = frozenset({"USD", "shares"})`; any other unit key (e.g. `"USD/shares"`) raises `UnrecognizedUnitError` before any row for that unit is constructed — never a guessed scale conversion | `normalize_edgar_facts`, `mizan/data/normalize.py` lines 219–224 | `ULTIMATE_PRD.md` §4.3's named failure mode "Silent type coercion (an XBRL fact reported in different unit scales across filings)," categorized **HALT-for-human**; addressed by rejecting rather than guessing |
| Instantaneous-concept substitution | A raw fact with `start=None` is normalized to `period_start = period_end` with `is_instantaneous = True`, losslessly preserving the original signal in a form with no nullable key column | `_build_fact_row`, `mizan/data/normalize.py` lines 243–269 | `PHASE_3_SPEC.md` §3, §7 guard G-N6 |
| Dedup-then-insert-with-backstop pattern | Pre-insert conflict check raises on a genuine value conflict at an existing key; `INSERT ... WHERE NOT EXISTS` silently skips a byte-identical replay; the table's own `PRIMARY KEY` is the last-resort backstop | `_bulk_load`, `_raise_on_conflict`, `mizan/data/normalize.py` | `PHASE_3_SPEC.md` §6.2 |
| DuckDB PRIMARY KEY constraint-violation behaviour | `INSERT`ing a second row with an identical PK and differing non-key values raises `duckdb.ConstraintException` | Verified live against DuckDB 1.5.5 in `.venv`; `tests/test_data_db.py::test_fundamentals_facts_primary_key_rejects_a_duplicate_key_insert` and the `price_bars` equivalent | `docs/modernization_log.md` §5.4 (dated 2026-08-30 build-time verification) |
| Single-writer file lock scope | Enforced by the OS across processes, not by a second same-process `duckdb.connect()` call (see §3 above) | `tests/test_data_db.py`'s two lock-behaviour tests | `docs/modernization_log.md` §5.4 correction |

None of these Phase 3 figures are marked `[UNVERIFIED]` — all are drawn from
`docs/modernization_log.md`'s own record of a live/documentation re-check performed 2026-08-30,
independently re-run this pass (the DuckDB PK-violation test and the two lock-behaviour tests were
executed as part of the `pytest` run in §5, not merely read).

## 5. Honesty audit

Ran the same class of verification `PHASE_3_SPEC.md` §8 (acceptance criteria) and §7 (guards)
specify, against the code as it exists in the repository right now, this run — not trusting the
spec's or the approval commit's claim that they pass.

**Everything below passed as claimed, verified this run, inside the project's `.venv`:**
- `pytest tests/` — **178 passed** (146 carried from Phase 1+2 + 32 new this phase across the three
  new test files: 10 in `test_data_db.py`, 14 in `test_data_normalize.py`, 8 in
  `test_cli_normalize.py`), no regressions.
- `ruff check mizan tests` — "All checks passed!", exit 0, under the pinned `ruff==0.16.5`.
- `mypy --strict mizan tests` — clean, "Success: no issues found in 32 source files," inside
  `.venv`.
- Boundary greps re-run this pass over the expanded tree: `grep -rn "httpx" mizan/data/normalize.py
  mizan/data/db.py mizan/cli/normalize.py` — no hits (G-N8 clean). `grep -rnE
  "^\s*(import|from)\s+(duckdb|pyarrow)" mizan/` — every hit is inside `mizan/data/db.py` or
  `mizan/data/normalize.py`, none elsewhere (G-DEP3 clean). `grep -rnE
  "^\s*(import|from)\s+(pandas|matplotlib)" mizan/` — zero hits anywhere (no premature import).
  `grep -rn "to_parquet\|read_parquet" mizan/data/` and `grep -rn "ALTER TABLE\|DROP TABLE"
  mizan/data/db.py` — zero hits (no Parquet, no schema alteration, §5.3/§9's stated V1 scope
  honored). `grep -n "RECOGNIZED_XBRL_UNITS" mizan/data/normalize.py` — one definition, used at
  every check site, no second ad-hoc unit check anywhere else.
- `.gitignore` reconciliation, verified live rather than just read: created a real, throwaway
  `.duckdb` file at the repo root via `mizan.data.db.connect()` this pass and confirmed
  `git check-ignore -v` reports it matched by `.gitignore:10:*.duckdb`; the file was then deleted.
  `git log --format=%B` across both Phase 3 commits (`8483b5b` docs, `8e99809` implementation,
  `e9a62c3` approval) — no `Co-Authored-By`, no "Generated with," no model/assistant name.
- `duckdb==1.5.5` and `pyarrow==25.0.1` reconcile identically between `pyproject.toml` and
  `docs/modernization_log.md`, with a fresh, dated 2026-08-30 re-check logged (actual
  `pip index versions` output pasted into the log, not silently carried forward from the Step 10
  entry) — AC20 holds.

**Phase 1's documented mypy/numpy gap — re-tested this run, and now compounded by a second,
related-but-distinct cause:**

Phase 1's comprehension pass found that `mypy --strict mizan tests` fails outside `.venv` because a
global, non-Mizan `numpy` install's type stubs use post-3.11 stub syntax the project's pinned
`python_version = "3.11"` mypy target can't parse. This run:
- **Inside `.venv`**: clean, 0 errors, 32 files (up from 26 in the Phase 2 pass — six new source
  files: `mizan/data/db.py`, `mizan/data/normalize.py`, `mizan/cli/normalize.py`, and their three
  test files).
- **Outside `.venv`** (`py -3.14 -m mypy --strict mizan tests`): the original numpy failure still
  reproduces verbatim (`numpy/__init__.pyi:737: error: Type statement is only supported in Python
  3.12 and greater`) — confirmed still real, still environment-specific, not something Phase 3
  fixed or worsened in isolation. **New this run:** outside `.venv`, mypy now *also* reports
  `Cannot find implementation or library stub for module named "duckdb"` at every one of the four
  files that import it (`mizan/data/db.py`, `mizan/data/normalize.py`,
  `tests/test_data_db.py`, `tests/test_data_normalize.py`) — because `duckdb` (a native-extension
  package) is naturally only installed inside `.venv`, not globally. This is not a new *bug*; it is
  the expected, correct consequence of Phase 3 adding a real third-party runtime dependency, and it
  makes `PHASE_3_SPEC.md` AC14's explicit instruction — "Building and verifying inside the project's
  `.venv` ... is required, not merely encouraged, now that this phase adds a second real third-party
  runtime dependency with native extension components" — concretely true rather than a hypothetical
  caution: outside `.venv`, verification does not merely hit the pre-existing numpy-stub false
  failure, it now cannot even import the modules under test.

**Two concrete, real spec-vs-code / honesty-surface findings from this pass:**

1. **Phase 2's AC15 noqa-enumeration finding is unchanged in `mizan/data/models.py` itself, but the
   repository's current honest state has moved: a second file now carries a `# noqa: N812`
   suppression for the identical reason.** `PHASE_2_SPEC.md` §8 AC15 stated ruff's suppressions in
   the *Phase-2* tree should be confined to `mizan/data/models.py` alone; Phase 2's own
   comprehension pass already flagged that `models.py` in fact lacks the `A003` suppression AC15's
   literal wording named (unaffected, unresolved, and out of Phase 3's scope to fix — `models.py` is
   untouched by Phase 3's diff). Separately, and newly this run: `mizan/data/normalize.py` line 17
   carries `from datetime import date as _Date  # noqa: N812`, the exact same alias pattern and the
   exact same real reason `models.py` line 25 already carries one (ruff's `N812` does fire on this
   alias under the pinned `ruff==0.16.5`, empirically, not by assumption). `PHASE_3_SPEC.md` itself
   does not restate AC15's file-enumeration claim, so this is not a violation of any Phase 3
   acceptance criterion — Phase 3's own AC15 asks only that `ruff check mizan tests` exit 0, which it
   does, with zero `RUF100` ("unused noqa") findings, confirmed this run. It is noted here because a
   reader relying on Phase 2's comprehension pass's literal claim ("models.py is still the only file
   with any noqa in the new tree") would now be reading a claim that no longer describes the
   repository: as of this pass, two files carry a noqa suppression, both legitimately, both for the
   same rule.
2. **No new gap Phase 3 itself introduces beyond the above.** Every `PHASE_3_SPEC.md` §5's
   "build-time verification item" (the PRIMARY KEY constraint-violation behaviour) and every §2.1
   "action item" (the live dependency-pin re-check) that the spec explicitly required as a mechanical,
   non-assumed action was in fact performed and logged in `docs/modernization_log.md`, confirmed by
   reading that file's actual new content this pass rather than trusting the spec's instruction that
   it *should* be done.

## 6. Open items

**Carried forward, status re-checked this pass:**

- **The mypy/tests-numpy interaction, re-confirmed above, now with a related second symptom
  outside `.venv`** — still open, still environment-specific, still not phase-blocking (Phase 3
  passes `mypy --strict mizan tests` fully clean inside `.venv`). Unresolved at the CI/tooling
  level; worth fixing by always invoking mypy inside `.venv` in any future automation, which is now
  a harder requirement than before (see §5) since `duckdb` itself cannot even be imported outside it.
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** — still open by
  design; Phase 3 is normalization only and makes no attempt to resolve them (`PHASE_3_SPEC.md` §9).
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged; nothing
  in Phase 3 touches `mizan/config/fiqh_params.py`.
- **The Phase 2 AC15 noqa-enumeration mismatch (`A003` absent from `mizan/data/models.py`)** — still
  present, unaffected by Phase 3 (that file is untouched); now joined by the related second-file
  finding in §5 above.
- **Corporate-action anomaly scan is deliberately conservative and will produce false positives** —
  unchanged from Phase 2's own carried-forward note; still true, still an accepted tradeoff, not a
  defect.
- **No real backfill has been run** — unchanged from Phase 2's own carried-forward note. Everything
  verified in Phase 2 and Phase 3 (and their own reviews) is against fixtures and mocked transports,
  not a full live ~100-ticker × ~10-year run.

**Resolved this phase:**

- **"`mizan/data/normalize.py` does not exist yet"** — Phase 2's comprehension pass flagged this as
  a known, intentional, spec-declared sequencing gap, not a defect. It is now resolved: the module
  exists, is imported by `mizan/cli/normalize.py`, and is covered by 14 tests, all passing this run.

**New this phase:**

- **`fundamentals_facts` and `price_bars` are queryable but nothing reads them yet.** Phase 3 ships
  the typed store; Phase 4's screening layer (`mizan/screening/business_activity.py`,
  `financial_ratios.py`) is the first consumer, per `MASTER_PRD.md` §9.4 and `PHASE_3_SPEC.md` §9.
  Worth knowing before assuming any screening/backtest behaviour exists — it does not yet.
- **The DuckDB file is a local, derived, regenerable artifact with no versioned migration path by
  deliberate V1 design decision (§3 above).** A future schema change requires deleting the
  gitignored `.duckdb` file and re-running `mizan normalize` from the still-intact raw JSON cache,
  not an in-place `ALTER TABLE`. Operationally fine for a single-developer local tool; would need
  revisiting before this became multi-developer or long-lived shared infrastructure.
- **`normalize_edgar_facts` only ever normalizes `companyfacts`-sourced cache entries, never
  `companyconcept`.** No cached `companyconcept` data currently exists for it to be missing anyway
  (`mizan/cli/ingest.py` never fetches it), but a future phase needing that narrower shape normalized
  would require an additive extension to `mizan/data/normalize.py`, not something already covered.
- **No real normalization run against a real, operator-backfilled cache has happened yet** — same
  posture as Phase 2's own deferred real-ingestion-backfill item (`PHASE_3_SPEC.md` §9): normalizing
  the actual ~100-ticker universe, once an operator runs a real backfill with a real
  `TIINGO_API_TOKEN`, is a one-time operator action still pending, not something this phase's
  automated tests exercised.

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
