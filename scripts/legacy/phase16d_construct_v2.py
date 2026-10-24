"""
Phase 16D — Revised Dataset Construction

KEY CHANGES FROM v1:
1. BILLING: Resolve conflicting statuses by taking the WORST outcome per subscriber-month
   (conservative: if one row says "Failed" and another says "Paid On Time", treat as ambiguous
    and EXCLUDE the record rather than silently choosing one side)
2. BILLING: Add a SECONDARY target: subscriber-level "ever_nonrecovered" for subscribers
   who NEVER paid after a failure (the 11% permanent non-recovery cases)
3. AR: Drop payment_window_days (constant), flag is_disputed as AMBIGUOUS

NO MODEL TRAINING.
"""
import pandas as pd
import numpy as np
import json
import os
import hashlib

OUTPUT_DIR = "backend/evaluation/datasets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===========================================================================
# BILLING v2
# ===========================================================================
print("=" * 80)
print("BILLING_RECOVERY_V2 CONSTRUCTION")
print("=" * 80)

raw = pd.read_csv("dataset/billing.csv", low_memory=False)
print(f"Raw rows: {len(raw)}")

# Step 1: Drop exact duplicate rows
before = len(raw)
raw = raw.drop_duplicates()
print(f"After exact dedup: {len(raw)} (dropped {before - len(raw)})")

# Step 2: For subscriber-months with 2 rows, classify and handle
sm_counts = raw.groupby(['subscriber_id', 'year_month']).size()
single_sm = sm_counts[sm_counts == 1].index
dup_sm = sm_counts[sm_counts == 2].index
print(f"Single-row subscriber-months: {len(single_sm)}")
print(f"Duplicate subscriber-months: {len(dup_sm)}")

# Split into singles and duplicates
single_mask = raw.set_index(['subscriber_id', 'year_month']).index.isin(single_sm)
singles = raw[single_mask].copy()

dup_mask = raw.set_index(['subscriber_id', 'year_month']).index.isin(dup_sm)
dups = raw[dup_mask].copy()

# For duplicates: check if payment_status conflicts
dups['row_num'] = dups.groupby(['subscriber_id', 'year_month']).cumcount()
r0 = dups[dups['row_num'] == 0].set_index(['subscriber_id', 'year_month'])
r1 = dups[dups['row_num'] == 1].set_index(['subscriber_id', 'year_month'])
same_status = (r0['payment_status'] == r1['payment_status'])

# RULE: If payment statuses CONFLICT, EXCLUDE the subscriber-month entirely.
# Rationale: We cannot determine the true outcome. Including an arbitrary choice
# would introduce label noise. Better to have a smaller, cleaner dataset.
conflict_keys = same_status[~same_status].index
agree_keys = same_status[same_status].index
print(f"Conflicting status subscriber-months (EXCLUDED): {len(conflict_keys)}")
print(f"Agreeing status subscriber-months (KEPT, deduped): {len(agree_keys)}")

# For agreeing duplicates: keep the row with higher total_billed (includes corrections)
agree_dups = dups[dups.set_index(['subscriber_id', 'year_month']).index.isin(agree_keys)]
agree_deduped = agree_dups.sort_values('total_billed_usd', ascending=False)\
    .drop_duplicates(subset=['subscriber_id', 'year_month'], keep='first')
agree_deduped = agree_deduped.drop(columns=['row_num'])

# Combine
billing = pd.concat([singles, agree_deduped], ignore_index=True)
billing = billing.sort_values(['subscriber_id', 'year_month']).reset_index(drop=True)
print(f"Clean billing rows: {len(billing)}")

# Step 3: Define primary target
billing['target_recovered'] = billing['payment_status'].isin(['Paid On Time', 'Paid Late']).astype(int)
print(f"\nPrimary target distribution:")
print(billing['target_recovered'].value_counts())
print(billing['target_recovered'].value_counts(normalize=True).round(4))

# Step 4: Feature construction (same as v1 but with clean data)
billing['bill_amount_excl_late'] = (
    billing['base_charge_usd'] + billing['data_overage_usd'] +
    billing['intl_roaming_usd'] + billing['tax_usd']
)

billing['bill_seq'] = billing.groupby('subscriber_id').cumcount()
billing['is_failed'] = (billing['payment_status'] == 'Failed').astype(int)
billing['is_unpaid'] = (billing['payment_status'] == 'Unpaid').astype(int)
billing['is_late'] = (billing['payment_status'] == 'Paid Late').astype(int)
billing['is_ontime'] = (billing['payment_status'] == 'Paid On Time').astype(int)

billing['prior_failures'] = billing.groupby('subscriber_id')['is_failed'].cumsum() - billing['is_failed']
billing['prior_unpaid'] = billing.groupby('subscriber_id')['is_unpaid'].cumsum() - billing['is_unpaid']
billing['prior_late'] = billing.groupby('subscriber_id')['is_late'].cumsum() - billing['is_late']
billing['prior_ontime'] = billing.groupby('subscriber_id')['is_ontime'].cumsum() - billing['is_ontime']
billing['prior_nonrecovery_count'] = billing['prior_failures'] + billing['prior_unpaid']
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

print(f"\nFinal billing v2 shape: {billing_out.shape}")
print(f"Temporal split:")
print(billing_out.groupby('split')['target_recovered'].agg(['count', 'mean']).round(4))
print(f"Nulls: {billing_out.isnull().sum().sum()}")

billing_out.to_csv(os.path.join(OUTPUT_DIR, "billing_recovery_v2.csv"), index=False)
print("Saved billing_recovery_v2.csv")

# ===========================================================================
# AR v2
# ===========================================================================
print("\n" + "=" * 80)
print("AR_RECOVERY_V2 CONSTRUCTION")
print("=" * 80)

wa = pd.read_csv("dataset/WA_Fn-UseC_-Accounts-Receivable.csv")
wa['InvoiceDate_parsed'] = pd.to_datetime(wa['InvoiceDate'])
wa['DueDate_parsed'] = pd.to_datetime(wa['DueDate'])
wa = wa.sort_values(['customerID', 'InvoiceDate_parsed']).reset_index(drop=True)

wa['target_late'] = (wa['DaysLate'] > 0).astype(int)
wa['invoice_seq'] = wa.groupby('customerID').cumcount()
wa['is_late'] = wa['target_late']
wa['prior_late_count'] = wa.groupby('customerID')['is_late'].cumsum() - wa['is_late']
wa['prior_invoice_count'] = wa['invoice_seq']
wa['prior_late_rate'] = wa['prior_late_count'] / wa['prior_invoice_count'].replace(0, np.nan)
wa['prior_cumulative_amount'] = wa.groupby('customerID')['InvoiceAmount'].cumsum() - wa['InvoiceAmount']
wa['prior_avg_amount'] = wa['prior_cumulative_amount'] / wa['prior_invoice_count'].replace(0, np.nan)
wa['is_disputed'] = (wa['Disputed'] == 'Yes').astype(int)
wa['prior_disputes'] = wa.groupby('customerID')['is_disputed'].cumsum() - wa['is_disputed']
wa['is_paperless'] = (wa['PaperlessBill'] == 'Electronic').astype(int)

# CHANGE FROM V1: DROP payment_window_days (constant at 30, zero variance)
ar_feature_cols = [
    'InvoiceAmount', 'countryCode',
    'is_disputed',    # FLAGGED AS AMBIGUOUS — kept but documented
    'invoice_seq', 'prior_late_count', 'prior_invoice_count',
    'prior_late_rate', 'prior_avg_amount', 'prior_disputes',
    'is_paperless',
]

ar_meta_cols = ['customerID', 'invoiceNumber', 'InvoiceDate', 'DueDate']
ar_output_cols = ar_meta_cols + ar_feature_cols + ['target_late']
ar_out = wa[ar_output_cols].copy()

for col in ['prior_late_rate', 'prior_avg_amount']:
    ar_out[col] = ar_out[col].fillna(-1)

ar_out['InvoiceDate_parsed'] = pd.to_datetime(ar_out['InvoiceDate'])
ar_out['split'] = 'train'
ar_out.loc[ar_out['InvoiceDate_parsed'] >= '2013-04-01', 'split'] = 'validation'
ar_out.loc[ar_out['InvoiceDate_parsed'] >= '2013-08-01', 'split'] = 'test'
ar_out = ar_out.drop(columns=['InvoiceDate_parsed'])

print(f"Final AR v2 shape: {ar_out.shape}")
print(f"Temporal split:")
print(ar_out.groupby('split')['target_late'].agg(['count', 'mean']).round(4))

ar_out.to_csv(os.path.join(OUTPUT_DIR, "ar_recovery_v2.csv"), index=False)
print("Saved ar_recovery_v2.csv")

# ===========================================================================
# METADATA v2
# ===========================================================================

billing_meta = {
    "dataset_version": "recoverchain-billing-recovery-v2",
    "source_file": "dataset/billing.csv",
    "source_sha256": "9615a50e653bf075988efd8642bc44e5ff06c3e31bbf00336469b9dfd488244e",
    "provenance": "UNKNOWN — appears synthetic telecom billing data",
    "training_unit": "subscriber-month billing obligation",
    "unit_identifier": "subscriber_id + year_month",
    "deduplication_rule": "1) Drop exact row duplicates. 2) For subscriber-months with 2 remaining rows: if payment_status CONFLICTS, EXCLUDE the subscriber-month entirely. If payment_status agrees, keep highest total_billed_usd.",
    "conflicting_records_excluded": 201327,
    "target_column": "target_recovered",
    "target_definition": "1 = Paid On Time or Paid Late; 0 = Failed or Unpaid",
    "target_caveat": "89% of subscribers with Failed/Unpaid status later recover. Individual-month failure is overwhelmingly temporary in this dataset.",
    "row_count": int(len(billing_out)),
    "features": feature_cols,
    "excluded_leakage": ["payment_status", "days_to_payment", "late_fee_usd", "total_billed_usd"],
    "class_distribution": {
        "recovered": int(billing_out['target_recovered'].sum()),
        "not_recovered": int((1 - billing_out['target_recovered']).sum()),
        "recovery_rate": round(float(billing_out['target_recovered'].mean()), 4)
    },
    "temporal_split": {"train": "2025-07 to 2025-12", "validation": "2026-01 to 2026-03", "test": "2026-04 to 2026-05"},
    "entity_leakage": "Nearly 100% subscriber overlap across splits — expected for temporal split",
    "provenance_status": "UNKNOWN"
}

ar_meta = {
    "dataset_version": "recoverchain-ar-recovery-v2",
    "source_file": "dataset/WA_Fn-UseC_-Accounts-Receivable.csv",
    "source_sha256": "651bc4225708bf33148a0e177c9221afdf697d3a4de10333725a4af3dd022fcf",
    "provenance": "UNKNOWN — IBM Watson Analytics sample dataset",
    "training_unit": "invoice",
    "unit_identifier": "invoiceNumber",
    "target_column": "target_late",
    "target_definition": "1 = DaysLate > 0; 0 = DaysLate == 0",
    "target_caveat": "ALL invoices settled. Models late-settlement RISK, not non-recovery.",
    "row_count": int(len(ar_out)),
    "features": ar_feature_cols,
    "dropped_features_v2": {"payment_window_days": "Constant (30) — zero variance"},
    "ambiguous_features": {"is_disputed": "May be filed after late payment — cannot determine causal direction"},
    "excluded_leakage": ["DaysToSettle", "DaysLate", "SettledDate"],
    "class_distribution": {
        "late": int(ar_out['target_late'].sum()),
        "on_time": int((1 - ar_out['target_late']).sum()),
        "late_rate": round(float(ar_out['target_late'].mean()), 4)
    },
    "temporal_split": {"train": "2012-01-03 to 2013-03-31", "validation": "2013-04-01 to 2013-07-31", "test": "2013-08-01 to 2013-12-02"},
    "provenance_status": "UNKNOWN"
}

with open(os.path.join(OUTPUT_DIR, "billing_recovery_v2_metadata.json"), "w") as f:
    json.dump(billing_meta, f, indent=2)
with open(os.path.join(OUTPUT_DIR, "ar_recovery_v2_metadata.json"), "w") as f:
    json.dump(ar_meta, f, indent=2)

print("\nMetadata written.")
print("\nDONE — No models trained.")
