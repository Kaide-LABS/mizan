"""Tests for mizan/data/db.py.

Implements PHASE_3_SPEC.md §8 acceptance criteria 5 (DuckDB file never committed — the `.gitignore`
half is verified here via a real on-disk file appearing where expected; the git-side half is a
manual `git status`/`git log` check, not a pytest concern), 10 (single-writer contention surfaces,
not retried), 12 (`ensure_schema` idempotent), and guards G-DB1, G-DB2 (partially), G-N2's DDL
backstop.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pytest

from mizan.data import db

# ── connect() (§4.1) ─────────────────────────────────────────────────────────────────────────────


def test_connect_creates_parent_directories(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "mizan.duckdb"

    con = db.connect(db_path)
    try:
        assert db_path.parent.is_dir()
        assert db_path.is_file()
    finally:
        con.close()


def test_connect_ensures_schema_by_default(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "mizan.duckdb")
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert {"fundamentals_facts", "price_bars"} <= tables
    finally:
        con.close()


def test_connect_read_only_does_not_create_schema_on_a_new_file(tmp_path: Path) -> None:
    db_path = tmp_path / "never_created.duckdb"

    with pytest.raises(Exception):  # noqa: B017, PT011 -- DuckDB's own IO error class, not ours
        db.connect(db_path, read_only=True)

    assert not db_path.exists()


def test_connect_read_only_can_read_an_already_created_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "mizan.duckdb"
    writer = db.connect(db_path)
    writer.close()

    reader = db.connect(db_path, read_only=True)
    try:
        tables = {row[0] for row in reader.execute("SHOW TABLES").fetchall()}
        assert {"fundamentals_facts", "price_bars"} <= tables
    finally:
        reader.close()


# ── ensure_schema idempotency (AC12) ────────────────────────────────────────────────────────────


def test_ensure_schema_is_idempotent(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "mizan.duckdb")
    try:
        db.ensure_schema(con)
        db.ensure_schema(con)
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert {"fundamentals_facts", "price_bars"} <= tables
    finally:
        con.close()


def test_ensure_schema_raises_on_incompatible_existing_table(tmp_path: Path) -> None:
    con = duckdb.connect(database=str(tmp_path / "mizan.duckdb"))
    try:
        con.execute("CREATE TABLE fundamentals_facts (only_one_column VARCHAR)")
        with pytest.raises(db.SchemaError):
            db.ensure_schema(con)
    finally:
        con.close()


# ── PRIMARY KEY constraint enforcement (backstop for G-N2/G-N3) ────────────────────────────────


def test_fundamentals_facts_primary_key_rejects_a_duplicate_key_insert(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "mizan.duckdb")
    try:
        insert = (
            "INSERT INTO fundamentals_facts VALUES "
            "('0000320193', 'us-gaap', 'Assets', 'USD', '2020-09-26', '2020-09-26', true, "
            "100.0, '0000320193-20-000096', 2020, 'FY', '10-K', '2020-10-30')"
        )
        con.execute(insert)
        with pytest.raises(duckdb.ConstraintException):
            con.execute(insert.replace("100.0", "999.0"))
    finally:
        con.close()


def test_price_bars_primary_key_rejects_a_duplicate_key_insert(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "mizan.duckdb")
    try:
        insert = (
            "INSERT INTO price_bars VALUES "
            "('AAPL', '2020-01-01', 100.0, 101.0, 99.0, 100.5, 1000, "
            "99.0, 100.0, 98.0, 99.5, 900, 0.0, 1.0)"
        )
        con.execute(insert)
        with pytest.raises(duckdb.ConstraintException):
            con.execute(insert.replace("100.5", "200.0"))
    finally:
        con.close()


# ── Single-writer contention surfaces as a raised error, not a retry (AC10, G-DB1) ─────────────
#
# Verified live (docs/modernization_log.md §5.4 correction): DuckDB 1.5.5's Python API caches one
# underlying database instance per file path WITHIN a single process — a second `db.connect()` call
# against a path already open in the SAME process shares that instance and does not raise. The real
# single-writer file lock is enforced by the OS, across processes, so G-DB1's guard is exercised
# with a second real process here, not a second same-process connection.


def test_second_writable_connection_to_a_locked_file_raises_across_processes(
    tmp_path: Path,
) -> None:
    """A second OS process trying to open a DuckDB file already held open (non-read-only) by this
    process hits DuckDB's real single-writer file lock and raises — uncaught, un-retried, exactly
    what `mizan/data/db.py` and `mizan/cli/normalize.py` must never wrap in a retry loop."""
    db_path = tmp_path / "mizan.duckdb"
    holder_script = tmp_path / "_hold_lock.py"
    ready_flag = tmp_path / "ready.flag"
    holder_script.write_text(
        "import sys\n"
        "import time\n"
        "import duckdb\n"
        "con = duckdb.connect(sys.argv[1])\n"
        "con.execute('CREATE TABLE IF NOT EXISTS t (a INT)')\n"
        f"open(r'{ready_flag}', 'w', encoding='utf-8').close()\n"
        "time.sleep(10)\n",
        encoding="utf-8",
    )

    holder = subprocess.Popen([sys.executable, str(holder_script), str(db_path)])
    try:
        deadline = time.monotonic() + 5.0
        while not ready_flag.exists():
            if time.monotonic() > deadline:
                raise TimeoutError("holder process never signalled ready")
            time.sleep(0.05)

        with pytest.raises(Exception):  # noqa: B017, PT011 -- DuckDB's own IOException
            db.connect(db_path)
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_second_same_process_connection_shares_the_instance_and_does_not_raise(
    tmp_path: Path,
) -> None:
    """Documents the verified divergence above: within one process, a second `connect()` to the
    same path shares state with the first rather than hitting a lock error."""
    db_path = tmp_path / "mizan.duckdb"
    first = db.connect(db_path)
    try:
        second = db.connect(db_path)
        try:
            second.execute(
                "INSERT INTO price_bars VALUES "
                "('AAPL', '2020-01-01', 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1)"
            )
            count = first.execute("SELECT count(*) FROM price_bars").fetchone()
            assert count is not None
            assert count[0] == 1
        finally:
            second.close()
    finally:
        first.close()
