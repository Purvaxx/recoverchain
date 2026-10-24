"""
Phase 16B — Training Dataset Construction Script

Constructs two separate training-ready datasets:
  1. billing_recovery_v1.csv — from billing.csv
  2. ar_recovery_v1.csv — from WA_Fn-UseC_-Accounts-Receivable.csv

NO MODEL TRAINING IS PERFORMED.
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

OUTPUT_DIR = "backend/evaluation/datasets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===========================================================================
# DATASET 1: billing.csv -> billing_recovery_v1
# ===========================================================================
print("=" * 80)
print("Constructing billing_recovery_v1")
print("=" * 80)

# Load full dataset in chunks, deduplicate
chunks = []
for chunk in pd.read_csv("dataset/billing.csv", chunksize=500000, low_memory=False):
    chunks.append(chunk)
billing = pd.concat(chunks, ignore_index=True)
print(f"Raw rows: {len(billing)}")

# Drop exact duplicate rows
billing = billing.drop_duplicates()
print(f"After exact dedup: {len(billing)}")

# Handle subscriber-month duplicates where one row has late_fee and one doesn't
# Keep the row with higher total_billed_usd (the corrected/final billing)
billing = billing.sort_values('total_billed_usd', ascending=False)
billing = billing.drop_duplicates(subset=['subscriber_id', 'year_month'], keep='first')
print(f"After subscriber-month dedup (keep highest total): {len(billing)}")

# Sort chronologically
billing = billing.sort_values(['subscriber_id', 'year_month']).reset_index(drop=True)

# Define binary target
# RECOVERED = Paid On Time OR Paid Late (obligation was met)
# NOT_RECOVERED = Failed OR Unpaid (obligation was NOT met)
billing['target_recovered'] = billing['payment_status'].isin(['Paid On Time', 'Paid Late']).astype(int)

print(f"\nTarget distribution:")
print(billing['target_recovered'].value_counts())
print(billing['target_recovered'].value_counts(normalize=True).round(4))

# ---- LEAKAGE AUDIT ----
# days_to_payment: LEAKAGE. This is the number of days it took to pay. 
#   For "Paid On Time" it's 0, for "Failed"/"Unpaid" it's >0. 
#   This is OUTCOME information, not available at decision time.
# payment_status: This IS the target. Must be excluded from features.
# late_fee_usd: AMBIGUOUS. A late fee could be applied BEFORE or AFTER resolution.
#   Conservatively EXCLUDE as potential leakage.

# ---- FEATURE CONSTRUCTION ----
# Features available BEFORE recovery decision:
#   - subscriber_id (for history, not as feature)
#   - year_month (temporal context)
#   - base_charge_usd (amount billed)
#   - data_overage_usd (overage charges)
#   - intl_roaming_usd (roaming charges)
#   - tax_usd (tax amount)
#   - total_billed_usd (CAUTION: includes late_fee which may be leakage)
#     -> We'll compute bill_amount_excl_late = base_charge + data_overage + intl_roaming + tax

billing['bill_amount_excl_late'] = (
    billing['base_charge_usd'] + 
    billing['data_overage_usd'] + 
    billing['intl_roaming_usd'] + 
    billing['tax_usd']
)

# ---- HISTORICAL FEATURES ----
# Must use ONLY information from PRIOR rows (strictly before current year_month)
billing['bill_seq'] = billing.groupby('subscriber_id').cumcount()

# Prior payment outcomes
billing['is_failed'] = (billing['payment_status'] == 'Failed').astype(int)
billing['is_unpaid'] = (billing['payment_status'] == 'Unpaid').astype(int)
billing['is_late'] = (billing['payment_status'] == 'Paid Late').astype(int)
billing['is_ontime'] = (billing['payment_status'] == 'Paid On Time').astype(int)

billing['prior_failures'] = billing.groupby('subscriber_id')['is_failed'].cumsum() - billing['is_failed']
billing['prior_unpaid'] = billing.groupby('subscriber_id')['is_unpaid'].cumsum() - billing['is_unpaid']
billing['prior_late'] = billing.groupby('subscriber_id')['is_late'].cumsum() - billing['is_late']
billing['prior_ontime'] = billing.groupby('subscriber_id')['is_ontime'].cumsum() - billing['is_ontime']

# Prior non-recovery rate (failures + unpaid) / total prior
billing['prior_nonrecovery_count'] = billing['prior_failures'] + billing['prior_unpaid']
billing['prior_nonrecovery_rate'] = billing['prior_nonrecovery_count'] / billing['bill_seq'].replace(0, np.nan)
billing['prior_late_rate'] = billing['prior_late'] / billing['bill_seq'].replace(0, np.nan)

# Prior average bill amount
billing['prior_cumulative_amount'] = billing.groupby('subscriber_id')['bill_amount_excl_late'].cumsum() - billing['bill_amount_excl_late']
billing['prior_avg_amount'] = billing['prior_cumulative_amount'] / billing['bill_seq'].replace(0, np.nan)

# Has data overage / intl roaming
billing['has_overage'] = (billing['data_overage_usd'] > 0).astype(int)
billing['has_roaming'] = (billing['intl_roaming_usd'] > 0).astype(int)

# ---- SELECT FINAL FEATURES ----
feature_cols = [
    'bill_amount_excl_late',
    'base_charge_usd',
    'data_overage_usd',
    'intl_roaming_usd',
    'tax_usd',
    'has_overage',
    'has_roaming',
    'bill_seq',
    'prior_failures',
    'prior_unpaid',
    'prior_late',
    'prior_ontime',
    'prior_nonrecovery_count',
    'prior_nonrecovery_rate',
    'prior_late_rate',
    'prior_avg_amount',
]

meta_cols = ['subscriber_id', 'year_month']
target_col = 'target_recovered'

output_cols = meta_cols + feature_cols + [target_col]
billing_out = billing[output_cols].copy()

# Fill NaN in history features for first observation (no prior history)
for col in ['prior_nonrecovery_rate', 'prior_late_rate', 'prior_avg_amount']:
    billing_out[col] = billing_out[col].fillna(-1)  # -1 = "no history available"

print(f"\nFinal billing dataset shape: {billing_out.shape}")
print(f"Missingness:\n{billing_out.isnull().sum()}")

# ---- TEMPORAL SPLIT ----
# Year-month values: 2025-07 through 2026-05 (with 2026-02 missing)
# Train: 2025-07 to 2025-12
# Validation: 2026-01 to 2026-03
# Test: 2026-04 to 2026-05
billing_out['split'] = 'train'
billing_out.loc[billing_out['year_month'].isin(['2026-01', '2026-03']), 'split'] = 'validation'
billing_out.loc[billing_out['year_month'].isin(['2026-04', '2026-05']), 'split'] = 'test'

print(f"\nTemporal split:")
print(billing_out.groupby('split')['target_recovered'].agg(['count', 'mean']).round(4))

# Save
billing_path = os.path.join(OUTPUT_DIR, "billing_recovery_v1.csv")
billing_out.to_csv(billing_path, index=False)
print(f"\nSaved to: {billing_path}")

# ===========================================================================
# DATASET 2: WA_Fn -> ar_recovery_v1
# ===========================================================================
print("\n" + "=" * 80)
print("Constructing ar_recovery_v1")
print("=" * 80)

wa = pd.read_csv("dataset/WA_Fn-UseC_-Accounts-Receivable.csv")
print(f"Raw rows: {len(wa)}")

# Parse dates
wa['InvoiceDate_parsed'] = pd.to_datetime(wa['InvoiceDate'])
wa['DueDate_parsed'] = pd.to_datetime(wa['DueDate'])
wa['SettledDate_parsed'] = pd.to_datetime(wa['SettledDate'])

# CRITICAL FINDING: ALL invoices settled (SettledDate has 0 nulls).
# This means we CANNOT model binary RECOVERED/NOT_RECOVERED here.
# Instead, model LATE SETTLEMENT as a proxy for recovery risk:
#   target = 1 if DaysLate > 0 (settlement was late = AT RISK)
#   target = 0 if DaysLate == 0 (settled on time = NOT AT RISK)

wa['target_late'] = (wa['DaysLate'] > 0).astype(int)

print(f"\nTarget distribution (is_late):")
print(wa['target_late'].value_counts())
print(wa['target_late'].value_counts(normalize=True).round(4))

# Sort by customer and invoice date
wa = wa.sort_values(['customerID', 'InvoiceDate_parsed']).reset_index(drop=True)

# ---- LEAKAGE AUDIT ----
# DaysToSettle: LEAKAGE. Only known after settlement.
# DaysLate: Used to DEFINE the target. Must NOT be a feature.
# SettledDate: LEAKAGE. Only known after settlement.

# ---- FEATURE CONSTRUCTION ----
# Available at invoice creation time:
#   - InvoiceAmount
#   - countryCode
#   - Disputed (known at invoice time? AMBIGUOUS — disputes may be filed later)
#     -> CONSERVATIVELY KEEP as it's listed in the original data alongside invoice
#   - PaperlessBill
#   - DueDate - InvoiceDate = payment_window_days

wa['payment_window_days'] = (wa['DueDate_parsed'] - wa['InvoiceDate_parsed']).dt.days

# ---- HISTORICAL FEATURES ----
wa['invoice_seq'] = wa.groupby('customerID').cumcount()
wa['is_late'] = wa['target_late']

wa['prior_late_count'] = wa.groupby('customerID')['is_late'].cumsum() - wa['is_late']
wa['prior_invoice_count'] = wa['invoice_seq']
wa['prior_late_rate'] = wa['prior_late_count'] / wa['prior_invoice_count'].replace(0, np.nan)

# Prior average amount
wa['prior_cumulative_amount'] = wa.groupby('customerID')['InvoiceAmount'].cumsum() - wa['InvoiceAmount']
wa['prior_avg_amount'] = wa['prior_cumulative_amount'] / wa['prior_invoice_count'].replace(0, np.nan)

# Prior disputed count
wa['is_disputed'] = (wa['Disputed'] == 'Yes').astype(int)
wa['prior_disputes'] = wa.groupby('customerID')['is_disputed'].cumsum() - wa['is_disputed']

# ---- SELECT FINAL FEATURES ----
ar_feature_cols = [
    'InvoiceAmount',
    'countryCode',
    'is_disputed',
    'payment_window_days',
    'invoice_seq',
    'prior_late_count',
    'prior_invoice_count',
    'prior_late_rate',
    'prior_avg_amount',
    'prior_disputes',
]

ar_meta_cols = ['customerID', 'invoiceNumber', 'InvoiceDate', 'DueDate']
ar_target_col = 'target_late'

# Encode PaperlessBill
wa['is_paperless'] = (wa['PaperlessBill'] == 'Electronic').astype(int)
ar_feature_cols.append('is_paperless')

ar_output_cols = ar_meta_cols + ar_feature_cols + [ar_target_col]
ar_out = wa[ar_output_cols].copy()

# Fill NaN for first-invoice customers
for col in ['prior_late_rate', 'prior_avg_amount']:
    ar_out[col] = ar_out[col].fillna(-1)

print(f"\nFinal AR dataset shape: {ar_out.shape}")
print(f"Missingness:\n{ar_out.isnull().sum()}")

# ---- TEMPORAL SPLIT ----
ar_out['InvoiceDate_parsed'] = pd.to_datetime(ar_out['InvoiceDate'])
# Date range: 2012-01-03 to 2013-12-02
# Train: 2012-01 to 2013-03
# Validation: 2013-04 to 2013-07
# Test: 2013-08 to 2013-12
ar_out['split'] = 'train'
ar_out.loc[ar_out['InvoiceDate_parsed'] >= '2013-04-01', 'split'] = 'validation'
ar_out.loc[ar_out['InvoiceDate_parsed'] >= '2013-08-01', 'split'] = 'test'

print(f"\nTemporal split:")
print(ar_out.groupby('split')[ar_target_col].agg(['count', 'mean']).round(4))

ar_out = ar_out.drop(columns=['InvoiceDate_parsed'])
ar_path = os.path.join(OUTPUT_DIR, "ar_recovery_v1.csv")
ar_out.to_csv(ar_path, index=False)
print(f"\nSaved to: {ar_path}")

# ===========================================================================
# DATASET JOINABILITY ANALYSIS
# ===========================================================================
print("\n" + "=" * 80)
print("DATASET JOINABILITY ANALYSIS")
print("=" * 80)
print("billing.csv: Telecom subscription billing. Entity = subscriber-month.")
print("WA_Fn: Accounts receivable invoices. Entity = invoice.")
print("")
print("JOIN KEY CANDIDATES:")
print("  - billing.subscriber_id vs WA_Fn.customerID: INCOMPATIBLE")
print("    billing uses SUB0000001 format, WA_Fn uses 0379-NEVHP format.")
print("    Different ID namespaces, different industries (telecom vs generic AR).")
print("  - No shared temporal key (billing=2025-2026, WA_Fn=2012-2013)")
print("  - No shared domain (telecom billing vs enterprise invoicing)")
print("")
print("DECISION: DO NOT JOIN. Keep as separate training datasets.")
print("REASON: Different entity types, different time periods, different industries,")
print("        no shared identifiers. Forcing a join would be scientifically invalid.")

# ===========================================================================
# METADATA FILES
# ===========================================================================
print("\n" + "=" * 80)
print("Writing metadata")
print("=" * 80)

billing_meta = {
    "dataset_version": "recoverchain-billing-recovery-v1",
    "source_file": "dataset/billing.csv",
    "provenance": "UNKNOWN — appears to be synthetic telecom subscription billing data. No verifiable real-world merchant source.",
    "description": "Telecom subscription billing records with payment outcomes. Each row = one subscriber-month billing event.",
    "training_unit": "subscriber-month billing obligation",
    "unit_identifier": "subscriber_id + year_month",
    "deduplication_rule": "Drop exact row duplicates, then keep highest total_billed_usd per subscriber-month",
    "target_column": "target_recovered",
    "target_definition": "1 = obligation was met (Paid On Time or Paid Late); 0 = obligation was NOT met (Failed or Unpaid)",
    "positive_class": "1 (recovered)",
    "negative_class": "0 (not recovered)",
    "row_count": int(len(billing_out)),
    "feature_count": len(feature_cols),
    "features": feature_cols,
    "excluded_leakage_columns": [
        "payment_status (IS the target)",
        "days_to_payment (only known after resolution)",
        "late_fee_usd (may be applied after resolution)",
        "total_billed_usd (includes late_fee)"
    ],
    "timestamp_range": {"min": "2025-07", "max": "2026-05", "missing": ["2026-02"]},
    "temporal_split": {
        "train": "2025-07 to 2025-12",
        "validation": "2026-01 to 2026-03",
        "test": "2026-04 to 2026-05"
    },
    "class_distribution": {
        "recovered": int(billing_out['target_recovered'].sum()),
        "not_recovered": int((1 - billing_out['target_recovered']).sum()),
        "recovery_rate": float(billing_out['target_recovered'].mean().round(4))
    },
    "preprocessing": [
        "Dropped exact duplicate rows",
        "Kept highest total_billed_usd per subscriber-month for near-duplicates",
        "Computed bill_amount_excl_late = base + overage + roaming + tax",
        "Constructed temporal history features using strictly prior rows",
        "Filled NaN history features with -1 for first-observation rows"
    ],
    "limitations": [
        "Provenance UNKNOWN — likely synthetic data",
        "2026-02 is missing from the time series",
        "94.7% recovery rate = significant class imbalance",
        "No failure reason codes available",
        "No payment method information",
        "Individual financial features show near-zero correlation with target"
    ],
    "provenance_status": "UNKNOWN"
}

ar_meta = {
    "dataset_version": "recoverchain-ar-recovery-v1",
    "source_file": "dataset/WA_Fn-UseC_-Accounts-Receivable.csv",
    "provenance": "UNKNOWN — IBM Watson Analytics sample dataset. Widely used for educational purposes. Not verified as real merchant data.",
    "description": "Enterprise accounts receivable invoices with settlement information. Each row = one invoice.",
    "training_unit": "invoice",
    "unit_identifier": "invoiceNumber",
    "deduplication_rule": "invoiceNumber is unique (verified: 2466 unique values, 2466 rows). No deduplication needed.",
    "target_column": "target_late",
    "target_definition": "1 = invoice was settled LATE (DaysLate > 0); 0 = invoice was settled ON TIME (DaysLate == 0)",
    "target_caveat": "ALL invoices in this dataset were eventually settled. There are ZERO write-offs or permanent non-payments. The target represents LATE settlement risk, NOT absolute non-recovery.",
    "positive_class": "1 (late settlement = at-risk)",
    "negative_class": "0 (on-time settlement = not at risk)",
    "row_count": int(len(ar_out)),
    "feature_count": len(ar_feature_cols),
    "features": ar_feature_cols,
    "excluded_leakage_columns": [
        "DaysToSettle (only known after settlement)",
        "DaysLate (used to define target, not a feature)",
        "SettledDate (only known after settlement)"
    ],
    "timestamp_range": {"min": "2012-01-03", "max": "2013-12-02"},
    "temporal_split": {
        "train": "2012-01-03 to 2013-03-31",
        "validation": "2013-04-01 to 2013-07-31",
        "test": "2013-08-01 to 2013-12-02"
    },
    "class_distribution": {
        "late": int(ar_out['target_late'].sum()),
        "on_time": int((1 - ar_out['target_late']).sum()),
        "late_rate": float(ar_out['target_late'].mean().round(4))
    },
    "preprocessing": [
        "No deduplication needed (invoiceNumber is unique)",
        "Parsed dates and computed payment_window_days",
        "Encoded PaperlessBill as binary is_paperless",
        "Encoded Disputed as binary is_disputed",
        "Constructed temporal history features using strictly prior invoices",
        "Filled NaN history features with -1 for first-invoice customers"
    ],
    "limitations": [
        "Only 2,466 rows — very small for ML",
        "Only 100 unique customers",
        "ALL invoices settled — cannot model absolute non-recovery",
        "Target is late-settlement proxy, not true recovery/non-recovery",
        "Provenance UNKNOWN — IBM Watson sample, not verified real-world data",
        "Date range is 2012-2013 — old data"
    ],
    "provenance_status": "UNKNOWN"
}

with open(os.path.join(OUTPUT_DIR, "billing_recovery_v1_metadata.json"), "w") as f:
    json.dump(billing_meta, f, indent=2)

with open(os.path.join(OUTPUT_DIR, "ar_recovery_v1_metadata.json"), "w") as f:
    json.dump(ar_meta, f, indent=2)

print("Metadata files written.")
print("\nDONE — No models trained.")
