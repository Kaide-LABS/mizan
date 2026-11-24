# Phase 1 — Invariant & Intent Foundations + Crypto Config

## Goal
Stand up the crypto-era **locks and config**: (1) the full hard-invariant surface for spot-only crypto, boot-gated and test-proven undisablable; (2) the no-najsh order/intent model that makes "an order without intent to fill" structurally impossible; (3) the locked 14-token universe constant; (4) the configurable crypto fiqh register (each entry PENDING_SCHOLARLY_VERIFICATION with a citation); and (5) the two-speed roadmap documentation. No data fetching, no screening logic, no backtest, no report, no signal-adapter implementation.

## Scope
In scope: `mizan/config/invariants.py` (extend), `mizan/config/boot_check.py` (extend), new `mizan/execution/intent.py`, new `mizan/crypto/universe.py`, new `mizan/crypto/fiqh_register.py`, new `docs/crypto/` docs, and their tests. Out of scope: everything in "Out of scope for this phase" below.

Every new module: `from __future__ import annotations` where the repo uses it, full type annotations (`mypy --strict` clean), ruff-clean, module docstring citing `docs/crypto/PHASE_1_SPEC.md §…`. No new runtime dependency is added.

## Part A (first agent)

### A1. Extend the hard-invariant surface
**File:** `mizan/config/invariants.py` (edit).
- Add three fields to `Invariants`, each a fixed constant with a safe default, documented like the existing ones:
  - `spot_only: bool = True` — spot-only with immediate settlement.
  - `synthetic_exposure_allowed: bool = False` — no CFDs / synthetic price exposure.
  - `lending_or_yield_allowed: bool = False` — no lending or yield products.
- Do not change any existing field, default, or docstring meaning. Update the class docstring's "Seven fields, exactly" note to the new count (ten) and restate the rule that adding a field requires adding its check to `boot_check` in the same diff.
- `INVARIANTS` singleton remains constructed with zero args.

**File:** `mizan/config/boot_check.py` (edit `check_invariants`).
- Add three hand-written checks (same style as existing), appended to `violations`:
  - `if not inv.spot_only: violations.append("spot_only must be True")`
  - `if inv.synthetic_exposure_allowed: violations.append("synthetic_exposure_allowed must be False")`
  - `if inv.lending_or_yield_allowed: violations.append("lending_or_yield_allowed must be False")`
- No other behaviour changes.

Invariant → representation map (for the Part B tests): spot-only/immediate-settlement → `spot_only`; fully-funded/no-margin-leverage → `fully_funded`+`margin_allowed`; no-perps/futures/options → `derivatives_allowed`; no-CFD/synthetic → `synthetic_exposure_allowed`; no-lending/yield → `lending_or_yield_allowed`; CASH_YIELD=0 → `cash_yield`; no-najsh → `mizan/execution/intent.py` (A2).

### A2. The no-najsh order/intent model
**File:** `mizan/execution/__init__.py` (empty) and `mizan/execution/intent.py` (new).

Define (all models inherit `MizanBaseModel`):
- `class OrderSide(StrEnum): BUY = "buy"; SELL = "sell"`.
- `class RejectionReason(StrEnum)` — closed set: `SCREEN_REJECTED`, `NOT_IN_UNIVERSE`, `INSUFFICIENT_CASH`, `NO_LIQUIDITY`.
- `class FillResult(MizanBaseModel)`: `kind: Literal["fill"] = "fill"`; `filled_quantity: float = Field(gt=0.0)`; `fill_price: float = Field(gt=0.0)`. A fill moves a strictly positive quantity at a strictly positive price — a zero-quantity "fill" is not intent to fill and cannot be constructed.
- `class OrderRejection(MizanBaseModel)`: `kind: Literal["rejection"] = "rejection"`; `reason: RejectionReason`; `detail: str = Field(min_length=1)`.
- `class ResolvedOrder(MizanBaseModel)`: `side: OrderSide`; `ticker: str`; `requested_quantity: float = Field(gt=0.0)`; `outcome: FillResult | OrderRejection = Field(discriminator="kind")`. `outcome` has **no default** — a `ResolvedOrder` cannot exist without a terminal fill or rejection. There is no `status` field, no "pending/open/resting/cancelable" state, and no `cancel()` (or any mutation) method anywhere in this module. Use the `kind` discriminator (not Pydantic smart-union) to resolve the union, matching the repo's standing stance against unspecified union resolution.
- `class NoIntentToFillError(RuntimeError)`.
- Factory `def place_order(*, side: OrderSide, ticker: str, requested_quantity: float, fill: FillResult | None = None, rejection: OrderRejection | None = None) -> ResolvedOrder:` — exactly one of `fill`/`rejection` must be non-`None`; if both are `None` **or** both are set, raise `NoIntentToFillError` with a message naming the violation. Otherwise return `ResolvedOrder(side=..., ticker=..., requested_quantity=..., outcome=<the non-None one>)`.

Module docstring must state the structural no-najsh argument: because the only way to hold an order is via a terminal `outcome`, and no cancelable/resting type exists, an order placed without intent to fill has no representation for the current backtest layer or any future HFT layer.

### A3. The locked crypto universe
**File:** `mizan/crypto/__init__.py` (empty) and `mizan/crypto/universe.py` (new).
- `CRYPTO_UNIVERSE: tuple[str, ...] = ("BTC", "LTC", "BCH", "ETH", "SOL", "ADA", "AVAX", "DOT", "NEAR", "ATOM", "ALGO", "XRP", "XLM", "LINK")` — exactly these 14, in PRD order.
- `CRYPTO_UNIVERSE_SET: frozenset[str] = frozenset(CRYPTO_UNIVERSE)`.
- Module-level assertion that `len(CRYPTO_UNIVERSE) == 14` and `len(CRYPTO_UNIVERSE_SET) == 14` (no duplicates).
- Exchange/product symbol mapping (e.g. `BTC-USD`) is **not** defined here — deferred to Phase 2.

### A4. The crypto fiqh register
**File:** `mizan/crypto/fiqh_register.py` (new). Reuse `from mizan.config.fiqh_params import FiqhParam, VerificationStatus`.
- `class CustodyModel(StrEnum): EXCHANGE_QABD_HUKMI = "exchange_qabd_hukmi"; SELF_CUSTODY = "self_custody"`.
- `class CryptoFiqhParams(MizanBaseModel)` with four `FiqhParam[...]` fields (register_ids 1–4), each `status=PENDING_SCHOLARLY_VERIFICATION` (the `FiqhParam` default), `configurable=True`, non-empty `source` citing the fiqh basis:
  1. `stablecoins_allowed: FiqhParam[bool]` = value `True`; source cites islamqa.info Q504160 and states "USDC is the cash leg, yield 0; Coinbase 'USDC rewards' never modelled".
  2. `staking_rewards_enabled: FiqhParam[bool]` = value `False`; source states "disputed; default OFF" and references Q106094/Q125758/Q310956.
  3. `custody_model: FiqhParam[CustodyModel]` = value `EXCHANGE_QABD_HUKMI`; source states "exchange custody accepted as qabd hukmi for V1"; non-empty `primary_source_gap` stating FTX-type failure and freeze risk are caveated-not-modelled and self-custody is the long-term target.
  4. `memecoin_exclusion_enabled: FiqhParam[bool]` = value `True`; source states "maysir/gharar; default excluded; parameter".
  - `@model_validator(mode="after")` asserting register_ids are exactly `{1,2,3,4}` with no duplicates (mirror the equity register's validator).
- `CRYPTO_FIQH_PARAMS = CryptoFiqhParams()` singleton.

### A5. Wire the crypto register into boot
**File:** `mizan/config/boot_check.py` (edit).
- Add `def check_crypto_fiqh_register(params: CryptoFiqhParams | None = None) -> None:` (reuse `FiqhRegisterError`; `params` defaults to `CRYPTO_FIQH_PARAMS`, parameter exists for tests only). Checks: exactly 4 entries; register_ids exactly `{1..4}`; every entry's `source` non-empty; every entry's `status is PENDING_SCHOLARLY_VERIFICATION`; every entry's `configurable is True`; entry #3 (`custody_model`) has a non-empty `primary_source_gap`. Raise `FiqhRegisterError` listing all problems.
- Add the call to `check_all()` after `check_fiqh_register()`. Import `CryptoFiqhParams`/`CRYPTO_FIQH_PARAMS` inside the function body if a top-level import would create a cycle (mirror existing patterns); otherwise top-level is fine.

### A6. Part-A smoke tests (so Part A commits with green tests)
**Files:** `tests/test_crypto_universe.py`, `tests/test_execution_intent.py` (happy path only), `tests/test_crypto_fiqh_register.py` (happy path only), and extend `tests/test_invariants.py` minimally for the three new default values.
- Universe: 14 members, no duplicates, exact tuple equality to the PRD order.
- Intent happy path: `place_order(..., fill=FillResult(filled_quantity=1.0, fill_price=100.0))` returns a `ResolvedOrder` whose `outcome.kind == "fill"`; `place_order(..., rejection=OrderRejection(reason=RejectionReason.NO_LIQUIDITY, detail="x"))` returns `outcome.kind == "rejection"`.
- Crypto register happy path: `check_crypto_fiqh_register()` does not raise; `CRYPTO_FIQH_PARAMS` has 4 entries with ids `{1,2,3,4}`.
- Invariants defaults: `Invariants().spot_only is True`, `synthetic_exposure_allowed is False`, `lending_or_yield_allowed is False`; `check_invariants()` still passes on the singleton.

**Part A done when:** all modules import, `mypy --strict` and `ruff` pass, `mizan-boot-check` exits 0 with crypto checks wired in, and the Part-A smoke tests pass.

## Part B (second agent)
Depends on Part A's committed modules. Delivers the edge cases, the per-invariant proofs, error handling, integration, and docs.

### B1. One test per hard invariant (AC 9)
**File:** `tests/test_hard_invariants.py` (new). One clearly-named test per PRD hard invariant, each proving the invariant cannot be disabled via config/flag by constructing a deliberately-violating `Invariants(...)` (the one sanctioned non-default construction, test-only) and asserting `check_invariants(violating)` raises `InvariantViolationError` matching the field name:
- `test_spot_only_cannot_be_disabled` → `Invariants(spot_only=False)`.
- `test_no_margin_or_leverage_cannot_be_disabled` → `Invariants(margin_allowed=True)` and `Invariants(fully_funded=False)` (both rejected).
- `test_no_perps_futures_options_cannot_be_disabled` → `Invariants(derivatives_allowed=True)`.
- `test_no_cfd_synthetic_exposure_cannot_be_disabled` → `Invariants(synthetic_exposure_allowed=True)`.
- `test_no_lending_or_yield_cannot_be_disabled` → `Invariants(lending_or_yield_allowed=True)`.
- `test_cash_yield_is_zero_and_cannot_be_disabled` → `Invariants(cash_yield=0.01)`.
- `test_invariants_singleton_is_frozen_and_rejects_unknown_field` → mutating `INVARIANTS.spot_only` and `Invariants(bogus=1)` both raise `ValidationError` (proves no runtime/config switch exists).
- `test_invariants_field_count_is_locked_at_ten` — update/replace the equity-era seven-field assertion to ten; comment that an eleventh requires a matching `boot_check` change.
Also update `tests/test_invariants.py`'s existing field-count and default-values tests to the new ten-field reality (surfaced edit).

### B2. No-najsh edge cases (AC 10, and the 7th invariant of AC 9)
**File:** `tests/test_execution_intent.py` (extend).
- `test_order_without_intent_to_fill_is_rejected`: `place_order(side=OrderSide.BUY, ticker="BTC", requested_quantity=1.0)` (both `fill` and `rejection` `None`) raises `NoIntentToFillError`.
- `test_order_cannot_be_both_filled_and_rejected`: passing both raises `NoIntentToFillError`.
- `test_resolved_order_requires_an_outcome`: constructing `ResolvedOrder(side=..., ticker=..., requested_quantity=1.0)` with no `outcome` raises `ValidationError`.
- `test_zero_or_negative_fill_is_not_intent_to_fill`: `FillResult(filled_quantity=0.0, fill_price=100.0)` and `FillResult(filled_quantity=1.0, fill_price=0.0)` each raise `ValidationError`.
- `test_no_cancelable_or_resting_order_type_exists`: assert `ResolvedOrder` has no `cancel` attribute and no field named `status`/`pending`/`open`/`resting` (introspect `model_fields` and `dir`), and that `ResolvedOrder` is frozen (mutating a field raises `ValidationError`).
- `test_rejection_requires_a_reason_detail`: `OrderRejection(reason=..., detail="")` raises `ValidationError`.

### B3. Crypto fiqh register honesty (AC 8)
**File:** `tests/test_crypto_fiqh_register.py` (extend).
- `test_every_entry_is_pending_scholarly_verification`: every entry `status is VerificationStatus.PENDING_SCHOLARLY_VERIFICATION`.
- `test_every_entry_has_nonempty_source` and `test_every_entry_is_configurable`.
- `test_custody_entry_states_freeze_risk_unmodelled`: entry #3's `primary_source_gap` mentions freeze/failure risk and self-custody target (substring checks).
- `test_register_ids_are_exactly_one_to_four`.
- `test_check_rejects_blanked_source`: `model_copy`-blank a `source`, assert `check_crypto_fiqh_register(broken)` raises `FiqhRegisterError` matching "source".
- `test_check_rejects_status_drift`: `model_copy` an entry to a drifted status string, assert it raises.
- Default-values test asserting stablecoins allowed, staking OFF, custody `EXCHANGE_QABD_HUKMI`, memecoin exclusion ON.

### B4. Boot integration (end-to-end of the gate)
**File:** `tests/test_boot_crypto_integration.py` (new).
- `test_check_all_runs_crypto_register`: `check_all()` does not raise; monkeypatch `CRYPTO_FIQH_PARAMS` (or pass a broken register through a thin seam) to prove `check_all()` surfaces a crypto register break as a non-zero `main()` exit on stderr in the existing `FiqhRegisterError` format.
- `test_mizan_boot_check_cli_passes`: invoking `boot_check.main()` returns 0 and prints the pass message (crypto checks included).

### B5. Documentation (AC 15)
- `docs/crypto/ROADMAP.md`: the two-speed system, documented, built now by nobody. Slow layer = gods-eye-view + Agent-Reach + MiroFish + Inkling 2 Small (predicts events/reactions; sets which tokens, direction long/flat-only, size limits). Fast layer = spot-only HFT execution on intraday/order-book data with TimesFM short-horizon forecasts, acting only within slow-layer limits and all hard invariants incl. no-najsh. Later phases: intraday ingestion, order-book data, adapter implementations, paper trading, then self-custody/live. State explicitly that **none of this is built in V1**.
- `docs/crypto/ARCHITECTURE.md`: the Phase 1 architecture — the single extended `Invariants` boundary + `boot_check` gate, the structural no-najsh `ResolvedOrder`, the reuse-vs-park map, and the clean signal-adapter seam (contract only, Phase 5). Reference the CONTEXT "Planned architecture".
- `docs/crypto/PHASE_1_SPEC.md`: commit this spec as the governing document the new module docstrings cite.
- Update the repo `README` with a short "Crypto pivot (V1)" section: what is locked, that it is research/backtest-only, and `mizan-boot-check` as the one command that proves the boundary holds today.

### B6. No forbidden code built (AC 15 constraint)
- Add/confirm a check (test or documented grep in `ARCHITECTURE.md`) that no HFT, live-trading, exchange-API-key, or signal-adapter implementation module exists under `mizan/` after Phase 1. `mizan/execution/intent.py` is the only execution-layer code and contains no live-order or network capability.

**Part B done when:** all Part-A + Part-B tests pass, `mypy --strict`/`ruff` clean, `mizan-boot-check` exits 0, and the three `docs/crypto/` files + README section exist.

## Acceptance-criteria mapping (Phase 1)
| AC | Satisfied by | Concrete check |
|----|--------------|----------------|
| 8 — fiqh register labelled PENDING_SCHOLARLY_VERIFICATION | A4, A5, B3 | `tests/test_crypto_fiqh_register.py::test_every_entry_is_pending_scholarly_verification` passes; `check_crypto_fiqh_register` rejects status drift. |
| 9 — one test per hard invariant, undisablable | A1, A2, B1, B2 | `tests/test_hard_invariants.py` has one passing test per the six config invariants (each asserts `check_invariants` rejects the flip) + the no-najsh test in B2; field count locked at ten. |
| 10 — no-najsh at order/intent level; rejects order with no intent to fill | A2, B2 | `test_order_without_intent_to_fill_is_rejected`, `test_resolved_order_requires_an_outcome`, `test_no_cancelable_or_resting_order_type_exists` all pass. |
| 15 — two-speed roadmap documented; no HFT/live/adapter code built | B5, B6 | `docs/crypto/ROADMAP.md` present with slow/fast layers + later phases; B6 check confirms no adapter/HFT/live/key implementation module exists. |
| 4, 1, 2, 3, 5, 6, 7, 11, 12, 13, 14 | Phases 2–6 (see CONTEXT phase plan) | Not in Phase 1 scope. |

## Documentation sources
- PEP 544 – Protocols (adapter/strategy seam pattern reused): https://peps.python.org/pep-0544/
- The Newtype and Type-State Patterns (structural "illegal states unrepresentable" basis for `ResolvedOrder`): https://microsoft.github.io/RustTraining/rust-patterns-book/ch03-the-newtype-and-type-state-patterns.html
- CFTC Final Interpretive Guidance on Disruptive Practices (intent-to-fill / anti-spoofing standard the no-najsh model encodes): https://www.cftc.gov/LawRegulation/FederalRegister/FinalRules/2013-12365.html
- QuantConnect Trade Fills — Key Concepts (backtests assume complete fills, no cancelable resting state): https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts

## Out of scope for this phase
- Any data fetching (Coinbase/Kraken), the DuckDB `candles` table, the raw cache, and the 24/7 market clock (Phase 2).
- Per-token business-activity verdict map, written per-token reasons, and the default-reject reasons (Phase 3).
- The baseline backtest, fees/slippage, rebalance cadence wiring (Phase 4).
- Any signal-adapter implementation; the `typing.Protocol` contract and validation-gate spec (Phase 5).
- The HTML report and the single end-to-end pipeline command (Phase 6).
- Deleting or modifying parked equity modules or their EDGAR/AAOIFI/SIC code; changing the equity `FiqhParams` register.
- Exchange/product symbol mapping, API keys, live trading, and any HFT code.

## Spec assumptions

Gaps found while writing this spec were resolved as follows (nobody was asked):

- The whole pivot is 6 build phases (P1 invariant+intent foundations & crypto config; P2 crypto ingestion + 24/7 clock + candles store; P3 token screening; P4 baseline backtest with fees/slippage; P5 signal-adapter seam; P6 HTML report + single pipeline command).
- "Reuse as-is: invariants module" is read as reuse-and-extend under the module's own documented rule ("adding a field requires adding its check to boot_check in the same diff"): Phase 1 adds three crypto hard-invariant fields and three hand-written checks; no existing field, default, or meaning changes; the existing field-count test is updated in the same change (a surfaced edit, not a silent one).
- The crypto fiqh register is a NEW model (`CryptoFiqhParams`) separate from the parked equity `FiqhParams`, reusing the existing `FiqhParam[T]` generic and `VerificationStatus` enum. The equity AAOIFI register stays unchanged and parked.
- No-najsh is enforced structurally with a frozen Pydantic "smart-constructor" order type (`ResolvedOrder`) whose only outcome is a terminal fill OR a reasoned rejection (a discriminated union, mandatory, no default); there is no pending/resting/cancelable order type and no `cancel()` anywhere, so "an order without intent to fill" has no representation. A `place_order(...)` factory requires exactly one of `fill`/`rejection`.
- A fill requires strictly positive filled quantity and fill price; a zero-quantity "fill" is not intent to fill and is rejected at construction.
- Phase 1 locks the 14-token universe constant and the four configurable crypto register parameters (stablecoins, staking, custody, memecoin-exclusion); the per-token business-activity verdict map and the default-reject reasons (AAVE/COMP/MKR, BNB/OKB/CRO, DOGE/SHIB/PEPE) are Phase 3 (screening), which consumes this universe (AC 4 maps to P3).
- The 24/7 market clock and moving the equity trading-day calendar off the default path (AC 13) are Phase 2; equity modules already import, so AC 14 is satisfied progressively and verified end-to-end in Phase 6.
- New crypto code lives under `mizan/crypto/` and `mizan/execution/`; new crypto docs under `docs/crypto/`; new tests are added flat in `tests/` to match repo convention (`testpaths = ["tests"]`).
- New crypto modules cite `docs/crypto/PHASE_1_SPEC.md §…` in their docstrings to avoid confusion with the parked equity phase-spec references.
- `duckdb` stays pinned at the repo's `1.5.5` (reuse-as-is); any bump is re-verified and logged in Phase 2. The unconfirmed "DuckDB 2.0.1" claim is not relied upon.
- `CustodyModel` defines `EXCHANGE_QABD_HUKMI` (V1 default) and `SELF_CUSTODY` (the PRD's declared long-term target); the self-custody path is not implemented in V1.
- boot_check reuses `FiqhRegisterError` for the crypto register; `check_all()` runs the crypto register check in addition to the existing checks, so every CLI entrypoint already gates on it.

## Implications

Second-order consequences found by an independent review of this spec. This section only adds to the spec; the locked PRD is unchanged.

### Additional acceptance criteria

S1. A test enumerates every public class defined in `mizan.execution` (not just `ResolvedOrder`) and asserts none exposes a `cancel`/`amend`/mutation method nor a field named `status`/`pending`/`open`/`resting`/`cancelable`; adding any such type to the execution layer makes this test fail. _(security: AC 10 / B2 proves no-najsh only by introspecting the single `ResolvedOrder` class. Nothing fails if a later edit (even in Phase 1's own `mizan/execution/`) adds a *second* class with a `cancel()`/`amend()` method or a `pending`/`open`/`resting` status field. The whole no-najsh invariant — explicitly meant to be inherited by the future HFT layer — would then erode with a green test suite, because the guard is scoped to one type, not the module.)_
S2. The complete pre-existing equity test suite still passes after the invariant extension, with the only edited equity tests being the surfaced field-count (7→10) and default-value assertions in `tests/test_invariants.py`; no equity logic/behaviour test is modified to accommodate the new fields. _(maintenance: The spec grows the shared `Invariants` singleton from 7 to 10 fields rather than creating a separate crypto model. `MizanBaseModel` is `extra='forbid'` and frozen, so any pre-existing equity test, golden report, or serialized artifact that dumps/compares the `Invariants` shape silently changes. AC 14 only guarantees equity modules still *import* — it does not guarantee the equity test suite still passes, which is where a shape-dependent break would surface.)_

### Noted, no action

- Monetary quantity/price are `float` by design in Phase 1; flag for Phase 4 whether fee/slippage accumulation over rebalances needs Decimal/rounding discipline before the figure is reported as authoritative. _(data)_

## Red-team findings

Weaknesses found by an adversarial review of this spec before it is built. This section only adds to the spec; the locked PRD is unchanged.

### Additional acceptance criteria

R1. A test proves the hard invariants are independent of and dominate the configurable register: for every CryptoFiqhParams configuration including staking_rewards_enabled=True, INVARIANTS.cash_yield remains 0 and lending_or_yield_allowed remains False, and check_invariants still rejects any attempt to derive nonzero yield from an enabled register parameter. _(high, fiqh-invariant: CASH_YIELD=0 and lending_or_yield_allowed=False are locked hard invariants, yet CryptoFiqhParams exposes configurable staking_rewards_enabled (A4 #2) — and staking rewards ARE a yield product. Phase 1 builds no link between the two surfaces; boot_check validates them independently. A later phase or config that flips staking_rewards_enabled=True to model rewards would generate yield while the locked invariant and the judge-facing register still report 'no lending or yield'. The configurable register becomes a side door around a hard invariant, and nothing fails.)_
R2. A test asserts that every field of Invariants is referenced by name in check_invariants (introspecting model_fields against the check source), so adding any new field without a corresponding boot-gate check fails the suite — replacing the mere count==10 assertion as the AC 9 guard. _(high, fiqh-invariant: AC 9's guarantee that no permissibility field escapes the boot gate rests on test_invariants_field_count_is_locked_at_ten (B1), which only asserts len==10. A later edit adding an 11th permissive field (e.g. defaulting True) need only bump the assertion to 11; nothing forces a matching check_invariants entry, so the new permissive default is never gated. The 'adding a field requires adding its check' rule is a docstring comment, not a test — the cheapest path to a silently-disablable invariant with a fully green suite.)_
R3. check_crypto_fiqh_register verifies each entry's source contains its governing fatwa identifier(s) (Q504160 for stablecoins/custody; Q106094/Q125758/Q310956 for staking), not merely that the source is non-empty; a test blanks or wrong-numbers a citation and asserts FiqhRegisterError matching 'source'. _(medium, data-provenance: check_crypto_fiqh_register only requires each entry's source to be non-empty (A5/B3). A source of 'see docs', a wrong fatwa number, or a copy-paste typo passes the honesty gate and is rendered to a non-technical grant judge as a verified citation. Mizan's entire claim is that its ethics are verifiable-not-promised, so an unchecked citation string is exactly the quiet failure: a caveat/citation that exists but does not actually name the governing basis.)_
R4. ResolvedOrder/place_order rejects any FillResult whose filled_quantity exceeds requested_quantity (overfill is not intent to fill); a test asserts construction with filled_quantity > requested_quantity raises ValidationError or NoIntentToFillError. _(medium, najsh: FillResult requires filled_quantity>0 and place_order requires exactly one of fill/rejection, but nothing constrains filled_quantity relative to ResolvedOrder.requested_quantity. An order requesting 1.0 can carry a FillResult of 1000.0 and still construct cleanly. Defined now, this seam lets the Phase 4 backtest (and the future HFT layer that inherits this type) fabricate positions that never happened — results that look good for the wrong reasons, with no overfill check anywhere.)_
