"""
Phase 16B — Billing.csv duplicate investigation.
Are these legitimate re-billings or exact row duplicates?
"""
import pandas as pd
import numpy as np

chunk = pd.read_csv("dataset/billing.csv", nrows=500000, low_memory=False)

# Look at subscriber-months with 2 rows
sub_month = chunk.groupby(['subscriber_id', 'year_month']).size()
dup_keys = sub_month[sub_month > 1].index

# Sample some duplicated subscriber-months
print("Sample duplicated subscriber-months:")
for i, (sub, ym) in enumerate(dup_keys[:5]):
    rows = chunk[(chunk['subscriber_id'] == sub) & (chunk['year_month'] == ym)]
    print(f"\n--- {sub}, {ym} ---")
    print(rows.to_string())
    # Are they exact duplicates?
    if len(rows) == 2:
        r1, r2 = rows.iloc[0], rows.iloc[1]
        is_exact = (r1 == r2).all()
        print(f"  Exact duplicate: {is_exact}")
        if not is_exact:
            for col in rows.columns:
                if r1[col] != r2[col]:
                    print(f"  Differs on: {col} -> {r1[col]} vs {r2[col]}")

# Count exact duplicates globally in the chunk
print(f"\n\nExact row duplicates in first 500k: {chunk.duplicated(keep=False).sum()}")
print(f"Rows that are first occurrence of a duplicate: {chunk.duplicated(keep='first').sum()}")

# Check if the second row in a subscriber-month always has different payment_status
print("\n\nChecking if duplicates have different payment statuses:")
for i, (sub, ym) in enumerate(dup_keys[:20]):
    rows = chunk[(chunk['subscriber_id'] == sub) & (chunk['year_month'] == ym)]
    statuses = rows['payment_status'].tolist()
    fees = rows['late_fee_usd'].tolist()
    totals = rows['total_billed_usd'].tolist()
    if statuses[0] != statuses[1] or fees[0] != fees[1]:
        print(f"  {sub} {ym}: statuses={statuses}, late_fees={fees}, totals={totals}")

# Is 2026-02 missing? 
print("\n\nYear-month values present:")
print(sorted(chunk['year_month'].unique()))

print("\nDONE")
