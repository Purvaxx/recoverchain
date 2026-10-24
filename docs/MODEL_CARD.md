# Model Card — Payment Failure Risk (shadow)

## Status: SHADOW-ONLY / ADVISORY

This model's output is **telemetry only**. It never authorizes, gates, or
triggers a recovery action — the deterministic `DeterministicPolicyEngine` is the
sole authority (`shadow_mode_active: true` is hard-coded in the predictor).

## Intended use

Estimate `P(payment failure)` for a case at decision time so operators can
prioritise. The complement (`1 - failure_prob`) is surfaced as a recovery
probability and feeds the *ranking only* of candidate actions / expected
recoverable value — not the policy decision.

## Training

| | |
|---|---|
| Script | `backend/run_phase19_training.py` → `application/ml_training.py` (`MLTrainingEngine`) |
| Dataset | `backend/evaluation/datasets/billing_recovery_v3.csv` (3,601,892 rows) |
| Provenance | **UNKNOWN — likely synthetic** (see `dataset_manifest.json`) |
| Target | `target_recovered` (inverted to model *failure* risk) |
| Features | 15 billing / prior-history columns (see manifest `features`) |
| Split | temporal, `split` column — train `2025-07..12`, val `2026-01..03`, test `2026-04..05` |
| Algorithms | LogisticRegression + XGBoost in an sklearn `Pipeline`; best by validation PR-AUC |
| Excluded (leakage) | `payment_status`, `days_to_payment`, `late_fee_usd`, `total_billed_usd` |

## Quality gate

`MLTrainingEngine` refuses to mark a model `SELECTED` unless
`test ROC-AUC ≥ ML_MIN_ROC_AUC` (default 0.55) and
`test rows ≥ ML_MIN_TEST_ROWS` (default 200). Failing models are written with
`status: REJECTED_LOW_QUALITY` and `MLPaymentFailurePredictor` will not load them
(`predict_failure_risk` → `NO_MODEL`, and the pipeline falls back to
`DeterministicBaselinePredictor`).

## Known limitations

- **Target is per-month billing-failure risk, not permanent non-recovery** — the
  manifest notes ~89% of failures later recover.
- **~16:1 class imbalance** — evaluate with PR-AUC / F1, never raw accuracy.
- **Temporal distribution shift** present and realistic (non-failure rate
  95.2% train → 93.0% test).
- **Entity overlap** across splits (352k subscribers) — the model forecasts the
  next outcome for *existing* subscribers, not cold-start.
- Provenance unverified; do not treat calibrated probabilities as production-grade.

## Reproduce

```bash
cd backend && set PYTHONPATH=.
python run_phase19_training.py      # writes ml/models/registry/train_<ts>_{model.joblib,metadata.json}
```
