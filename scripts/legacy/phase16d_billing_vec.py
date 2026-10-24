"""
Phase 16D — Vectorized billing duplicate analysis.
"""
import pandas as pd
import numpy as np

raw = pd.read_csv("dataset/billing.csv", low_memory=False)
print(f"Raw rows: {len(raw)}")

# Find subscriber-months with exactly 2 rows
sm_counts = raw.groupby(['subscriber_id', 'year_month']).size()
dup_keys = sm_counts[sm_counts == 2].index
print(f"Subscriber-months with 2 rows: {len(dup_keys)}")

# For each dup subscriber-month, self-join to get both rows side by side
dup_mask = raw.set_index(['subscriber_id', 'year_month']).index.isin(dup_keys)
dups = raw[dup_mask].copy()
print(f"Rows in duplicate groups: {len(dups)}")

# Number them within group
dups['row_num'] = dups.groupby(['subscriber_id', 'year_month']).cumcount()

r0 = dups[dups['row_num'] == 0].set_index(['subscriber_id', 'year_month'])
r1 = dups[dups['row_num'] == 1].set_index(['subscriber_id', 'year_month'])

# Compare
charge_cols = ['base_charge_usd', 'data_overage_usd', 'intl_roaming_usd', 'tax_usd']
compare_cols = [c for c in raw.columns if c not in ['subscriber_id', 'year_month']]

same_status = r0['payment_status'] == r1['payment_status']
same_charges = (r0[charge_cols] == r1[charge_cols]).all(axis=1)
same_all = (r0[compare_cols] == r1[compare_cols]).all(axis=1)

exact_dup = same_all.sum()
status_conflict = (~same_status).sum()
charge_only_diff = (same_status & ~same_charges).sum()
late_fee_diff = (same_status & same_charges & ~same_all).sum()

print(f"\nClassification of {len(dup_keys)} duplicate subscriber-months:")
print(f"  Exact duplicates: {exact_dup} ({exact_dup/len(dup_keys)*100:.1f}%)")
print(f"  Same status, diff charges: {charge_only_diff} ({charge_only_diff/len(dup_keys)*100:.1f}%)")
print(f"  Same status, same charges, diff late_fee/total: {late_fee_diff} ({late_fee_diff/len(dup_keys)*100:.1f}%)")
print(f"  CONFLICTING payment_status: {status_conflict} ({status_conflict/len(dup_keys)*100:.1f}%)")

# Status conflict combinations
conflicts = pd.DataFrame({
    's0': r0.loc[~same_status, 'payment_status'],
    's1': r1.loc[~same_status, 'payment_status']
})
conflicts['combo'] = conflicts.apply(lambda x: tuple(sorted([x['s0'], x['s1']])), axis=1)
print(f"\nStatus conflict combinations:")
print(conflicts['combo'].value_counts())

# For status conflicts with same charges: these are likely rebillings/corrections
conflict_same_charges = (~same_status & same_charges).sum()
conflict_diff_charges = (~same_status & ~same_charges).sum()
print(f"\nConflicts with SAME charges: {conflict_same_charges}")
print(f"Conflicts with DIFFERENT charges: {conflict_diff_charges}")

# Subscriber coverage
subs_with_conflict = r0.loc[~same_status].reset_index()['subscriber_id'].nunique()
total_subs = raw['subscriber_id'].nunique()
print(f"\nSubscribers with >=1 status conflict: {subs_with_conflict} / {total_subs} ({subs_with_conflict/total_subs*100:.1f}%)")

# "Failed" temporal analysis — is Failed usually followed by recovery?
print("\n--- FAILED RECOVERY ANALYSIS (vectorized) ---")
deduped = raw.drop_duplicates(subset=['subscriber_id', 'year_month', 'payment_status'])
deduped = deduped.sort_values(['subscriber_id', 'year_month'])

# For each subscriber, find if they have Failed AND a subsequent Paid
sub_statuses = deduped.groupby('subscriber_id')['payment_status'].apply(list)
failed_subs = sub_statuses[sub_statuses.apply(lambda x: 'Failed' in x)]
print(f"Subscribers with at least one Failed: {len(failed_subs)}")

recovered = 0
not_recovered = 0
for statuses in failed_subs:
    found_fail = False
    found_rec = False
    for s in statuses:
        if s == 'Failed':
            found_fail = True
        elif found_fail and s in ['Paid On Time', 'Paid Late']:
            found_rec = True
            break
    if found_rec:
        recovered += 1
    else:
        not_recovered += 1

print(f"  Later recovered: {recovered} ({recovered/len(failed_subs)*100:.1f}%)")
print(f"  No subsequent recovery: {not_recovered} ({not_recovered/len(failed_subs)*100:.1f}%)")

# Similarly for Unpaid
unpaid_subs = sub_statuses[sub_statuses.apply(lambda x: 'Unpaid' in x)]
print(f"\nSubscribers with at least one Unpaid: {len(unpaid_subs)}")
urec = 0
unot = 0
for statuses in unpaid_subs:
    found = False
    found_r = False
    for s in statuses:
        if s == 'Unpaid':
            found = True
        elif found and s in ['Paid On Time', 'Paid Late']:
            found_r = True
            break
    if found_r:
        urec += 1
    else:
        unot += 1

print(f"  Later recovered: {urec} ({urec/len(unpaid_subs)*100:.1f}%)")
print(f"  No subsequent recovery: {unot} ({unot/len(unpaid_subs)*100:.1f}%)")

print("\nDONE")
