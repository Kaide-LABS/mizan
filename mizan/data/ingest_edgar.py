"""mizan/data/ingest_edgar.py — SEC EDGAR ingestion: rate limiter, CIK resolution, raw cache.

Implements PHASE_2_SPEC.md §4.2, §6.1, §6.3.

Every network-touching function here follows the single cache-hit/cache-miss shape PHASE_2_SPEC.md
§6.2 fixes: `is_cached()` is checked before the rate limiter is touched at all, so a fully-cached
batch run issues zero HTTP requests. On a cache miss, the raw response bytes are written to the
cache *before* any row-shape validation raises — a shape drift is a HALT-for-human condition
(`ULTIMATE_PRD.md` §4.1), never a silently-discarded fetch, and the raw bytes must still be on disk
for a human to inspect (mirrors the Tiingo anomaly-scan ordering, PHASE_2_SPEC.md §6.4).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx

from mizan.data.models import CompanyTickerEntry, EdgarFactRow, EdgarSubmissionRecord
from mizan.data.raw_cache import cache_path, is_cached, read_raw_json, write_raw_json

if TYPE_CHECKING:
    from pathlib import Path

# The real, non-placeholder contact identity SEC EDGAR's fair-access policy requires
# (docs/modernization_log.md §6.1: "Behaviour without a declared UA: HTTP 403"). Decided by the
# project owner for this build, not invented here.
_EDGAR_USER_AGENT = "Mizan research sandbox schoolbalogun@gmail.com"

_EDGAR_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_EDGAR_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_EDGAR_COMPANYCONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json"
)

_MIN_REQUEST_SPACING_SECONDS = 0.12
_BLOCK_COOLDOWN_SECONDS = 600.0

_SUBMISSION_FIELDS = frozenset(EdgarSubmissionRecord.model_fields)

_LEGAL_SUFFIXES = frozenset(
    {"CORPORATION", "CORP", "INCORPORATED", "INC", "COMPANY", "CO", "LIMITED", "LTD", "PLC"}
)


class CikResolutionError(RuntimeError):
    """Raised when a ticker cannot be resolved to a CIK, or the resolved CIK's submissions `name`
    does not match company_tickers.json's `title` for that ticker (ULTIMATE_PRD.md §4.1)."""


class MissingCompanyFactsError(RuntimeError):
    """Raised when a CIK's companyfacts (or companyconcept) response is empty or has no usable
    facts/units data at all."""


class MissingSicError(RuntimeError):
    """Raised when a CIK's submissions record is missing or carries no `sic` key."""


class EdgarBlockedError(RuntimeError):
    """Raised on an HTTP 403 received with a well-formed, fully-declared request, or on a 429 that
    persists across the one permitted cooldown-and-retry. Per ULTIMATE_PRD.md §4.1, a 403 on a
    correct request means the header contract itself broke — this is NOT retried into a longer
    block; it halts immediately."""


class _EdgarRateLimiter:
    """Enforces ULTIMATE_PRD.md §4.1's EDGAR policy: >=0.12s spacing between requests; on a 429,
    sleep >=600s at zero request rate before the next attempt, flooring any Retry-After header at
    600 rather than trusting a shorter value.

    Module-private — an implementation detail of the ingest functions below, all of which route
    their HTTP calls through the single module-level `_rate_limiter` instance so that spacing is
    enforced across every EDGAR endpoint this module calls, not just within one function.
    """

    def __init__(self) -> None:
        self._last_request_at: float | None = None

    def wait_for_slot(self) -> None:
        """Block until at least `_MIN_REQUEST_SPACING_SECONDS` has elapsed since the last
        request."""
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < _MIN_REQUEST_SPACING_SECONDS:
                time.sleep(_MIN_REQUEST_SPACING_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    def note_block(self, retry_after_seconds: float | None) -> None:
        """Sleep the greater of `retry_after_seconds` and `_BLOCK_COOLDOWN_SECONDS`."""
        wait = max(retry_after_seconds or 0.0, _BLOCK_COOLDOWN_SECONDS)
        time.sleep(wait)
        self._last_request_at = time.monotonic()


_rate_limiter = _EdgarRateLimiter()


def _edgar_headers(url: str) -> dict[str, str]:
    """Build the required header triple (User-Agent, Accept-Encoding, Host) for one EDGAR request.

    G-E2 (PHASE_2_SPEC.md §7): this is the one literal header-construction site; every EDGAR
    request routes through `_edgar_get`, which calls this function, so the header triple is never
    optional or conditional.
    """
    host = httpx.URL(url).host
    return {
        "User-Agent": _EDGAR_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": host,
    }


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse a numeric `Retry-After` header value, if present and numeric."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _edgar_get(client: httpx.Client, url: str) -> httpx.Response:
    """Issue one rate-limited GET against `url`, applying PHASE_2_SPEC.md §6.1's retry contract.

    A 403 always halts immediately (never retried). A 429 triggers exactly one cooldown-and-retry;
    a second consecutive block is itself a HALT, not a longer wait (ULTIMATE_PRD.md §4.5's
    "a retry loop against a still-stuck remote endpoint is an infinite hang, not a recovery").
    """
    headers = _edgar_headers(url)

    _rate_limiter.wait_for_slot()
    response = client.get(url, headers=headers)
    if response.status_code == 403:
        raise EdgarBlockedError(
            f"EDGAR returned 403 for a fully-headered request to {url} — the header contract "
            "itself is broken, not a rate-limit condition; not retrying"
        )
    if response.status_code == 429:
        _rate_limiter.note_block(_parse_retry_after(response))
        response = client.get(url, headers=headers)
        if response.status_code == 403:
            raise EdgarBlockedError(
                f"EDGAR returned 403 for a fully-headered request to {url} on retry after cooldown"
            )
        if response.status_code == 429:
            raise EdgarBlockedError(
                f"EDGAR is still rate-limiting {url} after a {_BLOCK_COOLDOWN_SECONDS:.0f}s "
                "cooldown retry — halting rather than retrying indefinitely"
            )
    response.raise_for_status()
    return response


def _names_match(name_a: str, name_b: str) -> bool:
    """Case/whitespace/legal-suffix-insensitive company-name comparator.

    Written out by hand rather than via a fuzzy-match library (PHASE_2_SPEC.md §6.3): a
    false-negative here (a real ticker→CIK drift waved through) is exactly the failure
    `ULTIMATE_PRD.md` §4.1 wants caught, and a fuzzy-match library's tunable threshold would hide
    the actual comparison rule a review agent needs to be able to read.
    """
    return _normalize_company_name(name_a) == _normalize_company_name(name_b)


def _normalize_company_name(name: str) -> str:
    """Uppercase, strip punctuation, and drop common legal-entity suffixes from a company name."""
    cleaned = name.strip().upper().replace(".", "").replace(",", "")
    words = [word for word in cleaned.split() if word not in _LEGAL_SUFFIXES]
    return " ".join(words)


def _slice_submission_fields(data: dict[str, object]) -> dict[str, object]:
    """Keep only the keys `EdgarSubmissionRecord` declares, discarding the dozens of unrelated SEC
    fields (addresses, former names, filing history, ...) so `extra="forbid"` stays meaningful."""
    return {key: value for key, value in data.items() if key in _SUBMISSION_FIELDS}


def _require_json_object(value: object, *, context: str) -> dict[str, object]:
    """Narrow a parsed-JSON `object` to `dict[str, object]`, raising a clear error otherwise."""
    if not isinstance(value, dict):
        raise MissingCompanyFactsError(f"{context}: expected a JSON object, got {type(value)!r}")
    return value


def fetch_company_tickers(*, cache_dir: Path, client: httpx.Client) -> Path:
    """Fetch (or return the cached copy of) https://www.sec.gov/files/company_tickers.json.

    Cache-hit short-circuits with zero HTTP requests (acceptance criterion 1). Returns the cache
    path.
    """
    path = cache_path(cache_dir=cache_dir, source="edgar/company_tickers", key="company_tickers")
    if is_cached(path):
        return path
    response = _edgar_get(client, _EDGAR_COMPANY_TICKERS_URL)
    write_raw_json(path, response.content)
    return path


def resolve_cik(ticker: str, *, cache_dir: Path, client: httpx.Client) -> str:
    """Resolve `ticker` to a zero-padded 10-digit CIK string (e.g. "0000320193").

    Calls `fetch_company_tickers()` first (cache-aware), looks up `ticker` case-insensitively among
    the parsed `CompanyTickerEntry` rows, zero-pads via `f"{cik_str:010d}"`, then cross-checks:
    fetches (cache-aware) that CIK's submissions record and compares its `name` against the matched
    entry's `title`. A normalized-string mismatch raises `CikResolutionError`
    (`ULTIMATE_PRD.md` §4.1's "ticker→CIK drift, e.g. post-merger" guard). A ticker absent from
    company_tickers.json also raises `CikResolutionError`.
    """
    tickers_path = fetch_company_tickers(cache_dir=cache_dir, client=client)
    raw_tickers = _require_json_object(read_raw_json(tickers_path), context="company_tickers.json")
    entries = [CompanyTickerEntry.model_validate(entry) for entry in raw_tickers.values()]

    match = next((entry for entry in entries if entry.ticker.upper() == ticker.upper()), None)
    if match is None:
        raise CikResolutionError(f"{ticker!r} not found in company_tickers.json")

    cik10 = f"{match.cik_str:010d}"
    submissions_path = ingest_edgar_submissions(cik10, cache_dir=cache_dir, client=client)
    raw_submissions = _require_json_object(
        read_raw_json(submissions_path), context=f"submissions CIK{cik10}"
    )
    record = EdgarSubmissionRecord.model_validate(_slice_submission_fields(raw_submissions))

    if not _names_match(record.name, match.title):
        raise CikResolutionError(
            f"{ticker!r}: company_tickers.json title {match.title!r} vs submissions name "
            f"{record.name!r} — possible CIK drift (merger/rename)"
        )
    return cik10


def ingest_edgar_submissions(
    cik: str, *, cache_dir: Path, client: httpx.Client, force_refetch: bool = False
) -> Path:
    """Fetch (or return cached) https://data.sec.gov/submissions/CIK{cik}.json.

    Raises `MissingSicError` if the response is missing or carries an empty `sic` key. Returns the
    cache `Path` on success. `force_refetch=True` bypasses the cache-hit short-circuit — the one
    parameter this function has purely for operator-driven re-pulls; no production call site
    (the CLI, PHASE_2_SPEC.md §4.4) sets it `True` by default.
    """
    path = cache_path(cache_dir=cache_dir, source="edgar/submissions", key=cik)
    if is_cached(path) and not force_refetch:
        return path

    response = _edgar_get(client, _EDGAR_SUBMISSIONS_URL.format(cik=cik))
    write_raw_json(path, response.content)

    data = _require_json_object(read_raw_json(path), context=f"submissions CIK{cik}")
    sic = data.get("sic")
    if not isinstance(sic, str) or not sic.strip():
        raise MissingSicError(f"CIK {cik}: submissions response missing or empty `sic`")
    EdgarSubmissionRecord.model_validate(_slice_submission_fields(data))
    return path


def ingest_edgar_companyfacts(
    cik: str, *, cache_dir: Path, client: httpx.Client, force_refetch: bool = False
) -> Path:
    """Fetch (or return cached) https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json.

    Raises `MissingCompanyFactsError` if the response has no `facts` key or `facts` is empty. Every
    fact object under `facts.{taxonomy}.{tag}.units.{unit}` is validated against `EdgarFactRow` —
    a shape drift raises `pydantic.ValidationError`, surfaced to the caller unwrapped (the
    "malformed/undocumented XBRL tag drift" guard, `ULTIMATE_PRD.md` §4.1). The raw response is
    written to cache before this validation runs, so a flagged CIK's data is still on disk for a
    human to inspect.
    """
    path = cache_path(cache_dir=cache_dir, source="edgar/companyfacts", key=cik)
    if is_cached(path) and not force_refetch:
        return path

    response = _edgar_get(client, _EDGAR_COMPANYFACTS_URL.format(cik=cik))
    write_raw_json(path, response.content)

    data = _require_json_object(read_raw_json(path), context=f"companyfacts CIK{cik}")
    facts = data.get("facts")
    if not isinstance(facts, dict) or not facts:
        raise MissingCompanyFactsError(f"CIK {cik}: companyfacts response has no `facts` data")
    _validate_all_fact_rows(facts)
    return path


def ingest_edgar_companyconcept(
    cik: str,
    taxonomy: str,
    tag: str,
    *,
    cache_dir: Path,
    client: httpx.Client,
    force_refetch: bool = False,
) -> Path:
    """Fetch (or return cached)
    https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json.

    Same validation/HALT contract as `ingest_edgar_companyfacts`. Named separately per
    `ULTIMATE_PRD.md` §6's phase-ships line ("companyfacts + companyconcept + submissions") — a
    later phase may prefer the narrower companyconcept call for a single tag rather than the full
    companyfacts dump; both are cached identically.
    """
    path = cache_path(
        cache_dir=cache_dir, source="edgar/companyconcept", key=f"{cik}_{taxonomy}_{tag}"
    )
    if is_cached(path) and not force_refetch:
        return path

    url = _EDGAR_COMPANYCONCEPT_URL.format(cik=cik, taxonomy=taxonomy, tag=tag)
    response = _edgar_get(client, url)
    write_raw_json(path, response.content)

    data = _require_json_object(read_raw_json(path), context=f"companyconcept CIK{cik}/{tag}")
    units = data.get("units")
    if not isinstance(units, dict) or not units:
        raise MissingCompanyFactsError(
            f"CIK {cik} {taxonomy}/{tag}: companyconcept response has no `units` data"
        )
    _validate_unit_rows(units)
    return path


def _validate_all_fact_rows(facts: dict[str, object]) -> None:
    """Validate every fact object under `facts.{taxonomy}.{tag}.units.{unit}` against
    `EdgarFactRow`, letting `pydantic.ValidationError` propagate unwrapped on drift."""
    for taxonomy_value in facts.values():
        if not isinstance(taxonomy_value, dict):
            continue
        for tag_value in taxonomy_value.values():
            if not isinstance(tag_value, dict):
                continue
            units = tag_value.get("units")
            if isinstance(units, dict):
                _validate_unit_rows(units)


def _validate_unit_rows(units: dict[str, object]) -> None:
    """Validate every fact object under `units.{unit}` against `EdgarFactRow`."""
    for rows in units.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                EdgarFactRow.model_validate(row)
