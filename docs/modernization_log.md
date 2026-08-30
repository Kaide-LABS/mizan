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
| **2** | **2026-08-30** | **Step 10 PRD modernization + Phase 1 blueprint** | **All library versions; SEC EDGAR policy + live endpoint shapes; Tiingo endpoint/limits/auth; DuckDB + Pydantic API signatures; AAOIFI primary-source methodology; 2024–2026 literature sweep** |

Pass 2 corrected 2 wrong API facts, 1 wrong external limit, discharged 2 unverified flags from
pass 1, and demoted 1 previously-asserted claim to `[UNVERIFIED]`. See
`ULTIMATE_PRD.md` § MODERNIZATION CHANGELOG for the itemised list.

---

## 2. Runtime

| Item | Pinned | Verified | Source |
|---|---|---|---|
| Python (declared floor/ceiling) | `>=3.11,<3.15` | 2026-08-30 | Floor set by `pandas` 3.0.5 and `matplotlib` 3.11.1 (both require `>=3.11`); ceiling set because no pinned dependency publishes `cp315` wheels |
| Python (build/test interpreter) | **3.14.x** — record the exact patch here at first build: `3.14.__` | 2026-08-30 | https://www.python.org/downloads/release/python-3147/ (3.14.7, released 2026-08-05) |

Every runtime and dev dependency pinned below publishes `cp311`–`cp314` wheels, so any interpreter
in the declared range works. The local machine runs Python 3.14.x.

**Action for the Phase 1 execution agent:** replace `3.14.__` above with the actual
`python --version` output of the interpreter the project is built against, in the same commit that
adds `pyproject.toml`.

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
