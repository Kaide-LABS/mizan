"""Tests for mizan/data/raw_cache.py.

Implements PHASE_2_SPEC.md §8 acceptance criteria 1 (replayability, via `is_cached`), 2 (cache
files are valid JSON), plus the module's own path-determinism and corruption-handling contracts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mizan.data.raw_cache import RawCacheError, cache_path, is_cached, read_raw_json, write_raw_json


def test_cache_path_is_deterministic(tmp_path: Path) -> None:
    """The same (cache_dir, source, key, ext) always yields the same Path."""
    first = cache_path(cache_dir=tmp_path, source="edgar/companyfacts", key="0000320193")
    second = cache_path(cache_dir=tmp_path, source="edgar/companyfacts", key="0000320193")

    assert first == second
    assert first == tmp_path / "edgar" / "companyfacts" / "0000320193.json"


def test_cache_path_defaults_to_json_extension(tmp_path: Path) -> None:
    """`ext` defaults to "json" — no Parquet artifact is ever produced in Phase 2 (§5, §9)."""
    path = cache_path(cache_dir=tmp_path, source="tiingo/eod", key="AAPL_2020-01-01_2020-01-02")

    assert path.suffix == ".json"


def test_is_cached_false_when_missing(tmp_path: Path) -> None:
    """A path that does not exist on disk is not cached."""
    missing = tmp_path / "edgar" / "submissions" / "0000320193.json"

    assert is_cached(missing) is False


def test_is_cached_false_when_empty(tmp_path: Path) -> None:
    """A zero-byte file does not count as a valid cache hit."""
    empty = tmp_path / "empty.json"
    empty.parent.mkdir(parents=True, exist_ok=True)
    empty.write_bytes(b"")

    assert is_cached(empty) is False


def test_is_cached_true_after_write_raw_json(tmp_path: Path) -> None:
    """`write_raw_json` produces a file `is_cached` recognizes."""
    path = tmp_path / "edgar" / "submissions" / "0000320193.json"
    write_raw_json(path, b'{"sic": "3571"}')

    assert is_cached(path) is True


def test_write_raw_json_creates_parent_directories(tmp_path: Path) -> None:
    """`write_raw_json` creates any missing parent directories."""
    path = tmp_path / "a" / "b" / "c" / "artifact.json"
    write_raw_json(path, b"{}")

    assert path.is_file()


def test_write_raw_json_leaves_no_tmp_file_behind(tmp_path: Path) -> None:
    """The atomic write (tmp file + os.replace) leaves only the final file, never the `.tmp`."""
    path = tmp_path / "edgar" / "submissions" / "0000320193.json"
    write_raw_json(path, b'{"sic": "3571"}')

    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert list(path.parent.iterdir()) == [path]


def test_write_raw_json_stores_bytes_verbatim(tmp_path: Path) -> None:
    """The cache is a byte-for-byte record of what was received — no re-serialization
    (`MASTER_PRD.md` §5.3, "I can prove what the data said")."""
    path = tmp_path / "raw.json"
    # Deliberately unusual key ordering/whitespace to prove no re-serialization occurs.
    payload = b'{"b": 2,   "a": 1}'
    write_raw_json(path, payload)

    assert path.read_bytes() == payload


def test_read_raw_json_round_trips_an_object(tmp_path: Path) -> None:
    """A cached JSON object round-trips through `read_raw_json` unchanged."""
    path = tmp_path / "object.json"
    write_raw_json(path, json.dumps({"cik": 320193, "sic": "3571"}).encode("utf-8"))

    result = read_raw_json(path)

    assert result == {"cik": 320193, "sic": "3571"}


def test_read_raw_json_round_trips_an_array(tmp_path: Path) -> None:
    """A cached JSON array (Tiingo's EOD response shape) round-trips unchanged."""
    path = tmp_path / "array.json"
    write_raw_json(path, json.dumps([{"date": "2020-01-01"}, {"date": "2020-01-02"}]).encode())

    result = read_raw_json(path)

    assert result == [{"date": "2020-01-01"}, {"date": "2020-01-02"}]


def test_read_raw_json_raises_raw_cache_error_on_corrupt_file(tmp_path: Path) -> None:
    """A corrupt cache file raises `RawCacheError`, never a partial/best-effort parse."""
    path = tmp_path / "corrupt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"{not valid json")

    with pytest.raises(RawCacheError):
        read_raw_json(path)
