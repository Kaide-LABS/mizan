"""Tests for mizan/data/ingest_edgar.py.

Implements PHASE_2_SPEC.md §8 acceptance criteria 1 (replayability), 3 (required header triple),
4 (rate limiting actually sleeps), 6 (CIK resolution zero-pads and cross-checks), 9 (extra="forbid"
catches XBRL drift, wired into the ingest path itself) and guards G-E1 through G-E6.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from mizan.data import ingest_edgar

_VALID_FACT_ROW: dict[str, object] = {
    "start": "2019-09-29",
    "end": "2020-09-26",
    "val": 100.0,
    "accn": "0000320193-20-000096",
    "fy": 2020,
    "fp": "FY",
    "form": "10-K",
    "filed": "2020-10-30",
}

_VALID_SUBMISSION: dict[str, object] = {
    "cik": 320193,
    "entityType": "operating",
    "sic": "3571",
    "sicDescription": "Electronic Computers",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
}

_VALID_TICKERS_PAYLOAD: dict[str, object] = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
}


@pytest.fixture(autouse=True)
def _reset_edgar_rate_limiter() -> None:
    """Give every test a fresh rate-limiter instance so cross-test timing state never leaks."""
    ingest_edgar._rate_limiter = ingest_edgar._EdgarRateLimiter()


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _static_json_handler(
    payload: object, *, status_code: int = 200
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


def _counting_handler(
    payload: object | None, *, status_code: int = 200
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if payload is None:
            return httpx.Response(status_code)
        return httpx.Response(status_code, json=payload)

    return handler, captured


def _routing_handler(
    responses_by_path: dict[str, object],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        path = request.url.path
        if path not in responses_by_path:
            raise AssertionError(f"unexpected request to {request.url}")
        return httpx.Response(200, json=responses_by_path[path])

    return handler, captured


# ── Rate limiter (G-E1, AC4) ────────────────────────────────────────────────────────────────────


def test_wait_for_slot_sleeps_to_enforce_minimum_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    readings = iter([0.0, 0.0, 0.01, 0.20])
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: next(readings))
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    limiter = ingest_edgar._EdgarRateLimiter()
    limiter.wait_for_slot()
    limiter.wait_for_slot()

    assert sleep_calls == [pytest.approx(0.11)]


def test_wait_for_slot_does_not_sleep_when_spacing_already_sufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readings = iter([0.0, 0.0, 1.0, 1.0])
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: next(readings))
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    limiter = ingest_edgar._EdgarRateLimiter()
    limiter.wait_for_slot()
    limiter.wait_for_slot()

    assert sleep_calls == []


def test_note_block_floors_wait_at_600_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    ingest_edgar._EdgarRateLimiter().note_block(5.0)

    assert sleep_calls == [600.0]


def test_note_block_defaults_to_600_when_retry_after_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    ingest_edgar._EdgarRateLimiter().note_block(None)

    assert sleep_calls == [600.0]


def test_note_block_honours_a_longer_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    ingest_edgar._EdgarRateLimiter().note_block(900.0)

    assert sleep_calls == [900.0]


# ── Header contract (AC3, G-E2) ──────────────────────────────────────────────────────────────────


def test_edgar_requests_carry_the_required_header_triple(tmp_path: Path) -> None:
    handler, captured = _counting_handler(_VALID_TICKERS_PAYLOAD)

    with _client_with_handler(handler) as client:
        ingest_edgar.fetch_company_tickers(cache_dir=tmp_path, client=client)

    assert len(captured) == 1
    headers = captured[0].headers
    assert headers["User-Agent"] == "Mizan research sandbox schoolbalogun@gmail.com"
    assert "@" in headers["User-Agent"]
    assert headers["Accept-Encoding"] == "gzip, deflate"
    assert headers["Host"] == "www.sec.gov"


# ── 403 / 429 handling (G-E1, G-E2) ──────────────────────────────────────────────────────────────


def test_403_on_a_fully_headered_request_raises_immediately_without_retry(tmp_path: Path) -> None:
    handler, captured = _counting_handler(None, status_code=403)

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.EdgarBlockedError):
        ingest_edgar.fetch_company_tickers(cache_dir=tmp_path, client=client)

    assert len(captured) == 1


def test_429_retries_once_then_halts_on_a_second_consecutive_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    handler, captured = _counting_handler(None, status_code=429)

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.EdgarBlockedError):
        ingest_edgar.fetch_company_tickers(cache_dir=tmp_path, client=client)

    assert len(captured) == 2


def test_429_then_200_succeeds_after_one_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=_VALID_TICKERS_PAYLOAD)

    with _client_with_handler(handler) as client:
        path = ingest_edgar.fetch_company_tickers(cache_dir=tmp_path, client=client)

    assert call_count == 2
    assert path.is_file()


# ── Replayability (AC1) ─────────────────────────────────────────────────────────────────────────


def test_fetch_company_tickers_cache_hit_issues_zero_requests(tmp_path: Path) -> None:
    handler, captured = _counting_handler(_VALID_TICKERS_PAYLOAD)

    with _client_with_handler(handler) as client:
        first = ingest_edgar.fetch_company_tickers(cache_dir=tmp_path, client=client)
        assert len(captured) == 1
        second = ingest_edgar.fetch_company_tickers(cache_dir=tmp_path, client=client)

    assert len(captured) == 1
    assert first == second


def test_ingest_edgar_submissions_cache_hit_issues_zero_requests(tmp_path: Path) -> None:
    handler, captured = _counting_handler(_VALID_SUBMISSION)

    with _client_with_handler(handler) as client:
        first = ingest_edgar.ingest_edgar_submissions(
            "0000320193", cache_dir=tmp_path, client=client
        )
        assert len(captured) == 1
        second = ingest_edgar.ingest_edgar_submissions(
            "0000320193", cache_dir=tmp_path, client=client
        )

    assert len(captured) == 1
    assert first == second


def test_ingest_edgar_companyfacts_cache_hit_issues_zero_requests(tmp_path: Path) -> None:
    payload = {
        "cik": 320193,
        "facts": {"us-gaap": {"Assets": {"units": {"USD": [_VALID_FACT_ROW]}}}},
    }
    handler, captured = _counting_handler(payload)

    with _client_with_handler(handler) as client:
        first = ingest_edgar.ingest_edgar_companyfacts(
            "0000320193", cache_dir=tmp_path, client=client
        )
        assert len(captured) == 1
        second = ingest_edgar.ingest_edgar_companyfacts(
            "0000320193", cache_dir=tmp_path, client=client
        )

    assert len(captured) == 1
    assert first == second


def test_ingest_edgar_companyconcept_cache_hit_issues_zero_requests(tmp_path: Path) -> None:
    payload = {
        "cik": 320193,
        "taxonomy": "us-gaap",
        "tag": "Assets",
        "units": {"USD": [_VALID_FACT_ROW]},
    }
    handler, captured = _counting_handler(payload)

    with _client_with_handler(handler) as client:
        first = ingest_edgar.ingest_edgar_companyconcept(
            "0000320193", "us-gaap", "Assets", cache_dir=tmp_path, client=client
        )
        assert len(captured) == 1
        second = ingest_edgar.ingest_edgar_companyconcept(
            "0000320193", "us-gaap", "Assets", cache_dir=tmp_path, client=client
        )

    assert len(captured) == 1
    assert first == second


def test_force_refetch_bypasses_the_cache(tmp_path: Path) -> None:
    handler, captured = _counting_handler(_VALID_SUBMISSION)

    with _client_with_handler(handler) as client:
        ingest_edgar.ingest_edgar_submissions("0000320193", cache_dir=tmp_path, client=client)
        ingest_edgar.ingest_edgar_submissions(
            "0000320193", cache_dir=tmp_path, client=client, force_refetch=True
        )

    assert len(captured) == 2


# ── resolve_cik (AC6, G-E5) ──────────────────────────────────────────────────────────────────────


def test_resolve_cik_zero_pads_and_cross_checks_successfully(tmp_path: Path) -> None:
    handler, _ = _routing_handler(
        {
            "/files/company_tickers.json": _VALID_TICKERS_PAYLOAD,
            "/submissions/CIK0000320193.json": _VALID_SUBMISSION,
        }
    )

    with _client_with_handler(handler) as client:
        cik = ingest_edgar.resolve_cik("aapl", cache_dir=tmp_path, client=client)

    assert cik == "0000320193"
    assert len(cik) == 10


def test_resolve_cik_raises_on_name_title_mismatch(tmp_path: Path) -> None:
    drifted_submission = {**_VALID_SUBMISSION, "name": "Totally Different Corp"}
    handler, _ = _routing_handler(
        {
            "/files/company_tickers.json": _VALID_TICKERS_PAYLOAD,
            "/submissions/CIK0000320193.json": drifted_submission,
        }
    )

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.CikResolutionError):
        ingest_edgar.resolve_cik("AAPL", cache_dir=tmp_path, client=client)


def test_resolve_cik_raises_when_ticker_absent(tmp_path: Path) -> None:
    handler, _ = _routing_handler({"/files/company_tickers.json": _VALID_TICKERS_PAYLOAD})

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.CikResolutionError):
        ingest_edgar.resolve_cik("NOPE", cache_dir=tmp_path, client=client)


def test_names_match_ignores_case_punctuation_and_legal_suffix() -> None:
    assert ingest_edgar._names_match("Apple Inc.", "APPLE INC") is True
    assert ingest_edgar._names_match("Apple Inc.", "Apple Corporation") is True
    assert ingest_edgar._names_match("Apple Inc.", "Orange Inc.") is False


# ── MissingSicError (G-E4) ──────────────────────────────────────────────────────────────────────


def test_ingest_edgar_submissions_raises_missing_sic_error_when_key_absent(tmp_path: Path) -> None:
    payload = {k: v for k, v in _VALID_SUBMISSION.items() if k != "sic"}
    handler = _static_json_handler(payload)

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.MissingSicError):
        ingest_edgar.ingest_edgar_submissions("0000320193", cache_dir=tmp_path, client=client)


def test_ingest_edgar_submissions_raises_missing_sic_error_when_empty(tmp_path: Path) -> None:
    payload = {**_VALID_SUBMISSION, "sic": ""}
    handler = _static_json_handler(payload)

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.MissingSicError):
        ingest_edgar.ingest_edgar_submissions("0000320193", cache_dir=tmp_path, client=client)


def test_ingest_edgar_submissions_writes_cache_even_when_sic_missing(tmp_path: Path) -> None:
    payload = {k: v for k, v in _VALID_SUBMISSION.items() if k != "sic"}
    handler = _static_json_handler(payload)

    with _client_with_handler(handler) as client, pytest.raises(ingest_edgar.MissingSicError):
        ingest_edgar.ingest_edgar_submissions("0000320193", cache_dir=tmp_path, client=client)

    assert (tmp_path / "edgar" / "submissions" / "0000320193.json").is_file()


# ── MissingCompanyFactsError (G-E3) ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("payload", [{}, {"facts": {}}])
def test_ingest_edgar_companyfacts_raises_on_empty_facts(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    handler = _static_json_handler(payload)

    with (
        _client_with_handler(handler) as client,
        pytest.raises(ingest_edgar.MissingCompanyFactsError),
    ):
        ingest_edgar.ingest_edgar_companyfacts("0000320193", cache_dir=tmp_path, client=client)


def test_ingest_edgar_companyfacts_writes_cache_before_raising(tmp_path: Path) -> None:
    handler = _static_json_handler({})

    with (
        _client_with_handler(handler) as client,
        pytest.raises(ingest_edgar.MissingCompanyFactsError),
    ):
        ingest_edgar.ingest_edgar_companyfacts("0000320193", cache_dir=tmp_path, client=client)

    assert (tmp_path / "edgar" / "companyfacts" / "0000320193.json").is_file()


def test_ingest_edgar_companyconcept_raises_on_missing_units(tmp_path: Path) -> None:
    payload = {"cik": 320193, "taxonomy": "us-gaap", "tag": "Assets"}
    handler = _static_json_handler(payload)

    with (
        _client_with_handler(handler) as client,
        pytest.raises(ingest_edgar.MissingCompanyFactsError),
    ):
        ingest_edgar.ingest_edgar_companyconcept(
            "0000320193", "us-gaap", "Assets", cache_dir=tmp_path, client=client
        )


# ── extra="forbid" wired into the ingest path (AC9, G-E6) ───────────────────────────────────────


def test_ingest_edgar_companyfacts_raises_validation_error_on_drifted_fact_row(
    tmp_path: Path,
) -> None:
    payload = {
        "cik": 320193,
        "facts": {
            "us-gaap": {"Assets": {"units": {"USD": [{**_VALID_FACT_ROW, "unexpectedNewKey": 1}]}}}
        },
    }
    handler = _static_json_handler(payload)

    with _client_with_handler(handler) as client, pytest.raises(ValidationError):
        ingest_edgar.ingest_edgar_companyfacts("0000320193", cache_dir=tmp_path, client=client)


def test_ingest_edgar_companyconcept_raises_validation_error_on_drifted_fact_row(
    tmp_path: Path,
) -> None:
    payload = {
        "cik": 320193,
        "taxonomy": "us-gaap",
        "tag": "Assets",
        "units": {"USD": [{**_VALID_FACT_ROW, "unexpectedNewKey": 1}]},
    }
    handler = _static_json_handler(payload)

    with _client_with_handler(handler) as client, pytest.raises(ValidationError):
        ingest_edgar.ingest_edgar_companyconcept(
            "0000320193", "us-gaap", "Assets", cache_dir=tmp_path, client=client
        )
