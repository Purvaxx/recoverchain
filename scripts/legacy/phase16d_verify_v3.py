"""
Phase 16D — Deterministic Verification of billing_recovery_v3.
"""
import pandas as pd
import numpy as np
import json
import os
import hashlib

PASS = 0
FAIL = 0
WARN = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {name}" + (f" — {detail}" if detail else ""))

print("=" * 80)
print("BILLING_RECOVERY_V3 VERIFICATION")
print("=" * 80)

# Load full v3 data
try:
    b = pd.read_csv("backend/evaluation/datasets/billing_recovery_v3.csv")
    print(f"Loaded v3: {len(b)} rows")
except Exception as e:
    print(f"Failed to load dataset: {e}")
    exit(1)

# 1. Duplicate checks
dup_sm = b.duplicated(subset=['subscriber_id', 'year_month']).sum()
check("No duplicate subscriber-months", dup_sm == 0, f"found={dup_sm}")

# 2. Columns & Leakage
cols = list(b.columns)
leakage = ['payment_status', 'days_to_payment', 'late_fee_usd', 'total_billed_usd']
for lc in leakage:
    check(f"Leakage column '{lc}' absent", lc not in cols)

# 3. Target validity
check("target_recovered exists", 'target_recovered' in cols)
check("target_recovered is binary", set(b['target_recovered'].dropna().unique()) == {0, 1})

# 4. Nulls
nulls = b.isnull().sum().sum()
check("No nulls in dataset", nulls == 0, f"found={nulls}")

# 5. History temporal correctness (Crucial)
# Ensure history features do not leak the current row's target.
first_obs = b[b['bill_seq'] == 0]
check("First obs: prior_failures == 0", (first_obs['prior_failures'] == 0).all())
check("First obs: prior_nonrecovery_rate == -1", (first_obs['prior_nonrecovery_rate'] == -1).all())

# Manual temporal verification on a sample of subscribers
sample_subs = b['subscriber_id'].unique()[:50]
history_correct = True
for sub in sample_subs:
    sub_rows = b[b['subscriber_id'] == sub].sort_values('year_month')
    for idx, row in sub_rows.iterrows():
        seq = row['bill_seq']
        prior = sub_rows[sub_rows['bill_seq'] < seq]
        expected_nonrec = (prior['target_recovered'] == 0).sum()
        if expected_nonrec != row['prior_nonrecovery_count']:
            history_correct = False
            print(f"History mismatch for sub {sub}, seq {seq}: expected {expected_nonrec}, got {row['prior_nonrecovery_count']}")
            break
    if not history_correct:
        break
check("History features strictly respect temporal cutoff (verified on sample)", history_correct)

# 6. Class Distribution
pos = b['target_recovered'].sum()
neg = len(b) - pos
rate = pos / len(b)
print(f"\nClass Distribution:")
print(f"  Target=1 (No Failure Observed): {pos} ({rate*100:.2f}%)")
print(f"  Target=0 (Failure Observed): {neg} ({(1-rate)*100:.2f}%)")
print(f"  Imbalance Ratio: {pos/neg:.1f} : 1")
check("Minority class is non-zero", neg > 0)

# 7. Distribution Shift
print("\nTemporal Split Distribution:")
split_stats = b.groupby('split')['target_recovered'].agg(['count', 'mean'])
print(split_stats.round(4))
train_rate = split_stats.loc['train', 'mean']
test_rate = split_stats.loc['test', 'mean']
check("Splits exist", len(split_stats) == 3)
if abs(train_rate - test_rate) > 0.01:
    warn("Distribution shift detected", f"Train={train_rate:.3f}, Test={test_rate:.3f}")

# 8. Entity Leakage
train_subs = set(b[b['split'] == 'train']['subscriber_id'].unique())
test_subs = set(b[b['split'] == 'test']['subscriber_id'].unique())
overlap = len(train_subs & test_subs)
if overlap > 0:
    warn("Entity Leakage", f"{overlap} subscribers overlap between train and test splits")

# 9. AR Dataset Check
print("\n" + "=" * 80)
print("AR_RECOVERY_V2 VERIFICATION (Benchmark)")
print("=" * 80)
try:
    ar = pd.read_csv("backend/evaluation/datasets/ar_recovery_v2.csv")
    check("AR v2 exists", True)
    check("AR payment_window_days excluded", 'payment_window_days' not in ar.columns)
    check("AR DaysLate excluded", 'DaysLate' not in ar.columns)
except Exception as e:
    check("AR v2 exists", False, str(e))

print("\n" + "=" * 80)
print(f"VERIFICATION SUMMARY: {PASS} passed, {FAIL} failed, {WARN} warnings")
print("=" * 80)
