"""
Phase 16D — Selection bias analysis.
Does excluding conflicting-status subscriber-months introduce systematic bias?
Compare the characteristics of excluded vs retained records.
"""
import pandas as pd
import numpy as np

raw = pd.read_csv("dataset/billing.csv", low_memory=False)
raw = raw.drop_duplicates()  # drop exact dupes first

# Identify conflicting subscriber-months
sm_counts = raw.groupby(['subscriber_id', 'year_month']).size()
dup_keys = sm_counts[sm_counts == 2].index

dup_mask = raw.set_index(['subscriber_id', 'year_month']).index.isin(dup_keys)
dups = raw[dup_mask].copy()
dups['row_num'] = dups.groupby(['subscriber_id', 'year_month']).cumcount()

r0 = dups[dups['row_num'] == 0].set_index(['subscriber_id', 'year_month'])
r1 = dups[dups['row_num'] == 1].set_index(['subscriber_id', 'year_month'])
conflicting = (r0['payment_status'] != r1['payment_status'])
conflict_keys = set(conflicting[conflicting].index)

# Tag every raw row
raw['sm_key'] = list(zip(raw['subscriber_id'], raw['year_month']))
raw['is_conflict'] = raw['sm_key'].apply(lambda x: x in conflict_keys)
raw['is_single'] = raw.set_index(['subscriber_id', 'year_month']).index.isin(sm_counts[sm_counts == 1].index)

# Compare distributions
retained = raw[~raw['is_conflict']]
excluded = raw[raw['is_conflict']]

print("=" * 80)
print("SELECTION BIAS ANALYSIS")
print("=" * 80)

print(f"\nRetained rows: {len(retained)} ({len(retained)/len(raw)*100:.1f}%)")
print(f"Excluded rows: {len(excluded)} ({len(excluded)/len(raw)*100:.1f}%)")

# 1. Year-month distribution
print("\n--- Year-month distribution (conflict % by month) ---")
for ym in sorted(raw['year_month'].unique()):
    ym_total = (raw['year_month'] == ym).sum()
    ym_conflict = ((raw['year_month'] == ym) & raw['is_conflict']).sum()
    print(f"  {ym}: {ym_conflict}/{ym_total} ({ym_conflict/ym_total*100:.1f}% excluded)")

# 2. Charge amount comparison
print("\n--- Charge amount comparison ---")
print(f"  Retained mean base_charge: {retained['base_charge_usd'].mean():.2f}")
print(f"  Excluded mean base_charge: {excluded['base_charge_usd'].mean():.2f}")
print(f"  Retained mean total_billed: {retained['total_billed_usd'].mean():.2f}")
print(f"  Excluded mean total_billed: {excluded['total_billed_usd'].mean():.2f}")

# 3. Payment status distribution in each group
print("\n--- Payment status in retained ---")
print(retained['payment_status'].value_counts(normalize=True).round(4))
print("\n--- Payment status in excluded (both rows per conflict) ---")
print(excluded['payment_status'].value_counts(normalize=True).round(4))

# 4. Subscriber concentration
retained_subs = retained['subscriber_id'].nunique()
excluded_subs = excluded['subscriber_id'].nunique()
both = len(set(retained['subscriber_id'].unique()) & set(excluded['subscriber_id'].unique()))
print(f"\n--- Subscriber overlap ---")
print(f"  Retained subscribers: {retained_subs}")
print(f"  Excluded subscribers: {excluded_subs}")
print(f"  In both: {both}")

# 5. Key question: are excluded conflicts disproportionately "failure" cases?
# If so, excluding them biases the dataset toward success
print("\n--- Bias assessment ---")
# In retained, what fraction is Failed/Unpaid?
ret_fail = retained['payment_status'].isin(['Failed', 'Unpaid']).mean()
# In excluded, what fraction of ROWS is Failed/Unpaid?
exc_fail = excluded['payment_status'].isin(['Failed', 'Unpaid']).mean()
print(f"  Failure rate in retained: {ret_fail*100:.2f}%")
print(f"  Failure rate in excluded: {exc_fail*100:.2f}%")
print(f"  Difference: {(exc_fail - ret_fail)*100:.2f} percentage points")

if exc_fail > ret_fail + 0.02:
    print("  WARNING: Excluded records have higher failure rate -> exclusion biases toward success")
elif exc_fail < ret_fail - 0.02:
    print("  WARNING: Excluded records have lower failure rate -> exclusion biases toward failure")
else:
    print("  OK: Failure rates are comparable -> minimal selection bias")

print("\nDONE")
