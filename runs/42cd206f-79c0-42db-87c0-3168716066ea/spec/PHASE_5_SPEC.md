# Phase 5 — Signal-Adapter Seam and Validation Gate: Interface, Provenance, Calibration, Abstention

## Goal
Build the signal-adapter seam (AC 11, 12): a `typing.Protocol`-based contract for a pluggable
external forecasting signal that mandates declared data provenance/licence, a calibrated
probability-plus-uncertainty output with a structurally distinct abstention path, and a typed,
testable validation-gate specification (out-of-sample comparison, calibration, per-token/per-regime
error reporting, beating both a naive and a TimesFM baseline) that must pass before a signal is
permitted to drive allocations. No adapter implementation, no TimesFM integration, no wiring into
`run_crypto_backtest` or `Strategy`. Interface, metadata schema, and gate criteria only — matching
the PRD's "contract, no implementation" requirement for this seam.

## Scope
In scope: a new `mizan/signal/` package (`contract.py` — provenance, the predict-or-abstain signal
type, the `SignalAdapter` protocol; `validation_gate.py` — the gate's typed criteria and the
blocking-decision function); their tests; a new `docs/crypto/VALIDATION_GATE.md` (the written
validation-gate specification prose AC 12 names); `docs/crypto/ARCHITECTURE.md` (additive),
`docs/crypto/PHASE_5_SPEC.md` (commit this spec as the governing document), `README.md` (one
sentence); the scope-guard extension. Out of scope: everything in "Out of scope for this phase"
below.

Every new/edited module: `from __future__ import annotations`, full type annotations
(`mypy --strict` clean), ruff-clean, module docstring citing `docs/crypto/PHASE_5_SPEC.md §…`. No
new runtime dependency — `pydantic` is already pinned and reused as-is; `timesfm`/`numpy` are
**not** added (§Out of scope).

## Part A (first agent) — the signal contract types

### A1. Why a new parallel `mizan/signal/` package, not `mizan/execution/`
`mizan/execution/intent.py`'s `ResolvedOrder` (Phase 1) is the no-najsh order/intent model: a
frozen value object whose `outcome` is a mandatory discriminated union of exactly one terminal
state (`FillResult` or `OrderRejection`), with no resting/cancelable state. A signal adapter is a
different concern entirely — an external forecast *input* to a future allocation decision, not an
order's *outcome* — and the PRD's own research digest (`runs/42cd206f-79c0-42db-87c0-3168716066ea/
research/report.md` §"Pluggable forecasting-signal interface with provenance, calibration and
abstention") recommends a `typing.Protocol` (PEP 544) rather than an ABC for this exact reason:
third-party adapter authors must be able to satisfy the contract structurally, without being forced
into this repo's class hierarchy the way `ResolvedOrder`'s sealed union deliberately forces every
order through one type. `mizan/signal/` is new rather than folded into `mizan/execution/` so the
scope guard can assert, independently of the no-najsh invariant tests, that this seam ships with no
adapter implementation and no network capability of its own (§B6). The one genuine *pattern* reused
from `mizan/execution/intent.py` is the discriminated-union "illegal states unrepresentable"
technique applied to `Signal.outcome` (§A3) — not the module, not the type itself.

### A2. Provenance metadata — mandatory, not optional
**File:** `mizan/signal/contract.py` (new).
```python
class SignalProvenance(MizanBaseModel):
    source: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    licence_url: str | None = None
    data_provenance: str = Field(min_length=1)
```
Modelled on the Hugging Face model-card metadata spec (`license`/`license_name`/`license_link`/
`datasets`) the research digest cites as the most widely deployed provenance schema. `source`,
`licence`, and `data_provenance` are `Field(min_length=1)` — not `str = ""` defaults — so a
provenance block with an empty or absent declaration is a construction-time `ValidationError`, not a
runtime check an adapter author could skip (fatwa part 2's "every data source must be public or
licensed" is the reason this field exists at all; §Implications S7 is the test proving nothing
bypasses it).

### A3. The predict-or-abstain outcome — a sealed union, not two optional fields
**File:** `mizan/signal/contract.py`.
```python
class Prediction(MizanBaseModel):
    kind: Literal["prediction"] = "prediction"
    probability: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0)

class Abstention(MizanBaseModel):
    kind: Literal["abstention"] = "abstention"
    reason: str = Field(min_length=1)

class Signal(MizanBaseModel):
    ticker: str
    as_of_date: date
    provenance: SignalProvenance
    outcome: Prediction | Abstention = Field(discriminator="kind")
```
Mirrors `mizan.execution.intent.ResolvedOrder`'s own `outcome: FillResult | OrderRejection =
Field(discriminator="kind")` pattern exactly (§A1): a calibrated probability and an abstention are
modelled as one discriminated-union field, not as two independently-optional fields (`probability:
float | None`, `abstained: bool`) that could in principle both be set or both be unset. "Calibrated
probability/uncertainty" and "may abstain" are therefore mutually exclusive by construction, not by
runtime convention — the same "make illegal states unrepresentable" discipline the no-najsh order
type already established for this codebase (§A1's own citation of the research digest's "never
conflate 'low confidence' with 'no output'" recommendation). No smart-constructor/factory function
is needed here (unlike `place_order`'s own cross-field quantity check) — the discriminated union
alone is sufficient, since neither branch carries a field the other branch could invalidate.

### A4. The `SignalAdapter` protocol
**File:** `mizan/signal/contract.py`.
```python
@runtime_checkable
class SignalAdapter(Protocol):
    @property
    def provenance(self) -> SignalProvenance: ...

    def predict(
        self, *, as_of_date: date, ticker: str, context: tuple[float, ...]
    ) -> Signal: ...
```
`typing.Protocol`, not an ABC (§A1). `@runtime_checkable` so a test can `isinstance()`-check a
conforming object, with the PEP 544 caveat — "instance checks are not 100% reliable statically"
(quoted directly in the research digest) — restated in this file's own docstring so a future reader
does not over-trust `isinstance(obj, SignalAdapter)` as a full signature/behaviour check, only a
names-exist check (§Red-team R5). `context` is a plain `tuple[float, ...]` of past daily closes (or
log-returns), matching this build's daily-granularity ingestion and consistent with how the research
digest documents TimesFM's own `context` input shape — no adapter-specific input format is invented
here, this is the one shared shape every future adapter receives. No concrete class implementing
`SignalAdapter` ships anywhere under `mizan/` in this phase (§B6 enforces this; test-local stub
classes in `tests/test_signal_contract.py` are the only conforming objects that exist, and they
never leave the test file).

### A5. Part-A smoke tests
**File:** `tests/test_signal_contract.py` (new).
- `SignalProvenance` constructed with all four fields succeeds; omitting `source`, `licence`, or
  `data_provenance` each raises `pydantic.ValidationError`; an empty-string value for any of the
  three `min_length=1` fields also raises.
- `Prediction(probability=0.0, uncertainty=0.0)` and `Prediction(probability=1.0, uncertainty=0.0)`
  both succeed (inclusive boundary); `Prediction(probability=-1e-9, ...)` and
  `Prediction(probability=1.0 + 1e-9, ...)` both raise `pydantic.ValidationError` (§Red-team R3).
- `Prediction(probability=0.5, uncertainty=-0.01)` raises `pydantic.ValidationError`.
- `Abstention(reason="")` raises `pydantic.ValidationError`; `Abstention(reason="no edge detected")`
  succeeds.
- `Signal(..., outcome=Prediction(probability=0.6, uncertainty=0.1))` round-trips with
  `signal.outcome.kind == "prediction"`; `Signal(..., outcome=Abstention(reason="..."))` round-trips
  with `signal.outcome.kind == "abstention"` — the one assertion proving the discriminator actually
  resolves to the right concrete type on construction, not just on the literal default.
- A minimal test-local class defining both `provenance` (a property returning a `SignalProvenance`)
  and a matching `predict(...)` method satisfies `isinstance(stub, SignalAdapter)`; a second
  test-local class defining only `provenance` (no `predict`) does **not** satisfy it.

**Part A done when:** the module imports, `mypy --strict`/`ruff` pass, every A5 test passes.

## Part B (second agent)
Depends on Part A's committed module.

### B1. The validation-gate's typed criteria and required baselines
**File:** `mizan/signal/validation_gate.py` (new).
```python
class BaselineKind(StrEnum):
    NAIVE_LAST_VALUE = "naive_last_value"
    TIMESFM_2_5 = "timesfm_2_5"

class ScoringRule(StrEnum):
    CRPS = "crps"
    PINBALL = "pinball"

class CalibrationMethod(StrEnum):
    RELIABILITY_DIAGRAM = "reliability_diagram"
    PIT_HISTOGRAM = "pit_histogram"

class SignificanceTest(StrEnum):
    DIEBOLD_MARIANO = "diebold_mariano"

class ValidationGateSpec(MizanBaseModel):
    scoring_rule: ScoringRule
    calibration_method: CalibrationMethod
    significance_test: SignificanceTest = SignificanceTest.DIEBOLD_MARIANO
    required_baselines: frozenset[BaselineKind]

    @model_validator(mode="after")
    def _both_baselines_are_required(self) -> ValidationGateSpec:
        if self.required_baselines != frozenset(BaselineKind):
            raise ValueError(
                "validation gate must require beating every BaselineKind, not a subset — "
                "requiring only one baseline lets a signal pass by tying a weak comparator"
            )
        return self

DEFAULT_VALIDATION_GATE_SPEC = ValidationGateSpec(
    scoring_rule=ScoringRule.CRPS,
    calibration_method=CalibrationMethod.RELIABILITY_DIAGRAM,
    required_baselines=frozenset(BaselineKind),
)
```
`required_baselines != frozenset(BaselineKind)` is a construction-time rejection, not a lint — a
caller cannot build a `ValidationGateSpec` that only requires beating `TIMESFM_2_5` (dropping
`NAIVE_LAST_VALUE`, or vice versa), matching the research digest's explicit finding that TimesFM
alone frequently fails to beat a plain random-walk on financial return series, so a gate anchored to
TimesFM alone would be a weak null (§Documentation sources). `ScoringRule`/`CalibrationMethod` are
named enums, not free-text, so the gate's own methodology choice is itself type-checked: `CRPS`/
`PINBALL` (never bare MAE/MSE — point metrics alone don't reveal calibration per the digest), and
`RELIABILITY_DIAGRAM`/`PIT_HISTOGRAM` (never Brier-score-alone, per scikit-learn's own documented
caveat that Brier conflates calibration and refinement loss).

### B2. The pass/fail decision — caller-attested criteria, not a computed score
**File:** `mizan/signal/validation_gate.py`.
```python
class GateCriteria(MizanBaseModel):
    out_of_sample_disjoint: bool
    calibration_checked: bool
    beats_naive_last_value: bool
    beats_timesfm: bool
    per_token_breakdown_reported: bool
    per_regime_breakdown_reported: bool

def gate_passed(criteria: GateCriteria) -> bool:
    return all(criteria.model_dump().values())

class SignalNotValidatedError(RuntimeError):
    """Raised when a signal is used to drive allocations without a passing gate."""

def require_passing_gate(criteria: GateCriteria) -> None:
    if not gate_passed(criteria):
        raise SignalNotValidatedError(
            f"signal failed the validation gate: {criteria.model_dump()}"
        )
```
`GateCriteria`'s six boolean fields are the *structural* encoding of AC 12's own five requirements
(out-of-sample comparison against realised price; calibration; per-token error reporting;
per-regime error reporting; beating the TimesFM/naive baseline — split here into
`beats_naive_last_value` and `beats_timesfm` so neither can be silently dropped, matching
`ValidationGateSpec`'s own both-baselines rule in §B1). `gate_passed` has no score-threshold logic,
no CRPS/calibration computation, and no TimesFM call anywhere in its body — it is a pure boolean AND
over caller-supplied attestations, because no adapter or forecast implementation exists yet for it
to compute those booleans *from* (§Spec assumptions makes this explicit: this phase defines the
contract and the blocking function, not the measurement). `require_passing_gate` is the one
concrete callable a future phase's allocation-driving code is contractually required to call before
letting any `Signal` influence a `Strategy`'s `target_weights` — satisfying AC 11's "must pass a
validation gate before a signal can drive allocations" as a structural seam today, with the actual
wiring explicitly deferred (§Out of scope).

### B3. Part-B tests
**File:** `tests/test_validation_gate.py` (new).
- `DEFAULT_VALIDATION_GATE_SPEC.required_baselines == frozenset({BaselineKind.NAIVE_LAST_VALUE,
  BaselineKind.TIMESFM_2_5})`.
- `ValidationGateSpec(scoring_rule=ScoringRule.CRPS, calibration_method=
  CalibrationMethod.RELIABILITY_DIAGRAM, required_baselines=frozenset({BaselineKind.TIMESFM_2_5}))`
  (only one of the two baselines) raises `ValueError`; same for the naive-only subset and for an
  empty `frozenset()`.
- `gate_passed` is `True` when every `GateCriteria` field is `True`, and `False` when every field is
  `False`.
- Parametrized over all six field names: for each one, a `GateCriteria` with that single field
  `False` and every other field `True` must still make `gate_passed` return `False` — proving the
  decision is a genuine `all(...)`, not an `any(...)` typo that would silently pass a signal missing
  exactly one required check (§Red-team R4).
- `require_passing_gate` with an all-`True` `GateCriteria` does not raise; with any single field
  `False` it raises `SignalNotValidatedError` whose message names the failing criteria dict.

### B4. The written validation-gate specification document
**File:** `docs/crypto/VALIDATION_GATE.md` (new). The prose document AC 12 itself names
("the validation-gate specification requires…") — `ValidationGateSpec`/`GateCriteria` (§B1, §B2)
are its typed, testable companion, not a replacement for a human-readable spec. Must state, in
prose, each of the following (drawn from `runs/42cd206f-79c0-42db-87c0-3168716066ea/research/
report.md` §"Out-of-sample calibration, per-subgroup error and baseline-beating validation" and
§"TimesFM as zero-shot numeric baseline" — cited, not re-derived):
- Out-of-sample evaluation must use a leakage-safe split (walk-forward at minimum; purged/embargoed
  or combinatorial-purged cross-validation where resourcing allows) — never ordinary shuffled k-fold,
  which the digest's cited purging-library finding shows can report a spuriously high R² on a
  target that is provably unpredictable.
- Calibration must be reported as a reliability diagram / PIT histogram, never a Brier score alone
  (scikit-learn's own documented caveat: Brier conflates calibration loss and refinement loss).
- Error must be broken down per-token and per-regime as separate rows, not only in aggregate — the
  digest's cited 2026 benchmark paper shows an aggregate-looking improvement can collapse to
  near-zero statistical significance once broken out per asset.
- A signal must beat **both** a naive last-value baseline and zero-shot TimesFM, using a one-sided
  Diebold-Mariano significance test on forecast errors — not a smaller point-metric alone — citing
  the same benchmark paper's finding that pretrained time-series foundation models, including
  TimesFM, frequently fail to clear even a plain random-walk null on financial return series.
- The pinned TimesFM reference checkpoint is `google/timesfm-2.5-200m-pytorch` (Apache-2.0 weights,
  `pip install timesfm[torch]`), not TimesFM 3.0 (whose self-hosted weights carry a
  non-commercial-only licence) — matching fatwa part 2's "every data source must be public or
  licensed for this use" constraint, extended here to the reference model's own weight licence.
  TimesFM's own quantile heads are explicitly **not** used as the calibrated-probability source for
  this gate (Google's own TimesFM-2.0 model card states those heads "have not been calibrated after
  pretraining") — calibration must be measured independently against realised price.
- This document is prose/specification only; it states what a future adapter-implementing phase
  must build and measure, and builds none of it now.

### B5. Documentation
- `docs/crypto/ARCHITECTURE.md` (edit, additive paragraph): the new `mizan/signal/` package, why it
  is `typing.Protocol`-based rather than an ABC (§A1), and that `require_passing_gate` is a seam a
  future phase must call, not something any current code calls (§B2, §Out of scope).
- `docs/crypto/PHASE_5_SPEC.md`: commit this spec as the governing document, matching the Phase
  1–4 precedent (the backfill in Phase 2/3 shows this step is easy to forget; do it in this same
  turn).
- `README.md`: one added sentence noting the signal-adapter contract and validation-gate
  specification now exist (provenance/licence, calibrated probability with abstention, a
  structural out-of-sample/calibration/per-token/per-regime/dual-baseline gate), with no adapter
  implementation and no wiring to the backtest yet.

### B6. No forbidden code built (continuity of PHASE_1_SPEC.md §A6/B6, PHASE_2_SPEC.md §B7,
PHASE_3_SPEC.md A0.10/B5, PHASE_4_SPEC.md B6)
**File:** `tests/test_phase1_scope.py` (extend).
- `test_signal_package_has_no_network_or_forecasting_implementation`: source-grep every file under
  `mizan/signal/` for `httpx`/`requests`/`socket`/`timesfm`/`numpy` — none appears. This is a
  stricter check than the existing crypto scope guards (which only forbid network capability): it
  additionally forbids importing the reference forecasting library itself, since AC 11/12 require a
  contract and a written specification, not a dependency on `timesfm` landing in `pyproject.toml`
  this phase.
- `test_no_concrete_signal_adapter_implementation_ships_under_mizan`: `mizan/signal/` (and the rest
  of `mizan/`) contains no class whose source defines `predict(` and also inherits from or is
  decorated to satisfy `SignalAdapter` outside of `tests/` — implemented as a source-grep for the
  literal string `"SignalAdapter"` across `mizan/**/*.py` and asserting its only appearance is the
  protocol's own definition in `mizan/signal/contract.py` (no second file references the name at
  all, let alone subclasses or implements it).
- `test_require_passing_gate_is_not_yet_called_from_backtest_or_crypto_code`: source-grep
  `mizan/backtest/*.py` and `mizan/crypto/*.py` for `require_passing_gate` — it appears in neither,
  proving the seam exists without being prematurely half-wired into the one phase that actually
  drives allocations today (§Implications S7).
- `test_phase5_governing_spec_copy_exists_on_disk`: mirrors the existing Phase 2/4 siblings.

**Part B done when:** all Part-A + Part-B tests pass, `mypy --strict`/`ruff` clean,
`mizan-boot-check` still exits 0, the `SignalAdapter` protocol and `Signal`/`SignalProvenance`
contract types exist with zero concrete implementations under `mizan/`, the validation gate's typed
criteria and blocking function exist and are fully unit-tested, `docs/crypto/VALIDATION_GATE.md`
states the five AC-12 requirements in prose, and the stated `docs/`/README files are
updated/committed.

## Acceptance-criteria mapping (Phase 5)
| AC | Satisfied by | Concrete check |
|----|--------------|----------------|
| 11 — signal-adapter interface/contract (provenance/licence, calibrated probability/uncertainty, abstention, must pass a validation gate before driving allocations), no implementation | A2, A3, A4, B2, B6 | `tests/test_signal_contract.py::test_signal_provenance_*`, `test_prediction_*`, `test_abstention_*`; `tests/test_phase1_scope.py::test_no_concrete_signal_adapter_implementation_ships_under_mizan` |
| 12 — validation-gate specification: out-of-sample, calibration, per-token/per-regime error, beat TimesFM/naive baseline | B1, B3, B4 | `docs/crypto/VALIDATION_GATE.md`; `tests/test_validation_gate.py::test_validation_gate_spec_rejects_a_single_baseline_subset`, `test_gate_passed_is_false_for_any_single_false_criterion` |
| 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15 (doc) | Phases 1–4, 6 | Not in Phase 5 scope. |

## Documentation sources
No new external research was required for this phase. The contract design (`typing.Protocol` over
an ABC; mandatory provenance/licence metadata; a predict-or-abstain discriminated union; the
validation gate's scoring-rule/calibration/per-slice/dual-baseline/significance-test requirements)
follows the conventions already recorded in this run's own research digest
(`runs/42cd206f-79c0-42db-87c0-3168716066ea/spec/context.md` §"Research digest" and
`runs/42cd206f-79c0-42db-87c0-3168716066ea/research/report.md` §"Pluggable forecasting-signal
interface with provenance, calibration and abstention", §"Out-of-sample calibration, per-subgroup
error and baseline-beating validation", and §"TimesFM as zero-shot numeric baseline"). No new
technical-source dependency — `pydantic`'s discriminated-union support is already exercised by
`mizan.execution.intent.ResolvedOrder` (Phase 1).

## Out of scope for this phase
- Any concrete `SignalAdapter` implementation (gods-eye-view, Agent-Reach, MiroFish, TimesFM,
  Inkling 2 Small) — contract/interface only, per the locked PRD and this run's own research
  findings that Inkling 2 Small in particular has no role anywhere in this build's acceptance
  criteria.
- Any actual TimesFM call, model download, or `timesfm`/`numpy` dependency addition — the pinned
  checkpoint id and API shape are documented in `docs/crypto/VALIDATION_GATE.md` as the reference
  this gate requires a future adapter to beat, not integrated now.
- Any real calibration computation, CRPS/pinball scoring, Diebold-Mariano test, or purged/CPCV
  cross-validation code — `GateCriteria`'s booleans are caller-attested placeholders for a future
  phase's real measurement (§Spec assumptions).
- Wiring `SignalAdapter`/`require_passing_gate` into `mizan.backtest.strategy.Strategy`,
  `run_crypto_backtest`, or any CLI verb — `EqualWeightStrategy` remains the only concrete strategy
  exercised anywhere in this repo's tests after this phase, exactly as `PHASE_4_SPEC.md`'s own "Out
  of scope" section already stated.
- The two-speed ROADMAP's slow/fast layer build-out (still documentation-only, per
  `docs/crypto/ROADMAP.md`, unchanged by this phase).
- The HTML report and the single end-to-end pipeline command (Phase 6) — this phase's types are not
  rendered or invoked by any report or CLI verb.
- Re-deriving or contesting any fiqh register value — this phase touches no fiqh parameter; the
  signal-adapter seam is a technical/MLOps contract, not a fiqh judgment call.

## Spec assumptions
Gaps found while writing this spec were resolved as follows (nobody was asked):
- `GateCriteria`'s six boolean fields are **caller-attested inputs**, not values this phase computes
  from a real backtest or a real TimesFM call — no adapter or forecast implementation exists yet to
  compute them from. This phase's job is the structural contract (the typed criteria names and the
  all-must-be-true blocking function), not the measurement; a future phase that implements a real
  adapter and a real TimesFM/naive comparison will be the one to populate these booleans honestly
  and call `require_passing_gate`. This mirrors the PRD's own "contract, no implementation" framing
  for this entire phase.
- "Per-regime" is modelled as a single required boolean (`per_regime_breakdown_reported`), not an
  enumerated list of concrete regimes (e.g. bull/bear/high-volatility) — no regime-detection logic
  exists anywhere in this codebase yet, and inventing one now would be a second, undocumented
  feature beyond "the validation-gate specification requires… per-regime error reporting."
- `required_baselines` is a `frozenset[BaselineKind]` structurally forced to equal the full enum
  (§B1), rather than, say, two separate `bool` flags — chosen so that adding a third future required
  baseline (if ever needed) is a one-line enum addition that the existing validator's equality check
  picks up automatically, without a corresponding code change to every call site that currently
  writes `beats_naive_last_value and beats_timesfm` by hand.
- The pinned TimesFM reference is 2.5 (`google/timesfm-2.5-200m-pytorch`, Apache-2.0), not 3.0,
  because 3.0's self-hosted weights carry a non-commercial-only licence — a documentation choice,
  not a runtime dependency, since no TimesFM package is installed this phase.
- `mizan/signal/` is a new top-level package alongside `mizan/execution/`, not a submodule of either
  `mizan/crypto/` or `mizan/backtest/` — the signal-adapter contract is deliberately
  domain-agnostic (nothing in `SignalAdapter`/`Signal`/`ValidationGateSpec` names a crypto ticker
  type, a fiqh parameter, or an equity concept), matching the PRD's own framing of this seam as
  infrastructure for "a future two-speed prediction-plus-execution system," not a crypto-specific
  extension.
- `Signal` does not carry a smart-constructor/factory function the way `ResolvedOrder` does via
  `place_order` (§A3) — `ResolvedOrder`'s factory exists to enforce a cross-field invariant (fill
  quantity cannot exceed requested quantity) that has no analogue here; `Prediction`/`Abstention`'s
  own per-field validators are sufficient on their own, and adding an unnecessary factory function
  would be scope creep beyond what AC 11 requires.

## Implications
Second-order consequences found by review of this spec. This section only adds to the spec; the
locked PRD is unchanged.

### Additional acceptance criteria
S7. A test (source-grep, same technique as the existing scope guards) asserts
`require_passing_gate` is referenced nowhere under `mizan/backtest/` or `mizan/crypto/` —
confirming the gate function exists as a pure, free-standing seam and has not been prematurely,
partially wired into the one phase (Phase 4) that actually drives real allocations today.
_(correctness/scope: a well-intentioned future edit to `run_crypto_backtest` could import and call
`require_passing_gate` with a hand-waved, always-`True` `GateCriteria` "just to exercise the API,"
which would make the backtest's output look signal-gated when nothing real is being measured —
catching this early, in this phase's own test suite, is cheaper than catching it in a later
phase's review.)_

## Red-team findings
Weaknesses found by an adversarial review of this spec before it is built. This section only adds
to the spec; the locked PRD is unchanged.

### Additional acceptance criteria
R3. A test asserts `Prediction(probability=0.0, uncertainty=0.0)` and
`Prediction(probability=1.0, uncertainty=0.0)` both succeed, while `probability=-1e-9` and
`probability=1.0 + 1e-9` both raise `pydantic.ValidationError`. _(medium, correctness: `Field(ge=0.0,
le=1.0)`'s inclusive boundary is easy to get backwards — e.g. `gt=0.0, lt=1.0` would silently reject
a legitimate, fully-confident calibrated probability of exactly 0 or 1 — and this is exactly the
kind of off-by-epsilon mistake that survives a quick glance at the spec's code block but not a
boundary test.)_
R4. A test parametrized over all six `GateCriteria` field names asserts that flipping **any single
one** of them to `False` (holding the other five `True`) still makes `gate_passed(...)` return
`False`. _(high, correctness: `gate_passed`'s own spec text says "a pure boolean AND," but
`all(criteria.model_dump().values())` is one accidental `any(...)` away from silently passing a
signal that fails exactly one of the five AC-12 requirements — e.g. a signal that beats both
baselines and is out-of-sample-clean but was never calibration-checked would still pass a
mis-implemented gate, which is the single most consequential bug this phase could ship undetected.)_
R5. `tests/test_signal_contract.py`'s own module docstring (or the `SignalAdapter` protocol's
docstring in `mizan/signal/contract.py`) must state, verbatim, that `@runtime_checkable`
`isinstance()` checks verify method/attribute *names* only, never signatures or return types (the
PEP 544 caveat the research digest itself quotes). _(medium, maintenance: a future reviewer who
sees `isinstance(obj, SignalAdapter)` pass in a test could reasonably over-trust it as a full
contract-conformance check; a class with a `predict` method that takes the wrong arguments or
returns the wrong type would still pass this `isinstance()` check, and only `mypy --strict` — not
any runtime assertion — would ever catch that mismatch.)_
