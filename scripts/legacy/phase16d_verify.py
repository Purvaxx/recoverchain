"""
Phase 16D — Independent v2 dataset verification.
Checks every claim in the manifest against the actual data on disk.
Also performs the temporal leakage recheck and entity leakage analysis.
"""
import pandas as pd
import numpy as np
import json
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

# =====================================================================
# BILLING v2
# =====================================================================
print("=" * 80)
print("BILLING_RECOVERY_V2 VERIFICATION")
print("=" * 80)

b = pd.read_csv("backend/evaluation/datasets/billing_recovery_v2.csv", nrows=500000)
b_full_rows = sum(1 for _ in open("backend/evaluation/datasets/billing_recovery_v2.csv")) - 1
print(f"Total rows (line count): {b_full_rows}")

with open("backend/evaluation/datasets/billing_recovery_v2_metadata.json") as f:
    bmeta = json.load(f)

# 1. Row count matches manifest
check("Row count matches manifest",
      b_full_rows == 3400565,
      f"actual={b_full_rows}, manifest=3400565")

# 2. Columns check — no leakage columns
cols = list(b.columns)
print(f"\nColumns: {cols}")
leakage = ['payment_status', 'days_to_payment', 'late_fee_usd', 'total_billed_usd']
for lc in leakage:
    check(f"Leakage column '{lc}' absent", lc not in cols)

# 3. Target exists and is binary
check("target_recovered exists", 'target_recovered' in cols)
check("target_recovered is binary", set(b['target_recovered'].unique()) == {0, 1})

# 4. Split column exists
check("split column exists", 'split' in cols)
check("split values valid", set(b['split'].unique()) <= {'train', 'validation', 'test'})

# 5. No nulls in sample
check("No nulls (sample)", b.isnull().sum().sum() == 0)

# 6. No duplicate subscriber-months
dup_sm = b.duplicated(subset=['subscriber_id', 'year_month'], keep=False).sum()
check("No duplicate subscriber-months (sample)", dup_sm == 0, f"found={dup_sm}")

# 7. History feature temporal correctness
first_obs = b[b['bill_seq'] == 0]
check("First obs: prior_failures == 0", (first_obs['prior_failures'] == 0).all())
check("First obs: prior_nonrecovery_rate == -1", (first_obs['prior_nonrecovery_rate'] == -1).all())

# Manual verification for one subscriber
sample_sub = b['subscriber_id'].iloc[0]
sub_rows = b[b['subscriber_id'] == sample_sub].sort_values('year_month')
history_correct = True
for idx, row in sub_rows.iterrows():
    seq = row['bill_seq']
    prior = sub_rows[sub_rows['bill_seq'] < seq]
    expected_nonrec = ((prior['target_recovered'] == 0).sum())
    if expected_nonrec != row['prior_nonrecovery_count']:
        history_correct = False
        break
check("History features verified for sample subscriber", history_correct)

# 8. bill_amount_excl_late computed correctly
expected_amount = b['base_charge_usd'] + b['data_overage_usd'] + b['intl_roaming_usd'] + b['tax_usd']
check("bill_amount_excl_late correct", (abs(b['bill_amount_excl_late'] - expected_amount) < 0.01).all())

# 9. Value ranges
check("No negative base_charge", (b['base_charge_usd'] >= 0).all())
check("No negative data_overage", (b['data_overage_usd'] >= 0).all())
check("prior_nonrecovery_rate in [-1, 1]",
      ((b['prior_nonrecovery_rate'] >= -1) & (b['prior_nonrecovery_rate'] <= 1)).all())

# 10. Class distribution
pos = b['target_recovered'].sum()
neg = (1 - b['target_recovered']).sum()
rate = pos / len(b)
print(f"\nClass distribution (sample):")
print(f"  Recovered: {pos} ({rate*100:.2f}%)")
print(f"  Not recovered: {neg} ({(1-rate)*100:.2f}%)")
check("Class distribution close to manifest", abs(rate - 0.9606) < 0.01)

# 11. Temporal split counts
split_stats = b.groupby('split')['target_recovered'].agg(['count', 'mean'])
print(f"\nSplit stats (sample):\n{split_stats.round(4)}")

# 12. Entity leakage
train_subs = set(b[b['split'] == 'train']['subscriber_id'].unique())
test_subs = set(b[b['split'] == 'test']['subscriber_id'].unique())
val_subs = set(b[b['split'] == 'validation']['subscriber_id'].unique())
overlap_tt = len(train_subs & test_subs)
print(f"\nEntity overlap:")
print(f"  Train subs: {len(train_subs)}, Test subs: {len(test_subs)}")
print(f"  Train-Test overlap: {overlap_tt} ({overlap_tt/max(len(train_subs),1)*100:.1f}%)")
warn("Entity leakage: ~100% subscriber overlap", "Expected for temporal split on subscription data")

# =====================================================================
# AR v2
# =====================================================================
print("\n" + "=" * 80)
print("AR_RECOVERY_V2 VERIFICATION")
print("=" * 80)

ar = pd.read_csv("backend/evaluation/datasets/ar_recovery_v2.csv")
print(f"Rows: {len(ar)}")
cols_ar = list(ar.columns)
print(f"Columns: {cols_ar}")

# 1. Row count
check("AR row count matches manifest", len(ar) == 2466)

# 2. payment_window_days DROPPED
check("payment_window_days removed", 'payment_window_days' not in cols_ar)

# 3. Leakage columns absent
for lc in ['DaysToSettle', 'DaysLate', 'SettledDate']:
    check(f"Leakage column '{lc}' absent", lc not in cols_ar)

# 4. Target exists and is binary
check("target_late exists", 'target_late' in cols_ar)
check("target_late is binary", set(ar['target_late'].unique()) == {0, 1})

# 5. No nulls
check("No nulls", ar.isnull().sum().sum() == 0)

# 6. Unique invoiceNumber
check("invoiceNumber unique", ar['invoiceNumber'].nunique() == len(ar))

# 7. Split exists
check("split exists", 'split' in cols_ar)

# 8. Class distribution
late_rate = ar['target_late'].mean()
print(f"\nAR class distribution:")
print(f"  Late: {ar['target_late'].sum()} ({late_rate*100:.1f}%)")
print(f"  On-time: {(1-ar['target_late']).sum()} ({(1-late_rate)*100:.1f}%)")
check("Late rate close to manifest", abs(late_rate - 0.3556) < 0.01)

# 9. is_disputed flagged as ambiguous
warn("is_disputed has ambiguous temporal availability", "Documented in manifest")

# 10. History feature verification
sample_cust = ar['customerID'].iloc[0]
cust_rows = ar[ar['customerID'] == sample_cust].sort_values('InvoiceDate')
ar_history_ok = True
for idx, row in cust_rows.iterrows():
    seq = row['invoice_seq']
    prior = cust_rows[cust_rows['invoice_seq'] < seq]
    expected = prior['target_late'].sum()
    if expected != row['prior_late_count']:
        ar_history_ok = False
        break
check("AR history features verified for sample customer", ar_history_ok)

# 11. AR temporal split
ar_split = ar.groupby('split')['target_late'].agg(['count', 'mean'])
print(f"\nAR split stats:\n{ar_split.round(4)}")
warn("AR distribution shift", f"Late rate: train={ar_split.loc['train','mean']:.3f} -> test={ar_split.loc['test','mean']:.3f}")

# =====================================================================
# ORIGINAL FILES UNTOUCHED
# =====================================================================
print("\n" + "=" * 80)
print("SOURCE FILE INTEGRITY")
print("=" * 80)

import os
billing_size = os.path.getsize("dataset/billing.csv")
check("billing.csv size unchanged", billing_size == 273574298, f"actual={billing_size}")

h = hashlib.sha256()
with open("dataset/WA_Fn-UseC_-Accounts-Receivable.csv", "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        h.update(chunk)
ar_hash = h.hexdigest()
check("WA_Fn SHA256 matches manifest", ar_hash == "651bc4225708bf33148a0e177c9221afdf697d3a4de10333725a4af3dd022fcf")

# =====================================================================
# SUMMARY
# =====================================================================
print("\n" + "=" * 80)
print(f"VERIFICATION SUMMARY: {PASS} passed, {FAIL} failed, {WARN} warnings")
print("=" * 80)
