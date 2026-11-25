# Phase 6 — Crypto HTML Report and the Single End-to-End Pipeline Command

## Goal
Build the one remaining PRD surface nothing yet exposes end-to-end (AC 1, 7, 14, 15): a
self-contained crypto HTML report (fiqh-register citations, per-token verdicts with reasons, a
loud survivorship-bias warning, and the exchange-custody/freeze-risk caveat) and a single CLI verb
— `mizan crypto-pipeline` — that fetches the 14 tokens' candles, screens the full 23-token map,
runs the Phase 4 baseline backtest, and writes that report, in one documented command. Confirm
equity's CLI verbs and modules remain unaffected and still importable (AC 14) and that the
two-speed roadmap documentation is unchanged by this phase (AC 15, doc-only — nothing here builds
HFT, adapter, or live-trading code).

## Scope
In scope: a new `Caveat.CUSTODY_FREEZE_RISK` member (`mizan/core/caveats.py`, extend); the one
forced downstream edit that member's addition requires (`mizan/reporting/report.py`'s
`CAVEAT_DESCRIPTIONS` dict, extend); a new `mizan/crypto/report.py` (render functions + the
caveat-resolution helper); a new `render_crypto_equity_curve_plot` in `mizan/reporting/plots.py`
(extend, reuses the existing `Agg`-backend setup); a new `mizan/cli/crypto.py` registering the
`crypto-pipeline` verb; one added import + one added line in `mizan/cli/main.py`; their tests;
`docs/crypto/ARCHITECTURE.md` (additive), `docs/crypto/PHASE_6_SPEC.md` (commit this spec),
`README.md` (one sentence); the scope-guard extension. Out of scope: everything in "Out of scope
for this phase" below.

Every new/edited module: `from __future__ import annotations`, full type annotations
(`mypy --strict` clean), ruff-clean, module docstring citing `docs/crypto/PHASE_6_SPEC.md §…`. No
new runtime dependency — `httpx`, `duckdb`, and `matplotlib` are already pinned and reused as-is.

## Part A (first agent) — the caveat extension and the report's render primitives

### A1. Why a new `Caveat` member, not a crypto-local enum
`mizan/core/caveats.py`'s `Caveat` `StrEnum` (Phase 1) is the one honesty surface every
`ResultEnvelope` in this repo — equity and crypto alike — is built on
(`mizan/crypto/backtest.py:244-247` already returns
`ResultEnvelope(active_caveats=(Caveat.SURVIVORSHIP_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION), …)`
using this exact shared enum, not a crypto-specific one). The exchange-custody/freeze-risk caveat
the baby PRD names (`CryptoFiqhParams.custody_model`'s own `primary_source_gap`,
`mizan/crypto/fiqh_register.py:36-39`: "FTX-type failure and freeze risk are caveated-not-modelled;
self-custody is the long-term target") is exactly the same *kind* of fact `Caveat` already exists
to carry — a structural, always-stamped honesty disclosure — so it is a new member of the existing
enum, not a second, parallel crypto-only caveat type that would fragment the "no code path renders
a number without its caveat set" guarantee `mizan/core/caveats.py:43-50`'s own docstring states
across two incompatible vocabularies.

### A2. The new member
**File:** `mizan/core/caveats.py` (edit, additive).
```python
class Caveat(StrEnum):
    ...
    CUSTODY_FREEZE_RISK
        Exchange custody is accepted as qabd hukmi (constructive possession) for crypto V1
        (CryptoFiqhParams.custody_model, register #3). FTX-type exchange failure and asset-freeze
        risk are NOT modelled anywhere in this backtest; self-custody is the long-term target.
        Applies whenever a run's CryptoFiqhParams.custody_model is EXCHANGE_QABD_HUKMI.
    """

    LOOK_AHEAD_BIAS = "look_ahead_bias"
    SURVIVORSHIP_BIAS = "survivorship_bias"
    PENDING_SCHOLARLY_VERIFICATION = "pending_scholarly_verification"
    CUSTODY_FREEZE_RISK = "custody_freeze_risk"
```
Adding a fourth member to an enum two prior phases (4 and 5, via `ResultEnvelope`) already
pattern-match on by value, not by exhaustive `match`, is additive and backward-compatible: neither
`mizan/crypto/backtest.py` nor `mizan/signal/contract.py` enumerates `Caveat`'s members anywhere,
so this edit requires no change to either (confirmed by reading both files in full before writing
this spec).

### A3. The forced downstream edit — `mizan/reporting/report.py`'s completeness assert
`mizan/reporting/report.py:99-103` already runs, at import time:
```python
assert set(CAVEAT_DESCRIPTIONS) == set(Caveat), (...)
```
This means A2's edit, landed alone, breaks `import mizan.reporting.report` — and therefore every
equity CLI verb (`ingest`/`screen`/`backtest`/`report` all import it transitively) — with an
`AssertionError` at interpreter start. This is NOT scope creep into a "REUSE AS-IS" equity module
(baby PRD §"Reuse as-is: …HTML reporting"): it is the one-line consequence the existing
completeness guard itself mandates the instant a shared enum it closes over grows, and the guard
exists precisely so a new `Caveat` member can never silently go undescribed. Add exactly one entry:
```python
CAVEAT_DESCRIPTIONS: dict[Caveat, str] = {
    ...,
    Caveat.CUSTODY_FREEZE_RISK: (
        "Exchange-custody and freeze risk: crypto assets in this backtest are modelled as held "
        "in exchange custody (qabd hukmi, constructive possession), not self-custodied. "
        "Exchange failure (FTX-type) and asset-freeze risk are not modelled anywhere in this "
        "run's numbers; self-custody is this project's long-term target, not its current state."
    ),
}
```
No other line in `mizan/reporting/report.py` changes; every equity render function, test, and CLI
verb is unaffected because equity never emits `Caveat.CUSTODY_FREEZE_RISK` in any
`active_caveats` tuple it constructs (equity's own caveat set is `LOOK_AHEAD_BIAS` /
`SURVIVORSHIP_BIAS` / `PENDING_SCHOLARLY_VERIFICATION`, unchanged).

### A4. `mizan/crypto/report.py` — the crypto report's own input type and table renderers
**File:** `mizan/crypto/report.py` (new). A new, parallel module — exactly the precedent
`mizan/crypto/backtest.py:5-13` already set for Phase 4 ("a new, parallel module rather than an
extension") — because `mizan.reporting.report.ReportInput`/`render_report` are structurally
unusable for crypto: `ReportInput` requires an equity `FiqhParams` (11 fields,
`mizan/reporting/report.py:122-137` asserts exactly 11 rows) and a `BacktestResult` whose
`purification_ledger` is non-`None` (`ReportInput._purification_ledger_is_populated`,
`mizan/reporting/report.py:61-73`) — crypto's `CryptoFiqhParams` has exactly 4 fields
(`mizan/crypto/fiqh_register.py:18-52`) and `CryptoBacktestResult`
(`mizan/crypto/backtest.py:173-180`) carries no `purification_ledger` field at all (crypto
purification is near-empty per the baby PRD: no dividends, staking off). Reusing equity's
`ReportInput` would therefore either raise at construction or silently coerce crypto data into an
equity-shaped type it does not fit.
```python
class CryptoReportInput(MizanBaseModel):
    backtest_result: CryptoBacktestResult
    fiqh_params: CryptoFiqhParams = CRYPTO_FIQH_PARAMS
    token_verdicts: tuple[CryptoTokenVerdict, ...]
```
`token_verdicts` carries all 23 named tokens (the 14-token `CRYPTO_UNIVERSE` plus the 9-token
`DEFAULT_REJECT_LIST`) — the same set `mizan.crypto.screening.screen_universe()` already iterates
(`mizan/crypto/screening.py:180-185`), so AC 4's "per-token verdict with a written reason for every
one of the 14 tokens, and the default-reject list … each carries its stated reason" is rendered in
full, not only the compliant subset the backtest actually traded.

`render_crypto_fiqh_register(fiqh_params: CryptoFiqhParams) -> str` mirrors
`mizan.reporting.report.render_fiqh_register`'s own shape (`mizan/reporting/report.py:122-160`) —
sorted by `register_id`, one `<tr>` per field, asserting exactly 4 rows (not 11) — but is its own
function operating on `CryptoFiqhParams.model_fields`, not a parametrized reuse of the equity
function, since the two register types share no common field set `getattr` could walk generically
without `# type: ignore`.

`render_crypto_token_verdicts(token_verdicts: tuple[CryptoTokenVerdict, ...]) -> str` renders one
`<section id="token-verdicts">` table, one row per `CryptoTokenVerdict` (ticker, `verdict.value`,
`category.value`, `reason.detail`), sorted by ticker. Every cell passes through
`html.escape(value, quote=False)` — the exact escaping discipline
`mizan.reporting.report._escape` already established (`mizan/reporting/report.py:31-39`); this
module defines its own identical one-line `_escape` rather than importing the equity module's
private (leading-underscore) helper across a package boundary.

### A5. Part-A tests
**File:** `tests/test_caveats.py` (new — no dedicated test file for `mizan/core/caveats.py`
exists yet). `Caveat.CUSTODY_FREEZE_RISK.value == "custody_freeze_risk"`; `len(set(Caveat)) == 4`;
`import mizan.reporting.report` succeeds without raising (regression test for §A3's completeness
assert, since a future `Caveat` addition without a matching `CAVEAT_DESCRIPTIONS` entry must fail
exactly this way, not silently).

**File:** `tests/test_crypto_report.py` (new, mirrors `tests/test_reporting_report.py`'s
structure). `render_crypto_fiqh_register` on `CRYPTO_FIQH_PARAMS` produces exactly 4 `<tr>` rows
and contains the literal string `"qabd_hukmi"` or `"exchange_qabd_hukmi"` (the custody value);
`render_crypto_token_verdicts` on `screen_universe()`'s 23-ticker output produces exactly 23
`<tr>` rows, and the rendered output contains, verbatim, the reject-reason detail text for AAVE,
BNB, and DOGE (one example per category, proving real per-category reason strings reach the HTML,
not a placeholder); a ticker-verdict row's cells are `html.escape()`-d (a token whose `reason.detail`
contains `<`/`&` round-trips as `&lt;`/`&amp;` in the rendered row — constructed via a test-local
`CryptoTokenVerdict` instance, since no real classification text contains these characters).

**Part A done when:** both modules import, `mypy --strict`/`ruff` pass, every A5 test passes,
`mizan-boot-check` still exits 0.

## Part B (second agent)
Depends on Part A's committed module and the new `Caveat` member.

### B1. The backtest-summary renderer, the plot, and the caveat-resolution helper
**File:** `mizan/crypto/report.py` (continued).
```python
def render_crypto_backtest_summary(result: CryptoBacktestResult) -> str:
    ...  # strategy_label, final portfolio value, excluded_tickers, cost_params' two rates
```
One `<section id="backtest-summary">`: `result.strategy_label` (always `"baseline"`, rendered
literally so the report never implies a validated signal drove this run — AC 5's own "explicitly
labelled a baseline" requirement, carried through to the report); the final
`daily_snapshots[-1].portfolio_value` (or a literal "no trading days" sentence if
`daily_snapshots` is empty, same empty-input discipline `mizan.reporting.plots`'s own functions
already use, `mizan/reporting/plots.py:53-66`); `excluded_tickers` as a plain comma-joined list;
`cost_params.taker_fee_rate`/`slippage_rate` each rendered to 4 decimal places (AC 6's "applies a
taker fee … and … slippage" made visible in the one artefact a grant judge reads).

```python
def resolve_crypto_report_caveats(
    backtest_caveats: tuple[Caveat, ...], fiqh_params: CryptoFiqhParams
) -> tuple[Caveat, ...]:
    if fiqh_params.custody_model.value is CustodyModel.EXCHANGE_QABD_HUKMI:
        return (*backtest_caveats, Caveat.CUSTODY_FREEZE_RISK)
    return backtest_caveats
```
`run_crypto_backtest`'s own returned `envelope.active_caveats` is always exactly
`(SURVIVORSHIP_BIAS, PENDING_SCHOLARLY_VERIFICATION)` (`mizan/crypto/backtest.py:244-247`) — it has
no opinion on custody, because custody is a property of the fiqh register in force for the run,
not of the backtest mechanics. This function is the one place that composes the two: the
backtest's own caveats, plus the custody caveat **only when** the register in force actually
models exchange custody (`CustodyModel.EXCHANGE_QABD_HUKMI`, the V1 default,
`mizan/crypto/fiqh_register.py:32-40`) — a hand-constructed `CryptoFiqhParams(custody_model=
CustodyModel.SELF_CUSTODY, ...)` passed to a future run must not carry a caveat about a risk that
register no longer accepts. A pure function, no I/O, independent of `render_crypto_report` itself
so it is unit-testable without constructing a full report.

```python
def render_crypto_report(
    data: CryptoReportInput, *, active_caveats: tuple[Caveat, ...]
) -> str:
    ...
```
Mirrors `mizan.reporting.report.render_report`'s own keyword-only, no-default `active_caveats`
contract exactly (`mizan/reporting/report.py:269-279`) — `render_crypto_report(data)` raises
`TypeError` at the call site, before this function's body runs, and `mypy --strict` flags any
call site missing the keyword as a static error, matching `ULTIMATE_PRD.md §2.2`'s "no code path
renders a number without its caveat set" for the crypto path too. Internally calls the **reused,
unmodified** `mizan.reporting.report.render_caveats_banner(active_caveats)` — the one render
function that is genuinely domain-agnostic, since it only ever looks up `Caveat` members in the
now-complete (§A3) `CAVEAT_DESCRIPTIONS` dict and never touches an equity-shaped field — then
`render_crypto_fiqh_register`, `render_crypto_token_verdicts`, `render_crypto_backtest_summary`
(§A4, §B1), and one embedded plot section (§B2), concatenated in that fixed order (caveats first,
before any numeric figure — the same ordering discipline `render_report`'s own docstring states,
`mizan/reporting/report.py:281-282`). Returns one complete, self-contained
`<!DOCTYPE html>…</html>` document string.

### B2. The plot
**File:** `mizan/reporting/plots.py` (edit, additive).
```python
def render_crypto_equity_curve_plot(daily_snapshots: tuple[DailySnapshot, ...]) -> bytes:
    ...
```
One PNG, one line: `portfolio_value` at each `as_of_date`, via the same `Agg`-backend `plt.subplots()`
/ `figure.savefig(..., format="png")` / `plt.close(figure)` sequence `render_equity_curve_plot`
already uses (`mizan/reporting/plots.py:56-85`) — reused by literal code shape, not by calling the
equity function, since crypto has no gross-vs-net-of-purification split to plot a second line for
(crypto purification is near-empty per the baby PRD). Added to the existing `mizan/reporting/plots.py`
rather than a new `mizan/crypto/plots.py` so the `matplotlib.use("Agg")` backend selection
(`mizan/reporting/plots.py:19`, which must run before `pyplot` is ever imported anywhere in the
process) stays declared exactly once for the whole repo. `daily_snapshots == ()` renders the same
"No trading days in this backtest window." single-panel annotation the equity function already uses
for its own empty case (§7-equivalent guard, consistency over independent invention).
`mizan/crypto/report.py` imports this one new function from `mizan.reporting.plots`, base64-embeds
it exactly as `mizan.reporting.report._render_plots_section` already does
(`mizan/reporting/report.py:250-266`), inside its own local `_render_crypto_plots_section`.

### B3. `mizan/cli/crypto.py` — the single pipeline command
**File:** `mizan/cli/crypto.py` (new). Registers **one** verb, `crypto-pipeline`, deliberately
distinct from equity's four separate `ingest`/`screen`/`backtest`/`report` verbs
(`mizan/cli/main.py:36-41`): the baby PRD's own acceptance criterion is "a single command that runs
the full pipeline" (AC 1), not four composable ones — equity's multi-verb design is Phase 2–7's
own precedent for an *inspectable, re-runnable-per-stage* workflow; crypto's PRD explicitly asks
for the opposite (one command, one run).
```python
def add_subparser(subparsers) -> None:
    parser = subparsers.add_parser(
        "crypto-pipeline",
        help="Fetch, screen, backtest and report the locked 14-token crypto universe, end to end.",
    )
    parser.add_argument("--start-date", required=True, type=_parse_iso_date)
    parser.add_argument("--end-date", required=True, type=_parse_iso_date)
    parser.add_argument("--initial-cash", required=True, type=float)
    parser.add_argument("--db-path", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--interval-days", required=False, type=int, default=30)
    parser.add_argument("--granularity", required=False, default="1d")
    parser.add_argument("--taker-fee-rate", required=False, type=float, default=0.006)
    parser.add_argument("--slippage-rate", required=False, type=float, default=0.0005)
    parser.set_defaults(handler=run)
```
Deliberately **no** `--ticker` flag: `run_crypto_backtest` "takes no `tickers`/`universe`
parameter — the locked 14-token universe cannot be widened or narrowed by a caller"
(`mizan/crypto/backtest.py:199-201`, already a Phase 4 design decision this phase inherits
unchanged), matching AC 1's "fetches real OHLCV daily candles for all 14 named tokens" — not a
caller-chosen subset.

`run(args) -> int`:
1. Opens one `httpx.Client()` as a context manager (keyless, no auth headers — reusing
   `mizan.crypto.ingest_coinbase`/`ingest_kraken`'s own existing public-endpoint calls
   unmodified) and one **writable** `db.connect(args.db_path, read_only=False)` — unlike every
   equity verb and `mizan backtest`/`mizan report` (all `read_only=True`, since they only read an
   already-ingested DB), `crypto-pipeline` genuinely ingests, so it is the one CLI entry point in
   this repo that opens DuckDB for writing.
2. Calls `mizan.crypto.ingest.ingest_universe_candles(granularity=args.granularity,
   start=datetime.combine(args.start_date, time.min, tzinfo=UTC), end=datetime.combine(
   args.end_date, time.min, tzinfo=UTC), cache_dir=args.cache_dir, con=con, client=client)`,
   printing `f"{ticker}: fetched via {source}"` per ticker to stdout (surfacing the
   Coinbase-primary/Kraken-fallback choice AC 1 requires be real, not asserted).
3. Calls `mizan.crypto.screening.screen_universe()` once, for the report's full 23-token verdict
   table (§A4) — independent of step 4's own internal, fresh `screen_universe()` call inside
   `run_crypto_backtest` (`mizan/crypto/backtest.py:126`), matching that function's own documented
   "read fresh on every call — never cached at import time" posture (§A6 of `PHASE_4_SPEC.md`);
   calling it twice in one pipeline run is the correct, honest cost of that design, not a bug to
   dedupe away.
4. Calls `mizan.crypto.backtest.run_crypto_backtest(con=con, start_date=args.start_date,
   end_date=args.end_date, initial_cash=args.initial_cash, interval_days=args.interval_days,
   cost_params=BacktestCostParams(taker_fee_rate=args.taker_fee_rate,
   slippage_rate=args.slippage_rate), granularity=args.granularity)`.
5. Builds `CryptoReportInput(backtest_result=CryptoBacktestResult.model_validate(
   envelope.payload), token_verdicts=tuple(CryptoTokenVerdict.model_validate(v.payload) for v in
   verdicts.values()))`, resolves `active_caveats` via `resolve_crypto_report_caveats(
   envelope.active_caveats, CRYPTO_FIQH_PARAMS)` (§B1), calls `render_crypto_report(...)`, and
   writes the HTML to `args.output_path` — all still inside the `with db.connect(...)` block,
   matching `mizan/cli/report.py:103-129`'s own established "don't close the connection before the
   report is rendered" discipline.
6. Prints the output path and final portfolio value to stdout; returns 0. No per-ticker halting
   exception set is caught here (unlike equity's `_HALTING_ERRORS`): crypto screening is pure,
   in-memory, and total over the 23-token map (`mizan/crypto/screening.py:153-159` only raises
   `UnknownTokenError` for a ticker outside the curated map, which cannot occur here since the
   caller supplies no ticker argument at all).

`mizan/cli/main.py`: add `from mizan.cli import crypto as crypto_cli` and one line,
`crypto_cli.add_subparser(subparsers)`, inside `build_parser()` — the one place later phases touch
in this file, per its own docstring (`mizan/cli/main.py:28-31`).

### B4. Part-B tests
**File:** `tests/test_crypto_report.py` (continued). `resolve_crypto_report_caveats` returns the
backtest caveats plus `CUSTODY_FREEZE_RISK` when `fiqh_params.custody_model.value is
CustodyModel.EXCHANGE_QABD_HUKMI` (the default); returns exactly the backtest caveats, unchanged,
when a test-local `CryptoFiqhParams(custody_model=FiqhParam(register_id=3,
value=CustodyModel.SELF_CUSTODY, source="test"))` is passed instead. `render_crypto_report` on a
seeded `CryptoReportInput` produces a `<!DOCTYPE html>` document containing the literal rendered
survivorship-bias description text (verbatim substring, mirroring `PHASE_7_SPEC.md`'s own AC3
precedent) when `Caveat.SURVIVORSHIP_BIAS` is in `active_caveats`, and the literal custody/freeze
description text when `Caveat.CUSTODY_FREEZE_RISK` is in `active_caveats`; omitting the keyword
entirely (`render_crypto_report(data)`) is a `TypeError` (static `mypy --strict` check, not a
runtime test).

**File:** `tests/test_reporting_plots.py` (extend). `render_crypto_equity_curve_plot` on a
non-empty `daily_snapshots` tuple returns non-empty PNG bytes (`bytes[:8] ==
b"\x89PNG\r\n\x1a\n"`, the standard PNG magic-number check); on `()` returns valid PNG bytes with
no raised exception.

**File:** `tests/test_cli_crypto_pipeline.py` (new, mirrors `tests/test_cli_report.py`'s shape).
Seeds a real on-disk DuckDB file with `candles` rows for all 14 `CRYPTO_UNIVERSE` tickers
(reusing `tests/test_crypto_backtest_integration.py`'s own `_seed_db`-style helper, adapted to a
file-backed, not `:memory:`, connection, since the CLI handler opens its own connection by path)
and monkeypatches `mizan.crypto.ingest.ingest_universe_candles` to a no-op returning a fixed
source map (the integration test for *real* Coinbase/Kraken network calls is `tests/
test_crypto_backtest_integration.py`'s own established boundary — §Out of scope below keeps that
boundary unchanged for this phase too). Asserts the handler returns 0, `args.output_path` exists
and starts with `<!DOCTYPE html>`, and the written file contains the literal strings `"AAVE"` and
`"custody_freeze_risk"` is never printed as a raw enum repr anywhere (only its rendered
`CAVEAT_DESCRIPTIONS` prose should appear) — a regression guard against accidentally rendering
`str(Caveat.CUSTODY_FREEZE_RISK)` instead of its looked-up description.

### B5. Documentation
- `docs/crypto/ARCHITECTURE.md` (edit, additive paragraph): the new `Caveat.CUSTODY_FREEZE_RISK`
  member and why it is a shared-enum addition, not a crypto-local type (§A1); why
  `mizan/crypto/report.py` is a new, parallel module rather than a crypto-shaped reuse of
  `mizan.reporting.report.ReportInput` (§A4); why `crypto-pipeline` is one verb, not four (§B3).
- `docs/crypto/PHASE_6_SPEC.md`: commit this spec as the governing document, matching the Phase
  1–5 precedent.
- `README.md`: one added sentence noting the single `mizan crypto-pipeline` command and the
  self-contained crypto HTML report (fiqh citations, all 23 token verdicts with reasons,
  survivorship-bias warning, exchange-custody/freeze-risk caveat) now exist end-to-end, and that
  equity's own four CLI verbs remain unmodified and importable.

### B6. No forbidden drift built (continuity of PHASE_1_SPEC.md §A6/B6, PHASE_2_SPEC.md §B7,
PHASE_3_SPEC.md A0.10/B5, PHASE_4_SPEC.md B6, PHASE_5_SPEC.md B6)
**File:** `tests/test_phase1_scope.py` (extend).
- `test_crypto_pipeline_cli_takes_no_ticker_flag`: source-grep `mizan/cli/crypto.py` for the
  literal string `"--ticker"` — it does not appear, confirming the locked-universe design (§B3)
  was not quietly loosened into a caller-selectable universe.
- `test_crypto_report_module_has_no_network_capability`: source-grep `mizan/crypto/report.py` for
  `httpx`/`requests`/`socket` — none appears (reporting renders already-fetched data; it must
  never fetch anything itself).
- `test_equity_cli_verbs_and_modules_still_import_after_crypto_pipeline_lands`: imports
  `mizan.cli.ingest`, `mizan.cli.normalize`, `mizan.cli.screen`, `mizan.cli.backtest`,
  `mizan.cli.report`, `mizan.data.ingest_edgar`, `mizan.screening.financial_ratios`, and asserts
  `mizan.cli.main.build_parser()`'s subparser choices still include every equity verb name
  (`"ingest"`, `"normalize"`, `"screen"`, `"backtest"`, `"report"`) **and** the new
  `"crypto-pipeline"` — a concrete, machine-checked re-confirmation of AC 14 ("equity V1 modules
  still import successfully but are not invoked by the default command path") at the exact point
  a new top-level verb is wired into the one shared parser, not merely an assumption carried over
  from Phase 1's own test.
- `test_phase6_governing_spec_copy_exists_on_disk`: mirrors the existing Phase 2/4/5 siblings.

**Part B done when:** all Part-A + Part-B tests pass, `mypy --strict`/`ruff` clean,
`mizan-boot-check` still exits 0, `mizan crypto-pipeline --help` runs and lists every flag in §B3,
a full invocation against a seeded DB produces a single HTML file containing all four required
sections (fiqh register, all 23 token verdicts, survivorship warning, custody/freeze caveat) plus
the backtest summary and plot, and every equity CLI verb still resolves via
`mizan/cli/main.py:build_parser()`.

## Acceptance-criteria mapping (Phase 6)
| AC | Satisfied by | Concrete check |
|----|--------------|----------------|
| 1 — single command fetches real candles for all 14 tokens, Kraken fallback, end-to-end | B3 | `tests/test_cli_crypto_pipeline.py`; `tests/test_crypto_ingest*.py` (Phase 2, unchanged) for the real fetch behaviour `ingest_universe_candles` already has |
| 7 — single HTML report: fiqh citations, per-token verdicts w/ reasons, survivorship warning, custody/freeze caveat | A4, B1, B2 | `tests/test_crypto_report.py`; literal-substring assertions on rendered output |
| 14 — equity V1 modules still import, not on the default (crypto) command path | B6 | `tests/test_phase1_scope.py::test_equity_cli_verbs_and_modules_still_import_after_crypto_pipeline_lands` |
| 15 (doc) — two-speed roadmap documented, no HFT/adapter code built | B5 | `docs/crypto/ROADMAP.md` (Phase 1, unchanged); `tests/test_phase1_scope.py`'s existing no-network/no-adapter guards (Phases 1-5, unchanged) |
| 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13 | Phases 1–5 (unchanged by this phase) | Not in Phase 6 scope. |

## Documentation sources
No new external research was required for this phase. The report-module split (a new
`mizan/crypto/report.py` rather than forcing crypto data through equity's `ReportInput`), the
single-verb CLI design, and the shared-`Caveat`-enum extension all follow directly from reading
the actually-shipped Phase 1–5 code (`mizan/core/caveats.py`, `mizan/reporting/report.py`,
`mizan/reporting/plots.py`, `mizan/crypto/backtest.py`, `mizan/crypto/screening.py`,
`mizan/crypto/fiqh_register.py`, `mizan/cli/main.py`, `mizan/cli/report.py`,
`mizan/cli/backtest.py`, `mizan/config/boot_check.py`) rather than from this run's own research
digest, which (per `runs/42cd206f-79c0-42db-87c0-3168716066ea/spec/context.md` §"Phase plan") scoped
Phase 6 as "HTML report + single pipeline command; confirm equity parked" without a dedicated
research item of its own — the ingestion/backtest/screening research items (Phase 2-5's own
Documentation sources sections) already cover every technical dependency this phase reuses.

This spec was checked against the Phase 5 code actually shipped (`mizan/signal/contract.py`,
`mizan/signal/validation_gate.py`, HEAD `ddcdd6f`), not only against `PHASE_5_SPEC.md`'s text: the
signal-adapter seam remains entirely unreferenced by `mizan/crypto/` and `mizan/backtest/` (per
that phase's own B6 scope guard, re-verified by this reviewer turn at HEAD `44bc18c`), confirming
Phase 6's report and pipeline command have nothing to wire to or guard against on that front.

## Out of scope for this phase
- Any change to `mizan/signal/` or the validation-gate seam — Phase 5 is complete and this phase
  neither calls `require_passing_gate` nor references `SignalAdapter`/`Signal` anywhere.
- Real-network integration testing of `crypto-pipeline`'s ingestion step — `tests/
  test_cli_crypto_pipeline.py` (§B4) monkeypatches `ingest_universe_candles` to a no-op; the real
  Coinbase/Kraken HTTP calls remain covered exclusively by Phase 2's own ingestion tests and
  `tests/test_crypto_backtest_integration.py`'s existing seeded-DB boundary, unchanged by this
  phase.
- Equity's own `report`/`backtest`/`screen`/`ingest`/`normalize` CLI verbs or their underlying
  modules — none is modified beyond the one forced `CAVEAT_DESCRIPTIONS` line (§A3); every equity
  test file passes unchanged.
- A `--no-plots` or similar suppression flag on `crypto-pipeline` — matching
  `mizan/cli/report.py:46`'s own stated reasoning: a report that silently omits its own plot on
  request is not a reporting concern this phase's scope needs.
- Modelling the custody/freeze risk itself (an exchange-failure simulation, a freeze-probability
  parameter) — only the caveat disclosure is built; the baby PRD explicitly keeps this
  "caveated, not modelled."
- Any CLI flag to override the locked 14-token `CRYPTO_UNIVERSE` — `crypto-pipeline` takes no
  `--ticker` flag at all (§B3, enforced by B6's scope-guard test).
- Re-deriving or contesting any fiqh register value — this phase renders the existing
  `CryptoFiqhParams`/`FIQH_PARAMS` registers; it introduces no new fiqh judgment call of its own
  (the new `Caveat` member documents an existing, already-registered custody fact — register #3,
  `mizan/crypto/fiqh_register.py:32-40` — it does not create a new one).

## Spec assumptions
Gaps found while writing this spec were resolved as follows (nobody was asked):
- The pipeline verb is named `crypto-pipeline`, not `pipeline` or `run`: a bare `pipeline`/`run`
  verb name would read, next to equity's `ingest`/`normalize`/`screen`/`backtest`/`report`, as if
  it were a fifth stage in the *same* equity pipeline rather than a wholly separate, single-shot
  crypto command — the hyphenated `crypto-` prefix makes the domain boundary visible in the CLI
  surface itself, matching `mizan/crypto/`'s own module-naming convention.
- `resolve_crypto_report_caveats` treats the custody caveat as *derived from the register in
  force*, not hardcoded into every crypto report — chosen because `CryptoFiqhParams.custody_model`
  is itself a configurable `FiqhParam` (§B1), and a report rendered from a hypothetical
  self-custody register should not carry a caveat about a risk that register no longer accepts;
  inventing a second, always-true custody caveat would misrepresent a future non-default run.
- `screen_universe()` is called twice in one `crypto-pipeline` invocation (once by
  `run_crypto_backtest` internally, once by the CLI handler for the report's full 23-token table)
  rather than threading one shared result through both — chosen to preserve
  `_compliant_universe_tickers`'s own Phase 4 "read fresh on every call" contract
  (`mizan/crypto/backtest.py:124-125`) unmodified; `screen_universe` is pure, in-memory, and
  O(23), so the duplicate call costs nothing measurable and keeps `run_crypto_backtest`'s own
  signature untouched by this phase.
- The crypto report embeds exactly one plot (the portfolio equity curve), not two — equity's
  report embeds two (gross vs. net-of-purification equity curve, purification-by-ticker) because
  equity purification is a real, non-trivial ledger; crypto purification is near-empty by PRD
  design (no dividends, staking off), so a second "purification by ticker" plot would render an
  always-empty chart with no information content.
- `crypto-pipeline` opens DuckDB with `read_only=False` — the one necessary deviation from every
  other CLI verb's `read_only=True` convention (`mizan/cli/backtest.py:100`, `mizan/cli/
  report.py:103`, `mizan/cli/screen.py:90` are all read-only) — because this is the one verb in
  the entire CLI that performs its own ingestion rather than reading an already-populated store;
  the deviation is load-bearing, not an oversight, and is called out explicitly in §B3 so a future
  reviewer does not "fix" it back to `read_only=True`.

## Implications
Second-order consequences found by review of this spec. This section only adds to the spec; the
locked PRD is unchanged.

### Additional acceptance criteria
S8. A test (`tests/test_caveats.py::...`) asserts that importing `mizan.reporting.report` succeeds
after `Caveat` gains its fourth member — i.e. that §A3's forced edit was actually made, not merely
planned. _(correctness/scope: this is the one edit in this entire phase capable of silently
breaking every equity CLI verb at import time if skipped; catching it in this phase's own test
suite, rather than in a later phase's `mizan boot-check` run, is strictly cheaper.)_

## Red-team findings
Weaknesses found by an adversarial review of this spec before it is built. This section only adds
to the spec; the locked PRD is unchanged.

### Additional acceptance criteria
R6. A test asserts `render_crypto_report(data)` (the keyword omitted entirely) is a `TypeError`,
and that `mypy --strict` rejects a call site missing `active_caveats` as a static error — not only
that the rendered output "looks right" when the keyword is supplied. _(medium, correctness: if a
future contributor copies `render_report`'s call-site shape but gives `active_caveats` a default
value by mistake on the crypto side, a report could render with zero caveats and no error anywhere,
exactly the failure mode `ULTIMATE_PRD.md §2.2` exists to make structurally impossible.)_
R7. A test parametrized over `CustodyModel.EXCHANGE_QABD_HUKMI` and `CustodyModel.SELF_CUSTODY`
asserts `resolve_crypto_report_caveats` returns a *different* tuple for each — not merely that the
exchange-custody case includes the caveat, but that the self-custody case provably excludes it.
_(medium, correctness: a `resolve_crypto_report_caveats` that unconditionally appends
`CUSTODY_FREEZE_RISK` regardless of `custody_model` would still pass a test that only checks the
default case, silently mis-describing any future self-custody run as still carrying exchange-freeze
risk.)_
R8. A test asserts `crypto-pipeline`'s registered `argparse` parser has no `--ticker` argument
(§B3, §B6) using the parser object itself (`"--ticker" not in {a.option_strings[0] for a in
parser._actions if a.option_strings}` or equivalent), not only a source-grep for the string
`"--ticker"` — a source-grep alone would miss a differently-spelled-but-equivalent flag (e.g.
`--tickers` or `--symbol`) that reintroduces the same caller-selectable-universe hole under a new
name. _(low, maintenance: belt-and-suspenders against the scope guard's own blind spot.)_
