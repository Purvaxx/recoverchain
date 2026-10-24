"""
Phase 16C — Deep AR dataset validation.
Independently verify all Phase 16B claims.
"""
import pandas as pd
import numpy as np
import hashlib
import os

print("=" * 80)
print("PHASE 16C: WA_Fn AR DATASET DEEP VALIDATION")
print("=" * 80)

# Hash original
h = hashlib.sha256()
with open("dataset/WA_Fn-UseC_-Accounts-Receivable.csv", "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        h.update(chunk)
print(f"Original file SHA256: {h.hexdigest()}")

# Load original
wa = pd.read_csv("dataset/WA_Fn-UseC_-Accounts-Receivable.csv")
print(f"Original shape: {wa.shape}")

# Load constructed
ar = pd.read_csv("backend/evaluation/datasets/ar_recovery_v1.csv")
print(f"Constructed shape: {ar.shape}")

# 1. Verify target_late definition
print("\n--- TARGET VALIDATION ---")
wa['is_late_check'] = (wa['DaysLate'] > 0).astype(int)
# Merge to verify
merged = wa.merge(ar[['invoiceNumber', 'target_late']], on='invoiceNumber', how='inner')
mismatch = (merged['is_late_check'] != merged['target_late']).sum()
print(f"Target mismatches: {mismatch}")
print(f"Target correctly derived from DaysLate: {'YES' if mismatch == 0 else 'NO'}")

# 2. Is DaysLate truly post-outcome?
print("\n--- DAYSLATE TEMPORAL ANALYSIS ---")
wa['InvoiceDate_p'] = pd.to_datetime(wa['InvoiceDate'])
wa['DueDate_p'] = pd.to_datetime(wa['DueDate'])
wa['SettledDate_p'] = pd.to_datetime(wa['SettledDate'])

# DaysLate = max(0, SettledDate - DueDate) in days
wa['computed_days_late'] = (wa['SettledDate_p'] - wa['DueDate_p']).dt.days
wa['computed_days_late'] = wa['computed_days_late'].clip(lower=0)
match_count = (wa['computed_days_late'] == wa['DaysLate']).sum()
print(f"DaysLate matches (SettledDate - DueDate).clip(0): {match_count} / {len(wa)}")
# Check any that don't match
mismatches = wa[wa['computed_days_late'] != wa['DaysLate']]
if len(mismatches) > 0:
    print(f"Mismatches found: {len(mismatches)}")
    print(mismatches[['invoiceNumber', 'DueDate', 'SettledDate', 'DaysLate', 'computed_days_late']].head(10))
else:
    print("CONFIRMED: DaysLate = max(0, SettledDate - DueDate)")
    print("CONFIRMED: DaysLate is POST-OUTCOME information (requires SettledDate)")

# 3. Verify 100% settlement
print("\n--- SETTLEMENT COMPLETENESS ---")
print(f"SettledDate null count: {wa['SettledDate'].isnull().sum()}")
print(f"ALL INVOICES SETTLED: {'YES' if wa['SettledDate'].notnull().all() else 'NO'}")
print(f"DaysToSettle null count: {wa['DaysToSettle'].isnull().sum()}")
print(f"Min DaysToSettle: {wa['DaysToSettle'].min()}")
print(f"DaysToSettle == 0: {(wa['DaysToSettle'] == 0).sum()}")

# 4. Feature availability at InvoiceDate
print("\n--- FEATURE AVAILABILITY AT INVOICE TIME ---")
print("Checking each constructed feature:")
ar_cols = list(ar.columns)
print(f"Constructed columns: {ar_cols}")

# Check Disputed temporal availability
print(f"\n--- DISPUTED FIELD TEMPORAL CHECK ---")
# Is 'Disputed' known at invoice creation or only after?
# In AR, disputes are typically filed AFTER invoice issuance.
# Check: do disputed invoices have different DaysLate patterns?
ct = pd.crosstab(wa['Disputed'], wa['DaysLate'] > 0, normalize='index')
ct.columns = ['On Time %', 'Late %']
print(f"Disputed vs Late:")
print(ct.round(3))
print(f"\nDisputed=Yes AND DaysLate=0: {((wa['Disputed']=='Yes') & (wa['DaysLate']==0)).sum()}")
print(f"Disputed=Yes AND DaysLate>0: {((wa['Disputed']=='Yes') & (wa['DaysLate']>0)).sum()}")
# If Disputed is known before settlement, it's a valid feature.
# If it's filed AFTER a late payment, it's leakage.
# CRITICAL: 68.3% of disputed invoices are late vs 25.9% of non-disputed.
# This COULD be because disputes cause lateness, OR because lateness causes disputes.
# We CANNOT determine the causal direction from the data alone.
print("\nWARNING: 'Disputed' has ambiguous temporal availability.")
print("It could be a cause or consequence of late payment.")
print("CLASSIFICATION: AMBIGUOUS — should be tested with and without.")

# 5. Entity leakage check
print("\n--- ENTITY LEAKAGE CHECK ---")
print(f"Unique customers: {wa['customerID'].nunique()}")
print(f"Total invoices: {len(wa)}")
print(f"Invoices per customer: min={wa.groupby('customerID').size().min()}, "
      f"max={wa.groupby('customerID').size().max()}, "
      f"mean={wa.groupby('customerID').size().mean():.1f}")

# In temporal split, same customer appears in train AND test
train_custs = set(ar[ar['split'] == 'train']['customerID'].unique())
test_custs = set(ar[ar['split'] == 'test']['customerID'].unique())
val_custs = set(ar[ar['split'] == 'validation']['customerID'].unique())
print(f"\nCustomers in train: {len(train_custs)}")
print(f"Customers in validation: {len(val_custs)}")
print(f"Customers in test: {len(test_custs)}")
print(f"Overlap train-test: {len(train_custs & test_custs)}")
print(f"Overlap train-val: {len(train_custs & val_custs)}")
# With only 100 customers, most will appear in all splits.
# This is EXPECTED for temporal splits but means customer-level patterns leak.
# The history features partially account for this.

# 6. Verify history feature construction
print("\n--- HISTORY FEATURE VERIFICATION ---")
# Manually verify for one customer
sample_cust = ar['customerID'].iloc[0]
cust_rows = ar[ar['customerID'] == sample_cust].sort_values('InvoiceDate')
print(f"\nCustomer {sample_cust}:")
print(cust_rows[['invoiceNumber', 'InvoiceDate', 'invoice_seq', 'prior_late_count', 
                  'prior_invoice_count', 'prior_late_rate', 'target_late']].head(10).to_string())

# Verify: for row at invoice_seq=N, prior_late_count should equal
# sum of target_late for rows 0..N-1
for idx, row in cust_rows.head(6).iterrows():
    seq = row['invoice_seq']
    expected_prior = cust_rows[cust_rows['invoice_seq'] < seq]['target_late'].sum()
    actual_prior = row['prior_late_count']
    match = "OK" if expected_prior == actual_prior else f"MISMATCH (expected {expected_prior})"
    print(f"  seq={seq}: prior_late_count={actual_prior} {match}")

# 7. Check impossible/suspicious values
print("\n--- VALUE RANGE CHECK ---")
print(f"InvoiceAmount range: [{ar['InvoiceAmount'].min()}, {ar['InvoiceAmount'].max()}]")
print(f"Negative InvoiceAmount: {(ar['InvoiceAmount'] < 0).sum()}")
print(f"Zero InvoiceAmount: {(ar['InvoiceAmount'] == 0).sum()}")
print(f"payment_window_days range: [{ar['payment_window_days'].min()}, {ar['payment_window_days'].max()}]")
print(f"Negative payment_window: {(ar['payment_window_days'] < 0).sum()}")

print("\nDONE")
