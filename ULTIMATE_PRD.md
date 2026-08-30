# Mizan — ULTIMATE_PRD (V1)

**Status:** locked, pre-build · **modernised 2026-08-30** (Step 10 pass)
**Synthesized from:** `context.md` (posture) + `MASTER_PRD.md` (spec) + `.claude/loopr/baby_prd.md`
and `.claude/loopr/context.md` (confirmed loopr interrogation output).
**Document role:** This is the single canonical, execution-ready artifact the phase loop verifies
against. It does not restate every clause of `MASTER_PRD.md` — it locks the architecture, cites the
external grounding that validates it, and hands off a dependency-ordered build sequence. Where this
document is silent, `MASTER_PRD.md` governs. Where this document and `MASTER_PRD.md` conflict on a
**verifiable external fact** (a version number, an API shape, a published rate limit), **this
document governs** and the conflict is logged in `## MODERNIZATION CHANGELOG` below. Where they
conflict on **architecture or the permissibility boundary**, neither governs — it is escalated in
`## OPEN ARCHITECTURE QUESTIONS`.

**Modernization provenance:** every version, endpoint shape, rate limit, and threshold in this
document was re-verified against a primary source on **2026-08-30**. Anything that could not be
re-verified carries an explicit `[UNVERIFIED]` tag naming what was searched. See the changelog.

**Citation convention (note for the downstream loop).** Bare `context.md` §N references below are
**inherited from the Step-7-era context document, which is no longer present in this repository**;
they are kept because `MASTER_PRD.md` folded that document's content into itself (`MASTER_PRD.md`
§Document role), so the claims are traceable there. The *current, live* posture document is
**`.claude/loopr/context.md`**, which is cited by its section heading (e.g. "§ Soft context,
note 2"), never by number. Do not attempt to resolve a bare `context.md` §N against
`.claude/loopr/context.md` — they are different documents.

---

## 1. The Thesis

Mizan is a **personal, long-horizon research foundation** for halal-constrained quantitative
finance — not a product, not a client demo, not a live-trading system (`context.md` §1, §6;
`baby_prd.md` TL;DR). The problem it solves: there is no correct, honest, auditable substrate for
learning how AAOIFI-style Shariah screening, purification, and a compliance-flip state machine
actually behave under real market data, before any of it is allowed near real capital.

The hard constraints from `MASTER_PRD.md` force one architecture, not a menu of them:

- **A hallucinated compliance verdict is the worst possible failure** (`MASTER_PRD.md` §2, §13;
  `baby_prd.md` scope edge #5, reconfirmed as **permanent**, not a "for now") — compliance logic
  must be **fully deterministic**, which rules out any LLM/agent-routing design by construction,
  not by preference.
- **Every fiqh judgment call is a placeholder for a scholar's ruling, never a silent hardcode**
  (`MASTER_PRD.md` §0, §10) — the config layer must physically separate *invariants* (no knob) from
  *parameters* (knobbed, sourced, flagged), so the split is legible on disk, not just in prose.
  This is the honesty surface (`context.md` §2–3).
- **Every result carries its caveats structurally** (`MASTER_PRD.md` §9.2) — the result object,
  not the README, is where look-ahead/survivorship/pending-verification live. A reporter that can
  render an un-caveated number is a bug.
- **This is a single-user batch research tool, not a service** (`MASTER_PRD.md` §9, `context.md`
  §5) — jobs/CLI entrypoints over an embedded analytical store, static HTML+plots for output. No
  FastAPI, no dashboard, no concurrency-ops surface this tool doesn't need.

A deterministic batch pipeline is therefore not merely *an* option — given the failure mode that
must never happen (a hallucinated verdict) and the audience that must be served (one researcher
learning the mechanics), it is the only honest foundation. Anything more "production-shaped" would
be solving a problem this project doesn't have; anything less deterministic would risk the one
failure this project cannot tolerate.

### 1.1 Values position — what is settled, and what is explicitly deferred (NEW, from `baby_prd.md`)

The original `MASTER_PRD.md` scoped everything around "long-only quarterly-rebalance backtesting"
without distinguishing that this framing was *already inside* the settled-permissible zone from a
separate, still-open values question. The loopr interrogation (`baby_prd.md` scope edge #2, staleness
flag) resolved and named that split. It is now recorded here as a first-class scope edge:

| Position | Status | Consequence for this build |
|---|---|---|
| Baseline long-only, halal-screened, fully-funded, no shorting/derivatives/leverage, hold-and-rebalance at a **quarterly** cadence | **Settled-permissible enough to build now** (post-Musaffa education) | This is V1. Build it. |
| **HFT / daily-profit-seeking trading of any kind — even fully long-only and unlevered** | **DEFERRED — values position not yet resolved** | Out of scope entirely. Not a performance knob. |

**Operational rule for the phase loop and for every future request:** a proposal to shorten the
rebalance cadence below quarterly, to add intraday or daily signals, or to optimise for
short-horizon profit is **crossing a values boundary, not tuning a parameter**. It must be
escalated to the human, never absorbed as an enhancement. The rebalance cadence is quarterly
(`MASTER_PRD.md` §7); `grace_period_rebalances` (register #8) tunes *divestment timing within* that
cadence and is not a licence to change the cadence itself.

This edge is *deferred*, not *forbidden by the permissibility boundary* — it lives in §1.1, not in
§5. It does not gain a grep-able code check, because there is no V1 code shape that expresses it;
it is enforced at the spec/review layer. See `## OPEN ARCHITECTURE QUESTIONS` Q3 for a primary
source bearing on this edge that was surfaced (and deliberately **not** applied) by this pass.

---

## 2. The System Map (deterministic data flow — no agent routing)

```
INGEST (jobs)                 NORMALIZE              SCREEN (deterministic)        BACKTEST (event loop)          REPORT
──────────────                ───────────            ────────────────────        ────────────────────         ─────
SEC EDGAR                 │                          business_activity.py  │        clock.py (daily)                static
  companyfacts/           │                            (SIC first-pass +   │        portfolio.py                    HTML +
  companyconcept          │                             curated map,       │        (CASH_YIELD=0.0)                plots
  XBRL JSON               ── raw cache ──► DuckDB ───►    tiered)             ── Verdict → strategy.py → compliance_   (every
  + submissions (SIC)     │  (Parquet/     1.5.5        financial_ratios.py │   (3-     (long-only,   state.py       number
  (data.sec.gov)          │   JSON,        (typed,        (30/30/5,         │  state)    pluggable)   (flip→grace→   stamped
                          │   replayable)  as-of          denom from        │                          divest)       with
Tiingo EOD                │                tables)        config)           │                              │         active_
  adjClose + divCash      │                              verdict.py ────────                        purification.py  caveats
  + splitFactor           │                                (reason trace)                             (side-ledger,   [])
  (api.tiingo.com)                                                                                    divCash-driven)
```

**Change from the pre-modernization map:** SEC **`submissions`** is now shown as a distinct
required endpoint alongside `companyfacts`/`companyconcept`. `MASTER_PRD.md` §5.1 listed SIC codes
as a "bonus field" of the XBRL API; that is **wrong**. Verified live on 2026-08-30: `companyfacts`
returns only `{cik, entityName, facts:{dei, us-gaap}}` — no SIC anywhere. `sic` and `sicDescription`
live in `https://data.sec.gov/submissions/CIK##########.json`. The business-activity screen's
first-pass signal therefore requires a **third** EDGAR call per ticker. See §3.4 and the changelog.

### 2.1 Pinned dependency versions (all re-verified against PyPI/vendor docs on **2026-08-30**)

Pin **exact** versions. This is a reproducibility-critical research tool; a floating range that
silently changes a numerical result between runs is a correctness failure, not a convenience.

| Library | Pinned version | Verified at | Role |
|---|---|---|---|
| Python | `>=3.11,<3.15` (build against **3.14.x**) | [python.org 3.14.7](https://www.python.org/downloads/release/python-3147/) | runtime |
| `pydantic` | **2.13.5** (rel. 2026-08-28) | [pypi.org/project/pydantic](https://pypi.org/project/pydantic/) | `config/` + `core/` validation, `ConfigDict(extra="forbid")` everywhere |
| `duckdb` | **1.5.5** (rel. 2026-07-22) | [pypi.org/project/duckdb](https://pypi.org/project/duckdb/) | embedded analytical store |
| `pyarrow` | **25.0.1** (rel. 2026-08-10) | [pypi.org/project/pyarrow](https://pypi.org/project/pyarrow/) | Parquet raw cache + DuckDB↔Arrow interchange |
| `pandas` | **3.0.5** (rel. 2026-07-22) | [pypi.org/project/pandas](https://pypi.org/project/pandas/) | tabular glue for strategy/report layers |
| `matplotlib` | **3.11.1** (rel. 2026-07-18) | [pypi.org/project/matplotlib](https://pypi.org/project/matplotlib/) | static plots for the HTML report |
| `httpx` | **0.28.1** (rel. 2024-12-06) | [pypi.org/project/httpx](https://pypi.org/project/httpx/) | EDGAR/Tiingo REST calls (sync, explicit rate limiting) |
| `mypy` | **2.3.1** (rel. 2026-08-15) | [pypi.org/project/mypy](https://pypi.org/project/mypy/) | type gate, run `--strict` |
| `ruff` | **0.16.5** (rel. 2026-08-27) | [github.com/astral-sh/ruff/releases](https://github.com/astral-sh/ruff/releases) | lint/format |
| `pytest` | **9.1.1** (rel. 2026-06-19) | [pypi.org/project/pytest](https://pypi.org/project/pytest/) | test runner |

Every pin above publishes `cp311`–`cp314` wheels, so **any** interpreter in `>=3.11,<3.15` works;
the local machine runs Python 3.14.x, so build against that and record the exact patch version in
`docs/modernization_log.md`.

**`httpx` note:** 0.28.1 (Dec 2024) is still the latest **stable** release; `1.0.dev5` (2026-08-21)
is a pre-release. Pin the stable. Do not pin a `.dev` build into a research tool.

**Three version bumps carry behavioural consequences the build agent must know about:**

1. **`pandas` 3.0 is a major, breaking release** ([whatsnew/v3.0.0](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html)):
   Copy-on-Write is now the *only* behaviour (chained assignment `df[col][row] = v` silently no
   longer works — it is a no-op on the original, not an error); the default string dtype is now
   `str` (PyArrow-backed when PyArrow is installed, which it is here); `to_datetime` on strings now
   infers **microsecond** resolution (`datetime64[us]`), not nanosecond; minimum Python is 3.11.
   **Consequence for Phases 3/5/6/7:** never use chained assignment; assert dtypes explicitly at
   every DuckDB↔pandas boundary rather than trusting inference; and when comparing a Tiingo `date`
   to an EDGAR `filed` date, normalise both to `datetime.date` in Python rather than relying on
   pandas datetime resolution matching across sources.
2. **`mypy` 2.x is a major release** (2026-05-06,
   [mypy-lang.blogspot.com](https://mypy-lang.blogspot.com/2026/05/mypy-20-relased.html)):
   `--local-partial-types` and `--strict-bytes` are now **default**; `--allow-redefinition` changed
   meaning (legacy behaviour is now `--allow-redefinition-old`); `--python-version 3.9` is a hard
   error. `--strict` still exists and is still the gate. No project change needed beyond the pin —
   recorded so a build agent does not "fix" a new default by loosening it.
3. **`pyarrow` 25.x** pairs with `duckdb` 1.5.5 and `pandas` 3.0.5; the Arrow interchange path in
   §3.4 was re-verified against the DuckDB 1.5 reference, and one signature in the previous version
   of this document was **wrong** — see §3.4 and the changelog.

No FastAPI, no Gemini/Vertex SDK, no LLM client library, no `yfinance` anywhere in this table —
their absence is deliberate and permanent (`context.md` §6, `MASTER_PRD.md` §9,
`baby_prd.md` scope edge #5).

### 2.2 Two load-bearing seams (repeat from `MASTER_PRD.md` §9.2, because Phase 1 must not erode them)
- `screen(ticker, as_of_date) -> Verdict` is the **only** place the Fork-1 look-ahead simplification
  may live. Any other function touching filing dates must hard-filter by `as_of_date`.
- A backtest result is `(returns, purification_ledger, active_caveats: list[Caveat])`. The reporter
  takes this tuple as its only render input — there is no code path that renders a number without
  its caveat set attached.

---

## 3. State-of-the-Art Justification (grounded, not guessed)

Every citation below was fetched and read on **2026-08-30** by this pass, unless explicitly marked
inherited or `[UNVERIFIED]`. Where the previous version of this document asserted something it
could not re-verify, that assertion has been either upgraded to a verbatim primary-source quote or
demoted to `[UNVERIFIED]`.

### 3.1 Shariah screening math (denominator + threshold construction)

**Primary source, now actually read (upgrade from the previous pass, which could only cite it):**
the AAOIFI Secretary-General presentation *"Shari'ah Screening Methodology," Dr. Hamed Merah,
October 2017* ([oicexchanges.org PDF](https://www.oicexchanges.org/files/1---shari-ah-screening-in-the-islamic-capital-markets-dr-hamed-merah-secretary-general-aaoifi.pdf),
37 slides). AAOIFI Shari'ah Standard No. 21 itself remains paywalled; this presentation is the
public methodology reading. Slide 27 dates SS21: *"AAOIFI issued in May 2004, its Shari'ah standard
No. 21 on financial papers."*

**(a) The business-activity screen — AAOIFI's own enumerated list, verbatim (slide 18):**

> "According to the industry screening, if a company's core business is related to one of the
> following area, this company will be considered non Shari'ah Compliance… 1 Conventional financial
> institutions · 2 Conventional insurance companies · 3 Alcoholic beverages · 4 Gambling · 5 Pork
> and Non-Halal food · 6 Non-Halal food · 7 Tobacco-related Products · 8 Any activities deemed
> unlawful"

This **directly and independently validates** `MASTER_PRD.md` §6.1's tiering, on two specific
points that were previously reasoned rather than sourced:

1. **"Non-halal food," not just "pork," is AAOIFI-explicit** — items 5 *and* 6 both appear. The
   §6.1 correction to the earlier "pork-only" framing is confirmed against the primary source.
2. **Adult content and weapons/defence are NOT in AAOIFI's enumerated list.** They appear in this
   presentation only in slide 31's *comparison* table of Dow Jones / FTSE / S&P / Kuala Lumpur
   criteria ("Entertainment · arms, defence"). AAOIFI's own list reaches them only through item 8,
   "Any activities deemed unlawful." `MASTER_PRD.md` §6.1's decision to demote them out of the
   hardcoded Tier 0 into a **flagged, configurable Tier 0.5** is therefore not a judgment call —
   it is the primary-source-faithful reading. Register #6 stays configurable. Likewise Tier 1
   (media/music/entertainment, hotels) maps to the index-provider "Entertainment" line, not to
   AAOIFI — register #7 stays configurable and default-OFF.

**(b) The 30/30/5 thresholds — confirmed (slides 32, 33, 34):** the AAOIFI columns read "Halal
Financing 70% / 30%" for the debt ratio and again for the investment ratio, against DJ/FTSE/S&P at
33% and S&P at 49% receivables. Non-halal income is stated verbatim as *"Non Halal Income Should
not Exceed 5% of Total Income."* AAOIFI's tighter-than-33% posture is confirmed.

**Precision correction:** the non-permissible-income denominator in the primary source is
**"Total Income"**. `MASTER_PRD.md` §6.2 item 3 says "total revenue." These are not the same line
item under US GAAP. This is now register #5's explicit ambiguity and must be surfaced as such in
`config/fiqh_params.py` — see `## OPEN ARCHITECTURE QUESTIONS` Q2.

**(c) The three-state verdict taxonomy — confirmed verbatim (slide 21):**

> "Pure — Shari'ah compliant core business and no interest based deposits or loans"
> "Mixed — Shari'ah compliant core business and financial ratios that do not exceed the thresholds"
> "Non Shari'ah Compliance — with Non-Halal activity as its core source of income and if debt and
> investment ratios exceed the allowed thresholds"

`MASTER_PRD.md` §6.3's `Verdict` enum is a direct transcription of the primary source. Locked.

**(d) `[UNVERIFIED]` — AAOIFI's own denominator basis and averaging window.** The previous version
of this document asserted that "AAOIFI specifies *no averaging window* (SS21 refers only to 'the
last budget or verified financial position'), so spot market cap is the faithful reading." **This
pass could not verify that.** The Merah presentation states the *other* standards' denominators
explicitly (slide 31: DJ = "trailing 12 month moving average market capitalisation"; FTSE = "total
assets"; S&P = "market value of equity (12 month average)") but **never states AAOIFI's own
denominator or averaging window** in any extractable slide. Searched: the full 37-slide PDF text
(all slides extracted and grepped for "market cap", "average", "asset", "%"); `aaoifi.com`; a web
sweep for an SS21 revision or exposure draft touching stock screening (none found, 2025–2026).
The `amanahadvisors.com` 30%-rule explainer inherited from `MASTER_PRD.md` §Sources could not be
re-fetched — it now sits behind a Cloudflare bot challenge — so it too is `[UNVERIFIED]` this pass.

**This does not falsify the architecture; it strengthens it.** Register entries #1 (denominator
basis) and #2 (smoothing) already exist precisely because this is underdetermined. The correct
modernization is to **make the uncertainty louder**, not to resolve it: `config/fiqh_params.py` must
carry, for #1 and #2, a source string that says the AAOIFI denominator is *not* stated in the public
methodology and that the market-cap+spot default is an inference — not a source string that implies
AAOIFI settled it. This is a Phase 1 requirement (`PHASE_1_SPEC.md` §3.2, §7).

**Corroborating academic source (re-verified, and now at v2):** Qadi, Sharma & Medda, *"From Binary
Screens to Continuous Compliance: A Shariah Screening Measure for Portfolio Design,"*
[arXiv:2512.22858](https://arxiv.org/abs/2512.22858) — **v1 2025-12-28, v2 2026-03-11** (the
previous pass cited v1; v2 is now current). q-fin.PM / q-fin.GN. Continuous Shariah Compliance
Index (CSCI) on [0,1] embedding the business-activity and financial-ratio thresholds of **six**
leading standards, tested on CRSP/Compustat US equities 1999–2024. It corroborates three design
choices:

1. **Multiple standards map to materially different regions of a common compliance scale** — firms
   with the *same* pass/fail label "can still differ materially in compliance strength." This is
   exactly why `MASTER_PRD.md` §10 treats the denominator axis and the 30% threshold as
   *configurable parameters*, not settled constants.
2. **Providers differ specifically in "denominators, averaging windows, and the set of financial
   ratios they screen"** — a direct, independent restatement of Mizan's two-axis denominator config
   (register #1, #2). The paper naming *the same two axes* Mizan parameterises is the strongest
   available validation that the honesty surface is cut in the right place.
3. **A spot, unsmoothed denominator produces materially different compliance calls than an averaged
   one**, evidenced through the September-2023 DJIM/S&P methodology change admitting
   lower-compliance firms — the mechanism `MASTER_PRD.md` §6.2 names as "why a stock can flip
   compliant→non-compliant on price moves alone," and the empirical justification for building the
   compliance-flip state machine (§7.3) as a first-class mechanic rather than an edge case.

**New in v2 — an expectation-setting finding the reporter must not obscure:** CSCI shows **no
reliable association with returns** after controlling for standard characteristics. Compliance
intensity is not an alpha source. Mizan is a correctness-and-mechanics tool, not a strategy-search
tool; the report should not be built in a way that invites reading a compliance-tightness sweep as
a factor study. Recorded as guidance for Phase 7, not as a code invariant.

**New companion paper, same authors (2026-08-12):** *"The Price of Permission: Classification
Uncertainty in Constrained Capital Markets,"*
[arXiv:2608.12634](https://arxiv.org/abs/2608.12634) (q-fin.ST/GN/RM). 1999–2024 CRSP-Compustat
panel of 13,188 securities under **seven** researcher-emulated Shariah rulebooks. Two findings
bear directly on Mizan:

- **"Screening-rule disagreement and proximity to active boundaries rank next-month screen-implied
  transitions."** A holding's *distance to its binding threshold* predicts flips. This validates
  quarterly re-screening of every holding (§4.6 guard, `compliance_state.py`) as necessary rather
  than defensive, and suggests a **cheap, in-architecture enhancement**: since
  `financial_ratios.py` already computes every ratio against its threshold to produce the reason
  trace, the *margin* to each threshold is already in hand — surface it in the reason trace rather
  than discarding it. This is a reporting/inspection enrichment with zero effect on the verdict, so
  it does not touch the deterministic screen's output. **Applied** (see §6, Phase 4).
- **"U.S. Fama-MacBeth diagnostics do not support an unconditional equal-weighted permission
  premium… The evidence supports treating classification risk as a portfolio-monitoring state."**
  Again: monitoring, not alpha. Consistent with the framing above.

### 3.2 Purification math — now primary-sourced verbatim

The previous version of this document asserted that AAOIFI's P&L-exclusion rule needed "no
additional academic sourcing." That was true but unsourced. It is now sourced. Merah presentation,
slide 25, verbatim:

> "It must be noted that mixed shares will have to be cleansed (purified). Purification means that
> non Halal Income will have to be donated to Charity and cannot be included in the investors P&L
> accounts."

And slide 24, verbatim:

> "…it is allowed to invest in the institution [if] it passes the Shari'ah thresholds while it's a
> must to purify income through the Cleansing Process."

**"cannot be included in the investor's P&L accounts" is a side-ledger by construction.** Fork B
(`MASTER_PRD.md` §8) is therefore not a preference among accounting styles — it is the only reading
faithful to the primary source. This upgrades the §4.7 reporter assertion (`gross_return` and
`net_of_purification_return` must both be present and distinct) from a design choice to a
primary-source-backed correctness requirement.

Fork A (dividends-only, capital-gains OFF) and Fork C (time-bounded price appreciation for
forced-divestment attribution) remain **underdetermined by settled formula** — the presentation
says *that* non-halal income must be purified and *where it must not go*, but gives no formula for
attributing gains on a holding that flipped mid-hold. They stay configurable and `pending scholarly
verification` per the existing register (#9, #10). This document does not manufacture false
settledness.

### 3.3 Backtest correctness — look-ahead and survivorship bias

`MASTER_PRD.md` §7.1–7.2 and §13 name the canonical failure modes (look-ahead via
most-recent-available-filing instead of point-in-time; survivorship via an "exists today" universe)
and the correct fix (true point-in-time via EDGAR filing dates; a frozen historical universe
snapshot). The V1 simplification is quarantined to one function body — `screen(ticker, as_of_date)`
— so the V2 fix is a data-slicing change to that one function, not a rewrite.

**EDGAR's filing-date metadata is now verified present, not assumed.** Live fetch on 2026-08-30 of
`https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json`
returns facts with the key set `{start, end, val, accn, fy, fp, form, filed, frame}` — e.g.
`{"start":"2016-09-25","end":"2017-09-30","val":229234000000,"accn":"0000320193-19-000119","fy":2019,"fp":"FY","form":"10-K","filed":"2019-10-31","frame":"CY2017"}`.
Note the gap between `end` (2017-09-30) and `filed` (2019-10-31): **over two years.** That is the
look-ahead the V1 simplification incurs, made concrete. Instantaneous (balance-sheet) concepts omit
`start` and carry only `end`; duration concepts carry both. The V2 true-PIT fix is
`WHERE filed <= as_of_date` — a slicing change, confirmed.

**NEW literature, and the one applied enhancement of this pass:** Fonseca, *"Look-Ahead-Freedom as
Temporal Non-Interference: A Verifiable Correctness Property for Backtesting and Agentic Trading
Pipelines,"* [arXiv:2607.04958](https://arxiv.org/abs/2607.04958) (2026-07-06; cs.CR/LO/PL/SE,
q-fin.PM). It formalises look-ahead-freedom as *temporal non-interference over time-indexed
information structures*, and gives a type-and-effect system that is **sound and decidable in linear
time for value-independent operations — windowing, resampling, joins, and point-in-time reads** —
while showing the value-dependent case is Π⁰₁-hard.

This is directly applicable and **validates the locked architecture rather than threatening it**,
in a way worth spelling out: Mizan's entire screening data path *is* the value-independent
fragment — it is date-filtered reads and joins over as-of tables, with no data-dependent control
flow choosing which rows are visible. That is exactly the fragment the paper proves is
mechanically checkable. Two enhancements follow, both strictly inside the locked design:

1. **Name the property, not just the bug.** The one permitted look-ahead is not "a simplification we
   flagged" — it is a *single declared violation of temporal non-interference, confined to one
   function*. `screen()` gets that framing in its docstring and in the `Caveat` enum's
   documentation, so the V2 work item is "restore temporal non-interference in `screen()`," a
   checkable property, rather than "fix the look-ahead thing."
2. **Make the confinement grep-able and testable, not merely stated.** Every function other than
   `screen()` that touches a `filed` column must take `as_of_date` and filter on it. The Phase 4
   review check becomes: *grep every reference to the `filed` field across `mizan/`; every call site
   outside `screen()`'s body must be inside a function whose signature contains `as_of_date`.*
   That is a static, decidable, linear-time check on the value-independent fragment — precisely what
   the paper says is achievable. **Applied** (§4.4, §5, and §6 Phase 4).

No formal verification tooling is adopted. The enhancement is the *framing and the check*, not a
dependency. Adding a type-and-effect checker to a single-user research sandbox would be exactly the
"production-shaped solution to a problem this project doesn't have" §1 warns against.

### 3.4 API/library grounding (fetched live, not recalled)

**SEC EDGAR — access policy, re-verified this pass (the previous pass explicitly could not).** The
previous version of this document flagged that a re-fetch returned only SPA shell content and
deferred to `MASTER_PRD.md`'s inherited numbers. That flag is now **discharged**. `www.sec.gov`
returns HTTP 403 to a generic fetcher but serves normally to a request carrying a descriptive
`User-Agent` — which is itself the policy being verified.

- **Rate limit, verbatim** from [sec.gov/privacy.htm#security](https://www.sec.gov/privacy.htm#security)
  (the "Internet Security Policy" that
  [accessing-edgar-data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
  now redirects the reader to, rather than stating the number itself):
  > "Current guidelines limit users to a total of no more than 10 requests per second, regardless of
  > the number of machines used to submit requests. If a user or application submits more than 10
  > requests per second, further requests from the IP address(es) may be limited for a brief period.
  > **Once the rate of requests has dropped below the threshold for 10 minutes, the user may resume
  > accessing content on SEC.gov.**"
  The 10 req/s figure inherited from `MASTER_PRD.md` §5.1 is **confirmed**. The **10-minute
  cooldown is new information** and materially changes the ingestion backoff design — see §4.1.
- **User-Agent, verbatim** from
  [accessing-edgar-data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data):
  > "The SEC does not allow botnets or automated tools to crawl the site… Please declare your user
  > agent in request headers: **Sample Declared Bot Request Headers: `User-Agent: Sample Company
  > Name AdminContact@<sample company domain>.com` · `Accept-Encoding: gzip, deflate` · `Host:
  > www.sec.gov`**"
  Three headers, not one. `Accept-Encoding` and `Host` are part of the documented declared-bot
  shape and were not previously specified anywhere in this project's documents.

**SEC EDGAR — endpoint shapes, verified by live fetch on 2026-08-30 (CIK 0000320193, Apple Inc.):**

| Endpoint | Verified response shape |
|---|---|
| `https://www.sec.gov/files/company_tickers.json` | A JSON **object keyed by stringified integer index**, not an array: `{"0":{"cik_str":1045810,"ticker":"NVDA","title":"NVIDIA CORP"},"1":{"cik_str":320193,...},...}` — 10,391 entries. `cik_str` is an **`int`, despite the name** — the caller must zero-pad to 10 digits (`f"CIK{cik:010d}"`) for `data.sec.gov` paths. |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json` | `{cik, entityName, facts}` where `facts` has taxonomies `dei` and `us-gaap` (503 `us-gaap` tags for AAPL). `dei` carries **`EntityCommonStockSharesOutstanding`** and **`EntityPublicFloat`** — the shares-outstanding input the market-cap denominator needs, available from EDGAR itself. |
| `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{tag}.json` | `{cik, taxonomy, tag, label, description, entityName, units}`; `units` is keyed by unit (e.g. `"USD"`) → list of facts with keys `{start?, end, val, accn, fy, fp, form, filed, frame?}`. |
| `https://data.sec.gov/submissions/CIK{cik10}.json` | Carries `sic` (`"3571"`), `sicDescription` (`"Electronic Computers"`), `name`, `tickers`, `exchanges`, `entityType`, `fiscalYearEnd`. **This is the only source of SIC** — see §2's correction. |

**Tiingo — verified against vendor docs on 2026-08-30.** The previous pass could not re-verify these
and deferred to `MASTER_PRD.md`'s inherited figures. That flag is now discharged, and **one
inherited figure was wrong.**

- **Endpoint:** `https://api.tiingo.com/tiingo/daily/<ticker>/prices` with query params
  `startDate`, `endDate` (`YYYY-M-D`), `format`, `resampleFreq`, `token`
  ([documentation/end-of-day](https://www.tiingo.com/documentation/end-of-day)).
- **Response fields, confirmed:** `date, open, high, low, close, volume, adjOpen, adjHigh, adjLow,
  adjClose, adjVolume, divCash, splitFactor`. Both the total-return series (`adjClose`) and the raw
  per-event dividend cash (`divCash`) the purification engine needs come from one call, as designed.
- **Auth:** `Authorization: Token <YOUR_TOKEN>` header (note the literal `Token ` prefix and the
  space), or `?token=` query param; `Content-Type: application/json`
  ([documentation/general/connecting](https://www.tiingo.com/documentation/general/connecting)).
  **Use the header.** A token in a query string ends up in logs and in the replayable raw cache's
  filenames — an avoidable secret leak in a tool whose whole point is an auditable on-disk cache.
- **Free ("Starter") tier limits, from [tiingo.com/pricing](https://www.tiingo.com/pricing):**
  **500 unique symbols per month · 50 requests per hour · 1,000 requests per day · 1 GB bandwidth
  per month · licence "Internal Use Only."**
- **CORRECTION to `MASTER_PRD.md` §5.2.** The inherited figure "~50 unique symbols/hour" is
  **wrong**. It is **50 *requests* per hour**, and separately **500 unique *symbols* per month**.
  The backfill arithmetic survives — ~100 tickers, one ranged request each, is 100 requests ≈ 2
  hours at 50 req/hr, and 100 symbols sits well inside 500/month — but the *constraint that binds*
  is different, and an ingestion job written against the wrong constraint (e.g. batching many
  requests per symbol, which is free under a symbols/hour cap and fatal under a requests/hour cap)
  would stall. See §4.2.
- **Rate-limit mechanics** ([documentation/general/overview](https://www.tiingo.com/documentation/general/overview)):
  limits are enforced on hourly requests (reset hourly), daily requests (reset midnight EST), and
  monthly bandwidth (reset 1st of month, midnight EST). Verbatim: *"We do not rate limit to minute
  or second, so you are free to make your requests as you desire."* **Consequence:** unlike EDGAR,
  Tiingo needs **no inter-request spacing** — it needs a **budget counter** (requests this hour,
  this day) that refuses to issue request 51 in an hour. These are different mechanisms and the two
  ingestion jobs must not share one rate-limiter implementation.
- **Licence caveat, confirmed:** "Internal Use Only" — personal use, no display or sharing with
  another person or organisation. Fine for a private sandbox; it constrains any future sharing of
  raw cached data (derived results are a separate question). Flagged so it cannot ambush.

**DuckDB Python client (1.5.5)** — [duckdb.org/docs/current/clients/python/reference](https://duckdb.org/docs/current/clients/python/reference/):

- `duckdb.connect(database=..., read_only=..., config={...})` — `:memory:` for in-memory, a path for
  a persistent on-disk file; `config` takes a dict of DuckDB settings
  ([connect/overview](https://duckdb.org/docs/current/connect/overview)).
- `con.sql(query, *, alias: str = '', params: object = None) -> DuckDBPyRelation`
- `con.execute(query, parameters: object = None) -> DuckDBPyConnection`
- `con.read_parquet(file_glob: str | Sequence[str], binary_as_string: bool = False, *, file_row_number=False, filename=False, hive_partitioning=False, union_by_name=False, compression=None) -> DuckDBPyRelation`
- `con.register(view_name: str, python_object: object) -> DuckDBPyConnection`
- `con.to_arrow_table(batch_size: SupportsInt = 1_000_000) -> pyarrow.lib.Table`
- `con.fetch_arrow_table(rows_per_batch: SupportsInt = 1_000_000) -> pyarrow.lib.Table`
- `con.arrow(rows_per_batch=...) -> pyarrow.lib.RecordBatchReader` (alias of `to_arrow_reader()`)

**CORRECTED HALLUCINATED SYNTAX.** The previous version of this document stated
`duckdb.to_arrow_table(batch_size=..., connection=...)` as a **module-level** function taking a
`connection=` keyword. **No such module-level function is documented, and there is no `connection=`
parameter.** `to_arrow_table` is a **method on `DuckDBPyConnection`** taking only `batch_size`. An
execution agent that copied the old line would have written code that does not exist. This is
exactly the failure mode §2's "do not hallucinate syntax" rule exists to catch, and it was present
in this project's own canonical document. Logged in the changelog.

**DuckDB concurrency, verified** ([connect/concurrency](https://duckdb.org/docs/current/connect/concurrency)):
DuckDB permits **only one process to write to a database file at a time**; multiple processes may
read only if no process holds it read-write; access is coordinated with **file locks**. This
converts §4.5's "should never occur by design" from an assumption into a
mechanically-enforced-by-the-engine fact: a second concurrent writer will fail to acquire the lock
rather than corrupt data. The guard is still required (fail loudly, do not retry-loop), but the
corruption risk is bounded by the engine.

**Pydantic v2 (2.13.5)** — [pydantic.dev/docs/validation/latest/api/pydantic/config](https://pydantic.dev/docs/validation/latest/api/pydantic/config/):

- `extra` **defaults to `'ignore'`**; allowed values `'ignore' | 'forbid' | 'allow'`. Doc text:
  *"Whether to ignore, allow, or forbid extra data during model initialization. Defaults to
  `'ignore'`."* → the project-wide `extra="forbid"` is an **override of a permissive default**, and
  omitting it anywhere silently restores typo-swallowing. This is why it belongs on a shared base
  class, not repeated per model.
- `frozen` defaults to `False`; when `True`, blocks `__setattr__` and generates `__hash__()`.
- `validate_default` defaults to `False`; when `True`, defaults are validated like supplied values.

```python
from pydantic import BaseModel, ConfigDict

class Invariants(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_yield: float = 0.0
```

**Union-mode finding that changes a Phase 1 schema decision.** Pydantic's default union mode is
`union_mode='smart'`, and the docs state: *"Pydantic attempts to select the best match for the input
from the union members. **The exact algorithm may change between Pydantic minor releases** to allow
for improvements in both performance and accuracy"*
([concepts/unions](https://pydantic.dev/docs/validation/latest/concepts/unions/)). The docs do **not**
specify how smart mode resolves `bool` vs `int` (where `bool` is a subclass of `int`) or `int` vs
`float`. The pre-modernization `PHASE_1_SPEC.md` typed the honesty surface's central field as
`FiqhParam.value: bool | float | str` — i.e. it made **the fiqh judgment-call register depend on
explicitly-unspecified, minor-release-mutable behaviour.** For the one module whose entire purpose
is that nothing is silently decided, that is the wrong dependency. **Enhancement applied:**
`FiqhParam` becomes a **generic** model, `FiqhParam[T]`, so every register entry declares its exact
type and no union is resolved at all. Pydantic v2 generics are documented
([concepts/models](https://pydantic.dev/docs/validation/latest/concepts/models/)): inherit from
`BaseModel` and `typing.Generic` in that order. See `PHASE_1_SPEC.md` §3.2.

### 3.5 Literature sweep — scope, method, and null results

**Method:** the dedicated arXiv/paper-search MCP tools were attempted first and **both failed** in
this environment (`arxiv-mcp`: `SSL: CERTIFICATE_VERIFY_FAILED`; `paper-search-mcp`: proxy
`RemoteDisconnected`). Direct `curl` to `export.arxiv.org` also failed TLS. Per the degradation
rule, the sweep fell back to the arXiv Atom API and `arxiv.org/abs/*` over the available web-fetch
path, plus native web search. Queries run: `abs:"Shariah" OR abs:"Sharia" OR abs:"Islamic finance"`
sorted by submission date (50 results, full history); `abs:"look-ahead bias" OR abs:"point-in-time"
AND abs:"backtest"` sorted by submission date (30 results); `q-fin.PM/recent`; plus web searches for
AAOIFI SS21 revisions and 2026 Shariah-screening work.

**Found and used:** arXiv 2512.22858v2 (§3.1), 2608.12634 (§3.1), 2607.04958 (§3.3).

**Found and deliberately not used:** the look-ahead-bias literature of 2025–2026 is overwhelmingly
about *look-ahead leakage in LLMs* — 2601.13770 (Look-Ahead-Bench), 2512.06607, 2502.21206
(chronologically-consistent LLMs), 2605.24564, 2603.26797 (memorisation-contaminated signals),
2607.11889 (point-in-time language models). **None of it applies to Mizan**, because Mizan has no
LLM anywhere. Listing it would be padding. It is named here only to record that the sweep saw it
and rejected it, so a later reviewer does not mistake its absence for a gap.

**One LLM paper is relevant — as corroboration of the boundary, not as a component.** Elbadry et
al., *"SAHM: A Benchmark for Arabic Financial and Shari'ah-Compliant Reasoning,"*
[arXiv:2604.19098](https://arxiv.org/abs/2604.19098) (2026-04-21; cs.CL/AI/LG): 14,380
expert-verified instances across seven tasks including **AAOIFI standards QA** and fatwa-based
QA/MCQ. Evaluating 20 LLMs, it finds *"Arabic fluency does not imply financial reasoning: models
achieving 91% on recognition tasks drop sharply on generation, and event-cause reasoning exposes the
widest performance gap (1.89-9.84/10)."* A 2026 purpose-built benchmark measuring frontier models
directly on AAOIFI-standards reasoning finds wide, task-dependent, unreliable performance. That is
independent, current, empirical support for `MASTER_PRD.md` §2's no-LLM-in-compliance invariant and
`baby_prd.md` scope edge #5's "permanent, not a for-now." The invariant is not conservatism; it is
the correct read of the measured state of the art. Cited in §5.

**Null results, stated plainly:** no paper was found proposing a superior deterministic
business-activity classification method for a ~100-ticker hand-verifiable universe; none proposing a
settled formula for forced-divestment purification attribution (Fork C remains genuinely
underdetermined, as `MASTER_PRD.md` §8 says); and no AAOIFI SS21 revision or exposure draft touching
stock screening was found for 2025–2026. **No relevant new literature found** in those three areas.
Null evidence is evidence: Fork C stays a flagged parameter precisely because the literature does
not settle it.

---

## 4. Failure-Mode Analysis (expanded from `MASTER_PRD.md` §13)

Per layer. **HALT-for-human** = the pipeline stops and surfaces the exception; nothing auto-passes.
**Auto-retryable** = transient, bounded backoff, no human needed unless retries exhaust.

### 4.1 Ingestion (EDGAR)
| Failure | Detection | Prevention/Handling | Category |
|---|---|---|---|
| 429 / rate-limit block | HTTP 429, or HTTP 403 on a request with no/generic `User-Agent` | **≥0.12 s minimum spacing** between requests (≤10 req/s, [sec.gov/privacy.htm#security](https://www.sec.gov/privacy.htm#security)); on a block, **wait ≥10 minutes at zero request rate before resuming**, per the verbatim policy — *not* an exponential backoff starting in milliseconds, which will re-trip the block. Respect `Retry-After` when present, but floor the wait at 600 s. | Auto-retryable |
| Missing/declared-bot-header rejection (403) | HTTP 403 on an otherwise-valid URL | Send all three documented headers: `User-Agent: <app name> <contact email>`, `Accept-Encoding: gzip, deflate`, `Host: www.sec.gov` (or `data.sec.gov`). A 403 on a well-formed request means the header contract broke — do **not** retry-loop into a longer block. | **HALT-for-human** |
| Missing/incomplete `companyfacts` for a CIK | Empty or partial XBRL fact set | Mark ticker `unanalyzed`, never silently treat as pass | **HALT-for-human** |
| **Missing `submissions` record → no SIC** (NEW) | `submissions` fetch 404s, or returns no `sic` key | SIC is a *separate endpoint* (§2, §3.4). A ticker with fundamentals but no SIC must be `unanalyzed`, not "screened on the hand-verified map alone" — the map and SIC are a cross-check pair (§4.4), and losing one silently removes the backstop. | **HALT-for-human** |
| CIK resolution mismatch (ticker→CIK drift, e.g. post-merger) | `company_tickers.json` lookup returns wrong/stale CIK | Cross-check the resolved CIK's `submissions.name` against `company_tickers.json`'s `title` before ingest; flag mismatch. Note `cik_str` is an **int** — zero-pad to 10 (`f"CIK{cik:010d}"`); an unpadded CIK 404s rather than returning wrong data, which is the safe failure. | **HALT-for-human** |
| Malformed/undocumented XBRL tag drift (SEC changes a concept name) | Schema validation on ingest (Pydantic model rejects unknown shape) | `extra="forbid"` on the normalization model surfaces this immediately as a `ValidationError`, not a silent null | **HALT-for-human** |

### 4.2 Ingestion (Tiingo)
| Failure | Detection | Prevention/Handling | Category |
|---|---|---|---|
| **Hourly/daily request-budget exhaustion** (CORRECTED) | HTTP 429, or the job's own budget counter | The binding limit is **50 requests/hour and 1,000/day** — *not* 50 symbols/hour ([tiingo.com/pricing](https://www.tiingo.com/pricing)). Tiingo explicitly does **not** rate-limit per second, so no inter-request spacing is needed; instead the job maintains an explicit **hourly and daily request budget** and blocks before issuing an over-budget request. One ranged request per ticker keeps ~100 tickers at ~100 requests ≈ 2 h. **Do not** implement a per-symbol multi-request pattern. | Auto-retryable (sleep to the next hour boundary) |
| Monthly unique-symbol cap (500) or bandwidth cap (1 GB) exceeded | 429 with no hourly/daily budget consumed | Universe is ~100 tickers — far inside 500/month. Track distinct symbols requested per calendar month and refuse silently-expanding universes. | **HALT-for-human** (indicates universe drift, not transient load) |
| Adjusted-close / raw-close conflation | Column-contract check on ingest | Explicit typed columns (`adj_close`, `raw_close`) — never a single ambiguous `close` field. Tiingo returns both (`close` and `adjClose`); the normalizer must map them to distinctly-named typed columns and never allow a caller to pick "the close." | **HALT-for-human** (schema-level, caught at normalize) |
| Missing `divCash` on a known ex-dividend date | Cross-check against a second corporate-actions signal (a `splitFactor` discontinuity with no matching `divCash`) | Mark the dividend gap explicitly; purification engine must never silently treat missing `divCash` as zero | **HALT-for-human** |
| **API token leaked into the on-disk raw cache** (NEW) | Grep the raw cache directory and any cached request URL for the token value | Send the token as `Authorization: Token <token>` **header**, never as `?token=`; the cache key must be derived from `(ticker, startDate, endDate)`, never from the full URL. | **HALT-for-human** |

### 4.3 Normalization
| Failure | Detection | Prevention | Category |
|---|---|---|---|
| Silent type coercion (an XBRL fact reported in different unit scales across filings) | Unit-field cross-check on load — `companyconcept.units` is keyed by unit string (`"USD"`, `"shares"`, `"USD/shares"`) | Normalize explicitly against the XBRL `units` key; reject rather than guess a scale | **HALT-for-human** |
| Duplicate/overlapping filing periods loaded twice into DuckDB | Primary-key constraint on `(cik, taxonomy, tag, unit, start, end, accn)` — note `accn` is required for uniqueness, since the same period is legitimately re-reported across filings | DuckDB schema enforces uniqueness; violation raises, not upserts silently | **HALT-for-human** |
| **pandas 3.0 chained assignment silently no-ops** (NEW) | Copy-on-Write is now the only behaviour; `df[col][row] = v` no longer raises `SettingWithCopyWarning` — it does nothing | Ban chained assignment in review; use `.loc[]`. `ruff` rules covering pandas chained assignment should be enabled where available. ([pandas 3.0 whatsnew](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html)) | **HALT-for-human** (review gate) |
| **Datetime resolution mismatch across sources** (NEW) | pandas 3.0 infers `datetime64[us]` from strings, not `[ns]`; EDGAR `filed` and Tiingo `date` are both ISO strings from different pipelines | Convert both to `datetime.date` in Python at the normalize boundary and store as DuckDB `DATE`; never compare pandas datetimes across the two legs | **HALT-for-human** |

### 4.4 Screening
| Failure | Detection | Prevention | Category |
|---|---|---|---|
| **Wrong compliance verdict (WORST case, per `MASTER_PRD.md` §13)** | Unit tests against hand-verified reference cases; reason trace inspected per verdict | No LLM in `screening/` (grep-able invariant, §5); deterministic ratio math only. Corroborated by arXiv:2604.19098's measurement of frontier-model unreliability on AAOIFI-standards reasoning (§3.5). | **HALT-for-human**, always |
| Look-ahead beyond the flagged Fork-1 simplification | `as_of_date` filter test — assert no fact with `filed > as_of_date` reaches the screen | `screen()` hard-filters by date. **NEW static check (§3.3):** every reference to the `filed` field anywhere in `mizan/` outside `screen()`'s own body must sit inside a function whose signature takes `as_of_date`. This is the decidable, value-independent temporal-non-interference check. | **HALT-for-human** |
| SIC-code misclassification (compliant-coded conglomerate with a buried non-compliant division) | Hand-verified activity map cross-check against the SIC first-pass, per ticker in the curated ~100-universe | SIC is explicitly first-pass only (`MASTER_PRD.md` §6.1, and the primary source in §3.1(a) enumerates *activities*, not SIC codes) — the hand-verified map is the correctness backstop, not SIC alone | **HALT-for-human** on any SIC/map disagreement |
| **Tier 0.5 / Tier 1 silently promoted into the hardcoded core** (NEW) | Any adult-content or weapons/defence rule that is not gated on register #6; any media/hotels rule not gated on #7 | Primary source (§3.1(a)) shows AAOIFI enumerates neither. A build agent "helpfully" hardcoding an index-provider list would silently assert as settled law what the primary source leaves to interpretation — the project's #1 stated failure mode. | **HALT-for-human** |
| Denominator/threshold config drift (a `fiqh_params.py` edit silently changes verdicts) | Diff the verdict set before/after any config change during development | Every parameter change is visible in `config/fiqh_params.py` diffs, never a runtime-computed default | **HALT-for-human** (review gate, not runtime) |
| **A `fiqh_params` source string overstates what the primary source says** (NEW) | Review of every `source=` string against §3.1 | Register #1/#2 must state that AAOIFI's denominator basis and averaging window are **not stated in the public methodology** (§3.1(d)); register #5 must state the **"Total Income" vs "total revenue"** ambiguity (§3.1(b), Q2). A source string implying settledness is the honesty surface lying. | **HALT-for-human** |

### 4.5 Storage (DuckDB)
| Failure | Detection | Prevention | Category |
|---|---|---|---|
| Schema drift between raw cache and DuckDB typed tables | `mypy --strict` + Pydantic model validation at the normalize→DuckDB boundary | Typed load functions reject shape mismatches (`extra="forbid"`) | **HALT-for-human** |
| Concurrent-write conflict | DuckDB itself permits **one writer per file** and coordinates with **file locks** ([concurrency docs](https://duckdb.org/docs/current/connect/concurrency)) — a second writer fails to acquire the lock | Enforce single-process job execution. On a lock failure, **fail loudly and stop**; never retry-loop (a retry loop against a lock held by a stuck job is an infinite hang, not a recovery). Corruption risk is bounded by the engine; the guard exists to make the operator error visible. | **HALT-for-human** |

### 4.6 Backtest engine
| Failure | Detection | Prevention | Category |
|---|---|---|---|
| `CASH_YIELD != 0.0` at runtime | Boot validator asserts the invariant before any simulation starts | Fail-fast boot check (`MASTER_PRD.md` §9.5) — boot refuses to proceed | **HALT-for-human**, immediate |
| A strategy attempts to hold/select a Non-compliant-verdict ticker | Strategy interface only receives the screened/compliant subset; assert on any out-of-universe selection | Strategy interface is constructed to make this structurally impossible, not just checked | **HALT-for-human** if the assertion ever fires (indicates an interface bug) |
| Compliance-flip missed at a rebalance boundary (state machine skips a quarter) | Assert every HELD(compliant) position was re-screened at every rebalance date | `compliance_state.py` re-screens every holding every rebalance, no opportunistic skipping. Corroborated as necessary (not defensive) by arXiv:2608.12634's finding that boundary proximity predicts next-period transitions (§3.1). | **HALT-for-human** |
| Grace-period misconfiguration silently changes divestment timing | Config-diff review, same as §4.4 threshold drift | Flagged parameter, not a hidden default (register #8) | **HALT-for-human** (review gate) |
| **Rebalance cadence shortened below quarterly** (NEW — values boundary, §1.1) | Any code path or config that rebalances more often than quarterly | The cadence is not a parameter in the fiqh register and must not become one. A request to shorten it crosses the deferred HFT/daily-profit-seeking edge and is escalated to the human, never absorbed. | **HALT-for-human** (escalation, not a bug) |

### 4.7 Purification
| Failure | Detection | Prevention | Category |
|---|---|---|---|
| **Purification undercount** (missed dividend, or wrong period's ratio applied) | Reconcile every `divCash` event against the purification ledger; the ratio must be pinned to the screen *active at the dividend date*, not the current screen | Explicit per-holding-per-period reconciliation job; the ratio lookup is date-indexed, not "most recent" | **HALT-for-human** |
| Fork-C attribution window computed against the wrong flip/divest dates | Assert `flip_date <= divest_date` and that both dates come from `compliance_state.py`'s own event log, not re-derived | Single source of truth for flip/divest timestamps | **HALT-for-human** |
| Purification silently netted into NAV (violates AAOIFI P&L-exclusion) | Reporter-level assertion: `net_of_purification_return` and `gross_return` must both be present and distinct in every report | Side-ledger accounting (Fork B) is structural, not a report-formatting choice — and is now **primary-source-verbatim** backed (§3.2: *"cannot be included in the investors P&L accounts"*), not a design preference | **HALT-for-human** |

### 4.8 Reporting
| Failure | Detection | Prevention | Category |
|---|---|---|---|
| A result renders without its caveat set | The render function requires `active_caveats` as a non-optional argument | Type-level enforcement — there is no render call signature that omits caveats | **HALT-for-human** (should be a type error, caught before runtime) |
| Survivorship/look-ahead caveats present in code but missing from the rendered output | Snapshot-test the static HTML against an expected caveat-string checklist | Test asserts caveat text appears verbatim in every generated report (`baby_prd.md` AC #4) | **HALT-for-human** |
| **Gross and net-of-purification returns not both shown, or equal when the ledger is nonzero** | `baby_prd.md` AC #5 | Two distinct, separately-labelled figures; assert they differ whenever the purification ledger is nonzero | **HALT-for-human** |

**Categorization summary** (per `MASTER_PRD.md` §13): every compliance/correctness exception above
is **HALT-for-human** — nothing in `screening/`, `compliance_state.py`, or `purification.py` may
auto-recover by guessing. Only network-transient failures (§4.1 EDGAR 429 with its 10-minute
cooldown, §4.2 Tiingo budget exhaustion) are auto-retryable.

---

## 5. The Hard Boundary — grep-able checks for the downstream review agent

The permissibility boundary (`MASTER_PRD.md` §2, reconfirmed in `baby_prd.md` §Boundary) is the only
inviolable line in this project. **It outranks any newer or better method the research in §3
surfaces.** A modernization "enhancement" that touches any of the below is auto-rejected, not
applied. Code review for any PR touching `mizan/` should run the following and treat any hit as a
blocking finding, not a style note:

```bash
# 1. Non-zero cash yield, anywhere
grep -rnE "CASH_YIELD\s*=\s*[^0]" mizan/
grep -rniE "cash_yield\s*[:=]\s*(?!0\.0\b)" mizan/            # any non-0.0 assignment

# 2. Boundary-crossing position primitives anywhere in backtest/ or screening/
grep -rniE "\b(short|shorts|shorting|borrow|borrowed|borrowing|margin|leverage|leveraged|levered|option|options|future|futures|swap|swaps|derivative|derivatives)\b" mizan/backtest/ mizan/screening/

# 3. Negative position quantities (a short position in disguise)
grep -rnE "quantity\s*[:=]\s*-" mizan/backtest/
grep -rniE "(quantity|shares|position_size)\s*[:=]\s*-" mizan/backtest/

# 4. Any interest-accrual mechanic on cash
grep -rniE "interest|apr\b|yield_rate|risk_free|t_bill|tbill|money_market|sweep" mizan/backtest/

# 5. Any LLM/model client inside the deterministic core — imports AND names
grep -rniE "^\s*(import|from)\s+(openai|anthropic|google\.generativeai|google\.genai|vertexai|langchain|litellm|transformers|ollama)\b" mizan/
grep -rniE "openai|anthropic|gemini|vertex|langchain|\bllm\b|chat_completion|completion\(" mizan/screening/ mizan/backtest/compliance_state.py mizan/backtest/purification.py

# 6. LLM SDKs in the dependency manifest (they must never appear at all)
grep -niE "openai|anthropic|google-genai|google-generativeai|google-cloud-aiplatform|vertexai|langchain|litellm|yfinance" pyproject.toml

# 7. Temporal non-interference (§3.3): every `filed` reference outside screen() must be
#    inside a function taking as_of_date. Enumerate call sites, then check each by hand/AST.
grep -rn "filed" mizan/ --include=*.py

# 8. Values boundary (§1.1): rebalance cadence must not go sub-quarterly.
grep -rniE "\b(daily|intraday|hourly|minute|tick)[-_ ]?(rebalance|rebalancing|signal)\b|rebalance.{0,20}\b(daily|intraday)\b" mizan/
```

Checks 1–6 are **necessary but not sufficient** preconditions for merge. Checks 7–8 require a
one-line human/agent judgment per hit rather than a pure pass/fail. The sufficient conditions remain
the reason-trace requirement (`MASTER_PRD.md` §6.3) and the unit-tests-against-hand-verified-cases
requirement (§4.4).

**On check 5, restated because it is permanent:** there is no LLM in the V1 core anywhere —
ingestion, screening, the compliance-flip state machine, and purification are 100% deterministic
code, full stop. There is no LLM routing of any kind in this project; the "deterministic rules
engine anchors LLM output" invariant is satisfied vacuously and stricter — there is no LLM output to
anchor. `baby_prd.md` scope edge #5 classifies this as **permanent, not a "for now."** §3.5's SAHM
benchmark result is the current empirical justification, but the invariant does not depend on that
result and would not move if a future benchmark improved.

---

## 6. Execution Spec — dependency-ordered build sequence (7 phases)

**Phase count re-derived this pass, not inherited.** The pre-modernization `PHASE_1_SPEC.md` asserted
7 phases. Re-checking each candidate boundary against the sole criterion — *is this stage
independently buildable and testable before the next starts, and does nothing later reach back to
change its public shape except by additive extension?* — gives the same 7. The one seriously
considered alternative was splitting out an 8th CLI/orchestration phase; rejected, because each
phase ships its own entrypoint incrementally (Phase 1 registers `mizan-boot-check`; Phase 2 creates
`mizan/cli/` with `mizan ingest`; each later phase adds its verb), so an orchestration phase would
have nothing left to build. Recorded so the number is a decision, not a copy.

| # | Phase | Ships |
|---|---|---|
| **1** | **Foundation & Config** | `config/invariants.py`, `config/fiqh_params.py`, `config/boot_check.py`, shared base model, `Verdict`, `Caveat`/result envelope, `pyproject.toml`, `docs/modernization_log.md` |
| 2 | Ingestion & raw cache | `data/ingest_edgar.py` (companyfacts + companyconcept + **submissions**), `data/ingest_tiingo.py`, the two *different* rate limiters, replayable Parquet/JSON cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store | `data/normalize.py`, typed tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine | `screening/business_activity.py` (SIC first-pass + hand-verified map, tiered), `screening/financial_ratios.py` (30/30/5, two-axis denominator from config, **threshold margins in the reason trace**), `screening/verdict.py`, and the temporal-non-interference confinement check (§3.3) |
| 5 | Backtest engine + compliance-flip state machine | `backtest/clock.py`, `portfolio.py` (reads `CASH_YIELD`, never re-hardcodes), `strategy.py`, `compliance_state.py` |
| 6 | Purification | `backtest/purification.py` — side-ledger, `divCash`-driven, Fork A/B/C from `fiqh_params.py`, reconciliation test |
| 7 | Reporting | `reporting/report.py` — static HTML + matplotlib; caveats non-optional; gross vs net-of-purification as two distinct figures |

Nothing later reaches back to change an earlier stage's public shape except by **additive
extension** (new optional fields with defaults; never a renamed or removed symbol) without a phase
spec revision.

Definition of done for V1 = `MASTER_PRD.md` §11 items 1–5 and `baby_prd.md`'s five acceptance
criteria, achieved in the order above with no step skipped and no invariant/parameter split blurred.

---

## OPEN ARCHITECTURE QUESTIONS

Escalated for human decision. **None of these has been silently applied.** Each states the decision
at issue, the evidence, and the options.

### Q1 — AAOIFI's own ratio denominator and averaging window are not stated in any public source this pass could reach

- **Decision at issue:** register #1 (denominator basis = market cap) and #2 (smoothing = spot),
  and the rationale given for them in `MASTER_PRD.md` §6.2 ("AAOIFI specifies *no averaging window*
  — SS21 refers only to 'the last budget or verified financial position'").
- **Evidence:** the AAOIFI Secretary-General's own public methodology presentation states the
  *other* standards' denominators explicitly (slide 31: DJ = trailing 12-month moving average market
  cap; FTSE = total assets; S&P = market value of equity, 12-month average) and states AAOIFI's
  *thresholds* (slides 32–34: 30% / 30% / 5% of total income) — but never states AAOIFI's own
  denominator or averaging window. `[UNVERIFIED]`; searched: the full 37-slide PDF, `aaoifi.com`,
  and a 2025–2026 sweep for an SS21 revision or exposure draft (none found). The corroborating
  `amanahadvisors.com` explainer is now behind a bot challenge and could not be re-fetched.
  Source: [oicexchanges.org PDF](https://www.oicexchanges.org/files/1---shari-ah-screening-in-the-islamic-capital-markets-dr-hamed-merah-secretary-general-aaoifi.pdf).
- **Options:** (a) **keep the default and label the uncertainty honestly** — market-cap + spot stays
  the default, but register #1/#2's `source` strings say the AAOIFI denominator is not stated in
  public methodology and the default is an inference. *(This pass's recommendation; it changes only
  a source string, not a value or an architecture, and is specified in `PHASE_1_SPEC.md` §3.2.)*
  (b) obtain the paywalled SS21 text and resolve it factually. (c) change the default to something
  else — **not recommended, no evidential basis.**
- **Why it is escalated rather than just applied:** the *value* is unchanged and the *architecture*
  is unchanged, so (a) is applied as a documentation fix. What needs the human is the standing
  question of whether to buy SS21 to close this permanently. Flagged, not resolved.

### Q2 — "Total Income" vs "total revenue" as the non-permissible-income denominator (register #5)

- **Decision at issue:** `MASTER_PRD.md` §6.2 item 3: "Non-permissible income ÷ **total revenue** <
  5%."
- **Evidence:** the primary source says, verbatim, *"Non Halal Income Should not Exceed 5% of
  **Total Income**"* (slide 32). Under US GAAP, "total revenue" and "total income" are different
  line items, and the gap is not negligible for firms with material non-operating income —
  precisely the firms most likely to sit near the 5% boundary.
- **Options:** (a) default to **total revenue** (`us-gaap:Revenues` /
  `RevenueFromContractWithCustomerExcludingAssessedTax`) and add the denominator choice as a
  **12th register entry**, flagged `pending scholarly verification` with this ambiguity stated in
  its source string. (b) default to a total-income line and flag the same way. (c) leave it
  hardcoded to revenue with no flag — **rejected**: that is a silent fiqh judgment call dressed as
  settled law, which is `MASTER_PRD.md` §0's stated worst failure.
- **Why it is escalated:** `baby_prd.md` AC #2 requires a third party to count the register fields
  and confirm **1:1 coverage against `MASTER_PRD.md` §10's 11 rows**. Adding a 12th entry is
  therefore a *specified, testable* change to a locked acceptance criterion and is not this pass's
  to make. **Phase 1 ships 11 fields** and the ambiguity is recorded in register #5's `source`
  string; if the human approves (a) or (b), `MASTER_PRD.md` §10, `baby_prd.md` AC #2, and
  `PHASE_1_SPEC.md` §3.2/§8 all move together to 12.

### Q3 — SS21 clause 3/2 permits dealing in shares for price differences, which bears on the deferred HFT scope edge

- **Decision at issue:** `baby_prd.md` scope edge #2 — HFT/daily-profit-seeking trading is deferred
  because *the values position is not yet resolved by the education completed so far.*
- **Evidence, verbatim** from the same primary source, slide 30 (SS21 §3/2):
  > "It is permissible to buy and sell shares of corporations, on a spot or deferred basis in which
  > delay is permissible, if the activity of the corporation is permissible irrespective of its
  > being an investment (that is, the share is acquired with the aim of profiting from it) **or
  > dealing in it (that is, with the intention of benefiting from the difference in prices)**."
- **What this does and does not mean:** it is evidence that AAOIFI SS21 does not, on its face,
  distinguish holding-for-investment from trading-for-price-difference as a permissibility matter,
  for a share whose issuer passes the screens. It says **nothing** about frequency, and nothing
  about the several other questions HFT raises (gharar in very-short-horizon speculation, the
  settlement-cycle question, whether "spot" survives at intraday horizons).
- **Options:** (a) **leave the edge deferred exactly as confirmed** — record this citation against
  it for the future scholarly review, change nothing in scope, cadence, or code. *(This pass's
  action, and the recommendation.)* (b) reopen the values question with a scholar, informed by this
  clause. (c) un-defer the edge — **explicitly not done, and not recommended by this pass.**
- **Why it is escalated rather than applied:** the deferral is the human's values position, and
  §1.1 makes it an escalation trigger by design. Overruling a user's stated values position on the
  strength of one clause is precisely the failure this step exists to prevent — it is exactly the
  "modernising details vs. overruling locked decisions" line. The edge stays deferred. The quarterly
  cadence stays. This entry exists so the evidence is on the record, not so it can be acted on.

---

## MODERNIZATION CHANGELOG

Pass date **2026-08-30**. Capabilities used: native web search; direct HTTP fetch (including
`curl` with a declared SEC `User-Agent`, which was required to reach `sec.gov` at all); local PDF
text extraction. Capabilities **attempted and skipped**: `arxiv-mcp` (SSL certificate verification
failure) and `paper-search-mcp` (proxy connection closed) — degraded to the arXiv Atom API over the
web-fetch path plus native search, per the §2 degradation rule. See §3.5.

### A. Dependency versions — 8 changes, 1 confirmation

| Item | Was | Now | Source |
|---|---|---|---|
| `pydantic` | 2.13.4 | **2.13.5** | [PyPI](https://pypi.org/project/pydantic/) |
| `duckdb` | 1.5.4 | **1.5.5** | [PyPI](https://pypi.org/project/duckdb/) |
| `pyarrow` | 24.0.0 | **25.0.1** | [PyPI](https://pypi.org/project/pyarrow/) |
| `pandas` | "latest 2.x" (unpinned) | **3.0.5** (exact) | [PyPI](https://pypi.org/project/pandas/) · [whatsnew 3.0](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) |
| `matplotlib` | "latest 3.x" (unpinned) | **3.11.1** (exact) | [PyPI](https://pypi.org/project/matplotlib/) |
| `mypy` | "latest" / 2.1.0 | **2.3.1** | [PyPI](https://pypi.org/project/mypy/) · [mypy 2.0 notes](https://mypy-lang.blogspot.com/2026/05/mypy-20-relased.html) |
| `ruff` | 0.15.20 | **0.16.5** | [GitHub releases](https://github.com/astral-sh/ruff/releases) |
| `pytest` | ">=8.3,<9" | **9.1.1** (exact) | [PyPI](https://pypi.org/project/pytest/) |
| `httpx` | "latest 0.27+" / 0.28.1 | **0.28.1 — confirmed still latest stable**; `1.0.dev5` exists and is deliberately **not** pinned | [PyPI](https://pypi.org/project/httpx/) |
| Python | ">=3.11" | **">=3.11,<3.15"**, build against 3.14.x | [python.org 3.14.7](https://www.python.org/downloads/release/python-3147/) |

All floating ranges replaced with exact pins (reproducibility). Behavioural consequences of the
pandas 3.0 and mypy 2.0 majors documented in §2.1 and §4.3.

### B. Corrected hallucinated or wrong API syntax — 2 corrections

1. **`duckdb.to_arrow_table(batch_size=..., connection=...)` did not exist.** The previous
   ULTIMATE_PRD §3.4 stated it as a module-level function with a `connection=` keyword. It is a
   **method on `DuckDBPyConnection`**: `con.to_arrow_table(batch_size: SupportsInt = 1_000_000)`.
   No `connection=` parameter exists. Corrected in §3.4 with the full verified signature set.
   Source: [DuckDB Python reference](https://duckdb.org/docs/current/clients/python/reference/).
2. **SIC codes are not in `companyfacts`.** `MASTER_PRD.md` §5.1 called SIC a "bonus field" of the
   XBRL API. Verified live: `companyfacts` returns `{cik, entityName, facts:{dei, us-gaap}}` only.
   `sic`/`sicDescription` are in `https://data.sec.gov/submissions/CIK##########.json`. This adds a
   **third required EDGAR endpoint** to Phase 2 and a new failure mode (§4.1). Corrected in §2,
   §3.4, §4.1, §6.

### C. Corrected wrong external facts — 1 correction, 2 discharged flags

1. **Tiingo free-tier limit was wrong.** `MASTER_PRD.md` §5.2's "~50 unique symbols/hour" is
   actually **50 requests/hour**, with a separate **500 unique symbols/month** cap (plus 1,000
   requests/day, 1 GB/month, "Internal Use Only"). The binding constraint is different in kind, and
   an ingestion job written against the wrong one would stall. Corrected in §3.4, §4.2.
   Source: [tiingo.com/pricing](https://www.tiingo.com/pricing).
2. **Discharged: EDGAR rate limit and User-Agent policy.** The previous pass could not get past an
   SPA shell and left a "Flag for Phase 1 ingestion-job authors: re-confirm these before hardcoding
   backoff constants." **Confirmed:** 10 req/s, verbatim from
   [sec.gov/privacy.htm#security](https://www.sec.gov/privacy.htm#security) — and the policy also
   specifies a **10-minute** sub-threshold cooldown before access resumes, which was not previously
   known and which changes the backoff design (§4.1). The declared-bot header set is **three**
   headers (`User-Agent`, `Accept-Encoding`, `Host`), not one (§3.4). The flag is removed.
3. **Discharged: Tiingo endpoint and field contract.** `GET https://api.tiingo.com/tiingo/daily/<ticker>/prices`;
   fields `date, open, high, low, close, volume, adjOpen, adjHigh, adjLow, adjClose, adjVolume,
   divCash, splitFactor`; auth via `Authorization: Token <token>` header. Rate limiting is
   hourly/daily/monthly with **no per-second limit** — so Tiingo needs a *budget counter*, not
   *spacing*, the opposite of EDGAR. §3.4, §4.2.

### D. Upgraded from asserted to primary-source-verbatim — 4 upgrades

1. **AAOIFI's 8-item enumerated industry screen** now quoted verbatim (§3.1(a)), independently
   confirming that "non-halal food" is AAOIFI-explicit and that **adult content and weapons/defence
   are not** — validating `MASTER_PRD.md` §6.1's Tier 0.5 demotion as the primary-source-faithful
   reading rather than a judgment call.
2. **30/30/5 confirmed** against slides 32–34 (§3.1(b)), including AAOIFI's tighter-than-33% posture.
3. **Pure/Mixed/Non-compliant verdict definitions** now quoted verbatim from slide 21 (§3.1(c)) —
   `MASTER_PRD.md` §6.3's enum is a direct transcription.
4. **Purification's side-ledger requirement** now quoted verbatim from slide 25 (§3.2): *"non Halal
   Income will have to be donated to Charity and cannot be included in the investors P&L accounts."*
   Fork B is upgraded from a design choice to a primary-source-backed correctness requirement.
5. **EDGAR endpoint shapes** verified by live fetch, not inferred (§3.4), including the `filed`
   field that makes V2 true-PIT a slicing change, and `dei:EntityCommonStockSharesOutstanding` /
   `EntityPublicFloat` for the market-cap denominator.

### E. Demoted from asserted to `[UNVERIFIED]` — 1 demotion

**AAOIFI's own denominator basis and averaging window** (§3.1(d), Q1). Previously asserted with a
quoted SS21 fragment ("the last budget or verified financial position"); this pass could not verify
that fragment or the no-averaging claim against any reachable public source. Searched: the full
37-slide primary PDF, `aaoifi.com`, and a 2025–2026 sweep for an SS21 revision (none found). The
`amanahadvisors.com` corroborator is now behind a Cloudflare bot challenge and is also
`[UNVERIFIED]` this pass. The **value is unchanged** (market-cap + spot remains the default); only
the honesty of the label changes.

### F. Literature — 3 new papers used, 1 version bump, and an explicit null

- **arXiv:2512.22858 → v2** (2026-03-11; the previous pass cited v1). New v2 finding recorded: CSCI
  shows **no reliable association with returns** — expectation-setting for Phase 7 (§3.1).
- **arXiv:2608.12634** (2026-08-12), *"The Price of Permission."* Its finding that boundary
  proximity ranks next-period screen transitions upgrades every-holding-every-rebalance re-screening
  from defensive to necessary, and motivates one **applied** enhancement: surface each ratio's
  **margin to its threshold** in the reason trace (already computed; currently discarded). Verdict
  output is unchanged. §3.1, §4.6, §6 Phase 4.
- **arXiv:2607.04958** (2026-07-06), *"Look-Ahead-Freedom as Temporal Non-Interference."* Validates
  the one-function look-ahead quarantine and supplies the framing plus a **decidable, linear-time
  static check** for the value-independent fragment Mizan's data path lives in. Two **applied**
  enhancements: (i) name the property in `screen()`'s docstring and the `Caveat` documentation so
  the V2 work item is a checkable property; (ii) make the confinement grep-able — every `filed`
  reference outside `screen()` must sit in a function taking `as_of_date`. **No dependency added.**
  §3.3, §4.4, §5 check 7.
- **arXiv:2604.19098** (SAHM, 2026-04-21) cited as **corroboration of the no-LLM invariant**: a
  purpose-built AAOIFI-standards reasoning benchmark measures frontier models as wide-variance and
  unreliable (1.89–9.84/10 on the hardest task). §3.5, §5.
- **Explicit null:** no paper found proposing a better deterministic business-activity classifier
  for a hand-verifiable ~100-ticker universe; none settling Fork C's divestment attribution formula;
  no AAOIFI SS21 revision or exposure draft 2025–2026. **No relevant new literature found** in those
  areas. The 2025–2026 look-ahead literature is almost entirely about LLM leakage and was
  deliberately excluded as inapplicable (§3.5) rather than cited for volume.

### G. Scope / posture changes incorporated from `baby_prd.md` + `.claude/loopr/context.md`

1. **NEW §1.1 — the values position is now explicit.** Baseline long-only/halal-screened/
   quarterly-rebalance is settled-permissible and buildable now; **HFT/daily-profit-seeking trading
   is a separately-named, deferred scope edge**, which the original MASTER_PRD/ULTIMATE_PRD never
   named. A request to shorten the rebalance cadence below quarterly is now defined as **crossing a
   values boundary, escalated to the human**, not a tuning knob (§1.1, §4.6, §5 check 8).
2. **No-LLM restated as permanent, not "for now"** (`baby_prd.md` edge #5) — §1, §5.
3. **`baby_prd.md`'s five acceptance criteria** folded into the V1 definition of done (§6) and into
   §4.8's reporting guards (gross vs net-of-purification must both appear and must differ when the
   ledger is nonzero).
4. **Commits stay neutral — no AI attribution, configured git user only**
   (`.claude/loopr/context.md` § Soft context, note 2; `MASTER_PRD.md` §9.5). Unchanged, restated
   here so the loop's commit markers do not drift. Note the repository is **not yet a git
   repository** — Phase 1 initialises it.

### H. Categories with no changes

- **Model strings / LLM SDK versions:** **none exist and none were added.** This project has no LLM
  component; there is nothing to pin. Stated explicitly so the empty section is not read as an
  oversight.
- **LLM routing configuration:** N/A — no routing of any kind (§5).
- **The permissibility boundary itself:** **unchanged.** No invariant was weakened, widened, or made
  configurable by this pass. §5's grep set was *tightened* (word-stem coverage for plurals and
  inflections, an import-specific LLM check, a dependency-manifest check, and two new judgment
  checks), never loosened.
- **Architecture:** **unchanged.** Deterministic batch pipeline, DuckDB, from-scratch event loop,
  three-state verdict, side-ledger purification, static HTML report — all as locked. Every §3
  enhancement sits on top of the architecture, none through it.

---

## Sources consulted for this synthesis

**Primary (fetched and read on 2026-08-30 by this pass):**
- AAOIFI SS21 public methodology — Dr. Hamed Merah, *"Shari'ah Screening Methodology,"* Oct 2017, 37 slides (full text extracted; slides 18, 21, 24, 25, 27, 30, 31, 32, 33, 34 quoted): https://www.oicexchanges.org/files/1---shari-ah-screening-in-the-islamic-capital-markets-dr-hamed-merah-secretary-general-aaoifi.pdf
- SEC Internet Security Policy (10 req/s + 10-minute cooldown, verbatim): https://www.sec.gov/privacy.htm#security
- SEC Accessing EDGAR Data (declared-bot header set, verbatim): https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- SEC EDGAR live endpoint shapes (CIK 0000320193): https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json · https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json · https://data.sec.gov/submissions/CIK0000320193.json · https://www.sec.gov/files/company_tickers.json
- Tiingo EOD endpoint + response fields: https://www.tiingo.com/documentation/end-of-day
- Tiingo auth header format: https://www.tiingo.com/documentation/general/connecting
- Tiingo rate-limit mechanics (hourly/daily/monthly, no per-second limit): https://www.tiingo.com/documentation/general/overview
- Tiingo Starter-tier limits + "Internal Use Only" licence: https://www.tiingo.com/pricing
- DuckDB Python client reference (1.5.x signatures): https://duckdb.org/docs/current/clients/python/reference/
- DuckDB concurrency (single writer, file locks): https://duckdb.org/docs/current/connect/concurrency
- Pydantic `ConfigDict` API (`extra` default `'ignore'`; `frozen`, `validate_default`): https://pydantic.dev/docs/validation/latest/api/pydantic/config/
- Pydantic unions (smart mode is default; algorithm may change between minor releases): https://pydantic.dev/docs/validation/latest/concepts/unions/
- Pydantic generic models: https://pydantic.dev/docs/validation/latest/concepts/models/
- pandas 3.0.0 release notes (CoW-only, `str` dtype, `datetime64[us]`, Python ≥3.11): https://pandas.pydata.org/docs/whatsnew/v3.0.0.html
- mypy 2.0 release announcement (default flag changes): https://mypy-lang.blogspot.com/2026/05/mypy-20-relased.html
- PyPI version pages: pydantic · duckdb · pyarrow · pandas · matplotlib · httpx · mypy · pytest (https://pypi.org/project/<name>/)
- ruff releases: https://github.com/astral-sh/ruff/releases
- Python 3.14.7: https://www.python.org/downloads/release/python-3147/

**Literature (verified this pass):**
- Qadi, Sharma & Medda, *"From Binary Screens to Continuous Compliance: A Shariah Screening Measure for Portfolio Design,"* arXiv:2512.22858 **v2 (2026-03-11)**: https://arxiv.org/abs/2512.22858
- Qadi, Sharma & Medda, *"The Price of Permission: Classification Uncertainty in Constrained Capital Markets,"* arXiv:2608.12634 (2026-08-12): https://arxiv.org/abs/2608.12634
- Fonseca, *"Look-Ahead-Freedom as Temporal Non-Interference: A Verifiable Correctness Property for Backtesting and Agentic Trading Pipelines,"* arXiv:2607.04958 (2026-07-06): https://arxiv.org/abs/2607.04958
- Elbadry et al., *"SAHM: A Benchmark for Arabic Financial and Shari'ah-Compliant Reasoning,"* arXiv:2604.19098 (2026-04-21): https://arxiv.org/abs/2604.19098

**`[UNVERIFIED]` this pass (attempted, not reachable):**
- AAOIFI 30% ratio explainer (Cloudflare bot challenge on re-fetch): https://amanahadvisors.com/making-sense-of-the-30-rule-in-islamic-finance/
- AAOIFI Shari'ah Standard No. 21 full text — paywalled; the definitive text remains unread. All
  AAOIFI thresholds in this project are **as-implemented from public methodology, pending scholarly
  verification.**
