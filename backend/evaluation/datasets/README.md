# evaluation/datasets

Datasets for the deterministic evaluation harness and for training the
**shadow-only** payment-failure-risk model (see `../../../docs/MODEL_CARD.md`).

| File | Rows | Size | In repo | Notes |
|---|---|---|---|---|
| `billing_recovery_v3.csv` | 3,601,892 | ~341 MB | **Git LFS** | The reference-model training set. Target `target_recovered`; chronological `split` column. Provenance: unverified / likely synthetic. Schema and construction in `dataset_manifest.json`. |
| `ar_recovery_v1.csv`, `ar_recovery_v2.csv` | small | ~250 KB | plain git | Accounts-receivable recovery scenarios. |
| `billing_recovery_v1.csv`, `v2.csv` | ~3–4 M | ~320–340 MB each | **excluded** | Superseded by v3 (v3 fixes selection bias). Regenerate from `scripts/legacy/phase16d_construct_v3.py` if needed. |
| `*_metadata.json`, `dataset_manifest.json` | — | small | plain git | Column lists, splits, SHA-256, transformation notes. |

## Getting the LFS file

```bash
git lfs install
git lfs pull                      # fetches billing_recovery_v3.csv
```

Cloning without Git LFS installed leaves `billing_recovery_v3.csv` as a small
pointer file; the rest of the project (app, 216 tests) does not need it — the
tests use tiny inline fixtures. Only `run_phase19_training.py` reads it.

> **Note on LFS quota.** GitHub's free tier allows 1 GiB of LFS storage and
> 1 GiB/month of bandwidth. A full fetch of `billing_recovery_v3.csv` uses
> ~341 MB of that monthly bandwidth.
