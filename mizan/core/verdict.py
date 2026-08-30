"""Three-state screening verdict.

Implements PHASE_1_SPEC.md §3.4.
"""

from enum import StrEnum


class Verdict(StrEnum):
    """Three-state screening verdict. Never boolean.

    Defined in Phase 1 so every later module (screening in Phase 4, backtest in Phase 5) imports
    one canonical enum instead of each phase inventing its own.

    The three states and their definitions are a direct transcription of the AAOIFI public
    methodology (Merah, Oct 2017, slide 21), quoted in ULTIMATE_PRD.md §3.1(c):

    * PURE          - "Shari'ah compliant core business and no interest based deposits or loans"
    * MIXED         - "Shari'ah compliant core business and financial ratios that do not exceed
                       the thresholds" -> purification applies
    * NON_COMPLIANT - "with Non-Halal activity as its core source of income and if debt and
                       investment ratios exceed the allowed thresholds" -> not investable; if
                       held, triggers the flip -> forced-divestment path

    Enum definition only. No scoring logic, no reason-trace structure, no ``screen()`` function —
    all Phase 4 (PHASE_1_SPEC.md §9).
    """

    PURE = "pure"
    MIXED = "mixed"
    NON_COMPLIANT = "non_compliant"
