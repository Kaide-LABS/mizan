"""mizan/data/models.py — raw row-shape schemas for Phase 2 ingestion.

Implements PHASE_2_SPEC.md §3.

Field-shape sources: docs/modernization_log.md §6.1 (EDGAR, verified live 2026-08-30 against CIK
0000320193) and §6.2 (Tiingo, verified against public docs 2026-08-30).

These are raw row-shape schemas, not normalized typed tables. They validate the *shape* of data as
it arrives from EDGAR/Tiingo — rejecting upstream drift loudly instead of caching garbage silently
— and they are what gets written to and read back from the replayable cache
(mizan/data/raw_cache.py). Mapping raw wire fields to Phase 3's normalized, unit-scaled,
snake_case DuckDB columns is explicitly not this phase's job
(ULTIMATE_PRD.md §6, data/normalize.py).

Wire-format field names are kept verbatim (camelCase where SEC/Tiingo use camelCase), not renamed
to snake_case at this layer. A renamed field here would be exactly the kind of silent reshaping
that breaks "prove what the data said" (MASTER_PRD.md §5.3). This means ruff's N815 (mixed-case
attribute in class scope) and, for one Tiingo field, A003 (class attribute shadows a builtin:
``open``) fire on these models by design; suppressed with a targeted ``# noqa`` on each affected
line, never by relaxing the ruleset project-wide.
"""

from __future__ import annotations

from datetime import date as _Date  # noqa: N812 -- underscore-prefixed alias, not a rename

from mizan.core.base import MizanBaseModel


class CompanyTickerEntry(MizanBaseModel):
    """One row of https://www.sec.gov/files/company_tickers.json.

    The wire format is a JSON OBJECT keyed by stringified index (`{"0": {...}, "1": {...}, ...}`),
    NOT an array — `ingest_edgar.py` iterates `.values()` when parsing; this model describes one
    value, not the envelope. `cik_str` is an int despite the name (verified: 10,391 entries, all
    int) — this model does not zero-pad it; that happens at the call site (§6.3 of
    PHASE_2_SPEC.md), not in the schema, so the raw cache stores exactly what SEC sent, unmodified.
    """

    cik_str: int
    ticker: str
    title: str


class EdgarFactRow(MizanBaseModel):
    """One fact object from an XBRL `companyfacts` or `companyconcept` response.

    Field set verified live 2026-08-30: `{start?, end, val, accn, fy, fp, form, filed, frame?}`.
    `start` is present on duration concepts (e.g. revenue-over-a-period), absent on instantaneous
    ones (e.g. total-assets-at-a-point). `frame` is optional and often absent.

    `extra="forbid"` (inherited) is the concrete mechanism behind guard G-E6 (PHASE_2_SPEC.md §7):
    if SEC adds, removes, or renames a fact-object key, parsing raises `pydantic.ValidationError`
    instead of the key being silently dropped or `None`-filled.

    `filed` is the point-in-time key Phase 4's temporal-non-interference confinement check
    (`ULTIMATE_PRD.md` §3.3, §4.4) depends on existing, byte-for-byte, on every cached fact —
    Phase 2 must never drop or reformat it beyond ISO-date parsing.
    """

    start: _Date | None = None
    end: _Date
    val: float
    accn: str
    fy: int
    fp: str
    form: str
    filed: _Date
    frame: str | None = None


class EdgarSubmissionRecord(MizanBaseModel):
    """The subset of https://data.sec.gov/submissions/CIK##########.json Phase 2 reads.

    Deliberately NOT a full mirror of the submissions payload, which carries dozens of fields Mizan
    never uses (addresses, former names, filing history, ...). Modeling only the fields Phase 2
    consumes keeps `extra="forbid"` meaningful here rather than forcing every unrelated SEC field to
    be declared. The on-disk raw cache file still stores SEC's full JSON response verbatim
    (PHASE_2_SPEC.md §6.2) — this model validates the slice `ingest_edgar.py` actually reads out of
    it (principally `sic`, for the business-activity first-pass signal Phase 4 will use), not the
    cache file's contents.
    """

    cik: int
    entityType: str  # noqa: N815 — wire-format verbatim, see module docstring
    sic: str
    sicDescription: str  # noqa: N815
    name: str
    tickers: tuple[str, ...]
    exchanges: tuple[str | None, ...]


class TiingoEodBar(MizanBaseModel):
    """One daily bar from Tiingo's EOD endpoint.

    Field set verified 2026-08-30: `{date, open, high, low, close, volume, adjOpen, adjHigh,
    adjLow, adjClose, adjVolume, divCash, splitFactor}`.

    `close` and `adjClose` are two DISTINCT required fields, never collapsed into one ambiguous
    `close` — this is the schema-level guard against the adjusted/raw-close conflation failure mode
    (`ULTIMATE_PRD.md` §4.2, guard G-T3, PHASE_2_SPEC.md §7). Phase 3's normalizer maps these to
    `raw_close`/`adj_close` typed DuckDB columns; Phase 2's job is only to guarantee both survive,
    distinctly, from the moment of ingest — no code path in this phase may read one and call it
    "the close."
    """

    date: _Date
    open: float  # wire-format verbatim, shadows the builtin `open()` by design
    high: float
    low: float
    close: float
    volume: int
    adjOpen: float  # noqa: N815
    adjHigh: float  # noqa: N815
    adjLow: float  # noqa: N815
    adjClose: float  # noqa: N815
    adjVolume: int  # noqa: N815
    divCash: float  # noqa: N815
    splitFactor: float  # noqa: N815


class TiingoCorporateActionEvent(MizanBaseModel):
    """A DERIVED view of one `TiingoEodBar`'s corporate-action fields, used only by the anomaly
    flagging check (PHASE_2_SPEC.md §6.4; `ULTIMATE_PRD.md` §4.2, "missing divCash on a known
    ex-dividend date").

    Not independently fetched and not written to the raw cache on its own — the raw cache stores
    `TiingoEodBar` rows (the full response, PHASE_2_SPEC.md §6.2). This model exists so the anomaly
    detector has a small, explicit, unit-testable shape to operate over instead of reaching into
    `TiingoEodBar`'s full field set ad hoc. Constructed only via `from_bar`.
    """

    trade_date: _Date
    div_cash: float
    split_factor: float

    @classmethod
    def from_bar(cls, bar: TiingoEodBar) -> TiingoCorporateActionEvent:
        """Build a `TiingoCorporateActionEvent` view from one parsed `TiingoEodBar`."""
        return cls(trade_date=bar.date, div_cash=bar.divCash, split_factor=bar.splitFactor)
