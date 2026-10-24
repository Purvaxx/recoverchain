"""
Phase 17 — First Supervised ML Model (Payment Failure Risk)
"""
import pandas as pd
import numpy as np
import xgboost as xgb
import os
import json
import time

# Create directories
os.makedirs("backend/ml/models", exist_ok=True)
os.makedirs("backend/ml/evaluation", exist_ok=True)
os.makedirs("backend/ml/training", exist_ok=True)

# ---------------------------------------------------------
# PURE NUMPY METRIC IMPLEMENTATIONS (to bypass sklearn DLL block)
# ---------------------------------------------------------
def brier_score(y_true, y_prob):
    return np.mean((y_true - y_prob)**2)

def binary_metrics_at_threshold(y_true, y_prob, threshold=0.5):
    y_pred = (y_prob >= threshold).astype(int)
    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)
    }

def roc_pr_auc(y_true, y_prob):
    # Sort by descending probability
    desc_score_indices = np.argsort(y_prob)[::-1]
    y_score = y_prob[desc_score_indices]
    y_true_sorted = y_true[desc_score_indices]

    # Compute ROC and PR curves
    tps = np.cumsum(y_true_sorted)
    fps = np.cumsum(1 - y_true_sorted)
    
    # Handle ties (keep the last index of ties)
    distinct_value_indices = np.where(np.diff(y_score) != 0)[0]
    threshold_idxs = np.r_[distinct_value_indices, y_true_sorted.size - 1]
    
    tps = tps[threshold_idxs]
    fps = fps[threshold_idxs]
    
    if tps[-1] == 0 or fps[-1] == 0:
        return 0.0, 0.0 # undefined
        
    tpr = tps / tps[-1]
    fpr = fps / fps[-1]
    
    # ROC AUC
    roc_auc = np.trapezoid(tpr, fpr)
    
    # PR AUC (Average Precision)
    precision = tps / (tps + fps)
    precision = np.r_[1.0, precision] # start with precision 1
    recall = np.r_[0.0, tpr]          # start with recall 0
    pr_auc = np.sum(np.diff(recall) * precision[1:])
    
    return roc_auc, pr_auc

# ---------------------------------------------------------
# LOAD AND PREPARE DATA
# ---------------------------------------------------------
print("Loading dataset...")
df = pd.read_csv("backend/evaluation/datasets/billing_recovery_v3.csv")

# TARGET RE-DEFINITION FOR MODELING:
# The prompt defines: "supervised model for payment failure risk"
# So y=1 should mean FAILURE, y=0 means SUCCESS.
# In billing_recovery_v3, target_recovered=0 means failure. So we flip it.
df['target_failure'] = 1 - df['target_recovered']

features = [
    'bill_amount_excl_late', 'base_charge_usd', 'data_overage_usd',
    'intl_roaming_usd', 'tax_usd', 'has_overage', 'has_roaming',
    'bill_seq', 'prior_failures', 'prior_unpaid', 'prior_late',
    'prior_ontime', 'prior_nonrecovery_count', 'prior_nonrecovery_rate',
    'prior_late_rate', 'prior_avg_amount'
]

# Ensure no leakage columns in features list
leakage_cols = ['payment_status', 'days_to_payment', 'late_fee_usd', 'total_billed_usd', 'target_recovered', 'target_failure']
for lc in leakage_cols:
    assert lc not in features, f"LEAKAGE DETECTED: {lc} is in features"

train = df[df['split'] == 'train'].copy()
val = df[df['split'] == 'validation'].copy()
test = df[df['split'] == 'test'].copy()

X_train, y_train = train[features].values, train['target_failure'].values
X_val, y_val = val[features].values, val['target_failure'].values
X_test, y_test = test[features].values, test['target_failure'].values

print(f"\nTemporal Split Distribution (Target = Payment Failure Risk):")
for name, data in [("TRAIN", train), ("VALIDATION", val), ("TEST", test)]:
    pos = data['target_failure'].sum()
    total = len(data)
    print(f"{name}: {total} rows | Failures (pos): {pos} ({pos/total*100:.2f}%) | Successes (neg): {total-pos} ({(total-pos)/total*100:.2f}%)")

# ---------------------------------------------------------
# TRAIN MODELS
# ---------------------------------------------------------
print("\nTraining models...")

# 1. Majority Baseline
train_failure_rate = y_train.mean()
# Baseline predicts the training failure rate for everyone
baseline_prob = np.full(y_test.shape, train_failure_rate)

# 2. Logistic Regression (using XGBoost gblinear)
dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=features)
dval = xgb.DMatrix(X_val, label=y_val, feature_names=features)
dtest = xgb.DMatrix(X_test, label=y_test, feature_names=features)

params_lr = {
    'booster': 'gblinear',
    'objective': 'binary:logistic',
    'eval_metric': 'logloss',
    'eta': 0.1, # learning rate
    'updater': 'shotgun',
    'random_state': 42
}
model_lr = xgb.train(params_lr, dtrain, num_boost_round=100, evals=[(dval, 'val')], early_stopping_rounds=10, verbose_eval=False)
lr_prob = model_lr.predict(dtest)

# 3. Tree Model (XGBoost gbtree)
params_tree = {
    'booster': 'gbtree',
    'objective': 'binary:logistic',
    'eval_metric': 'logloss',
    'max_depth': 6,
    'eta': 0.1,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'random_state': 42
}
model_tree = xgb.train(params_tree, dtrain, num_boost_round=100, evals=[(dval, 'val')], early_stopping_rounds=10, verbose_eval=False)
tree_prob = model_tree.predict(dtest)

# ---------------------------------------------------------
# EVALUATION
# ---------------------------------------------------------
results = []
models = {
    "Majority Baseline": baseline_prob,
    "Logistic Regression (gblinear)": lr_prob,
    "Tree Model (gbtree)": tree_prob
}

# Determine a reasonable threshold based on training failure rate (approx 5%)
# Using exactly 0.5 is a bad idea for imbalanced data, but we'll report it. 
# Better: use the 90th percentile of predicted probs as threshold for "high risk" 
threshold_tree = np.percentile(tree_prob, 90) # Top 10% risky
print(f"\nUsing threshold {threshold_tree:.4f} for Confusion Matrix (Top 10% predicted risk on Test)")

print("\nModel Evaluation (Test Set):")
for name, probs in models.items():
    roc, pr = roc_pr_auc(y_test, probs)
    brier = brier_score(y_test, probs)
    mets = binary_metrics_at_threshold(y_test, probs, threshold=threshold_tree if name != "Majority Baseline" else 0.5)
    
    print(f"\n--- {name} ---")
    print(f"PR-AUC:    {pr:.4f}")
    print(f"ROC-AUC:   {roc:.4f}")
    print(f"Brier:     {brier:.4f}")
    if name != "Majority Baseline":
        print(f"Precision: {mets['precision']:.4f}")
        print(f"Recall:    {mets['recall']:.4f}")
        print(f"F1:        {mets['f1']:.4f}")
        print(f"Confusion: TP={mets['tp']} FP={mets['fp']} TN={mets['tn']} FN={mets['fn']}")
    
    results.append({
        "Model": name,
        "PR-AUC": pr,
        "ROC-AUC": roc,
        "Precision": mets['precision'],
        "Recall": mets['recall'],
        "F1": mets['f1'],
        "Brier": brier
    })

# Feature Importance
print("\nFeature Importance (Tree Model):")
importance = model_tree.get_score(importance_type='gain')
sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
for f, imp in sorted_imp:
    print(f"  {f}: {imp:.2f}")

# Save artifacts
model_tree.save_model("backend/ml/models/failure_risk_tree.json")
with open("backend/ml/models/features.json", "w") as f:
    json.dump(features, f)

print("\nSaved model artifacts.")
print("DONE.")
