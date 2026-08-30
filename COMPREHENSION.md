# COMPREHENSION.md — Mizan

Written after Phase 1 ("Foundation & Config") was reviewed and approved. This file explains, in the
operator's own language, what actually got built — grounded in the code as it exists in the repo
right now, not in what the specs said it would be.

---

## 1. Plain-language walkthrough

Mizan is a personal research tool for a single person who wants to test long-only stock-trading
strategies that follow Islamic finance rules ("halal" or "Shariah-compliant" investing), using real
historical US stock data. It is not a live trading system — no real money ever moves through it. It
is a sandbox for learning whether a rule-respecting strategy would have worked.

The core tension the whole project is built around: which Islamic finance rules are truly settled
(no company may profit mainly from things like alcohol, gambling, conventional interest-based
banking, and so on), and which rules are genuinely disputed even among qualified scholars (exactly
how do you measure "how much debt is too much debt," expressed as a percentage of what?). The
project's design insists on keeping these two categories visibly separate at all times: settled
rules are locked in stone and cannot be changed by anyone running the software; disputed rules are
left as clearly labeled, adjustable settings, each one stamped "not yet confirmed by a scholar,"
with an honest note about exactly what is uncertain.

What actually got built in this first phase is not the strategy engine itself — no stock is being
screened yet, no money is being simulated yet. What got built is the foundation everything else
will stand on: the list of settled rules (seven of them, e.g., "never use borrowed money," "never
earn interest on idle cash"), the list of eleven disputed judgment calls (with each one's best
current guess, its supporting citation, and an honest note about what is still unclear), a
"boot check" that refuses to even start the program if any of that foundation looks wrong, and a
handful of shared building-block definitions (a three-way pass/partial-pass/fail verdict, and a
set of warning labels that must travel with every result the tool ever produces). Nothing here
screens a stock or runs a backtest yet — that comes in later phases. This phase is the guardrail
and the honesty ledger that those later phases will be required to read from and obey.

## 2. Architecture walkthrough

Everything below is a real file in the repository, read directly this pass.

```
mizan/
├── __init__.py                  # empty — marks mizan as a Python package
├── py.typed                     # empty marker file so type-checkers treat the package as typed
├── config/
│   ├── __init__.py               # empty
│   ├── invariants.py             # the 7 settled, non-negotiable rules (Invariants class + INVARIANTS singleton)
│   ├── fiqh_params.py            # the 11-row disputed-judgment-call register (FiqhParams + FIQH_PARAMS singleton)
│   └── boot_check.py             # startup checks that refuse to run if invariants.py or fiqh_params.py are broken
└── core/
    ├── __init__.py               # empty
    ├── base.py                   # MizanBaseModel — the one shared base every data model in the project must use
    ├── verdict.py                # Verdict — the three-state pass/partial/fail screening outcome (definition only)
    └── caveats.py                # Caveat enum + ResultEnvelope — the mandatory warning-label wrapper for results
tests/
├── __init__.py                   # empty
├── test_invariants.py            # proves the boot check actually rejects a broken settled-rule config
├── test_fiqh_params.py           # proves the 11-row register is complete, honest, and structurally sound
└── test_core_types.py            # proves the shared base model, Verdict, and Caveat/ResultEnvelope behave as documented
pyproject.toml                    # project metadata, exact dependency version pins, mypy/ruff/pytest config, CLI entry point
docs/modernization_log.md         # a running log of exactly which external tool/library versions were verified and when
```

How the pieces connect:

- `mizan/core/base.py` defines `MizanBaseModel`, a Pydantic model with three settings turned on that
  Pydantic does not turn on by default: unknown fields are rejected outright rather than silently
  dropped, every instance is immutable once created, and default values are validated the same as
  any user-supplied value. Every other model class in the project (`Invariants`, `FiqhParam`,
  `FiqhParams`, `ResultEnvelope`) inherits from this one base — nothing else in `mizan/` is allowed
  to build directly on Pydantic's own base class. A test (`test_only_core_base_imports_or_subclasses_pydantic_basemodel`
  in `tests/test_core_types.py`) enforces this by scanning every `.py` file under `mizan/` for the
  literal word `BaseModel`.

- `mizan/config/invariants.py` defines the `Invariants` model (7 fields: `cash_yield`, `long_only`,
  `fully_funded`, `derivatives_allowed`, `margin_allowed`, `riba_modeling_allowed`,
  `llm_in_compliance_path_allowed`) and constructs exactly one instance, `INVARIANTS`, at import
  time with zero arguments. Nothing anywhere in the codebase is allowed to construct a second
  `Invariants()` with different values (the one deliberate exception is inside
  `tests/test_invariants.py`, which needs to build a "broken" instance to prove the checker catches
  it).

- `mizan/config/fiqh_params.py` defines `FiqhParams`, a model with exactly 11 fields, one per row of
  the disputed-judgment-call register (`MASTER_PRD.md` §10). Each field holds a `FiqhParam[T]`
  instance — a small generic wrapper carrying the row's current value, its register number, a
  human-readable source citation, an optional note about what the source does *not* settle, a
  verification status (currently always "pending scholarly verification"), and a `configurable`
  flag that is always `True`. A `@model_validator` on `FiqhParams` itself checks that the eleven
  `register_id`s are exactly `{1, ..., 11}` with no gaps or duplicates. One module-level instance,
  `FIQH_PARAMS`, is built at import time.

- `mizan/config/boot_check.py` reads both singletons and validates them. `check_invariants()` walks
  all seven `Invariants` fields by hand (not via a generic loop) and raises `InvariantViolationError`
  listing every violated field if anything is off. `check_fiqh_register()` walks all eleven
  `FiqhParams` entries and raises `FiqhRegisterError` if the register isn't exactly 11 entries, any
  entry's `source` is empty, any `status` has drifted, any `configurable` flag is `False`, or entries
  #1, #2, or #5 are missing their mandatory gap note. `check_all()` runs both. `main()` is the
  `mizan-boot-check` console-script entry point (registered in `pyproject.toml`) — it calls
  `check_all()`, prints a pass/fail message, and returns exit code 0 or 1.

- `mizan/core/verdict.py` defines `Verdict`, a three-member string enum (`PURE`, `MIXED`,
  `NON_COMPLIANT`). It is a bare enum definition — no scoring logic lives here yet.

- `mizan/core/caveats.py` defines `Caveat` (a three-member string enum: `LOOK_AHEAD_BIAS`,
  `SURVIVORSHIP_BIAS`, `PENDING_SCHOLARLY_VERIFICATION`) and `ResultEnvelope`, a model with two
  required fields: `active_caveats` (a tuple of `Caveat` values, with no default — it must be
  supplied explicitly, even as an empty tuple) and `payload` (an untyped `dict[str, object]` for
  now). This is the wrapper every future screening/backtest result must be returned inside, so no
  code path can hand a number to the user without also declaring which warnings apply to it.

- `pyproject.toml` declares one runtime dependency (`pydantic==2.13.5`), three optional-dependency
  groups reserved for later phases (`ingest`: httpx; `data`: duckdb/pyarrow/pandas; `report`:
  matplotlib) that nothing in this phase's code imports, a dev group (mypy, ruff, pytest, all exact
  pins), and the `mizan-boot-check` console script pointing at `mizan.config.boot_check:main`.

- `docs/modernization_log.md` was modified (not created) this phase: the placeholder Python
  interpreter line was replaced with the actual build-machine version, `3.14.4`. Verified this run —
  the interpreter currently on this machine reports `Python 3.14.4` and the installed `pydantic`
  reports `2.13.5`, both matching the pins.

## 3. Decisions and tradeoffs

- **`FiqhParam` is generic (`FiqhParam[T]`), not a `bool | float | str` union.** The tradeoff:
  Pydantic's own documentation states its "smart union" resolution algorithm "may change between
  minor releases" and does not pin down how it resolves `bool` vs `int` (`bool` is technically a
  subtype of `int` in Python). A generic type parameter is more code to declare per field
  (`FiqhParam[float]`, `FiqhParam[bool]`, etc., verified directly in `mizan/config/fiqh_params.py`
  lines 121-271) but removes any dependence on an algorithm the project doesn't control and that
  sits directly underneath the module whose entire job is "nothing here is silently decided."
  `tests/test_fiqh_params.py::test_fiqh_param_is_generic_not_a_union` locks this in by inspecting
  `FiqhParam.__parameters__` and each field's Pydantic generic metadata.

- **Hand-written, field-by-field checks in `check_invariants()` and `check_fiqh_register()`, instead
  of a generic loop over `model_dump()`.** The tradeoff: hand-written checks are more verbose and
  must be updated by hand every time a field is added, versus a generic diff-against-golden-dict
  approach that would auto-cover new fields. The code (and its docstrings, read directly) explains
  the choice: a generic loop would silently pass a newly added field that nobody wrote a check for;
  the hand-written version makes "a field was added but its check wasn't" a visible line-count gap
  in the diff, at the cost of needing a human to remember to add the check.

- **`StrEnum` (Python 3.11+ stdlib) rather than the spec's literally-written `class X(str, Enum)`.**
  `VerificationStatus`, `Verdict`, and `Caveat` are all built on `from enum import StrEnum` in the
  actual code (`mizan/config/fiqh_params.py` line 10, `mizan/core/verdict.py` line 6,
  `mizan/core/caveats.py` line 6), not the `str, Enum` double-inheritance pattern PHASE_1_SPEC.md
  §3.3.1/§3.4/§3.5 shows in its code blocks. These are behaviourally equivalent for this project's
  purposes (both give string-comparable enum members), so this is a real, if minor, divergence
  between what the spec's illustrative code says and what was actually shipped — noted here rather
  than silently treated as identical.

- **`docs/modernization_log.md` was edited, not created, and touched only its one placeholder line.**
  Verified by diffing `docs/modernization_log.md` between the two commits: the only change is
  replacing `3.14.x — record the exact patch here at first build: 3.14.__` with the measured
  `3.14.4`, plus removing the now-satisfied "Action for the Phase 1 execution agent" instruction
  paragraph. No other line in the file changed. This matches the constraint that the file's other
  entries are external facts that shouldn't be touched by application code changes.

- **`tests/__init__.py` was added even though §1's file tree in PHASE_1_SPEC.md does not explicitly
  list it** (it lists `test_invariants.py`, `test_fiqh_params.py`, `test_core_types.py` under
  `tests/` but the tree's own indentation implies a leading `__init__.py` row was omitted from the
  diagram). The actual repo has it, empty, consistent with `mizan/`'s own `__init__.py` files. Not a
  meaningful deviation — flagged only for completeness.

## 4. Domain mechanics

This phase is mostly config/scaffolding, but it does encode real domain figures — the entire
`mizan/config/fiqh_params.py` register is domain content. Every figure below is exactly what is
written in the code today, with the code's own citation carried alongside it. This project's own
methodology already distinguishes "sourced" from "inferred/unverified" more precisely than a blanket
verification pass could, so that distinction is preserved rather than flattened.

| # | Figure / default | Value in code | Code's own source citation | Code's own honesty flag |
|---|---|---|---|---|
| 1 | Ratio denominator basis | `market_cap` | AAOIFI SS21 public methodology (Merah presentation, Oct 2017) | Code itself marks this **[UNVERIFIED / INFERENCE]** — the register's own `primary_source_gap` text states AAOIFI's denominator basis is not stated anywhere in the public methodology; market-cap is inferred, not confirmed |
| 2 | Ratio denominator smoothing | `spot` (unsmoothed) | Same Merah presentation, by contrast with index-provider practice | Code itself marks this **[UNVERIFIED / INFERENCE]** — same reasoning, the averaging window is not stated in the public methodology |
| 3 | Debt-ratio threshold | 30% | "Merah presentation slides 32-34" (per code comment) | No gap flagged — code states this was verified verbatim against the cited slides |
| 4 | Interest-investments threshold | 30% | "Merah presentation slides 33-34" (per code comment) | No gap flagged — same claim of verbatim verification |
| 5 | Non-permissible income threshold | 5% | "Merah presentation slide 32" (per code comment), quoted as "Non Halal Income Should not Exceed 5% of Total Income" | Code flags a **denominator ambiguity**: the source says "Total Income," `MASTER_PRD.md` §6.2 says "total revenue" — these can differ under US GAAP, and the code states this matters most for firms near the boundary |
| 6 | Business-activity Tier 0.5 (adult content, weapons/defence) | enabled (`True`) | Code comment: reaches AAOIFI only via its catch-all "any activities deemed unlawful" clause | Code flags this as **not directly AAOIFI-enumerated** — appears only in an index-provider comparison column per the cited slide, not AAOIFI's own list |
| 7 | Business-activity Tier 1 (media/music/entertainment, hotels) | disabled (`False`) | Code comment: "genuinely contested across scholarly bodies" | Code flags this as **not AAOIFI-enumerated** either |
| 8 | Grace period before forced divestment | 1 rebalance period | Code comment: "common Islamic-fund practice" | Code flags **no AAOIFI-stated grace period was found** in the public methodology |
| 9 | Purify capital gains | disabled (`False`, dividends-only) | Code comment: "Fork A" | Code flags that the source establishes THAT non-halal income must be purified but has no formula for capital gains specifically |
| 10 | Divestment-attribution method | time-bounded price appreciation over the flip-to-divestment window | Code comment: "Fork C" | Code flags this as **no settled formula exists**, and states a 2024–2026 literature sweep found no proposed alternative either |
| 11 | Purification accounting | side-ledger (never netted into NAV) | Code comment: primary-source verbatim quote — non-halal income "will have to be donated to Charity and cannot be included in the investors P&L accounts" | No gap flagged — code treats this as the only faithful reading of a directly quoted source |

I did not independently re-pull the cited AAOIFI/Merah presentation or verify slide numbers this
run — I have no live web/document-fetch capability invoked in this pass, and the task's own
non-goals direct against inventing a new verification pipeline. Everything in the table above is
reported as *what the code itself claims and how the code itself already flags its own confidence*,
not as independently re-confirmed fact. Where the code marks something UNVERIFIED, this document
also marks it as such rather than upgrading its status.

Separately, the seven `Invariants` fields (`mizan/config/invariants.py`) are not "disputed" figures
but they are domain-grounded choices: `cash_yield = 0.0` in particular encodes the position that
idle cash may never earn interest (riba), sourced in the code's docstring to `MASTER_PRD.md` §2 and
`ULTIMATE_PRD.md` §5. These are treated in the code as settled boundary conditions, not judgment
calls, and carry no `primary_source_gap` mechanism because that mechanism exists only on the
`FiqhParam` register.

## 5. Honesty audit

I ran the exact verification commands PHASE_1_SPEC.md §7 and §8 specify, against the code as it
exists in the repository right now, rather than trusting the spec's or an approval commit's claim
that they pass.

**Everything below passed as claimed, verified this run:**
- `pytest tests/` — 63 tests, all green.
- `ruff check mizan tests` — "All checks passed!", exit 0.
- All seventeen boundary greps in §7 (G1, G6, G8, G12/G13, G14, G18) — clean, no hits, matching the
  spec's claim.
- `git log --format=%B` across all three commits — no `Co-Authored-By`, no "Generated with," no
  model/assistant name anywhere. AC21 holds.
- `python --version` reports `3.14.4` and `pip show pydantic` reports `2.13.5` on this machine —
  both match the pins recorded in `pyproject.toml` and `docs/modernization_log.md` exactly (AC20).

**One concrete, real gap found, not previously visible from reading the spec alone:**

AC14 states plainly: "`mypy --strict mizan tests` exits 0 (zero errors)." Run verbatim this pass,
it does not — it exits 1:

```
C:\Users\hp\AppData\Roaming\Python\Python314\site-packages\numpy\__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater  [syntax]
Found 1 error in 1 file (errors prevented further checking)
```

Root cause, traced with `mypy -v`: `pytest`'s own `_pytest.python_api` module optionally imports
`numpy` for its `approx()` typing, and mypy follows that import when checking the `tests` directory
(because `tests/` imports `pytest`). The globally-installed `numpy` (version 2.5.2 — not a Mizan
dependency at all; it's present on this machine's shared Python install, not inside a project-scoped
virtual environment) ships a type stub using Python 3.12+ `type`-statement syntax, which fails to
parse under `pyproject.toml`'s pinned `[tool.mypy] python_version = "3.11"`.

Scoping the same command to `mizan mizan/config mizan/core` (i.e. `mypy --strict mizan`, excluding
`tests`) passes cleanly — "Success: no issues found in 9 source files." So this is not a defect in
any line of Mizan's own shipped code; Mizan never imports numpy, and it is not declared anywhere in
`pyproject.toml`. It is a gap between AC14's literal claim ("`mizan tests` exits 0") and what
actually happens when that exact command is run in an environment without an isolated,
project-scoped virtual environment — a real, reproducible discrepancy between the acceptance
criterion as written and the environment it was verified in, worth carrying forward rather than
silently reconciling.

## 6. Open items

- **The mypy/tests-numpy interaction above** is unresolved. It does not block Phase 1's own approval
  (Phase 1's code passes `mypy --strict` on its own), but a future phase's CI or local verification
  step run without an isolated virtual environment will hit the same false failure the moment
  `tests/` is included in the mypy target. Worth pinning down before this becomes a recurring false
  alarm: either isolate the project into its own virtualenv (recommended — this repo currently has
  no `.venv` and installs directly into the shared, per-user Python site-packages), or scope future
  mypy invocations to exclude `tests/` if `pytest`'s numpy-optional typing keeps causing this.
- **The three escalated fiqh open questions (Q1, Q2, Q3 in `ULTIMATE_PRD.md`)** remain unresolved by
  design — this phase explicitly defers them to a human/scholar rather than picking an answer. Q1
  (AAOIFI's true denominator basis), Q2 (whether "Total Income" vs "total revenue" in entry #5
  should become a 12th register row), and Q3 are all still open.
- **All eleven fiqh register entries remain `PENDING_SCHOLARLY_VERIFICATION`** — this is the honest,
  expected state for V1 and is not itself a defect, but it means every future screening/backtest
  result inherits that caveat by construction (via `Caveat.PENDING_SCHOLARLY_VERIFICATION`), and
  nothing in this phase or the roadmap resolves it — only an actual scholar's ruling would.
- **No project-scoped virtual environment exists in this repo** (confirmed: no `.venv` directory,
  dependencies installed into the shared per-user Python 3.14 site-packages). This is what caused
  the mypy finding above and is itself worth fixing before Phase 2 adds real dependencies
  (`httpx`), since a shared environment makes "no premature imports" (G13) harder to verify with
  confidence going forward.

---

## Phase Log

**Phase 1 — Foundation & Config** (2026-08-30)

Phase 1 established Mizan's foundation before any ingestion, screening, or backtest logic exists.
It shipped: the seven-field `Invariants` model and its single `INVARIANTS` singleton, encoding the
permissibility boundary (long-only, fully-funded, zero cash yield, no derivatives, no margin, no
riba modeling, no LLM in the compliance path) as fixed constants with no override mechanism; the
eleven-row `FiqhParams` register and its `FIQH_PARAMS` singleton, encoding every genuinely disputed
Islamic-finance judgment call (ratio denominator basis and smoothing, the 30/30/5 thresholds,
business-activity tiering, grace period, and the three purification forks) as visible, sourced,
`pending_scholarly_verification`-stamped configuration rather than silent hardcoding; a fail-fast
`mizan-boot-check` CLI entry point that refuses to let the program start if either the invariants or
the register is structurally broken; and the shared cross-cutting types every later phase will
import — `MizanBaseModel` (the strict/frozen/validated Pydantic base every model must use),
`Verdict` (the three-state screening outcome enum), and `Caveat`/`ResultEnvelope` (the mandatory
warning-label wrapper for every future result). `pyproject.toml` was written with exact,
externally-verified dependency pins, and `docs/modernization_log.md` was updated with the actual
build-machine Python version (3.14.4). 63 tests were added covering boot-gate rejection behaviour,
register completeness and honesty, and the shared type contracts; all 63 pass, `ruff` is clean, and
`mypy --strict` is clean when scoped to `mizan/` itself. No screening, ingestion, backtest, or
purification logic was written — those remain Phases 2 through 7.
