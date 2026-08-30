# COMPREHENSION.md — Mizan

Written after Phase 2 ("Ingestion & Raw Cache") was reviewed and approved. Sections 1–6 below
describe the repository as it exists right now — Phase 1 ("Foundation & Config") and Phase 2
combined — grounded in the code read directly this pass, not in what any spec or prior handoff
claimed. The Phase Log at the bottom is append-only; Phase 1's entry is preserved untouched below
the new Phase 2 entry.

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

Phase 2, the subject of this update, is the first phase that actually talks to the outside world.
It teaches Mizan how to go out and pull real financial data for a given stock ticker from two
sources — the US government's own company-filings database (SEC EDGAR, for company fundamentals
like revenue and debt) and a commercial market-data provider (Tiingo, for daily stock prices and
dividends) — and to save every single response it gets to a local folder on disk before doing
anything else with it. The point of saving everything first is honesty and reproducibility: if the
program is run again for the same ticker and date range, it re-uses what it already saved instead
of asking the data provider again (saving time and respecting each provider's usage limits), and if
something ever looks wrong with the saved data, a human can open the actual file on disk and see
exactly what the data source sent, unmodified, rather than trusting the program's memory of it.

Phase 2 also teaches the program to be a polite, rule-following guest of both data providers: SEC
EDGAR asks that requests be spaced out and clearly identify who's asking, and if that's ignored the
site blocks the requester for ten minutes; Tiingo's free tier caps how many requests can be made in
an hour, in a day, and how many different stock tickers can be looked up in a calendar month. The
program tracks all of these limits itself and either waits patiently when it's allowed to, or stops
and reports the problem to a human when a limit means something is actually wrong (for example, if
someone tries to look up more different companies in a month than the free plan allows). It also
does one small piece of quality-control on prices: if it ever sees a day where a stock's price
history says a "split" happened (the kind of event that changes share count) but the same day shows
no dividend payment recorded, it flags that day for a human to look at, because that specific
combination has, in the past, turned out to sometimes mean a dividend record went missing rather
than that a stock split cleanly.

Still nothing here screens a stock for compliance or runs a backtest — no money is simulated, no
pass/fail verdict is produced yet. What exists after Phase 2 is: the settled/disputed rule registry
from Phase 1, plus a working, rate-limit-respecting, replay-safe pipeline for pulling and locally
caching the two kinds of real-world data (fundamentals and prices) that the screening and backtest
phases still to come will need to read from disk, unchanged from what the source actually sent.

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
├── data/                         # NEW this phase
│   ├── __init__.py                # empty
│   ├── models.py                  # raw wire-format row-shape schemas for EDGAR + Tiingo payloads
│   ├── raw_cache.py               # shared cache-path / cache-hit / atomic-write / read helpers, both legs
│   ├── ingest_edgar.py            # EDGAR client: rate limiter, header construction, CIK resolution, fetch fns
│   └── ingest_tiingo.py           # Tiingo client: request/symbol budget limiter, EOD fetch, anomaly scan
└── cli/                          # NEW this phase
    ├── __init__.py                # empty
    ├── main.py                    # `mizan` console-script entrypoint — boot-check-first dispatcher
    └── ingest.py                  # the `ingest` subcommand: argument parsing, per-ticker orchestration
tests/
├── __init__.py                   # empty
├── test_invariants.py            # proves the boot check actually rejects a broken settled-rule config
├── test_fiqh_params.py           # proves the 11-row register is complete, honest, and structurally sound
├── test_core_types.py            # proves the shared base model, Verdict, and Caveat/ResultEnvelope behave as documented
├── test_data_models.py           # NEW — proves every mizan/data/models.py schema parses/rejects as documented
├── test_raw_cache.py             # NEW — proves cache_path/is_cached/write_raw_json/read_raw_json behave as documented
├── test_ingest_edgar.py          # NEW — rate limiter timing, header contract, CIK resolution, HALT paths
├── test_ingest_tiingo.py         # NEW — budget throttling, symbol-log drift, anomaly scan, token handling
└── test_cli_ingest.py            # NEW — CLI arg parsing, boot-gate-first dispatch, per-ticker HALT/continue behaviour
.env.example                       # NEW — TIINGO_API_TOKEN placeholder template, never a real credential
pyproject.toml                    # project metadata, exact dependency version pins, mypy/ruff/pytest config, CLI entry points
docs/modernization_log.md         # a running log of exactly which external tool/library versions and API contracts were verified and when
```

How the Phase 1 pieces connect (unchanged, still true, re-verified this pass):

- `mizan/core/base.py` defines `MizanBaseModel`, a Pydantic model with three settings turned on that
  Pydantic does not turn on by default: unknown fields are rejected outright rather than silently
  dropped, every instance is immutable once created, and default values are validated the same as
  any user-supplied value. Every other model class in the project — `Invariants`, `FiqhParam`,
  `FiqhParams`, `ResultEnvelope`, and now every Phase 2 model in `mizan/data/models.py` — inherits
  from this one base. A test (`test_only_core_base_imports_or_subclasses_pydantic_basemodel` in
  `tests/test_core_types.py`) enforces this by scanning every `.py` file under `mizan/` for the
  literal word `BaseModel`; re-run this pass, it still finds nothing outside `core/base.py`.
- `mizan/config/invariants.py`, `mizan/config/fiqh_params.py`, and `mizan/config/boot_check.py`
  behave exactly as Phase 1's comprehension pass described — untouched by Phase 2's diff
  (`git diff 942d87a..bb947c5` touches none of `mizan/config/`).
- `mizan/core/verdict.py` and `mizan/core/caveats.py` are likewise untouched by Phase 2.

How the new Phase 2 pieces connect:

- `mizan/data/models.py` defines five schemas, all subclassing `MizanBaseModel`: `CompanyTickerEntry`
  (one row of EDGAR's `company_tickers.json`), `EdgarFactRow` (one XBRL fact object), 
  `EdgarSubmissionRecord` (the slice of a CIK's submissions record Mizan actually reads — `cik`,
  `entityType`, `sic`, `sicDescription`, `name`, `tickers`, `exchanges` — not a full mirror of SEC's
  much larger payload), `TiingoEodBar` (one daily price bar, with `close` and `adjClose` declared as
  two distinct required fields, never collapsed into one), and `TiingoCorporateActionEvent` (a small
  derived view over one `TiingoEodBar`, built only via its `from_bar` classmethod, used solely by the
  anomaly scan). Wire-format field names are kept verbatim — camelCase where SEC/Tiingo actually use
  camelCase (`entityType`, `adjOpen`, `divCash`, `splitFactor`, etc.) — rather than renamed to
  snake_case, so the cache stores exactly what the source sent.
- `mizan/data/raw_cache.py` is the one shared home for cache mechanics both ingestion legs use:
  `cache_path()` builds a deterministic `Path` from `(cache_dir, source, key, ext)`; `is_cached()`
  checks existence/non-emptiness with a `stat()` only; `write_raw_json()` writes bytes to a `.tmp`
  file and `os.replace()`s it into place (atomic, no re-serialization); `read_raw_json()` parses the
  cached file back with `json.loads`, returning the deliberately permissive `object` type (see §3)
  and raising `RawCacheError` on a corrupt file rather than a partial parse.
- `mizan/data/ingest_edgar.py` builds every EDGAR request through `_edgar_get`, which routes through
  a single module-level `_EdgarRateLimiter` instance enforcing ≥0.12s spacing between requests and a
  ≥600s cooldown-then-one-retry on a 429, and raises `EdgarBlockedError` immediately (no retry) on a
  403. `resolve_cik()` fetches (cache-aware) `company_tickers.json`, zero-pads the matched entry's
  `cik_str` to 10 digits, then fetches that CIK's submissions record and cross-checks its `name`
  against the ticker entry's `title` via a hand-written, legal-suffix-stripping comparator
  (`_names_match`), raising `CikResolutionError` on a mismatch (post-merger ticker/CIK drift) or an
  absent ticker. `ingest_edgar_submissions`, `ingest_edgar_companyfacts`, and
  `ingest_edgar_companyconcept` all follow the same cache-hit/cache-miss/write/validate shape, each
  raising a dedicated error (`MissingSicError`, `MissingCompanyFactsError`) or letting
  `pydantic.ValidationError` propagate unwrapped on a row-shape drift.
- `mizan/data/ingest_tiingo.py` builds every request via `ingest_tiingo_eod`, which first registers
  the ticker against a persisted per-calendar-month unique-symbol log (`_register_symbol_or_raise`,
  raising `TiingoUniverseDriftError` past 500 distinct symbols/month), then consumes one unit from a
  module-level `_TiingoBudget` instance that tracks and throttles against separate hourly (50) and
  daily (1000) request counters (sleeping to the next hour boundary when exhausted, never raising),
  then fetches, writes to cache, parses every bar as `TiingoEodBar`, and finally runs
  `_scan_for_corporate_action_anomalies`, raising `SuspectedCorporateActionAnomalyError` if any bar
  shows a nonzero `splitFactor` with zero `divCash` on the same date.
- `mizan/cli/main.py`'s `build_parser()` registers exactly one subparser this phase (`ingest`, via
  `mizan.cli.ingest.add_subparser`) and its `main()` calls `mizan.config.boot_check.check_all()`
  first, before any subcommand dispatch, exiting 1 on `InvariantViolationError` or
  `FiqhRegisterError` — no subcommand runs against an unverified foundation.
- `mizan/cli/ingest.py`'s `run()` iterates `--ticker` arguments, calling `resolve_cik` →
  `ingest_edgar_submissions` → `ingest_edgar_companyfacts` → `ingest_tiingo_eod` per ticker in that
  order (EDGAR before Tiingo, so a HALT on the EDGAR leg is caught before spending Tiingo request
  budget on a ticker that will end up unanalyzed anyway). A per-ticker exception in
  `_HALTING_ERRORS` prints a `HALT [ticker]: ...` line to stderr and continues to the next ticker,
  but the process's overall exit code is non-zero if any ticker halted.
- `pyproject.toml` promotes `httpx==0.28.1` from a Phase-1-forward-declared optional extra to a real
  `[project.dependencies]` entry (Phase 2 is the first phase that actually imports it), removes the
  now-empty `ingest` extra, and adds the `mizan` console script (`mizan.cli.main:main`) alongside
  Phase 1's `mizan-boot-check`. The `data` and `report` extras (duckdb/pyarrow/pandas,
  matplotlib) remain forward-declared and unused — nothing in the current tree imports them,
  verified via the boundary greps in §5.
- `docs/modernization_log.md` gained a Phase 2 `httpx` re-check entry (§3, confirming `0.28.1` is
  still latest-stable as of 2026-08-30) and, per the diff read this pass, §6's "External data-source
  contracts" section documents the live-verified EDGAR and Tiingo endpoint shapes and limits that
  §4 below cites directly.

## 3. Decisions and tradeoffs

**Carried forward from Phase 1 (still shipped, not overturned by Phase 2):**

- `FiqhParam` remains generic (`FiqhParam[T]`), not a `bool | float | str` union, to avoid
  depending on Pydantic's own stated-unstable "smart union" resolution order. Unaffected by this
  phase — `mizan/config/fiqh_params.py` is untouched in the Phase 2 diff.
- `check_invariants()` / `check_fiqh_register()` remain hand-written, field-by-field checks rather
  than a generic loop, for the same reason as before (a generic loop would silently pass an
  unchecked new field). Unaffected by this phase.
- `StrEnum` (not `class X(str, Enum)`) remains the pattern for `VerificationStatus`, `Verdict`, and
  `Caveat`. Unaffected by this phase.

**New this phase — five real decisions/resolutions, each verified directly against the code this
pass:**

- **`read_raw_json`'s return type was loosened from the spec's literal `dict[str, object]`
  (`PHASE_2_SPEC.md` line 375) to the actual shipped `object`** (`mizan/data/raw_cache.py`, verified
  this run). The tradeoff: EDGAR's four cached endpoints all return a top-level JSON *object*, but
  Tiingo's EOD endpoint returns a top-level JSON *array* of bars — a cache reader shared by both
  ingestion legs cannot honestly claim a `dict` return type without lying about one of them. Typing
  the return as `object` is less immediately useful at each call site (every caller must narrow with
  an `isinstance` check before indexing — confirmed in both `ingest_edgar.py`'s
  `_require_json_object` helper and `ingest_tiingo.py`'s inline `isinstance(bars_raw, list)` check)
  but keeps one shared, honest cache-reading function rather than forking it into two near-identical
  ones or silently mistyping one leg. The cost is pushed to the callers, deliberately, rather than
  hidden in the shared module.
- **Two ruff-noqa corrections driven by the actual pinned `ruff==0.16.5`'s real behaviour, not the
  spec's illustrative code.** `PHASE_2_SPEC.md` (line 290) shows `open: float  # noqa: A003` for
  `TiingoEodBar`'s field that shadows the builtin `open()`. The shipped code
  (`mizan/data/models.py` line 108) carries no `A003` suppression at all — verified this run by
  running `ruff check mizan tests` under the pinned version, which reports "All checks passed!"
  with zero `A003` findings anywhere in the tree, confirming the rule doesn't fire here under this
  ruff version's real behaviour on a Pydantic model field (a suppression for a warning that isn't
  raised would itself be flagged by ruff's `RUF100`, "unused noqa directive"). Conversely, the
  shipped code adds one suppression the spec's shown code never mentions: `from datetime import
  date as _Date  # noqa: N812` (line 25), because ruff's `N812` (lowercase import aliased to
  non-lowercase, or vice versa) does fire on this alias under the pinned version. Net effect: one
  suppression removed, one added, both discovered empirically against the real pinned tool rather
  than copied from the spec's own example code — `ruff check mizan tests` is verified clean this
  run either way.
- **EDGAR's write-cache-before-validate ordering was resolved to mirror Tiingo's own explicit
  precedent, rather than the generic pseudocode order `PHASE_2_SPEC.md` §6.2 sketches (validate,
  then write).** Verified in the actual code: `ingest_edgar_submissions`, `ingest_edgar_companyfacts`,
  and `ingest_edgar_companyconcept` (`mizan/data/ingest_edgar.py`) all call `write_raw_json()`
  *before* parsing/validating the response — a fact that appears in each function's own docstring
  and module docstring. `PHASE_2_SPEC.md` §6.4 states this ordering explicitly and only for Tiingo's
  anomaly scan ("the raw response is written to cache before this check runs, so a flagged run's
  data is still on disk for a human to inspect"); `ingest_tiingo_eod` follows the identical order in
  the shipped code (`write_raw_json` before `TiingoEodBar.model_validate` and before the anomaly
  scan). The tradeoff: writing before validating means a malformed/drifted response still lands on
  disk even though it will immediately trigger a `pydantic.ValidationError` or a halt — the
  alternative (validate first) would keep the cache directory free of any file that failed
  validation, at the cost of losing the one thing a human needs to diagnose *why* it failed. Both
  legs now resolve this the same way, closing a gap the generic §6.2 sketch left ambiguous for
  EDGAR specifically.
- **The Tiingo credential's environment variable is named `TIINGO_API_TOKEN`, per the spec's own
  literal text** (`PHASE_2_SPEC.md` §4.4, `TIINGO_TOKEN_ENV_VAR = "TIINGO_API_TOKEN"` in
  `mizan/cli/ingest.py`, and `.env.example`, all verified to agree this run). Not a deviation, but
  worth stating as a decision precisely because it's the one credential-facing name in the whole
  phase: the tradeoff is between a shorter name (`TIINGO_TOKEN`) and the spec's fuller,
  self-documenting one — the fuller name was kept, at the cost of a few extra characters at every
  call site, so a `printenv` or `.env` file is unambiguous about which provider it authenticates
  against without needing to open the code.

## 4. Domain mechanics

**Fiqh register — carried forward from Phase 1, unchanged (Phase 2 is ingestion only; nothing in
its diff touches `mizan/config/fiqh_params.py`):**

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
sourced to `MASTER_PRD.md` §2 and `ULTIMATE_PRD.md` §5. Re-verified this pass via the ULTIMATE_PRD.md
§5 boundary greps (§5 below) rather than re-asserted from memory.

**New this phase — ingestion domain mechanics, every figure cross-checked against
`docs/modernization_log.md` §6 (live-verified 2026-08-30) and the shipped code:**

| Figure | Value | Code enforcing it | Citation |
|---|---|---|---|
| SEC EDGAR rate limit | 10 requests/second per IP; Mizan spaces at ≥0.12s | `_EdgarRateLimiter.wait_for_slot`, `mizan/data/ingest_edgar.py` | `docs/modernization_log.md` §6.1, sourced to sec.gov/privacy.htm#security |
| SEC EDGAR block cooldown | ≥600s (10 min) wait, floored even if `Retry-After` is shorter, before one retry; a second consecutive block halts | `_EdgarRateLimiter.note_block`, `_edgar_get` | Same §6.1 |
| SEC EDGAR User-Agent requirement | Descriptive `User-Agent` + real contact email required; a bare/missing UA gets HTTP 403 | `_edgar_headers` (`_EDGAR_USER_AGENT = "Mizan research sandbox schoolbalogun@gmail.com"`) | Same §6.1, "empirical: confirmed 2026-08-30" |
| CIK zero-padding + name cross-check | `cik_str` zero-padded to 10 digits (`f"{cik:010d}"`); resolved CIK's submissions `name` cross-checked against `company_tickers.json`'s `title` (legal-suffix/case/whitespace-insensitive) | `resolve_cik`, `_names_match`, `mizan/data/ingest_edgar.py` | `PHASE_2_SPEC.md` §6.3; `ULTIMATE_PRD.md` §4.1's ticker→CIK-drift guard |
| Tiingo request budget | 50 requests/hour, 1,000 requests/day — throttled (sleeps to next hour boundary), never raised on its own | `_TiingoBudget.consume`, `mizan/data/ingest_tiingo.py` | `docs/modernization_log.md` §6.2, sourced to tiingo.com/pricing |
| Tiingo unique-symbol budget | 500 unique tickers/calendar month — a 501st distinct ticker in one month raises `TiingoUniverseDriftError` immediately, never retried | `_register_symbol_or_raise`, persisted month-keyed symbol log | Same §6.2; `ULTIMATE_PRD.md` §4.2 categorizes universe drift as non-transient, unlike request-budget exhaustion |
| Corporate-action anomaly heuristic | A bar with `splitFactor != 1.0` and `divCash == 0.0` on the same date is flagged (deliberately conservative — an ordinary split with no dividend also flags) | `_scan_for_corporate_action_anomalies`, `mizan/data/ingest_tiingo.py` | `PHASE_2_SPEC.md` §6.4; `ULTIMATE_PRD.md` §4.2, "missing divCash on a known ex-dividend date" |
| Adjusted vs raw close never conflated | `TiingoEodBar.close` and `.adjClose` are two independently required fields; no function derives one from the other | `mizan/data/models.py` | `PHASE_2_SPEC.md` §7 guard G-T3; `ULTIMATE_PRD.md` §4.2 |

None of these figures are marked `[UNVERIFIED]` by the code — all are drawn from
`docs/modernization_log.md`'s own record of a live/documentation re-check performed 2026-08-30, which
this pass's honesty audit (§5) independently re-ran the boundary/behavioural checks against (not the
live SEC/Tiingo endpoints themselves — no network calls were made this pass; the checks re-run were
`ruff`, `mypy`, `pytest`, and the repository-local boundary greps).

## 5. Honesty audit

Ran the same class of verification `PHASE_2_SPEC.md` §8 (acceptance criteria) and §7 (guards)
specify, against the code as it exists in the repository right now, this run — not trusting the
spec's or the approval commit's claim that they pass.

**Everything below passed as claimed, verified this run, inside the project's `.venv`:**
- `pytest tests/` — **146 passed** (63 carried from Phase 1 + 83 new this phase across the five new
  test files), no regressions.
- `ruff check mizan tests` — "All checks passed!", exit 0, under the pinned `ruff==0.16.5`.
- `mypy --strict mizan tests` — **clean, "Success: no issues found in 26 source files."**
- All eight `ULTIMATE_PRD.md` §5 boundary greps (checks 1–8) — clean. Checks 2–4 and the
  `mizan/screening/`/`compliance_state.py`/`purification.py`-scoped part of check 5 correctly error
  "No such file or directory," because those modules don't exist yet (accurate for a phase that
  ships ingestion only, not a false pass). Check 7's `filed` grep finds exactly three hits, all in
  `mizan/data/models.py` — the field's own docstring mentions and its declaration
  (`filed: _Date`) — no other file references it, consistent with "Phase 2 must never drop or
  reformat it beyond ISO-date parsing" and with the fact that no `as_of_date`-taking function exists
  yet to consume it.
- `git log --format=%B` across all three Phase 2 commits (`2ace895`, `bb947c5`, `e73e9cc`) — no
  `Co-Authored-By`, no "Generated with," no model/assistant name. AC21 holds for this phase too.
- `httpx==0.28.1` pin reconciles identically between `pyproject.toml` and
  `docs/modernization_log.md` §3, with the Phase 2 re-check dated and logged rather than silently
  skipped (AC20).

**Phase 1's documented mypy/numpy gap — re-tested this run, not re-asserted from memory:**

Phase 1's comprehension pass found that `mypy --strict mizan tests` fails outside an isolated
virtual environment because a global, non-Mizan `numpy` install's type stubs (pulled in only because
`pytest`'s `approx()` typing optionally imports `numpy`) use post-3.11 stub syntax that the project's
pinned `python_version = "3.11"` mypy target can't parse. This run:
- **Inside `.venv`** (`.venv/Scripts/python.exe -m mypy --strict mizan tests`): clean, 0 errors, 26
  files. Confirmed `numpy` is not installed in `.venv` at all (`import numpy` raises
  `ModuleNotFoundError` there) — the isolated environment simply never pulls it in, so the failure
  mode cannot occur inside it.
- **Outside `.venv`**, invoked via the machine's global Python 3.14 interpreter
  (`py -3.14 -m mypy --strict mizan tests`): the **exact same failure reproduces verbatim** —
  `numpy/__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater`. This
  confirms the gap is real, still exists, and is environment-specific (a global-site-packages
  artifact), not something Phase 2's new `httpx` dependency introduced or fixed — `httpx` itself
  installs and type-checks cleanly in both environments.

This directly answers `PHASE_2_SPEC.md` AC14's carve-out, which asked this exact question to be
re-confirmed rather than assumed unchanged: the failure is still isolated to the non-Mizan
global-numpy-stub/`pytest` interaction, and Phase 2 was in fact built inside `.venv` (confirmed by
`httpx==0.28.1` being installed there and nowhere else needed), where the gap does not surface at
all.

**One concrete, real spec-vs-code textual finding, not previously visible from reading the spec
alone:**

`PHASE_2_SPEC.md` §8 AC15 states ruff must pass "including the deliberate `# noqa: N815` /
`# noqa: A003` suppressions in `mizan/data/models.py` being the *only* such suppressions in the new
tree." Read directly this run, the shipped `mizan/data/models.py` carries `N815` and `N812`
suppressions, but **no `A003` suppression exists anywhere in the file** (see §3's noqa-corrections
decision above for why). The behavioural claim still holds — `ruff check mizan tests` does exit 0,
and `models.py` is still the only file with any noqa in the new tree — but AC15's literal rule-code
enumeration no longer matches what's on disk. A narrow, cosmetic drift between the acceptance
criterion's exact wording and the shipped code, not a functional gap; noted here rather than
silently reconciled, per this pass's own standard.

## 6. Open items

**Carried forward from Phase 1, status re-checked this pass:**

- **The mypy/tests-numpy interaction, re-confirmed above** — still open, still environment-specific
  (§5). Not phase-blocking for either Phase 1 or Phase 2 (both pass `mypy --strict mizan` scoped to
  the package alone, and pass `mizan tests` inside `.venv`), but any future verification step run
  without `.venv` will still hit this false failure. Unresolved; worth fixing at the CI/tooling
  level (either always invoke mypy inside `.venv`, or scope future invocations to exclude `tests/`)
  rather than continuing to carry it as a per-phase caveat.
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** — still open by
  design. Phase 2 is ingestion only and makes no attempt to resolve them; `PHASE_2_SPEC.md` §9
  restates this explicitly ("No resolution of `ULTIMATE_PRD.md`'s open questions (Q1/Q2/Q3) ...
  unrelated to ingestion").
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged, still
  the honest expected state; nothing in Phase 2 touches `mizan/config/fiqh_params.py`.
- **"No project-scoped virtual environment exists" — RESOLVED this phase, confirmed not merely
  assumed.** Phase 1's comprehension pass flagged the absence of a `.venv` as an open item. A
  `.venv` now exists at the repo root (correctly gitignored per `.gitignore`), and this pass
  confirmed it was actually used, not just present: `httpx==0.28.1` (Phase 2's one new runtime
  dependency) is installed inside it and importable there, `ruff==0.16.5` and `mypy==2.3.1` inside
  it match the pins exactly, and `mypy --strict mizan tests` is fully clean inside it (unlike the
  global interpreter, see §5) — direct evidence Phase 2 was built and verified against the isolated
  environment `PHASE_2_SPEC.md` AC14 itself recommended. Marking resolved rather than carried
  forward.

**New this phase:**

- **Corporate-action anomaly scan is deliberately conservative and will produce false positives.**
  `_scan_for_corporate_action_anomalies` flags every bar with a nonzero `splitFactor` and zero
  `divCash`, including ordinary stock splits with no accompanying dividend — the code's own
  docstring states this is intentional (no reference corporate-actions signal exists to
  disambiguate). This is a known, accepted tradeoff, not a defect, but it means any batch ingest of
  a ticker with a real historical split will halt for human review even when nothing is actually
  wrong — worth knowing before running a real multi-year backfill in operator use.
- **No real backfill has been run.** `PHASE_2_SPEC.md` §9 explicitly excludes the actual
  ~100-ticker × ~10-year production backfill from this phase's own acceptance criteria — it's an
  operator action for after approval, requiring a real `TIINGO_API_TOKEN` the automated build/review
  loop never had. Everything verified this pass (and in Phase 2's own review) is against mocked
  transports and a handful of real-or-recorded fixtures, not a full live run. The rate limiter and
  budget-throttle *logic* is tested; its behaviour under sustained real-world load over hours is not
  yet observed.
- **`mizan/data/normalize.py` does not exist yet.** `MASTER_PRD.md` §9.4 lists it under `data/` as
  part of the eventual module boundary; it is explicitly Phase 3's responsibility
  (`PHASE_2_SPEC.md` §9) to map the raw, wire-format-verbatim rows this phase caches into typed,
  unit-scaled, snake_case DuckDB tables. Not a gap — an intentional, spec-declared sequencing — but
  listed here so a reader of this file knows the raw cache is not yet queryable as structured data.

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
