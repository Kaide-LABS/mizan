"""mizan/data/raw_cache.py — shared replayable-cache helpers.

Implements PHASE_2_SPEC.md §4.1, §6.2.

The replayable cache mechanics — path construction, cache-hit detection, atomic write — are
identical in shape for both ingestion legs even though their *rate-limiting* mechanics are
deliberately different (`ULTIMATE_PRD.md` §6, "the two ingestion jobs must not share one
rate-limiter implementation"). This module is the one canonical home for cache-hit/write logic so
`mizan/data/ingest_edgar.py` and `mizan/data/ingest_tiingo.py` cannot drift on exactly the property
(idempotent replay) that acceptance criterion 1 tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class RawCacheError(RuntimeError):
    """Raised on a cache-layer inconsistency (e.g. a cached file that fails to parse as JSON)."""


def cache_path(*, cache_dir: Path, source: str, key: str, ext: str = "json") -> Path:
    """Compute the deterministic path for one cached artifact.

    Args:
        cache_dir: the ingestion job's cache root (CLI-supplied, PHASE_2_SPEC.md §4.4).
        source: one of "edgar/company_tickers", "edgar/companyfacts", "edgar/companyconcept",
            "edgar/submissions", "tiingo/eod" — a fixed, closed set (PHASE_2_SPEC.md §6.2); not
            free-form, so the directory layout is predictable and grep-able for a review agent.
        key: the cache key proper — e.g. a zero-padded CIK for EDGAR legs, or
            f"{ticker}_{start_date.isoformat()}_{end_date.isoformat()}" for Tiingo — NEVER the raw
            request URL and NEVER including any token/credential (`ULTIMATE_PRD.md` §4.2 NEW row:
            "API token leaked into the on-disk raw cache").
        ext: file extension, "json" for every Phase 2 artifact (no Parquet yet — see
            PHASE_2_SPEC.md §9).

    Returns:
        `cache_dir / source / f"{key}.{ext}"`, constructed with `pathlib` only (no string
        concatenation), so the same `(source, key)` always yields the same `Path` across processes
        and OSes.
    """
    return cache_dir / source / f"{key}.{ext}"


def is_cached(path: Path) -> bool:
    """Return True iff `path` exists and is non-empty.

    The sole idempotency check every ingest function calls before making any HTTP request
    (PHASE_2_SPEC.md §6.2) — this function performs no I/O beyond `stat()`.
    """
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def write_raw_json(path: Path, payload: bytes) -> None:
    """Write `payload` to `path` atomically.

    Writes to `path.with_suffix(path.suffix + ".tmp")`, then `os.replace`s it into place, creating
    parent directories as needed. `payload` is the raw response body exactly as received — no
    re-serialization, no key reordering, no pretty-printing that could diverge from what the source
    actually sent (`MASTER_PRD.md` §5.3, "I can prove what the data said"). Row-shape validation
    (PHASE_2_SPEC.md §3) happens on READ, not on write, so the cache is a faithful record even in
    the rare case a row-shape model needs a fix later (`ULTIMATE_PRD.md` §6, "later phases must
    reprocess raw, not re-fetch").
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(payload)
    os.replace(tmp_path, path)


def read_raw_json(path: Path) -> object:
    """Read and `json.loads` the cached file.

    Return type is deliberately the permissive `object` rather than `dict[str, object]`: every
    EDGAR endpoint this phase caches (§6.2) returns a top-level JSON *object*, but Tiingo's EOD
    endpoint returns a top-level JSON *array* of bars (verified against `docs/modernization_log.md`
    §6.2's response-field table together with Tiingo's own documented example payloads). A cache
    reader shared by both legs cannot claim a `dict` shape by construction without lying about one
    of them — callers narrow the type themselves (`isinstance` checks in `ingest_edgar.py` /
    `ingest_tiingo.py`) before indexing into the parsed value.

    Raises:
        RawCacheError: wrapping the underlying `JSONDecodeError` on a corrupt cache file — never
            returns a partial/best-effort parse.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RawCacheError(f"corrupt cache file at {path}: {exc}") from exc
