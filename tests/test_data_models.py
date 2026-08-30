"""Tests for mizan/data/models.py — raw row-shape schema validation.

Implements PHASE_2_SPEC.md §8 acceptance criteria 2 (model-readable JSON), 7 (adjusted/raw close
never conflate), 9 (`extra="forbid"` catches XBRL drift), 13 (every model inherits
`MizanBaseModel`).
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from mizan.core.base import MizanBaseModel
from mizan.data.models import (
    CompanyTickerEntry,
    EdgarFactRow,
    EdgarSubmissionRecord,
    TiingoCorporateActionEvent,
    TiingoEodBar,
)

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

_VALID_BAR: dict[str, object] = {
    "date": "2020-01-02",
    "open": 100.0,
    "high": 101.0,
    "low": 99.0,
    "close": 100.5,
    "volume": 1000,
    "adjOpen": 99.0,
    "adjHigh": 100.0,
    "adjLow": 98.0,
    "adjClose": 99.5,
    "adjVolume": 1000,
    "divCash": 0.0,
    "splitFactor": 1.0,
}


@pytest.mark.parametrize(
    "model",
    [
        CompanyTickerEntry,
        EdgarFactRow,
        EdgarSubmissionRecord,
        TiingoEodBar,
        TiingoCorporateActionEvent,
    ],
)
def test_every_data_model_inherits_mizan_base_model(model: type[MizanBaseModel]) -> None:
    """Every Phase 2 row-shape model must inherit `MizanBaseModel` (AC 13, guard G8)."""
    assert issubclass(model, MizanBaseModel)


def test_company_ticker_entry_parses_a_valid_row() -> None:
    entry = CompanyTickerEntry.model_validate(
        {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
    )

    assert entry.cik_str == 320193
    assert entry.ticker == "AAPL"


def test_edgar_fact_row_parses_a_valid_row() -> None:
    row = EdgarFactRow.model_validate(_VALID_FACT_ROW)

    assert row.start == date(2019, 9, 29)
    assert row.end == date(2020, 9, 26)
    assert row.filed == date(2020, 10, 30)
    assert row.frame is None


def test_edgar_fact_row_start_and_frame_are_optional() -> None:
    """`start` is absent on instantaneous concepts; `frame` is often absent (§3)."""
    minimal = dict(_VALID_FACT_ROW)
    del minimal["start"]

    row = EdgarFactRow.model_validate(minimal)

    assert row.start is None
    assert row.frame is None


def test_edgar_fact_row_rejects_an_unrecognized_key() -> None:
    """`extra="forbid"` catches malformed/undocumented XBRL tag drift (AC 9, guard G-E6)."""
    drifted = {**_VALID_FACT_ROW, "unexpectedNewKey": 1}

    with pytest.raises(ValidationError):
        EdgarFactRow.model_validate(drifted)


def test_edgar_fact_row_rejects_a_missing_required_key() -> None:
    incomplete = dict(_VALID_FACT_ROW)
    del incomplete["filed"]

    with pytest.raises(ValidationError):
        EdgarFactRow.model_validate(incomplete)


def test_edgar_submission_record_parses_a_valid_slice() -> None:
    record = EdgarSubmissionRecord.model_validate(_VALID_SUBMISSION)

    assert record.sic == "3571"
    assert record.tickers == ("AAPL",)
    assert record.exchanges == ("Nasdaq",)


def test_edgar_submission_record_rejects_an_unrecognized_key() -> None:
    drifted = {**_VALID_SUBMISSION, "someNewSecField": "x"}

    with pytest.raises(ValidationError):
        EdgarSubmissionRecord.model_validate(drifted)


def test_edgar_submission_record_allows_a_null_exchange() -> None:
    """`exchanges` entries may be `None` (e.g. an OTC-only issuer)."""
    with_null = {**_VALID_SUBMISSION, "exchanges": [None]}

    record = EdgarSubmissionRecord.model_validate(with_null)

    assert record.exchanges == (None,)


def test_tiingo_eod_bar_declares_close_and_adj_close_independently() -> None:
    """`close` and `adjClose` are two distinct required fields — the schema-level guard against
    adjusted/raw-close conflation (AC 7, guard G-T3)."""
    bar = TiingoEodBar.model_validate(_VALID_BAR)

    assert bar.close == 100.5
    assert bar.adjClose == 99.5
    assert bar.close != bar.adjClose


def test_tiingo_eod_bar_requires_close_and_adj_close_separately() -> None:
    missing_adj_close = {k: v for k, v in _VALID_BAR.items() if k != "adjClose"}

    with pytest.raises(ValidationError):
        TiingoEodBar.model_validate(missing_adj_close)

    missing_close = {k: v for k, v in _VALID_BAR.items() if k != "close"}

    with pytest.raises(ValidationError):
        TiingoEodBar.model_validate(missing_close)


def test_tiingo_eod_bar_rejects_an_unrecognized_key() -> None:
    with pytest.raises(ValidationError):
        TiingoEodBar.model_validate({**_VALID_BAR, "newField": 1})


def test_tiingo_corporate_action_event_from_bar() -> None:
    bar = TiingoEodBar.model_validate({**_VALID_BAR, "divCash": 0.5, "splitFactor": 1.0})

    event = TiingoCorporateActionEvent.from_bar(bar)

    assert event.trade_date == date(2020, 1, 2)
    assert event.div_cash == 0.5
    assert event.split_factor == 1.0


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CompanyTickerEntry, {"cik_str": 1, "ticker": "X", "title": "X Corp"}),
        (EdgarFactRow, _VALID_FACT_ROW),
        (EdgarSubmissionRecord, _VALID_SUBMISSION),
        (TiingoEodBar, _VALID_BAR),
    ],
)
def test_models_are_frozen(model: type[MizanBaseModel], payload: dict[str, object]) -> None:
    """`frozen=True` (inherited from `MizanBaseModel`) must be real on every Phase 2 model."""
    instance = model.model_validate(payload)
    field_name = next(iter(model.model_fields))

    with pytest.raises(ValidationError):
        setattr(instance, field_name, getattr(instance, field_name))
