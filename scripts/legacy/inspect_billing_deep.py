"""
Phase 16B — Deeper analysis of billing.csv
Check full dataset stats, duplicate analysis, and temporal structure.
"""
import pandas as pd
import numpy as np

print("=" * 80)
print("BILLING.CSV — FULL DATASET ANALYSIS (chunked)")
print("=" * 80)

# Count total rows and unique subscribers
total_rows = 0
status_counts = {}
subscriber_set = set()
year_month_counts = {}

for chunk in pd.read_csv("dataset/billing.csv", chunksize=500000, low_memory=False):
    total_rows += len(chunk)
    for s, c in chunk['payment_status'].value_counts().items():
        status_counts[s] = status_counts.get(s, 0) + c
    subscriber_set.update(chunk['subscriber_id'].unique())
    for ym, c in chunk['year_month'].value_counts().items():
        year_month_counts[ym] = year_month_counts.get(ym, 0) + c

print(f"Total rows: {total_rows}")
print(f"Unique subscribers: {len(subscriber_set)}")
print(f"\nPayment Status Distribution:")
for k, v in sorted(status_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total_rows*100:.2f}%)")

print(f"\nYear-Month Distribution:")
for k, v in sorted(year_month_counts.items()):
    print(f"  {k}: {v}")

# Check for exact duplicate rows in first 500k
chunk1 = pd.read_csv("dataset/billing.csv", nrows=500000, low_memory=False)
print(f"\nDuplicate analysis (first 500k):")
print(f"  Exact duplicates: {chunk1.duplicated().sum()}")
print(f"  Subscriber+YearMonth duplicates: {chunk1.duplicated(subset=['subscriber_id', 'year_month']).sum()}")

# Check subscriber with multiple rows in same month
sub_month = chunk1.groupby(['subscriber_id', 'year_month']).size()
print(f"  Max rows per subscriber-month: {sub_month.max()}")
print(f"  Subscriber-months with >1 row: {(sub_month > 1).sum()}")
print(f"  Distribution of rows per subscriber-month:")
print(sub_month.value_counts().sort_index())

# What does a single subscriber look like?
sample_sub = chunk1[chunk1['subscriber_id'] == 'SUB0000001'].sort_values('year_month')
print(f"\nSample subscriber SUB0000001:")
print(sample_sub.to_string())

# Check if subscriber_id + year_month + base_charge is unique
print(f"\n  Subscriber+YearMonth+BaseCharge duplicates: {chunk1.duplicated(subset=['subscriber_id', 'year_month', 'base_charge_usd']).sum()}")

print("\n\nDONE")
