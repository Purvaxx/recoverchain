"""
Phase 16C — Deep billing.csv validation.
Independently verify all Phase 16B claims.
"""
import pandas as pd
import numpy as np
import hashlib
import os

print("=" * 80)
print("PHASE 16C: BILLING.CSV DEEP VALIDATION")
print("=" * 80)

# 1. Hash the original file for lineage
h = hashlib.sha256()
with open("dataset/billing.csv", "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        h.update(chunk)
print(f"Original file SHA256: {h.hexdigest()}")
print(f"Original file size: {os.path.getsize('dataset/billing.csv')} bytes")

# 2. Load raw data in chunks to understand the EXACT duplicate situation
print("\n--- RAW DUPLICATE ANALYSIS ---")
raw_chunks = []
for chunk in pd.read_csv("dataset/billing.csv", chunksize=500000, low_memory=False):
    raw_chunks.append(chunk)
raw = pd.concat(raw_chunks, ignore_index=True)
print(f"Raw rows: {len(raw)}")

# Exact duplicates
exact_dup_count = raw.duplicated().sum()
print(f"Exact duplicate rows: {exact_dup_count}")

# Subscriber-month groups
sm_groups = raw.groupby(['subscriber_id', 'year_month'])
sm_sizes = sm_groups.size()
print(f"\nSubscriber-month pairs: {len(sm_sizes)}")
print(f"Subscriber-months with 1 row: {(sm_sizes == 1).sum()}")
print(f"Subscriber-months with 2 rows: {(sm_sizes == 2).sum()}")
print(f"Subscriber-months with >2 rows: {(sm_sizes > 2).sum()}")

# 3. Investigate ALL subscriber-months with 2 rows — classify them
print("\n--- CLASSIFYING DUPLICATE SUBSCRIBER-MONTHS ---")
dup_sm = sm_sizes[sm_sizes == 2].index
sample_size = min(10000, len(dup_sm))
np.random.seed(42)
sample_indices = np.random.choice(len(dup_sm), sample_size, replace=False)

exact_dup = 0
differ_late_fee_only = 0
differ_payment_status = 0
differ_other = 0
conflicting_status_examples = []

for idx in sample_indices:
    sub, ym = dup_sm[idx]
    rows = raw[(raw['subscriber_id'] == sub) & (raw['year_month'] == ym)]
    r1, r2 = rows.iloc[0], rows.iloc[1]
    
    if (r1 == r2).all():
        exact_dup += 1
    else:
        diffs = [c for c in rows.columns if r1[c] != r2[c]]
        if diffs == ['late_fee_usd', 'total_billed_usd']:
            differ_late_fee_only += 1
        elif diffs == ['late_fee_usd']:
            differ_late_fee_only += 1
        elif 'payment_status' in diffs:
            differ_payment_status += 1
            if len(conflicting_status_examples) < 5:
                conflicting_status_examples.append({
                    'subscriber': sub, 'year_month': ym,
                    'status1': r1['payment_status'], 'status2': r2['payment_status'],
                    'diffs': diffs
                })
        else:
            differ_other += 1

print(f"Sampled {sample_size} duplicate subscriber-months:")
print(f"  Exact duplicates: {exact_dup} ({exact_dup/sample_size*100:.1f}%)")
print(f"  Differ on late_fee only: {differ_late_fee_only} ({differ_late_fee_only/sample_size*100:.1f}%)")
print(f"  Differ on payment_status: {differ_payment_status} ({differ_payment_status/sample_size*100:.1f}%)")
print(f"  Differ on other fields: {differ_other} ({differ_other/sample_size*100:.1f}%)")

if conflicting_status_examples:
    print(f"\nConflicting payment_status examples:")
    for ex in conflicting_status_examples:
        print(f"  {ex['subscriber']} {ex['year_month']}: {ex['status1']} vs {ex['status2']}, diffs={ex['diffs']}")

# 4. Investigate what "Failed" actually means
print("\n--- FAILED vs UNPAID SEMANTICS ---")
# Do subscribers who have "Failed" in one month show "Paid" in a later month?
raw_sorted = raw.sort_values(['subscriber_id', 'year_month'])
failed_subs = raw[raw['payment_status'] == 'Failed']['subscriber_id'].unique()
print(f"Subscribers with at least one Failed: {len(failed_subs)}")

# For failed subscribers, look at subsequent months
recovery_after_fail = 0
no_recovery_after_fail = 0
for sub in failed_subs[:500]:  # sample
    sub_rows = raw_sorted[raw_sorted['subscriber_id'] == sub].drop_duplicates()
    statuses = sub_rows['payment_status'].tolist()
    months = sub_rows['year_month'].tolist()
    
    found_fail = False
    found_recovery = False
    for s in statuses:
        if s == 'Failed':
            found_fail = True
        elif found_fail and s in ['Paid On Time', 'Paid Late']:
            found_recovery = True
            break
    
    if found_fail and found_recovery:
        recovery_after_fail += 1
    elif found_fail:
        no_recovery_after_fail += 1

print(f"Subscribers (sampled 500 with Failed):")
print(f"  Later recovered (paid in subsequent month): {recovery_after_fail}")
print(f"  No subsequent recovery observed: {no_recovery_after_fail}")

# 5. Check days_to_payment semantics precisely
print("\n--- DAYS_TO_PAYMENT DEEP CHECK ---")
for status in ['Paid On Time', 'Paid Late', 'Failed', 'Unpaid']:
    subset = raw[raw['payment_status'] == status]
    d2p = subset['days_to_payment']
    print(f"  {status}: count={len(subset)}, mean_d2p={d2p.mean():.1f}, "
          f"min={d2p.min()}, max={d2p.max()}, "
          f"zero_pct={((d2p==0).sum()/len(subset)*100):.1f}%")

# 6. Check for impossible values
print("\n--- IMPOSSIBLE VALUES CHECK ---")
print(f"Negative amounts: {(raw['base_charge_usd'] < 0).sum()}")
print(f"Negative total: {(raw['total_billed_usd'] < 0).sum()}")
print(f"Negative days_to_payment: {(raw['days_to_payment'] < 0).sum()}")
print(f"Zero base_charge: {(raw['base_charge_usd'] == 0).sum()}")

# 7. Subscriber continuity
print("\n--- SUBSCRIBER CONTINUITY ---")
sub_months = raw.drop_duplicates(subset=['subscriber_id', 'year_month'])
sub_month_counts = sub_months.groupby('subscriber_id').size()
print(f"Min months per subscriber: {sub_month_counts.min()}")
print(f"Max months per subscriber: {sub_month_counts.max()}")
print(f"Mean months per subscriber: {sub_month_counts.mean():.1f}")
print(f"Median months per subscriber: {sub_month_counts.median()}")

all_months = sorted(raw['year_month'].unique())
print(f"All year_months in data: {all_months}")
print(f"Total distinct months: {len(all_months)}")

print("\nDONE")
