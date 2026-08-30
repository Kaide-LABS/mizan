"""mizan/data/normalize.py — normalized, typed row shapes + raw-cache-to-DuckDB mapping functions.

Implements PHASE_3_SPEC.md §3, §4.2, §6.

Grounded in ULTIMATE_PRD.md §4.3 (Normalization failure-mode table): silent unit-scale coercion and
duplicate/overlapping filing periods are the two named HALT-for-human failure modes this module's
row shapes and load logic must structurally prevent, not just document.

Zero network capability: this module never fetches. It reads only the raw cache Phase 2's ingest
functions already wrote to disk (`mizan/data/raw_cache.py`), and every function here raises
`NotIngestedError` rather than falling back to a live call when the raw file it needs is absent
(§7 guard G-N7, G-N8).
"""

from __future__ import annotations

from datetime import date as _Date  # noqa: N812 -- underscore-prefixed alias, not a rename
from typing import TYPE_CHECKING

import pyarrow

from mizan.core.base import MizanBaseModel
from mizan.data.ingest_edgar import CikResolutionError
from mizan.data.models import CompanyTickerEntry, EdgarFactRow, TiingoEodBar
from mizan.data.raw_cache import cache_path, is_cached, read_raw_json

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import duckdb

#: The XBRL unit strings Mizan's Phase 4 financial-ratio screen (30/30/5, MASTER_PRD.md §6.2) will
#: actually consume: interest-bearing-debt/deposits/revenue figures are USD; the market-cap
#: denominator's other factor (shares outstanding) is `shares`. Any other unit key
#: (`"USD/shares"` EPS-type concepts, `"pure"` ratio concepts, or anything else SEC's XBRL taxonomy
#: uses) is out of V1's scope and its appearance under a tag Mizan ingests is a signal to look, not
#: guess — ULTIMATE_PRD.md §4.3's "reject rather than guess a scale," applied as a closed allow-list
#: rather than an attempted scale-conversion. Extending this set is a deliberate, reviewed change
#: (a later phase's spec revision), never a silent widening inside normalize.py.
RECOGNIZED_XBRL_UNITS: frozenset[str] = frozenset({"USD", "shares"})

#: `fundamentals_facts`' uniqueness key (PHASE_1_SPEC.md §5's forward declaration, PHASE_3_SPEC.md
#: §5). `taxonomy` + `tag` together are "concept"; `unit` is a necessary fourth axis; `accn` (not
#: `filed`) is the discriminator for "same period reported in two filings."
_FUNDAMENTALS_FACTS_KEY_COLUMNS: tuple[str, ...] = (
    "cik",
    "taxonomy",
    "tag",
    "unit",
    "period_start",
    "period_end",
    "accn",
)

#: `price_bars`' uniqueness key (PHASE_3_SPEC.md §5.2).
_PRICE_BARS_KEY_COLUMNS: tuple[str, ...] = ("ticker", "trade_date")


class FundamentalsFactRow(MizanBaseModel):
    """One normalized XBRL fact row, as it will be loaded into DuckDB's `fundamentals_facts` table.

    `cik` is the zero-padded 10-digit string form (matches `ingest_edgar.resolve_cik`'s return type
    and every EDGAR raw-cache key, PHASE_2_SPEC.md §6.3) — never the bare int `EdgarSubmissionRecord
    .cik` carries at the raw layer; Phase 3 is where that canonicalization is finalized for every
    downstream consumer.

    `taxonomy`, `tag`, and `unit` are NOT present on `mizan.data.models.EdgarFactRow` itself — they
    are the nesting keys (`facts.{taxonomy}.{tag}.units.{unit}`) the raw companyfacts JSON stores
    each fact object under (docs/modernization_log.md §6.1). `normalize_edgar_facts` (§6.1) carries
    them from the traversal into this row explicitly; losing them here would make the
    (cik, taxonomy, tag, unit, period_start, period_end, accn) uniqueness key (PHASE_1_SPEC.md §5's
    forward note) impossible to enforce.

    `period_start`/`period_end`/`is_instantaneous` replace the raw model's optional `start`/required
    `end`: an instantaneous concept's raw `start=None` is normalized to `period_start = period_end`
    (a single-point period's start IS its end) with `is_instantaneous = True` preserving the
    original signal losslessly — no information is discarded, only re-expressed in a form with no
    nullable key column (DuckDB's PRIMARY KEY columns are declared NOT NULL by construction, §5).
    `is_instantaneous = False` alongside a `period_start != period_end` marks an ordinary duration
    concept.

    `value` (not `val`) is a deliberate rename — PHASE_2_SPEC.md §3 named this exact rename as
    Phase 3's job; it is not a drift, it is the one place in the whole codebase where wire-format
    naming is intentionally left behind for a typed table's own naming convention.
    """

    cik: str
    taxonomy: str
    tag: str
    unit: str
    period_start: _Date
    period_end: _Date
    is_instantaneous: bool
    value: float
    accn: str
    fy: int
    fp: str
    form: str
    filed: _Date


class PriceBarRow(MizanBaseModel):
    """One normalized Tiingo EOD bar row, as it will be loaded into DuckDB's `price_bars` table.

    `raw_*`/`adj_*` naming is the exact typed-column contract `mizan.data.models.TiingoEodBar`'s own
    docstring already promised downstream. `raw_close`/`adj_close` (and every other raw/adj pair)
    remain two independently-populated columns here — no function in this module, or any later
    phase, may derive one from the other or read one and call it "the close" (ULTIMATE_PRD.md §4.2
    guard G-T3, carried through unbroken).
    """

    ticker: str
    trade_date: _Date
    raw_open: float
    raw_high: float
    raw_low: float
    raw_close: float
    volume: int
    adj_open: float
    adj_high: float
    adj_low: float
    adj_close: float
    adj_volume: int
    div_cash: float
    split_factor: float


class UnrecognizedUnitError(RuntimeError):
    """Raised when an XBRL fact's unit key is outside `RECOGNIZED_XBRL_UNITS` (§3) —
    ULTIMATE_PRD.md §4.3's "reject rather than guess a scale," applied as a closed allow-list."""


class DuplicateFactRowError(RuntimeError):
    """Raised when a fact row's (cik, taxonomy, tag, unit, period_start, period_end, accn) key
    already exists in `fundamentals_facts` with a DIFFERENT `value`/`fy`/`fp`/`form`/`filed` than
    the incoming row — ULTIMATE_PRD.md §4.3's "duplicate/overlapping filing periods loaded twice ...
    violation raises, not upserts silently." An incoming row that is byte-identical to the existing
    row at the same key is NOT an error (§6.2's idempotent-replay dedup) — this exception fires only
    on a genuine value conflict at an existing key."""


class DuplicatePriceBarError(RuntimeError):
    """Same contract as `DuplicateFactRowError`, for `price_bars`' (ticker, trade_date) key."""


class NotIngestedError(RuntimeError):
    """Raised by `normalize_edgar_facts`/`normalize_tiingo_bars` when the raw cache file they need
    does not exist — normalize.py never fetches; a missing raw file is a HALT (§7 G-N7), never a
    silent skip or an implicit live network call."""


def resolve_cik_offline(ticker: str, *, cache_dir: Path) -> str:
    """Resolve `ticker` to its zero-padded CIK using ONLY the already-cached
    `edgar/company_tickers/company_tickers.json` file — no network-client parameter exists on this
    function, structurally guaranteeing zero network capability (§7 G-N8).

    Raises `mizan.data.ingest_edgar.CikResolutionError` (Phase 2's own exception type, imported and
    reused, not redefined) if `company_tickers.json` is not cached at all, or if `ticker` is not
    found in it. Does NOT perform Phase 2's `resolve_cik`'s submissions-name cross-check — this
    function's only job is the ticker->CIK lookup Phase 3's CLI needs to locate the right cache
    files, not to re-run Phase 2's own drift detection a second time.
    """
    path = cache_path(cache_dir=cache_dir, source="edgar/company_tickers", key="company_tickers")
    if not is_cached(path):
        raise CikResolutionError(
            f"{ticker!r}: no cached company_tickers.json — run `mizan ingest` first"
        )
    raw = read_raw_json(path)
    if not isinstance(raw, dict):
        raise CikResolutionError(f"{ticker!r}: cached company_tickers.json is not a JSON object")
    entries = [CompanyTickerEntry.model_validate(entry) for entry in raw.values()]

    match = next((entry for entry in entries if entry.ticker.upper() == ticker.upper()), None)
    if match is None:
        raise CikResolutionError(f"{ticker!r} not found in cached company_tickers.json")
    return f"{match.cik_str:010d}"


def normalize_edgar_facts(cik: str, *, cache_dir: Path, con: duckdb.DuckDBPyConnection) -> int:
    """Read the already-cached `edgar/companyfacts/{cik}.json` raw file, validate and flatten every
    fact object into a `FundamentalsFactRow` (rejecting via `UnrecognizedUnitError` on any unit
    outside `RECOGNIZED_XBRL_UNITS`), and bulk-load the rows that are new into
    `fundamentals_facts` (§6.1's dedup-then-insert logic). Returns the count of rows newly
    inserted — 0 on a fully-idempotent re-run over an already-normalized CIK.

    Scoped to `companyfacts` only for V1: `companyfacts` is a strict superset of any single
    `companyconcept` call for the same CIK, and every ticker `mizan ingest` processes always fetches
    `companyfacts` (companyconcept is never called from the CLI). Normalizing a companyconcept-only
    cache entry is out of scope (§9).

    Raises:
        NotIngestedError: if the cache file is absent (§7 G-N7).
        UnrecognizedUnitError: if any fact's unit key is outside `RECOGNIZED_XBRL_UNITS` (§7 G-N1).
        DuplicateFactRowError: if an incoming row's key matches an existing row with a different
            non-key value (§7 G-N2).
    """
    path = cache_path(cache_dir=cache_dir, source="edgar/companyfacts", key=cik)
    if not is_cached(path):
        raise NotIngestedError(f"CIK {cik}: no cached companyfacts — run `mizan ingest` first")

    data = read_raw_json(path)
    if not isinstance(data, dict):
        raise NotIngestedError(f"CIK {cik}: cached companyfacts is not a JSON object")
    facts = data.get("facts")
    if not isinstance(facts, dict):
        raise NotIngestedError(f"CIK {cik}: cached companyfacts has no usable `facts` data")

    rows: list[FundamentalsFactRow] = []
    for taxonomy, tags in facts.items():
        if not isinstance(tags, dict):
            continue
        for tag, tag_body in tags.items():
            if not isinstance(tag_body, dict):
                continue
            units = tag_body.get("units")
            if not isinstance(units, dict):
                continue
            for unit, fact_list in units.items():
                if unit not in RECOGNIZED_XBRL_UNITS:
                    raise UnrecognizedUnitError(
                        f"CIK {cik} {taxonomy}:{tag}: unit {unit!r} is not in "
                        f"RECOGNIZED_XBRL_UNITS {sorted(RECOGNIZED_XBRL_UNITS)} — refusing to guess"
                    )
                if not isinstance(fact_list, list):
                    continue
                for raw_fact in fact_list:
                    rows.append(
                        _build_fact_row(
                            cik=cik, taxonomy=taxonomy, tag=tag, unit=unit, raw_fact=raw_fact
                        )
                    )

    return _bulk_load(
        con,
        table="fundamentals_facts",
        rows=rows,
        key_columns=_FUNDAMENTALS_FACTS_KEY_COLUMNS,
        conflict_error_cls=DuplicateFactRowError,
    )


def _build_fact_row(
    *, cik: str, taxonomy: str, tag: str, unit: str, raw_fact: object
) -> FundamentalsFactRow:
    """Validate one raw fact object (Phase 2's `EdgarFactRow` shape) and map it to a
    `FundamentalsFactRow`, applying the instantaneous-concept substitution (§3, §7 guard G-N6)."""
    fact = EdgarFactRow.model_validate(raw_fact)
    if fact.start is None:
        is_instantaneous = True
        period_start = fact.end
    else:
        is_instantaneous = False
        period_start = fact.start
    return FundamentalsFactRow(
        cik=cik,
        taxonomy=taxonomy,
        tag=tag,
        unit=unit,
        period_start=period_start,
        period_end=fact.end,
        is_instantaneous=is_instantaneous,
        value=fact.val,
        accn=fact.accn,
        fy=fact.fy,
        fp=fact.fp,
        form=fact.form,
        filed=fact.filed,
    )


def normalize_tiingo_bars(
    ticker: str,
    start_date: _Date,
    end_date: _Date,
    *,
    cache_dir: Path,
    con: duckdb.DuckDBPyConnection,
) -> int:
    """Read the already-cached `tiingo/eod/{ticker}_{start_date}_{end_date}.json` raw file
    (raises `NotIngestedError` if absent), validate every bar as `TiingoEodBar` (re-validated here
    since normalize treats the raw cache, not the ingest process's memory, as its only input), map
    each to a `PriceBarRow` preserving `raw_*`/`adj_*` as distinct columns (§3, §6.3), and bulk-load
    new rows into `price_bars`. Returns the count of rows newly inserted.
    """
    key = f"{ticker}_{start_date.isoformat()}_{end_date.isoformat()}"
    path = cache_path(cache_dir=cache_dir, source="tiingo/eod", key=key)
    if not is_cached(path):
        raise NotIngestedError(f"{ticker} {start_date}..{end_date}: no cached Tiingo EOD data")

    bars_raw = read_raw_json(path)
    if not isinstance(bars_raw, list):
        raise NotIngestedError(f"{ticker}: cached Tiingo EOD data is not a JSON array")
    bars = [TiingoEodBar.model_validate(row) for row in bars_raw]

    # Every raw_*/adj_* field is assigned from its own, distinctly-named TiingoEodBar attribute on
    # its own line — no shared local variable named `close` or `open` anywhere in this function
    # body (ULTIMATE_PRD.md §4.2 guard G-T3, §6.3).
    rows = [
        PriceBarRow(
            ticker=ticker,
            trade_date=bar.date,
            raw_open=bar.open,
            raw_high=bar.high,
            raw_low=bar.low,
            raw_close=bar.close,
            volume=bar.volume,
            adj_open=bar.adjOpen,
            adj_high=bar.adjHigh,
            adj_low=bar.adjLow,
            adj_close=bar.adjClose,
            adj_volume=bar.adjVolume,
            div_cash=bar.divCash,
            split_factor=bar.splitFactor,
        )
        for bar in bars
    ]

    return _bulk_load(
        con,
        table="price_bars",
        rows=rows,
        key_columns=_PRICE_BARS_KEY_COLUMNS,
        conflict_error_cls=DuplicatePriceBarError,
    )


def _bulk_load(
    con: duckdb.DuckDBPyConnection,
    *,
    table: str,
    rows: Sequence[MizanBaseModel],
    key_columns: tuple[str, ...],
    conflict_error_cls: type[RuntimeError],
) -> int:
    """The dedup-then-insert-with-backstop pattern shared by both normalize functions (§6.2).

    Builds one `pyarrow.Table` from `rows`, `register()`s it as a queryable view, and:

    1. Runs a pre-insert conflict check restricted to incoming rows whose `key_columns` match an
       existing row but whose other columns differ, raising `conflict_error_cls` naming the
       conflicting key and both the existing and incoming values (§7 guard G-N2) before any
       `INSERT` runs.
    2. Runs one `INSERT ... SELECT ... WHERE NOT EXISTS (...)` against `table`, so a row whose key
       already exists with byte-identical other-column values is silently (and correctly) skipped
       as an idempotent no-op — never an error (§7 guard G-N3, §8 AC4).

    `table`'s own `PRIMARY KEY` constraint (§5) is the last-resort backstop if step 1 is ever itself
    wrong; a `duckdb.ConstraintException` surfacing from the `INSERT` below indicates a bug in this
    function and must be treated as one, not caught or routed around.

    Returns the count of rows newly inserted — 0 if `rows` is empty or every row was already
    present.
    """
    if not rows:
        return 0

    payload = [row.model_dump() for row in rows]
    all_columns = list(payload[0].keys())
    non_key_columns = [column for column in all_columns if column not in key_columns]
    key_match = " AND ".join(f"t.{column} = s.{column}" for column in key_columns)

    arrow_table = pyarrow.Table.from_pylist(payload)
    con.register("_staging", arrow_table)
    try:
        if non_key_columns:
            _raise_on_conflict(
                con,
                table=table,
                key_columns=key_columns,
                non_key_columns=non_key_columns,
                key_match=key_match,
                conflict_error_cls=conflict_error_cls,
            )

        before = _row_count(con, table)
        # `table`/`key_match` are this module's own fixed, closed set of identifiers (never user
        # input) — string-built SQL here is a controlled DDL/DML concern, not an injection risk.
        con.execute(
            f"INSERT INTO {table} SELECT s.* FROM _staging s "
            f"WHERE NOT EXISTS (SELECT 1 FROM {table} t WHERE {key_match})"
        )
        after = _row_count(con, table)
        return after - before
    finally:
        con.unregister("_staging")


def _row_count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    """Return `table`'s current row count."""
    result = con.execute(f"SELECT count(*) FROM {table}").fetchone()
    if result is None:
        return 0
    return int(result[0])


def _raise_on_conflict(
    con: duckdb.DuckDBPyConnection,
    *,
    table: str,
    key_columns: tuple[str, ...],
    non_key_columns: list[str],
    key_match: str,
    conflict_error_cls: type[RuntimeError],
) -> None:
    """Raise `conflict_error_cls` if any staged row's key matches an existing row with a differing
    non-key column value — the "genuine conflict" guard (§7 G-N2), distinct from an idempotent
    replay (§7 G-N3, handled by the caller's separate `WHERE NOT EXISTS` insert)."""
    diff_clause = " OR ".join(
        f"t.{column} IS DISTINCT FROM s.{column}" for column in non_key_columns
    )
    select_columns = (
        [f"s.{column} AS new_{column}" for column in key_columns]
        + [f"s.{column} AS new_{column}" for column in non_key_columns]
        + [f"t.{column} AS old_{column}" for column in non_key_columns]
    )
    query = (
        f"SELECT {', '.join(select_columns)} FROM _staging s "
        f"JOIN {table} t ON {key_match} WHERE {diff_clause} LIMIT 1"
    )
    conflict = con.execute(query).fetchone()
    if conflict is None:
        return

    result_columns = (
        [f"new_{column}" for column in key_columns]
        + [f"new_{column}" for column in non_key_columns]
        + [f"old_{column}" for column in non_key_columns]
    )
    values = dict(zip(result_columns, conflict, strict=True))
    key_repr = {column: values[f"new_{column}"] for column in key_columns}
    new_repr = {column: values[f"new_{column}"] for column in non_key_columns}
    old_repr = {column: values[f"old_{column}"] for column in non_key_columns}
    raise conflict_error_cls(
        f"{table}: key {key_repr} already exists with a different value — "
        f"existing={old_repr!r}, incoming={new_repr!r}"
    )
