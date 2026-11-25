# Validation-Gate Specification

Governing spec: `docs/crypto/PHASE_5_SPEC.md` §B4. This document is prose/specification
only — it states what a future adapter-implementing phase must build and measure before a
signal may drive allocations. It builds none of it now; `mizan/signal/validation_gate.py`'s
`ValidationGateSpec`/`GateCriteria` are its typed, testable companion, not a replacement for
this prose.

A signal must pass every one of the following before `require_passing_gate` lets it drive
allocations:

1. **Leakage-safe out-of-sample evaluation.** Walk-forward split at minimum, with
   purged/embargoed or combinatorial-purged cross-validation where resourcing allows — never
   ordinary shuffled k-fold, which can report a spuriously high R² on a target that is
   provably unpredictable.
2. **Calibration reported as a reliability diagram / PIT histogram, never a Brier score
   alone.** Brier conflates calibration loss and refinement loss (scikit-learn's own
   documented caveat).
3. **Per-token and per-regime error breakdown, each as separate rows, not only in
   aggregate.** An aggregate-looking improvement can collapse to near-zero statistical
   significance once broken out per asset.
4. **Beats both a naive last-value baseline and zero-shot TimesFM, via a one-sided
   Diebold-Mariano significance test on forecast errors** — not a smaller point-metric alone.
   Pretrained time-series foundation models, including TimesFM, frequently fail to clear even
   a plain random-walk null on financial return series, so the bar is genuine.
5. **Reference model pin.** The pinned TimesFM reference checkpoint is
   `google/timesfm-2.5-200m-pytorch` (Apache-2.0 weights, `pip install timesfm[torch]`), not
   TimesFM 3.0 (whose self-hosted weights carry a non-commercial-only licence) — matching
   fatwa part 2's "every data source must be public or licensed for this use" constraint,
   extended to the reference model's own weight licence. TimesFM's own quantile heads are
   explicitly **not** used as the calibrated-probability source for this gate (Google's own
   TimesFM-2.0 model card states those heads "have not been calibrated after pretraining") —
   calibration must be measured independently against realised price.

No concrete measurement, CRPS/pinball scoring, Diebold-Mariano test, or purged/CPCV
cross-validation code exists yet in this repo. `GateCriteria`'s six boolean fields are
caller-attested placeholders a future phase must populate honestly from a real backtest and a
real TimesFM/naive comparison.
