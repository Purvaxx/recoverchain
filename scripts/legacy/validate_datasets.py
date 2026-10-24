"""
Phase 16B — Final validation checks on constructed datasets.
"""
import pandas as pd
import json

print("=" * 80)
print("VALIDATION: billing_recovery_v1.csv")
print("=" * 80)

# Load a sample to verify structure
b = pd.read_csv("backend/evaluation/datasets/billing_recovery_v1.csv", nrows=50000)
print(f"Columns: {list(b.columns)}")
print(f"Shape (sample): {b.shape}")
print(f"Dtypes:\n{b.dtypes}")

# Verify no leakage columns present
leakage_cols = ['payment_status', 'days_to_payment', 'late_fee_usd', 'total_billed_usd']
for lc in leakage_cols:
    assert lc not in b.columns, f"LEAKAGE: {lc} found in output!"
print("\nLeakage check: PASSED (no leakage columns present)")

# Verify target exists and is binary
assert 'target_recovered' in b.columns
assert set(b['target_recovered'].unique()) == {0, 1}
print("Target check: PASSED")

# Verify split column
assert 'split' in b.columns
assert set(b['split'].unique()) <= {'train', 'validation', 'test'}
print("Split check: PASSED")

# Verify no nulls
assert b.isnull().sum().sum() == 0
print("Null check: PASSED")

# Verify history features use prior-only data
# For bill_seq == 0, prior history should be -1 or 0
first_bills = b[b['bill_seq'] == 0]
assert (first_bills['prior_failures'] == 0).all()
assert (first_bills['prior_nonrecovery_rate'] == -1).all()
print("History temporal correctness: PASSED")

print("\n" + "=" * 80)
print("VALIDATION: ar_recovery_v1.csv")
print("=" * 80)

ar = pd.read_csv("backend/evaluation/datasets/ar_recovery_v1.csv")
print(f"Columns: {list(ar.columns)}")
print(f"Shape: {ar.shape}")

# Verify no leakage columns
ar_leakage = ['DaysToSettle', 'DaysLate', 'SettledDate']
for lc in ar_leakage:
    assert lc not in ar.columns, f"LEAKAGE: {lc} found in output!"
print("\nLeakage check: PASSED")

# Verify target
assert 'target_late' in ar.columns
assert set(ar['target_late'].unique()) == {0, 1}
print("Target check: PASSED")

# Verify unique invoiceNumber
assert ar['invoiceNumber'].nunique() == len(ar)
print("Deduplication check: PASSED (invoiceNumber is unique)")

# Verify split
assert 'split' in ar.columns
print("Split check: PASSED")

# Verify no nulls
assert ar.isnull().sum().sum() == 0
print("Null check: PASSED")

# Verify history temporal correctness
first_invoices = ar[ar['invoice_seq'] == 0]
assert (first_invoices['prior_late_count'] == 0).all()
assert (first_invoices['prior_late_rate'] == -1).all()
print("History temporal correctness: PASSED")

# Load and verify metadata
print("\n" + "=" * 80)
print("METADATA VALIDATION")
print("=" * 80)

with open("backend/evaluation/datasets/billing_recovery_v1_metadata.json") as f:
    bm = json.load(f)
print(f"Billing version: {bm['dataset_version']}")
print(f"Billing provenance: {bm['provenance_status']}")
print(f"Billing row_count: {bm['row_count']}")

with open("backend/evaluation/datasets/ar_recovery_v1_metadata.json") as f:
    am = json.load(f)
print(f"AR version: {am['dataset_version']}")
print(f"AR provenance: {am['provenance_status']}")
print(f"AR row_count: {am['row_count']}")

print("\n" + "=" * 80)
print("ALL VALIDATION CHECKS PASSED")
print("=" * 80)
