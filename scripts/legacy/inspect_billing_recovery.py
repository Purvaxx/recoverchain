"""
Phase 16B — billing.csv recovery semantics and history construction investigation.
"""
import pandas as pd
import numpy as np

# Load a manageable chunk (first 1M rows) for detailed analysis
print("Loading billing.csv (first 1M rows)...")
df = pd.read_csv("dataset/billing.csv", nrows=1000000, low_memory=False)
print(f"Loaded shape: {df.shape}")

# First, drop exact duplicates for analysis
before = len(df)
df_dedup = df.drop_duplicates()
after = len(df_dedup)
print(f"\nExact duplicates dropped: {before - after}")
print(f"Rows after dedup: {after}")

# Define target semantics
# payment_status values: Paid On Time, Paid Late, Failed, Unpaid
# For P(Recovery), we need: was the billing obligation eventually settled?
# "Paid On Time" and "Paid Late" = RECOVERED (obligation met)
# "Failed" = unclear — was there a retry? or permanent failure?
# "Unpaid" = NOT RECOVERED

print("\n--- Payment Status after dedup ---")
print(df_dedup['payment_status'].value_counts())
print(df_dedup['payment_status'].value_counts(normalize=True).round(4))

# Binary target: Recovered = (Paid On Time | Paid Late), Not Recovered = (Failed | Unpaid)
df_dedup = df_dedup.copy()
df_dedup['recovered'] = df_dedup['payment_status'].isin(['Paid On Time', 'Paid Late']).astype(int)
print(f"\n--- Binary Recovery Target ---")
print(f"Recovered (1): {df_dedup['recovered'].sum()} ({df_dedup['recovered'].mean()*100:.2f}%)")
print(f"Not Recovered (0): {(1 - df_dedup['recovered']).sum()} ({(1-df_dedup['recovered']).mean()*100:.2f}%)")

# Subscriber history construction 
print("\n--- Subscriber payment history ---")
# Sort by subscriber and time
df_dedup = df_dedup.sort_values(['subscriber_id', 'year_month'])

# For each row, compute rolling history
df_dedup['bill_seq'] = df_dedup.groupby('subscriber_id').cumcount()
df_dedup['is_failed'] = (df_dedup['payment_status'] == 'Failed').astype(int)
df_dedup['is_unpaid'] = (df_dedup['payment_status'] == 'Unpaid').astype(int)
df_dedup['is_late'] = (df_dedup['payment_status'] == 'Paid Late').astype(int)

# Prior history (exclude current row)
df_dedup['prior_failures'] = df_dedup.groupby('subscriber_id')['is_failed'].cumsum() - df_dedup['is_failed']
df_dedup['prior_unpaid'] = df_dedup.groupby('subscriber_id')['is_unpaid'].cumsum() - df_dedup['is_unpaid']
df_dedup['prior_late'] = df_dedup.groupby('subscriber_id')['is_late'].cumsum() - df_dedup['is_late']

# Prior failure rate
df_dedup['prior_nonrecovery_rate'] = (df_dedup['prior_failures'] + df_dedup['prior_unpaid']) / df_dedup['bill_seq'].replace(0, np.nan)

# Does history predict current outcome?
has_history = df_dedup[df_dedup['bill_seq'] >= 3].copy()
print(f"Rows with 3+ prior bills: {len(has_history)}")

# Predictive power of prior_nonrecovery_rate
bins = [0, 0.01, 0.1, 0.2, 0.5, 1.01]
labels = ['0%', '1-10%', '10-20%', '20-50%', '50-100%']
has_history['history_bucket'] = pd.cut(has_history['prior_nonrecovery_rate'], bins=bins, labels=labels, right=False)
print(f"\nRecovery rate by prior non-recovery history:")
print(has_history.groupby('history_bucket', observed=True)['recovered'].agg(['mean', 'count']))

# late_fee_usd as signal
print(f"\n--- late_fee_usd as a signal ---")
print(f"Mean late_fee (recovered): {df_dedup.loc[df_dedup['recovered']==1, 'late_fee_usd'].mean():.2f}")
print(f"Mean late_fee (not recovered): {df_dedup.loc[df_dedup['recovered']==0, 'late_fee_usd'].mean():.2f}")

# Feature candidate analysis
print(f"\n--- Feature correlation with target ---")
numerical_cols = ['base_charge_usd', 'data_overage_usd', 'intl_roaming_usd', 'tax_usd', 'late_fee_usd', 'total_billed_usd']
for col in numerical_cols:
    corr = df_dedup[col].corr(df_dedup['recovered'])
    print(f"  {col}: correlation = {corr:.4f}")

# days_to_payment leakage check
print(f"\n--- days_to_payment LEAKAGE CHECK ---")
print(f"days_to_payment distribution by status:")
for status in df_dedup['payment_status'].unique():
    subset = df_dedup[df_dedup['payment_status'] == status]
    print(f"  {status}: mean={subset['days_to_payment'].mean():.1f}, min={subset['days_to_payment'].min()}, max={subset['days_to_payment'].max()}")

print("\nDONE")
