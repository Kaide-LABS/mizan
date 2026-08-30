# COMPREHENSION.md — Mizan

Written after Phase 4 ("Screening Engine") was reviewed and approved. Sections 1–6 below describe
the repository as it exists right now — Phase 1 ("Foundation & Config"), Phase 2 ("Ingestion & Raw
Cache"), Phase 3 ("Normalization & DuckDB Store"), and Phase 4 combined — grounded in the code read
directly this pass, not in what any spec or prior handoff claimed. The Phase Log at the bottom is
append-only; Phase 1's, Phase 2's, and Phase 3's entries are preserved untouched below the new
Phase 4 entry.

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
can open the actual file on disk and see exactly what the data source sent, unmodified.

Phase 3 turned those saved-but-still-raw files into something a computer program can actually query
and trust. Up through Phase 2, "the data" was just a pile of JSON files on disk, shaped exactly like
whatever SEC or Tiingo happened to send. Phase 3 reads that pile, checks every entry against a
strict, typed shape, and loads it into a real local database (DuckDB) — one table for company
financial facts (revenue, assets, and so on, pulled from SEC filings) and one table for daily stock
prices, with a duplicate guard and a closed unit-of-measurement allow-list built directly into the
loading step.

**Phase 4, the subject of this update, is the first phase where Mizan actually decides whether a
company is halal to invest in.** Given a ticker symbol and a date, `mizan screen` now runs two
checks in order. First, a business-activity check: does the company's registered industry code (SIC
code) fall into a "definitely excluded" bucket (conventional banks, insurers, alcohol, tobacco,
non-halal food) or one of two more debatable buckets (adult content/weapons; media/hotels) that the
owner can turn on or off? If a company is excluded here, screening stops immediately — no amount of
financial cleanliness can rescue a company whose core business itself is disqualifying. Second, if
the business-activity check passes, a financial-ratio check: how much interest-bearing debt does the
company carry relative to its size, how much interest-bearing investment/deposit does it hold, and
how much of its revenue comes from non-halal sources (mainly interest income) — each compared
against a configurable percentage threshold (30%/30%/5% by default, from AAOIFI's own published
methodology). The combination of these two checks produces one of three verdicts — Pure (fully
clean), Mixed (compliant but with some incidental non-halal income requiring "purification," a later
phase's job), or Non-compliant — always accompanied by a full, human-readable explanation of exactly
which check drove the result and by how much.

Two things this phase deliberately did NOT do, stated as plainly as the project's own honesty
discipline demands: it did not hardcode any company-industry classification the SIC-code check
alone would get wrong (a company can be given a manually-researched override, but the map ships
completely empty — no per-ticker research is baked in), and it did not build the real universe of
~100 stocks a person would actually want to screen. **What exists after Phase 4 is a working, fully
tested screening engine — proven correct only against about a dozen invented example companies
(with names like `ZZPURE01`, clearly labeled as fake, never real issuers) built specifically to
exercise every rule the engine implements. It does not yet produce a trustworthy real-world
screening result for any actual company, unless the tool's owner has separately done the hand-
research needed to supply a real SIC override map.** That hand-research is explicitly the owner's
own future work, not something an automated build was ever supposed to fabricate.

Still nothing here runs a backtest or simulates a portfolio — no money is simulated yet, no strategy
picks stocks yet. What exists after Phase 4 is: the settled/disputed rule registry from Phase 1; the
working, rate-limit-respecting, replay-safe data-pulling pipeline from Phase 2; the typed local
database from Phase 3; and now, new this phase, a real, working three-state compliance screen with a
full audit trail — the first piece of Mizan that actually answers "is this halal?" for a single
ticker on a single date, even though the answer is only as good as the (currently synthetic, or
owner-supplied) data behind it.

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
│   ├── verdict.py                # Verdict — the three-state pass/partial/fail screening outcome (definition ONLY — see §2's naming note below)
│   └── caveats.py                # Caveat enum + ResultEnvelope — the mandatory warning-label wrapper for results
├── data/
│   ├── __init__.py                # empty
│   ├── models.py                  # raw wire-format row-shape schemas for EDGAR + Tiingo payloads (Phase 2)
│   ├── raw_cache.py               # shared cache-path / cache-hit / atomic-write / read helpers, both legs (Phase 2)
│   ├── ingest_edgar.py            # EDGAR client: rate limiter, header construction, CIK resolution, fetch fns (Phase 2)
│   ├── ingest_tiingo.py           # Tiingo client: request/symbol budget limiter, EOD fetch, anomaly scan (Phase 2)
│   ├── db.py                      # DuckDB connection + idempotent schema creation (Phase 3)
│   └── normalize.py               # typed row shapes + raw-cache-to-DuckDB mapping functions, incl. resolve_cik_offline (Phase 3)
├── screening/                      # NEW this phase — the whole package is new
│   ├── __init__.py                 # NEW — empty, package marker only
│   ├── business_activity.py        # NEW — SIC-code first-pass tier classifier + pluggable, ships-empty override map
│   ├── financial_ratios.py         # NEW — the 30/30/5 ratio arithmetic, pure functions over already-resolved floats
│   └── verdict.py                  # NEW — screen(), the canonical entry point; combines both layers into a Verdict +
│                                    #        reason trace. DISTINCT from mizan/core/verdict.py — see the naming note below.
└── cli/
    ├── __init__.py                # empty
    ├── main.py                    # `mizan` console-script entrypoint — boot-check-first dispatcher (MODIFIED this phase: registers `screen`)
    ├── ingest.py                  # the `ingest` subcommand (Phase 2, untouched this phase)
    ├── normalize.py               # the `normalize` subcommand (Phase 3, untouched this phase)
    └── screen.py                  # NEW this phase — the `screen` subcommand
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
├── fixtures/                       # NEW this phase
│   ├── __init__.py                 # NEW — package marker
│   └── synthetic_universe.py       # NEW — ~12 SYNTHETIC, clearly-labeled fixture tickers (ZZPURE01, ZZMIXED01, etc.)
│                                    #        and the helpers that materialize them into a cache dir / DuckDB connection
├── test_screening_business_activity.py  # NEW this phase — SIC_TIER_MAP lookups, override precedence both directions, tier toggles
├── test_screening_financial_ratios.py   # NEW this phase — ratio arithmetic, boundary (<=) semantics, numerator-vs-denominator asymmetry
├── test_screening_verdict.py             # NEW this phase — screen() end-to-end over the synthetic universe, fail-fast, look-ahead non-interference
└── test_cli_screen.py                    # NEW this phase — CLI arg parsing, boot-gate-first dispatch, per-ticker HALT/continue behaviour
.env.example                       # TIINGO_API_TOKEN placeholder template, never a real credential
pyproject.toml                    # project metadata, exact dependency version pins, mypy/ruff/pytest config, CLI entry points (UNCHANGED this phase — §2.1)
docs/modernization_log.md         # a running log of exactly which external tool/library versions and API contracts were verified and when (MODIFIED this phase — §6.3, §6.4)
.gitignore                        # UNCHANGED this phase
PHASE_4_SPEC.md                   # NEW this phase — the Phase 4 build contract
```

**The two `verdict.py` files, named explicitly so a future reader is never confused (confirmed by
reading both files in full this pass):** `mizan/core/verdict.py` (Phase 1, unmodified by this
phase's diff — confirmed via `git diff e9a62c3..0060cfd -- mizan/core/verdict.py`, empty) defines
*only* the three-state `Verdict` **enum** — `PURE`/`MIXED`/`NON_COMPLIANT` — with no scoring logic
of its own. `mizan/screening/verdict.py` is a different, much larger module (441 lines) that is
where `screen(ticker, as_of_date)` itself lives, where the business-activity and financial-ratio
layers are combined, and where the reason trace is assembled. Every reference to the enum inside the
new module imports it by full path (`from mizan.core.verdict import Verdict`), never as a bare
`Verdict`, specifically so a `grep -n "Verdict"` distinguishes "the enum" from "the module that
produces it" — confirmed by direct read of `mizan/screening/verdict.py` line 49.

How the Phase 1 pieces connect (unchanged, still true, re-verified this pass):

- `mizan/core/base.py` defines `MizanBaseModel`. Every new Phase 4 model —
  `ActivityOverride`/`BusinessActivityOverrideMap`/`BusinessActivityScreenResult` in
  `business_activity.py`, `FinancialRatioScreenResult` in `financial_ratios.py`, and
  `ReasonTraceEntry`/`ScreeningVerdict` in `verdict.py` — inherits from it, confirmed by direct read
  of every one of those class definitions.
- `mizan/config/invariants.py`, `mizan/config/fiqh_params.py`, and `mizan/config/boot_check.py`
  behave exactly as prior comprehension passes described — confirmed untouched by Phase 4's diff
  (`git diff e9a62c3..0060cfd -- mizan/config/` is empty).
- `mizan/core/caveats.py` is likewise untouched.

How the Phase 2 and Phase 3 pieces connect (unchanged, still true, re-verified this pass):

- `mizan/data/raw_cache.py`'s `cache_path`/`is_cached`/`read_raw_json` are reused directly by Phase
  4's own `resolve_sic_offline` (`mizan/screening/business_activity.py`), the same pattern Phase 3's
  `resolve_cik_offline` already established.
- `mizan/data/ingest_edgar.py`'s `CikResolutionError` is imported and reused by
  `mizan/cli/screen.py` — no new exception type for the same failure kind.
- `mizan/data/normalize.py`'s `resolve_cik_offline` is imported directly by
  `mizan/screening/verdict.py`'s `screen()` — Phase 4 does not re-derive ticker→CIK resolution.
- `mizan/data/db.py` and `mizan/data/normalize.py` are themselves untouched by Phase 4's diff
  (confirmed: neither file appears in `git diff e9a62c3..0060cfd --stat`) — Phase 4 is a read-only
  consumer of the `fundamentals_facts`/`price_bars` tables those modules already built.
- `mizan/cli/ingest.py` and `mizan/cli/normalize.py` are untouched.

How the new Phase 4 pieces connect:

- **`mizan/screening/business_activity.py`** (356 lines) defines `BusinessActivityTier`
  (`TIER_0`/`TIER_0_5`/`TIER_1`, a `StrEnum` whose values are names, never meant to be ordered),
  `ClassificationSource` (`SIC_FIRST_PASS`/`OVERRIDE_MAP`), `ActivityOverride` (one override entry:
  `cik`, `ticker`, `tier_override: BusinessActivityTier | None`, mandatory non-empty `rationale`),
  `BusinessActivityOverrideMap` (`overrides: dict[str, ActivityOverride]`, keyed by zero-padded
  10-digit CIK, never ticker), `BusinessActivityScreenResult`, and `SicResolutionError`. Its module
  constant `SIC_TIER_MAP` (a closed `dict[str, BusinessActivityTier]`) maps 21 real, SEC-verified
  SIC codes across the three tiers (§4 below has the full table). `resolve_sic_offline(cik, *,
  cache_dir)` reads the already-cached `edgar/submissions/{cik}.json` raw file (written by Phase 2,
  never re-fetched) and returns its `sic` field, raising `SicResolutionError` if the cache entry is
  missing or has no usable `sic` key; it takes no network parameter at all. `load_override_map(path)`
  returns an honest empty `BusinessActivityOverrideMap(overrides={})` when `path is None` (no file
  read), or `model_validate_json`s a given path, raising `pydantic.ValidationError` on any malformed
  content. `classify_business_activity(cik, sic, *, overrides, fiqh_params=FIQH_PARAMS)` is a pure
  function (no DB, no cache, no dates, no network — confirmed by its signature and body): an override
  present for `cik` wins outright in either direction (rescues a false positive when
  `tier_override is None`, or flags a false negative when a tier is set); otherwise a Tier 0 SIC match
  always fails, a Tier 0.5 match fails only if `fiqh_params.business_activity_tier_0_5_enabled.value`
  is `True` (default `True`), and a Tier 1 match fails only if
  `fiqh_params.business_activity_tier_1_enabled.value` is `True` (default `False`) — both toggles read
  fresh from `fiqh_params` on every call, never cached.
- **`mizan/screening/financial_ratios.py`** (194 lines) is pure arithmetic over already-resolved
  plain `float`s — confirmed by direct read that no function in this file touches a DB connection,
  cache directory, date, or network call. Four closed `frozenset[str]` allow-lists of XBRL tags:
  `INTEREST_BEARING_DEBT_TAGS`, `INTEREST_BEARING_INVESTMENT_TAGS`, `NON_PERMISSIBLE_INCOME_TAGS`
  (numerator-side; a company reporting under none of them contributes a legitimate `0.0`, not an
  error), and `TOTAL_REVENUE_TAGS` (denominator-side for ratio 3; an empty result here is instead
  `InsufficientDataError`, raised one level up in `verdict.py`). `compute_debt_ratio`,
  `compute_interest_investments_ratio`, and `compute_non_permissible_income_ratio` each call a shared
  private `_ratio_reason` helper that divides, compares with `<=` (a value exactly at the threshold
  passes), and records a signed `margin` (positive = comfortable margin when passing, positive = how
  far over when failing). `compute_financial_ratio_screen` runs all three and combines them —
  `passed` iff all three pass.
- **`mizan/screening/verdict.py`** (441 lines) is the only function body in `mizan/` permitted to
  treat "most-recently-filed fact with `filed <= as_of_date`" as sufficient point-in-time resolution
  (the Fork-1 simplification) — confirmed by direct read that every reference to `filed` inside
  `mizan/screening/` (functional, not prose) lives inside this one file's private helpers
  (`_resolve_total_assets_denominator`, `_resolve_market_cap_denominator`, `_resolve_denominator`,
  `_resolve_tag_set_sum`), all reachable only from `screen()`, and that
  `business_activity.py`/`financial_ratios.py` never reference `filed` as a field access anywhere
  (a plain-text grep for the substring "filed" does surface two hits in `business_activity.py`, but
  both are prose — "filed under" in a comment and "does not reference `filed`" in a docstring — not a
  functional read, confirmed by reading both lines). `screen(ticker, as_of_date, *, con, cache_dir,
  overrides=None, fiqh_params=FIQH_PARAMS)` resolves `cik`/`sic` from the cache only (no DuckDB touch
  yet), runs `classify_business_activity`, and returns immediately with a one-entry reason trace and
  `Verdict.NON_COMPLIANT` if Layer 1 fails — never opening a `fundamentals_facts`/`price_bars` query
  for a Layer-1-failing ticker. If Layer 1 passes, it confirms the ticker was ever normalized at all
  (`_ensure_normalized`, raising `NotNormalizedError` otherwise), resolves the two-axis denominator
  (`_resolve_denominator`, dispatching on `fiqh_params.ratio_denominator_basis.value` between total
  assets and market cap, and on `fiqh_params.ratio_denominator_smoothing.value` between spot and a
  trailing-12-month average — using `raw_close`, never `adj_close`, for the market-cap axis), sums
  every ratio numerator via `_resolve_tag_set_sum`, and combines both layers: `NON_COMPLIANT` if any
  ratio fails, `PURE` if all three ratio `actual_value`s are exactly `0.0`, otherwise `MIXED`. The
  result is wrapped in `ResultEnvelope(active_caveats=(Caveat.LOOK_AHEAD_BIAS,
  Caveat.PENDING_SCHOLARLY_VERIFICATION), payload=screening_verdict.model_dump())` — never
  `Caveat.SURVIVORSHIP_BIAS`, which the module's own docstring states is a universe-selection concern
  for Phase 5, not something one `screen()` call can assert about itself. `screen()` imports
  `classify_business_activity`/`resolve_sic_offline` and `compute_financial_ratio_screen` **locally**
  inside its own body, not at module top level — confirmed by reading the function body — to break a
  genuine two-way import dependency (`business_activity.py`/`financial_ratios.py` both need
  `ReasonTraceEntry`/`ScreenName`, defined in `verdict.py`, to type their own result models).
- **`mizan/cli/screen.py`** (119 lines) registers `screen --ticker TICKER [--ticker TICKER ...]
  --as-of-date YYYY-MM-DD --db-path PATH --cache-dir PATH [--overrides-path PATH]`. `--overrides-path`
  is the only optional flag, defaulting to `None` (no hidden default file). `run()` opens exactly one
  read-only DuckDB connection (`db.connect(args.db_path, read_only=True)` — confirmed by direct read,
  `screen` never writes to DuckDB), loads the override map once, then for each ticker calls `screen()`
  and prints the verdict plus every reason-trace entry to stdout, catching
  `CikResolutionError`/`SicResolutionError`/`NotNormalizedError`/`InsufficientDataError` per ticker
  and printing a `HALT [{ticker}]: ...` line to stderr while continuing to the next ticker — returning
  exit code 1 if any ticker halted, the same contract `mizan.cli.ingest.run`/`mizan.cli.normalize.run`
  already established.
- **`mizan/cli/main.py`** gained one new import and one new registration line
  (`screen_cli.add_subparser(subparsers)`) — confirmed by reading the diff; `main()`'s boot-check-first
  dispatch is otherwise unchanged, so `mizan screen` also halts before any screening logic runs if the
  Phase 1 foundation is broken.
- **`tests/fixtures/synthetic_universe.py`** (470 lines) defines 12 `SyntheticTicker` fixtures
  (`ZZPURE01`, `ZZMIXED01`, `ZZNONCOMP_ACT01`, `ZZNONCOMP_RATIO01`, `ZZNONCOMP_RATIO02`,
  `ZZTIER05_01`, `ZZTIER1_01`, `ZZOVERRIDE_RESCUE01`, `ZZOVERRIDE_FLAG01`, `ZZBOUNDARY01`,
  `ZZLOOKAHEAD01`, `ZZNODATA01`, confirmed by counting `ALL_SYNTHETIC_TICKERS`), every one using a
  CIK with the unmistakably-synthetic `999...` prefix and a module-top docstring stating explicitly
  that none of them is a real issuer. `write_universe_cache`/`load_into_duckdb` materialize a given
  fixture ticker's facts/price bars/SIC directly into a cache dir and DuckDB connection, bypassing
  `normalize_edgar_facts`/`normalize_tiingo_bars` entirely since these rows already are the
  pre-normalized shape `screen()` consumes.
- `pyproject.toml` is **unmodified** by this phase — confirmed absent from the diff stat; Phase 4
  adds zero new third-party dependencies (pure computation over `pydantic` schemas and already-open
  `duckdb` connections).
- `docs/modernization_log.md` gained two new dated (2026-08-30) entries this phase, both read in
  full: §6.3 logs a live XBRL-concept-tag verification against real EDGAR `companyfacts` responses
  for six real companies (13 of 14 candidate tags confirmed; `LongTermInvestments` could not be
  confirmed against any of the six and is logged `[UNVERIFIED]`); §6.4 logs a live verification of
  every `SIC_TIER_MAP` code against SEC's own published SIC code list plus a live EDGAR
  company-search per code, and records that `PHASE_4_SPEC.md` §4.1's own illustrative "7993
  (gambling)" example is not an SEC-assigned SIC code at all and was omitted rather than shipped (see
  §3 below).

## 3. Decisions and tradeoffs

**Carried forward from Phase 1 (still shipped, not overturned by any later phase):**

- `FiqhParam` remains generic (`FiqhParam[T]`), not a `bool | float | str` union. `mizan/config/`
  remains untouched by Phase 4's diff.
- `check_invariants()` / `check_fiqh_register()` remain hand-written, field-by-field checks rather
  than a generic loop.
- `StrEnum` (not `class X(str, Enum)`) remains the pattern for every enum in the project, including
  Phase 4's new `BusinessActivityTier`, `ClassificationSource`, and `ScreenName` — confirmed by direct
  read of all three definitions.

**Carried forward from Phase 2/3 (still shipped, not overturned by Phase 4):**

- `read_raw_json`'s `object` return type remains load-bearing: `resolve_sic_offline`
  (`mizan/screening/business_activity.py`) narrows it with `isinstance(raw, dict)` before reading
  `sic`, the same pattern Phase 3's `normalize.py` already used for its own reads.
- DuckDB's single-writer lock, the dedup-then-insert-with-backstop pattern, and the closed
  `RECOGNIZED_XBRL_UNITS` allow-list are all unaffected — `mizan/data/db.py` and
  `mizan/data/normalize.py` are both untouched by Phase 4's diff.
- The Phase 2/3 `# noqa: N812` findings on the `_Date` alias in `mizan/data/models.py` and
  `mizan/data/normalize.py` are unaffected; see §5 below for whether a third instance appears in
  Phase 4's own new code.

**New this phase — real decisions/resolutions, each verified directly against the code and
`docs/modernization_log.md` this pass:**

- **The SIC-code omission finding: `PHASE_4_SPEC.md` §4.1's own illustrative "7993 (gambling)" entry
  does not exist in the shipped `SIC_TIER_MAP`, and this is a documented finding, not an oversight.**
  Verified live 2026-08-30 (`docs/modernization_log.md` §6.4, read in full this pass) that SIC 7993
  is absent from SEC's own published SIC code list and that a live EDGAR company-search for
  `SIC=7993` returns zero registrants — it was never a real, assigned SEC code, only a plausible-
  looking number the spec's own illustrative table repeated without live verification. Two real
  gambling/casino issuers checked instead (Wynn Resorts, CIK 0001174922; Caesars Entertainment, CIK
  0001590895) both file under SIC 7011 (Hotels & Motels), which `SIC_TIER_MAP` already carries under
  Tier 1. **The tradeoff, stated plainly:** `SIC_TIER_MAP` now has no dedicated Tier-0 gambling code
  at all — a gambling-core-business issuer filed under 7011 is only caught when
  `business_activity_tier_1_enabled` is turned on, or via a hand-researched override — which is a
  real, documented granularity gap in an illustrative engineering constant. The alternative
  (inventing a plausible-looking substitute SIC code that was itself never verified to exist) would
  have been exactly the fabricated-precision failure mode this project's honesty discipline exists to
  forbid; a documented gap is more honest than false completeness, and is logged as such rather than
  silently patched over.
- **`screen()`'s `overrides` parameter default changed from a live `BusinessActivityOverrideMap`
  object (as `PHASE_4_SPEC.md` §4.3's own illustrative signature showed) to `overrides:
  BusinessActivityOverrideMap | None = None`, resolved inside the function body — a lint-rule
  correction, not a behavior change.** Confirmed by direct read of `mizan/screening/verdict.py` lines
  318 and 368–370: `ruff`'s `B008` rule forbids a function call in an argument default (the spec's own
  `BusinessActivityOverrideMap(overrides={})` default expression would trip it), so the shipped code
  uses the `None`-sentinel pattern and resolves it to the identical empty map inside `screen()`'s own
  body on every call. Since `BusinessActivityOverrideMap` is `frozen=True` and an empty map compared
  to another empty map is never observably different, this is behaviorally identical to the spec's
  illustrative default for every caller — purely a tooling-compliance fix, confirmed by reading the
  module's own docstring explaining exactly this.
- **`business_activity.py`, not `normalize.py`, resolves SIC — and this does not violate Phase 4's
  "no new migrations" non-goal, because SIC is read from Phase 2's raw cache, never from DuckDB.**
  Verified directly: Phase 3's two DuckDB tables (`fundamentals_facts`, `price_bars`,
  `mizan/data/db.py`, untouched by this phase) carry no SIC column at all, and SIC lives only in the
  already-cached `edgar/submissions/{cik}.json` file Phase 2's `ingest_edgar_submissions` wrote.
  Resolving it therefore had exactly two options: add a third DuckDB table (which would be a schema
  migration, explicitly forbidden by `PHASE_4_SPEC.md` §5 — "Phase 4 adds no DuckDB table, column, or
  index"), or read the already-cached raw file directly, offline, the same pattern Phase 3's own
  `resolve_cik_offline` already established for `company_tickers.json`. The shipped
  `resolve_sic_offline` (`mizan/screening/business_activity.py` lines 233–257) does the latter — zero
  network capability (no client/httpx parameter exists on its signature, confirmed by reading it), no
  `filed`-based temporal resolution (SIC has no temporal dimension in this cache), and no DuckDB
  touch. Since this reads a Phase-2-owned raw cache file that Phase 3 never touched or normalized
  (`fundamentals_facts`/`price_bars` remain the only two tables Phase 3 built), it is not a
  re-reading of Phase 3's scope — it is applying Phase 3's own established offline-cache-read
  precedent to a data source Phase 3 correctly left alone, without adding any new migration or schema
  surface anywhere.

## 4. Domain mechanics

**Fiqh register — carried forward from Phase 1, unchanged (neither Phase 2, 3, nor 4 touches
`mizan/config/fiqh_params.py`; confirmed by re-reading it this pass), now shown alongside exactly
which Phase 4 code reads each entry:**

| # | Figure / default | Value in code | Code's own source citation | Read by (Phase 4) |
|---|---|---|---|---|
| 1 | Ratio denominator basis | `market_cap` | AAOIFI SS21 public methodology (Merah presentation, Oct 2017) — **[UNVERIFIED / INFERENCE]**, basis not stated in the public methodology | `FiqhParams.ratio_denominator_basis`, `mizan/screening/verdict.py`'s `_resolve_denominator` |
| 2 | Ratio denominator smoothing | `spot` (unsmoothed) | Same Merah presentation, by contrast with index-provider practice — **[UNVERIFIED / INFERENCE]** | `FiqhParams.ratio_denominator_smoothing`, same function |
| 3 | Debt-ratio threshold | 30% | "Merah presentation slides 32-34," verified verbatim | `FiqhParams.debt_ratio_threshold`, `compute_debt_ratio` |
| 4 | Interest-investments threshold | 30% | "Merah presentation slides 33-34," verified verbatim | `FiqhParams.interest_investments_threshold`, `compute_interest_investments_ratio` |
| 5 | Non-permissible income threshold | 5% | "Merah presentation slide 32," quoted "Non Halal Income Should not Exceed 5% of Total Income" — denominator ambiguity flagged (source says "Income," `MASTER_PRD.md` §6.2 says "revenue") | `FiqhParams.non_permissible_income_threshold`, `compute_non_permissible_income_ratio` — Phase 4 concretely picks the "total revenue" reading to compute with (`TOTAL_REVENUE_TAGS`'s own docstring), which does NOT resolve `ULTIMATE_PRD.md` Q2, only makes a transparent, cited pick so the code can run |
| 6 | Business-activity Tier 0.5 (adult content, weapons/defence) | enabled (default `True`) | Reaches AAOIFI only via its catch-all "unlawful activities" clause | `FiqhParams.business_activity_tier_0_5_enabled`, `classify_business_activity` |
| 7 | Business-activity Tier 1 (media/music/entertainment, hotels) | disabled (default `False`) | "genuinely contested across scholarly bodies" | `FiqhParams.business_activity_tier_1_enabled`, `classify_business_activity` |
| 8–11 | Grace period, capital-gains purification, divestment attribution, purification accounting | unchanged | unchanged | Not read anywhere in Phase 4 — these are Phase 5/6 concerns (`screen()` produces only a Verdict, no purification amount) |

**New this phase — the tiered business-activity screen (`MASTER_PRD.md` §6.1's three tiers,
implemented in `mizan/screening/business_activity.py`'s `SIC_TIER_MAP`), every SIC code verified
live 2026-08-30 against SEC's own published SIC code list and cross-checked for at least one real
registered filer (`docs/modernization_log.md` §6.4):**

| Tier | AAOIFI basis (`MASTER_PRD.md` §6.1) | Real SIC codes shipped in `SIC_TIER_MAP` | Gate |
|---|---|---|---|
| Tier 0 | AAOIFI-explicit (SS21 industry screen): conventional finance, insurance, alcohol, non-halal food, tobacco | `2000`, `2011`, `2013` (food/meat), `2080`, `2082` (beverages/alcohol), `2100`, `2111` (tobacco), `6021`, `6022`, `6029`, `6035`, `6036` (commercial/savings banks), `6311`, `6321`, `6324`, `6331`, `6351`, `6361`, `6399`, `6411` (insurance) | Always fails — never gated by any `fiqh_params` toggle |
| Tier 0.5 | AAOIFI catch-all "any unlawful activity," not SS21-enumerated | `2741`, `2750` (adult-content-adjacent publishing/printing), `3480`, `3760` (ordnance/guided missiles — weapons) | Fails only if `business_activity_tier_0_5_enabled.value is True` (default `True`) |
| Tier 1 | Genuinely contested across scholarly bodies | `7812`, `7822` (motion picture), `7011` (hotels — also the SIC real gambling/casino issuers file under, per the omission finding in §3) | Fails only if `business_activity_tier_1_enabled.value is True` (default `False`) |

**New this phase — the AAOIFI 30/30/5 financial-ratio screen (`MASTER_PRD.md` §6.2, implemented in
`mizan/screening/financial_ratios.py` + `verdict.py`'s denominator resolution), every threshold and
axis read from `FIQH_PARAMS` at call time, never hardcoded:**

| Ratio | Numerator (summed-as-available XBRL tags) | Denominator | Threshold (`FIQH_PARAMS` entry) | Comparison |
|---|---|---|---|---|
| 1. Debt ratio | `INTEREST_BEARING_DEBT_TAGS` = `{LongTermDebtNoncurrent, LongTermDebtCurrent, ShortTermBorrowings, DebtCurrent}` | the two-axis denominator (below) | `debt_ratio_threshold` (30%) | `<=` |
| 2. Interest/investments ratio | `INTEREST_BEARING_INVESTMENT_TAGS` = `{ShortTermInvestments, LongTermInvestments, MarketableSecuritiesCurrent}` | same two-axis denominator | `interest_investments_threshold` (30%) | `<=` |
| 3. Non-permissible income ratio | `NON_PERMISSIBLE_INCOME_TAGS` = `{InvestmentIncomeInterest, InterestIncomeOther, InterestAndDividendIncomeOperating}` — a documented, sourced proxy for "non-halal income," not a settled AAOIFI-named line item | `TOTAL_REVENUE_TAGS` = `{Revenues, RevenueFromContractWithCustomerExcludingAssessedTax}`, always — never the two-axis choice | `non_permissible_income_threshold` (5%) | `<=` |

**The two-axis denominator** (`_resolve_denominator`, `mizan/screening/verdict.py`): Axis A —
`ratio_denominator_basis` — `TOTAL_ASSETS` (sum of `us-gaap:Assets`, unit USD, instantaneous) vs.
`MARKET_CAP` (default; `dei:EntityCommonStockSharesOutstanding` × `price_bars.raw_close`, never
`adj_close`). Axis B — `ratio_denominator_smoothing` — `SPOT` (default; single most-recently-filed
value) vs. `AVERAGED` (mean of one value per distinct `period_end`/`trade_date` within the trailing
12 months of `as_of_date`). All four `<=` comparisons use AAOIFI's own verbatim "should not EXCEED"
wording (a value exactly at the threshold passes) per `docs/modernization_log.md` §7's citation of
the Merah presentation (slides 32–34) — the exact phrase "should not EXCEED" appears in that source
document as quoted in this project's own register entry #5 above, not as a separate literal
sentence in `docs/modernization_log.md` §7's own summary table, which instead states "30% / 30%
thresholds ... verified (slides 32–34)"; both point to the same primary source and the same
verified figures, so this is a citation-precision note, not a discrepancy.

**Ingestion and normalization domain mechanics — carried forward from Phase 2/3, unchanged (neither
`ingest_edgar.py`, `ingest_tiingo.py`, `db.py`, nor `normalize.py` is touched by Phase 4's diff):**
SEC EDGAR's 10 req/s rate limit and ≥600s block cooldown, Tiingo's 50/hour–1,000/day request budget
and 500-ticker/month unique-symbol cap, the corporate-action anomaly heuristic, the
`fundamentals_facts`/`price_bars` uniqueness keys, and the closed `RECOGNIZED_XBRL_UNITS` allow-list
all remain exactly as the Phase 3 comprehension pass described and verified — not re-verified again
in full this pass since the owning code is unchanged, but re-confirmed present and untouched via
`git diff e9a62c3..0060cfd --stat`.

## 5. Honesty audit

Ran the same class of verification `PHASE_4_SPEC.md` §8 (acceptance criteria) and §7 (guards)
specify, against the code as it exists in the repository right now, this run — not trusting the
spec's or the approval commit's claim that they pass. No adversarial re-review was performed (Phase
4 is already approved); this is a comprehension-grade honesty pass.

**Everything below passed as claimed, verified this run, inside the project's `.venv`:**
- `pytest tests/` — **259 passed** (178 carried from Phase 1+2+3 + 81 new this phase across the four
  new test files plus the synthetic fixture module), no regressions.
- `ruff check mizan tests` — "All checks passed!", exit 0, under the pinned `ruff==0.16.5`.
- `mypy --strict mizan tests` — "Success: no issues found in 43 source files" (up from 32 in the
  Phase 3 pass — 11 new files: 4 `mizan/screening/` modules, `mizan/cli/screen.py`,
  `tests/fixtures/__init__.py`, `tests/fixtures/synthetic_universe.py`, and 4 new test files),
  inside `.venv`.
- Boundary greps re-run this pass over the full tree including `mizan/screening/` and
  `mizan/cli/screen.py`: `grep -rniE "openai|anthropic|gemini|vertex|langchain|\bllm\b|
  chat_completion|completion\(" mizan/screening/` — zero hits (G-S1/G-LLM4 clean). `grep -rn
  "duckdb\|httpx\|cache_dir" mizan/screening/business_activity.py mizan/screening/financial_ratios.py`
  — the only hits are `resolve_sic_offline`'s own declared `cache_dir` parameter (G-S7 clean). `grep
  -rn "httpx" mizan/screening/` — zero hits anywhere (G-S8 clean). `grep -rniE "INSERT INTO|CREATE
  TABLE|ALTER TABLE" mizan/screening/` — zero hits (G-DB3 clean). `grep -rn "BaseModel"
  mizan/screening/ mizan/cli/screen.py` — every hit is `MizanBaseModel` or its import, no direct
  `pydantic.BaseModel` subclass anywhere. `grep -rnE "^\s*(import|from)\s+(pandas|matplotlib)"
  mizan/` — zero hits anywhere (no premature import). `git log --format=%B a95af9b..0060cfd` — no
  `Co-Authored-By`, no "Generated with," no model/assistant name (G-AI clean).
- **The `filed`-confinement guard (G-S2) holds, verified precisely, not just by a raw grep count.** A
  plain-text `grep -rl "filed" mizan/screening/` surfaces both `verdict.py` (expected — this is the
  one file permitted to reference it) and `business_activity.py`. Reading the two matching lines in
  `business_activity.py` directly confirms both are prose, not a field access: a comment ("...issuer
  filed under...") and a docstring sentence ("Does not reference `filed` at all..."). No function
  body outside `mizan/screening/verdict.py` performs a `filed`-keyed query or comparison anywhere in
  `mizan/screening/`.
- `pyproject.toml` — confirmed byte-for-byte unmodified by this phase's diff (absent from `git diff
  e9a62c3..0060cfd --stat`); zero new dependencies, matching `PHASE_4_SPEC.md` §2.1's stated decision.

**Phase 1's documented mypy/numpy environment gap, and Phase 3's related duckdb-import gap — both
re-tested this run, both still real, the duckdb gap now touching more files:**

- **Inside `.venv`**: clean, 0 errors, 43 files.
- **Outside `.venv`** (`py -3.14 -m mypy --strict mizan tests`): the original numpy stub failure
  still reproduces verbatim (`numpy/__init__.pyi:737: error: Type statement is only supported in
  Python 3.12 and greater`). The duckdb-import gap Phase 3's comprehension pass first found now
  spans two more files this phase adds: `mizan/screening/verdict.py` and
  `tests/test_screening_verdict.py` both import `duckdb` for type annotations
  (`duckdb.DuckDBPyConnection`) and both now report `Cannot find implementation or library stub for
  module named "duckdb"` outside `.venv`, alongside the four files Phase 3 already affected and
  `tests/fixtures/synthetic_universe.py` (which also imports `duckdb` under `TYPE_CHECKING`). This is
  not a new bug Phase 4 introduces — it is the same environment-specific, already-flagged limitation
  simply reaching one more consumer of `duckdb`'s type, and `PHASE_3_SPEC.md`/`PHASE_4_SPEC.md`'s own
  "build and verify inside `.venv`" instruction remains the correct, already-documented mitigation.

**Phase 2's AC15 noqa-enumeration finding — re-checked this run, unchanged, no third file added:**

`grep -rn "noqa" mizan/` this pass finds exactly the same two suppressions Phase 3's comprehension
pass already found (`mizan/data/models.py` and `mizan/data/normalize.py`, both `# noqa: N812` on a
`_Date` alias) — Phase 4's new code introduces **no** third `noqa` suppression anywhere; `ruff check
mizan tests` remains clean with zero `RUF100` ("unused noqa") findings. The Phase 2 AC15
file-enumeration mismatch itself (the spec's literal wording named only `models.py`) remains present
and unaffected — it is `models.py`'s own long-standing, out-of-scope-for-this-phase finding, not
something Phase 4 could have fixed or worsened.

**A concrete, real spec-vs-code finding new to this phase, run down to ground rather than restated
from the review's own verdict:**

The `screen()` signature actually shipped (`overrides: BusinessActivityOverrideMap | None = None`)
differs textually from `PHASE_4_SPEC.md` §4.3's own illustrative code block (`overrides:
BusinessActivityOverrideMap = BusinessActivityOverrideMap(overrides={})`). This is not a silent,
unexplained drift: `mizan/screening/verdict.py`'s own docstring (lines 331–335) states the reason
(`ruff`'s `B008` forbids a function call in an argument default) and asserts the behavior is
identical for every caller. Verified this run: `ruff check mizan tests` is in fact clean, and
`BusinessActivityOverrideMap(overrides={})` — constructed either as the spec's literal default or as
the shipped `None`-then-resolve pattern — is a frozen, `extra="forbid"` Pydantic model whose only
field is an empty dict either way, so there is no behavioral divergence, only a mechanical,
correctly-explained deviation from the spec's own illustrative (not normative) code. See §3 above.

**No new gap this pass otherwise found beyond what §3 above already surfaces as a deliberate,
logged decision** (the SIC 7993 omission) rather than a silent one.

## 6. Open items

**The single most important NEW open item this phase, stated prominently because it is the largest
gap between "the pipeline runs" and "the pipeline produces a trustworthy real-world screening
result":**

- **The real ~100-ticker curated universe and its hand-verified business-activity override map still
  do not exist anywhere in this repository.** Phase 4 built the generic, configurable screening
  MECHANISM — `SIC_TIER_MAP` (a small, closed, publicly-sourced engineering constant) plus
  `BusinessActivityOverrideMap` (a pluggable map that ships completely empty) — verified only against
  ~12 explicitly-synthetic fixture tickers (`ZZPURE01`, etc., never real issuers). It did **not**
  build, and was never supposed to build, the real hand-researched activity map `MASTER_PRD.md` §6.1
  calls the honest V1 implementation for an actual usable universe. That hand-research — reading real
  10-Ks, real business-segment disclosures, real conglomerate structures for ~100 real tickers — is
  explicitly the project owner's own future work (`PHASE_4_SPEC.md` §9's first, most prominent
  non-goal), not a code task any later automated phase should attempt to fabricate. Until that
  research is supplied (via a real `--overrides-path` JSON file, in the documented format), `mizan
  screen` run against a real ticker produces only a generic SIC-first-pass result — not a
  trustworthy, hand-verified real-world compliance answer for that company.

**Carried forward, status re-checked this pass:**

- **The mypy/numpy-outside-.venv gap, and the now-larger duckdb-import gap it travels with** — still
  open, still environment-specific, still not phase-blocking (Phase 4 passes `mypy --strict mizan
  tests` fully clean inside `.venv`, 43 files). See §5.
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** — still open by
  design. Phase 4's own `TOTAL_REVENUE_TAGS` docstring states explicitly that picking "total revenue"
  to compute with does **not** resolve Q2 (Total Income vs. total revenue) — it remains escalated,
  unchanged, exactly as every prior phase's comprehension pass carried it forward.
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged; nothing
  in Phase 4 touches `mizan/config/fiqh_params.py`.
- **The Phase 2 AC15 noqa-enumeration mismatch (`A003` absent from `mizan/data/models.py`)** — still
  present, unaffected by Phase 4 (that file is untouched).
- **Corporate-action anomaly scan is deliberately conservative and will produce false positives** —
  unchanged, still an accepted tradeoff, not a defect.
- **No real backfill has been run** — unchanged. Everything verified in Phases 1–4 (and their own
  reviews) is against fixtures and mocked transports/synthetic data, not a full live ~100-ticker ×
  ~10-year run, and not a real screening result for any actual company.
- **The DuckDB file remains a local, derived, regenerable artifact with no versioned migration
  path** — unchanged from Phase 3's own carried-forward note; Phase 4 adds no migration either (§5 of
  `PHASE_4_SPEC.md`, confirmed: no new table/column/index anywhere under `mizan/screening/`).

**Other new Phase 4 open items:**

- **`LongTermInvestments` (one of `INTEREST_BEARING_INVESTMENT_TAGS`'s three candidate tags) could
  not be confirmed live against any of the six real companies checked this phase** (Apple, JPMorgan,
  Travelers, NIKE, Caterpillar, Progressive) — logged `[UNVERIFIED]` in `docs/modernization_log.md`
  §6.3 rather than silently assumed. It remains a standard, taxonomically valid `us-gaap` concept
  name; its live presence in a real filing is simply unconfirmed by this phase's own verification
  pass. Worth a real company's `companyfacts` response actually reporting it being checked before
  this tag is trusted without caveat.
- **The `SIC_TIER_MAP` has no dedicated Tier-0 code for gambling/casino issuers** (the SIC-7993
  omission finding, §3 above) — a real gambling-core-business issuer filed under the real SIC 7011
  (hotels) is only caught if `business_activity_tier_1_enabled` is turned on, or via a hand-researched
  override. This is a known, documented granularity limitation of the generic SIC-first-pass
  mechanism, not a silently-dropped requirement, but it means the default configuration
  (`business_activity_tier_1_enabled=False`) will NOT catch a real-world casino operator on SIC alone.
- **Nothing yet consumes `screen()`'s output over time or across a universe.** `screen()` produces a
  single verdict for one ticker at one `as_of_date` — it does not track state, does not know about
  holdings, and does not decide when a previously-compliant ticker's flip should trigger divestment.
  That is explicitly Phase 5's `compliance_state.py`/backtest engine, unread by Phase 4.

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
