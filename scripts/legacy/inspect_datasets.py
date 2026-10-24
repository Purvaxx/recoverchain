"""
Phase 16B — Deep Dataset Inspection Script
Inspects both Tier-1 candidates and Tier-2 supporting datasets.
Outputs detailed analysis to stdout.
"""
import pandas as pd
import numpy as np
import json
import os

print("=" * 80)
print("DATASET 1: WA_Fn-UseC_-Accounts-Receivable.csv")
print("=" * 80)

wa = pd.read_csv("dataset/WA_Fn-UseC_-Accounts-Receivable.csv")
print(f"Shape: {wa.shape}")
print(f"\nColumns: {list(wa.columns)}")
print(f"\nDtypes:\n{wa.dtypes}")
print(f"\nFirst 5 rows:\n{wa.head()}")
print(f"\nDescribe:\n{wa.describe(include='all')}")
print(f"\nNull counts:\n{wa.isnull().sum()}")
print(f"\nDuplicate rows: {wa.duplicated().sum()}")

# Investigate key columns
print(f"\n--- countryCode ---")
print(wa['countryCode'].value_counts())
print(f"\n--- Disputed ---")
print(wa['Disputed'].value_counts())
print(f"\n--- PaperlessBill ---")
print(wa['PaperlessBill'].value_counts())

# Investigate SettledDate
print(f"\n--- SettledDate (sample) ---")
print(wa['SettledDate'].head(20))
print(f"SettledDate nulls: {wa['SettledDate'].isnull().sum()}")

# Investigate DaysToSettle and DaysLate
print(f"\n--- DaysToSettle ---")
print(wa['DaysToSettle'].describe())
print(f"\n--- DaysLate ---")
print(wa['DaysLate'].describe())
print(wa['DaysLate'].value_counts().head(20))

# Check if DaysLate > 0 means "late"
print(f"\nDaysLate > 0: {(wa['DaysLate'] > 0).sum()}")
print(f"DaysLate == 0: {(wa['DaysLate'] == 0).sum()}")
print(f"DaysLate < 0: {(wa['DaysLate'] < 0).sum()}")

# Investigate InvoiceAmount
print(f"\n--- InvoiceAmount ---")
print(wa['InvoiceAmount'].describe())

# Check customerID uniqueness
print(f"\n--- customerID ---")
print(f"Unique customers: {wa['customerID'].nunique()}")
print(f"Total invoices: {len(wa)}")
print(f"Invoices per customer:\n{wa['customerID'].value_counts().describe()}")

# Check invoiceNumber uniqueness
print(f"\n--- invoiceNumber ---")
print(f"Unique invoiceNumbers: {wa['invoiceNumber'].nunique()}")
print(f"Total rows: {len(wa)}")
dup_invoices = wa['invoiceNumber'].value_counts()
print(f"Max invoices with same number: {dup_invoices.max()}")
if dup_invoices.max() > 1:
    print("WARNING: invoiceNumber is NOT unique per row")
    print(dup_invoices[dup_invoices > 1].head())

# Date range
for col in ['PaperlessDate', 'InvoiceDate', 'DueDate', 'SettledDate']:
    try:
        parsed = pd.to_datetime(wa[col], errors='coerce')
        print(f"\n{col}: min={parsed.min()}, max={parsed.max()}, nulls={parsed.isnull().sum()}")
    except Exception as e:
        print(f"\n{col}: parse error: {e}")

print("\n\n")
print("=" * 80)
print("DATASET 2: billing.csv (first 100k rows for inspection)")
print("=" * 80)

billing = pd.read_csv("dataset/billing.csv", nrows=100000)
print(f"Shape (sample): {billing.shape}")
print(f"\nColumns: {list(billing.columns)}")
print(f"\nDtypes:\n{billing.dtypes}")
print(f"\nFirst 5 rows:\n{billing.head()}")
print(f"\nDescribe:\n{billing.describe(include='all')}")
print(f"\nNull counts:\n{billing.isnull().sum()}")

# payment_status
print(f"\n--- payment_status ---")
print(billing['payment_status'].value_counts())

# days_to_payment
print(f"\n--- days_to_payment ---")
print(billing['days_to_payment'].describe())
print(f"Nulls: {billing['days_to_payment'].isnull().sum()}")

# subscriber_id
print(f"\n--- subscriber_id ---")
print(f"Unique subscribers (in sample): {billing['subscriber_id'].nunique()}")
print(f"Sample values: {billing['subscriber_id'].head(10).tolist()}")

# year_month
print(f"\n--- year_month ---")
print(billing['year_month'].value_counts().sort_index())

# Financial columns
for col in ['base_charge_usd', 'total_billed_usd', 'late_fee_usd']:
    print(f"\n--- {col} ---")
    print(billing[col].describe())

print("\n\n")
print("=" * 80)
print("DATASET 3: fraud_data (Tier-2 supporting)")
print("=" * 80)

fraud = pd.read_csv("dataset/fraud_data_20251225_004640.csv")
print(f"Shape: {fraud.shape}")
print(f"\nColumns: {list(fraud.columns)}")
print(f"\nFirst 5 rows:\n{fraud.head()}")
print(f"\nNull counts:\n{fraud.isnull().sum()}")
print(f"\n--- status ---")
print(fraud['status'].value_counts())
print(f"\n--- error_code ---")
print(fraud['error_code'].value_counts().head(10))
print(f"\n--- payment_method ---")
print(fraud['payment_method'].value_counts())

print("\n\nDONE")
