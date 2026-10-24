"""
Phase 16C — Validate the CONSTRUCTED billing_recovery_v1.csv (sample).
Check feature values, history consistency, entity leakage.
"""
import pandas as pd
import numpy as np

print("=" * 80)
print("CONSTRUCTED BILLING DATASET VALIDATION")
print("=" * 80)

# Load a large sample
b = pd.read_csv("backend/evaluation/datasets/billing_recovery_v1.csv", nrows=200000)
print(f"Loaded sample: {b.shape}")
print(f"Columns: {list(b.columns)}")

# 1. Verify no leakage columns
leakage_cols = ['payment_status', 'days_to_payment', 'late_fee_usd', 'total_billed_usd']
for lc in leakage_cols:
    present = lc in b.columns
    print(f"  Leakage column '{lc}': {'PRESENT (FAIL)' if present else 'absent (ok)'}")

# 2. Target distribution in sample
print(f"\nTarget distribution (sample):")
print(b['target_recovered'].value_counts())
print(b['target_recovered'].value_counts(normalize=True).round(4))

# 3. Entity leakage across splits
print(f"\n--- ENTITY LEAKAGE ---")
train_subs = set(b[b['split'] == 'train']['subscriber_id'].unique())
val_subs = set(b[b['split'] == 'validation']['subscriber_id'].unique())
test_subs = set(b[b['split'] == 'test']['subscriber_id'].unique())
print(f"Subscribers in train: {len(train_subs)}")
print(f"Subscribers in validation: {len(val_subs)}")
print(f"Subscribers in test: {len(test_subs)}")
print(f"Overlap train-val: {len(train_subs & val_subs)}")
print(f"Overlap train-test: {len(train_subs & test_subs)}")
print(f"Overlap val-test: {len(val_subs & test_subs)}")

# 4. History feature verification for sample subscribers
print(f"\n--- HISTORY FEATURE VERIFICATION ---")
# Pick a subscriber and manually verify
sample_sub = b['subscriber_id'].iloc[0]
sub_rows = b[b['subscriber_id'] == sample_sub].sort_values('year_month')
print(f"\nSubscriber {sample_sub}:")
print(sub_rows[['year_month', 'bill_seq', 'prior_failures', 'prior_unpaid', 
                 'prior_nonrecovery_count', 'prior_nonrecovery_rate', 'target_recovered']].to_string())

# Verify manually
for idx, row in sub_rows.iterrows():
    seq = row['bill_seq']
    prior_rows = sub_rows[sub_rows['bill_seq'] < seq]
    expected_non_rec = (prior_rows['target_recovered'] == 0).sum()
    actual = row['prior_nonrecovery_count']
    match = "OK" if expected_non_rec == actual else f"MISMATCH (expected {expected_non_rec})"
    print(f"  seq={seq}: prior_nonrecovery_count={actual} {match}")

# 5. Check for duplicate subscriber-months in constructed data
print(f"\n--- DEDUPLICATION CHECK ---")
dup_sm = b.duplicated(subset=['subscriber_id', 'year_month'], keep=False)
print(f"Duplicate subscriber-months in constructed data: {dup_sm.sum()}")
if dup_sm.sum() > 0:
    print("WARNING: Constructed dataset still has duplicate subscriber-months!")
    print(b[dup_sm].head(10))

# 6. bill_amount_excl_late check
print(f"\n--- BILL AMOUNT CHECK ---")
expected = b['base_charge_usd'] + b['data_overage_usd'] + b['intl_roaming_usd'] + b['tax_usd']
mismatch = (abs(b['bill_amount_excl_late'] - expected) > 0.01).sum()
print(f"bill_amount_excl_late mismatches: {mismatch}")

# 7. Value ranges
print(f"\n--- VALUE RANGES ---")
for col in ['bill_amount_excl_late', 'base_charge_usd', 'data_overage_usd', 
            'intl_roaming_usd', 'tax_usd']:
    neg = (b[col] < 0).sum()
    print(f"  {col}: min={b[col].min():.2f}, max={b[col].max():.2f}, negatives={neg}")

# 8. prior_nonrecovery_rate sanity check
print(f"\n--- HISTORY SANITY ---")
first_obs = b[b['bill_seq'] == 0]
print(f"First observations (bill_seq=0): {len(first_obs)}")
print(f"  prior_nonrecovery_rate == -1: {(first_obs['prior_nonrecovery_rate'] == -1).sum()}")
print(f"  prior_failures == 0: {(first_obs['prior_failures'] == 0).sum()}")
print(f"  prior_late_rate == -1: {(first_obs['prior_late_rate'] == -1).sum()}")

# For subscribers with bill_seq > 0, rate should be in [0, 1]
later_obs = b[b['bill_seq'] > 0]
print(f"\nLater observations (bill_seq > 0): {len(later_obs)}")
rate_range = later_obs['prior_nonrecovery_rate']
print(f"  prior_nonrecovery_rate: min={rate_range.min():.4f}, max={rate_range.max():.4f}")
out_of_range = ((rate_range < 0) | (rate_range > 1)).sum()
print(f"  Out of [0,1] range: {out_of_range}")

print("\nDONE")
