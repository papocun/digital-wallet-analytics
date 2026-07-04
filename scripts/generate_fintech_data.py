"""
generate_fintech_data.py
=========================
Generates synthetic B2C FinTech digital wallet dataset.
Produces: users_dim.csv, user_engagement_logs.csv, transactions_fact.csv
"""

import uuid
import numpy as np
import pandas as pd
from faker import Faker

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------
SEED = 42
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

N_USERS        = 25_000
START_DATE     = pd.Timestamp("2025-01-01")
END_DATE       = pd.Timestamp("2026-06-30 23:59:59")
OUTPUT_DIR     = "data/raw"          # ← local path

SIGNUP_CHANNELS        = ["Organic", "Paid Ads", "Referral"]
SIGNUP_CHANNEL_WEIGHTS = [0.40, 0.45, 0.15]

DEVICE_OS        = ["iOS", "Android"]
DEVICE_OS_WEIGHTS = [0.55, 0.45]

EVENT_NAMES = [
    "App_Open", "Onboarding_Step_1", "Onboarding_Completed", "View_Dashboard",
    "Link_Bank_Account", "Initiate_Transfer", "KYC_Failed", "Support_Ticket_Opened",
]

TXN_TYPES          = ["Deposit", "P2P_Transfer", "Bill_Payment", "Crypto_Buy", "Merchant_Cashback"]
TXN_TYPE_WEIGHTS   = [0.30, 0.30, 0.20, 0.10, 0.10]
TXN_STATUS         = ["Success", "Failed", "Pending"]
TXN_STATUS_WEIGHTS = [0.90, 0.07, 0.03]


# --------------------------------------------------------------------------
# 1. USERS_DIM
# --------------------------------------------------------------------------
def generate_users(n_users: int) -> pd.DataFrame:
    user_ids = [str(uuid.uuid4()) for _ in range(n_users)]

    total_days     = (END_DATE - START_DATE).days
    day_offsets    = np.arange(total_days + 1)
    growth_weights = 1 + (day_offsets / total_days) * 2.5
    growth_weights = growth_weights / growth_weights.sum()

    sampled_day_offsets = np.random.choice(day_offsets, size=n_users, p=growth_weights)
    random_seconds      = np.random.randint(0, 86400, size=n_users)
    signup_timestamps   = (
        START_DATE
        + pd.to_timedelta(sampled_day_offsets, unit="D")
        + pd.to_timedelta(random_seconds, unit="s")
    )

    signup_channel = np.random.choice(SIGNUP_CHANNELS, size=n_users, p=SIGNUP_CHANNEL_WEIGHTS)
    device_os      = np.random.choice(DEVICE_OS, size=n_users, p=DEVICE_OS_WEIGHTS).astype(object)
    age            = np.clip(np.random.normal(loc=31, scale=9, size=n_users), 18, 65).round().astype(int)

    base_completion_prob = np.where(signup_channel == "Paid Ads", 0.70, 0.82)
    onboarding_completed = np.random.binomial(1, base_completion_prob).astype(bool)

    users = pd.DataFrame({
        "user_id":              user_ids,
        "signup_timestamp":     signup_timestamps,
        "signup_channel":       signup_channel,
        "device_os":            device_os,
        "age":                  age,
        "onboarding_completed": onboarding_completed,
    })

    # Inject ~3% nulls into device_os
    null_mask = np.random.rand(n_users) < 0.03
    users.loc[null_mask, "device_os"] = np.nan

    return users


# --------------------------------------------------------------------------
# 2. RETENTION / LIFESPAN MODEL
# --------------------------------------------------------------------------
def compute_user_lifespans(users: pd.DataFrame) -> pd.DataFrame:
    n = len(users)

    max_possible_days = (END_DATE - users["signup_timestamp"]).dt.days.clip(lower=0).values
    raw_lifespan      = np.random.lognormal(mean=2.0, sigma=1.3, size=n)
    active_days       = np.minimum(raw_lifespan, max_possible_days)

    not_onboarded         = ~users["onboarding_completed"].values
    immediate_churn_prob  = np.where(not_onboarded, 0.20 * 1.75, 0.20)
    immediate_churn_mask  = np.random.rand(n) < immediate_churn_prob
    active_days           = np.where(
        immediate_churn_mask,
        np.random.uniform(0, 1, size=n),
        active_days
    )

    is_march26    = (
        (users["signup_timestamp"] >= "2026-03-01") &
        (users["signup_timestamp"] <  "2026-04-01")
    )
    drift_penalty = np.random.uniform(0.25, 0.45, size=n)
    active_days   = np.where(is_march26.values, active_days * drift_penalty, active_days)
    active_days   = np.clip(active_days, 0, max_possible_days)

    out = users[["user_id", "signup_timestamp"]].copy()
    out["active_days"]       = active_days
    out["is_march26_cohort"] = is_march26.values
    return out


# --------------------------------------------------------------------------
# 3. USER_ENGAGEMENT_LOGS
# --------------------------------------------------------------------------
def generate_engagement_logs(users: pd.DataFrame, lifespans: pd.DataFrame) -> pd.DataFrame:
    records_user_id   = []
    records_timestamp = []
    records_event     = []

    signup_arr      = users["signup_timestamp"].values
    onboarded_arr   = users["onboarding_completed"].values
    user_id_arr     = users["user_id"].values
    active_days_arr = lifespans["active_days"].values

    for i in range(len(users)):
        lifespan = active_days_arr[i]
        if lifespan <= 0:
            continue

        signup_ts  = signup_arr[i]
        user_id    = user_id_arr[i]
        onboarded  = onboarded_arr[i]

        n_sessions   = max(1, int(np.random.poisson(
            lam=2.5 + 3.0 * np.sqrt(min(lifespan, 60)) / 7
        )))
        decay_scale  = max(lifespan / 4, 0.5)
        day_offsets  = np.clip(
            np.random.exponential(scale=decay_scale, size=n_sessions), 0, lifespan
        )
        second_offsets     = np.random.randint(0, 86400, size=n_sessions)
        session_timestamps = (
            pd.to_datetime(signup_ts)
            + pd.to_timedelta(day_offsets, unit="D")
            + pd.to_timedelta(second_offsets, unit="s")
        )

        for ts in session_timestamps:
            records_user_id.append(user_id)
            records_timestamp.append(ts)
            records_event.append("App_Open")

        records_user_id.append(user_id)
        records_timestamp.append(
            pd.to_datetime(signup_ts)
            + pd.Timedelta(seconds=int(np.random.randint(5, 600)))
        )
        records_event.append("Onboarding_Step_1")

        if onboarded:
            records_user_id.append(user_id)
            records_timestamp.append(
                pd.to_datetime(signup_ts)
                + pd.Timedelta(seconds=int(np.random.randint(600, 3600)))
            )
            records_event.append("Onboarding_Completed")

            funnel_events = ["View_Dashboard", "Link_Bank_Account", "Initiate_Transfer"]
            funnel_probs  = [0.85, 0.55, 0.40]
            for ev, p in zip(funnel_events, funnel_probs):
                if np.random.rand() < p and n_sessions > 0:
                    pick_idx = np.random.randint(0, n_sessions)
                    records_user_id.append(user_id)
                    records_timestamp.append(
                        session_timestamps[pick_idx]
                        + pd.Timedelta(seconds=int(np.random.randint(1, 300)))
                    )
                    records_event.append(ev)

            if np.random.rand() < 0.06:
                pick_idx = np.random.randint(0, n_sessions)
                records_user_id.append(user_id)
                records_timestamp.append(
                    session_timestamps[pick_idx]
                    + pd.Timedelta(seconds=int(np.random.randint(1, 300)))
                )
                records_event.append("KYC_Failed")

    logs = pd.DataFrame({
        "user_id":         records_user_id,
        "event_timestamp": records_timestamp,
        "event_name":      records_event,
    })
    logs["event_id"] = [str(uuid.uuid4()) for _ in range(len(logs))]
    logs = logs[["event_id", "user_id", "event_timestamp", "event_name"]]
    logs = logs.sort_values("event_timestamp").reset_index(drop=True)
    return logs


# --------------------------------------------------------------------------
# 4. TRANSACTIONS_FACT
# --------------------------------------------------------------------------
TXN_AMOUNT_PARAMS = {
    "Deposit":           lambda size: np.round(np.random.uniform(20,  500,  size=size), 2),
    "P2P_Transfer":      lambda size: np.round(np.random.uniform(10,  50,   size=size), 2),
    "Bill_Payment":      lambda size: np.round(np.random.uniform(15,  250,  size=size), 2),
    "Crypto_Buy":        lambda size: np.round(np.random.uniform(100, 1000, size=size), 2),
    "Merchant_Cashback": lambda size: np.round(np.random.uniform(1,   25,   size=size), 2),
}

def generate_transactions(
    users: pd.DataFrame,
    lifespans: pd.DataFrame,
    logs: pd.DataFrame
) -> tuple:

    eligible_user_ids = logs.loc[
        logs["event_name"].isin(["Initiate_Transfer", "Link_Bank_Account"]), "user_id"
    ].unique()

    signup_lookup   = users.set_index("user_id")["signup_timestamp"]
    lifespan_lookup = lifespans.set_index("user_id")["active_days"]

    txn_user_id, txn_timestamp, txn_type = [], [], []

    for user_id in eligible_user_ids:
        signup_ts = signup_lookup.loc[user_id]
        lifespan  = lifespan_lookup.loc[user_id]
        if lifespan <= 0:
            continue

        n_txns       = max(1, np.random.poisson(lam=2 + 4 * np.sqrt(min(lifespan, 90)) / 9))
        decay_scale  = max(lifespan / 3, 0.5)
        day_offsets  = np.clip(
            np.random.exponential(scale=decay_scale, size=n_txns), 0, lifespan
        )
        second_offsets = np.random.randint(0, 86400, size=n_txns)
        timestamps     = (
            pd.to_datetime(signup_ts)
            + pd.to_timedelta(day_offsets, unit="D")
            + pd.to_timedelta(second_offsets, unit="s")
        )
        types = np.random.choice(TXN_TYPES, size=n_txns, p=TXN_TYPE_WEIGHTS)

        txn_user_id.extend([user_id] * n_txns)
        txn_timestamp.extend(timestamps)
        txn_type.extend(types)

    txn_type_arr = np.array(txn_type)
    amounts      = np.empty(len(txn_type_arr), dtype=float)
    for t_type, fn in TXN_AMOUNT_PARAMS.items():
        mask = txn_type_arr == t_type
        n    = mask.sum()
        if n > 0:
            amounts[mask] = fn(n)

    n_total = len(txn_user_id)
    status  = np.random.choice(TXN_STATUS, size=n_total, p=TXN_STATUS_WEIGHTS)

    transactions = pd.DataFrame({
        "transaction_id":        [str(uuid.uuid4()) for _ in range(n_total)],
        "user_id":               txn_user_id,
        "transaction_timestamp": txn_timestamp,
        "transaction_type":      txn_type_arr,
        "amount":                amounts,
        "status":                status,
    })

    # Inject ~3% nulls into amount
    null_mask = np.random.rand(len(transactions)) < 0.03
    transactions.loc[null_mask, "amount"] = np.nan

    # Out-of-bounds timestamps: <0.1% predate signup (timezone bug)
    bug_mask = np.random.rand(len(transactions)) < 0.001
    if bug_mask.sum() > 0:
        bug_idx          = transactions.index[bug_mask]
        signup_for_bugged = transactions.loc[bug_idx, "user_id"].map(signup_lookup)
        backshift         = pd.to_timedelta(np.random.randint(1, 5, size=len(bug_idx)), unit="D")
        transactions.loc[bug_idx, "transaction_timestamp"] = signup_for_bugged - backshift

    # Duplicate rows: simulate API retries
    n_dups   = int(len(transactions) * 0.015)
    dup_rows = transactions.sample(n=n_dups, random_state=SEED, replace=False).copy()
    transactions = pd.concat([transactions, dup_rows], ignore_index=True)

    # Correlate Failed transactions → Support_Ticket_Opened events
    failed_txns                          = transactions[transactions["status"] == "Failed"]
    support_tickets_user_id, support_tickets_ts = [], []

    for _, row in failed_txns.iterrows():
        if np.random.rand() < 0.30:
            ticket_ts = row["transaction_timestamp"] + pd.Timedelta(
                minutes=int(np.random.randint(5, 1440))
            )
            support_tickets_user_id.append(row["user_id"])
            support_tickets_ts.append(ticket_ts)

    extra_logs = pd.DataFrame({
        "user_id":         support_tickets_user_id,
        "event_timestamp": support_tickets_ts,
        "event_name":      ["Support_Ticket_Opened"] * len(support_tickets_user_id),
    })
    extra_logs["event_id"] = [str(uuid.uuid4()) for _ in range(len(extra_logs))]
    extra_logs = extra_logs[["event_id", "user_id", "event_timestamp", "event_name"]]

    transactions = transactions.sample(frac=1, random_state=SEED).reset_index(drop=True)

    return transactions, extra_logs


# --------------------------------------------------------------------------
# 5. MAIN PIPELINE
# --------------------------------------------------------------------------
def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[1/5] Generating {N_USERS:,} users...")
    users = generate_users(N_USERS)

    print("[2/5] Computing retention / lifespan model...")
    lifespans = compute_user_lifespans(users)

    print("[3/5] Generating engagement event logs...")
    logs = generate_engagement_logs(users, lifespans)

    print("[4/5] Generating transaction records...")
    transactions, support_ticket_logs = generate_transactions(users, lifespans, logs)

    logs = pd.concat([logs, support_ticket_logs], ignore_index=True)
    logs = logs.sort_values("event_timestamp").reset_index(drop=True)

    signup_lookup = users.set_index("user_id")["signup_timestamp"]
    logs_signup   = logs["user_id"].map(signup_lookup)
    logs          = logs[logs["event_timestamp"] >= logs_signup].reset_index(drop=True)

    print("[5/5] Writing CSV files...")

    users_out        = users.copy()
    users_out["signup_timestamp"] = users_out["signup_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    logs_out         = logs.copy()
    logs_out["event_timestamp"] = pd.to_datetime(
        logs_out["event_timestamp"]
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    transactions_out = transactions.copy()
    transactions_out["transaction_timestamp"] = pd.to_datetime(
        transactions_out["transaction_timestamp"]
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    users_out.to_csv(f"{OUTPUT_DIR}/users_dim.csv", index=False)
    logs_out.to_csv(f"{OUTPUT_DIR}/user_engagement_logs.csv", index=False)
    transactions_out.to_csv(f"{OUTPUT_DIR}/transactions_fact.csv", index=False)

    print("\n" + "=" * 60)
    print("DATASET GENERATION COMPLETE")
    print("=" * 60)
    print(f"users_dim.csv            → {len(users_out):,} rows")
    print(f"user_engagement_logs.csv → {len(logs_out):,} rows")
    print(f"transactions_fact.csv    → {len(transactions_out):,} rows")
    print(f"\nFiles saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()