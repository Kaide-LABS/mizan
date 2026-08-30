"""Tests for mizan/screening/verdict.py — the screen() entry point.

Implements PHASE_4_SPEC.md §8 acceptance criteria 1 (every §6e fixture ticker matches its expected
Verdict), 2 (fail-fast is structural), 3 (config-drift changes the verdict, proven not asserted), 4
(temporal non-interference), 5 (override precedence), 6 (missing denominator halts), 7 (missing
numerator is 0.0, not an error), 8 (boundary semantics), 9 (no LLM import), 10 (screen() never
writes to DuckDB), 12 (boot gate — covered in test_cli_screen.py), 21 (boundary greps), plus guards
G-S1, G-S2, G-DB3.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from mizan.config.fiqh_params import (
    FIQH_PARAMS,
    FiqhParams,
    RatioDenominatorBasis,
    RatioDenominatorSmoothing,
)
from mizan.core.caveats import Caveat
from mizan.core.verdict import Verdict
from mizan.data import db
from mizan.screening.business_activity import BusinessActivityOverrideMap
from mizan.screening.verdict import (
    InsufficientDataError,
    NotNormalizedError,
    ScreeningVerdict,
    ScreenName,
    screen,
)
from tests.fixtures import synthetic_universe as fx


@pytest.fixture
def universe(tmp_path: Path) -> Iterator[tuple[Path, duckdb.DuckDBPyConnection]]:
    """Writes the full synthetic-universe cache and loads every fixture ticker's facts/price bars
    into one fresh DuckDB file. Tickers with no facts (e.g. `ZZNONCOMP_ACT01`, `ZZOVERRIDE_FLAG01`)
    naturally have zero rows for their CIK — no special-casing needed."""
    fx.write_universe_cache(tmp_path)
    con = db.connect(tmp_path / "test.duckdb")
    for ticker in fx.ALL_SYNTHETIC_TICKERS:
        fx.load_into_duckdb(con, ticker)
    try:
        yield tmp_path, con
    finally:
        con.close()


def _with_bool_param(name: str, value: bool) -> FiqhParams:
    """Return a `model_copy` of `FIQH_PARAMS` with the named boolean `FiqhParam` field's `.value`
    replaced — the only way to change a frozen `FiqhParams`/`FiqhParam`."""
    current = getattr(FIQH_PARAMS, name)
    return FIQH_PARAMS.model_copy(update={name: current.model_copy(update={"value": value})})


def _with_param(name: str, value: object) -> FiqhParams:
    """Same as `_with_bool_param`, generalized to any `FiqhParam` value type (used here for the two
    enum-valued denominator-axis fields)."""
    current = getattr(FIQH_PARAMS, name)
    return FIQH_PARAMS.model_copy(update={name: current.model_copy(update={"value": value})})


def _screen(
    cache_dir: Path,
    con: duckdb.DuckDBPyConnection,
    ticker: fx.SyntheticTicker,
    *,
    overrides: BusinessActivityOverrideMap | None = None,
    fiqh_params: FiqhParams = FIQH_PARAMS,
) -> ScreeningVerdict:
    envelope = screen(
        ticker.ticker,
        fx.AS_OF_DATE,
        con=con,
        cache_dir=cache_dir,
        overrides=overrides,
        fiqh_params=fiqh_params,
    )
    expected_caveats = (Caveat.LOOK_AHEAD_BIAS, Caveat.PENDING_SCHOLARLY_VERIFICATION)
    assert envelope.active_caveats == expected_caveats
    return ScreeningVerdict.model_validate(envelope.payload)


# ── §8 AC1: every §6e fixture ticker matches its expected Verdict ──────────────────────────────


def test_zzpure01_is_pure(universe: tuple[Path, duckdb.DuckDBPyConnection]) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZPURE01)
    assert result.verdict is Verdict.PURE
    assert len(result.reason_trace) == 4
    assert [entry.screen for entry in result.reason_trace] == [
        ScreenName.BUSINESS_ACTIVITY,
        ScreenName.DEBT_RATIO,
        ScreenName.INTEREST_INVESTMENTS_RATIO,
        ScreenName.NON_PERMISSIBLE_INCOME_RATIO,
    ]
    assert all(entry.passed for entry in result.reason_trace)


def test_zzmixed01_is_mixed(universe: tuple[Path, duckdb.DuckDBPyConnection]) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZMIXED01)
    assert result.verdict is Verdict.MIXED
    assert all(entry.passed for entry in result.reason_trace)


def test_zznoncomp_act01_is_non_compliant_with_single_entry_trace(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    """§8 AC2: fail-fast is structural. This ticker has ZERO fundamentals_facts/price_bars rows —
    `screen()` must still succeed (reach NON_COMPLIANT) WITHOUT raising `NotNormalizedError`,
    proving Layer 2 is never even attempted."""
    cache_dir, con = universe
    facts_count = con.execute(
        "SELECT count(*) FROM fundamentals_facts WHERE cik = ?", [fx.ZZNONCOMP_ACT01.cik]
    ).fetchone()
    assert facts_count is not None
    assert facts_count[0] == 0

    result = _screen(cache_dir, con, fx.ZZNONCOMP_ACT01)

    assert result.verdict is Verdict.NON_COMPLIANT
    assert len(result.reason_trace) == 1
    assert result.reason_trace[0].screen is ScreenName.BUSINESS_ACTIVITY
    assert not any(
        entry.screen
        in (
            ScreenName.DEBT_RATIO,
            ScreenName.INTEREST_INVESTMENTS_RATIO,
            ScreenName.NON_PERMISSIBLE_INCOME_RATIO,
        )
        for entry in result.reason_trace
    )


def test_zznoncomp_ratio01_is_non_compliant_on_debt_ratio(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZNONCOMP_RATIO01)
    assert result.verdict is Verdict.NON_COMPLIANT
    debt_entry = next(e for e in result.reason_trace if e.screen is ScreenName.DEBT_RATIO)
    assert debt_entry.passed is False
    assert debt_entry.actual_value == pytest.approx(0.35)


def test_zznoncomp_ratio02_is_non_compliant_on_income_ratio(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZNONCOMP_RATIO02)
    assert result.verdict is Verdict.NON_COMPLIANT
    income_entry = next(
        e for e in result.reason_trace if e.screen is ScreenName.NON_PERMISSIBLE_INCOME_RATIO
    )
    assert income_entry.passed is False
    assert income_entry.actual_value == pytest.approx(0.07)


def test_zztier05_01_is_non_compliant_by_default(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZTIER05_01)
    assert result.verdict is Verdict.NON_COMPLIANT
    assert len(result.reason_trace) == 1


def test_zztier1_01_is_pure_by_default(universe: tuple[Path, duckdb.DuckDBPyConnection]) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZTIER1_01)
    assert result.verdict is Verdict.PURE


def test_zzoverride_rescue01_is_pure(universe: tuple[Path, duckdb.DuckDBPyConnection]) -> None:
    assert fx.ZZOVERRIDE_RESCUE01.override is not None
    cache_dir, con = universe
    overrides = BusinessActivityOverrideMap(
        overrides={fx.ZZOVERRIDE_RESCUE01.cik: fx.ZZOVERRIDE_RESCUE01.override}
    )
    result = _screen(cache_dir, con, fx.ZZOVERRIDE_RESCUE01, overrides=overrides)
    assert result.verdict is Verdict.PURE


def test_zzoverride_flag01_is_non_compliant(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    assert fx.ZZOVERRIDE_FLAG01.override is not None
    cache_dir, con = universe
    overrides = BusinessActivityOverrideMap(
        overrides={fx.ZZOVERRIDE_FLAG01.cik: fx.ZZOVERRIDE_FLAG01.override}
    )
    result = _screen(cache_dir, con, fx.ZZOVERRIDE_FLAG01, overrides=overrides)
    assert result.verdict is Verdict.NON_COMPLIANT
    assert len(result.reason_trace) == 1


def test_zzoverride_without_the_override_map_behaves_as_plain_sic_first_pass(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    """Screening `ZZOVERRIDE_RESCUE01` (Tier 0 SIC) WITHOUT supplying its override must fall back to
    the plain SIC first-pass and fail — proving the rescue in the test above really came from the
    override, not from some other property of the fixture."""
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZOVERRIDE_RESCUE01, overrides=None)
    assert result.verdict is Verdict.NON_COMPLIANT


def test_zzboundary01_debt_ratio_exactly_at_threshold_passes(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    cache_dir, con = universe
    result = _screen(cache_dir, con, fx.ZZBOUNDARY01)
    debt_entry = next(e for e in result.reason_trace if e.screen is ScreenName.DEBT_RATIO)
    assert debt_entry.passed is True
    assert debt_entry.actual_value == pytest.approx(0.30)
    assert debt_entry.margin == pytest.approx(0.0)
    assert result.verdict is Verdict.MIXED  # actual_value != 0.0, so not PURE


def test_zznodata01_raises_insufficient_data_error(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    cache_dir, con = universe
    with pytest.raises(InsufficientDataError):
        screen(fx.ZZNODATA01.ticker, fx.AS_OF_DATE, con=con, cache_dir=cache_dir)


# ── §8 AC3 / G-S4 / G-S5: config values are read, not hardcoded ────────────────────────────────


def test_ac3_tier_0_5_toggle_changes_zztier05_01s_verdict(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    cache_dir, con = universe
    default_result = _screen(cache_dir, con, fx.ZZTIER05_01)
    assert default_result.verdict is Verdict.NON_COMPLIANT

    disabled_params = _with_bool_param("business_activity_tier_0_5_enabled", False)
    toggled_result = _screen(cache_dir, con, fx.ZZTIER05_01, fiqh_params=disabled_params)
    # The two `is` assertions (NON_COMPLIANT above, PURE here) already prove the verdict changed.
    assert toggled_result.verdict is Verdict.PURE


def test_ac3_debt_ratio_threshold_change_flips_zzboundary01s_verdict(
    universe: tuple[Path, duckdb.DuckDBPyConnection],
) -> None:
    """`ZZBOUNDARY01` passes at the default 30% threshold; lowering the threshold below its 30%
    actual debt ratio must flip it to NON_COMPLIANT — proving the threshold is read fresh from
    `fiqh_params`, never hardcoded."""
    cache_dir, con = universe
    default_result = _screen(cache_dir, con, fx.ZZBOUNDARY01)
    assert default_result.verdict is not Verdict.NON_COMPLIANT

    lowered_params = FIQH_PARAMS.model_copy(
        update={
            "debt_ratio_threshold": FIQH_PARAMS.debt_ratio_threshold.model_copy(
                update={"value": 0.10}
            )
        }
    )
    lowered_result = _screen(cache_dir, con, fx.ZZBOUNDARY01, fiqh_params=lowered_params)
    assert lowered_result.verdict is Verdict.NON_COMPLIANT


# ── §6b: all four denominator-axis combinations (basis x smoothing) ────────────────────────────
#
# The §6e synthetic universe above deliberately exercises only the DEFAULT axis (MARKET_CAP/SPOT) —
# that is what "clean, default-config fixtures" means. The other three combinations, plus the two
# denominator-specific InsufficientDataError branches and NotNormalizedError itself, are exercised
# here against small, purpose-built ad-hoc tickers (never part of ALL_SYNTHETIC_TICKERS, and never
# presented as anything but what they are: bare config-path fixtures).


def _ad_hoc_ticker(
    ticker: str,
    cik: str,
    *,
    facts: tuple[fx.FundamentalsFactFixture, ...] = (),
    price_bars: tuple[fx.PriceBarFixture, ...] = (),
) -> fx.SyntheticTicker:
    return fx.SyntheticTicker(
        ticker=ticker,
        cik=cik,
        sic="7372",
        description="ad-hoc denominator-axis config-path fixture, not one of §6e's twelve",
        facts=facts,
        price_bars=price_bars,
    )


def test_total_assets_basis_spot_smoothing(tmp_path: Path) -> None:
    ticker = _ad_hoc_ticker(
        "ZZASSETS_SPOT",
        "9990000101",
        facts=(
            fx._balance_sheet_fact("Assets", 200_000_000.0, accn="9990000101-26-000001"),
            fx._revenue_fact(),
        ),
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    params = _with_param("ratio_denominator_basis", RatioDenominatorBasis.TOTAL_ASSETS)
    result = _screen(tmp_path, con, ticker, fiqh_params=params)

    debt_entry = next(e for e in result.reason_trace if e.screen is ScreenName.DEBT_RATIO)
    assert debt_entry.actual_value == pytest.approx(0.0)  # 0 debt / 200,000,000 assets
    con.close()


def test_total_assets_basis_averaged_smoothing(tmp_path: Path) -> None:
    """Two `Assets` facts at different `period_end`s, both within the trailing 12 months of
    `AS_OF_DATE` -> AVERAGED takes their mean (100,000,000 average of 50,000,000 and
    150,000,000)."""
    ticker = _ad_hoc_ticker(
        "ZZASSETS_AVG",
        "9990000102",
        facts=(
            fx.FundamentalsFactFixture(
                taxonomy="us-gaap",
                tag="Assets",
                unit="USD",
                period_start=date(2025, 6, 30),
                period_end=date(2025, 6, 30),
                is_instantaneous=True,
                value=50_000_000.0,
                accn="9990000102-26-000001",
                filed=fx._FILED_BEFORE,
            ),
            fx.FundamentalsFactFixture(
                taxonomy="us-gaap",
                tag="Assets",
                unit="USD",
                period_start=fx._PERIOD_END,
                period_end=fx._PERIOD_END,
                is_instantaneous=True,
                value=150_000_000.0,
                accn="9990000102-26-000002",
                filed=fx._FILED_BEFORE,
            ),
            fx._revenue_fact(),
        ),
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    params = FIQH_PARAMS.model_copy(
        update={
            "ratio_denominator_basis": FIQH_PARAMS.ratio_denominator_basis.model_copy(
                update={"value": RatioDenominatorBasis.TOTAL_ASSETS}
            ),
            "ratio_denominator_smoothing": FIQH_PARAMS.ratio_denominator_smoothing.model_copy(
                update={"value": RatioDenominatorSmoothing.AVERAGED}
            ),
        }
    )
    result = _screen(tmp_path, con, ticker, fiqh_params=params)

    debt_entry = next(e for e in result.reason_trace if e.screen is ScreenName.DEBT_RATIO)
    assert debt_entry.actual_value == pytest.approx(0.0)  # 0 debt / 100,000,000 averaged assets
    con.close()


def test_market_cap_basis_averaged_smoothing(tmp_path: Path) -> None:
    """Two price bars within the trailing 12 months -> AVERAGED takes their mean price."""
    ticker = _ad_hoc_ticker(
        "ZZMKTCAP_AVG",
        "9990000103",
        facts=(fx._shares_fact(1_000_000.0), fx._revenue_fact()),
        price_bars=(
            fx.PriceBarFixture(trade_date=date(2026, 1, 1), raw_close=80.0),
            fx.PriceBarFixture(trade_date=fx._TRADE_DATE, raw_close=120.0),
        ),
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    params = _with_param("ratio_denominator_smoothing", RatioDenominatorSmoothing.AVERAGED)
    result = _screen(tmp_path, con, ticker, fiqh_params=params)

    # mean price = 100.0, shares = 1,000,000 -> denominator = 100,000,000, same as the default-axis
    # fixtures above, so a 0-debt ticker's debt ratio is exactly 0.0.
    debt_entry = next(e for e in result.reason_trace if e.screen is ScreenName.DEBT_RATIO)
    assert debt_entry.actual_value == pytest.approx(0.0)
    con.close()


def test_market_cap_spot_missing_price_bars_raises_insufficient_data_error(
    tmp_path: Path,
) -> None:
    """Shares outstanding present, but zero `price_bars` rows at all -> `InsufficientDataError` on
    the price-side of the market-cap denominator (distinct from `ZZNODATA01`, which is missing
    shares)."""
    ticker = _ad_hoc_ticker(
        "ZZNOPRICE",
        "9990000104",
        facts=(fx._shares_fact(), fx._revenue_fact()),
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    with pytest.raises(InsufficientDataError):
        screen(ticker.ticker, fx.AS_OF_DATE, con=con, cache_dir=tmp_path)
    con.close()


def test_layer_1_pass_with_zero_normalized_rows_raises_not_normalized_error(
    tmp_path: Path,
) -> None:
    """A clean-SIC ticker (passes Layer 1) with ZERO rows in both `fundamentals_facts` and
    `price_bars` -> `NotNormalizedError`, distinct from `InsufficientDataError` (§6e's own
    distinction: "never normalized at all" vs. "normalized, but missing one required figure")."""
    ticker = _ad_hoc_ticker("ZZNEVERNORMALIZED", "9990000105")
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")

    with pytest.raises(NotNormalizedError):
        screen(ticker.ticker, fx.AS_OF_DATE, con=con, cache_dir=tmp_path)
    con.close()


def test_total_assets_basis_no_facts_at_all_raises_insufficient_data_error(
    tmp_path: Path,
) -> None:
    """TOTAL_ASSETS basis with zero `us-gaap:Assets` rows at all (some other fact IS present, so
    `_ensure_normalized` passes) -> `InsufficientDataError`, not a `NotNormalizedError` and not a
    `ZeroDivisionError`."""
    ticker = _ad_hoc_ticker("ZZNOASSETS", "9990000106", facts=(fx._revenue_fact(),))
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    params = _with_param("ratio_denominator_basis", RatioDenominatorBasis.TOTAL_ASSETS)
    with pytest.raises(InsufficientDataError):
        screen(ticker.ticker, fx.AS_OF_DATE, con=con, cache_dir=tmp_path, fiqh_params=params)
    con.close()


def test_total_assets_averaged_with_only_a_stale_fact_raises_insufficient_data_error(
    tmp_path: Path,
) -> None:
    """TOTAL_ASSETS + AVERAGED: an `Assets` fact exists (so the `rows` query is non-empty) but its
    `period_end` falls OUTSIDE the trailing-12-month window -> the AVERAGED-specific
    `InsufficientDataError` (distinct from the "no rows at all" one above)."""
    stale_period_end = fx.AS_OF_DATE.replace(year=fx.AS_OF_DATE.year - 5)
    ticker = _ad_hoc_ticker(
        "ZZSTALEASSETS",
        "9990000107",
        facts=(
            fx.FundamentalsFactFixture(
                taxonomy="us-gaap",
                tag="Assets",
                unit="USD",
                period_start=stale_period_end,
                period_end=stale_period_end,
                is_instantaneous=True,
                value=100_000_000.0,
                accn="9990000107-26-000001",
                filed=fx._FILED_BEFORE,
            ),
            fx._revenue_fact(),
        ),
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    params = FIQH_PARAMS.model_copy(
        update={
            "ratio_denominator_basis": FIQH_PARAMS.ratio_denominator_basis.model_copy(
                update={"value": RatioDenominatorBasis.TOTAL_ASSETS}
            ),
            "ratio_denominator_smoothing": FIQH_PARAMS.ratio_denominator_smoothing.model_copy(
                update={"value": RatioDenominatorSmoothing.AVERAGED}
            ),
        }
    )
    with pytest.raises(InsufficientDataError):
        screen(ticker.ticker, fx.AS_OF_DATE, con=con, cache_dir=tmp_path, fiqh_params=params)
    con.close()


def test_market_cap_averaged_with_only_a_stale_price_bar_raises_insufficient_data_error(
    tmp_path: Path,
) -> None:
    """MARKET_CAP + AVERAGED: shares present, and a `price_bars` row exists, but it falls OUTSIDE
    the trailing-12-month window -> the AVERAGED-specific `InsufficientDataError` for the price
    side (distinct from `test_market_cap_spot_missing_price_bars_raises_insufficient_data_error`,
    which has zero price rows at all)."""
    stale_trade_date = fx.AS_OF_DATE.replace(year=fx.AS_OF_DATE.year - 5)
    ticker = _ad_hoc_ticker(
        "ZZSTALEPRICE",
        "9990000108",
        facts=(fx._shares_fact(), fx._revenue_fact()),
        price_bars=(fx.PriceBarFixture(trade_date=stale_trade_date, raw_close=100.0),),
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    params = _with_param("ratio_denominator_smoothing", RatioDenominatorSmoothing.AVERAGED)
    with pytest.raises(InsufficientDataError):
        screen(ticker.ticker, fx.AS_OF_DATE, con=con, cache_dir=tmp_path, fiqh_params=params)
    con.close()


def test_missing_total_revenue_raises_insufficient_data_error(tmp_path: Path) -> None:
    """A clean, otherwise-fully-resolvable ticker with NO `TOTAL_REVENUE_TAGS` fact at all ->
    `InsufficientDataError` — total revenue is a required denominator (ratio 3), never a legitimate
    `0.0` the way a numerator-side miss is (§4.2)."""
    ticker = _ad_hoc_ticker(
        "ZZNOREVENUE", "9990000109", facts=(fx._shares_fact(),), price_bars=fx._CLEAN_PRICE_BARS
    )
    fx.write_universe_cache(tmp_path, (ticker,))
    con = db.connect(tmp_path / "test.duckdb")
    fx.load_into_duckdb(con, ticker)

    with pytest.raises(InsufficientDataError):
        screen(ticker.ticker, fx.AS_OF_DATE, con=con, cache_dir=tmp_path)
    con.close()


# ── §8 AC4 / G-S2: temporal non-interference ────────────────────────────────────────────────────


def test_ac4_zzlookahead01_ignores_the_later_filed_fact(tmp_path: Path) -> None:
    """Builds two otherwise-identical DuckDB states differing only in whether a `filed`-after-
    `as_of_date` fact is present, and asserts identical `screen()` output for the same
    `as_of_date`."""
    fx.write_universe_cache(tmp_path, (fx.ZZLOOKAHEAD01,))

    without_lookahead_db = tmp_path / "without.duckdb"
    con_without = db.connect(without_lookahead_db)
    fx.load_into_duckdb(con_without, fx.ZZLOOKAHEAD01)
    result_without = ScreeningVerdict.model_validate(
        screen(fx.ZZLOOKAHEAD01.ticker, fx.AS_OF_DATE, con=con_without, cache_dir=tmp_path).payload
    )
    con_without.close()

    with_lookahead_db = tmp_path / "with.duckdb"
    con_with = db.connect(with_lookahead_db)
    fx.load_into_duckdb(con_with, fx.ZZLOOKAHEAD01, extra_facts=(fx.ZZLOOKAHEAD01_LOOKAHEAD_FACT,))
    result_with = ScreeningVerdict.model_validate(
        screen(fx.ZZLOOKAHEAD01.ticker, fx.AS_OF_DATE, con=con_with, cache_dir=tmp_path).payload
    )
    con_with.close()

    assert result_without == result_with
    debt_entry = next(e for e in result_with.reason_trace if e.screen is ScreenName.DEBT_RATIO)
    # Only the EARLIER ($5,000,000) fact may have influenced this — never the later ($200,000,000)
    # look-ahead fact, which would have produced an actual_value far above 1.0.
    assert debt_entry.actual_value == pytest.approx(5_000_000.0 / fx.DENOMINATOR)


def test_ac4_the_lookahead_fact_alone_would_have_produced_a_wildly_different_ratio() -> None:
    """Sanity check on the fixture itself: confirms the look-ahead fact's value really would flip
    the result if it were wrongly included, so the test above is a meaningful assertion and not a
    vacuously-passing one."""
    wrongly_included_total = 5_000_000.0 + fx.ZZLOOKAHEAD01_LOOKAHEAD_FACT.value
    assert wrongly_included_total / fx.DENOMINATOR > FIQH_PARAMS.debt_ratio_threshold.value


# ── §7 G-S2 / §8 AC21: boundary greps, re-run as tests ──────────────────────────────────────────


def test_filed_is_referenced_only_inside_verdict_module() -> None:
    """G-S2's grep, re-run as a test. Checked as the actual code-relevant patterns (a `filed`
    dict/column/attribute access or SQL predicate), not a bare substring match on `"filed"` — both
    sibling modules' own docstrings use the English word "filed" in prose (e.g. "a real gambling
    issuer filed under..."), which is not itself a temporal-filtering code path."""
    import mizan.screening.business_activity as business_activity_module
    import mizan.screening.financial_ratios as financial_ratios_module

    code_relevant_patterns = ('"filed"', "'filed'", ".filed", "filed <=", "filed<=")
    for module in (business_activity_module, financial_ratios_module):
        source = inspect.getsource(module)
        for pattern in code_relevant_patterns:
            assert pattern not in source, f"{module.__name__} contains {pattern!r}"


def test_no_llm_import_anywhere_in_screening_package() -> None:
    import mizan.screening.business_activity as business_activity_module
    import mizan.screening.financial_ratios as financial_ratios_module
    import mizan.screening.verdict as verdict_module

    for module in (business_activity_module, financial_ratios_module, verdict_module):
        source = inspect.getsource(module).lower()
        for forbidden in (
            "openai",
            "anthropic",
            "gemini",
            "vertex",
            "langchain",
            "chat_completion",
        ):
            message = f"{module.__name__} references forbidden term {forbidden!r}"
            assert forbidden not in source, message


def test_no_write_statement_anywhere_in_screening_package() -> None:
    """G-DB3: no INSERT/CREATE/ALTER anywhere under mizan/screening/."""
    import mizan.screening.business_activity as business_activity_module
    import mizan.screening.financial_ratios as financial_ratios_module
    import mizan.screening.verdict as verdict_module

    for module in (business_activity_module, financial_ratios_module, verdict_module):
        source = inspect.getsource(module).upper()
        for forbidden in ("INSERT INTO", "CREATE TABLE", "ALTER TABLE"):
            assert forbidden not in source, f"{module.__name__} contains {forbidden!r}"


def test_screen_has_no_random_or_time_based_nondeterminism() -> None:
    """No `random`/`datetime.now`/`time.time` call anywhere in the screening package — `screen()`
    must be a pure, reproducible function of its inputs."""
    import mizan.screening.business_activity as business_activity_module
    import mizan.screening.financial_ratios as financial_ratios_module
    import mizan.screening.verdict as verdict_module

    for module in (business_activity_module, financial_ratios_module, verdict_module):
        source = inspect.getsource(module)
        assert "random" not in source.lower()
        assert "datetime.now" not in source
        assert "date.today" not in source
