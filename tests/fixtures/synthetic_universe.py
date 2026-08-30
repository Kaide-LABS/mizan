"""tests/fixtures/synthetic_universe.py — ~12 SYNTHETIC fixture tickers for Phase 4 screening tests.

Implements PHASE_4_SPEC.md §6e, §8.

**EVERY TICKER NAME IN THIS FILE IS INVENTED FOR TESTING PURPOSES ONLY.** None of these is a real
issuer. None of the "facts" attached to any of them is researched, or claims any correspondence to a
real company's actual filings, business, or compliance status. This module — and no other file in
this repository — is, or may ever be, silently repurposed as, or mistaken for, the real ~100-ticker
curated Shari'ah-compliance universe and its hand-verified business-activity map that
`MASTER_PRD.md` §6.1 names and `PHASE_4_SPEC.md` §9 explicitly places out of scope for this phase.
Every CIK below uses the unmistakably-synthetic `999...` numeric prefix, distinct from any real
SEC-assigned CIK range.

Each ticker below corresponds 1:1 to a row of `PHASE_4_SPEC.md` §6e's table; the `description` field
on each restates, verbatim, what that row says the ticker proves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from mizan.data.raw_cache import cache_path, write_raw_json
from mizan.screening.business_activity import ActivityOverride, BusinessActivityTier

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

#: The fixed `as_of_date` every test in this suite screens against, unless a test deliberately
#: varies it (e.g. to exercise `ZZLOOKAHEAD01`'s temporal-non-interference property).
AS_OF_DATE = date(2026, 6, 30)

#: `filed`/`trade_date` values comfortably before `AS_OF_DATE`, used by every fixture fact that is
#: meant to be visible to `screen(..., as_of_date=AS_OF_DATE, ...)`.
_FILED_BEFORE = date(2026, 1, 15)
_TRADE_DATE = date(2026, 6, 1)
_PERIOD_START = date(2025, 1, 1)
_PERIOD_END = date(2025, 12, 31)

#: A `filed` value strictly AFTER `AS_OF_DATE` — `ZZLOOKAHEAD01`'s look-ahead fact uses this so a
#: correct `screen()` must never let it influence the result.
_FILED_AFTER = date(2026, 8, 1)

#: A SIC code with NO entry in `mizan.screening.business_activity.SIC_TIER_MAP` at all — "clean" for
#: every fixture ticker that is meant to pass the business-activity screen outright. A real,
#: SEC-assigned code (7372, PREPACKAGED SOFTWARE) so it is not itself a fabricated number, even
#: though which company it is attached to here is entirely synthetic.
_CLEAN_SIC = "7372"


@dataclass(frozen=True)
class FundamentalsFactFixture:
    """One pre-normalized `fundamentals_facts` row, in exactly the shape
    `mizan.data.db.ensure_schema` creates the table with — bypassing `normalize_edgar_facts`
    entirely, since these values ARE the already-normalized data `screen()` consumes, not raw
    companyfacts JSON that would need re-normalizing."""

    taxonomy: str
    tag: str
    unit: str
    period_start: date
    period_end: date
    is_instantaneous: bool
    value: float
    accn: str
    filed: date
    fy: int = 2025
    fp: str = "FY"
    form: str = "10-K"


@dataclass(frozen=True)
class PriceBarFixture:
    """One pre-normalized `price_bars` row (only the columns Phase 4 actually reads —
    `trade_date`/`raw_close` — vary meaningfully across fixtures; the rest are filled with
    plausible constants)."""

    trade_date: date
    raw_close: float


@dataclass(frozen=True)
class SyntheticTicker:
    """One synthetic, clearly-labeled fixture ticker (§6e). `description` restates, verbatim, what
    `PHASE_4_SPEC.md` §6e's table says this ticker proves."""

    ticker: str
    cik: str
    sic: str
    description: str
    facts: tuple[FundamentalsFactFixture, ...] = field(default_factory=tuple)
    price_bars: tuple[PriceBarFixture, ...] = field(default_factory=tuple)
    override: ActivityOverride | None = None


def _shares_fact(value: float = 1_000_000.0) -> FundamentalsFactFixture:
    """A `dei:EntityCommonStockSharesOutstanding` fact — the market-cap denominator's share count,
    filed comfortably before `AS_OF_DATE`."""
    return FundamentalsFactFixture(
        taxonomy="dei",
        tag="EntityCommonStockSharesOutstanding",
        unit="shares",
        period_start=_PERIOD_END,
        period_end=_PERIOD_END,
        is_instantaneous=True,
        value=value,
        accn="9990000000-26-000001",
        filed=_FILED_BEFORE,
    )


def _revenue_fact(value: float = 50_000_000.0) -> FundamentalsFactFixture:
    """A `us-gaap:Revenues` fact — ratio 3's required denominator."""
    return FundamentalsFactFixture(
        taxonomy="us-gaap",
        tag="Revenues",
        unit="USD",
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
        is_instantaneous=False,
        value=value,
        accn="9990000000-26-000002",
        filed=_FILED_BEFORE,
    )


def _balance_sheet_fact(
    tag: str, value: float, *, accn: str, filed: date = _FILED_BEFORE
) -> FundamentalsFactFixture:
    """An instantaneous `us-gaap` balance-sheet fact (a debt or investment tag)."""
    return FundamentalsFactFixture(
        taxonomy="us-gaap",
        tag=tag,
        unit="USD",
        period_start=_PERIOD_END,
        period_end=_PERIOD_END,
        is_instantaneous=True,
        value=value,
        accn=accn,
        filed=filed,
    )


def _income_statement_fact(tag: str, value: float, *, accn: str) -> FundamentalsFactFixture:
    """A duration `us-gaap` income-statement fact (a non-permissible-income tag)."""
    return FundamentalsFactFixture(
        taxonomy="us-gaap",
        tag=tag,
        unit="USD",
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
        is_instantaneous=False,
        value=value,
        accn=accn,
        filed=_FILED_BEFORE,
    )


def _clean_denominator_facts(revenue: float = 50_000_000.0) -> tuple[FundamentalsFactFixture, ...]:
    """Shares-outstanding + revenue — the two facts every Layer-2-reaching ticker needs regardless
    of its own debt/investment/income numerators."""
    return (_shares_fact(), _revenue_fact(revenue))


_CLEAN_PRICE_BARS: tuple[PriceBarFixture, ...] = (
    PriceBarFixture(trade_date=_TRADE_DATE, raw_close=100.0),
)
#: With `_shares_fact()` (1,000,000 shares) and this price (100.0/share), the resolved market-cap
#: denominator every Layer-2-reaching fixture ticker below is built against is exactly
#: 100,000,000.0.
DENOMINATOR = 100_000_000.0


# ── §6e's twelve synthetic tickers ──────────────────────────────────────────────────────────────

ZZPURE01 = SyntheticTicker(
    ticker="ZZPURE01",
    cik="9990000001",
    sic=_CLEAN_SIC,
    description="Layer 1 pass + all-zero ratios -> PURE.",
    facts=_clean_denominator_facts(),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZMIXED01 = SyntheticTicker(
    ticker="ZZMIXED01",
    cik="9990000002",
    sic=_CLEAN_SIC,
    description="Layer 1 pass + nonzero-but-compliant ratios -> MIXED.",
    facts=(
        *_clean_denominator_facts(),
        _balance_sheet_fact("LongTermDebtNoncurrent", 10_000_000.0, accn="9990000002-26-000003"),
        _balance_sheet_fact("ShortTermInvestments", 5_000_000.0, accn="9990000002-26-000004"),
        _income_statement_fact("InterestIncomeOther", 1_000_000.0, accn="9990000002-26-000005"),
    ),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZNONCOMP_ACT01 = SyntheticTicker(
    ticker="ZZNONCOMP_ACT01",
    cik="9990000003",
    sic="6022",  # Tier 0: STATE COMMERCIAL BANKS
    description=(
        "§8 AC2: fail-fast, zero ratio entries in trace. No fundamentals_facts/price_bars rows at "
        "all — Layer 1 alone must be sufficient to reach NON_COMPLIANT without ever querying "
        "Phase 3's tables."
    ),
)

ZZNONCOMP_RATIO01 = SyntheticTicker(
    ticker="ZZNONCOMP_RATIO01",
    cik="9990000004",
    sic=_CLEAN_SIC,
    description="Layer 2 debt-ratio failure (35% > 30% threshold) -> NON_COMPLIANT.",
    facts=(
        *_clean_denominator_facts(),
        _balance_sheet_fact("LongTermDebtNoncurrent", 35_000_000.0, accn="9990000004-26-000003"),
    ),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZNONCOMP_RATIO02 = SyntheticTicker(
    ticker="ZZNONCOMP_RATIO02",
    cik="9990000005",
    sic=_CLEAN_SIC,
    description=(
        "Layer 2 non-permissible-income-ratio failure (7% > 5% threshold) -> NON_COMPLIANT."
    ),
    facts=(
        *_clean_denominator_facts(),
        _income_statement_fact(
            "InvestmentIncomeInterest", 3_500_000.0, accn="9990000005-26-000003"
        ),
    ),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZTIER05_01 = SyntheticTicker(
    ticker="ZZTIER05_01",
    cik="9990000006",
    sic="3760",  # Tier 0.5: GUIDED MISSILES & SPACE VEHICLES & PARTS (weapons)
    description=(
        "register #6 default-ON -> NON_COMPLIANT at Layer 1 by default; toggling "
        "business_activity_tier_0_5_enabled OFF via model_copy changes this ticker's verdict "
        "(§8 AC3) — clean Layer-2 facts are attached so that when Layer 1 passes under the toggled "
        "config, Layer 2 has data to run against (all-zero -> PURE)."
    ),
    facts=_clean_denominator_facts(),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZTIER1_01 = SyntheticTicker(
    ticker="ZZTIER1_01",
    cik="9990000007",
    sic="7011",  # Tier 1: HOTELS & MOTELS
    description=(
        "register #7 default-OFF -> passes Layer 1 despite being on the contested list; clean "
        "Layer-2 facts -> PURE."
    ),
    facts=_clean_denominator_facts(),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZOVERRIDE_RESCUE01 = SyntheticTicker(
    ticker="ZZOVERRIDE_RESCUE01",
    cik="9990000008",
    sic="6022",  # Tier 0 SIC that the override below rescues
    description="Override RESCUES a SIC false positive — precedence, direction 1 -> PURE.",
    facts=_clean_denominator_facts(),
    price_bars=_CLEAN_PRICE_BARS,
    override=ActivityOverride(
        cik="9990000008",
        ticker="ZZOVERRIDE_RESCUE01",
        tier_override=None,
        rationale=(
            "SYNTHETIC FIXTURE rationale (not real research): invented as a diversified holding "
            "company whose SIC first-pass (bank) over-broadly flags it; the fixture's own facts "
            "stipulate no interest-bearing-deposit core business."
        ),
    ),
)

ZZOVERRIDE_FLAG01 = SyntheticTicker(
    ticker="ZZOVERRIDE_FLAG01",
    cik="9990000009",
    sic=_CLEAN_SIC,
    description="Override FLAGS a SIC false negative — precedence, direction 2 -> NON_COMPLIANT.",
    override=ActivityOverride(
        cik="9990000009",
        ticker="ZZOVERRIDE_FLAG01",
        tier_override=BusinessActivityTier.TIER_0,
        rationale=(
            "SYNTHETIC FIXTURE rationale (not real research): invented as a software-SIC-coded "
            "shell whose actual core business the fixture stipulates is interest-based lending, "
            "which the generic SIC first-pass alone would have missed."
        ),
    ),
)

ZZBOUNDARY01 = SyntheticTicker(
    ticker="ZZBOUNDARY01",
    cik="9990000010",
    sic=_CLEAN_SIC,
    description="Debt ratio EXACTLY 30.0% -> passes (§6c's <=, boundary-inclusive) -> MIXED.",
    facts=(
        *_clean_denominator_facts(),
        _balance_sheet_fact("LongTermDebtNoncurrent", 30_000_000.0, accn="9990000010-26-000003"),
    ),
    price_bars=_CLEAN_PRICE_BARS,
)

ZZLOOKAHEAD01 = SyntheticTicker(
    ticker="ZZLOOKAHEAD01",
    cik="9990000011",
    sic=_CLEAN_SIC,
    description=(
        "One fact with `filed` AFTER as_of_date (a $200,000,000 restated LongTermDebtNoncurrent "
        "value, accn ...-000099), an earlier fact with `filed` BEFORE it ($5,000,000, accn "
        "...-000003) -> verdict must be computed from the EARLIER fact only (§7/§8 temporal-"
        "non-interference)."
    ),
    facts=(
        *_clean_denominator_facts(),
        _balance_sheet_fact("LongTermDebtNoncurrent", 5_000_000.0, accn="9990000011-26-000003"),
    ),
    price_bars=_CLEAN_PRICE_BARS,
)

#: The look-ahead fact itself, deliberately NOT included in `ZZLOOKAHEAD01.facts` above — tests
#: insert it separately (via `load_into_duckdb(con, ZZLOOKAHEAD01,
#: extra_facts=(ZZLOOKAHEAD01_LOOKAHEAD_FACT,))`) so the same ticker can be screened both with and
#: without it present.
ZZLOOKAHEAD01_LOOKAHEAD_FACT = _balance_sheet_fact(
    "LongTermDebtNoncurrent", 200_000_000.0, accn="9990000011-26-000099", filed=_FILED_AFTER
)

ZZNODATA01 = SyntheticTicker(
    ticker="ZZNODATA01",
    cik="9990000012",
    sic=_CLEAN_SIC,
    description=(
        "No Assets/shares/price facts at all (only an unrelated Revenues fact, so the ticker IS "
        "normalized in general) -> screen() raises InsufficientDataError, never a guess."
    ),
    facts=(_revenue_fact(),),
)

ALL_SYNTHETIC_TICKERS: tuple[SyntheticTicker, ...] = (
    ZZPURE01,
    ZZMIXED01,
    ZZNONCOMP_ACT01,
    ZZNONCOMP_RATIO01,
    ZZNONCOMP_RATIO02,
    ZZTIER05_01,
    ZZTIER1_01,
    ZZOVERRIDE_RESCUE01,
    ZZOVERRIDE_FLAG01,
    ZZBOUNDARY01,
    ZZLOOKAHEAD01,
    ZZNODATA01,
)


# ── Materializing the universe into a cache dir / DuckDB connection ────────────────────────────


def write_company_tickers_cache(
    cache_dir: Path, tickers: Sequence[SyntheticTicker] = ALL_SYNTHETIC_TICKERS
) -> None:
    """Write a single `edgar/company_tickers/company_tickers.json` cache file covering every given
    fixture ticker, in the exact object-keyed-by-stringified-index shape SEC actually serves
    (`mizan.data.models.CompanyTickerEntry`'s own docstring)."""
    payload = {
        str(index): {
            "cik_str": int(ticker.cik),
            "ticker": ticker.ticker,
            "title": f"{ticker.ticker} SYNTHETIC TEST FIXTURE — not a real issuer",
        }
        for index, ticker in enumerate(tickers)
    }
    path = cache_path(cache_dir=cache_dir, source="edgar/company_tickers", key="company_tickers")
    write_raw_json(path, json.dumps(payload).encode("utf-8"))


def write_submissions_cache(cache_dir: Path, ticker: SyntheticTicker) -> None:
    """Write one `edgar/submissions/{cik}.json` cache file for `ticker`, carrying just enough shape
    for `resolve_sic_offline` to read `sic` back out."""
    payload = {
        "cik": int(ticker.cik),
        "sic": ticker.sic,
        "sicDescription": "SYNTHETIC TEST FIXTURE — not a real SIC description",
        "name": f"{ticker.ticker} SYNTHETIC TEST FIXTURE — not a real issuer",
    }
    path = cache_path(cache_dir=cache_dir, source="edgar/submissions", key=ticker.cik)
    write_raw_json(path, json.dumps(payload).encode("utf-8"))


def write_universe_cache(
    cache_dir: Path, tickers: Sequence[SyntheticTicker] = ALL_SYNTHETIC_TICKERS
) -> None:
    """Write both the shared `company_tickers.json` and one `submissions/{cik}.json` per ticker —
    everything `screen()`'s cache-only Layer-1 resolution (`resolve_cik_offline`,
    `resolve_sic_offline`) needs for every ticker in `tickers`."""
    write_company_tickers_cache(cache_dir, tickers)
    for ticker in tickers:
        write_submissions_cache(cache_dir, ticker)


def load_into_duckdb(
    con: duckdb.DuckDBPyConnection,
    ticker: SyntheticTicker,
    *,
    extra_facts: Sequence[FundamentalsFactFixture] = (),
) -> None:
    """Insert `ticker.facts` (+ any `extra_facts`, e.g. `ZZLOOKAHEAD01_LOOKAHEAD_FACT`) into
    `fundamentals_facts`, and `ticker.price_bars` into `price_bars` — directly, via plain
    parameterized `INSERT`s, bypassing `normalize_edgar_facts`/`normalize_tiingo_bars` entirely,
    since these fixture rows already ARE the pre-normalized shape `screen()` consumes.
    `con` must already have both tables (`mizan.data.db.connect(..., read_only=False)`).
    """
    for fact in (*ticker.facts, *extra_facts):
        con.execute(
            "INSERT INTO fundamentals_facts "
            "(cik, taxonomy, tag, unit, period_start, period_end, is_instantaneous, value, accn, "
            "fy, fp, form, filed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ticker.cik,
                fact.taxonomy,
                fact.tag,
                fact.unit,
                fact.period_start,
                fact.period_end,
                fact.is_instantaneous,
                fact.value,
                fact.accn,
                fact.fy,
                fact.fp,
                fact.form,
                fact.filed,
            ],
        )
    for bar in ticker.price_bars:
        con.execute(
            "INSERT INTO price_bars "
            "(ticker, trade_date, raw_open, raw_high, raw_low, raw_close, volume, adj_open, "
            "adj_high, adj_low, adj_close, adj_volume, div_cash, split_factor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ticker.ticker,
                bar.trade_date,
                bar.raw_close,
                bar.raw_close,
                bar.raw_close,
                bar.raw_close,
                1_000,
                bar.raw_close,
                bar.raw_close,
                bar.raw_close,
                bar.raw_close,
                1_000,
                0.0,
                1.0,
            ],
        )
