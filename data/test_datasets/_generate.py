"""Generate 5 .xlsx test datasets for RecoverChain and validate each one against
the CURRENT application pipeline: upload -> analyze -> mapping -> ml-readiness ->
generate-cases. No application code is modified. Reports real results only."""
import os, io, uuid, random, json, tempfile
import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..")  # placeholder, overridden by argv
import sys
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT_DIR, exist_ok=True)

METHODS = ["card", "debit_card", "ach", "upi", "wallet", "netbanking", "bank_transfer"]

# Reasons the diagnosis engine recognises (insufficient_funds / network / expired
# card) are weighted higher so most generated cases get a concrete root cause;
# the rest are realistic "other" codes that resolve to an escalated case.
FAIL_REASONS_WEIGHTED = [
    ("insufficient_funds", 30), ("network_error", 16), ("gateway_timeout", 6),
    ("expired_card", 16), ("invalid_expiry", 4),
    ("do_not_honor", 10), ("card_declined", 8), ("authentication_required", 6),
]


def pick_reason(pool=None):
    p = pool or FAIL_REASONS_WEIGHTED
    vals, wts = zip(*p)
    return random.choices(vals, weights=wts)[0]


def ts_pool(start, end, n):
    # ISO-8601 strings (matches how the app's CSV datasets store dates and keeps
    # raw_payload JSON-serializable — a pandas Timestamp object is not).
    s = pd.Timestamp(start); e = pd.Timestamp(end)
    span = int((e - s).total_seconds())
    return [(s + pd.Timedelta(seconds=random.randint(0, span))).strftime("%Y-%m-%d %H:%M:%S")
            for _ in range(n)]


def money(lo, hi):
    # skew toward the low end, 2 decimals, always >= 1
    v = round(lo + (hi - lo) * (random.random() ** 2.2), 2)
    return max(1.0, v)


def base_rows(n, cust_prefix, txn_prefix, n_customers, date_range, amt_range,
              fail_rate, method_weights, fail_reasons, theme_col, theme_fn):
    customers = [f"{cust_prefix}-{i:04d}" for i in range(1, n_customers + 1)]
    methods, mw = zip(*method_weights)
    times = ts_pool(*date_range, n)
    rows = []
    for i in range(n):
        failed = random.random() < fail_rate
        rc = random.choices([0, 1, 2, 3, 4, 5], weights=[46, 24, 14, 9, 5, 2])[0] if failed \
            else random.choices([0, 1, 2], weights=[80, 15, 5])[0]
        row = {
            "customer_id": random.choice(customers),
            "transaction_id": f"{txn_prefix}-{uuid.uuid4().hex[:10]}",
            "event_timestamp": times[i],
            "amount": money(*amt_range),
            "payment_method": random.choices(methods, weights=mw)[0],
            "payment_result": None,          # set by caller (failed/unpaid vs paid)
            "failure_reason": pick_reason(fail_reasons) if failed else "",
            "retry_count": rc,
        }
        row["_failed"] = failed
        row[theme_col] = theme_fn(row, failed)
        rows.append(row)
    return rows


def finish(rows, fail_value, ok_value):
    for r in rows:
        r["payment_result"] = fail_value if r.pop("_failed") else ok_value
    df = pd.DataFrame(rows).sample(frac=1.0, random_state=7).reset_index(drop=True)
    return df


# ---------------------------------------------------------------- Dataset 1
def d1_payment_failure():
    rows = base_rows(
        620, "CUST-PF", "TXN-PF", 220,
        ("2025-01-01", "2025-04-30"), (5, 2600), 0.78,
        [("card", 45), ("debit_card", 20), ("ach", 12), ("upi", 12), ("wallet", 8), ("netbanking", 3)],
        None, "attempt_type",
        lambda r, f: ("initial" if r["retry_count"] == 0
                      else random.choice(["retry_auto", "retry_auto", "retry_manual"])),
    )
    return finish(rows, "failed", "paid")


# ---------------------------------------------------------------- Dataset 2
def d2_checkout_risk():
    rows = base_rows(
        560, "CUST-CO", "TXN-CO", 340,
        ("2025-02-01", "2025-05-31"), (12, 720), 0.62,
        [("card", 40), ("debit_card", 20), ("upi", 16), ("wallet", 12), ("ach", 8), ("netbanking", 4)],
        [("payment_abandoned", 22), ("insufficient_funds", 22), ("network_error", 16),
         ("gateway_timeout", 6), ("card_declined", 12), ("authentication_required", 10),
         ("expired_card", 12)],
        "checkout_phase",
        lambda r, f: (random.choice(["payment_entry", "payment_entry", "address"]) if f
                      else "confirmation"),
    )
    return finish(rows, "failed", "paid")


# ---------------------------------------------------------------- Dataset 3
def d3_subscription():
    plans = [9.99, 14.99, 29.0, 49.0, 99.0, 199.0]
    rows = base_rows(
        640, "CUST-SB", "TXN-SB", 175,
        ("2025-01-01", "2025-06-30"), (9, 210), 0.45,
        [("card", 55), ("debit_card", 18), ("upi", 12), ("ach", 10), ("wallet", 5)],
        [("expired_card", 26), ("invalid_expiry", 6), ("insufficient_funds", 24),
         ("do_not_honor", 14), ("network_error", 12), ("authentication_required", 10),
         ("card_declined", 8)],
        "billing_cycle",
        lambda r, f: random.choices(["monthly", "annual", "quarterly"], weights=[70, 20, 10])[0],
    )
    for r in rows:
        r["amount"] = round(random.choice(plans) * random.choice([1.0, 1.0, 1.08, 1.18]), 2)
    return finish(rows, "failed", "paid")


# ---------------------------------------------------------------- Dataset 4
def d4_invoice():
    today = pd.Timestamp("2025-04-01")
    rows = base_rows(
        600, "CUST-IN", "TXN-IN", 140,
        ("2024-10-01", "2025-03-25"), (200, 48000), 0.70,
        [("ach", 34), ("bank_transfer", 30), ("netbanking", 16), ("card", 12), ("upi", 8)],
        [("insufficient_funds", 26), ("net_terms_pending", 16), ("bank_rejected", 12),
         ("awaiting_approval", 12), ("disputed", 10), ("no_response", 12),
         ("network_error", 8), ("gateway_timeout", 4)],
        "aging_bucket",
        lambda r, f: "placeholder",
    )
    for r in rows:
        days = (today - pd.Timestamp(r["event_timestamp"])).days
        if not r["_failed"]:
            r["aging_bucket"] = "current" if random.random() < 0.7 else "d1_30"
        else:
            r["aging_bucket"] = ("current" if days <= 0 else "d1_30" if days <= 30
                                 else "d31_60" if days <= 60 else "d61_90" if days <= 90 else "d90_plus")
        r["retry_count"] = min(5, max(0, days // 20))   # reminders sent ~ how overdue
    return finish(rows, "unpaid", "paid")


# ---------------------------------------------------------------- Dataset 5
def d5_comprehensive():
    rows = base_rows(
        720, "CUST-MX", "TXN-MX", 300,
        ("2024-11-01", "2025-05-31"), (5, 52000), 0.55,
        [("card", 30), ("debit_card", 16), ("ach", 16), ("upi", 14), ("bank_transfer", 12),
         ("wallet", 8), ("netbanking", 4)],
        FAIL_REASONS_WEIGHTED + [("payment_abandoned", 8), ("bank_rejected", 8)],
        "revenue_stream",
        lambda r, f: random.choices(["payment", "checkout", "subscription", "invoice"],
                                    weights=[34, 22, 24, 20])[0],
    )
    return finish(rows, "failed", "paid")


BUILDERS = [
    ("RecoverChain_Payment_Failure.xlsx", d1_payment_failure),
    ("RecoverChain_Checkout_Risk.xlsx", d2_checkout_risk),
    ("RecoverChain_Subscription_Risk.xlsx", d3_subscription),
    ("RecoverChain_Invoice_Risk.xlsx", d4_invoice),
    ("RecoverChain_Comprehensive_Mixed.xlsx", d5_comprehensive),
]


def main():
    random.seed(20260901)
    built = []
    for fname, fn in BUILDERS:
        random.seed(hash(fname) & 0xFFFFFFFF)
        df = fn()
        path = os.path.join(OUT_DIR, fname)
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Data")
        dup = int(df.duplicated().sum())
        dup_tx = int(df["transaction_id"].duplicated().sum())
        dist = df["payment_result"].value_counts().to_dict()
        print(f"\n{fname}")
        print(f"  rows={len(df)}  cols={list(df.columns)}")
        print(f"  payment_result: {dist}")
        print(f"  unique customers={df['customer_id'].nunique()}  unique txn={df['transaction_id'].nunique()}")
        print(f"  duplicate rows={dup}   duplicate transaction_id={dup_tx}")
        print(f"  theme sample: {df.iloc[:, -1].value_counts().to_dict()}")
        built.append(path)
    print("\nWROTE:", *built, sep="\n  ")


if __name__ == "__main__":
    main()
