# PHASE_1_SPEC.md — Mizan: Foundation & Config

> **Provenance: this file is Built FROM the modernised `ULTIMATE_PRD.md`** (Step 10 modernization
> pass, 2026-08-30), not from the pre-modernization version. Every dependency pin, every schema
> decision, and every guard below traces to a section of that document, cited inline. Where this
> spec and the pre-modernization Phase 1 spec differ, the differences are enumerated in
> §10 *Rebuild Delta* at the end of this file, each with its cause in the modernised PRD.

**Generated:** 2026-08-30 · **Supersedes:** the pre-modernization `PHASE_1_SPEC.md` (overwritten in
place) · **Canonical references:** `ULTIMATE_PRD.md` (governs), `MASTER_PRD.md` (governs where
ULTIMATE is silent), `.claude/loopr/baby_prd.md` (confirmed scope/AC/boundary),
`docs/modernization_log.md` (pinned external reality).

---

## §0 Phase Plan Header

# **Phase 1 of 7: Foundation & Config**

Full phase sequence, **re-derived this pass** (not inherited) in `ULTIMATE_PRD.md` §6 against the
sole criterion *"is this stage independently buildable and testable before the next starts, and does
nothing later reach back to change its public shape except by additive extension?"*:

| # | Phase | Ships |
|---|---|---|
| **1** | **Foundation & Config** ← *this document* | invariants, fiqh register, boot gate, shared base model, `Verdict`, `Caveat`/`ResultEnvelope`, `pyproject.toml` |
| 2 | Ingestion & raw cache | EDGAR (companyfacts + companyconcept + **submissions**) + Tiingo clients, two *distinct* rate limiters, replayable cache, `mizan/cli/` |
| 3 | Normalization & DuckDB store | raw → typed tables, uniqueness constraints, unit-scale handling |
| 4 | Screening engine | business-activity (tiered), financial ratios (30/30/5, two-axis denominator), verdict + reason trace, temporal-non-interference confinement check |
| 5 | Backtest engine + compliance-flip state machine | daily clock, portfolio, strategy interface, flip→grace→divest |
| 6 | Purification | side-ledger, `divCash`-driven, Forks A/B/C from config |
| 7 | Reporting | static HTML + matplotlib, caveats non-optional, gross vs net-of-purification |

The one alternative seriously considered was an 8th CLI/orchestration phase; rejected because each
phase ships its own entrypoint incrementally (Phase 1 registers `mizan-boot-check`; Phase 2 creates
`mizan/cli/` with `mizan ingest`; each later phase adds its verb), leaving an orchestration phase
with nothing to build. **7 is a decision, not a copy.** (`ULTIMATE_PRD.md` §6.)

This spec covers **Phase 1 only**. It is the contract the Phase 1 execution agent builds against and
the Phase 1 review agent verifies against. Every later phase imports from Phase 1's public surface
(`mizan.config.invariants`, `mizan.config.fiqh_params`, `mizan.core.base`, `mizan.core.verdict`,
`mizan.core.caveats`) — nothing in Phase 1 may be reshaped later except by **strict additive
extension** (new optional fields with defaults; never a renamed or removed symbol) without a new
phase spec revision.

---

## §1 Files Added or Modified

**Repository root is `C:\Users\hp\HMS`. Everything below is created at the repository root — there
is no nesting directory.** The pre-modernization spec nested the package under `mizan-sandbox/`;
that is **removed**, because `ULTIMATE_PRD.md` §5's grep-able boundary checks are written against
paths like `mizan/config/invariants.py` and `mizan/backtest/`, and a review agent running those
greps from the repo root must find the files. Path ambiguity here would silently defeat the entire
boundary-check apparatus.

The repo currently contains only documents and loopr state: `MASTER_PRD.md`, `ULTIMATE_PRD.md`,
`PHASE_1_SPEC.md`, `docs/modernization_log.md`, `.claude/`, `.loopr-state/`, `prompts/`. **There is
no application code yet.** Every file below except `docs/modernization_log.md` is new.

```
C:\Users\hp\HMS\
├── pyproject.toml                     # NEW — metadata, exact pins, ruff/mypy/pytest config, console script
├── .gitignore                         # NEW — Python + data-cache ignores
├── docs/
│   └── modernization_log.md           # EXISTS (created by the Step 10 pass) — Phase 1 MODIFIES it
│                                      #   only to fill in the actual build interpreter version (§2.4)
├── mizan/
│   ├── __init__.py                    # NEW — empty; marks package
│   ├── py.typed                       # NEW — empty marker file (PEP 561); required for mypy --strict
│   │                                  #   to treat this package as typed when imported by tests
│   ├── config/
│   │   ├── __init__.py                # NEW — empty
│   │   ├── invariants.py              # NEW — permissibility boundary; constants, NO knobs
│   │   ├── fiqh_params.py             # NEW — the 11-row judgment-call register (honesty surface)
│   │   └── boot_check.py              # NEW — fail-fast validators + `mizan-boot-check` entrypoint
│   └── core/
│       ├── __init__.py                # NEW — empty
│       ├── base.py                    # NEW — MizanBaseModel (extra="forbid", frozen, validate_default)
│       ├── verdict.py                 # NEW — Verdict three-state enum (definition only)
│       └── caveats.py                 # NEW — Caveat enum + ResultEnvelope contract
└── tests/
    ├── __init__.py                    # NEW — empty
    ├── test_invariants.py             # NEW — boot-check pass/fail cases
    ├── test_fiqh_params.py            # NEW — register completeness, 1:1 mapping, metadata honesty
    └── test_core_types.py             # NEW — MizanBaseModel, Verdict, Caveat, ResultEnvelope
```

**Files explicitly NOT created in Phase 1:** `mizan/data/`, `mizan/screening/`, `mizan/backtest/`,
`mizan/reporting/`, `mizan/cli/`. These are named in `MASTER_PRD.md` §9.4 and `ULTIMATE_PRD.md` §6
for Phases 2–7. See §9.

**`mizan/core/` justification (it is not in `MASTER_PRD.md` §9.4's module tree):** `Verdict` and the
caveat/result contract are cross-cutting types that Phases 4, 5, 6 and 7 all import. They must have
**one** canonical home decided now, not re-decided in Phase 4 and again in Phase 7. Placing
`Verdict` under `mizan/screening/` would force Phase 5's backtest to import from the screening
package for a type, coupling two phases that should share only data. `mizan/core/` is a Phase-1
addition of scope, and it is deliberate.

**Repository is not currently a git repository.** Phase 1 initialises it (`git init`) if the loop's
harness has not. Per `.claude/loopr/context.md` § Soft context note 2 and `MASTER_PRD.md` §9.5: **commits stay neutral
— no AI attribution** (`Co-Authored-By`, "Generated with", or similar), configured git user only.

---

## §2 Dependencies

All versions below are the **exact** pins verified on 2026-08-30 and recorded with source URLs in
`docs/modernization_log.md` §3–§4. They come from `ULTIMATE_PRD.md` §2.1. **No version here is
recalled from training data, and no floating range is permitted** — this is a
reproducibility-critical research tool; a range that silently changes a numerical result between
runs is a correctness failure, not a convenience (`ULTIMATE_PRD.md` §2.1).

### 2.1 `pyproject.toml` — required content

```toml
[project]
name = "mizan"
version = "0.1.0"
description = "Halal-constrained market simulation and research sandbox (single-user, deterministic, batch)."
requires-python = ">=3.11,<3.15"

dependencies = [
    "pydantic==2.13.5",
]

[project.optional-dependencies]
# Declared now so pyproject.toml is complete and stable across phases. NOT imported by any
# Phase 1 module. Installing them in Phase 1 is harmless; importing them in Phase 1 is a
# review-blocking finding (§7, §9).
ingest = [
    "httpx==0.28.1",
]
data = [
    "duckdb==1.5.5",
    "pyarrow==25.0.1",
    "pandas==3.0.5",
]
report = [
    "matplotlib==3.11.1",
]

[dependency-groups]
dev = [
    "mypy==2.3.1",
    "ruff==0.16.5",
    "pytest==9.1.1",
]

[project.scripts]
mizan-boot-check = "mizan.config.boot_check:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.mypy]
strict = true
python_version = "3.11"          # lowest supported interpreter — check against the floor, not the ceiling
files = ["mizan", "tests"]
warn_unused_configs = true

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "PT", "SIM", "TID", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 2.2 Version deltas from the pre-modernization spec

| Package | Pre-modernization pin | **Phase 1 pin** | Cause |
|---|---|---|---|
| `pydantic` | `2.13.4` | **`2.13.5`** | `ULTIMATE_PRD.md` §2.1 · changelog A |
| `duckdb` | `1.5.4` | **`1.5.5`** | same |
| `pyarrow` | `24.0.0` | **`25.0.1`** | same |
| `pandas` | `>=2.2,<3` | **`3.0.5`** | same — **major version bump, see 2.3** |
| `matplotlib` | `>=3.9,<4` | **`3.11.1`** | same — range → exact pin |
| `httpx` | `0.28.1` | **`0.28.1`** (unchanged) | still latest **stable**; `1.0.dev5` deliberately not pinned |
| `mypy` | `2.1.0` | **`2.3.1`** | same |
| `ruff` | `0.15.20` | **`0.16.5`** | same |
| `pytest` | `>=8.3,<9` | **`9.1.1`** | same — range → exact pin |
| Python | `>=3.11` | **`>=3.11,<3.15`** | ceiling added: no pinned dependency publishes `cp315` wheels |

### 2.3 Behavioural notes the Phase 1 agent must not "fix"

Phase 1 imports **only `pydantic`**, so none of these bite in Phase 1 — they are recorded here
because `pyproject.toml` is written in Phase 1 and a later agent reading it must not loosen a pin to
make a new upstream default go away (`ULTIMATE_PRD.md` §2.1, `docs/modernization_log.md` §5):

- **`mypy` 2.x**: `--local-partial-types` and `--strict-bytes` are now defaults; `--python-version
  3.9` is a hard error. `strict = true` remains the gate. **Do not relax `strict` — fix the code.**
- **`pandas` 3.0**: Copy-on-Write is the only behaviour and `SettingWithCopyWarning` is *removed*,
  so chained assignment now fails **silently**; default string dtype is `str`; `to_datetime` on
  strings infers `datetime64[us]`. Relevant from Phase 3 onward.
- **`pydantic` defaults this project overrides**: `extra` defaults to `'ignore'`, `frozen` to
  `False`, `validate_default` to `False` — all three are overridden on the shared base (§3.1).

### 2.4 Modernization-log reconciliation (a Phase 1 deliverable)

`docs/modernization_log.md` already exists (created by the Step 10 pass). Phase 1 must:

1. Replace the placeholder `3.14.__` in §2 of that file with the actual `python --version` output of
   the interpreter the project is built against, **in the same commit that adds `pyproject.toml`.**
2. Change nothing else in it. Every other line is a verified external fact with a source URL.
3. Ensure **every pin in `pyproject.toml` appears in `docs/modernization_log.md` §3–§4 with the
   identical version string.** A mismatch between the two files is a review-blocking finding (§7).

### 2.5 Permanently forbidden dependencies

**Never present in `pyproject.toml`, in any dependency group or extra, in this or any later phase:**
`openai`, `anthropic`, `google-genai`, `google-generativeai`, `google-cloud-aiplatform`, `vertexai`,
`langchain`, `litellm`, `transformers`, `ollama`, any other LLM/model-client SDK, and `yfinance`.

This is not a Phase 1 scope limit — it is the permanent boundary (`ULTIMATE_PRD.md` §5,
`baby_prd.md` scope edge #5, `MASTER_PRD.md` §2). Presence of any of them is a **HALT**, and it is
grep-able: `ULTIMATE_PRD.md` §5 check 6.

---

## §3 Pydantic Schemas

Every model in Phase 1 inherits one shared base. `ULTIMATE_PRD.md` §3.4 records the verified
Pydantic defaults this base overrides: `extra` defaults to `'ignore'` (silently swallows typos),
`frozen` to `False`, `validate_default` to `False`.

### 3.1 `mizan/core/base.py`

```python
from pydantic import BaseModel, ConfigDict


class MizanBaseModel(BaseModel):
    """Shared base for every Mizan Pydantic model.

    Three non-default settings, each load-bearing:

    * ``extra="forbid"`` — Pydantic's default is ``"ignore"``, which silently discards unknown
      keys. Forbidding is the mechanism that makes ``invariants.py`` and ``fiqh_params.py`` fail
      loudly on a typo or a drifted key rather than quietly ignoring it.
      (ULTIMATE_PRD.md §3.4; https://pydantic.dev/docs/validation/latest/api/pydantic/config/)
    * ``frozen=True`` — loaded config must not be mutated in place by any downstream module. A
      later phase needing a modified copy constructs one with ``model_copy(update=...)``; it must
      never flip ``frozen`` off on this shared base.
    * ``validate_default=True`` — in this project, defaults are where every fiqh value actually
      lives. An unvalidated default is an unchecked value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
```

**No other module in `mizan/` may subclass `pydantic.BaseModel` directly.** Every model inherits
`MizanBaseModel`. This is grep-checked (§7).

**`frozen=True` consequence to be aware of, not to be "fixed":** Pydantic generates `__hash__()` on
frozen models. `ResultEnvelope` (§3.4) carries a `dict` payload and is therefore **not actually
hashable at call time** — `hash(envelope)` raises `TypeError`. Nothing in Phase 1 hashes it, and
nothing in Phases 5–7 may put a `ResultEnvelope` in a `set` or use it as a dict key. This is
documented rather than worked around, because dropping `frozen` to make a hash work would trade a
never-needed capability for the ability to silently mutate a result object.

### 3.2 `mizan/config/invariants.py` — the permissibility boundary

```python
from mizan.core.base import MizanBaseModel


class Invariants(MizanBaseModel):
    """The permissibility boundary. Every field here is a fixed constant, never a runtime knob.

    There is no mechanism anywhere in this class, this module, or its callers to override these
    values via environment variable, CLI flag, config file, or constructor argument. A field
    becoming configurable is itself a hard-boundary violation (PHASE_1_SPEC.md §7).

    Source: MASTER_PRD.md §2 INVARIANTS; ULTIMATE_PRD.md §5; baby_prd.md §Boundary.
    """

    cash_yield: float = 0.0
    long_only: bool = True
    fully_funded: bool = True
    derivatives_allowed: bool = False
    margin_allowed: bool = False
    riba_modeling_allowed: bool = False
    llm_in_compliance_path_allowed: bool = False


INVARIANTS = Invariants()
```

- **`INVARIANTS` is the single module-level instance** every other module imports
  (`from mizan.config.invariants import INVARIANTS`). No module constructs its own `Invariants()`.
  There is exactly one instance, constructed once at import time, **with zero arguments**.
- **A call site passing any argument into `Invariants(...)` is a review-blocking finding**, because
  it implies the invariant became parameterisable at a call site. The one permitted exception is
  inside `tests/test_invariants.py`, which must construct violating instances in order to prove the
  boot gate rejects them (§8 criterion 2).
- **Seven fields, exactly.** Adding an eighth requires adding its check to `check_invariants()`
  (§6.1) in the same diff — the deliberately hand-written check style makes the omission visible.

### 3.3 `mizan/config/fiqh_params.py` — the honesty surface (11 rows)

This module is the reason the project exists (`MASTER_PRD.md` §0). Its correctness bar is higher
than the rest of Phase 1: **a source string that overstates what the primary source actually says is
the honesty surface lying**, and is categorised **HALT-for-human** in `ULTIMATE_PRD.md` §4.4.

#### 3.3.1 Supporting enums

```python
from enum import Enum


class VerificationStatus(str, Enum):
    """Verification state of a fiqh judgment call."""

    PENDING_SCHOLARLY_VERIFICATION = "pending_scholarly_verification"
    # No other member is defined in Phase 1. A future member (e.g. SCHOLAR_RATIFIED) may only be
    # added once an actual scholarly ruling exists — never speculatively.


class RatioDenominatorBasis(str, Enum):
    MARKET_CAP = "market_cap"        # AAOIFI-faithful default (INFERRED — see register #1 source)
    TOTAL_ASSETS = "total_assets"    # MSCI/FTSE-style alternative


class RatioDenominatorSmoothing(str, Enum):
    SPOT = "spot"                    # AAOIFI-faithful default (INFERRED — see register #2 source)
    AVERAGED = "averaged"            # index-provider style (DJ/S&P use a 12-month average)


class DivestmentAttributionMethod(str, Enum):
    """Fork C. Only the V1 default is defined.

    ULTIMATE_PRD.md §3.2 and the Step 10 literature sweep found NO settled formula and NO proposed
    alternative in the 2024-2026 literature. Defining a speculative second member here would
    manufacture a false menu of options. Adding a member requires a phase-spec revision.
    """

    TIME_BOUNDED_PRICE_APPRECIATION = "time_bounded_price_appreciation"


class PurificationAccountingMethod(str, Enum):
    """Fork B. Only the side-ledger is defined.

    ULTIMATE_PRD.md §3.2 quotes the primary source verbatim: non-halal income "will have to be
    donated to Charity and cannot be included in the investors P&L accounts." A netted-into-NAV
    member would be a member that violates the primary source, so it is not defined. The entry
    stays in the register (it is a fiqh judgment call, not a permissibility invariant) but there is
    nothing to configure it TO without a phase-spec revision.
    """

    SIDE_LEDGER = "side_ledger"
```

#### 3.3.2 `FiqhParam[T]` — a GENERIC model, not a union

```python
from typing import Generic, TypeVar

from pydantic import Field

from mizan.core.base import MizanBaseModel

T = TypeVar("T")


class FiqhParam(MizanBaseModel, Generic[T]):
    """One row of the judgment-call register (MASTER_PRD.md §10).

    Generic, deliberately. The pre-modernization spec typed ``value`` as ``bool | float | str``.
    Pydantic's default union mode is ``smart`` and its docs state the algorithm "may change between
    Pydantic minor releases"; the docs do not specify bool-vs-int resolution (``bool`` is an ``int``
    subclass). Putting an explicitly-unspecified, minor-release-mutable resolution rule underneath
    the one module whose entire purpose is that nothing is silently decided is the wrong
    dependency. A generic parameter removes the union entirely.
    (ULTIMATE_PRD.md §3.4; https://pydantic.dev/docs/validation/latest/concepts/unions/ ·
     https://pydantic.dev/docs/validation/latest/concepts/models/)
    """

    register_id: int = Field(ge=1, le=11)
    """Row number in MASTER_PRD.md §10. Makes the 1:1 register mapping machine-checkable, which is
    exactly what baby_prd.md acceptance criterion #2 requires a third party to be able to confirm."""

    value: T

    source: str = Field(min_length=1)
    """Human-readable citation for the DEFAULT. Must never imply more settledness than the primary
    source supports."""

    primary_source_gap: str = ""
    """What the primary source does NOT settle about this entry. Non-empty and specific for entries
    #1, #2 and #5 (ULTIMATE_PRD.md §3.1(d) and Q1/Q2); empty string where the primary source is
    clear. This field exists because 'pending scholarly verification' alone does not distinguish
    'the standard says X and a scholar should confirm our reading of X' from 'the standard does not
    say anything and we inferred X'."""

    status: VerificationStatus = VerificationStatus.PENDING_SCHOLARLY_VERIFICATION

    configurable: bool = True
    """True for every register entry (MASTER_PRD.md §0: every judgment call is configurable).
    Means 'this is a fiqh judgment call, not a permissibility invariant' — it does NOT assert that
    more than one option is currently implemented (see DivestmentAttributionMethod,
    PurificationAccountingMethod)."""
```

Field defaults that are `FiqhParam` instances (below) are **shared across all `FiqhParams`
instances**. That is safe and intended here precisely because `MizanBaseModel` is `frozen=True`.
**Do not "fix" this with `default_factory`** — it would create per-instance copies of immutable
objects for no benefit and would obscure that these are single canonical values.

#### 3.3.3 `FiqhParams` — exactly 11 fields, 1:1 with `MASTER_PRD.md` §10

```python
from pydantic import model_validator

from mizan.core.base import MizanBaseModel


class FiqhParams(MizanBaseModel):
    """The full judgment-call register. Every field maps 1:1 to a row of MASTER_PRD.md §10."""

    # ── #1 ────────────────────────────────────────────────────────────────────────────────────
    ratio_denominator_basis: FiqhParam[RatioDenominatorBasis] = FiqhParam[RatioDenominatorBasis](
        register_id=1,
        value=RatioDenominatorBasis.MARKET_CAP,
        source=(
            "AAOIFI SS21 public methodology (Merah, Oct 2017). Market-cap is the conventional "
            "reading; the MSCI/FTSE-style alternative is total assets."
        ),
        primary_source_gap=(
            "UNVERIFIED: AAOIFI's own denominator basis is NOT stated anywhere in the public "
            "methodology. The Merah presentation states the OTHER standards' denominators "
            "explicitly (slide 31: DJ = trailing 12-month moving average market cap; FTSE = total "
            "assets; S&P = market value of equity) but never AAOIFI's. market_cap is an INFERENCE. "
            "See ULTIMATE_PRD.md §3.1(d) and OPEN ARCHITECTURE QUESTIONS Q1."
        ),
    )

    # ── #2 ────────────────────────────────────────────────────────────────────────────────────
    ratio_denominator_smoothing: FiqhParam[RatioDenominatorSmoothing] = (
        FiqhParam[RatioDenominatorSmoothing](
            register_id=2,
            value=RatioDenominatorSmoothing.SPOT,
            source=(
                "Spot (unsmoothed) is the conventional AAOIFI-faithful reading; index providers "
                "bolt on 12/24/36-month smoothing."
            ),
            primary_source_gap=(
                "UNVERIFIED: AAOIFI's averaging window (or its absence) is NOT stated in the "
                "public methodology. The previously-asserted SS21 fragment 'the last budget or "
                "verified financial position' could not be verified against any reachable source. "
                "spot is an INFERENCE. See ULTIMATE_PRD.md §3.1(d) and Q1."
            ),
        )
    )

    # ── #3 ────────────────────────────────────────────────────────────────────────────────────
    debt_ratio_threshold: FiqhParam[float] = FiqhParam[float](
        register_id=3,
        value=0.30,
        source=(
            "AAOIFI SS21, verified verbatim in the Merah presentation slides 32-34: AAOIFI 30% "
            "vs DJ/FTSE/S&P 33%."
        ),
    )

    # ── #4 ────────────────────────────────────────────────────────────────────────────────────
    interest_investments_threshold: FiqhParam[float] = FiqhParam[float](
        register_id=4,
        value=0.30,
        source="AAOIFI SS21, verified verbatim in the Merah presentation slides 33-34 (30%).",
    )

    # ── #5 ────────────────────────────────────────────────────────────────────────────────────
    non_permissible_income_threshold: FiqhParam[float] = FiqhParam[float](
        register_id=5,
        value=0.05,
        source=(
            "AAOIFI SS21, verified verbatim (Merah slide 32): 'Non Halal Income Should not Exceed "
            "5% of Total Income'."
        ),
        primary_source_gap=(
            "DENOMINATOR AMBIGUITY: the primary source says 'Total Income'; MASTER_PRD.md §6.2 "
            "item 3 says 'total revenue'. Under US GAAP these are different line items, and the "
            "gap is material precisely for firms near the 5% boundary. Phase 4 must pick one "
            "explicitly and cite this gap. See ULTIMATE_PRD.md OPEN ARCHITECTURE QUESTIONS Q2 — "
            "the human may promote this into a 12th register entry, which would move "
            "MASTER_PRD.md §10, baby_prd.md AC #2 and this spec together."
        ),
    )

    # ── #6 ────────────────────────────────────────────────────────────────────────────────────
    business_activity_tier_0_5_enabled: FiqhParam[bool] = FiqhParam[bool](
        register_id=6,
        value=True,
        source=(
            "Tier 0.5 = adult content, weapons/defence. Reaches AAOIFI only via enumerated item 8, "
            "'Any activities deemed unlawful'. Default ON."
        ),
        primary_source_gap=(
            "Verified NOT AAOIFI-enumerated: the Merah presentation's AAOIFI industry list (slide "
            "18) is exactly 8 items and contains neither adult content nor weapons/defence; both "
            "appear only in the index-provider comparison column (slide 31). Keeping this "
            "configurable rather than hardcoded is the primary-source-faithful choice."
        ),
    )

    # ── #7 ────────────────────────────────────────────────────────────────────────────────────
    business_activity_tier_1_enabled: FiqhParam[bool] = FiqhParam[bool](
        register_id=7,
        value=False,
        source=(
            "Tier 1 = media/music/entertainment, hotels. Genuinely contested across scholarly "
            "bodies. Default OFF."
        ),
        primary_source_gap=(
            "Not AAOIFI-enumerated (Merah slide 18); 'Entertainment' appears only in the "
            "index-provider comparison column (slide 31)."
        ),
    )

    # ── #8 ────────────────────────────────────────────────────────────────────────────────────
    grace_period_rebalances: FiqhParam[int] = FiqhParam[int](
        register_id=8,
        value=1,
        source=(
            "Common Islamic-fund practice: divest at the next rebalance after a compliance flip. "
            "Unit is WHOLE REBALANCE PERIODS, not days."
        ),
        primary_source_gap=(
            "No AAOIFI-stated grace period found in the public methodology. This tunes divestment "
            "timing WITHIN the quarterly cadence; it is not a licence to change the cadence "
            "itself (ULTIMATE_PRD.md §1.1)."
        ),
    )

    # ── #9 ────────────────────────────────────────────────────────────────────────────────────
    purify_capital_gains: FiqhParam[bool] = FiqhParam[bool](
        register_id=9,
        value=False,
        source="Fork A: dividends-only for V1; capital-gains purification default OFF.",
        primary_source_gap=(
            "The primary source establishes THAT non-halal income must be purified (Merah slides "
            "24-25) but gives no formula for capital gains. Genuinely underdetermined."
        ),
    )

    # ── #10 ───────────────────────────────────────────────────────────────────────────────────
    divestment_attribution_method: FiqhParam[DivestmentAttributionMethod] = (
        FiqhParam[DivestmentAttributionMethod](
            register_id=10,
            value=DivestmentAttributionMethod.TIME_BOUNDED_PRICE_APPRECIATION,
            source="Fork C: price appreciation over the flip-date to divestment-date window.",
            primary_source_gap=(
                "No settled formula exists. The Step 10 literature sweep (2024-2026) found no "
                "proposed alternative either — an explicit null result, not an unsearched gap. "
                "See ULTIMATE_PRD.md §3.5."
            ),
        )
    )

    # ── #11 ───────────────────────────────────────────────────────────────────────────────────
    purification_accounting_method: FiqhParam[PurificationAccountingMethod] = (
        FiqhParam[PurificationAccountingMethod](
            register_id=11,
            value=PurificationAccountingMethod.SIDE_LEDGER,
            source=(
                "Fork B, now PRIMARY-SOURCE VERBATIM (Merah slide 25): purification means non-halal "
                "income 'will have to be donated to Charity and cannot be included in the investors "
                "P&L accounts'. A side-ledger is the only faithful reading."
            ),
        )
    )

    @model_validator(mode="after")
    def _register_ids_are_exactly_one_to_eleven(self) -> "FiqhParams":
        """The register must cover MASTER_PRD.md §10 rows #1-#11 exactly once each."""
        ids = sorted(getattr(self, name).register_id for name in type(self).model_fields)
        if ids != list(range(1, 12)):
            raise ValueError(
                f"fiqh register_id set must be exactly 1..11 with no duplicates; got {ids}"
            )
        return self


FIQH_PARAMS = FiqhParams()
```

**Exactly 11 fields**, matching `MASTER_PRD.md` §10 rows #1–#11 and satisfying `baby_prd.md` AC #2's
requirement that a third party can count them and confirm 1:1 coverage. `register_id` makes that
count machine-checkable rather than a naming-convention argument.

**Do not add a 12th entry in Phase 1.** `ULTIMATE_PRD.md` Q2 proposes one (the "Total Income" vs
"total revenue" denominator) but it is escalated to the human, not applied — adding it would break
`baby_prd.md` AC #2's stated count. The ambiguity is carried in #5's `primary_source_gap` instead.

### 3.4 `mizan/core/verdict.py`

```python
from enum import Enum


class Verdict(str, Enum):
    """Three-state screening verdict. Never boolean.

    Defined in Phase 1 so every later module (screening in Phase 4, backtest in Phase 5) imports
    one canonical enum instead of each phase inventing its own.

    The three states and their definitions are a direct transcription of the AAOIFI public
    methodology (Merah, Oct 2017, slide 21), quoted in ULTIMATE_PRD.md §3.1(c):

    * PURE          - "Shari'ah compliant core business and no interest based deposits or loans"
    * MIXED         - "Shari'ah compliant core business and financial ratios that do not exceed
                       the thresholds"  -> purification applies
    * NON_COMPLIANT - "with Non-Halal activity as its core source of income and if debt and
                       investment ratios exceed the allowed thresholds"  -> not investable; if
                       held, triggers the flip -> forced-divestment path
    """

    PURE = "pure"
    MIXED = "mixed"
    NON_COMPLIANT = "non_compliant"
```

**Enum definition only.** No scoring logic, no reason-trace structure, no `screen()` function — all
Phase 4 (§9).

### 3.5 `mizan/core/caveats.py`

```python
from enum import Enum

from mizan.core.base import MizanBaseModel


class Caveat(str, Enum):
    """Honesty caveats that must be stamped on every result that reaches a human.

    LOOK_AHEAD_BIAS
        The V1 Fork-1 simplification: `screen(ticker, as_of_date)` uses the most-recent-available
        filing rather than true filing-lag-corrected point-in-time data. Stated precisely
        (ULTIMATE_PRD.md §3.3, after arXiv:2607.04958): this is a SINGLE DECLARED VIOLATION OF
        TEMPORAL NON-INTERFERENCE, CONFINED TO ONE FUNCTION BODY. The V2 work item is therefore a
        checkable property - "restore temporal non-interference in screen()" - not a vague "fix the
        look-ahead thing". Observed magnitude: EDGAR facts routinely carry a >2-year gap between
        period `end` and `filed` (ULTIMATE_PRD.md §3.3).

    SURVIVORSHIP_BIAS
        The universe is "companies that exist today", which silently excludes anything delisted or
        gone to zero. Accepted and loudly flagged for V1; V2 freezes a historical as-of snapshot.

    PENDING_SCHOLARLY_VERIFICATION
        At least one fiqh judgment call in the run's configuration is unratified. Given
        FiqhParams' Phase 1 shape, this is true of every run: all 11 register entries carry
        VerificationStatus.PENDING_SCHOLARLY_VERIFICATION.
    """

    LOOK_AHEAD_BIAS = "look_ahead_bias"
    SURVIVORSHIP_BIAS = "survivorship_bias"
    PENDING_SCHOLARLY_VERIFICATION = "pending_scholarly_verification"


class ResultEnvelope(MizanBaseModel):
    """Every backtest/screening result that reaches a human MUST be wrapped in this envelope.

    `active_caveats` has NO default. Omitting it at construction raises ValidationError; it is not
    silently an empty tuple. An empty tuple `()` is a valid, explicit choice a caller can make; an
    *omitted* argument is not. This is the Phase 1 mechanism that makes ULTIMATE_PRD.md §2.2's "no
    code path renders a number without its caveat set" a type-level fact from Phase 7 onward.

    NOTE: this model inherits frozen=True, so Pydantic generates __hash__(), but `payload` is a
    dict and therefore unhashable - `hash(envelope)` raises TypeError. Do not place a
    ResultEnvelope in a set or use it as a dict key, in this or any later phase.
    """

    active_caveats: tuple[Caveat, ...]
    payload: dict[str, object]
```

`payload` is intentionally loose (`dict[str, object]`) in Phase 1 — Phases 5, 6 and 7 define their
own typed payload models and this field's practical shape narrows then. Phase 1 fixes only the
envelope's outer contract.

---

## §4 Public Interfaces / Function Signatures

**This project has no HTTP API.** It is a batch/CLI tool (`MASTER_PRD.md` §9; `baby_prd.md` scope
edge #6 — no FastAPI, no dashboard, ever, in V1). This section therefore covers module-level
function signatures and the one CLI entrypoint.

### 4.1 `mizan/config/boot_check.py`

```python
class InvariantViolationError(RuntimeError):
    """Raised by check_invariants() when any Invariants field fails its required value."""


class FiqhRegisterError(RuntimeError):
    """Raised by check_fiqh_register() when the honesty surface is structurally broken."""


def check_invariants(invariants: Invariants | None = None) -> None:
    """Assert every permissibility invariant holds.

    Args:
        invariants: the instance to check. Defaults to the module-level INVARIANTS singleton.
            The parameter exists SOLELY so tests can construct a deliberately-violating instance
            and prove this function rejects it (PHASE_1_SPEC.md §8 criterion 2). No production
            call site may pass it.

    Raises:
        InvariantViolationError: on any violation, listing every violated field.

    Never returns a boolean. Never logs-and-continues. Callers wanting a non-raising check catch
    the exception themselves; this function's contract is raise-or-silently-pass.
    """


def check_fiqh_register(params: FiqhParams | None = None) -> None:
    """Assert the fiqh judgment-call register is structurally honest.

    Checks, for the register as a whole and every entry:
      * exactly 11 entries;
      * register_ids are exactly {1..11}, each once;
      * every entry's `source` is non-empty;
      * every entry's `status` is PENDING_SCHOLARLY_VERIFICATION;
      * every entry's `configurable` is True;
      * entries #1, #2 and #5 have a non-empty `primary_source_gap`.

    Args:
        params: defaults to the module-level FIQH_PARAMS singleton. Parameter exists for tests
            only, same rationale as check_invariants().

    Raises:
        FiqhRegisterError: listing every structural failure found.

    Rationale: the register IS the honesty surface (MASTER_PRD.md §0). A silently-dropped
    verification flag or an empty source string is exactly the kind of silent-correctness failure
    MASTER_PRD.md §13 names as this project's dangerous class, so it is gated at boot rather than
    left to review.
    """


def check_all() -> None:
    """Run check_invariants() then check_fiqh_register(). Raises on the first failure."""


def main() -> int:
    """CLI entrypoint for `mizan-boot-check`.

    Calls check_all(). Returns 0 on success; 1 on InvariantViolationError or FiqhRegisterError
    (message printed to stderr). A non-zero exit code is the machine-readable signal the phase
    loop's review agent checks for.

    Every later phase's CLI entrypoints (ingest | screen | backtest | report, Phases 2-7) MUST
    call check_all() as their first action and exit non-zero on failure, matching this behaviour.
    """
```

Registered in `pyproject.toml` as:
```toml
[project.scripts]
mizan-boot-check = "mizan.config.boot_check:main"
```

### 4.2 `mizan/core/base.py`, `mizan/core/verdict.py`, `mizan/core/caveats.py`

**No functions.** Pure type/model definitions as specified in §3. The only callable surface is
Pydantic's own generated `__init__` plus the standard model methods (`model_dump()`,
`model_validate()`, `model_copy()`) — none of which Phase 1 overrides or wraps.

### 4.3 `mizan/config/invariants.py`, `mizan/config/fiqh_params.py`

**No functions** beyond the module-level singletons `INVARIANTS` and `FIQH_PARAMS`, and
`FiqhParams`' one `@model_validator`. Later phases read fields directly — e.g.
`FIQH_PARAMS.debt_ratio_threshold.value`, `INVARIANTS.cash_yield`. Phase 1 provides **no**
getter/accessor layer; the typed model attributes are the interface.

---

## §5 Migrations

**N/A in Phase 1.**

DuckDB schema design, table creation, and any migration tooling belong to **Phase 3**
(Normalization & DuckDB store), per `ULTIMATE_PRD.md` §6. Phase 1 introduces no database, no schema,
and no persistent storage of any kind — `Invariants` and `FiqhParams` are pure in-memory Pydantic
models constructed at import time.

Any Phase 1 code that opens a DuckDB connection, reads or writes a Parquet file, or otherwise
touches persistent storage is out of scope and must be rejected by the review agent (§9).

Forward note, so Phase 3 does not have to rediscover it: DuckDB permits **one writer per database
file**, coordinated by file locks (`ULTIMATE_PRD.md` §3.4, §4.5). The Phase 3 uniqueness constraint
for XBRL facts is `(cik, taxonomy, tag, unit, start, end, accn)` — `accn` is required because the
same reporting period is legitimately re-reported across filings.

---

## §6 Implementation Logic Flow

Function by function. Deterministic anchors named explicitly, per the loop's audit requirement.

### 6.1 `check_invariants()`

```python
def check_invariants(invariants: Invariants | None = None) -> None:
    from mizan.config.invariants import INVARIANTS

    inv = INVARIANTS if invariants is None else invariants
    violations: list[str] = []

    if inv.cash_yield != 0.0:
        violations.append(f"cash_yield must be 0.0, got {inv.cash_yield!r}")
    if not inv.long_only:
        violations.append("long_only must be True")
    if not inv.fully_funded:
        violations.append("fully_funded must be True")
    if inv.derivatives_allowed:
        violations.append("derivatives_allowed must be False")
    if inv.margin_allowed:
        violations.append("margin_allowed must be False")
    if inv.riba_modeling_allowed:
        violations.append("riba_modeling_allowed must be False")
    if inv.llm_in_compliance_path_allowed:
        violations.append("llm_in_compliance_path_allowed must be False")

    if violations:
        raise InvariantViolationError("; ".join(violations))
```

Each check is written out explicitly, field by field. **No loop over `model_dump()` comparing
against a "golden dict."** This is deliberate: a golden-dict diff would silently pass a newly-added
`Invariants` field that this function was never updated to assert on. Writing each check by hand
makes *adding a field without adding its check* a visible, reviewable diff gap — the model changed
and `check_invariants` didn't. All seven violations are collected before raising, so a broken config
reports everything at once rather than one field per run.

### 6.2 `check_fiqh_register()`

```python
def check_fiqh_register(params: FiqhParams | None = None) -> None:
    from mizan.config.fiqh_params import FIQH_PARAMS

    reg = FIQH_PARAMS if params is None else params
    problems: list[str] = []

    field_names = list(type(reg).model_fields)
    if len(field_names) != 11:
        problems.append(f"register must have exactly 11 entries, found {len(field_names)}")

    seen_ids: list[int] = []
    gap_required = {1, 2, 5}

    for name in field_names:
        entry = getattr(reg, name)
        seen_ids.append(entry.register_id)
        if not entry.source.strip():
            problems.append(f"{name}: source is empty")
        if entry.status is not VerificationStatus.PENDING_SCHOLARLY_VERIFICATION:
            problems.append(f"{name}: status is {entry.status!r}, expected pending verification")
        if not entry.configurable:
            problems.append(f"{name}: configurable must be True (MASTER_PRD.md §0)")
        if entry.register_id in gap_required and not entry.primary_source_gap.strip():
            problems.append(
                f"{name}: register #{entry.register_id} requires a non-empty "
                f"primary_source_gap (ULTIMATE_PRD.md §3.1(d), Q1/Q2)"
            )

    if sorted(seen_ids) != list(range(1, 12)):
        problems.append(f"register_id set must be exactly 1..11, got {sorted(seen_ids)}")

    if problems:
        raise FiqhRegisterError("; ".join(problems))
```

The `{1, 2, 5}` gap-required set is written as a literal, not derived, for the same
visible-diff-gap reason as §6.1: if `ULTIMATE_PRD.md` Q1 or Q2 is later resolved and an entry no
longer needs its gap note, that change must appear in this function's diff.

### 6.3 `check_all()` and `main()`

```python
def check_all() -> None:
    check_invariants()
    check_fiqh_register()


import sys


def main() -> int:
    try:
        check_all()
    except InvariantViolationError as exc:
        print(f"BOOT FAILED — permissibility invariant violated: {exc}", file=sys.stderr)
        return 1
    except FiqhRegisterError as exc:
        print(f"BOOT FAILED — fiqh register is structurally broken: {exc}", file=sys.stderr)
        return 1
    print("Boot check passed: permissibility invariants hold; fiqh register is intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Only `main()` may catch these exceptions. A `try`/`except` inside `check_invariants()` or
`check_fiqh_register()` themselves is a review-blocking finding (§7).

### 6.4 Deterministic anchors established by Phase 1 (explicit, per the loop's audit requirement)

Phase 1 establishes the project's first **deterministic anchors** — units whose output is a pure
function of their fixed inputs, with **no LLM, no network call, no filesystem read, no clock read,
and no randomness**:

| Anchor | Determinism guarantee |
|---|---|
| `mizan.config.invariants.INVARIANTS` | Fixed at import time from literal defaults. Always identical. |
| `mizan.config.fiqh_params.FIQH_PARAMS` | Fixed at import time from literal defaults. Always identical. |
| `mizan.config.boot_check.check_invariants` | Pure function of an `Invariants` instance. |
| `mizan.config.boot_check.check_fiqh_register` | Pure function of a `FiqhParams` instance. |
| `mizan.core.verdict.Verdict` | Closed three-member enum. |
| `mizan.core.caveats.Caveat` | Closed three-member enum. |

**There is nothing for a deterministic anchor to *anchor* in this project, and that is the point.**
The universal invariant "deterministic rules engines anchor any LLM extraction/generation" is
satisfied vacuously and more strictly than usual: Mizan's V1 core has **no LLM anywhere** —
ingestion, screening, the compliance-flip state machine, and purification are 100% deterministic
code (`ULTIMATE_PRD.md` §5; `baby_prd.md` scope edge #5, **permanent, not a "for now"**). Likewise
**LLM routing is N/A** for this project and does not apply to any module under `mizan/config`,
`mizan/data`, `mizan/screening`, `mizan/backtest`, or `mizan/reporting`.

Every later phase must name its own anchors with the same explicitness in its own phase spec
(`screen()` in Phase 4, state transitions in Phase 5, the purification computation in Phase 6).
Phase 1 sets the convention; it does not enumerate later phases' anchors.

---

## §7 Failure-Mode Guards

Derived from `ULTIMATE_PRD.md` §4 (failure-mode analysis) and §5 (grep-able boundary), restricted to
what can actually go wrong in Phase 1.

| # | Anticipated Phase 1 failure mode | Guard | Exactly what the review agent checks |
|---|---|---|---|
| G1 | An `Invariants` field becomes a runtime knob (env var, CLI flag, config file) | `Invariants()` constructed with **zero arguments** at module scope (§3.2); `frozen=True` blocks post-construction mutation | `grep -nE "os\.environ\|getenv\|argparse\|sys\.argv\|configparser\|tomllib\|json\.load\|open\(" mizan/config/invariants.py` — **any hit is blocking**. Also: `grep -rn "Invariants(" mizan/` — every hit outside `tests/` must be the bare `Invariants()` with no arguments. |
| G2 | `cash_yield` (or any invariant) set to a non-default value anywhere | `check_invariants()` explicit per-field assertions (§6.1) | Run `mizan-boot-check` → exit 0. Then run `tests/test_invariants.py`, which constructs `Invariants(cash_yield=0.01)` and asserts `InvariantViolationError` is raised. Also `ULTIMATE_PRD.md` §5 checks 1 and 4 over `mizan/`. |
| G3 | A register entry loses its `source`, or `status` drifts off `PENDING_SCHOLARLY_VERIFICATION` | Every `FiqhParam` literal sets `register_id`, `value` and `source` explicitly; `status` has a class default never overridden inline; **`check_fiqh_register()` gates it at boot** (§6.2) | `mizan-boot-check` exits non-zero if any entry is broken. `tests/test_fiqh_params.py` asserts, for all 11: non-empty `source`, `status == PENDING_SCHOLARLY_VERIFICATION`, `configurable is True`. |
| G4 | The register drifts from `MASTER_PRD.md` §10's 11 rows (fewer, more, renamed, or duplicated) | `FiqhParams` is a `MizanBaseModel` (`extra="forbid"`); the `@model_validator` asserts `register_id`s are exactly `{1..11}`; `check_fiqh_register()` asserts the field count | `len(FiqhParams.model_fields) == 11` **and** the sorted `register_id` list equals `[1..11]`. A mismatch requires either a PRD update or a code fix, **never a silent one-sided change**. |
| G5 | **A `source` string overstates what the primary source says** — the honesty surface lying (`ULTIMATE_PRD.md` §4.4, HALT-for-human) | Entries #1, #2, #5 carry a mandatory non-empty `primary_source_gap`, enforced at boot (§6.2) and by test | Read all 11 `source` + `primary_source_gap` strings against `ULTIMATE_PRD.md` §3.1. Specifically: **#1 and #2 must say AAOIFI's denominator/averaging window is NOT stated in public methodology and the default is an inference; #5 must state the "Total Income" vs "total revenue" ambiguity.** A source string implying AAOIFI settled #1 or #2 is **blocking**. |
| G6 | **`FiqhParam.value` typed as a union**, reintroducing dependence on Pydantic's unspecified, minor-release-mutable smart-union resolution (`ULTIMATE_PRD.md` §3.4) | `FiqhParam` is generic: `FiqhParam(MizanBaseModel, Generic[T])` with `value: T` | `grep -nE "value\s*:\s*.*\|" mizan/config/fiqh_params.py` — any union in the `value` annotation is blocking. Every `FiqhParams` field must be an explicitly parameterised `FiqhParam[...]`. |
| G7 | `check_invariants()` / `check_fiqh_register()` "softened" to log-and-continue | Contract is raise-or-silently-pass (§4.1); no `logging.warning(...) + return` path exists | `grep -nE "warning\(\|warn\(\|except .*(InvariantViolationError\|FiqhRegisterError)" mizan/config/boot_check.py` — an `except` for these types anywhere **except inside `main()`** is blocking. |
| G8 | `ConfigDict(extra="forbid")` omitted on a new model, or a model subclasses `pydantic.BaseModel` directly | All models inherit `MizanBaseModel` (§3.1) | `grep -rn "BaseModel" mizan/` — the only file that may import or subclass `pydantic.BaseModel` is `mizan/core/base.py`. Any other direct subclass is blocking. |
| G9 | `Verdict` defined as a boolean or a two-state enum | Three literal members (§3.4) | `len(Verdict) == 3` and members are exactly `{PURE, MIXED, NON_COMPLIANT}`. |
| G10 | A `ResultEnvelope` constructible without `active_caveats` (a default `()` sneaks in) | No default on `active_caveats` (§3.5) | `ResultEnvelope(payload={})` raises `pydantic.ValidationError`; `ResultEnvelope(active_caveats=(), payload={})` succeeds. Both asserted in `tests/test_core_types.py`. |
| G11 | The `Caveat` set silently shrinks below the three `baby_prd.md` AC #4 requires | Three literal members (§3.5) | `len(Caveat) == 3`, members exactly `{LOOK_AHEAD_BIAS, SURVIVORSHIP_BIAS, PENDING_SCHOLARLY_VERIFICATION}`. |
| G12 | An LLM/model-client SDK or `yfinance` enters `pyproject.toml` or any Phase 1 module | Dependency list is closed (§2.5); Phase 1 imports only `pydantic` | `ULTIMATE_PRD.md` §5 checks 5 and 6, run over `mizan/` and `pyproject.toml`. **Any hit is a HALT**, not a discussion. |
| G13 | A Phase 1 module imports a not-yet-needed dependency (`httpx`, `duckdb`, `pyarrow`, `pandas`, `matplotlib`) | §2.1 declares them in extras for forward stability only; §9 forbids importing them | `grep -rnE "^\s*(import\|from)\s+(httpx\|duckdb\|pyarrow\|pandas\|matplotlib)" mizan/` — any hit is blocking in Phase 1. |
| G14 | Persistent storage touched in Phase 1 | §5: no DB, no files | `grep -rnE "open\(\|Path\(.*\)\.(write\|read)\|connect\(\|read_parquet\|to_parquet" mizan/` — any hit is blocking. |
| G15 | **`pyproject.toml` pins disagree with `docs/modernization_log.md`** | §2.4 requires exact string match | Compare every version string in `pyproject.toml` `dependencies` / `optional-dependencies` / `dev` against `docs/modernization_log.md` §3–§4. Any mismatch is blocking. Also: the `3.14.__` placeholder in §2 of that file must be filled in. |
| G16 | `mypy --strict` or `ruff` not actually wired or not clean | `[tool.mypy] strict = true`, `[tool.ruff]` configured (§2.1) | `mypy --strict mizan tests` exits 0; `ruff check mizan tests` exits 0. |
| G17 | AI attribution appears in commit messages | `.claude/loopr/context.md` § Soft context note 2, `MASTER_PRD.md` §9.5 | `git log --format=%B` for this phase's commits contains no `Co-Authored-By`, no "Generated with", no model or assistant name. Configured git user only. |
| G18 | The **values boundary** (§1.1 of `ULTIMATE_PRD.md`) drifts into Phase 1 as a "cadence" knob | Rebalance cadence is not in the fiqh register and must not be added to it | `grep -rniE "\b(daily\|intraday\|hourly\|minute\|tick)[-_ ]?(rebalance\|rebalancing\|signal)\b" mizan/` — expected to be trivially clean in Phase 1; a hit means a build agent invented a cadence parameter. **HALT and escalate to the human**, do not fix silently. |

**Categorisation:** G1–G7, G12, G15, G17, G18 are **HALT-for-human** — they touch the
permissibility boundary, the honesty surface, or the loop's own integrity. G8–G11, G13, G14, G16 are
blocking-but-mechanical: fix and re-run.

---

## §8 Phase Acceptance Criteria

All of the following must hold for the review agent to mark Phase 1 complete. Each is concrete and
runnable by a third party with no knowledge of how it was built (the `baby_prd.md` AC standard,
applied at phase level).

1. **Boot gate passes on defaults.** `mizan-boot-check` (or `python -m mizan.config.boot_check`)
   exits **0** and prints `Boot check passed: permissibility invariants hold; fiqh register is
   intact.`
2. **Boot gate actually gates — invariants.** A test constructing `Invariants(cash_yield=0.01)` and
   calling `check_invariants(that_instance)` raises `InvariantViolationError`. Repeated for at
   least one boolean invariant (e.g. `Invariants(margin_allowed=True)`).
3. **Boot gate actually gates — register.** A test constructing a `FiqhParams` copy with one entry's
   `source` blanked (via `model_copy(update=...)`) and calling `check_fiqh_register(that_instance)`
   raises `FiqhRegisterError`. Repeated for a blanked `primary_source_gap` on entry #1.
4. **Register is exactly 11, 1:1 with `MASTER_PRD.md` §10.** `len(FiqhParams.model_fields) == 11`,
   and the sorted set of `register_id` values is exactly `[1,2,3,4,5,6,7,8,9,10,11]`. Field names
   may differ in style from the PRD's prose labels, but every PRD row has exactly one field, and
   `register_id` names which.
5. **Every register entry is flagged and sourced.** For all 11: `source` is a non-empty string,
   `status == VerificationStatus.PENDING_SCHOLARLY_VERIFICATION`, `configurable is True`.
6. **The three honesty gaps are recorded.** Entries with `register_id` in `{1, 2, 5}` each have a
   non-empty `primary_source_gap`; #1 and #2's text states that AAOIFI's denominator basis /
   averaging window is not stated in the public methodology and the default is an inference; #5's
   text states the "Total Income" vs "total revenue" ambiguity. (`ULTIMATE_PRD.md` §3.1(d), Q1, Q2.)
7. **`FiqhParam.value` carries no union.** `FiqhParam` is declared
   `class FiqhParam(MizanBaseModel, Generic[T])` with `value: T`, and every `FiqhParams` field is an
   explicitly parameterised `FiqhParam[...]`.
8. **`Verdict` is a three-member `str, Enum`** with members exactly `PURE`, `MIXED`,
   `NON_COMPLIANT` — no more, no fewer.
9. **`Caveat` is a three-member `str, Enum`** with members exactly `LOOK_AHEAD_BIAS`,
   `SURVIVORSHIP_BIAS`, `PENDING_SCHOLARLY_VERIFICATION`.
10. **`ResultEnvelope` cannot be built without a caveat set.** `ResultEnvelope(payload={})` raises
    `pydantic.ValidationError`; `ResultEnvelope(active_caveats=(), payload={})` succeeds.
11. **`extra="forbid"` is real.** Constructing any Phase 1 model with an undeclared keyword (e.g.
    `Invariants(nonexistent_field=1)`) raises `pydantic.ValidationError`.
12. **`frozen=True` is real.** `INVARIANTS.cash_yield = 0.01` raises (Pydantic frozen-instance
    error).
13. **Every model inherits `MizanBaseModel`.** No file under `mizan/` other than
    `mizan/core/base.py` imports or subclasses `pydantic.BaseModel`.
14. **`mypy --strict mizan tests` exits 0** (zero errors), under the pinned `mypy==2.3.1`.
15. **`ruff check mizan tests` exits 0** under the pinned `ruff==0.16.5` and the ruleset configured
    in `pyproject.toml`.
16. **`pytest` passes in full** — `test_invariants.py`, `test_fiqh_params.py`, `test_core_types.py`
    all green under the pinned `pytest==9.1.1`.
17. **No forbidden dependency anywhere.** `pyproject.toml` contains no `openai`, `anthropic`,
    `google-genai`, `google-generativeai`, `google-cloud-aiplatform`, `vertexai`, `langchain`,
    `litellm`, `transformers`, `ollama`, or `yfinance`, in `dependencies`, any extra, or the dev
    group. `ULTIMATE_PRD.md` §5 checks 5 and 6 come back clean over `mizan/`.
18. **No premature imports.** No module under `mizan/` imports `httpx`, `duckdb`, `pyarrow`,
    `pandas`, or `matplotlib` (they are declared for forward stability only).
19. **No persistent storage.** No module under `mizan/` opens a file, a database connection, or a
    Parquet path.
20. **Pins reconcile.** Every version string in `pyproject.toml` appears identically in
    `docs/modernization_log.md` §3–§4, **and** the `3.14.__` placeholder in that file's §2 has been
    replaced with the actual build interpreter version.
21. **Commits are neutral.** `git log` for this phase's commits contains no AI attribution
    (`Co-Authored-By`, "Generated with", model or assistant names) — configured git user only.
22. **Boundary greps are clean.** All of `ULTIMATE_PRD.md` §5 checks 1–6 return no hits when run
    from the repository root against the Phase 1 tree. (Checks 7 and 8 are trivially clean in
    Phase 1 — no `filed` field and no cadence code exists yet — but must still be run and recorded
    as clean, so the loop has a baseline.)

**Any single failing criterion is a phase-loop HALT, not a partial pass.** Phase 2 must not begin
ingestion work against an unstable foundation — this mirrors `MASTER_PRD.md` §13's
"HALT-for-human on any correctness exception," applied to the build loop itself.

---

## §9 Explicit NON-GOALS (what is NOT built in Phase 1)

- **No ingestion.** No EDGAR client, no Tiingo client, no `httpx` call sites, no raw-cache read or
  write. `httpx` is declared in the `ingest` extra for forward stability only. → **Phase 2**, which
  also owns: the three EDGAR endpoints (`companyfacts`, `companyconcept`, **`submissions` for SIC**
  — `ULTIMATE_PRD.md` §2), the declared-bot header triple, the ≥0.12 s spacing plus **≥600 s
  cooldown** on an EDGAR block, and Tiingo's *separate* hourly/daily **request-budget** limiter
  (50/hr, 1,000/day — **not** a per-second spacing, and **not** 50 symbols/hour;
  `ULTIMATE_PRD.md` §3.4).
- **No DuckDB, no Parquet, no persistent storage of any kind.** See §5. `duckdb` and `pyarrow` are
  declared for the same forward-stability reason. → **Phase 3**.
- **No screening logic.** `Verdict` (§3.4) is an **enum definition only** — no business-activity
  classifier, no SIC first-pass, no hand-verified activity map, no ratio calculator, no reason-trace
  structure, no `screen(ticker, as_of_date)` function, no tier gating. → **Phase 4**, which also
  owns the threshold-margin enrichment of the reason trace and the temporal-non-interference
  confinement check (`ULTIMATE_PRD.md` §3.3, §4.4, §5 check 7).
- **No resolution of `ULTIMATE_PRD.md`'s open questions.** Q1 (AAOIFI denominator `[UNVERIFIED]`),
  Q2 (a possible 12th register entry for the "Total Income" denominator), and Q3 (SS21 §3/2 and the
  deferred HFT edge) are **escalated to the human, not Phase 1's to resolve.** Phase 1 ships **11**
  register entries and records the ambiguities in `primary_source_gap` (§3.3.3). Adding a 12th entry
  in Phase 1 would break `baby_prd.md` AC #2's stated count.
- **No backtest engine, no compliance-flip state machine, no portfolio or strategy code.** →
  **Phase 5**.
- **No purification logic** (side-ledger computation, `divCash` reconciliation, Fork A/B/C
  application). The `FiqhParams` entries #9/#10/#11 are *declarations*; nothing reads them yet. →
  **Phase 6**.
- **No reporting.** No HTML generation, no `matplotlib` plots, no caveat-stamped rendering, no
  gross-vs-net-of-purification figures. `ResultEnvelope` (§3.5) is a **contract definition only** —
  no renderer consumes it yet. → **Phase 7**.
- **No CLI entrypoints beyond `mizan-boot-check`.** The `mizan/cli/` package and the
  `ingest | screen | backtest | report` verbs belong to their respective later phases.
- **No LLM, ever, in any phase.** Not deferred — **permanently** out of scope for the V1 core
  (`ULTIMATE_PRD.md` §5; `baby_prd.md` scope edge #5; `MASTER_PRD.md` §2). Restated here because
  Phase 1 is exactly where a build agent might reach for a "smart config loader" or "LLM-assisted
  parameter suggestion" convenience. That instinct is **wrong for this project** and must not appear
  anywhere, including as an optional, disabled, or commented-out code path.
- **No HTTP API, no service, no dashboard.** Not a Phase-1 deferral — out of V1 entirely
  (`baby_prd.md` scope edge #6).
- **No change to the rebalance cadence surface.** Quarterly is settled (`ULTIMATE_PRD.md` §1.1);
  sub-quarterly rebalancing or intraday signals cross a **values** boundary and are escalated, never
  implemented. Nothing in Phase 1 should create a cadence parameter.

---

## §10 Rebuild Delta (what changed vs. the pre-modernization Phase 1 spec, and why)

Recorded so the review agent can confirm this file is a genuine output of the Step 10 pass rather
than the old file left in place.

| # | Change | Cause in the modernised PRD |
|---|---|---|
| 1 | **Layout flattened to the repository root**; the `mizan-sandbox/` nesting directory is removed | `ULTIMATE_PRD.md` §5's grep checks are written against `mizan/config/...` and `mizan/backtest/...`; a nesting directory would make a review agent's boundary greps silently find nothing |
| 2 | **9 dependency pins updated, 3 ranges converted to exact pins**, Python ceiling added | `ULTIMATE_PRD.md` §2.1, changelog A |
| 3 | **`FiqhParam` is now generic (`FiqhParam[T]`)** instead of `value: bool \| float \| str` | `ULTIMATE_PRD.md` §3.4 — Pydantic's smart-union algorithm is explicitly documented as changeable between minor releases and does not specify `bool`/`int` resolution; the honesty surface must not depend on it |
| 4 | **`register_id: int` field added** to `FiqhParam` + a `@model_validator` asserting `{1..11}` | Makes `baby_prd.md` AC #2's "count these against MASTER_PRD.md §10's 11-row register and confirm 1:1 coverage" machine-checkable instead of a naming argument |
| 5 | **`primary_source_gap: str` field added**, mandatory for entries #1, #2, #5 | `ULTIMATE_PRD.md` §3.1(d) demoted AAOIFI's denominator/averaging claim to `[UNVERIFIED]`, and §3.1(b) found the "Total Income" vs "total revenue" ambiguity. `pending scholarly verification` alone cannot distinguish "confirm our reading of what the standard says" from "the standard says nothing and we inferred this" |
| 6 | **Register `source` strings rewritten** to match the primary source actually read | `ULTIMATE_PRD.md` §3.1 — the AAOIFI presentation was extracted and quoted this pass; slides 18, 21, 25, 32–34 now back entries #3–#7 and #11, and slide 31 backs the Tier 0.5/Tier 1 demotion |
| 7 | **Four new enums** (`RatioDenominatorBasis` and `RatioDenominatorSmoothing` kept; `DivestmentAttributionMethod` and `PurificationAccountingMethod` added) replacing free-form strings | Removes free-form strings from the honesty surface. Each new enum defines **only** the V1 default, because §3.2 and the §3.5 null result establish that no alternative is settled or even proposed |
| 8 | **`check_fiqh_register()` + `FiqhRegisterError` added**, and `main()` now runs `check_all()` | The register *is* the honesty surface (`MASTER_PRD.md` §0) and a dropped flag is a silent-correctness failure (`ULTIMATE_PRD.md` §4.4, HALT-for-human) — so it is gated at boot, not left to review |
| 9 | **`check_invariants()` gained an optional parameter** | Lets the test suite prove the gate rejects violations without mutating the module singleton; production call sites still pass nothing |
| 10 | **`mizan/py.typed` added** | Required for `mypy --strict` to treat the package as typed when imported from `tests/` |
| 11 | **`docs/modernization_log.md` is now MODIFIED, not created**, in Phase 1 | The Step 10 pass created it; Phase 1's only edit is filling in the build interpreter version (§2.4), plus the new pin-reconciliation criterion (§8.20, G15) |
| 12 | **Guards G5, G6, G15, G18 are new**; the LLM check split into import-specific and name-based forms; a dependency-manifest check added | `ULTIMATE_PRD.md` §4.4 (source-string honesty), §3.4 (union hazard), §2.4 (pin reconciliation), §1.1 (the newly-named values boundary), §5 (tightened grep set) |
| 13 | **Acceptance criteria grew from 13 to 22**, and every one is now third-party-runnable | `baby_prd.md`'s acceptance-criteria standard applied at phase level; new criteria cover the register honesty gaps, the generic-`FiqhParam` requirement, premature imports, persistent storage, and pin reconciliation |
| 14 | **`Caveat.LOOK_AHEAD_BIAS` docstring reframed** as "a single declared violation of temporal non-interference, confined to one function body" | `ULTIMATE_PRD.md` §3.3, applying arXiv:2607.04958 — makes the V2 work item a checkable property rather than a vague fix, at zero cost and with no new dependency |
| 15 | **§9 non-goals now name the escalated open questions** (Q1/Q2/Q3) as explicitly not Phase 1's to resolve | `ULTIMATE_PRD.md` OPEN ARCHITECTURE QUESTIONS — a literal-minded execution agent reading only this file must not "helpfully" add a 12th register entry or reopen a deferred values edge |
| 16 | **Phase count restated as a re-derived decision** with the rejected 8th-phase alternative named | `ULTIMATE_PRD.md` §6 — the instruction was to decide the number, not copy it |
