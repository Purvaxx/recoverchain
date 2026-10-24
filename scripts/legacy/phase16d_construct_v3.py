"""
Phase 16D Execution — billing_recovery_v3 construction.

Resolution: AGGREGATE TARGET (Option 2 from Phase 16D report)

For conflicting subscriber-months:
  If ANY row has payment_status in {Failed, Unpaid}, target_recovered = 0
  If ALL rows have payment_status in {Paid On Time, Paid Late}, target_recovered = 1

This is the conservative approach:
  - No data discarded
  - All failure events captured
  - Selection bias eliminated
  - Adds label noise for cases where failure was followed by correction,
    but this is appropriate for a recovery-risk model (the failure DID occur)

NO MODEL TRAINING.
"""
import pandas as pd
import numpy as np
import json
import os

OUTPUT_DIR = "backend/evaluation/datasets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 80)
print("BILLING_RECOVERY_V3 CONSTRUCTION")
print("=" * 80)

raw = pd.read_csv("dataset/billing.csv", low_memory=False)
print(f"Raw rows: {len(raw)}")

# Step 1: Drop exact duplicate rows
before = len(raw)
raw = raw.drop_duplicates()
print(f"After exact dedup: {len(raw)} (dropped {before - len(raw)})")

# Step 2: For each subscriber-month, determine AGGREGATE outcome
# Rule: if ANY row for this (subscriber, month) has Failed or Unpaid, target = 0
# This captures all failure events, even if another row shows recovery.
sm_has_failure = raw.groupby(['subscriber_id', 'year_month'])['payment_status'].apply(
    lambda x: x.isin(['Failed', 'Unpaid']).any()
).rename('has_any_failure')

# Step 3: For features, keep the row with the HIGHEST total_billed_usd per subscriber-month
# (representing the most complete/corrected billing record)
billing = raw.sort_values('total_billed_usd', ascending=False)\
    .drop_duplicates(subset=['subscriber_id', 'year_month'], keep='first')\
    .sort_values(['subscriber_id', 'year_month'])\
    .reset_index(drop=True)

print(f"After subscriber-month dedup: {len(billing)}")

# Step 4: Apply AGGREGATE target
billing = billing.join(sm_has_failure, on=['subscriber_id', 'year_month'])
billing['target_recovered'] = (~billing['has_any_failure']).astype(int)
billing = billing.drop(columns=['has_any_failure'])

print(f"\nTarget distribution:")
print(billing['target_recovered'].value_counts())
print(billing['target_recovered'].value_counts(normalize=True).round(4))

# Step 5: Construct features (same as v2)
billing['bill_amount_excl_late'] = (
    billing['base_charge_usd'] + billing['data_overage_usd'] +
    billing['intl_roaming_usd'] + billing['tax_usd']
)

billing['bill_seq'] = billing.groupby('subscriber_id').cumcount()
billing['is_failed'] = (billing['payment_status'] == 'Failed').astype(int)
billing['is_unpaid'] = (billing['payment_status'] == 'Unpaid').astype(int)
billing['is_late'] = (billing['payment_status'] == 'Paid Late').astype(int)
billing['is_ontime'] = (billing['payment_status'] == 'Paid On Time').astype(int)

# IMPORTANT: history features use the AGGREGATE target, not per-row status
# This ensures history reflects whether each prior month had ANY failure
billing['prior_nonrec'] = billing.groupby('subscriber_id')['target_recovered'].apply(
    lambda x: (1 - x).cumsum() - (1 - x)
).reset_index(level=0, drop=True)

billing['prior_failures'] = billing.groupby('subscriber_id')['is_failed'].cumsum() - billing['is_failed']
billing['prior_unpaid'] = billing.groupby('subscriber_id')['is_unpaid'].cumsum() - billing['is_unpaid']
billing['prior_late'] = billing.groupby('subscriber_id')['is_late'].cumsum() - billing['is_late']
billing['prior_ontime'] = billing.groupby('subscriber_id')['is_ontime'].cumsum() - billing['is_ontime']
billing['prior_nonrecovery_count'] = billing['prior_nonrec']
billing['prior_nonrecovery_rate'] = billing['prior_nonrecovery_count'] / billing['bill_seq'].replace(0, np.nan)
billing['prior_late_rate'] = billing['prior_late'] / billing['bill_seq'].replace(0, np.nan)
billing['prior_cumulative_amount'] = billing.groupby('subscriber_id')['bill_amount_excl_late'].cumsum() - billing['bill_amount_excl_late']
billing['prior_avg_amount'] = billing['prior_cumulative_amount'] / billing['bill_seq'].replace(0, np.nan)
billing['has_overage'] = (billing['data_overage_usd'] > 0).astype(int)
billing['has_roaming'] = (billing['intl_roaming_usd'] > 0).astype(int)

feature_cols = [
    'bill_amount_excl_late', 'base_charge_usd', 'data_overage_usd',
    'intl_roaming_usd', 'tax_usd', 'has_overage', 'has_roaming',
    'bill_seq', 'prior_failures', 'prior_unpaid', 'prior_late',
    'prior_ontime', 'prior_nonrecovery_count', 'prior_nonrecovery_rate',
    'prior_late_rate', 'prior_avg_amount',
]

meta_cols = ['subscriber_id', 'year_month']
output_cols = meta_cols + feature_cols + ['target_recovered']
billing_out = billing[output_cols].copy()

for col in ['prior_nonrecovery_rate', 'prior_late_rate', 'prior_avg_amount']:
    billing_out[col] = billing_out[col].fillna(-1)

# Temporal split
billing_out['split'] = 'train'
billing_out.loc[billing_out['year_month'].isin(['2026-01', '2026-03']), 'split'] = 'validation'
billing_out.loc[billing_out['year_month'].isin(['2026-04', '2026-05']), 'split'] = 'test'

print(f"\nFinal billing v3 shape: {billing_out.shape}")
print(f"\nTemporal split stats:")
split_stats = billing_out.groupby('split')['target_recovered'].agg(['count', 'mean'])
print(split_stats.round(4))
print(f"\nNulls: {billing_out.isnull().sum().sum()}")
print(f"Duplicate subscriber-months: {billing_out.duplicated(subset=['subscriber_id', 'year_month']).sum()}")

# Verify history temporal correctness
first_obs = billing_out[billing_out['bill_seq'] == 0]
assert (first_obs['prior_failures'] == 0).all(), "First obs prior_failures not 0!"
assert (first_obs['prior_nonrecovery_rate'] == -1).all(), "First obs rate not -1!"
print("\nHistory temporal correctness: PASSED")

billing_out.to_csv(os.path.join(OUTPUT_DIR, "billing_recovery_v3.csv"), index=False)
print(f"\nSaved billing_recovery_v3.csv ({len(billing_out)} rows)")

# Metadata
meta = {
    "dataset_version": "recoverchain-billing-recovery-v3",
    "source_file": "dataset/billing.csv",
    "source_sha256": "9615a50e653bf075988efd8642bc44e5ff06c3e31bbf00336469b9dfd488244e",
    "provenance": "UNKNOWN — appears synthetic telecom billing data",
    "training_unit": "subscriber-month billing obligation",
    "unit_identifier": "subscriber_id + year_month",
    "prediction_timestamp": "Start of billing month (year_month). Model sees subscriber history and current charges.",
    "deduplication_rule": "1) Drop exact row duplicates. 2) For each subscriber-month, if ANY row has Failed/Unpaid status, target = 0. 3) Keep row with highest total_billed_usd for feature values.",
    "target_column": "target_recovered",
    "target_definition": "1 = ALL rows for this subscriber-month had Paid On Time or Paid Late. 0 = ANY row for this subscriber-month had Failed or Unpaid.",
    "target_semantics": "Per-month billing cycle outcome. If a failure event occurred at any point during this billing cycle (even if later corrected), target = 0. This is conservative and captures all revenue-risk events.",
    "target_caveat": "89% of subscribers with Failed/Unpaid status in any month later show successful payment in subsequent months. The target captures per-cycle payment failures, which are mostly temporary in this dataset.",
    "row_count": int(len(billing_out)),
    "features": feature_cols,
    "excluded_leakage": ["payment_status", "days_to_payment", "late_fee_usd", "total_billed_usd"],
    "class_distribution": {
        "recovered": int(billing_out['target_recovered'].sum()),
        "not_recovered": int((billing_out['target_recovered'] == 0).sum()),
        "recovery_rate": round(float(billing_out['target_recovered'].mean()), 4)
    },
    "temporal_split": {
        "train": {"period": "2025-07 to 2025-12", "rows": int(split_stats.loc['train', 'count']), "recovery_rate": round(float(split_stats.loc['train', 'mean']), 4)},
        "validation": {"period": "2026-01 to 2026-03", "rows": int(split_stats.loc['validation', 'count']), "recovery_rate": round(float(split_stats.loc['validation', 'mean']), 4)},
        "test": {"period": "2026-04 to 2026-05", "rows": int(split_stats.loc['test', 'count']), "recovery_rate": round(float(split_stats.loc['test', 'mean']), 4)}
    },
    "entity_leakage": "Nearly 100% subscriber overlap across splits — model forecasts existing subscribers",
    "selection_bias": "RESOLVED — v3 includes ALL subscriber-months (no conflicting records excluded)",
    "provenance_status": "UNKNOWN"
}

with open(os.path.join(OUTPUT_DIR, "billing_recovery_v3_metadata.json"), "w") as f:
    json.dump(meta, f, indent=2)

print("Metadata written.")
print("\nDONE — No models trained.")
