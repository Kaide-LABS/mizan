# BUILD_COMPLETE.md — Mizan V1

Written immediately after Phase 7's comprehension pass (`9d31877`), closing out the seven-phase
automated build. **Mizan V1 is code-complete: all seven phases specified in `ULTIMATE_PRD.md` §6 are
implemented, reviewed, approved, and comprehension-verified.** This document is the final
handoff — written per the FINAL PHASE convention established in `PHASE_6_SPEC.md`/`PHASE_7_SPEC.md`
and `.claude/agents/loopr-step12.md`'s own customization for Mizan — in place of a `PHASE_8_SPEC.md`,
because there is no Phase 8.

---

## 1. Confirmation: all seven phases built and approved

Looked up directly from `git log`, not reconstructed from memory. Each phase's full lifecycle
(technical blueprint → implementation → review approval → comprehension pass) is a real, separate
commit on `main`, in order:

| # | Phase | Implementation commit | Review-approval commit |
|---|---|---|---|
| 1 | Foundation & Config | `8ed6de2d03d9017442627be14f4f5a06a991bba7` | `942d87a48e4dabd42114b0447400acd1777bcaf7` |
| 2 | Ingestion & Raw Cache (EDGAR + Tiingo) | `bb947c5842f0b4f42e3bcf682399f46e487c73ab` | `e73e9ccc2abf611c36e3ad9f8b70588822a41b9e` |
| 3 | Normalization & DuckDB Store | `8e9980995c764476f0327ef8954b6f83d467f3ef` | `e9a62c34883f040f330b473025c33994da69f488` |
| 4 | Screening Engine | `0060cfd439a20310cf1ed541d614488f3f607074` | `d70b29d2f0b2bcf7c37166899828ef50f645ee74` |
| 5 | Backtest Engine & Compliance-Flip State Machine | `3f9ccc6f5cdf79f057623369209439267429ba3a` | `9e989ebaedac40e2107ee2c0167d730eb6c437dd` |
| 6 | Purification Engine (side-ledger) | `9750a1837310bc28bbb34cb56aaf1c28c030551e` | `6edb9b59ffb8cdc2ee3c6fc330a1e7232b3609bd` |
| 7 | Reporting (static HTML + plots) — **final phase** | `804b333fbdb30ed37a23b1f5084ec73497d50460` | `47d33987c85209a61061e090e6ef34f83cf56f7d` |

Each phase also has its own technical-blueprint commit (`docs: Phase N technical blueprint (mizan)`)
preceding implementation, and its own comprehension-pass commit (`docs: Phase N comprehension pass
(mizan)`) following approval — all present on `main`, all confirmed via `git log --oneline`. Phase 7's
comprehension pass, `9d31877176a706aa4fafd6feca59ed5427960a4f`, is the current `HEAD` this document is
being written on top of.

**Final acceptance-suite results — run fresh, this pass, not reused from any prior commit message:**

```
.venv/Scripts/python -m pytest tests/ -q
406 passed in 39.90s
```

406 of 406 tests pass, zero failures, zero errors. This matches the count Phase 7's own comprehension
pass (`9d31877`) reported, but it was not taken on faith — it was re-run independently as part of
writing this document, against the repository exactly as it sits at `HEAD`.

---

## 2. Deployment target

**N/A.** Mizan is a local batch/CLI tool with no server, no hosted deployment, and no URL. There is
nothing to deploy. This was already established in Phase 6's and Phase 7's own spec reasoning
(`PHASE_6_SPEC.md`, `PHASE_7_SPEC.md` — both cite `MASTER_PRD.md` §9's single-user, no-hosting-surface
posture) and is restated here plainly rather than filled in with a placeholder URL.

---

## 3. Citation-gate summary

**Not applicable.** No phase spec across the whole seven-phase build ever inserted a §0.5
citation-verification gate. The reasoning, established starting at `PHASE_6_SPEC.md` and carried
through `PHASE_7_SPEC.md` and `.claude/agents/loopr-step12.md`'s own project-specific customization:
Mizan's arXiv citations (`ULTIMATE_PRD.md` §3, §8) are background corroboration for design choices
already independently justified by primary sources — AAOIFI Shari'ah Standard No. 21's public
methodology and the SEC EDGAR / Tiingo API documentation themselves, both of which carry their own
citation discipline via `docs/modernization_log.md`. No phase spec's implementation copies a method,
formula, or numeric result from any arXiv paper — the load-bearing technical claims trace to AAOIFI
and to the two data-source APIs, already re-verified per `PHASE_1_SPEC.md` and the modernization log.
Re-verifying abstract-level corroboration at every phase boundary would have added process weight with
no correctness payoff, so no phase ever added the gate.

---

## 4. Handoff instructions (in place of a demo recording)

Mizan has no live demo to record — it is a personal batch CLI, not a hosted app. In its place, here
are the exact local commands that run the full pipeline end to end, and where the report lands on
disk.

### 4a. What CAN be run right now — no real network access, no real API key

There is no real ~100-ticker universe and no real Tiingo API key configured (`.env.example` only
documents the `TIINGO_API_TOKEN` placeholder; no real key has ever been supplied to this build). What
*can* be verified right now, with zero network access, is the full `screen → backtest → report` half
of the pipeline against the synthetic fixture universe every one of the 406 tests already exercises
(`tests/fixtures/synthetic_universe.py`) — the same thing Phase 7's own comprehension pass did to
independently confirm the reporter's output. `mizan ingest` itself talks to real EDGAR/Tiingo
endpoints, so the synthetic-fixture path seeds the cache and DuckDB store directly via the test
suite's own fixture-writing helpers instead of running `ingest` against invented tickers that don't
exist upstream:

```bash
# from the repo root, inside .venv
.venv/Scripts/python - <<'PY'
from pathlib import Path
from mizan.data import db
from tests.fixtures import synthetic_universe as fx

cache_dir = Path("scratch_cache")
db_path = Path("scratch.duckdb")
tickers = (fx.ZZMIXED_RATIODRIFT01,)   # any subset of fx.ALL_SYNTHETIC_TICKERS

fx.write_universe_cache(cache_dir, tickers)
con = db.connect(db_path)
for t in tickers:
    fx.load_into_duckdb(con, t)
con.close()
PY

# now run the real CLI verbs against that seeded cache/DB — no network access needed:
.venv/Scripts/python -m mizan.cli.main screen \
  --ticker ZZMIXED_RATIODRIFT01 --as-of-date 2026-06-30 \
  --db-path scratch.duckdb --cache-dir scratch_cache

.venv/Scripts/python -m mizan.cli.main backtest \
  --ticker ZZMIXED_RATIODRIFT01 \
  --start-date 2026-01-01 --end-date 2026-07-01 --initial-cash 1000000.0 \
  --db-path scratch.duckdb --cache-dir scratch_cache

.venv/Scripts/python -m mizan.cli.main report \
  --ticker ZZMIXED_RATIODRIFT01 \
  --start-date 2026-01-01 --end-date 2026-07-01 --initial-cash 1000000.0 \
  --db-path scratch.duckdb --cache-dir scratch_cache \
  --output-path scratch_report.html
```

`mizan report`'s generated HTML lands wherever `--output-path` names it — in the example above,
`scratch_report.html` in the current working directory, a single self-contained file (no sibling
`.png`/`assets/` files, confirmed empirically by Phase 7's own comprehension pass: exactly one file on
disk afterward). Opening it in any browser shows, in fixed order: the active caveats banner, the full
eleven-row fiqh judgment-call register, the gross and net-of-purification return figures side by side,
a per-ticker compliance/outcome table, the full purification-ledger detail, and two embedded
base64 PNG charts.

### 4b. What requires the operator's own future setup before results are trustworthy

The commands above prove the pipeline runs correctly — they do **not** prove anything about real
markets or real companies, because they never touch either. Two things, entirely outside this
automated build's scope, must exist before a real run means anything:

1. **A real Tiingo API key**, placed in a local `.env` following `.env.example`'s
   `TIINGO_API_TOKEN` placeholder. `mizan ingest` is already built, tested, and rate-limited correctly
   for both EDGAR (≥0.12s/≥600s spacing) and Tiingo (50/hour–1,000/day budget, 500-ticker/month cap) —
   nothing in the ingestion code needs to change, only a real credential.
2. **Genuine, hand-researched, hand-cited business-activity data for real tickers** — the ~100-company
   curated universe `MASTER_PRD.md` §4 and §11 item 1 call for, and its `BusinessActivityOverrideMap`
   (`mizan/screening/business_activity.py`, built, tested, ships empty, keyed by CIK, requires a
   non-empty `rationale` string per entry). Without it, `mizan screen`/`report` against real tickers
   falls back to the generic SIC-code first-pass tier classifier alone, which is a real, working
   mechanism but not a verified one for any individual company.

Once both exist, the real end-to-end pipeline is:

```bash
mizan ingest --ticker AAPL --ticker MSFT ... --start-date 2015-01-01 --end-date 2026-01-01 \
  --cache-dir cache/ --tiingo-token "$TIINGO_API_TOKEN"

mizan normalize --ticker AAPL --ticker MSFT ... --start-date 2015-01-01 --end-date 2026-01-01 \
  --cache-dir cache/ --db-path mizan.duckdb

mizan screen --ticker AAPL --ticker MSFT ... --as-of-date 2026-01-01 \
  --db-path mizan.duckdb --cache-dir cache/ --overrides-path real_overrides.json

mizan backtest --ticker AAPL --ticker MSFT ... \
  --start-date 2015-01-01 --end-date 2026-01-01 --initial-cash 1000000.0 \
  --db-path mizan.duckdb --cache-dir cache/ --overrides-path real_overrides.json

mizan report --ticker AAPL --ticker MSFT ... \
  --start-date 2015-01-01 --end-date 2026-01-01 --initial-cash 1000000.0 \
  --db-path mizan.duckdb --cache-dir cache/ --overrides-path real_overrides.json \
  --output-path real_report.html
```

`real_report.html` lands wherever `--output-path` names, exactly as in §4a — one self-contained file,
double-clickable in any browser, no server required.

---

## 5. What's genuinely done vs. what's still open

**The single most important fact about V1, stated plainly, up front — not buried at the bottom:**
Mizan is a working, fully-tested, seven-phase PIPELINE — 406 passing tests, `mypy --strict` and `ruff`
both clean — but it has **never screened or backtested a single real company**. Every test, every
fixture, every report generated by any phase of this build, including this final one, was built from
a small set of invented, obviously-fake ticker symbols (`ZZPURE01`, `ZZFLIP01`,
`ZZMIXED_RATIODRIFT01`, and a dozen or so others, CIK prefix `999...`, never real issuers). The
real ~100-ticker curated universe and its hand-verified business-activity map were **deliberately
never built** — this was scoped from Phase 4 onward as the project owner's own future research task,
explicitly outside what an automated phase build does, not a code gap or an oversight. A report
generated against real tickers today would render — fully, correctly, with every caveat and the
complete fiqh register — but it would be built on a generic SIC-code first-pass classification, not a
verified one.

**Genuinely done, verified by 406 passing tests plus this pass's own fresh re-run:**

- The seven-phase pipeline itself: ingest → normalize → screen → backtest → report, all four CLI verbs
  wired and working (`mizan --help` lists all four).
- The three-state (`PURE`/`MIXED`/`NON_COMPLIANT`) screening engine with full reason traces.
- The quarterly-rebalance backtest engine with the flip → one-quarter grace period → forced-divestment
  state machine, no un-flip edge.
- The purification side-ledger — Fork A (dividend purification, date-pinned ratio re-derivation) and
  Fork C (forced-divestment price-appreciation attribution), gated by `purify_capital_gains`.
- The static HTML report — caveats-first ordering, the full eleven-row fiqh register, distinct
  gross/net-of-purification figures, per-ticker and per-entry detail tables, two embedded charts, one
  portable file.
- `mypy --strict mizan tests` clean (66 source files, inside `.venv`); `ruff check mizan tests` clean;
  zero unexplained `noqa` suppressions.

**Still genuinely open — the complete list carried forward from `COMPREHENSION.md` §6, none dropped:**

1. **The real ~100-ticker curated universe and its hand-verified business-activity override map do not
   exist anywhere in this repository.** The headline gap, restated here one final time.
2. **The mypy/numpy-outside-`.venv` gap** — the specific PEP 695 stub-parse crash the `numpy.*` mypy
   override targets is genuinely, empirically fixed (re-verified independently, outside `.venv`, this
   build). What remains is a narrower, pre-existing, orthogonal gap: `mypy --strict` still won't cleanly
   pass on a machine that simply doesn't have `duckdb`/`matplotlib` installed at all — covered by the
   standing "build and verify inside `.venv`" instruction, not a new defect.
3. **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** remain open by design;
   no phase, including Phase 7, adjudicates them.
4. **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — unchanged since Phase
   1, and nothing in this automated build was ever meant to change that status.
5. **`PHASE_5_SPEC.md`'s own missing §6e section** — referenced nine times, never written. Cosmetic; no
   later phase's spec has an equivalent gap, and nothing depends on it, but it is not fixed.
6. **The frozen/workable portfolio partition adds real complexity to `rebalance()`** that a future
   maintainer must understand correctly to avoid reintroducing the exact grace-period bug it exists to
   prevent.
7. **The grace period's value (one rebalance period) carries no AAOIFI primary-source citation** —
   `[UNVERIFIED / INFERENCE]` in the fiqh register, unchanged.
8. **The Phase 2 AC15 noqa-enumeration mismatch** — a small, still-present spec/code drift, unaffected
   by any later phase.
9. **`LongTermInvestments` remains `[UNVERIFIED]`, and `SIC_TIER_MAP` has no dedicated gambling/casino
   Tier-0 SIC code** — both unaffected by any phase since Phase 4.
10. **The corporate-action anomaly scan is deliberately conservative and will produce false
    positives** — an accepted tradeoff, not a defect, unchanged since Phase 2.
11. **The Fork A/Fork C `purify_capital_gains` gating decision rests on a reasoned textual inference
    from `MASTER_PRD.md` §8, not a verbatim instruction** — a future scholarly-verification pass could
    reasonably reopen it.
12. **`mizan/purification/` deviates from `MASTER_PRD.md` §9.4's and `PHASE_5_SPEC.md`'s own diagrammed
    module path** (a two-file top-level package instead of a single `backtest/purification.py`) — real,
    cited, reasoned, still not corrected in `ULTIMATE_PRD.md` itself.
13. **The gross/net-of-purification return figures are plain point-to-point returns** — not annualized,
    risk-adjusted, or time-weighted. An honest, deliberate Phase 6 scope limit, now visible to a report
    reader for the first time via Phase 7's `id="returns"` section.
14. **The DuckDB file is a local, derived, regenerable artifact with no versioned migration path** —
    unchanged; Phase 7 added no new table, column, or index.
15. **No real report has ever been generated against the real ~100-ticker universe** — the final-phase
    restatement of item 1: every report any phase's build or review generated, including this one's own
    verification runs, was built from invented fixture tickers.
16. **Report file size scales with the number and resolution of embedded plots** (the base64-inline
    tradeoff, §4 above) — accepted at V1's own two-plot scope, worth attention if a future,
    out-of-V1-scope enhancement adds more charts.
17. **No CLI flag suppresses any report section or plot** — a deliberate, honesty-preserving design
    choice (`PHASE_7_SPEC.md` §9), not a missing feature.

**What a human (the project owner) should actually do next**, compiled here because this is the last
phase, not generic advice:

1. **Do the real ~100-ticker research** — pick the real universe, hand-verify each company's
   business-activity classification, and build a real `BusinessActivityOverrideMap` rather than relying
   on the generic SIC first-pass alone for anything genuinely ambiguous.
2. **Buy a real Tiingo API key and run a real backfill** — `mizan ingest` needs no new code, only real
   credentials and a real run against the real universe from step 1.
3. **Run `mizan report` end to end against that real data**, once steps 1–2 are done, and actually read
   the resulting page — its own honesty surface (caveats banner, fiqh register) is designed to make any
   remaining limitation visible at that point.
4. **Get a qualified muamalat scholar to actually rule on the eleven pending fiqh register entries**,
   per `MASTER_PRD.md` §10's own standing rule — this sandbox learns the mechanics; it does not rule on
   them, and nothing in this automated build was ever meant to change that.
5. **Consider fixing `PHASE_5_SPEC.md`'s own dangling "§6e" cross-references and `ULTIMATE_PRD.md` §5
   check 5's stale `mizan/backtest/purification.py` grep path** — small, low-risk documentation
   cleanups, non-blocking.
6. **Treat the shipped `EqualWeightStrategy` as exactly what it is** — a reference implementation and
   testing vehicle, not a real research strategy — before trusting any actual investment decision on
   top of this substrate; `mizan/backtest/strategy.py`'s `Strategy` `Protocol` is the extension point.

---

## 6. MASTER_PRD.md §11 — V1 Definition of Done, checked off item by item

| # | DoD item | Status | Delivered by (phase / commit) |
|---|---|---|---|
| 1 | Ingestion pulls and caches EDGAR fundamentals + EOD total-return price data (incl. dividends) for the ~100-ticker universe, **replayably** | **Done — mechanism verified, real universe not yet run** | Phase 2 (`bb947c5` / `e73e9cc`) shipped `mizan/data/ingest_edgar.py`, `ingest_tiingo.py`, and `raw_cache.py`'s replayable cache-hit/atomic-write discipline, tested via 83 tests including cache-idempotency and rate-limiter timing. Replayability against real tickers is proven mechanically (same 83 tests); the real ~100-ticker backfill itself was never run (§5 above) |
| 2 | Screening engine computes business-activity + configurable financial-ratio screens from public AAOIFI methodology, emits **three-state** verdicts with **every fiqh judgment call exposed as a flagged parameter** and a reason trace, pass/fail inspectable | **Done** | Phase 4 (`0060cfd` / `d70b29d`) shipped `mizan/screening/business_activity.py`, `financial_ratios.py`, and `verdict.py`'s `screen()` entry point — `Verdict.PURE`/`MIXED`/`NON_COMPLIANT` with a full reason trace, every disputed threshold read from Phase 1's `FIQH_PARAMS` register. 81 tests, all passing |
| 3 | Backtest engine runs a long-only quarterly-rebalance strategy over the screened universe with the **compliance-flip → forced-divestment → purification** state machine working end to end | **Done** | Phase 5 (`3f9ccc6` / `9e989eb`) shipped the flip → one-quarter grace → divest state machine (`mizan/backtest/compliance_state.py`, `clock.py`) and the frozen/workable portfolio partition; Phase 6 (`9750a18` / `6edb9b5`) closed the loop with the purification side-ledger (`mizan/purification/ledger.py`, `attribution.py`) consuming a completed `BacktestResult`. Together, 106 tests (81 + 25), all passing, prove the full flip→divest→purify chain end to end |
| 4 | **Every honesty caveat** (look-ahead, survivorship, pending-scholarly-verification) is stamped on **every result output**, structurally (via the result object), not buried in a README | **Done** | Phase 1 (`8ed6de2` / `942d87a`) established `Caveat`/`ResultEnvelope` as the mandatory warning-label wrapper. Phase 7 (`804b333` / `47d3398`) makes this structurally unavoidable at the final output layer: `render_report`'s `active_caveats` parameter is required and keyword-only with no default — omitting it is a `TypeError` at the call site and a static `mypy --strict` error, not merely a documented convention. Confirmed empirically: the real report this build generated renders the caveats banner before any number, verbatim, unescaped |
| 5 | Results come out as a **generated static report** (HTML + plots) | **Done** | Phase 7 (`804b333` / `47d3398`) shipped `mizan/reporting/report.py` and `plots.py` — one self-contained HTML file per run, two embedded base64 PNG charts (equity curve, purification-by-ticker bar chart), no server, no external files. Confirmed empirically: a real generated report was 64,341 bytes, exactly one file on disk, both plot images inline |

All 5 items: **done**, each cited against the actual phase and commit that delivered it, not merely
asserted.

---

## Closing statement

Mizan V1 is code-complete. The pipeline works, is genuinely tested, and is honest about its own
limits by structural design — the caveats banner and fiqh register cannot be rendered around. What it
is not, yet, is a tool that has ever evaluated a real company. That gap is entirely the project
owner's own next step (§5 above), not an artifact of anything left unbuilt in these seven phases.
