# Research report -- Pivoting an equity Shariah-research/backtest sandbox to a crypto-first, spot-only halal research and backtesting rig with a future-proof signal-adapter seam

Generated 2026-11-24T14:49:46.891Z by OSA. Researched by claude-code using its built-in web search. Time range: last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].
Values marked [uncertain] could not be verified from a source the agent opened; they are repeated under *Open uncertainties*.

## Findings

### Official documentation: Coinbase (Advanced Trade / Exchange public market data API)
*Find the OFFICIAL documentation for "Coinbase (Advanced Trade / Exchange public market data API)": its current stable version, how it is installed or enabled, the API surface this build will use, and any breaking changes or pitfalls in the last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].*

Coinbase offers two overlapping, keyless, public (no-auth) REST endpoints for historical daily OHLCV candles: the legacy-rebranded 'Exchange API' at api.exchange.coinbase.com (successor to the shut-down Coinbase Pro API, itself not deprecated) and the newer 'Advanced Trade' public market data endpoint under api.coinbase.com/api/v3/brokerage. Both require no API key for market-data reads, but have different parameter shapes, different per-call candle caps (300 vs 350), and both are capped per request, so multi-year daily history for 14 coins requires simple pagination. For a keyless, zero-setup, spot-only daily OHLCV ingester, the Exchange API endpoint is the simpler of the two (optional start/end, granularity as integer seconds) and has no CDP account/project requirement, making it the natural primary source with Kraken as fallback for symbols/history it lacks.

**Key findings**
- Exchange API public candles: GET https://api.exchange.coinbase.com/products/{product_id}/candles, no auth ('security: []' in the OpenAPI spec), granularity must be one of 60/300/900/3600/21600/86400 seconds; max 300 data points per request, request is rejected if start/end+granularity would exceed that.
- Exchange API candle response is an array ordered [time, low, high, open, close, volume] (note: open/close order differs from the Advanced Trade object fields).
- Advanced Trade public candles: GET https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/candles, no auth required, but start, end AND granularity are required params; granularity is a string enum (ONE_MINUTE...ONE_DAY); optional 'limit', default and max 350 candles per call; public responses are cached for 1 second.
- Coinbase Pro (api.pro.coinbase.com) was fully shut down/migrated by 2023-NOV-09; its successor for unauthenticated market data is the Exchange API (api.exchange.coinbase.com), which the Exchange changelog explicitly does NOT list as deprecated as of this review.
- Public (unauthenticated) Exchange API endpoints are rate-limited to 10 req/s per IP with burst to 15 req/s; private (authenticated) endpoints get higher limits — not relevant to this keyless build but important for pagination throttling.
- 2025-FEB-05: Coinbase deprecated legacy *authenticated* API keys (forces migration to CDP/Advanced Trade keys) — this affects authenticated/trading use, not the keyless public candles endpoints this build relies on, but is a pitfall if anyone later adds authenticated order flow.
- 2025-JAN-01: Coinbase Price Oracle API deprecated (irrelevant to candles, but shows Coinbase does retire adjacent data APIs without notice to this project).
- 2025-OCT-20: Coinbase enforced TLS 1.2+ on the *.exchange.coinbase.com domain for all system access — any HTTP client/library pinned to an older TLS version will fail against the Exchange API candles endpoint.
- Historical Exchange API docs explicitly warn: 'Historical rate data may be incomplete. No data is published for intervals where there are no ticks.' and advise against frequent polling of the candles endpoint — relevant for building a cache-respecting daily ingester.
- Advanced Trade's public market endpoints additionally expose /market/products (list) and /market/products/{id}/ticker, which could serve as a lighter 'is this symbol listed' check before calling candles for each of the 14 named tokens.

**Recommendations**
- Use the Exchange API public candles endpoint (api.exchange.coinbase.com/products/{product_id}/candles, granularity=86400 for daily) as the primary Coinbase data path: it needs no CDP account/project, no key, and has simpler optional start/end semantics than Advanced Trade's required-params version.
- Design the ingestion layer's granularity parameter around the Exchange API's integer-seconds enum (60,300,900,3600,21600,86400) so non-daily granularities (e.g. 3600 for hourly) can be requested later without code changes, per acceptance criterion 3 — just pass a different integer today while defaulting to 86400.
- Paginate daily-candle pulls in chunks of ≤300 days per request (Exchange API hard cap) when backfilling multi-year history for each of the 14 tokens; do not request a date range that silently gets truncated.
- Respect the 10 req/s (burst 15 req/s) public IP rate limit with basic client-side throttling/backoff on HTTP 429 across the 14-token backfill loop.
- [removed by OSA: this line looked like an instruction aimed at an AI (governance)]
- Treat Coinbase Pro references in any third-party library/example code as dead — do not route through api.pro.coinbase.com; use api.exchange.coinbase.com (Exchange API) or api.coinbase.com/api/v3/brokerage/market (Advanced Trade public) instead.
- Do not use any authenticated Advanced Trade endpoints or CDP API keys for this build — the PRD requires keyless/public access only, and authenticated-key flows are the ones currently churning (legacy key deprecation Feb 2025), which keyless public endpoints are insulated from.
- Fall back to Kraken's public OHLC endpoint for any of the 14 tokens not listed on Coinbase or lacking sufficient history, per the locked constraint — verify per-token product availability via the Exchange API's /products or Advanced Trade's /market/products list endpoint before attempting a candles call, to fail over cleanly rather than treating a 404 as a hard error.

**current version:** No formal version numbering published; Advanced Trade public market data REST is on base path /api/v3/brokerage (v3); Exchange API (api.exchange.coinbase.com) is unversioned in its URL and remains the active, non-deprecated successor to the shut-down Coinbase Pro API [uncertain]

**api surface**
- GET https://api.exchange.coinbase.com/products/{product_id}/candles?granularity=86400&start=...&end=... (primary daily OHLCV pull, keyless, max 300 rows/call)
- GET https://api.exchange.coinbase.com/products (optional: verify product/symbol availability before requesting candles)
- GET https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/candles?granularity=ONE_DAY&start=...&end=... (alternative/backup keyless daily OHLCV source, max 350 rows/call)
- GET https://api.coinbase.com/api/v3/brokerage/market/products (alternative product listing check)

**pitfalls**
- Coinbase Pro (api.pro.coinbase.com) is fully retired since 2023-11-09; any code/snippet referencing it will fail — must use Exchange API or Advanced Trade public paths instead.
- 2025-02-05: legacy authenticated API keys deprecated — irrelevant to this keyless build today, but a trap if authenticated/live-order code is ever added later without updating to CDP keys.
- 2025-10-20: TLS 1.2+ enforced on *.exchange.coinbase.com — clients/libraries with outdated TLS stacks will see connection failures that look like the endpoint is down.
- Exchange API candles hard-caps at 300 rows and Advanced Trade at 350 rows per call — both silently reject (Exchange) or truncate oversized start/end+granularity ranges, requiring explicit pagination logic for multi-year daily backfills across 14 tokens.
- The two Coinbase candle response shapes differ in field order/naming (Exchange: [time,low,high,open,close,volume] array; Advanced Trade: named object fields start/open/close/high/low/volume) — a single ingestion adapter must not assume one format when switching between them or to Kraken.
- Exchange API docs themselves warn that polling the candles endpoint frequently is discouraged and historical data 'may be incomplete' for low-liquidity intervals — a risk for newer/thinner-volume tokens among the 14 named coins.

*As of: Documentation reviewed 2026-11-24; most recent cited changelog entries are 2025-OCT-20 (TLS enforcement) and 2025-FEB-05 (legacy key deprecation). No explicit 'current version' number is published by Coinbase for either API; Advanced Trade's REST base path is versioned 'v3' (api/v3/brokerage), Exchange API is unversioned in its URL.*

**Sources**
- [Get Public Product Candles - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles) (official-docs) -- "Returns 'rates for a single product by product ID, grouped in buckets.' Default response contains 350 candles maximum; granularity enum ONE_MINUTE...ONE_DAY; start and end are required."
- [Get product candles - Coinbase Developer Documentation (Exchange API)](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles) (official-docs) -- "granularity must be one of: 60, 300, 900, 3600, 21600, 86400 seconds... Max Candles per Request: 300... Historical rate data may be incomplete."
- [Exchange Changelog - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/exchange/changes/changelog) (official-docs) -- "Pro API (2024-SEP-11): deprecated in favor of Exchange API ... no entries mentioning deprecation, sunset, retirement, or shutdown of the Exchange API itself."
- [Exchange Rate Limits Overview / REST Rate Limits - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits) (official-docs) -- "Requests Per Second: 10 per IP. Burst Capacity: Up to 15 requests per second per IP. Public endpoints do not require authentication."
- [Advanced Trade REST Endpoints - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-api) (official-docs) -- "Base URL: https://api.coinbase.com/api/v3/brokerage ... Public (No Auth Required): /time, /market/products, /market/products/{product_id}/candles, /market/products/{product_id}/ticker."


### Official documentation: Kraken (public REST market data API)
*Find the OFFICIAL documentation for "Kraken (public REST market data API)": its current stable version, how it is installed or enabled, the API surface this build will use, and any breaking changes or pitfalls in the last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].*

Kraken's public Spot REST market data API is unauthenticated, keyless, and reachable at https://api.kraken.com/0/public/*, which fits the build's 'free, keyless, public' constraint and makes Kraken a valid fallback to Coinbase for the 14 named tokens. The relevant endpoints are Assets, AssetPairs (to resolve tickers/pair names) and OHLC (to fetch candles), with OHLC supporting a minutes-based interval parameter (1,5,15,30,60,240,1440,10080,21600) where 1440 = daily, satisfying the acceptance criterion that ingestion accept a granularity parameter. The critical pitfall for this build is that the OHLC REST endpoint caps results at 720 of the most recent candles regardless of the `since` value — older history cannot be retrieved via this endpoint at all, so for daily candles that is a hard ceiling of ~720 days (~2 years) of backfillable history per call. A confirmed breaking change in the research window: as of 1 Jan 2024 Kraken removed support for POST requests to all public endpoints, so only GET must be used.

**Key findings**
- Base URL for public REST calls: https://api.kraken.com/0/public/ (path-versioned as '0'; Kraken does not publish a separate semantic version number for the REST API itself).
- OHLC endpoint: GET /0/public/OHLC?pair=<PAIR>&interval=<minutes>&since=<unix_ts>. interval accepted values (minutes): 1, 5, 15, 30, 60, 240, 1440, 10080, 21600; 1440 = 1 day.
- OHLC response rows: [time, open, high, low, close, vwap, volume, count]; the last row in the array is always the current, not-yet-closed candle regardless of `since` and must be discarded/handled separately for a 'closed daily candle' dataset.
- OHLC is capped at 720 of the most recent entries per call — older data cannot be retrieved via this endpoint regardless of the `since` value. For daily (1440) interval this is a hard ~720-day history limit via REST OHLC alone.
- Public endpoints require no API key/authentication at all ('no authentication is needed' for public methods).
- Public rate limit: 'Calling the public endpoints at a frequency of 1 per second (or less) would remain within the rate limits.' Trades and OHLC calls are rate-limited by IP address + currency pair; all other public endpoints are rate-limited by IP address only.
- Breaking change (effective 1 Jan 2024, within the research window): POST requests to all public endpoints are no longer supported and now return a 4xx error — GET is required.
- Recent additive changes found in the changelog (2024-2026) are not relevant to plain spot crypto OHLC: a `country_code` AssetPairs param (May 2024), an `asset_class`/`tokenized_asset` param for xStocks support (Aug 2025), `execution_venue` filtering (Apr 2026), and cursor-based pagination added to Ledgers/TradesHistory/ClosedOrders (2026) — none of these affect the basic public OHLC/Assets/AssetPairs calls this build needs.
- AssetPairs (GET /0/public/AssetPairs) and Assets (GET /0/public/Assets) endpoints are used to resolve a token's Kraken pair name/altname (e.g. confirming a ticker like 'XBT' vs 'BTC') before calling OHLC; AssetPairs also exposes `status` which should be checked so delisted/unlisted pairs aren't silently fetched.
- TLS 1.0/1.1 are no longer supported by Kraken's infra; clients must use TLS 1.2+ or may see connection/403 issues (also watch for Cloudflare 'Browser Integrity Check' 403s if the HTTP client doesn't send a normal User-Agent).

**Recommendations**
- Use Kraken only as the documented fallback when Coinbase lacks a token/history, exactly as the build specifies — implement it against GET /0/public/OHLC with interval=1440 for daily candles.
- Build the granularity parameter directly around Kraken's `interval` enum (1,5,15,30,60,240,1440,10080,21600 minutes) so the 'non-daily without code changes' acceptance criterion maps cleanly onto Kraken's real accepted values; default to 1440.
- Always drop the final row of the OHLC response array (the open/uncommitted candle) before writing to the raw cache / DuckDB store, or daily bars will be understated/incomplete on the most recent day.
- Do not rely on Kraken REST OHLC alone for deep backfills: since it returns at most 720 of the most recent candles and ignores `since` beyond that window, any daily history older than ~2 years from today is unavailable through this endpoint — document this as a known data limitation in the report rather than assuming Coinbase+Kraken together guarantee arbitrarily long history.
- Only ever issue GET requests to Kraken public endpoints (never POST) — this has been a hard requirement since 1 Jan 2024.
- Throttle Kraken public calls to no more than ~1/second per IP+pair (for Trades/OHLC) to stay under the published rate limit, and add basic retry/backoff on 'EService: Throttled' responses.
- Resolve each of the 14 tokens' Kraken pair name via AssetPairs/Assets first (don't hardcode guessed pair strings), and check pair `status` to avoid silently ingesting from a delisted or non-tradable pair.

**current version:** Kraken Spot REST API does not use semantic versioning for the public surface; all endpoints documented here are served under the stable path prefix /0/public/ (e.g. https://api.kraken.com/0/public/OHLC) with an optional per-endpoint `assetVersion` query param (only value `1` supported as of this review) [uncertain]

**api surface**
- GET https://api.kraken.com/0/public/OHLC?pair=<PAIR>&interval=1440&since=<unix_ts> — daily (and future non-daily) candle fetch
- GET https://api.kraken.com/0/public/AssetPairs?pair=<PAIR> — resolve/validate a token's tradable pair name and status before fetching OHLC
- GET https://api.kraken.com/0/public/Assets?asset=<ASSET> — resolve canonical asset/altname mapping for a token symbol
- interval parameter values (minutes): 1, 5, 15, 30, 60, 240, 1440, 10080, 21600 — used for the granularity-parameter interface requirement
- since parameter (unix timestamp) for incremental polling, bounded by the 720-row recency cap

**pitfalls**
- OHLC endpoint returns at most 720 of the most recent candles regardless of `since` — no way to backfill older daily history via this endpoint; for 1440-minute interval this is a hard ~720-day (~2 year) ceiling.
- As of 1 Jan 2024, POST requests to Kraken public endpoints are rejected (4xx) — GET is mandatory.
- The last entry of every OHLC response array is the current, still-open candle and will always be present; treating it as a closed daily bar will corrupt the most recent day's data.
- Public OHLC/Trades calls are rate-limited per IP+pair (not just per IP), so parallel fetchers hitting many pairs from the same IP can still be throttled even though each individual pair looks under 1 req/sec.
- Dropped TLS 1.0/1.1 support and Cloudflare bot-integrity checks can cause opaque 403/connection errors if the HTTP client is misconfigured (no modern TLS, missing/odd User-Agent) — unrelated to API logic but can look like an API outage.
- Recent additive params (`asset_class`/`tokenized_asset` for xStocks, `country_code`, `execution_venue`) target non-crypto or institutional use cases and should be left untouched/omitted for this build's plain spot-crypto pairs to avoid unintended filtering.

*As of: Documentation reviewed as of 2026-11-24; changelog entries observed up to September/October 2026; the Jan 2024 POST-removal breaking change falls inside the requested 2024-prioritised window.*

**Sources**
- [Get OHLC Data — Kraken Developers (official REST API reference)](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data) (official-docs) -- "Returns up to 720 of the most recent entries (older data cannot be retrieved, regardless of the value of since). ... interval (integer, default: 1): Time frame in minutes — Valid values: 1, 5, 15, 30, 60, 240, 1440, 10080, 21600."
- [Spot REST Rate Limits — Kraken Developers](https://docs.kraken.com/exchange/guides/rest/ratelimits) (official-docs) -- "Kraken implements a 'call counter' system... 'EAPI:Rate limit exceeded' – counter exceeded maximum; 'EService: Throttled: [UNIX timestamp]' – too many concurrent requests."
- [What are the API rate limits? — Kraken Support](https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-) (official-docs) -- "The Spot public endpoints are rate limited by IP address and currency pair for calls to Trades and OHLC, and by IP address only for calls to all other public endpoints... Calling the public endpoints at a frequency of 1 per second (or less) would remain within the rate limits."
- [Advanced API FAQ — Kraken Support](https://support.kraken.com/articles/advanced-api-faq) (official-docs) -- "If you only intend to make calls to public methods, then you may choose to opt out of client libraries as no authentication is needed... we have recently dropped support for TLS 1.0 and 1.1."
- [Exchange Changelog — Kraken Developers](https://docs.kraken.com/exchange/changelog) (official-docs) -- "Kraken 'removed support for POST requests to all public endpoints' as of January 1, 2024, requiring GET-only access for market data."
- [kraken-swagger-validated.json (community-maintained OpenAPI spec mirror of Kraken public endpoints)](https://gist.github.com/maliky/03de5e2a1664ec8df5a665c517d0d151) (repo) -- "Path: /public/OHLC ... Response Schema: Returns array of tick data with structure: [time, open, high, low, close, vwap, volume, count]."


### Official documentation: DuckDB
*Find the OFFICIAL documentation for "DuckDB": its current stable version, how it is installed or enabled, the API surface this build will use, and any breaking changes or pitfalls in the last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].*

DuckDB's current stable line is 2.0, released as a Long-Term-Support (LTS) release on 2026-10-21 under codename 'Cinnamon Teal', with the Python package at version 2.0.1 as of the installation docs. For this build it is used purely as an embedded, file-based analytical store: install via `pip install duckdb`, open a persistent file with `duckdb.connect("path/to/db.duckdb")`, and move pandas OHLCV DataFrames in/out with `con.sql("CREATE TABLE ... AS SELECT * FROM df")` / `con.register()` / `.df()`. The prior LTS (1.5.x, supported until 2027-03) is a safer pin if the team wants to avoid 2.0's SQL-parser and lambda-syntax changes, but 2.0 is the officially current stable and has a longer support horizon (through 2027-10).

**Key findings**
- Current stable/LTS release: DuckDB 2.0.0 'Cinnamon Teal', announced 2026-10-21 on the official blog; Python client package is at 2.0.1 per the official installation docs.
- LTS support windows stated in the official announcement: 2.0 supported through October 2027; 1.5 extended to March 2027; 1.4 supported until November 2026.
- Install for Python: `pip install --upgrade duckdb`; pin an older release with e.g. `pip install duckdb==1.5.6`. CLI available separately via `pip install duckdb-cli` (or `duckdb-cli==1.5.6` for the LTS 1.x line).
- Windows requires the Microsoft Visual C++ Redistributable for the Python package to load.
- Database files written by 2.0 cannot be opened by pre-2.0 DuckDB builds; 2.0 can still read/write older pre-2.0 database files (one-way compatibility) — relevant if a cached/shared .duckdb file is later opened with an older runtime.
- Breaking change: integer division by zero (`//` or `%` on integers) now raises an error instead of returning NULL in 2.0; float `/` still returns infinity on divide-by-zero.
- Breaking change: the old single-arrow lambda syntax is disabled in 2.0's new PEG-based SQL parser (replacing the Postgres-derived parser).
- Build requirement bumped to C++17 (from C++11) and release builds now use Clang — not directly relevant to pip-installed Python usage but relevant if building extensions from source.
- Python API change in 2.0: `fetchone()` was removed from relation objects returned by `con.sql(...)` (lazy relations re-execute per call); use `.fetchall()`/`.df()`/`.fetchdf()` on a cursor via `con.execute(...)` instead, or materialize the relation first.
- DuckDB Python natively queries pandas/Polars/PyArrow objects by name in SQL (e.g. `duckdb.sql("SELECT * FROM pandas_df")`) but these external-object scans are read-only — you cannot INSERT/UPDATE directly into a DataFrame; data must be materialized into a real DuckDB table to persist it.
- `duckdb.connect()` with no path gives a session-only in-memory database; `duckdb.connect("file.duckdb")` gives a persistent file-backed database that reloads on reconnect — this is the mode the ingestion store needs.
- CSV ingestion supported via `duckdb.read_csv("file.csv")` or directly querying `'file.csv'` in SQL; relations can be exported with `.write_parquet()` / `.write_csv()` for the raw-cache layer.
- S3 URL query-string credentials/config are disabled by default in 2.0 (treated as literal object key) — not applicable here since this build uses no cloud storage, but worth noting if a future adapter layer touches S3-hosted data.

**Recommendations**
- Pin an explicit DuckDB version in requirements (e.g. `duckdb==2.0.1`) rather than floating `duckdb`, since 2.0 is a new major line with parser/behavior changes versus 1.x.
- Use a single persistent file path, e.g. `duckdb.connect("data/mizan.duckdb")`, as the DuckDB store referenced in acceptance criterion 2; keep the raw cache (Parquet/CSV per candle fetch) as a separate directory, written independently of the DB so re-ingestion is idempotent.
- Write OHLCV data by materializing pandas DataFrames into real tables (`CREATE TABLE IF NOT EXISTS ... AS SELECT * FROM df` or `INSERT INTO ... SELECT * FROM df`) rather than relying on read-only DataFrame scans, since the fetched candles must persist across runs.
- Do not rely on `.fetchone()` on relation objects from `con.sql(...)`; use `con.execute(sql).fetchall()`/`.df()` for cursor-style access if iterative row fetching is needed anywhere in the pipeline.
- Avoid integer division (`//`, `%`) on any fee/slippage or rebalance-weight calculation paths without explicit zero-guards, since 2.0 raises on integer divide-by-zero where 1.x may have returned NULL — this could silently break if ported from older DuckDB-based code.
- If the existing equity-era repo was built against an older DuckDB (1.x) and its database files/queries are reused as-is per the 'preserve equity code as-is' constraint, verify those files still open under 2.0 (one-way compatible) but do not downgrade the new crypto store to be read by pre-2.0 tooling.
- No DuckDB extensions are required for this build's stated feature set (local pandas <-> file-backed table, CSV/Parquet caching); avoid pulling in optional extensions (httpfs, S3, lakehouse formats) since all data fetching happens via the Coinbase/Kraken clients in Python, not via DuckDB's own HTTP/S3 readers.

**current version:** 2.0.1 (DuckDB 2.0.0 'Cinnamon Teal' LTS, released 2026-10-21; Python package shown at 2.0.1 on the official install docs)

**api surface**
- duckdb.connect("path.duckdb") — persistent file-backed connection for the DuckDB store
- con.sql(sql) / con.execute(sql) — run SQL, returns a lazy relation or cursor
- con.register(name, df) — expose a pandas DataFrame to SQL by name (read-only)
- CREATE TABLE ... AS SELECT * FROM df / INSERT INTO ... SELECT * FROM df — materialize fetched OHLCV data into persistent tables
- relation.df() / .fetchdf() / .to_arrow_table() — pull query results back into pandas/Arrow for the backtest engine
- duckdb.read_csv("file.csv") / querying 'file.csv' directly in SQL — optional raw-cache ingestion path
- relation.write_parquet(path) / relation.write_csv(path) — persist raw cache snapshots
- pip install duckdb (Python package) — no server, no keys, local-only, satisfies 'free, keyless' constraint

**pitfalls**
- Integer division/modulo by zero raises an error in 2.0 instead of returning NULL (1.x behavior) — guard fee/weight math.
- Old single-arrow lambda SQL syntax removed under the new PEG parser in 2.0.
- `fetchone()` removed from lazy relation objects returned by con.sql(); use execute()+fetchall()/df() instead.
- Database files created by 2.0 are not readable by pre-2.0 DuckDB — one-way forward compatibility only.
- C++17 now required to build DuckDB/extensions from source (irrelevant for pip-installed wheels, relevant only if compiling extensions).
- S3 URL query-string credentials disabled by default in 2.0 (not applicable to this keyless, local-file build, but a trap if cloud storage is added later).
- 1.x LTS (1.5.6) remains supported only until 2027-03, and 1.4 until 2026-11 — do not pin to an EOL'd 1.4 line going forward.

*As of: 2026-11-24; DuckDB 2.0.0 announced 2026-10-21, Python package 2.0.1 per docs.2.0 installation page fetched same day*

**Sources**
- [DuckDB Documentation (docs/2.0)](https://duckdb.org/docs/2.0/) (official-docs) -- "See what's new in the 2.0 documentation"
- [DuckDB Python Client Overview (docs/2.0)](https://duckdb.org/docs/2.0/clients/python/overview.html) (official-docs) -- "any data written to that connection will be persisted, and can be reloaded by reconnecting to the same file"
- [DuckDB Installation (docs/2.0)](https://duckdb.org/docs/2.0/installation/) (official-docs) -- "pip install --upgrade duckdb ... DuckDB requires the Microsoft Visual C++ Redistributable"
- [Announcing DuckDB 2.0.0 LTS "Cinnamon Teal"](https://duckdb.org/2026/10/21/announcing-duckdb-200) (official-docs) -- "DuckDB 2.0 comes with a small set of breaking changes"


### Official documentation: TimesFM
*Find the OFFICIAL documentation for "TimesFM": its current stable version, how it is installed or enabled, the API surface this build will use, and any breaking changes or pitfalls in the last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].*

TimesFM's official documentation lives in the google-research/timesfm GitHub repo and the corresponding Hugging Face model cards. The current stable release is TimesFM 3.0 (PyPI package timesfm 3.0.2, HF checkpoint google/timesfm-3.0-pytorch), but its pretrained weights are now restricted to a non-commercial license; the prior checkpoint, TimesFM 2.5 (google/timesfm-2.5-200m-pytorch), keeps the original Apache-2.0 weight license and is the more appropriate choice for this free/keyless research-only build if TimesFM is ever wired in as the 'naive baseline' comparator required by the validation-gate spec (acceptance criterion 12). Installation is a plain `pip install timesfm[torch]` (no API key), and the 2.5 API is `from_pretrained` -> `compile(ForecastConfig(...))` -> `forecast(horizon, inputs)`. For this build, which only needs to document the validation-gate requirement to 'beat TimesFM/naive baseline' and build no implementation, the key documentation facts are: exact package/checkpoint name, context/horizon limits, and the 1.0->2.5 API/license breaking changes.

**Key findings**
- Current stable PyPI package is timesfm 3.0.2; HF collection shows checkpoints 1.0 (200M, context 512), 2.0 (500M, context 2,048), 2.5 (200M, context up to 16,384, horizon up to 1,000 via continuous quantile head), and 3.0 (~0.3B params, native multivariate/covariate support, context up to ~15,360).
- TimesFM 2.5 removed the mandatory 'freq' (frequency) categorical argument ({0,1,2}) that was required in 1.0 and 2.0 -- confirmed directly in the official GitHub README ('gets rid of the frequency indicator').
- API class names changed across versions and are not drop-in compatible: 1.0 used a `TimesFm` class, 2.5 uses `timesfm.TimesFM_2p5_200M_torch.from_pretrained(...)` + `.compile(ForecastConfig(...))` + `.forecast(horizon, inputs)`, and 3.0 introduces `TimesFM3Evaluator`/`ModelConfig` with multivariate covariate inputs.
- License split: source code is Apache-2.0 across all versions, and model weights for 1.0 through 2.5 are Apache-2.0, but TimesFM 3.0's pretrained weights are under a separate 'timesfm-non-commercial-license-v1.0' that prohibits self-hosted commercial/production use (only permitted via Google Cloud BigQuery ML / Vertex Model Garden).
- The TimesFM-2.5-200M-pytorch model card's own usage example configures `max_context=1024, max_horizon=256`, which is far below the architecture's stated ceiling of context<=16,384 / horizon<=1,000 -- these are configurable `ForecastConfig` values, not hard model limits.
- Every HF checkpoint card states: 'This checkpoint is not an officially supported Google product.'
- Installation requires no API key (`pip install timesfm[torch]`, or `pip install timesfm[mlx]` on Apple Silicon), but it does pull multi-hundred-MB model weights from Hugging Face on first run, which is a network dependency distinct from the 'free, keyless' market-data constraint in this build.

**Recommendations**
- If/when the validation-gate spec needs a concrete TimesFM reference, name TimesFM 2.5 (`google/timesfm-2.5-200m-pytorch`, installed via `pip install timesfm[torch]`) rather than 3.0, because its weights are unambiguously Apache-2.0 -- avoids any licensing question for a free/public research-only tool; 3.0's non-commercial weight license is a new complication worth flagging but not needed for this build.
- Since this build only requires the validation-gate specification to state 'must beat TimesFM/naive baseline' (no adapter implementation yet), document the exact pinned package version and checkpoint id (e.g. `timesfm==2.5.x`, `google/timesfm-2.5-200m-pytorch`) in the architecture/plan docs now, so a future implementer isn't exposed to the 1.0/2.0/2.5/3.0 API churn.
- Do not port any 1.0/2.0-style code that passes a `freq` argument -- the 2.5 API removed it entirely and will error or behave unexpectedly if treated as an optional parameter.
- Note in docs that TimesFM's own weight download (from Hugging Face, no key required) is a one-time setup dependency separate from the 'free, keyless, public' market-data sourcing rule -- it should not be conflated with the Coinbase/Kraken ingestion constraint.
- If an adapter implementation is ever built, explicitly size `ForecastConfig(max_context=..., max_horizon=...)` to the real OHLCV window rather than relying on the model card's small example defaults (1024/256), since the real ceiling is much higher (16,384/1,000).

**current version:** TimesFM 3.0 (PyPI package timesfm 3.0.2, checkpoint google/timesfm-3.0-pytorch); prior Apache-2.0-licensed checkpoint TimesFM 2.5 (google/timesfm-2.5-200m-pytorch) remains available and is the recommended reference for this build

**api surface**
- pip install timesfm[torch]  (keyless, open-weights; pip install timesfm[mlx] for Apple Silicon)
- import timesfm; model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
- model.compile(timesfm.ForecastConfig(max_context=<window_len>, max_horizon=<horizon>, normalize_inputs=True, use_continuous_quantile_head=True, fix_quantile_crossing=True))
- point_forecast, quantile_forecast = model.forecast(horizon=H, inputs=[series])  -- used only as the referenced 'naive baseline/TimesFM' comparator named in the validation-gate spec (criterion 12); no implementation is built in this phase
- No freq/frequency argument in the 2.5 API (present and required as {0,1,2} in 1.0/2.0)

**pitfalls**
- Breaking change: TimesFM 2.5 removed the mandatory 'freq' categorical argument used by 1.0/2.0 -- code written against the older API will not match the 2.5 call signature.
- API class names are not stable across versions (TimesFm -> TimesFM_2p5_200M_torch -> TimesFM3Evaluator); pin an exact package version and checkpoint id rather than following generic 'timesfm' examples.
- TimesFM 3.0's pretrained weights carry a non-commercial-only license (timesfm-non-commercial-license-v1.0); self-hosted commercial/production use is prohibited, only Google Cloud BigQuery ML/Vertex deployments are permitted commercially -- 2.5 and earlier weights remain Apache-2.0 and are safer for an openly licensed research tool.
- Model card example configs understate the model's real ceiling (example shows max_context=1024/max_horizon=256 while the architecture supports up to 16,384 context / 1,000 horizon) -- must be explicitly configured, not assumed from the quickstart snippet.
- All HF checkpoints are explicitly marked 'not an officially supported Google product' -- no support SLA.
- First run downloads multi-hundred-MB weights from Hugging Face; this is a network dependency even though no API key or payment is required, which should not be conflated with the build's 'free, keyless, public' market-data sourcing rule.

*As of: Checked 2026-11-24. PyPI timesfm package version 3.0.2 (released ~Sep 2026 per PyPI); HF checkpoint google/timesfm-2.5-200m-pytorch last updated Oct 2, 2025; HF checkpoint google/timesfm-3.0-pytorch listed as updated 'Sep 2' (2026) in the HF collection page; GitHub README reviewed live at the same date.*

**Sources**
- [google-research/timesfm (official GitHub repository README)](https://github.com/google-research/timesfm) (official-docs) -- "pip install timesfm[torch] ... TimesFM 2.5 ... gets rid of the frequency indicator ... supports up to 16k context length, up from 2048 ... TimesFM 3.0 pretrained weights are distributed under the separate timesfm-non-commercial-license-v1.0 license and are restricted to non-commercial, non-production use."
- [google/timesfm-2.5-200m-pytorch (Hugging Face model card)](https://huggingface.co/google/timesfm-2.5-200m-pytorch) (official-docs) -- "max_context=1024, max_horizon=256 ... This checkpoint is not an officially supported Google product. ... license: apache-2.0"
- [google/timesfm-1.0-200m-pytorch (Hugging Face model card)](https://huggingface.co/google/timesfm-1.0-200m-pytorch) (official-docs) -- "Both forecast methods expect (1) the input time series contexts, (2) along with their frequencies ... a max context length of 512 ... Please visit our GitHub repo and follow the instructions there to install the timesfm library."
- [timesfm · PyPI](https://pypi.org/project/timesfm/) (official-docs) -- "a pretrained time-series foundation model developed by Google Research for time-series forecasting ... Extras: torch, mlx, flax, xreg"
- [TimesFM Release collection (Hugging Face)](https://huggingface.co/collections/google/timesfm-release-66e4be5fdb56e960c1e482a6) (official-docs) -- "google/timesfm-3.0-pytorch ... 0.3B params ... google/timesfm-2.5-200m-pytorch ... updated Oct 2, 2025 ... google/timesfm-1.0-200m-pytorch ... updated Aug 29, 2024"


### Official documentation: Inkling 2 Small (Thinking Machines)
*Find the OFFICIAL documentation for "Inkling 2 Small (Thinking Machines)": its current stable version, how it is installed or enabled, the API surface this build will use, and any breaking changes or pitfalls in the last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].*

Inkling 2 Small is a real, recently-released (Nov 2026) multimodal Mixture-of-Experts LLM from Thinking Machines Lab (594B total / ~17-18B active parameters, up to 1M-token context), distributed under Apache 2.0 via Hugging Face, the Tinker/Cookbook SDK, and third-party inference hosts including Cloudflare Workers AI. However, nothing in the locked PRD for the crypto Shariah backtest rig (OHLCV ingestion, screening, buy-and-hold backtest, HTML report, signal-adapter contract-only stub) calls for an LLM inference model at all -- there is no stated component, API call, or acceptance criterion that this build would exercise. The build's constraints (free, keyless, public data; no HFT/live/adapter code built yet; signal-adapter is a type/contract only, no implementation) are also incompatible with a 594B-parameter model that requires 500GB+ aggregated GPU VRAM or a paid API tier.

**Key findings**
- Inkling 2 Small is a Mixture-of-Experts multimodal model: 594B total parameters, ~17B (model card) / 18B (Cloudflare) active parameters per token, context window up to 1,048,576 tokens, released per its official model card on 2026-11-05.
- License is Apache 2.0; weights are hosted on Hugging Face at thinkingmachines/Inkling-2-Small.
- Native NVFP4 checkpoint requires >=500GB aggregated VRAM (e.g. 2x NVIDIA B300 or 4x NVIDIA H200); MXFP8 variant requires >=800GB VRAM -- this is datacenter-class hardware, not a laptop/CI box.
- Local/self-hosted serving is via SGLang (`python3 -m sglang.launch_server --model-path thinkingmachines/Inkling-2-Small`), vLLM (`vllm serve thinkingmachines/Inkling-2-Small`), Docker (`docker model run hf.co/thinkingmachines/Inkling-2-Small`), or the `transformers` library (AutoProcessor/AutoModelForMultimodalLM).
- Thinking Machines' own 'Tinker' workflow requires `uv pip install tinker-cookbook` and setting `model_name = "thinkingmachines/Inkling-2-Small"`; it depends on a separate `tml_renderers` package for prompt formatting.
- Cloudflare Workers AI hosts it as `@cf/thinkingmachines/inkling-2-small`, exposed via an OpenAI-compatible `/v1/chat/completions` endpoint and the native Cloudflare AI run endpoint; pricing is $0.30/M input tokens, $1.00/M output tokens, $0.10/M cached input tokens, with zero data retention; explicitly NOT available on Cloudflare's free tier -- it requires the Workers Paid plan or prepaid AI Gateway credits.
- No version-history, changelog, or 'breaking changes' section is published on either the Hugging Face model card or the Cloudflare docs page; both state no prior version history is documented for this specific checkpoint.
- No part of this model's API surface (chat/completions, SGLang/vLLM serving, Tinker Cookbook) maps to any acceptance criterion, module, or data flow in the locked crypto Shariah backtest PRD -- there is no ingestion, screening, backtest, or reporting step in that PRD that specifies calling an LLM.

**Recommendations**
- Do not integrate Inkling 2 Small (or any Thinking Machines model) into this build -- it has no role in OHLCV ingestion, fiqh screening, the equal-weight backtest, or HTML report generation as specified, and pulling it in would violate the 'free, keyless, public data' and 'no HFT/live/adapter code' constraints (it needs paid hosting or 500GB+ VRAM).
- If this research item was intended to cover a different dependency (e.g. the LLM used to help author the fiqh-register text, or the coding agent building the repo itself), flag that back to the planner/user for clarification rather than forcing a fit here.
- If a future phase genuinely needs an LLM-backed signal adapter, treat it as out of scope for the current phase: the PRD already specifies the signal-adapter seam is contract/type-only with no implementation, so no model (Inkling or otherwise) should be wired in yet.
- Treat the version/date facts above as correct only as of the pages fetched on 2026-11-24; re-verify before any future use since the Hugging Face and Cloudflare pages carry no changelog and this is a very recently released model.

**current version:** Inkling 2 Small [uncertain] -- no explicit semantic version number is published on any official page opened; the model name/checkpoint identifier itself (released 2026-11-05 per the model card) is the only version marker available.

**api surface**
- None of this build's acceptance criteria call for this API; documented purely because it was the research item -- if ever used it would be: Hugging Face `transformers` AutoModelForMultimodalLM.from_pretrained('thinkingmachines/Inkling-2-Small')
- SGLang server: `python3 -m sglang.launch_server --model-path thinkingmachines/Inkling-2-Small`
- vLLM server: `vllm serve thinkingmachines/Inkling-2-Small`
- Tinker Cookbook: `uv pip install tinker-cookbook`, then `model_name = "thinkingmachines/Inkling-2-Small"`
- Cloudflare Workers AI OpenAI-compatible endpoint: POST to `/v1/chat/completions` or `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/thinkingmachines/inkling-2-small` (requires paid plan)

**pitfalls**
- Requires >=500GB aggregated GPU VRAM (NVFP4) or >=800GB (MXFP8) for self-hosting -- infeasible for a free/local research rig.
- Not available on Cloudflare Workers AI's free billing tier; needs Workers Paid plan or prepaid AI Gateway credits, conflicting with the build's 'free, keyless' data/tooling constraint.
- No published changelog, version history, or breaking-changes notes were found on the Hugging Face card or Cloudflare docs page, so prior-version compatibility risk cannot be assessed from official sources.
- This item appears unrelated to any module, API, or acceptance criterion in the locked PRD; treat as a likely planning mismatch rather than a dependency to integrate.

*As of: 2026-11-24 (model card states release date 2026-11-05; no prior version history published)*

**Sources**
- [Inkling 2 Small Model Card - Thinking Machines Lab](https://thinkingmachines.ai/model-card/inkling-2-small/) (official-docs) -- "Model: Inkling 2 Small; Release Date: November 5, 2026; Provider: Thinking Machines Lab, Inc.; Architecture: 48-layer decoder-only transformer with sparse Mixture-of-Experts (MoE); Parameters: 594B total; 17B active per token"
- [inkling-2-small (Thinking Machines) · Cloudflare Workers AI docs](https://developers.cloudflare.com/workers-ai/models/inkling-2-small/) (official-docs) -- "Model ID: @cf/thinkingmachines/inkling-2-small; Architecture: Mixture-of-Experts with 594B total and 18B active parameters; This model is not available through standard Workers Free billing."
- [thinkingmachines/Inkling-2-Small · Hugging Face](https://huggingface.co/thinkingmachines/Inkling-2-Small) (official-docs) -- "vllm serve "thinkingmachines/Inkling-2-Small" ... The model demands a GPU cluster with at least 500GB of aggregated VRAM ... License: Apache 2.0"
- [Using Inkling - Tinker Documentation - Thinking Machines Lab](https://tinker-docs.thinkingmachines.ai/cookbook/inkling/) (official-docs) -- "To set up Inkling, install the Cookbook package: uv pip install tinker-cookbook ... Set model_name = "thinkingmachines/Inkling-2-Small" in your Cookbook workflow"


### Official documentation: gods-eye-view
*Find the OFFICIAL documentation for "gods-eye-view": its current stable version, how it is installed or enabled, the API surface this build will use, and any breaking changes or pitfalls in the last 3 years (prioritise 2024 [OSA: truncated, the planner wrote 101 characters].*

"gods-eye-view" (github.com/bilawalsidhu/gods-eye-view) is an open-source, browser-based 3D geospatial intelligence globe that visualizes live public flights, ships, satellites, weather, earthquakes, and street/traffic cameras using CesiumJS, Vue 3, and Google Photorealistic 3D Tiles. It is unrelated to cryptocurrency price data, Shariah screening, backtesting, or OHLCV ingestion of any kind, and has no overlap with the Mizan crypto-Shariah-backtest build's requirements (Coinbase/Kraken OHLCV fetch, DuckDB storage, fiqh screening, equal-weight backtest, HTML report, hard-rule invariants, signal-adapter contract). There is no legitimate API surface from this project for this build to consume; it is a geospatial visualization app, not a financial-data or backtesting library.

**Key findings**
- Official repo is bilawalsidhu/gods-eye-view on GitHub, tagline: 'a spy satellite simulator in your browser, except the data is real', official site godseyeview.ai
- Requires Node.js 24.14.0+ or 26.x; install via `git clone`, `npm ci`, `npm run dev`, or via Pinokio desktop app 8.2+, or `docker compose up`
- App serves locally at http://localhost:4173 and requires no API keys to start exploring at a basic level
- It integrates 23 live-data layers: no-key sources (OpenSky flights, adsb.lol, USGS earthquakes, CelesTrak satellites, OSRM, NOAA/ECMWF weather, OSM-based ALPR cameras, NASA FIRMS fires), free-key-tier sources (AISStream ships, TomTom traffic, Cesium ion terrain, Mapillary, World News API), and metered-key sources (Google Maps 3D tiles/place search, OpenAI voice/chat)
- API keys, when needed for free-key or metered layers, are configured via an in-app 'POWER UP' panel or a repository-root .env file; none of these keys relate to financial/crypto data providers
- The README notes that older builds fail against OpenStreetMap Overpass servers for the Traffic/Mapped Installations layers and recommends updating to the latest version to restore them
- Core stack is Vue 3, Pinia, CesiumJS, and Vite — a frontend geospatial visualization stack, not a data-ingestion, backtesting, or quant-finance library
- No cryptocurrency, OHLCV, exchange, or Shariah/fiqh-related functionality exists anywhere in this project's documented feature set or API list

**Recommendations**
- Do not integrate gods-eye-view into the Mizan build in any form; it provides no OHLCV/exchange/finance API and has no bearing on acceptance criteria 1-15
- Treat this research item as a mismatch between the planner's item name and the actual build requirements; flag to the planner that 'gods-eye-view' does not correspond to any dependency needed for crypto OHLCV ingestion, DuckDB storage, Shariah screening, backtesting, or the signal-adapter contract
- For the actual build, continue sourcing OHLCV data from Coinbase (primary) and Kraken (fallback) as already locked in the PRD — this item surfaced no alternative or complementary data source worth adopting
- If the planner intended a different tool (e.g., a monitoring/dashboard library with a similar name), re-issue the research item with the correct, verified tool name before relying on any findings here

**current version:** No numbered stable release found; distributed as a continuously updated main-branch repo (Node 24.14.x/26.x compatible, MIT-licensed as of 2026-08-24) — not applicable to this build

**api surface**
- Not applicable: this project exposes no financial-data, exchange, backtesting, or Shariah-screening API and will not be called by the Mizan build
- If ever embedded only as an unrelated visualization demo (out of scope), its only relevant surface is `npm run dev` (local Vite dev server on :4173) and optional `.env` keys for OpenSky/AISStream/TomTom/Cesium ion/Mapillary/Google Maps/OpenAI — none of which are financial data providers

**pitfalls**
- Entirely unrelated domain (geospatial/ADS-B/AIS/satellite tracking) to the crypto-Shariah backtest build; adopting it would violate the PRD's constraint that data sources be relevant, free, keyless, and licensed for OHLCV ingestion
- Project requires Node 24.14+/26.x and, for several layers, third-party API keys (TomTom, Cesium ion, Mapillary, World News API, Google Maps, OpenAI) that are out of scope and unrelated to Coinbase/Kraken OHLCV
- Older builds reportedly break against OpenStreetMap Overpass endpoints for specific layers — irrelevant to this build but noted as the only documented 'breaking change' in the project's README

*As of: README.md content as fetched 2026-11-24; repository described as released under MIT license on 2026-08-24*

**Sources**
- [bilawalsidhu/gods-eye-view README.md](https://github.com/bilawalsidhu/gods-eye-view/blob/main/README.md) (official-docs) -- "God's Eye View is an open-source, browser-based 3D globe that visualizes real-time public signals including aircraft, ships, satellites, weather, and public cameras... requires no API keys to begin exploring."
- [GitHub - bilawalsidhu/gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view) (repo) -- "God's Eye View: a spy satellite simulator in your browser, except the data is real. Live open source spatial intelligence on a photorealistic 3D globe. Official site: godseyeview.ai"


### Coinbase public OHLCV candle retrieval
*Which free, keyless Coinbase endpoint returns daily OHLCV candles for these tokens, what are its granularity options, rate limits, pagination and maximum available history?*

Coinbase offers two keyless, no-API-key public endpoints that return daily OHLCV candles: the legacy Exchange API `GET https://api.exchange.coinbase.com/products/{product_id}/candles` and the newer Advanced Trade public market-data endpoint `GET https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/candles` (public endpoints added 2024-04-09). Both expose `security: []` (no auth) in their official OpenAPI specs. For a crypto-first daily-candle ingestion layer with a future-proof granularity parameter, the Advanced Trade public candles endpoint is the better default: it supports a named granularity enum including `ONE_DAY` plus intraday options, returns up to 350 candles per call, and start/end are plain unix-timestamp window bounds rather than a response pagination token, so multi-year history must be built by walking the window backward in a loop.

**Key findings**
- Legacy Coinbase Exchange public candles endpoint `GET https://api.exchange.coinbase.com/products/{product_id}/candles` requires no authentication (OpenAPI `security: []`), per the official CDP API reference.
- Legacy Exchange API granularity enum is in seconds: 60, 300, 900, 3600, 21600, 86400 (1m, 5m, 15m, 1h, 6h, 1d); daily candles use granularity=86400.
- Legacy Exchange API caps each request at a maximum of 300 candles; a start/end+granularity combination yielding more than 300 points is rejected and must be split into multiple sequential requests (no cursor token is returned, only a plain array).
- Official Coinbase Exchange public-endpoint rate limit is 10 requests/second per IP sustained, with bursts allowed up to 15 requests/second per IP, enforced via a token-bucket algorithm, per the official CDP rate-limits documentation.
- The newer Advanced Trade public market-data candles endpoint `GET https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/candles` also requires no authentication (OpenAPI `security: []`) and was published as part of Coinbase's public market-data endpoints released 2024-04-09.
- Advanced Trade public candles granularity enum is named-string based and includes ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, TWO_HOUR, FOUR_HOUR, SIX_HOUR, ONE_DAY; daily candles use granularity=ONE_DAY.
- Advanced Trade public candles endpoint returns up to 350 candles per request (default and max 350 via the `limit` parameter); `start` and `end` are unix timestamps defining the query window, not pagination cursors, so full history requires repeated calls sliding the window backward.
- Neither the Exchange API nor the Advanced Trade API official reference pages state a fixed maximum historical lookback depth (e.g., N years); available depth is bounded only by each product's own listing/trading-start date on Coinbase, so full-history daily backfill must be discovered at run time by walking the window back until responses go empty [uncertain].

**Recommendations**
- Default the Coinbase fetcher to the Advanced Trade public market-data candles endpoint (`/api/v3/brokerage/market/products/{product_id}/candles`) with granularity=ONE_DAY, since it is the current, documented, keyless public path and its named granularity enum (vs. legacy raw-seconds enum) maps more cleanly onto a future non-daily granularity parameter required by acceptance criterion #3.
- Implement pagination as a backward-walking loop over `start`/`end` unix-timestamp windows (max 350 candles per call on Advanced Trade, 300 on legacy Exchange API) rather than assuming a cursor/next-page token exists in the response — none is documented.
- Add client-side rate limiting/backoff targeting the documented public-endpoint limit of 10 req/s (burst 15 req/s) and handle HTTP 429 with retry/backoff, since both Coinbase API families share this public rate-limit tier.
- Do not assume a fixed maximum history window; discover each token's earliest available daily candle by walking the start/end range backward until the endpoint returns zero candles, and log/report per-token data-start dates for the survivorship-bias warning required in the HTML report.
- For any of the 14 named tokens not listed on Coinbase, or with materially shorter history there than on Kraken, apply the build's documented Kraken-fallback rule rather than silently accepting a short Coinbase series.

*As of: Accessed 2026-11-24 against the current Coinbase Developer Platform (CDP) API reference docs for both the Exchange API and the Advanced Trade API; the Advanced Trade public market-data endpoints are separately documented as introduced on 2024-04-09.*

**Sources**
- [Get Product Candles - Exchange API Reference - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles) (official-docs) -- "The maximum number of data points for a single request is 300 candles... The allowed granularity values are: {60, 300, 900, 3600, 21600, 86400}... security: [] (no authentication required)"
- [REST Rate Limits Overview - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits) (official-docs) -- "Requests per second per IP: 10 (sustained); Burst rate: Up to 15 requests per second per IP, enforced via a token bucket algorithm"
- [Get Public Product Candles - Advanced Trade API Reference - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles) (official-docs) -- "security: [] ... Supported granularity values: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, TWO_HOUR, FOUR_HOUR, SIX_HOUR, ONE_DAY ... By default, returns 350 (max 350)"


### Granularity-agnostic candle storage in DuckDB
*How to schema and ingest OHLCV in DuckDB so the same path serves daily now and intraday/order-book later without migration?*

Use a single wide 'candles' table keyed by (exchange, symbol, granularity, ts) rather than one table per timeframe or per asset class: granularity is just a VARCHAR/ENUM dimension column alongside the OHLCV fields, so adding intraday or order-book-derived bars later means inserting new rows with a different granularity value into the same schema -- no ALTER TABLE or migration. Store ts as native TIMESTAMP (UTC), not VARCHAR, for both correctness and a documented ~10x speed/space win in DuckDB. For idempotent re-ingestion, declare the natural key as a composite PRIMARY KEY/UNIQUE constraint up front (data volume here is tiny -- 14 tokens x a few years of daily bars) and write with DuckDB's native 'INSERT OR REPLACE' (built on ON CONFLICT), which requires that constraint to exist as the conflict target. Keep trades/order-book data in a separate table with its own natural columns (side, level, price, amount) joined by the same (exchange, symbol, ts) convention, rather than cramming it into the OHLCV table; this is the pattern used by existing DuckDB-based crypto market-data projects (vgi-ccxt, the-rule-and-compass) specifically to avoid schema migrations when new granularities or data types are added.

**Key findings**
- DuckDB official performance guide (docs v2.0, 'Schema' page): use native types (BIGINT, DATE, DATETIME) not VARCHAR for columns like timestamps -- on a 554M-row benchmark, DATETIME processed in 0.19s vs 1.85s for VARCHAR (~10x), with 37% smaller storage (3.3 GiB vs 5.3 GiB).
- Same DuckDB guide: 'For best bulk load performance, avoid primary key constraints... if they are required, define them after the bulk loading step' -- their microbenchmark showed loading with PK = 159.3s vs without PK = 45.0s vs load-then-add-PK = 77.5s. At this build's scale (14 symbols x daily bars) this cost is negligible, so defining the composite PK upfront for idempotency is the right tradeoff here.
- DuckDB 'INSERT' statement docs (v1.3): 'INSERT OR REPLACE INTO tbl VALUES (...)' is shorthand for INSERT ... ON CONFLICT DO UPDATE SET col=EXCLUDED.col for every column; 'An ON CONFLICT clause can be used to perform a certain action on conflicts that arise from UNIQUE or PRIMARY KEY constraints' -- i.e. a declared PK/UNIQUE on (exchange, symbol, granularity, ts) is required for idempotent re-runs to work.
- DuckDB date functions docs (v2.0): time_bucket(bucket_width, date[, offset|origin]) truncates a timestamp onto a fixed-width grid (e.g. time_bucket(INTERVAL '2 months', DATE '1992-04-20', INTERVAL '1 month') -> '1992-04-01'); date_trunc(part, date) truncates to a named precision and always returns TIMESTAMP. These are the native tools for deriving coarser candles from finer stored rows without duplicating storage.
- vgi-ccxt (GitHub, Query-farm, DuckDB+CCXT table functions for 100+ exchanges): its ohlcv() function signature returns columns 'exchange, symbol, timeframe, ts, open, high, low, close, volume' -- timeframe/granularity is modeled as a value/column, not a separate table or schema; trades and order-book data are separate functions with their own distinct column shapes (trade_id/side/price/amount/taker_or_maker for trades; side/level/price/amount for order book), joined via (exchange, symbol, ts).
- the-rule-and-compass issue #125 (GitHub, 'first-class OHLCV market-data layer'): proposes a canonical model (timestamp, OHLC, volume, quote volume, trades, taker-buy base/quote) with timeframe and calendar as explicit dimensions; recommends materializing only the timeframes actually used as derived views/aggregates from a canonical finest-grain base table rather than one table per timeframe, explicitly to support adding granularities 'without migration'; stores prices/volume as integer minor units to keep resampling exact; treats calendars as append-only session-ledger tables rather than hardcoded rules.
- jssyxd/multi-asset-ohlcv (GitHub, monthly Parquet shards for 24 assets): uses a directory/partition convention of {SYMBOL}-{INTERVAL}/{SYMBOL}/{YEAR}/{YEAR}_{interval}.parquet with nanosecond-integer UTC timestamps (ts_event, ts_init) and enforces 'zero duplicate timestamps' plus monotonic ts_event <= ts_init ordering as its dedup/causality invariant -- useful as a cache/raw-file-tier convention alongside the DuckDB store, complementing rather than replacing the DB schema.

**Recommendations**
- Create one table, e.g. candles(exchange VARCHAR, symbol VARCHAR, granularity VARCHAR, ts TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, source VARCHAR, ingested_at TIMESTAMP, PRIMARY KEY(exchange, symbol, granularity, ts)). Granularity is a plain string value ('1d' today, '1h'/'1m'/'orderbook_snapshot' later) -- this is the whole mechanism that makes the ingestion layer's granularity parameter 'work without code changes' per acceptance criterion 3.
- Write with 'INSERT OR REPLACE INTO candles VALUES (...)' for every ingestion run so re-running the pipeline is idempotent and never duplicates rows; this depends on the PK above existing as the conflict target.
- Keep ts as native UTC TIMESTAMP (bucket start, e.g. midnight UTC for daily bars), never VARCHAR -- matches the documented DuckDB performance/storage advantage and avoids later type-migration pain when intraday timestamps need sub-day precision.
- Do not build per-timeframe tables or per-asset-class tables now. When intraday/order-book data is added later, (a) continue inserting OHLCV rows into the same candles table with a new granularity value, and (b) if/when order-book or trade-level data is needed, add a separate orderbook/trades table keyed by (exchange, symbol, ts, ...) rather than widening candles -- this mirrors the vgi-ccxt and the-rule-and-compass separation and keeps the OHLCV schema stable.
- Favor deriving any coarser candle the pipeline might want later (e.g. a weekly rollup for display) via DuckDB's time_bucket()/date_trunc() over the stored finest-grain rows, instead of pre-materializing and storing every possible granularity -- avoids storage duplication and keeps 'granularity-agnostic' meaning 'one source table, computed views', not 'many stored tables'.
- Given the trivial row count in this build (14 symbols x a few years of daily candles, likely low thousands of rows), do not defer the PRIMARY KEY for bulk-load speed as the general DuckDB guide suggests for large loads -- the correctness/idempotency benefit dominates at this scale; revisit only if/when minute-level or order-book ingestion pushes row counts into the millions.
- Mirror the existing raw-cache file convention (acceptance criterion 2 requires writing to both raw cache and DuckDB) using a path shape keyed by symbol and granularity (e.g. raw/{exchange}/{symbol}/{granularity}/...), consistent with the {SYMBOL}-{INTERVAL} partitioning seen in multi-asset-ohlcv, so the file cache and the DB share the same addressing scheme and neither needs restructuring when new granularities are added.

*As of: DuckDB docs: 'performance/schema' and 'sql/statements/insert' (v1.3/v2.0 branches of duckdb.org/docs) and 'sql/functions/date.html' (v2.0 branch), all accessed 2026-11-24; GitHub repos/issues (Query-farm/vgi-ccxt, a-holm/the-rule-and-compass#125, jssyxd/multi-asset-ohlcv) as retrieved 2026-11-24, reflecting 2024-2025-era design patterns -- no ccxt-specific manual facts were used since that fetch failed (ECONNRESET) and was not independently verified.*

**Sources**
- [DuckDB Docs -- Performance Guide: Schema](https://duckdb.org/docs/2.0/guides/performance/schema.html) (official-docs) -- "For best bulk load performance, avoid primary key constraints... They very rarely improve the performance of queries as DuckDB does not rely on these indexes for join and aggregation operators."
- [DuckDB Docs -- INSERT Statement](https://duckdb.org/docs/1.3/sql/statements/insert) (official-docs) -- "INSERT OR REPLACE INTO tbl VALUES (1, 84); ... An ON CONFLICT clause can be used to perform a certain action on conflicts that arise from UNIQUE or PRIMARY KEY constraints."
- [DuckDB Docs -- Date Functions (time_bucket, date_trunc)](https://duckdb.org/docs/2.0/sql/functions/date.html) (official-docs) -- "time_bucket(bucket_width, date[, offset]) ... Truncate date to a grid of width bucket_width ... date_trunc(part, date) ... Always returns a TIMESTAMP, even when the input is a DATE."
- [Query-farm/vgi-ccxt (GitHub)](https://github.com/Query-farm/vgi-ccxt) (repo) -- "exchange, symbol, timeframe, ts, open, high, low, close, volume"
- [a-holm/the-rule-and-compass, Issue #125: first-class OHLCV market-data layer](https://github.com/a-holm/the-rule-and-compass/issues/125) (repo) -- "only...timeframes actually used ... materializes derived views from a canonical 1-minute base ... prices as integer ticks and volume as integer minor units"
- [jssyxd/multi-asset-ohlcv (GitHub)](https://github.com/jssyxd/multi-asset-ohlcv) (repo) -- "catalog/data/bar/{SYMBOL}-{INTERVAL}/{SYMBOL}/{YEAR}/{YEAR}_{interval}.parquet ... zero duplicate timestamps"


### Equal-weight buy-and-hold with periodic rebalance and realistic costs
*Standard conventions for periodic-rebalance equal-weight long-only backtests and correct application of per-side taker fees plus slippage over a 24/7 market clock?*

The standard convention for equal-weight long-only crypto backtests with periodic rebalancing is: set target weights equal at each rebalance date, let them drift intra-period, then force sells of outperformers and buys of underperformers back to equal weight (this mean-reversion mechanism is what generates any 'rebalancing premium'). Costs are applied per leg/per order — a taker fee as a percentage of notional on every buy AND every sell (so a round-trip rebalance pays the fee twice), plus slippage as an additional adverse percentage move on the fill price (buys fill higher, sells fill lower), both applied at the moment of execution, not netted across the portfolio. Coinbase's lowest-tier (<$10k 30-day volume) taker fee of 0.60% matches the PRD's stated default exactly, which is the appropriate conservative, no-API-key-tier assumption for a backtest. Because crypto trades 24/7 with no exchange holidays, backtesting frameworks (e.g. vectorbt) index candles continuously by UTC calendar date/timestamp rather than a business-day trading calendar — every day is a potential rebalance day, so 'daily candles, periodic (e.g. weekly/monthly) rebalance' needs no special gap-handling logic. Academic work on crypto rebalancing premium (Quantpedia, 2018–2021 sample) shows daily/monthly rebalancing beating buy-and-hold on raw returns and Sharpe, but that specific study explicitly ignores transaction costs — which is the gap this build's cost-aware backtest should close rather than replicate.

**Key findings**
- Coinbase Advanced Trade taker fee at the lowest 30-day-volume tier (<$10,000) is 0.60%, rising with volume tiers and dropping toward ~0% at institutional tiers (>$300M/month) [opened source: makervstakerfee.org, corroborated by independent search summaries].
- Kraken's entry-tier spot taker fee is reported at 0.80% (vs ~0.40% maker) under a cross-platform tier structure effective July 9, 2026, per an aggregator page last updated Aug 24, 2026 — this is a secondary/aggregator source, not Kraken's own fee page (official kraken.com fee-schedule page could not be fetched directly due to repeated connection errors), so treat the exact Kraken figure as [uncertain].
- vectorbt's fee/slippage convention (a de facto standard for vectorized crypto backtests) is: `fees` is a fraction of each order's notional value applied independently to every order (buy and sell each incur it — i.e. 'per side'), `fixed_fees` adds a flat per-order amount, and `slippage` is a percentage that moves the fill price adversely at execution time (buys fill higher, sells fill lower), applied after the fill decision, not before [opened source: vectorbt.pro docs].
- Quantpedia's study of 27 cryptocurrencies (Dec 2018–Oct 2021) found both daily- and monthly-rebalanced equal-weight portfolios outperformed buy-and-hold on cumulative return and Sharpe ratio, with daily rebalancing outperforming monthly — the mechanism is selling relative winners and buying relative losers, capturing mean reversion [opened source: quantpedia.com]. The same source explicitly does not model transaction costs or slippage — a known limitation this build's backtest must not inherit, since fees applied on every rebalance leg can erase or reverse the apparent premium, especially at daily frequency.
- Search-only (not independently opened/verified) secondary findings on cost sensitivity: momentum-style crypto strategies have reported breakeven costs around 13–35 bps, with turnover-heavy rebalancing able to turn large gross returns negative once realistic costs are applied, and threshold/band-based rebalancing (e.g. 15–20% deviation bands) is sometimes used instead of fixed-calendar rebalancing specifically to control turnover and costs — these figures are [uncertain] since derived from WebSearch summaries, not pages I opened and read myself.
- Crypto backtesting libraries and exchanges operate on continuous 24/7 UTC daily candles with no trading-day/holiday calendar; rebalance scheduling in such systems is simply 'every Nth calendar day' rather than 'every Nth trading day,' since there is no concept of a market-closed day to skip.

**Recommendations**
- Apply the taker fee (default 0.6%) and slippage (default 0.05%) independently to every individual buy and every individual sell generated by the rebalance (per-leg, not netted), consistent with vectorbt's `fees`/`slippage` convention and the PRD's own 'per side' wording in acceptance criterion 6.
- Choose a rebalance period coarser than daily (e.g. weekly or monthly) by default for the baseline — daily rebalancing with 0.6% taker + 0.05% slippage per side will almost certainly make round-trip costs dominate any equal-weight rebalancing premium (Quantpedia's own result excluded costs entirely, so its daily-beats-monthly finding cannot be assumed to survive realistic frictions).
- Index the backtest clock on continuous UTC calendar days/timestamps (no trading-day calendar, no holiday gaps), matching the 24/7 nature of crypto markets and the PRD's acceptance criterion 13.
- Keep cost parameters (taker fee, slippage %) in config with non-zero defaults and a test asserting they are never silently defaulted to zero, per acceptance criterion 6 — this is the most common way such backtests silently overstate returns.
- Do not hard-code Coinbase's or Kraken's exact live fee schedule into the backtest cost model as if it were authoritative — those schedules are tiered by 30-day volume, change over time (Kraken's own schedule reportedly restructured in 2026), and are irrelevant to a keyless public-data research backtest; instead treat 0.6%/0.05% as a fixed, documented, conservative assumption independent of which venue the OHLCV candles came from.
- If/when threshold- or band-based rebalancing is considered later (outside this baseline), note it reduces turnover versus fixed-calendar rebalancing in cost-sensitive crypto research — but this is out of scope for the locked 'baseline equal-weight, periodic rebalance' requirement and should not be substituted in without being asked.

*As of: Fee and schedule figures as reported by secondary sources in November 2026 (Coinbase tier table via makervstakerfee.org; Kraken tier table via datawallet.com, article updated 2026-08-24, schedule described as effective 2026-07-09); vectorbt fee/slippage semantics per vectorbt.pro docs (undated, current site content); Quantpedia rebalancing-premium study covers crypto data Dec 2018–Oct 2021, article undated but reflects that historical window.*

**Sources**
- [Maker vs Taker Fee Coinbase: Advanced Trade Fee Schedule & How to Pay Less](https://www.makervstakerfee.org/maker-vs-taker-fee-coinbase/) (article) -- "Less than $10,000 | 0.60% ... The entry-level taker fee of 0.60% represents the lowest non-institutional tier rate."
- [Kraken Fees Explained: Spot, xStocks, Futures & Staking (2026)](https://www.datawallet.com/crypto/kraken-fees-explained) (article) -- "Tier 1 applies to $0+ in volume, with rates of 0.40% maker and 0.80% taker ... cross-platform tier structure implemented July 9, 2026."
- [Fees, slippage, and leverage in backtests — VectorBT PRO](https://vectorbt.pro/features/backtesting/fees-slippage-and-leverage/) (official-docs) -- "Slippage moves market-order fills adversely: buys fill higher and sells fill lower ... fees represents a fraction of each order's value."
- [Estimating Rebalancing Premium in Cryptocurrencies](https://quantpedia.com/estimating-rebalancing-premium-in-cryptocurrencies/) (article) -- "Daily and monthly rebalanced portfolios outperformed buy-and-hold ... the article does not address transaction costs, fees, or slippage."


### Pluggable forecasting-signal interface with provenance, calibration and abstention
*How to design a plugin/adapter contract that mandates licence/provenance metadata, calibrated probabilistic output, abstention, and a pass/fail validation gate before a signal can drive allocations?*

Build the signal-adapter contract as a Python `typing.Protocol` (PEP 544, Python 3.8+) rather than an ABC, since OSA only needs a type/interface definition with zero implementations and Protocols let future adapters satisfy the contract structurally without forced inheritance. The contract should require a provenance/licence block modeled on the Hugging Face model-card metadata spec (license, license_link/license_name, datasets/source identifiers), a `predict()` method returning a calibrated probability plus uncertainty (not a raw score), an explicit abstain/no-opinion return path drawn from the selective-prediction literature's coverage/risk framing, and a separate validation-gate spec modeled on champion/challenger promotion gates (DataRobot) and Google's 'ML Test Score' rubric: out-of-sample evaluation, calibration checking (Brier score / reliability diagrams per scikit-learn's calibration module), per-slice (token/regime) error breakdown, and a required beat of a naive baseline and TimesFM as the two reference forecasters. None of this needs an implementation yet — only the interface, metadata schema, and gate criteria, matching the PRD's 'contract, no implementation' requirement.

**Key findings**
- PEP 544 (Python 3.8+) defines `typing.Protocol` for structural subtyping: a class satisfies the protocol by implementing matching method signatures, with no inheritance required; `@runtime_checkable` enables optional `isinstance()` checks but the PEP notes these are 'not 100% reliable statically.'
- Community guidance (Belderbos, RealPython — 2024/2025 articles) converges on: use `Protocol` for the external plugin boundary (so third-party adapter authors aren't forced into your class hierarchy) and an internal ABC only if adapters need shared concrete helper code.
- Hugging Face's model-card YAML metadata spec (current as of its docs, 2026) is the most widely deployed provenance schema: `license`, `license_name`/`license_link` for custom licences, `datasets` (source identifiers), `base_model`, and a `model-index` block for structured eval results with a `source.url` field — a usable template for an adapter's provenance/licence metadata.
- Selective prediction / abstention literature frames abstention as a risk-coverage tradeoff: a model predicts only when a confidence threshold is met, otherwise abstains; Area Under the Risk-Coverage Curve (AURC) is the standard single-number metric, and recent work explicitly warns that accepted (non-abstained) predictions must still be separately checked for calibration — abstention and calibration are not the same property and both must be specified.
- scikit-learn's `calibration` module (stable docs) provides the standard calibration vocabulary the validation gate should reuse: reliability diagrams/calibration curves (predicted probability vs. observed frequency, binned) and `brier_score_loss`, with the explicit caveat that 'a lower Brier score does not always mean a better calibrated model' because it conflates calibration loss and refinement loss — the gate spec should require a calibration curve, not Brier score alone.
- Google's TimesFM paper (arXiv:2310.10688v2, dated 2024-01-31) benchmarks against a naive baseline defined as 'constantly predicts the last value in the context,' using mean-scaled MAE (scaled by the naive baseline's own MAE) averaged across datasets, and reports TimesFM beating naive and being statistically comparable to supervised baselines like PatchTST in zero-shot evaluation — this is the concrete naive-baseline definition and metric the PRD's 'beat TimesFM/naive baseline' gate should cite.
- Google's 'ML Test Score' paper (Breck et al., research.google.com, pub45742) defines a 28-item production-readiness rubric across 4 sections including 'test against a simpler model as a baseline,' 'test model quality on important data slices,' and 'test model quality before serving' — directly supporting a per-regime/per-token slice requirement and a pre-serving validation gate as standard MLOps practice, not an OSA-specific invention.
- DataRobot's Challengers feature (docs.datarobot.com, v11.0 docs) requires the comparison dataset to be explicitly out-of-sample for both the champion and challenger models before a 'Promote to champion' action is enabled, and generates accuracy metrics, dual-lift charts, and ROC curves as the comparison artifacts — a concrete precedent for a pass/fail gate UI/workflow, though DataRobot itself leaves the actual threshold decision to the user rather than enforcing an automatic pass/fail.

**Recommendations**
- Define the adapter contract as a `typing.Protocol` (not an ABC) with a frozen/dataclass metadata object required at construction time: `source: str`, `licence: str`, `licence_url: str | None`, `data_provenance: str` — mirroring the Hugging Face `license`/`license_name`/`license_link`/`datasets` fields — so provenance is declared, not optional.
- Make the core prediction method return a typed result carrying both a calibrated probability (or probability distribution/quantiles) AND an explicit abstain flag/sentinel, e.g. `Signal = probability: float, uncertainty: float, abstained: bool` — do not conflate 'low confidence' with 'no output'; the abstain path must be a distinct, non-numeric return per the selective-prediction literature.
- Specify the validation gate as its own dataclass/spec (not code) requiring: (1) out-of-sample evaluation window disjoint from any fitting data, (2) a calibration check via reliability-diagram-style binned comparison (not Brier score alone, since Brier conflates calibration and refinement per sklearn's own docs), (3) per-token and per-regime error breakdown as separate rows, not an aggregate, and (4) a required beat of both a naive last-value baseline and TimesFM using the same scaled-MAE style metric TimesFM's own paper uses, so the comparison is apples-to-apples with published numbers.
- Treat the validation gate as pass/fail against pre-declared thresholds (unlike DataRobot's user-driven promotion), since the PRD requires a gate that blocks allocation-driving use automatically, not a human-reviewed dashboard.
- Do not implement any adapter, scoring code, or TimesFM integration now — acceptance criteria 11-12 only require the interface/dataclass definitions and the written gate spec; building real adapters would violate the 'no HFT/live/adapter code' constraint and the two-speed roadmap boundary.
- Keep the contract in the 'fast layer' documentation seam only — the PRD explicitly forbids building live/adapter code in this phase, so the Protocol definition and gate spec should live as typed stubs/interfaces plus a markdown spec, with no concrete forecaster wired to the backtest or allocation logic.

*As of: 2026-11 (TimesFM paper dated 2024-01-31; PEP 544 landed Python 3.8; Hugging Face model-card docs and scikit-learn calibration docs reflect their current/stable pages as fetched; DataRobot docs version 11.0)*

**Sources**
- [PEP 544 – Protocols: Structural subtyping (static duck typing)](https://peps.python.org/pep-0544/) (official-docs) -- "instance checks are not 100% reliable statically, this is why this behavior is opt-in"
- [Model Cards · Hugging Face](https://huggingface.co/docs/hub/model-cards) (official-docs) -- "You can specify the license in the model card metadata section... If required, you can also specify a custom license by adding `other` as the license value and specifying the name and a link to the license"
- [Selective Prediction: Coverage, Risk, and Abstention](https://insightful-data-lab.com/2025/03/28/selective-prediction/) (article) -- "Risk-coverage curves (RCC) plot the compromise between coverage and error rate against changes in the confidence threshold, with Area Under the Risk-Coverage Curve (AURC) emerging as a single measure for comparing models."
- [A decoder-only foundation model for time-series forecasting (TimesFM)](https://arxiv.org/html/2310.10688v2) (paper) -- "just constantly predicts the last value in the context for each time-series... mean scaled MAE's are averaged across all datasets"
- [1.16. Probability calibration — scikit-learn documentation](https://scikit-learn.org/stable/auto_examples/calibration/plot_calibration_curve.html) (official-docs) -- "a lower Brier score does not always mean a better calibrated model... the Brier score metric is a combination of calibration loss and refinement loss"
- [The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction](https://research.google.com/pubs/archive/aad9f93b86b7addfea4c419b9100c6cdd26cacea.pdf) (paper) -- "a set of 28 actionable tests... test against a simpler model as a baseline, and testing model quality on important data slices"
- [Challengers tab — DataRobot docs (v11.0)](https://docs.datarobot.com/11.0/en/docs/mlops/monitor/challengers.html) (official-docs) -- "select a dataset for generating insights on both models... recommends using holdout or validation partitions, or uploading a fresh dataset"
- [Protocol or ABC? Designing a pluggable provider interface — Bob Belderbos](https://belderbos.dev/blog/protocol-vs-abc-provider-interface/) (article) -- "A Protocol defines the contract, an ABC on the other hand, is just an implementation detail my providers happen to reuse."


### Out-of-sample calibration, per-subgroup error and baseline-beating validation
*What calibration metrics, proper scoring rules, regime/subgroup breakdowns and out-of-sample comparisons are required to show a signal beats a naive/TimesFM baseline rather than just fitting aggregate data?*

To credibly claim a signal beats a naive/TimesFM baseline rather than overfitting, the validation gate needs: (1) proper scoring rules evaluated out-of-sample -- CRPS or pinball/quantile loss for probabilistic forecasts, not just MAE/MSE on point forecasts; (2) explicit calibration checks (e.g. PIT histograms / reliability diagrams) since foundation models are known to be miscalibrated, especially at longer horizons; (3) a leakage-safe out-of-sample protocol -- purged and embargoed walk-forward or combinatorial purged cross-validation (CPCV) rather than naive shuffled k-fold, which is shown to produce artificially inflated scores on time series; (4) statistical significance testing of the signal versus baseline via a one-sided Diebold-Mariano test on forecast errors, plus Probabilistic/Deflated Sharpe Ratio and Probability of Backtest Overfitting (PBO) if the validation extends to strategy-level returns, to correct for multiple-testing/selection bias; and (5) per-asset and per-regime breakdowns, since aggregate-level 'beats baseline' claims can hide near-total failure on most individual series. A 2026 benchmark of pretrained time-series foundation models (including TimesFM-2.5) on financial returns found gains over a zero-return random-walk baseline were 'small and sparse,' with Diebold-Mariano rejecting the null of equal-or-worse accuracy for only 2 of many model/asset pairs -- i.e. aggregate improvement claims did not hold up per-asset.

**Key findings**
- arXiv:2606.27100 (2026) benchmarks TimesFM-2.5, TimeGPT, Moirai-2.0, Chronos/Chronos-2 against train-from-scratch NBEATS/NHITS/PatchTST/iTransformer/KAN on 5 liquid US equities, using a zero-return random walk and a weekly seasonal naive as baselines, and MAE as the primary point-forecast metric because it is 'robust to the heavy tails of daily equity returns.'
- The same paper uses pinball/quantile loss for probabilistic model outputs (e.g. Moirai-2.0), stating that averaged pinball loss approximates CRPS, 'a strictly proper scoring rule for one-dimensional predictive distributions' -- i.e. it recommends CRPS/pinball loss over plain MSE for evaluating probabilistic signals.
- arXiv:2606.27100 finding: 'gains over the random-walk benchmark are small and sparse. A one-sided Diebold-Mariano test rejects equal or inferior predictive accuracy only for Chronos on AMZN and Moirai-2.0 on GOOG' -- out of many model/asset combinations, almost none statistically beat the naive baseline, which is direct evidence that aggregate benchmark tables can overstate real predictive edge unless broken down per-asset and tested for significance.
- The same paper's conclusion is that TSFMs are 'useful practical priors that reduce model-development costs... but not as universal engines of statistically reliable alpha generation' -- supporting a validation gate that defaults to skepticism of foundation-model signals absent per-asset significance testing.
- The purged-cross-validation / purgedcv library (eslazarev) demonstrates that naive shuffled k-fold CV on time series can report R^2 = 0.83-0.91 on a target that is completely unpredictable, while purging overlapping-window training rows and applying an embargo period correctly reveals R^2 below zero -- demonstrating that leakage-safe splitting is a prerequisite for any valid out-of-sample claim, not an optional refinement.
- The same library implements Combinatorial Purged Cross-Validation (CPCV), which builds C(N,K) fold combinations into multiple distinct out-of-sample backtest paths, plus Probabilistic Sharpe Ratio (PSR), Deflated Sharpe Ratio (DSR), and Probability of Backtest Overfitting (PBO) to adjust performance claims for multiple-testing/selection bias when many strategy variants are tried.
- A 2024 Knowledge-Based Systems study (via ScienceDirect/SSRN) compares CPCV against k-fold, purged k-fold, and walk-forward out-of-sample testing in a synthetic controlled environment and reports CPCV ahead of the alternatives on both backtest-overfitting probability and Deflated Sharpe Ratio, i.e. CPCV is the stronger choice among these when ranking strategy-level out-of-sample validity [uncertain -- derived from search-result summary of the paper, not a fully opened primary read of the paper's own results tables].

**Recommendations**
- Define the signal-adapter validation gate (criterion 12) to require: realised-price comparison via a proper scoring rule (CRPS or pinball/quantile loss) in addition to any point-accuracy metric, since point metrics alone do not reveal calibration quality.
- Require an explicit calibration report (e.g. PIT/reliability diagram or coverage of stated confidence intervals) as part of the validation gate output, not just a scalar score, because TSFMs are documented to be miscalibrated and calibration quality degrades with forecast horizon.
- Specify per-token AND per-regime error breakdowns as a gate requirement, not an aggregate pass/fail -- the cited benchmark shows an aggregate-looking improvement can collapse to near-zero significance once broken out per asset.
- Mandate a purged/embargoed out-of-sample split (walk-forward at minimum; CPCV if resourcing allows) rather than ordinary k-fold or random train/test splits, given documented leakage-driven false positives on time series.
- Require a formal significance test of signal-vs-baseline forecast errors (e.g. Diebold-Mariano) before a signal is allowed to 'beat' the naive/TimesFM baseline claim in any report; a smaller MAE/CRPS alone is not sufficient evidence given how often such gains were not statistically significant in the cited benchmark.
- Keep the validation-gate spec (criterion 12) as documentation only at this phase per the locked build scope -- do not implement CPCV/DSR/PBO tooling now, since no adapter or live signal code is to be built; simply reference these as the required methodology for when adapters are built later.
- Treat TimesFM/naive-baseline-beating as a high bar: per the cited 2026 paper, well-known pretrained TSFMs rarely clear this bar on financial return series, so the gate's naive/TimesFM baseline should be treated as a genuinely strong null, not a token comparison.

*As of: 2026-11-24 (web search/fetch date); primary paper arXiv:2606.27100 dated 2026; purgedcv repo and CPCV/DSR/PBO description as currently published on GitHub; Knowledge-Based Systems CPCV comparison study is 2024*

**Sources**
- [Pretrained Time-Series Foundation Models for Financial Return Forecasting](https://arxiv.org/html/2606.27100) (paper) -- "gains over the random-walk benchmark are small and sparse. A one-sided Diebold-Mariano test rejects equal or inferior predictive accuracy only for Chronos on AMZN and Moirai-2.0 on GOOG."
- [purged-cross-validation (purgedcv): scikit-learn-compatible time-series cross-validation with purging, embargo, CPCV, and deflated Sharpe ratios](https://github.com/eslazarev/purged-cross-validation) (repo) -- "naive shuffled k-fold reported R2 = 0.83-0.91 on a completely unpredictable target, while purged k-fold correctly revealed R2 below zero."
- [Backtest overfitting in the machine learning era: A comparison of out-of-sample testing methods in a synthetic controlled environment](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110) (article) -- "Combinatorial Purged Cross-Validation (CPCV) outperforming traditional methods as evidenced by its lower Probability of Backtest Overfitting (PBO) and superior Deflated Sharpe Ratio (DSR) test statistic."


### TimesFM as zero-shot numeric baseline
*What interface, input format and forecast outputs does TimesFM provide so it can be specified (not implemented) as the baseline every signal must beat?*

TimesFM is a pretrained decoder-only time-series foundation model (Google Research, Apache-2.0 for v1.0/2.0/2.5, non-commercial license for self-hosted 3.0 weights) that forecasts zero-shot with no fine-tuning: you pass a context array of past values (1D per series, or 2D for multivariate) plus a horizon length, and it returns a point forecast via predict()/predict_batch(), with an optional return_quantiles=True flag that adds 9 decile quantiles (0.1-0.9). Earlier versions (1.0/2.0) required a categorical frequency indicator (0=high/daily, 1=medium, 2=low); 2.5 removed this requirement. Google's own 2.0 model card explicitly states the quantile heads are experimental and 'have not been calibrated after pretraining,' which matters directly for this build's validation-gate calibration requirement. An independent 2026 benchmark paper found TimesFM-2.5 wins task-level ranks on equity return forecasting but its gains over a plain random-walk baseline are 'small and sparse' and not statistically significant for TimesFM specifically — supporting the PRD's choice to require beating both TimesFM AND a naive baseline, not TimesFM alone.

**Key findings**
- Official repo (github.com/google-research/timesfm) documents the current API as forecaster.predict(context, horizon=int, past_only_covariates=None, past_future_covariates=None, return_quantiles=True, use_symmetric_averaging=False) and predict_batch() for multiple series; context is a 1D NumPy array (univariate) or 2D array shaped (num_variates, context_length) for multivariate.
- Output: point forecast exposed as shape (horizon,) [or (num_variates, horizon)]; when return_quantiles=True, an additional array of shape (horizon, 9) [or (num_variates, horizon, 9)] gives the 10th-90th percentile deciles.
- TimesFM 2.0 (500M params, Apache-2.0, huggingface.co/google/timesfm-2.0-500m-pytorch): decoder-only, 50 layers, 1280-dim, input patch length 32, output patch length 128; trained context up to 2,048 timepoints, horizon recommended ≤ context length; requires a frequency indicator in {0,1,2} (0 = up to daily).
- Google's own TimesFM-2.0 model card states explicitly: 'we experimentally offer 10 quantile heads but they have not been calibrated after pretraining' -- i.e. out-of-the-box quantile/uncertainty outputs are not a trustworthy calibrated-probability source as-is.
- TimesFM-2.5 (released September 2025 per official Google Research blog, 200M params, Apache-2.0): extends context to 16,384 timepoints and removes the explicit frequency-indicator argument from the API.
- TimesFM-3 (official Google Research blog, dated 2026-08-31): adds native multivariate + past/future covariate support, still predicts point forecasts plus 9 quantiles (10th-90th percentile); self-hosted weights ship under a non-commercial, non-production license (commercial use only via Google Cloud BigQuery ML / Vertex Model Garden), unlike the Apache-2.0 1.0/2.0/2.5 releases.
- It is explicitly a zero-shot generalist model -- no task-specific fine-tuning is required or expected to use it as a forecasting baseline.
- Independent benchmark paper (arXiv:2606.27100, dated 2026-06-25, evaluating TimesFM-2.5 and other TSFMs on linear/log returns of 5 US equities): TimesFM-2.5 had the strongest average task-level ranks among tested TSFMs, but a formal statistical test rejecting 'no better than random walk' succeeded only for Chronos (AMZN) and Moirai-2.0 (GOOG) -- not for TimesFM -- concluding pretrained TSFMs are 'useful practical priors' but 'not universal engines for statistically reliable alpha generation.'

**Recommendations**
- Spec the validation-gate contract to require each adapter to beat BOTH a naive/random-walk (last-value or no-change) baseline AND zero-shot TimesFM forecasts on held-out data -- per-token, per-regime -- since the benchmark literature shows TimesFM alone frequently fails to beat random walk on financial series; requiring only 'beat TimesFM' would let a signal pass by tying a weak baseline.
- Do not spec TimesFM's own quantile heads as the source of 'calibrated probability/uncertainty' for the validation gate -- Google's model card states those quantiles are uncalibrated. The validation-gate spec should require calibration to be measured independently (e.g. reliability diagrams / Brier score against realised price) rather than trusting TimesFM's internal uncertainty output.
- Pin a specific TimesFM checkpoint and version in the spec document (point to the interface, don't implement) -- note that 1.0/2.0/2.5 are Apache-2.0 (safe for research reuse) while self-hosted 3.0 weights carry a non-commercial/non-production license, which matters if this baseline spec is ever operationalised.
- Document the input-format contract explicitly in the spec: context = array of past daily close prices or log-returns per token, horizon = rebalance-period length in days, consistent with the build's daily-granularity ingestion; note that 2.0/1.0 needs an explicit frequency indicator (use 0 for daily) while 2.5+ drops that parameter -- the spec should state which API shape is assumed so a future implementer isn't surprised.
- Because this item is spec-only per the PRD (no implementation), capture the predict()/predict_batch() signature, context/horizon input shapes, and point+quantile output shapes as the documented contract the adapter validation gate benchmarks against -- no code should be written now.

*As of: TimesFM-2.0 model card and GitHub README as observed 2026-11-24; TimesFM-2.5 officially released September 2025 per Google Research blog; TimesFM-3 blog post dated 2026-08-31; benchmark paper arXiv:2606.27100 dated 2026-06-25*

**Sources**
- [google-research/timesfm GitHub repository (README)](https://github.com/google-research/timesfm) (repo) -- "forecaster.predict(context, horizon=X, return_quantiles=True) ... License by Version: 1.0, 2.0, 2.5 Apache-2.0 | 3.0 weights timesfm-non-commercial-license-v1.0"
- [google/timesfm-2.0-500m-pytorch · Hugging Face](https://huggingface.co/google/timesfm-2.0-500m-pytorch) (official-docs) -- "It focuses on point forecasts. We experimentally offer 10 quantile heads but they have not been calibrated after pretraining."
- [TimesFM-3: A zero-shot foundation model for multivariate forecasting (Google Research blog)](https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/) (official-docs) -- "The model predicts 9 quantiles (from the 10th to the 90th percentile) for each target time series ... TimesFM-2.5 release: September 2025"
- [Pretrained Time-Series Foundation Models for Financial Return Forecasting (arXiv:2606.27100)](https://arxiv.org/abs/2606.27100) (paper) -- "gains over the random-walk benchmark are small and sparse ... rejects equal or inferior predictive accuracy only for Chronos on AMZN and Moirai-2.0 on GOOG"


### Enforcing no-najsh at the order/intent model level
*How to model an order/intent type whose construction mandates genuine intent-to-fill so spoofing/layering is structurally impossible for the current and future HFT layers to introduce?*

The structural fix is to never give the order/intent type a state that can exist without a paired fill: model it as an immutable, frozen value object whose constructor (a private/sealed factory, not a public __init__) requires both the trade parameters AND a resolved Fill (or an explicit, logged Rejection) in the same atomic call, so there is no intermediate 'resting, cancelable, unfilled' state for a current backtest-only build to misuse and no legal way for a future HFT layer to bypass. This follows the well-established 'make illegal states unrepresentable' / typestate / smart-constructor pattern (encode state in the type, use private constructors + validating factories) and matches how backtest-only engines (QuantConnect) sidestep spoofing entirely by assuming orders fill completely with no cancelable resting state, while explicit order-lifecycle engines (nautilus_trader) keep intent, acknowledgment, fill and cancellation as separate typed stages precisely so 'genuine intent to trade' can be audited. Legally, the CFTC's own test for spoofing turns on provable intent-to-cancel-before-execution versus a 'legitimate, good-faith attempt to consummate a trade' -- so the test suite should assert that the type cannot be instantiated unless it carries proof of a consummated (or explicitly rejected) trade, never a bare, cancelable posting.

**Key findings**
- The 'make illegal states unrepresentable' pattern (F# for Fun and Profit, fsharpforfunandprofit.com) uses discriminated unions / smart constructors so an invalid combination (e.g., an order with no fill and no rejection) simply has no corresponding type value -- the compiler/validator rejects construction rather than relying on a later runtime check.
- The typestate pattern (multiple Rust sources, e.g. microsoft/RustTraining) encodes lifecycle state in the type itself (Order<Created>, Order<Filled>) using private fields/constructors, so callers cannot forge an intermediate state; methods consume self and return a new type on transition, making an 'order that exists but was never intended to fill' unconstructable.
- CFTC Final Rule on spoofing (17 CFR Part 180, Federal Register 2013-12365, dated May 28, 2013) defines spoofing under CEA section 4c(a)(5)(C) as 'bidding or offering with the intent to cancel the bid or offer before execution,' requires intent/scienter beyond recklessness, and explicitly exempts orders that are 'part of a legitimate, good-faith attempt to consummate a trade' -- i.e., the legal line is drawn at provable intent-to-fill, matching the required test-level invariant.
- QuantConnect's v2 docs (quantconnect.com, page last modified 2026-11-24) state that in backtests 'pre-built fill models assume orders completely fill' by default -- i.e., the reference backtest-only platform's default architecture has no cancelable-before-fill resting-order concept at all, which structurally removes the precondition for spoofing in a backtest/research context.
- nautilus_trader (GitHub issue #2194, opened 2025-01-08, closed 2025-10-30) keeps order lifecycle stages explicit and separate (OrderIntent/acknowledgment/fill/partial-fill/cancel) via a FillModel hook, showing that even order-book-aware engines treat 'intent' as a first-class, auditable stage distinct from cancellation -- useful as the pattern for a later, more realistic fast/HFT layer, but not needed for the current equal-weight baseline.
- Python's standard mechanisms for this (docs.python.org dataclasses + pydantic docs) are frozen dataclasses (immutable after construction, __setattr__ rejects mutation) combined with __post_init__ validation or a Pydantic validator, plus a private constructor exposed only through a validating factory function/classmethod -- the practical way to implement a 'smart constructor' in this codebase's likely Python stack.
- No source found an existing open-source library that ships an 'OrderIntent' type specifically engineered to make spoofing structurally impossible; marketmaker.cc's fill-simulation article (2026-07-16) models order lifecycle states but does not validate intent at construction, confirming this is a design choice the build must make itself rather than an off-the-shelf component.

**Recommendations**
- Model the V1 (buy-and-hold/rebalance) order/intent type as a single frozen, immutable value object with NO public bare constructor: only a factory function (e.g. `Fill.resolve(intent, ...)`) that requires the trade parameters AND either a concrete Fill result or an explicit, logged Rejection to exist simultaneously -- never allow an `Intent` or `Order` instance to exist on its own with an unresolved/cancelable status, since this backtest has no live order book and does not need one.
- Expose no `cancel()` method on the type in V1 at all; since every rebalance trade is assumed to execute at the next bar's price (matching the no-fake-order constraint), there is no legitimate reason for a cancelable, restable order to exist, which eliminates the precondition for spoofing/layering by construction rather than by policy.
- Write the required invariant test to literally attempt construction of the order/intent type with a missing or null fill/rejection field and assert it raises (TypeError/ValidationError) -- this directly satisfies acceptance criterion 10 ('rejects an order created without intent to fill').
- For the future fast/HFT-layer seam, define (spec only, no implementation) that any resting/cancelable order type MUST be a structurally distinct, sealed type family requiring a mandatory, non-optional 'intent attestation' field at construction (e.g., a reserved-notional/capital-commitment proof), echoing the CFTC's legal distinction between a 'legitimate good-faith attempt to consummate a trade' and a cancel-intent posting -- this keeps the contract honest for later phases without building any live-trading code now.
- Implement via Python frozen dataclass + `__post_init__` validation (or a Pydantic model with a validator) with a private/underscore-prefixed constructor and a public validating factory classmethod, since that is the idiomatic, low-dependency way to get smart-constructor/typestate guarantees in a Python research codebase without adopting Rust-style generics.
- Do not attempt runtime spoofing *detection* (statistical/order-book heuristics); that is the wrong layer for this build -- the PRD requires structural impossibility at the type level, not surveillance, and detection-style approaches (TCN models, order-to-trade ratios) are out of scope for a backtest-only, no-order-book system.

*As of: 2026-11-24*

**Sources**
- [Designing with types: Making illegal states unrepresentable](https://fsharpforfunandprofit.com/posts/designing-with-types-making-illegal-states-unrepresentable/) (article) -- "use a union type with a case for each possibility"
- [2013-12365 (CFTC Final Interpretive Guidance and Policy Statement on Disruptive Practices)](https://www.cftc.gov/LawRegulation/FederalRegister/FinalRules/2013-12365.html) (official-docs) -- "a legitimate, good-faith cancellation or modification of orders...would not violate section CEA 4c(a)(5)(C)"
- [Key Concepts - Trade Fills - QuantConnect Documentation](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts) (official-docs) -- "in backtests, the pre-built fill models assume orders completely fill"
- [Enhanced order-fill simulation in backtesting · Issue #2194 · nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader/issues/2194) (repo) -- "Keep the current FillModel responsibility of determining if/how much of an order is filled"
- [Fill simulation: the ladder from close-price fantasy to queue-aware reality](https://www.marketmaker.cc/en/blog/post/fill-simulation-partial-fills-backtest/) (article) -- "any price amend resets q_ahead to the full current level volume"
- [3. The Newtype and Type-State Patterns - Rust Patterns & Engineering How-Tos](https://microsoft.github.io/RustTraining/rust-patterns-book/ch03-the-newtype-and-type-state-patterns.html) (official-docs) -- "Typestate makes invalid operations impossible to call using private fields to prevent callers from forging invalid states"

## Documentation sources

- [Get Public Product Candles - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles)
- [Get product candles - Coinbase Developer Documentation (Exchange API)](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
- [Exchange Changelog - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/exchange/changes/changelog)
- [Exchange Rate Limits Overview / REST Rate Limits - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits)
- [Advanced Trade REST Endpoints - Coinbase Developer Documentation](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-api)
- [Get OHLC Data — Kraken Developers (official REST API reference)](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data)
- [Spot REST Rate Limits — Kraken Developers](https://docs.kraken.com/exchange/guides/rest/ratelimits)
- [What are the API rate limits? — Kraken Support](https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-)
- [Advanced API FAQ — Kraken Support](https://support.kraken.com/articles/advanced-api-faq)
- [Exchange Changelog — Kraken Developers](https://docs.kraken.com/exchange/changelog)
- [DuckDB Documentation (docs/2.0)](https://duckdb.org/docs/2.0/)
- [DuckDB Python Client Overview (docs/2.0)](https://duckdb.org/docs/2.0/clients/python/overview.html)
- [DuckDB Installation (docs/2.0)](https://duckdb.org/docs/2.0/installation/)
- [Announcing DuckDB 2.0.0 LTS "Cinnamon Teal"](https://duckdb.org/2026/10/21/announcing-duckdb-200)
- [google-research/timesfm (official GitHub repository README)](https://github.com/google-research/timesfm)
- [google/timesfm-2.5-200m-pytorch (Hugging Face model card)](https://huggingface.co/google/timesfm-2.5-200m-pytorch)
- [google/timesfm-1.0-200m-pytorch (Hugging Face model card)](https://huggingface.co/google/timesfm-1.0-200m-pytorch)
- [timesfm · PyPI](https://pypi.org/project/timesfm/)
- [TimesFM Release collection (Hugging Face)](https://huggingface.co/collections/google/timesfm-release-66e4be5fdb56e960c1e482a6)
- [Inkling 2 Small Model Card - Thinking Machines Lab](https://thinkingmachines.ai/model-card/inkling-2-small/)
- [inkling-2-small (Thinking Machines) · Cloudflare Workers AI docs](https://developers.cloudflare.com/workers-ai/models/inkling-2-small/)
- [thinkingmachines/Inkling-2-Small · Hugging Face](https://huggingface.co/thinkingmachines/Inkling-2-Small)
- [Using Inkling - Tinker Documentation - Thinking Machines Lab](https://tinker-docs.thinkingmachines.ai/cookbook/inkling/)
- [bilawalsidhu/gods-eye-view README.md](https://github.com/bilawalsidhu/gods-eye-view/blob/main/README.md)
- [DuckDB Docs -- Performance Guide: Schema](https://duckdb.org/docs/2.0/guides/performance/schema.html)
- [DuckDB Docs -- INSERT Statement](https://duckdb.org/docs/1.3/sql/statements/insert)
- [DuckDB Docs -- Date Functions (time_bucket, date_trunc)](https://duckdb.org/docs/2.0/sql/functions/date.html)
- [Fees, slippage, and leverage in backtests — VectorBT PRO](https://vectorbt.pro/features/backtesting/fees-slippage-and-leverage/)
- [PEP 544 – Protocols: Structural subtyping (static duck typing)](https://peps.python.org/pep-0544/)
- [Model Cards · Hugging Face](https://huggingface.co/docs/hub/model-cards)
- [1.16. Probability calibration — scikit-learn documentation](https://scikit-learn.org/stable/auto_examples/calibration/plot_calibration_curve.html)
- [Challengers tab — DataRobot docs (v11.0)](https://docs.datarobot.com/11.0/en/docs/mlops/monitor/challengers.html)
- [google/timesfm-2.0-500m-pytorch · Hugging Face](https://huggingface.co/google/timesfm-2.0-500m-pytorch)
- [TimesFM-3: A zero-shot foundation model for multivariate forecasting (Google Research blog)](https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/)
- [2013-12365 (CFTC Final Interpretive Guidance and Policy Statement on Disruptive Practices)](https://www.cftc.gov/LawRegulation/FederalRegister/FinalRules/2013-12365.html)
- [Key Concepts - Trade Fills - QuantConnect Documentation](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts)
- [3. The Newtype and Type-State Patterns - Rust Patterns & Engineering How-Tos](https://microsoft.github.io/RustTraining/rust-patterns-book/ch03-the-newtype-and-type-state-patterns.html)

Documentation items with no official source: Official documentation: Agent-Reach; Official documentation: MiroFish.

## Academic literature

- **Pretrained Time-Series Foundation Models for Financial Return Forecasting** (2026), cited 8x -- [link](https://doi.org/10.48550/arxiv.2606.27100) / [PDF](https://arxiv.org/pdf/2606.27100) _(via openalex)_
- **Narrow Decision Models: A System-1 Architecture for Calibrated, Typed Decisions** (2026), cited 6x -- [link](https://doi.org/10.48550/arxiv.2610.25553) / [PDF](https://arxiv.org/pdf/2610.25553) _(via openalex)_
- **Seeking SOTA: Time-Series Forecasting Must Adopt Taxonomy-Specific Evaluation to Dispel Illusory Gains** (2026), cited 6x -- [link](https://doi.org/10.48550/arxiv.2603.15506) / [PDF](https://arxiv.org/pdf/2603.15506) _(via openalex)_

## Prior art

_No public repositories matched._

_No public repositories matched the prior-art queries._

## Open uncertainties

- Official documentation: Coinbase (Advanced Trade / Exchange public market data API): `current_version`
- Official documentation: Kraken (public REST market data API): `current_version`
- Official documentation: Inkling 2 Small (Thinking Machines): `current_version`
- Coinbase public OHLCV candle retrieval: `key_findings`
- Equal-weight buy-and-hold with periodic rebalance and realistic costs: `key_findings`
- Out-of-sample calibration, per-subgroup error and baseline-beating validation: `key_findings`

## Not researched

- docs-agent-reach: Field "pitfalls" contains [uncertain] but is not listed in the "uncertain" array.
- docs-mirofish: A documentation item must cite at least one source of type "official-docs".
- kraken-public-candles: "uncertain" names "endpoint_url_and_params", which is not a field of this result. "uncertain" names "interval_values", which is not a field of this result. "uncertain" names "720_candle_limit_daily_lookback", which is not a field of this result. "uncertain" names "last_candle_not_closed", which is not a field of this result. "uncertain" names "ohlcvt_csv_full_history_download", which is not a field of this result. "uncertain" names "legacy_prefix_mapping", which is not a field of this result. "uncertain" names "newer_asset_plain_symbol_convention", which is not a field of this result. "uncertain" names "BNB_OKB_CRO_pair_availability", which is not a field of this result. "uncertain" names "general_kraken_doc_access_failure", which is not a field of this result. Field "key_findings" contains [uncertain] but is not listed in the "uncertain" array.

## Independent check

Researched by claude-code; checked by claude-code (claude-code (opus) reviewed work written by claude-code (sonnet): the same model family but a different capability class.). Verdict: **issues**.

I opened the cited Coinbase (Exchange + Advanced Trade), DuckDB 2.0 announcement, TimesFM GitHub, Inkling model-card, and Coinbase rate-limit pages, and corroborated the Kraken OHLC facts via search after repeated ECONNRESET on docs.kraken.com. Every build-critical claim I could check — candle caps (300/350), granularity enums, no-auth public access, 10/15 req/s limits, DuckDB 2.0.0 'Cinnamon Teal' (2026-10-21) version/LTS/breaking-changes, TimesFM 3.0/2.5 versions and licensing, Inkling 2 Small's existence/irrelevance, and Kraken's 720-entry cap plus the Jan-1-2024 POST removal — matched its source. No unsupported or contradicted build claims and no surviving planted instructions were found. OSA also removed 1 planted instruction(s) from the sources before the reviewer saw them.

Claims NOT confirmed (treat as uncertain downstream):
- [unverifiable] DuckDB Python package is at 2.0.1 per the install docs. -- Install-docs page not opened (announcement page does not state the Python package minor version). Plausible and consistent with 2.0.0 release but not independently confirmed. (https://duckdb.org/docs/2.0/installation/)
- [unverifiable] Kraken OHLC interval enum (minutes) is 1,5,15,30,60,240,1440,10080,21600; response row is [time,open,high,low,close,vwap,volume,count]. -- Could not open the OHLC reference directly (ECONNRESET); these are the long-standing documented Kraken values and are not contradicted by any source, but not independently confirmed this session. (https://docs.kraken.com/api/docs/rest-api/get-ohlc-data)
- [unverifiable] Coinbase Pro (api.pro.coinbase.com) was fully shut down by 2023-11-09; Exchange API is its non-deprecated successor. -- Exchange changelog not opened this session (report's own changelog citation gives a 2024-SEP-11 'Pro API deprecated' entry, a slightly different date/event). Not build-critical and widely corroborated that Pro is retired; exact date not re-verified. (https://docs.cdp.coinbase.com/exchange/changes/changelog)

### Planted instructions found in sources (removed before use)

1 line(s) of source text were aimed at an AI rather than at a reader. They were cut out before any model used the material, and nothing in this report relies on them.

- governance in research result (model output derived from web pages) (research:docs-coinbase-advanced-trade-exchange-public-market-dat)
