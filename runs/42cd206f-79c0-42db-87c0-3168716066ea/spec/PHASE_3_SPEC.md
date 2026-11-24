# Phase 3 — Token Screening + Phase 2 Test/Doc Closure

## Goal
Build the per-token crypto business-activity screen (AC 4): a hand-documented verdict map covering
the 14-token locked universe (`mizan.crypto.universe.CRYPTO_UNIVERSE`, all expected to pass) plus
the PRD's named default-reject list (AAVE, COMP, MKR; BNB, OKB, CRO; DOGE, SHIB, PEPE — each with
its stated reason), gated through the existing `CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled`
parameter for the memecoin category only. This phase also closes a large test/documentation gap
left by Phase 2: both Phase 2 executor turns shipped real, ruff-clean, mypy-strict production code
(ingestion, the `candles` table, the 24/7 clock) but **zero new or modified test files** — `git diff
--stat` across both turns touches only `mizan/`, `docs/`, and `README.md`; no file under `tests/`
changed, and the full suite is still exactly 437 tests, the same count the Phase 1 review recorded.
Every test PHASE_2_SPEC.md's own Part A0, A6, B4, B5 and B7 specified is still outstanding, and the
required `docs/crypto/PHASE_2_SPEC.md` governing-document copy (B6) was never made. No screening
module existed before this phase; no backtest wiring, no CLI pipeline verb, no report.

## Scope
In scope: a Part A0 backfill (first agent, before any new work) that writes every test PHASE_2_SPEC.md
specified and never got, copies the governing spec into `docs/crypto/`, and closes three small,
genuinely new correctness gaps (R5 non-finite-row rejection test, R6 Kraken non-tradable-status
rejection test, R7 same-ticker-batch atomicity — this one needs one real production line, a
transaction wrap, not just a test — plus S3/S4 from Phase 2's own Implications section); then Part A
(the crypto token-classification map and `screen_token`/`screen_universe` functions) and Part B
(default-reject-list verdicts, memecoin-parameter gating proof, integration test, docs, scope guard).
Out of scope: everything in "Out of scope for this phase" below.

Every new/edited module: `from __future__ import annotations` where the repo uses it, full type
annotations (`mypy --strict` clean), ruff-clean, module docstring citing `docs/crypto/PHASE_3_SPEC.md
§…`. No new runtime dependency.

## Part A0 (first agent, before any new work) — Phase 2 test/doc closure

PHASE_2_SPEC.md's own "done when" bars for Part A and Part B both name specific test files and
specific test behaviours as the acceptance bar, not merely "ruff/mypy clean, code exists." Neither
Phase 2 executor turn wrote any of them. Close every one of the following before Part A begins — they
are the proof that Phase 2's ingestion/candles/clock code actually behaves as PHASE_2_SPEC.md
specified, which Phase 3's own `screen_universe` (Part B) will be trusted to run against later once a
screening-aware pipeline consumes `candles` rows.

### A0.1 — R1: hard invariants dominate the configurable register (PHASE_2_SPEC.md §A0.1)
**File:** `tests/test_hard_invariants.py` (extend).
- `test_staking_rewards_enabled_cannot_leak_into_the_invariant_surface`: build a `CryptoFiqhParams`
  via `model_copy` with `staking_rewards_enabled` flipped to `value=True`; assert
  `INVARIANTS.cash_yield == 0.0` and `INVARIANTS.lending_or_yield_allowed is False` still hold on the
  unmodified `INVARIANTS` singleton, and `check_invariants()` still passes regardless of the flipped
  register's value.

### A0.2 — R2: every `Invariants` field is referenced by name in `check_invariants` (§A0.2)
**File:** `tests/test_hard_invariants.py` (extend).
- `test_check_invariants_references_every_invariants_field_by_name`: `inspect.getsource(check_invariants)`;
  assert every name in `Invariants.model_fields` appears as a substring of the source. Keep the
  existing `test_invariants_field_count_is_locked_at_ten` alongside it.

### A0.3 — R3: citations name their governing fatwa (§A0.3)
**File:** `tests/test_crypto_fiqh_register.py` (extend). Production code for this already exists —
`mizan/config/boot_check.py::check_crypto_fiqh_register` already checks entries #1/#3 for `"Q504160"`
and entry #2 for one of `"Q106094"`/`"Q125758"`/`"Q310956"` — only the tests are missing.
- `test_check_rejects_a_source_missing_its_governing_citation`: `model_copy` entry #1's `source` to
  `"see docs"` (no `Q504160` substring); assert `check_crypto_fiqh_register(broken)` raises
  `FiqhRegisterError` matching `"citation"` or `"Q504160"`.
- `test_check_rejects_entry_two_with_the_wrong_fatwa_number`: `model_copy` entry #2's `source` to
  reference only `"Q999999"`; assert it raises.
- Confirm `test_check_rejects_blanked_source`/`test_check_rejects_status_drift` still pass unchanged.

### A0.4 — R4: a fill cannot exceed what was requested (§A0.4)
**File:** `tests/test_execution_intent.py` (extend). Production code already exists —
`mizan/execution/intent.py::place_order` already raises `NoIntentToFillError` on overfill (lines
69–73) — only the tests are missing.
- `test_overfill_is_not_intent_to_fill`: `place_order(side=OrderSide.BUY, ticker="BTC",
  requested_quantity=1.0, fill=FillResult(filled_quantity=1000.0, fill_price=100.0))` raises
  `NoIntentToFillError`.
- `test_fill_exactly_matching_requested_quantity_is_allowed`: `filled_quantity == requested_quantity`
  (both `1.0`) succeeds.

### A0.5 — S1: no second execution-layer type can reintroduce a resting order (§A0.5)
**File:** `tests/test_execution_intent.py` (extend).
- `test_no_public_class_in_execution_module_exposes_a_mutation_or_resting_state`: iterate every class
  `mizan.execution.intent` defines (`inspect.getmembers(intent_module, inspect.isclass)` filtered to
  `obj.__module__ == intent_module.__name__`); assert none has a `cancel`/`amend` attribute and none
  that is a `BaseModel` subclass has a field named `status`/`pending`/`open`/`resting`/`cancelable`.

### A0.6 — Part A smoke tests PHASE_2_SPEC.md §A6 specified and neither turn wrote
**Files:** `tests/test_crypto_models.py` (new), `tests/test_crypto_ingest_coinbase.py` (new),
`tests/test_data_db.py` (extend).
- `CandleBar` happy path; each `Field(gt=0.0)` rejection (open/high/low/close); naive-datetime
  rejection via the `_utc_aware` validator; a non-UTC-but-aware datetime rejection.
- `_parse_coinbase_row`/`_parse_kraken_row` happy path (correct field reordering — build the
  Coinbase fixture in `[time, low, high, open, close, volume]` order, NOT OHLC order, and assert the
  returned tuple's `open`/`high`/`low`/`close` land in the right slots) and a wrong-length-row
  `MalformedCandleRowError`.
- `fetch_coinbase_candles` happy path against `httpx.MockTransport` returning one page of
  well-formed rows; asserts returned `CandleBar`s have the right OHLC values in the right fields.
- `fetch_coinbase_candles` raises `CoinbaseProductNotFoundError` against a 404 `MockTransport`.
- `upsert_candles` happy path (insert, `SELECT`, assert row count/values); re-insert the same bars,
  assert row count unchanged; `ensure_schema` run twice on the same connection is a no-op.
- One assertion added to whatever existing schema-creation test covers `ensure_schema` on a fresh
  connection: all three tables (`fundamentals_facts`, `price_bars`, `candles`) exist with their exact
  column sets.

### A0.7 — Part B edge-case tests PHASE_2_SPEC.md §B4 specified and neither turn wrote
**Files:** `tests/test_crypto_ingest_kraken.py` (new), `tests/test_crypto_ingest_coinbase.py`
(extend), `tests/test_crypto_clock.py` (new).
- `test_kraken_always_drops_the_last_open_candle`: a `MockTransport` OHLC fixture whose last row has
  a deliberately sentinel `close`; assert the returned tuple's length is `len(raw_rows) - 1` and that
  row's values never appear in the result.
- `test_kraken_rejects_post_requests_are_never_issued`: capture every `request.method` the
  `MockTransport` handler sees during one `fetch_kraken_candles` call; assert all are `"GET"`.
- `test_kraken_720_candle_cap_is_not_silently_treated_as_full_history`: feed exactly 720 rows;
  assert the function returns without raising, and a source-grep assertion that `"720"` appears in
  `mizan/crypto/ingest_kraken.py` (it already does, as `_KRAKEN_MAX_CANDLES`) so the limitation stays
  documented.
- `test_coinbase_product_not_found_triggers_kraken_fallback`: `ingest_universe_candles` with a
  Coinbase handler that 404s for one ticker and succeeds for the rest, Kraken succeeding for that one
  ticker; assert the returned `{ticker: source}` map shows `"kraken"` only for the 404'd ticker and
  the fallback ticker's `candles` rows carry `exchange="kraken"`.
- `test_a_single_tickers_series_is_never_blended_across_sources`: Coinbase returns a short-but-
  nonempty series for a ticker; assert Kraken is never called for that ticker at all.
- `test_generate_market_days_includes_weekends_and_arbitrary_calendar_dates`: a span including at
  least one Saturday, one Sunday, and a US-equity-market holiday (e.g. 2024-07-04); assert every one
  is present in the returned tuple.
- `test_generate_market_days_is_pure_and_inclusive_of_both_endpoints`: `start_date == end_date`
  returns a one-element tuple; calling twice with identical arguments returns equal tuples.

### A0.8 — Integration tests PHASE_2_SPEC.md §B5 specified and neither turn wrote
**File:** `tests/test_crypto_ingest_integration.py` (new).
- `test_ingest_universe_candles_writes_every_ticker_into_candles_table`: in-memory DuckDB connection
  plus `ensure_schema`, `MockTransport` handlers covering all 14 tickers (mixed Coinbase/Kraken
  fallback); after one `ingest_universe_candles` run, `SELECT DISTINCT symbol FROM candles` returns
  exactly `CRYPTO_UNIVERSE`'s 14 members, every row's `granularity == "1d"`.
- `test_rerunning_ingestion_is_idempotent`: run twice against the same connection/cache dir with
  identical handlers; assert the second run makes zero additional HTTP calls and the `candles` row
  count is unchanged.
- `test_boot_check_still_passes_after_a_full_ingestion_run`: call `mizan.config.boot_check.check_all()`
  after a successful `ingest_universe_candles` call in the same test.

### A0.9 — Phase 2 governing-spec copy PHASE_2_SPEC.md §B6 required and neither turn made
**File:** `docs/crypto/PHASE_2_SPEC.md` (new — copy of
`runs/42cd206f-79c0-42db-87c0-3168716066ea/spec/PHASE_2_SPEC.md`, matching the existing
`docs/crypto/PHASE_1_SPEC.md` precedent for the Phase 1 spec).
- A trivial test asserting the file exists and its first line matches the governing spec's own title,
  mirroring however `docs/crypto/PHASE_1_SPEC.md`'s presence is (or is not) currently test-proven —
  if Phase 1 added no such test, do not invent a new convention here; a file-exists check in
  `tests/test_phase1_scope.py`'s sibling (A0.10 below) is sufficient.

### A0.10 — Scope guard PHASE_2_SPEC.md §B7 specified and neither turn wrote
**File:** `tests/test_phase1_scope.py` (extend) or a new `tests/test_phase2_scope.py`.
- Extend `test_no_forbidden_implementation_modules_exist_under_mizan`'s path scan to also cover
  `mizan/crypto/` (it already scans all of `mizan/`, so confirm this explicitly in a docstring rather
  than silently assuming it — the existing test's `package_root.rglob("*.py")` already walks into
  `mizan/crypto/`, so no code change, only a confirming assertion/comment).
- A new assertion: `mizan/crypto/clock.py` and `mizan/crypto/models.py` import neither `httpx` nor
  `socket` (source-grep, same technique as the existing
  `test_intent_module_has_no_network_or_live_order_capability`).
- A new assertion: `docs/crypto/PHASE_2_SPEC.md` (A0.9) exists on disk.

### A0.11 — R5: non-finite candle values must raise, not silently construct a poisoned bar
**File:** `tests/test_crypto_models.py` (new, if not already created by A0.6).
- `test_parse_rejects_nan_and_infinity_rows`: build a Coinbase-shaped row and a Kraken-shaped row each
  containing one `float("nan")` and, separately, one `float("inf")` value (Python's `json` module
  round-trips both even though strict JSON forbids them); assert both `_parse_coinbase_row` and
  `_parse_kraken_row` raise `MalformedCandleRowError` for each case. `mizan/crypto/models.py::_finite`
  already guards this (`math.isfinite`) — only the test is missing, and `inf` is the case that
  matters most: `Field(gt=0.0)` alone would have silently accepted a positive `inf` price without
  `_finite`'s explicit guard.

### A0.12 — R6: a non-"online" Kraken pair must never be silently accepted
**File:** `tests/test_crypto_ingest_kraken.py` (new, if not already created by A0.7).
- `test_resolve_kraken_pair_rejects_a_non_online_status`: an `AssetPairs` fixture containing a pair
  whose `status` is `"cancel_only"` (or `"reduce_only"`/`"post_only"`/`"limit_only"`/`"delisted"`)
  and otherwise matches the ticker; assert `resolve_kraken_pair` raises `KrakenPairNotFoundError`.
  `mizan/crypto/ingest_kraken.py::resolve_kraken_pair` already requires `status == "online"`
  (line 50) — only the test proving the non-"online" branch is missing.

### A0.13 — R7: a ticker's candle batch must commit atomically, not partially
**Files:** `mizan/data/db.py` (edit — one real production change) and `tests/test_data_db.py`
(extend).
- Edit `upsert_candles` to wrap its per-bar `INSERT OR REPLACE` loop in an explicit transaction:
  `con.execute("BEGIN TRANSACTION")` before the loop, `con.execute("COMMIT")` after it; on any
  exception inside the loop, `con.execute("ROLLBACK")` then re-raise. This is the one-line-class fix
  PHASE_2_SPEC.md's own R7 finding named as missing — without it, a mid-batch failure (e.g. a
  malformed row reaching `upsert_candles` after passing an earlier, looser check) could leave a
  ticker's `candles` rows truncated with no record anywhere that the series is partial.
- `test_upsert_candles_is_all_or_nothing_on_a_mid_batch_failure`: construct a tuple of `CandleBar`s
  where a DB-level failure is forced partway through (e.g. patch one bar's `ts` to a value that
  violates a constraint on insert, or monkeypatch `con.execute` to raise on the Nth call); assert
  `candles` has either zero rows for that ticker or the full batch, never a partial count.

### A0.14 — S3: `INSERT OR REPLACE` actually replaces, not just avoids duplicating
**File:** `tests/test_data_db.py` (extend).
- `test_upsert_candles_overwrites_changed_values_for_the_same_key`: insert a `CandleBar`, then insert
  a second `CandleBar` sharing the same `(exchange, symbol, granularity, ts)` key but a different
  `close`/`volume`; assert a `SELECT` on that key returns the SECOND bar's values, not the first's —
  this is the half of idempotent-replay the existing A6 test (re-inserting byte-identical rows) does
  not prove.

### A0.15 — S4: the crypto and equity calendars stay structurally unreachable from each other
**File:** `tests/test_phase1_scope.py` (extend) or the new `tests/test_phase2_scope.py` (A0.10).
- `test_crypto_clock_module_never_imports_the_equity_rebalance_clock`: source-grep
  `mizan/crypto/clock.py` (and, for defence-in-depth, every other file under `mizan/crypto/`) for
  `"mizan.backtest.clock"`/`"generate_rebalance_dates"`; assert neither string appears anywhere under
  `mizan/crypto/`.

**Part A0 done when:** every test above exists and passes, the full existing suite (Phase 1 + Phase 2
production code, unmodified apart from the stated extensions and the one `upsert_candles` transaction
wrap) still passes, `docs/crypto/PHASE_2_SPEC.md` exists, `mypy --strict` and `ruff` stay clean.

## Part A (first agent, after A0) — the crypto token-classification map

### A1. Why a flat classification map, not a two-layer SIC-first-pass-plus-override design
Unlike equity's `SIC_TIER_MAP` (a generic engineering constant resolved from untyped SEC data) plus
`BusinessActivityOverrideMap` (a sparse, pluggable, hand-researched correction layer), the PRD gives
crypto's classifications directly and completely: the 14-token universe (presumed compliant — it is
the already-curated locked universe, not raw unscreened input) and the 9-token default-reject list
with each token's stated category. There is no external data source to resolve a "first pass" from
and no sparse-override need — every one of the 23 named tickers' classification is already a written,
final PRD fact. A single flat `dict[str, _TokenClassification]` constant is therefore the correct
mechanism here, not an adaptation of the two-layer equity pattern.

### A2. The classification schema
**File:** `mizan/crypto/screening.py` (new).
- `class CryptoBusinessActivityCategory(StrEnum)`: `LENDING_RIBA`, `EXCHANGE_MARGIN_FUTURES_INCOME`,
  `MAYSIR_GHARAR_MEMECOIN`, `NONE` (no disqualifying category — the 14-universe default).
- `class CryptoTokenVerdict(MizanBaseModel)`: `ticker: str`, `verdict: Verdict` (imported from
  `mizan.core.verdict` — reused as-is; only `PURE`/`NON_COMPLIANT` are ever produced here, `MIXED`
  is never reachable since there is no ratio axis for crypto), `category: CryptoBusinessActivityCategory`,
  `reason: ReasonTraceEntry` (imported from `mizan.screening.verdict`, reused as-is — its existing
  `ScreenName.BUSINESS_ACTIVITY` member already fits; no edit to that module).
- `class UnknownTokenError(RuntimeError)` — raised when `screen_token` is called for a ticker that is
  neither in `CRYPTO_UNIVERSE` nor in `DEFAULT_REJECT_LIST` (A3) — an unrecognised ticker is a caller
  bug (nothing in this build's scope screens an arbitrary, non-curated token), not a silent pass.

### A3. The classification constant
**File:** `mizan/crypto/screening.py`.
- `DEFAULT_REJECT_LIST: tuple[str, ...] = ("AAVE", "COMP", "MKR", "BNB", "OKB", "CRO", "DOGE", "SHIB", "PEPE")`
  — the PRD's own fixed list, transcribed verbatim.
- `_TOKEN_CLASSIFICATIONS: dict[str, tuple[CryptoBusinessActivityCategory, str]]` — one entry per
  ticker in `CRYPTO_UNIVERSE` (14) plus `DEFAULT_REJECT_LIST` (9) = 23 entries total:
  - Each of the 14 `CRYPTO_UNIVERSE` tickers maps to `(CryptoBusinessActivityCategory.NONE, reason)`,
    where `reason` is a short, ticker-specific sentence (e.g. for `BTC`: `"Store-of-value/payment
    network; no lending, margin/futures revenue, or maysir/gharar business model identified."`) — not
    one copy-pasted boilerplate string for all 14, so a reviewer reading the reason trace sees that
    each was actually considered, not templated.
  - `AAVE`, `COMP`, `MKR` map to `(LENDING_RIBA, "<token>: lending/borrowing protocol governance
    token; core business is interest-based (riba) lending, per the PRD's own stated reason.")`.
  - `BNB`, `OKB`, `CRO` map to `(EXCHANGE_MARGIN_FUTURES_INCOME, "<token>: exchange token; issuing
    exchange's core revenue includes margin/futures trading fees, per the PRD's own stated reason.")`.
  - `DOGE`, `SHIB`, `PEPE` map to `(MAYSIR_GHARAR_MEMECOIN, "<token>: memecoin; maysir/gharar basis,
    excluded by the configurable memecoin_exclusion_enabled parameter (currently
    {CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled.value}).")` — the only category whose rejection is
    parameter-gated, matching the PRD's own "(parameter)" annotation on exactly this one category.

### A4. `screen_token`/`screen_universe`
**File:** `mizan/crypto/screening.py`.
- `def screen_token(ticker: str, *, fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS) -> ResultEnvelope:`
  — looks up `ticker` in `_TOKEN_CLASSIFICATIONS`, raising `UnknownTokenError` if absent. If the
  category is `MAYSIR_GHARAR_MEMECOIN`, `passed = not fiqh_params.memecoin_exclusion_enabled.value`
  (read fresh on every call, never cached — same discipline as the equity screen's `fiqh_params`
  re-read, PHASE_4_SPEC.md §7 guard precedent); for every other category, `passed = category is
  CryptoBusinessActivityCategory.NONE` (never parameter-gated — `LENDING_RIBA` and
  `EXCHANGE_MARGIN_FUTURES_INCOME` are permanent business-activity facts, matching equity's Tier-0
  "always fails, never gated" precedent). Builds a `ReasonTraceEntry(screen=ScreenName.BUSINESS_ACTIVITY,
  passed=passed, threshold=None, actual_value=None, margin=None, detail=<the stored reason string>)`,
  wraps a `CryptoTokenVerdict` in a `ResultEnvelope(active_caveats=(Caveat.PENDING_SCHOLARLY_VERIFICATION,),
  payload=token_verdict.model_dump())` — deliberately NOT `Caveat.LOOK_AHEAD_BIAS` (this screen has no
  temporal/filing-date dimension at all, unlike equity's) and NOT `Caveat.SURVIVORSHIP_BIAS` (a
  universe-selection concern for the report layer, Phase 6, exactly as the equity `screen()`'s own
  docstring already states for itself).
- `def screen_universe(*, fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS) -> dict[str, ResultEnvelope]:`
  — `screen_token` for every ticker in `CRYPTO_UNIVERSE + DEFAULT_REJECT_LIST` (23 total, sorted,
  deterministic order), returned as `{ticker: envelope}`. This is the one function Phase 6's report
  layer will call; it does not touch `candles`, the DB, or the cache — pure, in-memory, and
  side-effect-free, mirroring A1's "no external data source" rationale.

### A5. Part-A smoke tests
**File:** `tests/test_crypto_screening.py` (new).
- `screen_token` happy path for one `CRYPTO_UNIVERSE` member (`BTC`): `verdict == Verdict.PURE`,
  `category == NONE`.
- `screen_token` happy path for one of each reject category (`AAVE`, `BNB`, `DOGE` with the default
  `memecoin_exclusion_enabled=True`): all three `verdict == Verdict.NON_COMPLIANT`.
- `screen_token("NOTATOKEN")` raises `UnknownTokenError`.
- `ResultEnvelope.active_caveats == (Caveat.PENDING_SCHOLARLY_VERIFICATION,)` for any one result.

**Part A done when:** the module imports, `mypy --strict`/`ruff` pass, the Part-A smoke tests pass.

## Part B (second agent)
Depends on Part A0's and Part A's committed modules.

### B1. The memecoin parameter actually gates, proven both ways
**File:** `tests/test_crypto_screening.py` (extend).
- `test_memecoin_exclusion_can_be_turned_off_via_the_register_parameter`: build a `CryptoFiqhParams`
  copy with `memecoin_exclusion_enabled.value = False`; assert `screen_token("DOGE", fiqh_params=that_copy).verdict
  == Verdict.PURE` while the module-level default (`memecoin_exclusion_enabled.value is True`) still
  rejects `DOGE` — proves the gate is live, not merely documented, in both directions.
- `test_lending_and_exchange_categories_are_never_parameter_gated`: constructing a `CryptoFiqhParams`
  copy with every boolean flipped to its most permissive value still rejects `AAVE`/`COMP`/`MKR` and
  `BNB`/`OKB`/`CRO` — there is no flag anywhere in `CryptoFiqhParams` that can flip these, matching
  equity's Tier-0 "always fails, not gated by any fiqh_params toggle" precedent exactly.

### B2. Every one of the 14 universe tokens has its own non-templated reason
**File:** `tests/test_crypto_screening.py` (extend).
- `test_every_universe_token_has_a_distinct_written_reason`: `screen_universe()`'s 14 `CRYPTO_UNIVERSE`
  entries' `reason.detail` strings are pairwise distinct (`len(set(...)) == 14`) — a literal,
  mechanical proof against the single most likely shortcut failure (one copy-pasted "no issues found"
  string for all 14, which would technically satisfy AC 4's "a written reason for every one of the 14
  tokens" without actually having considered each one).

### B3. Full-universe-plus-reject-list integration test
**File:** `tests/test_crypto_screening.py` (extend).
- `test_screen_universe_covers_all_23_named_tokens_with_the_right_verdicts`: `screen_universe()`
  returns exactly 23 keys (`CRYPTO_UNIVERSE`'s 14 plus `DEFAULT_REJECT_LIST`'s 9, no fewer, no more,
  no duplicates); every `CRYPTO_UNIVERSE` member's verdict is `PURE`; every `DEFAULT_REJECT_LIST`
  member's verdict is `NON_COMPLIANT` under the default (unflipped) register.
- `test_boot_check_still_passes_after_a_full_screen_universe_run`: call
  `mizan.config.boot_check.check_all()` after a `screen_universe()` call in the same test (defensive —
  screening touches no `Invariants`/`FiqhParams` state today).

### B4. Documentation
- `docs/crypto/ARCHITECTURE.md` (edit, additive section): one new paragraph describing the flat
  23-entry classification map, the memecoin-only parameter gate, and why this differs from equity's
  two-layer SIC-plus-override design (A1's rationale, cross-referenced).
- `docs/crypto/PHASE_3_SPEC.md`: commit this spec as the governing document, matching the Phase 1/
  Phase 2 precedent (and closing A0.9's gap pattern before it can recur for Phase 3 itself).
- `README.md`: one added sentence noting the 14-token universe and the 9-token default-reject list
  now each carry a documented per-token verdict, not yet wired to a CLI verb (Phase 6).

### B5. No forbidden code built (continuity of PHASE_1_SPEC.md §A6/B6, PHASE_2_SPEC.md §B7)
- Extend the scope-guard test (A0.10) to also scan `mizan/crypto/screening.py` for the same forbidden
  fragments and confirm it makes no network/DB call (source-grep: no `httpx`, no `duckdb`, no
  `socket` import in this file).

**Part B done when:** all Part-A0 + Part-A + Part-B tests pass, `mypy --strict`/`ruff` clean,
`mizan-boot-check` still exits 0, `screen_universe()` returns a verdict for all 23 named tokens with
the PRD's stated reject categories, and the stated `docs/` files are updated/committed.

## Acceptance-criteria mapping (Phase 3)
| AC | Satisfied by | Concrete check |
|----|--------------|----------------|
| 4 — per-token verdict with written reason for all 14 tokens; default-reject list each carries its stated reason | A2–A4, B1–B3 | `tests/test_crypto_screening.py::test_screen_universe_covers_all_23_named_tokens_with_the_right_verdicts` |
| R1, R2, R3, R4, S1 (Phase 1 carry-forward) | A0.1–A0.5 | See Part A0. |
| Phase 2's own §A6/B4/B5/B6/B7 test/doc deliverables (never implemented) | A0.6–A0.10 | See Part A0. |
| R5, R6, R7, S3, S4 (Phase 2's own Implications/Red-team carry-forward) | A0.11–A0.15 | See Part A0. |
| 1, 2, 3, 5, 6, 7, 8 (doc), 9, 10, 11, 12, 13, 14, 15 (doc) | Phases 1, 2, 4, 5, 6 | Not in Phase 3 scope. |

## Documentation sources
No new external research was required for this phase — AC 4's classification categories and the
default-reject list are given verbatim by the locked PRD (`runs/.../baby-prd.md`'s own "Original
request" section); this phase's only technical-source dependency (DuckDB transaction semantics for
A0.13) is already covered by `docs/modernization_log.md`'s existing DuckDB entries.

## Out of scope for this phase
- The baseline backtest, fees/slippage, and rebalance-cadence wiring (Phase 4).
- Any CLI verb for crypto screening or the single end-to-end pipeline command (Phase 6);
  `screen_universe` is called directly by tests in this phase, not by `mizan/cli/main.py`.
- Re-deriving or contesting any of the PRD's own stated classification reasons (cited, not contested,
  matching the project's standing fiqh-basis rule).
- Screening any token outside the 23 named ones (the locked 14-universe plus the 9-token reject
  list) — `UnknownTokenError` is the deliberate boundary, not a gap to be filled with a general
  classifier.
- Normalizing screen results into any typed report-facing shape (Phase 6's job).
- Deleting or modifying parked equity screening modules (`business_activity.py`, `financial_ratios.py`,
  `verdict.py`) or their tests.

## Spec assumptions
Gaps found while writing this spec were resolved as follows (nobody was asked):
- The 14 `CRYPTO_UNIVERSE` tokens are treated as pre-screened by construction (the PRD names them as
  the fixed universe without listing a rejection reason for any of them) — Phase 3 still requires a
  written per-token reason for each (AC 4's own wording: "for every one of the 14 tokens"), so A3
  requires 14 distinct, ticker-specific sentences rather than a single shared "already curated"
  boilerplate string.
- `UnknownTokenError` rather than a permissive default-pass is chosen for any ticker outside the 23
  named ones, because nothing in the locked PRD describes how an arbitrary, non-curated token should
  be classified, and silently passing an unrecognised ticker would be a worse failure mode than a
  loud, explicit error a caller must handle.
- `screen_token`/`screen_universe` take no `cache_dir`/`con` parameters (unlike equity's `screen()`):
  the classification map is a static, hand-authored constant with no external data dependency, so
  there is nothing to read from cache or DuckDB at this phase — a later phase wiring the full
  fetch→screen→backtest pipeline passes `screen_universe()`'s output alongside `candles` query
  results, not through them.
- Part A0's size in this spec (15 sub-items) reflects an actual, verified gap, not spec inflation:
  `git diff --stat` across both Phase 2 executor turns touches zero files under `tests/`, and the
  full suite's pass count (437) is identical to the count recorded at the end of the Phase 1 review —
  mechanical confirmation that no test was added anywhere in Phase 2.

## Implications
Second-order consequences found by review of this spec. This section only adds to the spec; the
locked PRD is unchanged.

### Additional acceptance criteria
S5. A test asserts that flipping `CRYPTO_FIQH_PARAMS.memecoin_exclusion_enabled` affects only the
three memecoin tickers' verdicts and no other ticker's verdict changes as a side effect —
`screen_universe()` called once with the default register and once with the flipped register should
differ in exactly `{"DOGE", "SHIB", "PEPE"}` and nowhere else. _(correctness: B1 proves the gate
fires for `DOGE` in isolation; it does not prove the gate is scoped correctly across the whole
23-entry map, which matters once a later phase lets an operator change this one parameter and expects
every other verdict to stay stable.)_

## Red-team findings
Weaknesses found by an adversarial review of this spec before it is built. This section only adds to
the spec; the locked PRD is unchanged.

### Additional acceptance criteria
R8. A test asserts `screen_token`/`screen_universe` never raise or warn when
`CRYPTO_FIQH_PARAMS` itself is passed with a register whose `memecoin_exclusion_enabled.register_id`
has been tampered with (e.g. via a malformed `model_copy`) — specifically, that `screen_token` reads
`.value` only and never branches on `.register_id`, so a future refactor of the register's internal
IDs cannot silently change screening behaviour. _(low, maintenance: A4 specifies reading
`fiqh_params.memecoin_exclusion_enabled.value`; nothing currently stops a future edit from
accidentally keying off `register_id` instead, which would silently break if the register's ID
assignment ever changed for unrelated reasons.)_
