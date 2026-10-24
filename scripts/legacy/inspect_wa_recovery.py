"""
Phase 16B — WA_Fn recovery semantics investigation.
If ALL invoices settled, what does "recovery" mean?
"""
import pandas as pd
import numpy as np

wa = pd.read_csv("dataset/WA_Fn-UseC_-Accounts-Receivable.csv")

# Key question: If ALL invoices settled, then "recovery probability" is always 1.0.
# That means this dataset cannot serve as a binary RECOVERED / NOT_RECOVERED target.
# Instead, we should investigate:
# 1. DaysLate > 0 as "at-risk" vs DaysLate == 0 as "on-time"
# 2. Disputed as a risk factor

print("=" * 80)
print("WA_Fn — RECOVERY SEMANTICS AUDIT")
print("=" * 80)

# All invoices settled
print(f"\nSettledDate non-null: {wa['SettledDate'].notnull().sum()} / {len(wa)}")
print(f"ALL INVOICES SETTLED: {'YES' if wa['SettledDate'].notnull().all() else 'NO'}")

# DaysLate distribution
print(f"\n--- DaysLate as potential target ---")
print(f"On-time (DaysLate == 0): {(wa['DaysLate'] == 0).sum()} ({(wa['DaysLate'] == 0).mean()*100:.1f}%)")
print(f"Late (DaysLate > 0):    {(wa['DaysLate'] > 0).sum()} ({(wa['DaysLate'] > 0).mean()*100:.1f}%)")
print(f"Mean DaysLate when late: {wa.loc[wa['DaysLate'] > 0, 'DaysLate'].mean():.1f}")
print(f"Max DaysLate: {wa['DaysLate'].max()}")

# Disputed vs DaysLate cross-tabulation
print(f"\n--- Disputed vs Late ---")
ct = pd.crosstab(wa['Disputed'], wa['DaysLate'] > 0, margins=True)
ct.columns = ['On Time', 'Late', 'Total']
print(ct)

# InvoiceAmount vs DaysLate
print(f"\n--- InvoiceAmount vs DaysLate ---")
print(f"Mean amount (on-time): {wa.loc[wa['DaysLate']==0, 'InvoiceAmount'].mean():.2f}")
print(f"Mean amount (late):    {wa.loc[wa['DaysLate']>0, 'InvoiceAmount'].mean():.2f}")

# countryCode vs DaysLate
print(f"\n--- countryCode vs DaysLate > 0 ---")
ct2 = pd.crosstab(wa['countryCode'], wa['DaysLate'] > 0, normalize='index')
ct2.columns = ['On Time %', 'Late %']
print(ct2.round(3))

# PaperlessBill vs DaysLate
print(f"\n--- PaperlessBill vs Late ---")
ct3 = pd.crosstab(wa['PaperlessBill'], wa['DaysLate'] > 0, normalize='index')
ct3.columns = ['On Time %', 'Late %']
print(ct3.round(3))

# Customer settlement history — can we build features?
print(f"\n--- Customer history potential ---")
wa['InvoiceDate_parsed'] = pd.to_datetime(wa['InvoiceDate'])
wa = wa.sort_values(['customerID', 'InvoiceDate_parsed'])
# For each invoice, count prior invoices and prior late invoices
wa['invoice_seq'] = wa.groupby('customerID').cumcount()
wa['is_late'] = (wa['DaysLate'] > 0).astype(int)
wa['prior_late_count'] = wa.groupby('customerID')['is_late'].cumsum() - wa['is_late']
wa['prior_invoice_count'] = wa['invoice_seq']
wa['prior_late_rate'] = wa['prior_late_count'] / wa['prior_invoice_count'].replace(0, np.nan)

print(f"Customers with history (>= 5 invoices): {(wa.groupby('customerID').size() >= 5).sum()}")
print(f"Mean prior_late_rate (where available): {wa['prior_late_rate'].dropna().mean():.3f}")

# Does prior_late_rate predict current late?
print(f"\n--- Prior late rate vs current lateness ---")
has_history = wa[wa['prior_invoice_count'] >= 3]
print(f"Rows with 3+ prior invoices: {len(has_history)}")
print(f"Late rate when prior_late_rate == 0: {has_history.loc[has_history['prior_late_rate']==0, 'is_late'].mean():.3f}")
print(f"Late rate when prior_late_rate > 0.3: {has_history.loc[has_history['prior_late_rate']>0.3, 'is_late'].mean():.3f}")

print("\nDONE")
