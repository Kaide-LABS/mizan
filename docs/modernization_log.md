# Mizan — Modernization Log

Pinned external reality for this project. **No version number appears in this file without a
verification date and a source URL.** Every entry below was checked by direct fetch of the cited
page, not recalled.

Canonical consumer of this file: `pyproject.toml` (§2 of `PHASE_1_SPEC.md`). If the two disagree,
this file is the record of what was *verified* and `pyproject.toml` is the record of what is
*installed* — reconcile them and log the reconciliation here, never silently.

---

## 1. Verification passes

| Pass | Date | Performed by | Scope |
|---|---|---|---|
| 1 | 2026-07-02 | Step 7 synthesis (`ULTIMATE_PRD.md` v1) | Library versions only; SEC/Tiingo re-fetch failed (SPA shell), numbers inherited unverified |
| 2 | 2026-08-30 | Step 10 PRD modernization + Phase 1 blueprint | All library versions; SEC EDGAR policy + live endpoint shapes; Tiingo endpoint/limits/auth; DuckDB + Pydantic API signatures; AAOIFI primary-source methodology; 2024–2026 literature sweep |
| **3** | **2026-08-30** | **Phase 4 implementation** | **`SIC_TIER_MAP`'s SIC codes (live against SEC's own published code list + live EDGAR company-search per code); §6b's XBRL concept-tag allow-lists (live against real EDGAR `companyfacts` responses for six real CIKs)** |

Pass 2 corrected 2 wrong API facts, 1 wrong external limit, discharged 2 unverified flags from
pass 1, and demoted 1 previously-asserted claim to `[UNVERIFIED]`. See
`ULTIMATE_PRD.md` § MODERNIZATION CHANGELOG for the itemised list. Pass 3 (§6.3 below) confirmed 13
of 14 candidate XBRL tags live and found that `PHASE_4_SPEC.md` §4.1's own illustrative "7993
(gambling)" SIC code is not an SEC-assigned code at all.

---

## 2. Runtime

| Item | Pinned | Verified | Source |
|---|---|---|---|
| Python (declared floor/ceiling) | `>=3.11,<3.15` | 2026-08-30 | Floor set by `pandas` 3.0.5 and `matplotlib` 3.11.1 (both require `>=3.11`); ceiling set because no pinned dependency publishes `cp315` wheels |
| Python (build/test interpreter) | **3.14.4** | 2026-08-30 | `python --version` output on the Phase 1 build machine, verified 2026-08-30 (release page: https://www.python.org/downloads/release/python-3147/, 3.14.7, released 2026-08-05 — the build machine runs the earlier 3.14.4 patch, still within the declared `<3.15` range) |

Every runtime and dev dependency pinned below publishes `cp311`–`cp314` wheels, so any interpreter
in the declared range works. The local machine runs Python 3.14.4.

---

## 3. Runtime dependencies (exact pins)

Floating ranges are deliberately not used. This is a reproducibility-critical research tool: a
range that silently changes a numerical backtest result between two runs is a correctness failure,
not a convenience.

| Package | Pin | Released | Verified | Source |
|---|---|---|---|---|
| `pydantic` | `2.13.5` | 2026-08-28 | 2026-08-30 | https://pypi.org/project/pydantic/ |
| `duckdb` | `1.5.5` | 2026-07-22 | 2026-08-30 | https://pypi.org/project/duckdb/ |
| `pyarrow` | `25.0.1` | 2026-08-10 | 2026-08-30 | https://pypi.org/project/pyarrow/ |
| `pandas` | `3.0.5` | 2026-07-22 | 2026-08-30 | https://pypi.org/project/pandas/ |
| `matplotlib` | `3.11.1` | 2026-07-18 | 2026-08-30 | https://pypi.org/project/matplotlib/ |
| `httpx` | `0.28.1` | 2024-12-06 | 2026-08-30 | https://pypi.org/project/httpx/ |

**`httpx` note.** 0.28.1 is still the latest **stable** release as of 2026-08-30. A `1.0.dev5`
pre-release exists (2026-08-21). It is deliberately **not** pinned — a `.dev` build does not belong
in a tool whose output is meant to be reproducible and auditable. Re-check at the start of Phase 2
(the first phase that actually imports `httpx`); if 1.0 has gone stable by then, evaluate and log
the decision here rather than silently bumping.

**Phase 2 re-check performed, 2026-08-30 (same day — Phase 2 built immediately after Phase 1's
comprehension pass and the Step 10 blueprint, per this file's own action item above).** `pip index
versions httpx` against the live PyPI index confirms `0.28.1` is still the newest release; no
stable `1.0` release exists yet (the `1.0.dev5` pre-release noted above is unchanged and is not
surfaced by a stable-only index query). **Decision: keep the pin at `httpx==0.28.1`, unchanged.**
`httpx` is promoted from `[project.optional-dependencies].ingest` (removed, PHASE_2_SPEC.md §2.1)
to a core `[project.dependencies]` entry in this phase, since `mizan/data/ingest_edgar.py` and
`mizan/data/ingest_tiingo.py` are the first modules to actually import it — the version number
itself does not change.

**Phase 3 re-check performed, 2026-08-30 (same day, per this file's own §1 governing rule that a
same-calendar-date entry is not proof no time has passed — PHASE_3_SPEC.md §2.1's explicit action
item).** `pip index versions duckdb` and `pip index versions pyarrow` run live against the real
PyPI index from inside the project's `.venv` on the Phase 3 build machine:

```
$ .venv/Scripts/python -m pip index versions duckdb
duckdb (1.5.5)
Available versions: 1.5.5, 1.5.4, 1.5.3, ...

$ .venv/Scripts/python -m pip index versions pyarrow
pyarrow (25.0.1)
Available versions: 25.0.1, 25.0.0, 24.0.0, ...
```

**Decision: both pins are unchanged** — `duckdb==1.5.5` and `pyarrow==25.0.1` are still the newest
releases on PyPI as of this check. `duckdb` and `pyarrow` are promoted from
`[project.optional-dependencies].data` (PHASE_1_SPEC.md §2.1's forward declaration, carried
unimported through Phase 2) to core `[project.dependencies]` entries in Phase 3
(PHASE_3_SPEC.md §2.1), since `mizan/data/db.py` and `mizan/data/normalize.py` are the first
modules to actually import them — the version numbers themselves do not change. `pandas` remains
forward-declared and unused (PHASE_3_SPEC.md §2.2) pending whichever of Phase 5 or Phase 7 needs it
first.

**PRIMARY KEY constraint-violation behaviour, verified live 2026-08-30 (PHASE_3_SPEC.md §5's own
build-time verification item):** inserting two rows with an identical PRIMARY KEY and differing
non-key values via `duckdb.connect()` + `CREATE TABLE ... PRIMARY KEY (...)` + two `INSERT`
statements raises `duckdb.ConstraintException` ("Duplicate key ... violates primary key
constraint") on the second `INSERT` — confirmed against DuckDB 1.5.5's actual Python API in this
project's `.venv`, not assumed from Postgres/SQLite-familiar semantics. This is the backstop guard
G-N2/G-N3 rely on; the application-level pre-insert conflict check in
`mizan/data/normalize.py::_bulk_load` is the primary mechanism (PHASE_3_SPEC.md §6.2).

---

## 4. Development dependencies (exact pins)

| Package | Pin | Released | Verified | Source |
|---|---|---|---|---|
| `mypy` | `2.3.1` | 2026-08-15 | 2026-08-30 | https://pypi.org/project/mypy/ |
| `ruff` | `0.16.5` | 2026-08-27 | 2026-08-30 | https://github.com/astral-sh/ruff/releases |
| `pytest` | `9.1.1` | 2026-06-19 | 2026-08-30 | https://pypi.org/project/pytest/ |

---

## 5. Breaking-change notes carried by these pins

Recorded so a future build agent does not "fix" a new upstream default by loosening the project's
own gates.

### 5.1 `pandas` 3.0 is a major release
Source: https://pandas.pydata.org/docs/whatsnew/v3.0.0.html (verified 2026-08-30)

- **Copy-on-Write is the only behaviour.** Chained assignment (`df[col][row] = v`) no longer
  modifies the original — and `SettingWithCopyWarning` is **removed**, so it fails *silently*.
  Use `.loc[]`. This is a silent-correctness hazard of exactly the kind `MASTER_PRD.md` §13 says is
  the dangerous class for this project.
- **Default string dtype is `str`**, PyArrow-backed when PyArrow is installed (it is, `25.0.1`).
  Non-strings raise on setitem; the missing sentinel is always `NaN`.
- **`to_datetime` on strings infers `datetime64[us]`**, not `[ns]`. Normalise EDGAR `filed` and
  Tiingo `date` to `datetime.date` in Python at the normalize boundary; do not compare pandas
  datetimes across the two ingestion legs.
- **`pytz` is no longer a dependency** — timezone handling uses stdlib `zoneinfo`.
- Minimum Python raised to 3.11.
- **PyArrow is optional, not required**, in pandas 3.0 — but this project installs it regardless
  (DuckDB↔Arrow interchange and the Parquet raw cache), so the PyArrow-backed string path is the
  one this project actually gets.

### 5.2 `mypy` 2.0 is a major release
Source: https://mypy-lang.blogspot.com/2026/05/mypy-20-relased.html (verified 2026-08-30)

- `--local-partial-types` is now **default**.
- `--strict-bytes` is now **default** (per PEP 688): passing `bytearray`/`memoryview` where `bytes`
  is expected no longer type-checks.
- `--allow-redefinition` changed meaning; legacy behaviour is now `--allow-redefinition-old`.
- `--python-version 3.9` is a hard error; minimum target is 3.10.
- `--num-workers N` / `-nN` adds parallel checking.
- **`--strict` still exists and remains this project's gate.** Do not relax it to accommodate a new
  default; fix the code.

### 5.3 `pydantic` v2 defaults that this project overrides
Source: https://pydantic.dev/docs/validation/latest/api/pydantic/config/ (verified 2026-08-30)

| Setting | Pydantic default | Mizan value | Why |
|---|---|---|---|
| `extra` | `'ignore'` | **`'forbid'`** | The default silently swallows typos and config drift. Forbidding is what makes `invariants.py` / `fiqh_params.py` fail loudly. |
| `frozen` | `False` | **`True`** | Loaded config must not be mutated in place by any downstream module. |
| `validate_default` | `False` | **`True`** | Defaults are where every fiqh value actually lives in this project; an unvalidated default is an unchecked value. |

**Union-mode caveat.** Pydantic's default union mode is `union_mode='smart'`, and the docs state the
algorithm *"may change between Pydantic minor releases."* The docs do not specify `bool`-vs-`int`
resolution (`bool` is an `int` subclass). Mizan therefore **does not put a union on the honesty
surface**: `FiqhParam` is a generic model, `FiqhParam[T]`, so each register entry declares its exact
type. Source: https://pydantic.dev/docs/validation/latest/concepts/unions/ ·
https://pydantic.dev/docs/validation/latest/concepts/models/ (both verified 2026-08-30).

### 5.4 `duckdb` 1.5 Python API — corrected signatures
Source: https://duckdb.org/docs/current/clients/python/reference/ (verified 2026-08-30)

```
duckdb.connect(database=..., read_only=..., config={...})           -> DuckDBPyConnection
con.sql(query, *, alias: str = '', params: object = None)           -> DuckDBPyRelation
con.execute(query, parameters: object = None)                       -> DuckDBPyConnection
con.read_parquet(file_glob: str | Sequence[str], binary_as_string: bool = False, *,
                 file_row_number=False, filename=False, hive_partitioning=False,
                 union_by_name=False, compression=None)             -> DuckDBPyRelation
con.register(view_name: str, python_object: object)                 -> DuckDBPyConnection
con.to_arrow_table(batch_size: SupportsInt = 1_000_000)             -> pyarrow.lib.Table
con.fetch_arrow_table(rows_per_batch: SupportsInt = 1_000_000)      -> pyarrow.lib.Table
con.arrow(rows_per_batch=...)                                       -> pyarrow.lib.RecordBatchReader
```

**Correction logged:** the pre-modernization `ULTIMATE_PRD.md` §3.4 asserted a **module-level**
`duckdb.to_arrow_table(batch_size=..., connection=...)`. No such function is documented and there is
no `connection=` parameter. `to_arrow_table` is a **connection method** taking only `batch_size`.

**Concurrency:** DuckDB permits **one writer per database file**, coordinated by file locks; readers
are excluded while a writer holds it. Source: https://duckdb.org/docs/current/connect/concurrency
(verified 2026-08-30).

**Correction logged, Phase 3, verified live 2026-08-30:** the single-writer file lock above is
enforced by the OS, **across processes** — it is NOT triggered by a second `duckdb.connect()` call
against the same path from WITHIN the same process. DuckDB 1.5.5's Python API caches one underlying
database instance per file path per process: two `connect()` calls to the same path in one process
share that instance (confirmed empirically — a row inserted via the second connection is
immediately visible via the first, no exception). A real second OS process attempting to open the
same file while the first holds it open (non-read-only) *does* raise
(`_duckdb.IOException: ... The process cannot access the file because it is being used by another
process`), confirmed empirically via a subprocess test. PHASE_3_SPEC.md §8 AC10's own test
description ("a second connection attempt ... in the same process") assumed the former would
reproduce the latter; it does not. `tests/test_data_db.py` exercises the guard with a real second
process instead. This does not change `mizan/data/db.py`'s implementation (it already contains no
retry/catch around any DuckDB call) — only how the guard is verified.

---

## 6. External data-source contracts

### 6.1 SEC EDGAR

| Item | Verified value | Source |
|---|---|---|
| Rate limit | **10 requests/second**, per IP, regardless of machine count | https://www.sec.gov/privacy.htm#security |
| Block recovery | Access resumes once the request rate has stayed **below the threshold for 10 minutes** | same |
| Required headers | `User-Agent: <Company/App Name> <contact email>` · `Accept-Encoding: gzip, deflate` · `Host: www.sec.gov` (or `data.sec.gov`) | https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data |
| Behaviour without a declared UA | HTTP **403** (confirmed empirically 2026-08-30: a generic fetcher gets 403; the same URL with a declared UA returns 200) | empirical |
| API key | none required | same |

**Endpoint shapes, verified live 2026-08-30 against CIK `0000320193` (Apple Inc.):**

| Endpoint | Shape |
|---|---|
| `https://www.sec.gov/files/company_tickers.json` | JSON **object keyed by stringified index** (not an array): `{"0":{"cik_str":1045810,"ticker":"NVDA","title":"NVIDIA CORP"},...}`, 10,391 entries. `cik_str` is an **`int`** despite the name — zero-pad to 10 for `data.sec.gov` paths: `f"CIK{cik:010d}"`. |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json` | `{cik, entityName, facts}`; `facts` taxonomies are `dei` and `us-gaap` (503 `us-gaap` tags for AAPL). `dei` includes `EntityCommonStockSharesOutstanding` and `EntityPublicFloat`. |
| `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{tag}.json` | `{cik, taxonomy, tag, label, description, entityName, units}`; `units` keyed by unit string (`"USD"`, `"shares"`, …) → list of facts. |
| Fact object keys | `{start?, end, val, accn, fy, fp, form, filed, frame?}` — `start` present on duration concepts, absent on instantaneous ones; `frame` optional. **`filed` is the point-in-time key** that makes the V2 true-PIT fix a `WHERE filed <= as_of_date` slicing change. |
| `https://data.sec.gov/submissions/CIK{cik10}.json` | `{cik, entityType, sic, sicDescription, name, tickers, exchanges, fiscalYearEnd, ...}` — **the only source of SIC.** |

**Correction logged:** `MASTER_PRD.md` §5.1 described SIC codes as a "bonus field" of the XBRL
`companyfacts` API. They are not there. SIC requires a **separate `submissions` call per CIK** —
a third EDGAR endpoint for Phase 2.

**Observed example of the look-ahead gap** (AAPL, `RevenueFromContractWithCustomerExcludingAssessedTax`):
`{"start":"2016-09-25","end":"2017-09-30","val":229234000000,"accn":"0000320193-19-000119","fy":2019,"fp":"FY","form":"10-K","filed":"2019-10-31","frame":"CY2017"}`
— period end 2017-09-30, filed 2019-10-31, a **>2-year** gap. This is the concrete size of the V1
Fork-1 simplification.

### 6.2 Tiingo

| Item | Verified value | Source |
|---|---|---|
| EOD endpoint | `GET https://api.tiingo.com/tiingo/daily/<ticker>/prices` | https://www.tiingo.com/documentation/end-of-day |
| Query params | `startDate`, `endDate` (`YYYY-M-D`), `format`, `resampleFreq`, `token` | same |
| Response fields | `date, open, high, low, close, volume, adjOpen, adjHigh, adjLow, adjClose, adjVolume, divCash, splitFactor` | same |
| Auth | `Authorization: Token <TOKEN>` header (literal `Token ` prefix + space), or `?token=`; `Content-Type: application/json`. **Use the header** — a query-param token leaks into logs and into the on-disk replayable cache. | https://www.tiingo.com/documentation/general/connecting |
| Rate-limit metrics | Hourly requests (reset hourly) · daily requests (reset midnight EST) · monthly bandwidth (reset 1st of month). Verbatim: *"We do not rate limit to minute or second, so you are free to make your requests as you desire."* | https://www.tiingo.com/documentation/general/overview |
| **Free ("Starter") tier limits** | **500 unique symbols/month · 50 requests/hour · 1,000 requests/day · 1 GB bandwidth/month** | https://www.tiingo.com/pricing |
| Licence | **"Internal Use Only"** — personal use; no display or sharing with another person or organisation | same |

**Correction logged:** `MASTER_PRD.md` §5.2 states "~50 unique symbols/hour." That is **wrong**.
It is **50 *requests* per hour**, with a separate **500 unique *symbols* per month** cap. The
backfill arithmetic survives (~100 tickers × one ranged request each ≈ 100 requests ≈ 2 h at
50 req/hr; 100 symbols is well inside 500/month), but the constraint that binds is different in
kind. An ingestion design that issues several requests per symbol is free under a symbols/hour cap
and stalls under a requests/hour cap.

**Design consequence:** EDGAR needs **inter-request spacing** (≥0.12 s) plus a **≥600 s cooldown**
on a block. Tiingo needs **no spacing at all** but a hard **hourly/daily request budget counter**.
These are different mechanisms; the two ingestion jobs must not share one rate-limiter
implementation.

### 6.2b Phase 5: `splitFactor` arithmetic direction (`mizan/backtest/portfolio.py`, `PHASE_5_SPEC.md` §0.1/§2.5/§6a)

**Verified live 2026-08-31**, resolving the build-time verification item `PHASE_5_SPEC.md` §0.1
named rather than guessed: Tiingo's own splits documentation
(https://www.tiingo.com/documentation/corporate-actions/splits, fetched this pass) states, quoted
verbatim: *"The ratio of splitTo from splitFrom. In other words: splitFactor = splitTo/splitFrom.
This ratio is helpful in calculating split price adjustments."* A live worked example (Realty
Income, 2021-11-15, a 1-to-1.0327 split, `splitFactor: 1.0327`) confirms `splitFactor` directly
states how many new shares one old share becomes.

**Consequence for `apply_split` (§4.1):** `splitFactor` is the multiplier applied to a **held share
count**, not its reciprocal — a 2-for-1 split (`splitTo=2, splitFrom=1`) carries `splitFactor=2.0`,
and 100 held shares become `100 * 2.0 = 200` shares. `mizan/backtest/portfolio.py`'s `apply_split`
therefore computes `new_quantity = holding.quantity * split_factor`. This is the arithmetic
direction that keeps `quantity * raw_close` continuous across the split (post-split raw prices are
correspondingly lower, roughly `raw_close / split_factor`, on Tiingo's own convention) — the build
does not additionally re-derive that price-side identity, since `mizan/backtest/portfolio.py` never
adjusts price, only share count, per `PHASE_5_SPEC.md` §6a's `raw_close`-governs-valuation decision.

### 6.2c Phase 7: `matplotlib` re-verified ahead of its promotion to a real dependency (`mizan/reporting/plots.py`, `PHASE_7_SPEC.md` §2.1)

**Verified live 2026-08-31.** Fetched `https://pypi.org/project/matplotlib/` directly ahead of
Phase 7 — the first phase that actually imports `matplotlib` — since a stale pin promoted from
"forward-declared, unused" to "real runtime dependency" without a fresh check would be exactly the
kind of silent staleness every prior phase's own dependency-promotion step (Phase 2's `httpx`,
Phase 3's `duckdb`/`pyarrow`, §6.1/§3 above) re-verified before promoting. Latest published release
remains **3.11.1**, uploaded **2026-07-18** — unchanged from what §3 above already recorded on
2026-08-30. **Decision: pin stays exactly `matplotlib==3.11.1`, no change.** Logged because this is
the pin's first *load-bearing* verification (the prior entry recorded it as forward-declared and
unused; this is the first phase where a stale pin would actually matter to a real import), not
because anything changed.

### 6.3 Phase 4: XBRL concept-tag verification (`mizan/screening/financial_ratios.py` §2.2)

Every tag `financial_ratios.py`'s four allow-lists name was checked live 2026-08-30 against real
EDGAR `companyfacts` responses (`GET https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`,
same declared User-Agent header as §6.1). 13 of 14 candidate tags confirmed; `LongTermInvestments`
could not be confirmed against any of the six real companies checked in this pass.

| Tag | Taxonomy | Role | Confirmed against | Shape |
|---|---|---|---|---|
| `Assets` | us-gaap | two-axis denominator (TOTAL_ASSETS basis) | Apple Inc., CIK 0000320193 | instantaneous, unit USD — as expected |
| `EntityCommonStockSharesOutstanding` | dei | two-axis denominator (MARKET_CAP basis) | Apple Inc., CIK 0000320193 | instantaneous, unit shares — as expected |
| `LongTermDebtNoncurrent` | us-gaap | `INTEREST_BEARING_DEBT_TAGS` | Apple Inc., CIK 0000320193 | instantaneous, unit USD |
| `LongTermDebtCurrent` | us-gaap | `INTEREST_BEARING_DEBT_TAGS` | Apple Inc., CIK 0000320193 | instantaneous, unit USD |
| `ShortTermBorrowings` | us-gaap | `INTEREST_BEARING_DEBT_TAGS` | JPMorgan Chase & Co., CIK 0000019617 | instantaneous, unit USD |
| `DebtCurrent` | us-gaap | `INTEREST_BEARING_DEBT_TAGS` | The Travelers Companies, Inc., CIK 0000086312 | instantaneous, unit USD |
| `ShortTermInvestments` | us-gaap | `INTEREST_BEARING_INVESTMENT_TAGS` | NIKE, Inc. (CIK 0000320187) and Caterpillar Inc. (CIK 0000018230) | instantaneous, unit USD |
| `MarketableSecuritiesCurrent` | us-gaap | `INTEREST_BEARING_INVESTMENT_TAGS` | Apple Inc., CIK 0000320193 | instantaneous, unit USD |
| `LongTermInvestments` | us-gaap | `INTEREST_BEARING_INVESTMENT_TAGS` | **not found** in any of the six companies checked (Apple, JPMorgan, Travelers, NIKE, Caterpillar, Progressive) | **`[UNVERIFIED]`** — standard, taxonomically valid `us-gaap` concept name; live presence unconfirmed this pass |
| `InvestmentIncomeInterest` | us-gaap | `NON_PERMISSIBLE_INCOME_TAGS` | JPMorgan Chase & Co., CIK 0000019617 | duration, unit USD |
| `InterestIncomeOther` | us-gaap | `NON_PERMISSIBLE_INCOME_TAGS` | JPMorgan Chase & Co., CIK 0000019617 | duration, unit USD |
| `InterestAndDividendIncomeOperating` | us-gaap | `NON_PERMISSIBLE_INCOME_TAGS` | JPMorgan Chase & Co., CIK 0000019617 | duration, unit USD |
| `Revenues` | us-gaap | `TOTAL_REVENUE_TAGS` | Apple Inc., CIK 0000320193 | duration, unit USD |
| `RevenueFromContractWithCustomerExcludingAssessedTax` | us-gaap | `TOTAL_REVENUE_TAGS` | Apple Inc., CIK 0000320193 | duration, unit USD |

**Why the numerator-side "misses" (`ShortTermBorrowings`/`ShortTermInvestments`/the three income
tags absent from Apple's own companyfacts) are not a problem:** Apple, having no
interest-bearing-deposit core business, simply never files those bank-typical tags at all — this is
exactly the "0.0, not an error" numerator-absence design `financial_ratios.py` already anticipates
(§4.2 of `PHASE_4_SPEC.md`), confirmed as a real, observed pattern rather than only a documented
policy. Note also, purely as an observation for a future pass and NOT acted on in this phase's own
tag lists (which are fixed by `PHASE_4_SPEC.md` §4.2 and out of scope to revise here): Apple itself
reports interest/dividend income under `InvestmentIncomeInterestAndDividend` (not
`InvestmentIncomeInterest`) and short-term borrowings under `OtherShortTermBorrowings` (not
`ShortTermBorrowings`) — two real, live-observed us-gaap tag variants outside the current allow-lists.

### 6.4 Phase 4: `SIC_TIER_MAP` SIC-code verification (`mizan/screening/business_activity.py` §4.1)

Every SIC code in `SIC_TIER_MAP` was checked live 2026-08-30 against SEC's own published SIC code
list
(https://www.sec.gov/corpfin/division-of-corporation-finance-standard-industrial-classification-sic-code-list,
444 assigned codes) and cross-checked for at least one real registered filer via
`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&SIC={code}`. All codes named in
`PHASE_4_SPEC.md` §4.1's illustrative table were confirmed **except one**:

**Correction logged:** `PHASE_4_SPEC.md` §4.1 names "7993 (gambling)" as an illustrative Tier-0 SIC
code. **SIC 7993 is not an SEC-assigned code at all** — absent from SEC's own published list, and a
live EDGAR company-search for `SIC=7993` returns zero registrants. Checked instead: two real
gambling/casino issuers — Wynn Resorts, Limited (CIK 0001174922) and Caesars Entertainment, Inc.
(CIK 0001590895) — both file under SIC **7011 (Hotels & Motels)**, which `SIC_TIER_MAP` already
carries (as Tier 1, per `PHASE_4_SPEC.md` §4.1's own table). `SIC_TIER_MAP` therefore omits 7993
entirely rather than including a code that was itself never verified to exist — a documented,
known granularity limitation of the generic SIC-first-pass mechanism (a gambling-core-business
issuer is only caught when `business_activity_tier_1_enabled` is on, or via a hand-researched
override), not a silently-dropped requirement.

---

## 7. Methodology sources (fiqh layer)

| Claim | Status | Source |
|---|---|---|
| AAOIFI SS21 issued May 2004 | **verified** (slide 27) | [oicexchanges.org PDF](https://www.oicexchanges.org/files/1---shari-ah-screening-in-the-islamic-capital-markets-dr-hamed-merah-secretary-general-aaoifi.pdf) |
| 8-item enumerated industry screen; adult content and weapons/defence **not** among them | **verified** (slide 18) | same |
| 30% / 30% thresholds (tighter than DJ/FTSE/S&P's 33%) | **verified** (slides 32–34) | same |
| Non-permissible income < 5% of **"Total Income"** | **verified** (slide 32) — note: primary source says *income*, `MASTER_PRD.md` §6.2 says *revenue*. See `ULTIMATE_PRD.md` Q2. | same |
| Pure / Mixed / Non-compliant three-state taxonomy and its definitions | **verified** (slide 21) | same |
| Purification = donate to charity, **excluded from investor P&L** (side-ledger) | **verified** (slides 24–25) | same |
| SS21 §3/2 permits dealing in shares "with the intention of benefiting from the difference in prices" | **verified** (slide 30) — bears on the deferred HFT scope edge; see `ULTIMATE_PRD.md` Q3. **Deliberately not acted on.** | same |
| **AAOIFI's own ratio denominator basis (market cap vs total assets)** | **`[UNVERIFIED]`** — not stated anywhere in the public methodology this pass could reach | searched: full 37-slide PDF, `aaoifi.com`, 2025–2026 SS21-revision sweep |
| **AAOIFI's own averaging window (or absence of one)** | **`[UNVERIFIED]`** — the presentation states the *other* standards' windows (slide 31) but never AAOIFI's | same |
| `amanahadvisors.com` 30%-rule explainer | **`[UNVERIFIED]`** this pass — now behind a Cloudflare bot challenge, could not be re-fetched | https://amanahadvisors.com/making-sense-of-the-30-rule-in-islamic-finance/ |
| AAOIFI Shari'ah Standard No. 21, full text | **paywalled, unread** | https://aaoifi.com/ |

**Standing disclaimer, unchanged:** all AAOIFI thresholds in this project are *as-implemented from
public methodology, pending scholarly verification.* The definitive text is AAOIFI Shari'ah
Standard No. 21 itself, which no pass of this project has read.

---

## 8. Literature pins

| Paper | Version pinned | Role |
|---|---|---|
| Qadi, Sharma & Medda, *From Binary Screens to Continuous Compliance* — [arXiv:2512.22858](https://arxiv.org/abs/2512.22858) | **v2, 2026-03-11** (pass 1 cited v1, 2025-12-28) | Corroborates the configurable denominator/threshold design; v2 adds "no reliable association with returns" |
| Qadi, Sharma & Medda, *The Price of Permission* — [arXiv:2608.12634](https://arxiv.org/abs/2608.12634) | v1, 2026-08-12 | Boundary proximity predicts screen transitions → every-holding re-screening is necessary; motivates threshold-margin in the reason trace |
| Fonseca, *Look-Ahead-Freedom as Temporal Non-Interference* — [arXiv:2607.04958](https://arxiv.org/abs/2607.04958) | v1, 2026-07-06 | Validates the one-function look-ahead quarantine; supplies the decidable static confinement check |
| Elbadry et al., *SAHM* — [arXiv:2604.19098](https://arxiv.org/abs/2604.19098) | v2, 2026-04-30 | Corroborates the no-LLM-in-compliance invariant with measured frontier-model unreliability on AAOIFI-standards reasoning |

**Null results (pass 2):** no paper found proposing a better deterministic business-activity
classifier for a hand-verifiable ~100-ticker universe; none settling Fork C's divestment-attribution
formula; no AAOIFI SS21 revision or exposure draft 2025–2026.

---

## 9. Capability log (what was and was not available to each pass)

| Capability | Pass 1 (2026-07-02) | Pass 2 (2026-08-30) |
|---|---|---|
| Native web search | used | **used** |
| Direct HTTP fetch | used (SEC/Tiingo returned SPA shell only) | **used — including `curl` with a declared SEC `User-Agent`, which was required to get past HTTP 403** |
| Local PDF text extraction | not used | **used** (AAOIFI 37-slide presentation, all slides extracted) |
| `arxiv-mcp` MCP tools | n/a | **attempted, FAILED** — `SSL: CERTIFICATE_VERIFY_FAILED` (self-signed cert in chain). Degraded. |
| `paper-search-mcp` MCP tools | n/a | **attempted, FAILED** — proxy `RemoteDisconnected`. Degraded. |
| `curl` to `export.arxiv.org` | n/a | **attempted, FAILED** — TLS handshake (exit 35). Degraded to the arXiv Atom API over the web-fetch path. |
| Nia | used (pass 1's stated fetch tool) | not used |

No pass hit a genuine halt condition. Pass 2's paper-search failures were degraded around, not
worked around by fabrication — the literature sweep in §8 was completed via the arXiv Atom API and
`arxiv.org/abs/*` over the available fetch path.
