"""mizan/data/db.py — DuckDB connection + idempotent schema creation.

Implements PHASE_3_SPEC.md §4.1, §5.

DuckDB permits one writer per database file (docs/modernization_log.md §5.4); this module is the
one canonical home for opening a connection and creating the two Phase 3 tables
(`fundamentals_facts`, `price_bars`), so `mizan/data/normalize.py`'s row-mapping/business logic
never has to know how the schema is created, and every later phase's read-only consumer imports
this module rather than re-deriving the DDL (§1's own justification for this file's existence).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from pathlib import Path

    from mizan.crypto.models import CandleBar

#: Column order `fundamentals_facts` is created with (§5.1) — the defensive column-set check in
#: `ensure_schema` compares an already-existing table's actual columns against this tuple.
_FUNDAMENTALS_FACTS_COLUMNS: tuple[str, ...] = (
    "cik",
    "taxonomy",
    "tag",
    "unit",
    "period_start",
    "period_end",
    "is_instantaneous",
    "value",
    "accn",
    "fy",
    "fp",
    "form",
    "filed",
)

#: Column order `price_bars` is created with (§5.2).
_PRICE_BARS_COLUMNS: tuple[str, ...] = (
    "ticker",
    "trade_date",
    "raw_open",
    "raw_high",
    "raw_low",
    "raw_close",
    "volume",
    "adj_open",
    "adj_high",
    "adj_low",
    "adj_close",
    "adj_volume",
    "div_cash",
    "split_factor",
)
_CANDLES_COLUMNS: tuple[str, ...] = (
    "exchange", "symbol", "granularity", "ts", "open", "high", "low", "close",
    "volume", "source", "ingested_at",
)

_CREATE_FUNDAMENTALS_FACTS = """
    CREATE TABLE IF NOT EXISTS fundamentals_facts (
        cik              VARCHAR NOT NULL,
        taxonomy         VARCHAR NOT NULL,
        tag              VARCHAR NOT NULL,
        unit             VARCHAR NOT NULL,
        period_start     DATE    NOT NULL,
        period_end       DATE    NOT NULL,
        is_instantaneous BOOLEAN NOT NULL,
        value            DOUBLE  NOT NULL,
        accn             VARCHAR NOT NULL,
        fy               INTEGER NOT NULL,
        fp               VARCHAR NOT NULL,
        form             VARCHAR NOT NULL,
        filed            DATE    NOT NULL,
        PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn)
    )
"""

_CREATE_PRICE_BARS = """
    CREATE TABLE IF NOT EXISTS price_bars (
        ticker       VARCHAR NOT NULL,
        trade_date   DATE    NOT NULL,
        raw_open     DOUBLE  NOT NULL,
        raw_high     DOUBLE  NOT NULL,
        raw_low      DOUBLE  NOT NULL,
        raw_close    DOUBLE  NOT NULL,
        volume       BIGINT  NOT NULL,
        adj_open     DOUBLE  NOT NULL,
        adj_high     DOUBLE  NOT NULL,
        adj_low      DOUBLE  NOT NULL,
        adj_close    DOUBLE  NOT NULL,
        adj_volume   BIGINT  NOT NULL,
        div_cash     DOUBLE  NOT NULL,
        split_factor DOUBLE  NOT NULL,
        PRIMARY KEY (ticker, trade_date)
    )
"""
_CREATE_CANDLES = """
    CREATE TABLE IF NOT EXISTS candles (
        exchange VARCHAR NOT NULL, symbol VARCHAR NOT NULL, granularity VARCHAR NOT NULL,
        ts TIMESTAMP NOT NULL, open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL,
        close DOUBLE NOT NULL, volume DOUBLE NOT NULL, source VARCHAR NOT NULL,
        ingested_at TIMESTAMP NOT NULL, PRIMARY KEY (exchange, symbol, granularity, ts)
    )
"""


class SchemaError(RuntimeError):
    """Raised when `ensure_schema` detects that an already-existing table's column set disagrees
    with what this module expects to create.

    A defensive check only: `CREATE TABLE IF NOT EXISTS` silently no-ops against an existing table
    of the same name regardless of its actual columns, so without this check a DuckDB file created
    by an incompatible earlier/later version of this module would pass `ensure_schema` silently and
    fail confusingly on the first mismatched `INSERT`. V1 has no migration path (§5.3): a
    disagreement here means the file must be regenerated from the raw cache, not silently altered.
    """


def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open (creating if absent) the DuckDB database file at `db_path`.

    Creates `db_path`'s parent directories first. When `read_only=False` (the default, used by
    every Phase 3 write path), calls `ensure_schema(con)` before returning, so no caller can obtain
    a writable connection to a database missing either table. `read_only=True` (for Phase 4+
    read-only consumers) skips schema creation — DuckDB's own read-only mode does not permit DDL
    anyway.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con: duckdb.DuckDBPyConnection = duckdb.connect(database=str(db_path), read_only=read_only)
    if not read_only:
        ensure_schema(con)
    return con


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Idempotently `CREATE TABLE IF NOT EXISTS` both `fundamentals_facts` and `price_bars`.

    Never drops, alters, or re-creates an existing table (§5.3 — no versioned migration framework
    in V1). Safe to call on every `connect()` — the second and subsequent calls in a process (or
    across processes against the same file) are no-ops, verified by the defensive column-set check
    below rather than assumed.

    Raises:
        SchemaError: if a table with the expected name already exists but its actual column set
            does not match what this module would create — signalling an incompatible schema
            version on disk (§5.3's "delete and regenerate from raw cache" remedy applies).
    """
    con.execute(_CREATE_FUNDAMENTALS_FACTS)
    _verify_columns(con, table="fundamentals_facts", expected_columns=_FUNDAMENTALS_FACTS_COLUMNS)
    con.execute(_CREATE_PRICE_BARS)
    _verify_columns(con, table="price_bars", expected_columns=_PRICE_BARS_COLUMNS)
    con.execute(_CREATE_CANDLES)
    _verify_columns(con, table="candles", expected_columns=_CANDLES_COLUMNS)


def upsert_candles(con: duckdb.DuckDBPyConnection, bars: tuple[CandleBar, ...]) -> int:
    """Insert normalized candles idempotently; batching is a later optimization."""
    from datetime import UTC, datetime

    for bar in bars:
        ingested_at = datetime.now(UTC).replace(tzinfo=None)
        con.execute(
            "INSERT OR REPLACE INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bar.exchange, bar.symbol, bar.granularity, bar.ts.replace(tzinfo=None), bar.open,
             bar.high, bar.low, bar.close, bar.volume, bar.source, ingested_at),
        )
    return len(bars)


def _verify_columns(
    con: duckdb.DuckDBPyConnection, *, table: str, expected_columns: tuple[str, ...]
) -> None:
    """Raise `SchemaError` if `table`'s actual column names/order disagree with `expected_columns`.

    Uses `PRAGMA table_info(...)`, whose second result column is the column name in creation
    order (verified live against DuckDB 1.5.5, docs/modernization_log.md §5.4).
    """
    rows = con.execute(f"PRAGMA table_info('{table}')").fetchall()
    actual_columns = tuple(str(row[1]) for row in rows)
    if actual_columns != expected_columns:
        raise SchemaError(
            f"table {table!r} already exists with an incompatible column set: "
            f"expected {expected_columns}, found {actual_columns}. This DuckDB file was created by "
            f"a different version of mizan.data.db — regenerate it from the raw cache (§5.3), do "
            f"not alter it in place."
        )
