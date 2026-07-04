import nbformat as nbf
import os

nb = nbf.v4.new_notebook()
cells = []

def md(text): cells.append(nbf.v4.new_markdown_cell(text))
def code(text): cells.append(nbf.v4.new_code_cell(text))

# --------------------------------------------------------------------------
# TITLE
# --------------------------------------------------------------------------
md("""# Phase 2: Data Cleaning & EDA
### Digital Wallet Cohort & Retention Project
**Input:** `data/raw/` | **Output:** `data/cleaned/`""")

# --------------------------------------------------------------------------
# IMPORTS & CONFIG
# --------------------------------------------------------------------------
code("""import pandas as pd
import numpy as np

INPUT_DIR  = "../data/raw"
OUTPUT_DIR = "../data/cleaned"

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", None)""")

# --------------------------------------------------------------------------
# STEP 1: INITIAL DATA INSPECTION
# --------------------------------------------------------------------------
md("## 1. Initial Data Inspection")

code("""users = pd.read_csv(f"{INPUT_DIR}/users_dim.csv")
logs  = pd.read_csv(f"{INPUT_DIR}/user_engagement_logs.csv")
txns  = pd.read_csv(f"{INPUT_DIR}/transactions_fact.csv")

users["signup_timestamp"]      = pd.to_datetime(users["signup_timestamp"])
logs["event_timestamp"]        = pd.to_datetime(logs["event_timestamp"])
txns["transaction_timestamp"]  = pd.to_datetime(txns["transaction_timestamp"])""")

code("""print("--- DataFrame Shapes ---")
print(f"users_dim:            {users.shape}")
print(f"user_engagement_logs: {logs.shape}")
print(f"transactions_fact:    {txns.shape}")""")

code("""print("--- Missing Values: users_dim ---")
print(users.isnull().sum())""")

code("""print("--- Missing Values: user_engagement_logs ---")
print(logs.isnull().sum())""")

code("""print("--- Missing Values: transactions_fact ---")
print(txns.isnull().sum())""")

# --------------------------------------------------------------------------
# STEP 2: DATA CLEANING & ANOMALY HANDLING
# --------------------------------------------------------------------------
md("## 2. Data Cleaning & Anomaly Handling")

md("### 2a. Deduplication")

code("""dupe_count = txns.duplicated(subset="transaction_id", keep="first").sum()
print(f"Duplicate transaction_id rows found: {dupe_count}")

txns = txns.drop_duplicates(subset="transaction_id", keep="first")
print(f"Shape after dedup: {txns.shape}")""")

md("### 2b. Missing Values")

code("""# device_os: impute with Unknown — missing platform does not
# invalidate the rest of the user record
missing_device_os = users["device_os"].isnull().sum()
users["device_os"] = users["device_os"].fillna("Unknown")
print(f"Imputed {missing_device_os} missing device_os values with 'Unknown'.")""")

code("""# amount: drop rows entirely — we cannot evaluate financial volume
# or monetization metrics with a missing currency field
missing_amount = txns["amount"].isnull().sum()
txns = txns.dropna(subset=["amount"])
print(f"Dropped {missing_amount} rows with missing amount.")
print(f"Shape after amount cleanup: {txns.shape}")""")

md("### 2c. Temporal Logic Verification")

code("""# Remove events that were logged before the user even signed up
# This is caused by a simulated system timezone bug in the raw data
signup_lookup  = users.set_index("user_id")["signup_timestamp"]

logs_signup_ts = logs["user_id"].map(signup_lookup)
bad_logs_mask  = logs["event_timestamp"] < logs_signup_ts
bad_logs_count = bad_logs_mask.sum()
logs           = logs.loc[~bad_logs_mask].reset_index(drop=True)
print(f"Removed {bad_logs_count} log rows where event predates signup.")""")

code("""# Same check for transactions
txns_signup_ts = txns["user_id"].map(signup_lookup)
bad_txns_mask  = txns["transaction_timestamp"] < txns_signup_ts
bad_txns_count = bad_txns_mask.sum()
txns           = txns.loc[~bad_txns_mask].reset_index(drop=True)
print(f"Removed {bad_txns_count} transaction rows where timestamp predates signup.")
print(f"\\nFinal shapes -> users: {users.shape} | logs: {logs.shape} | txns: {txns.shape}")""")

# --------------------------------------------------------------------------
# STEP 3: BASELINE METRICS (EDA)
# --------------------------------------------------------------------------
md("## 3. Baseline Metrics (EDA)")

md("### 3a. Core Activation Metric — Onboarding Conversion Rate")

code("""rate = users["onboarding_completed"].mean()
print(f"Overall Onboarding Conversion Rate: {rate:.2%}")""")

md("### 3b. Platform Reliability Metric — Transaction Success Rate")

code("""success_rate = (txns["status"] == "Success").mean()
print(f"Overall Transaction Success Rate: {success_rate:.2%}")""")

md("### 3c. Acquisition Performance by Channel")

code("""channel_performance = users.groupby("signup_channel").agg(
    total_signups   = ("user_id", "count"),
    onboarding_rate = ("onboarding_completed", "mean"),
).round(4)

print("Acquisition Performance by signup_channel:")
channel_performance""")

md("### 3d. Average Transaction Amount by Channel")

code("""txns_with_channel = txns.merge(
    users[["user_id", "signup_channel"]],
    on  = "user_id",
    how = "left"
)

avg_amount = (
    txns_with_channel
    .groupby("signup_channel")["amount"]
    .mean()
    .round(2)
    .rename("avg_transaction_amount")
)

print("Average Transaction Amount by signup_channel:")
avg_amount""")

# --------------------------------------------------------------------------
# STEP 4: ROOT CAUSE ISOLATION — MARCH 2026 ANOMALY
# --------------------------------------------------------------------------
md("## 4. Root Cause Isolation — March 2026 Anomaly")

md("### 4a. Build Monthly Cohort Labels")

code("""users["signup_cohort"] = users["signup_timestamp"].dt.to_period("M").astype(str)

cohort_onboarding = users.groupby("signup_cohort")["onboarding_completed"].agg(
    total_signups   = "count",
    onboarding_rate = "mean"
).round(4)

print("Onboarding completion rate by signup cohort:")
cohort_onboarding""")

md("### 4b. Feb 2026 vs March 2026 Direct Comparison")

code("""feb_rate  = cohort_onboarding.loc["2026-02", "onboarding_rate"]
mar_rate  = cohort_onboarding.loc["2026-03", "onboarding_rate"]
rate_drop = feb_rate - mar_rate

print("--- Feb 2026 vs March 2026 Onboarding Comparison ---")
print(f"February 2026 onboarding rate : {feb_rate:.2%}")
print(f"March 2026 onboarding rate    : {mar_rate:.2%}")
print(f"Absolute drop                 : {rate_drop:.2%}")
print(f"Relative decline              : {rate_drop / feb_rate:.1%}")""")

md("### 4c. Friction Event Frequency Comparison")

code("""march_users = users.loc[users["signup_cohort"] == "2026-03", "user_id"]
feb_users   = users.loc[users["signup_cohort"] == "2026-02", "user_id"]

march_logs  = logs[logs["user_id"].isin(march_users)]
feb_logs    = logs[logs["user_id"].isin(feb_users)]

march_dist  = march_logs["event_name"].value_counts(normalize=True).round(4)
feb_dist    = feb_logs["event_name"].value_counts(normalize=True).round(4)

event_comparison = pd.DataFrame({
    "march_2026_pct" : march_dist,
    "feb_2026_pct"   : feb_dist,
}).fillna(0).sort_values("march_2026_pct", ascending=False)

print("Event distribution: March 2026 vs February 2026:")
event_comparison""")

code("""friction_events = ["KYC_Failed", "Support_Ticket_Opened"]
print("--- Friction Event Spotlight ---")
for ev in friction_events:
    m = march_dist.get(ev, 0)
    f = feb_dist.get(ev, 0)
    print(f"{ev:>25}: March = {m:.2%}  |  Feb = {f:.2%}")""")

md("""**Finding:** Onboarding completion and friction event rates are essentially
flat between February and March 2026. The March drop is not happening at the
onboarding stage — it surfaces downstream in Month 1+ retention and transaction
behavior, which the Phase 3 SQL cohort matrix will expose directly.""")

# --------------------------------------------------------------------------
# STEP 5: EXPORT CLEANED DATASETS
# --------------------------------------------------------------------------
md("## 5. Export Cleaned Datasets")

code("""import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

users_export = users.drop(columns=["signup_cohort"])

users_export.to_csv(f"{OUTPUT_DIR}/cleaned_users_dim.csv",            index=False)
logs.to_csv(f"{OUTPUT_DIR}/cleaned_user_engagement_logs.csv",          index=False)
txns.to_csv(f"{OUTPUT_DIR}/cleaned_transactions_fact.csv",             index=False)

print("Exported successfully:")
print(f"  cleaned_users_dim.csv            -> {users_export.shape[0]:,} rows")
print(f"  cleaned_user_engagement_logs.csv -> {logs.shape[0]:,} rows")
print(f"  cleaned_transactions_fact.csv    -> {txns.shape[0]:,} rows")
print("\\nPhase 2 complete.")""")

# --------------------------------------------------------------------------
# WRITE THE NOTEBOOK FILE
# --------------------------------------------------------------------------
nb["cells"] = cells

os.makedirs("notebooks", exist_ok=True)

with open("notebooks/phase2_cleaning_eda.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print("Notebook created at notebooks/phase2_cleaning_eda.ipynb")