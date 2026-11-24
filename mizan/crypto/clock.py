"""Gap-free UTC crypto calendar; see ``docs/crypto/PHASE_2_SPEC.md`` §B3.

Equity dates arise implicitly from available ``price_bars`` rows. Crypto deliberately treats
every UTC calendar day as a market day, independent of stored rows or holidays.
"""

from datetime import date, timedelta


def generate_market_days(start_date: date, end_date: date) -> tuple[date, ...]:
    """Return every inclusive calendar date, including weekends and holidays."""
    if end_date < start_date:
        return ()
    return tuple(
        start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)
    )
