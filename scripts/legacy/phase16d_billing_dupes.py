"""
Phase 16D — Billing duplicate semantics investigation.
Determine whether conflicting-status rows represent:
  A. Correction/rebilling (keep the latest/final record)
  B. Separate line items (aggregate)
  C. Data quality issue (flag and exclude)
"""
import pandas as pd
import numpy as np

raw = pd.read_csv("dataset/billing.csv", low_memory=False)
print(f"Raw rows: {len(raw)}")

# Focus on subscriber-months with exactly 2 rows
sm = raw.groupby(['subscriber_id', 'year_month'])
sm_sizes = sm.size()
dup_sm = sm_sizes[sm_sizes == 2].index

print(f"Subscriber-months with 2 rows: {len(dup_sm)}")

# Classify ALL duplicates (not just a sample)
exact = 0
late_fee_only = 0
status_conflict = 0
charge_diff = 0

# Also track: for status conflicts, which status combinations appear?
status_combos = {}

for sub, ym in dup_sm:
    rows = raw[(raw['subscriber_id'] == sub) & (raw['year_month'] == ym)]
    r1, r2 = rows.iloc[0], rows.iloc[1]
    
    if (r1 == r2).all():
        exact += 1
    else:
        diffs = [c for c in rows.columns if r1[c] != r2[c]]
        if 'payment_status' in diffs:
            status_conflict += 1
            combo = tuple(sorted([r1['payment_status'], r2['payment_status']]))
            status_combos[combo] = status_combos.get(combo, 0) + 1
        elif set(diffs) <= {'late_fee_usd', 'total_billed_usd'}:
            late_fee_only += 1
        else:
            charge_diff += 1

print(f"\nClassification of ALL {len(dup_sm)} duplicate subscriber-months:")
print(f"  Exact duplicates: {exact} ({exact/len(dup_sm)*100:.1f}%)")
print(f"  Differ on late_fee/total only: {late_fee_only} ({late_fee_only/len(dup_sm)*100:.1f}%)")
print(f"  CONFLICTING payment_status: {status_conflict} ({status_conflict/len(dup_sm)*100:.1f}%)")
print(f"  Differ on charges (no status conflict): {charge_diff} ({charge_diff/len(dup_sm)*100:.1f}%)")

print(f"\nStatus conflict combinations:")
for combo, count in sorted(status_combos.items(), key=lambda x: -x[1]):
    print(f"  {combo[0]} vs {combo[1]}: {count}")

# Key question: For "Failed vs Paid On Time" conflicts,
# do the rows differ on charges or just on status/days_to_payment?
print(f"\n--- Deep dive: Failed vs Paid On Time conflicts ---")
fp_count = 0
fp_same_charges = 0
fp_diff_charges = 0

for sub, ym in dup_sm:
    rows = raw[(raw['subscriber_id'] == sub) & (raw['year_month'] == ym)]
    r1, r2 = rows.iloc[0], rows.iloc[1]
    statuses = set([r1['payment_status'], r2['payment_status']])
    
    if statuses == {'Failed', 'Paid On Time'}:
        fp_count += 1
        charge_cols = ['base_charge_usd', 'data_overage_usd', 'intl_roaming_usd', 'tax_usd']
        charges_same = all(r1[c] == r2[c] for c in charge_cols)
        if charges_same:
            fp_same_charges += 1
        else:
            fp_diff_charges += 1
            if fp_diff_charges <= 3:
                print(f"  {sub} {ym}:")
                for c in charge_cols + ['late_fee_usd', 'total_billed_usd', 'payment_status', 'days_to_payment']:
                    if r1[c] != r2[c]:
                        print(f"    {c}: {r1[c]} vs {r2[c]}")

print(f"\nFailed vs Paid On Time: {fp_count} total")
print(f"  Same charges (likely rebilling/correction): {fp_same_charges}")
print(f"  Different charges (separate line items?): {fp_diff_charges}")

# Subscriber-level analysis: what fraction of subscribers have ANY status conflict?
subs_with_conflict = set()
for sub, ym in dup_sm:
    rows = raw[(raw['subscriber_id'] == sub) & (raw['year_month'] == ym)]
    if rows['payment_status'].nunique() > 1:
        subs_with_conflict.add(sub)

total_subs = raw['subscriber_id'].nunique()
print(f"\nSubscribers with at least one status conflict: {len(subs_with_conflict)} / {total_subs} ({len(subs_with_conflict)/total_subs*100:.1f}%)")

print("\nDONE")
