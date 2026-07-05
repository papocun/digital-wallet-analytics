"""
run_sql_models.py
==================
Phase 3: Execute SQL cohort retention models locally using DuckDB.
DuckDB uses standard ANSI SQL — identical to PostgreSQL/BigQuery syntax.

Reads:  data/cleaned/ CSVs
Writes: data/sql_outputs/ CSVs (one per query result)
"""

import duckdb
import pandas as pd
import os

INPUT_DIR  = "data/cleaned"
OUTPUT_DIR = "data/sql_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# CONNECT & LOAD TABLES
# --------------------------------------------------------------------------
print("Connecting to DuckDB...")
con = duckdb.connect()

print("Loading cleaned CSVs into DuckDB tables...")
con.execute(f"""
    CREATE TABLE cleaned_users_dim AS
    SELECT * FROM read_csv_auto('{INPUT_DIR}/cleaned_users_dim.csv')
""")

con.execute(f"""
    CREATE TABLE cleaned_user_engagement_logs AS
    SELECT * FROM read_csv_auto('{INPUT_DIR}/cleaned_user_engagement_logs.csv')
""")

con.execute(f"""
    CREATE TABLE cleaned_transactions_fact AS
    SELECT * FROM read_csv_auto('{INPUT_DIR}/cleaned_transactions_fact.csv')
""")

print("Tables loaded successfully.")
print("-" * 60)

# --------------------------------------------------------------------------
# QUERY 1: MONTHLY COHORT RETENTION MATRIX
# --------------------------------------------------------------------------
print("\nRunning Query 1: Monthly Cohort Retention Matrix...")

query1 = """
WITH user_cohorts AS (
    SELECT
        user_id,
        DATE_TRUNC('month', signup_timestamp::TIMESTAMP) AS cohort_month
    FROM cleaned_users_dim
    WHERE onboarding_completed = TRUE
),

user_activity AS (
    SELECT DISTINCT
        user_id,
        DATE_TRUNC('month', event_timestamp::TIMESTAMP) AS activity_month
    FROM cleaned_user_engagement_logs
),

cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT user_id) AS cohort_size
    FROM user_cohorts
    GROUP BY cohort_month
)

SELECT
    uc.cohort_month,
    cs.cohort_size,
    (
        (EXTRACT(YEAR  FROM ua.activity_month) - EXTRACT(YEAR  FROM uc.cohort_month)) * 12
      + (EXTRACT(MONTH FROM ua.activity_month) - EXTRACT(MONTH FROM uc.cohort_month))
    ) AS month_number,
    COUNT(DISTINCT ua.user_id)  AS active_users,
    ROUND(
        100.0 * COUNT(DISTINCT ua.user_id) / cs.cohort_size,
        2
    ) AS retention_pct

FROM user_cohorts uc
INNER JOIN user_activity  ua ON uc.user_id       = ua.user_id
INNER JOIN cohort_sizes   cs ON uc.cohort_month  = cs.cohort_month

GROUP BY
    uc.cohort_month,
    cs.cohort_size,
    month_number

ORDER BY
    uc.cohort_month,
    month_number
"""

result1 = con.execute(query1).fetchdf()
result1.to_csv(f"{OUTPUT_DIR}/q1_cohort_retention_matrix.csv", index=False)

print(f"Rows returned: {len(result1)}")
print("\nSample output (first 10 rows):")
print(result1.head(10).to_string(index=False))
print(f"\nFull result saved to: {OUTPUT_DIR}/q1_cohort_retention_matrix.csv")

# --------------------------------------------------------------------------
# QUERY 2: MARCH 2026 DIAGNOSTIC — FRICTION BY DEVICE OS
# --------------------------------------------------------------------------
print("\n" + "-" * 60)
print("Running Query 2: March 2026 Segmented Diagnostic...")

query2 = """
WITH cohort_users AS (
    SELECT
        user_id,
        device_os,
        DATE_TRUNC('month', signup_timestamp::TIMESTAMP) AS cohort_month
    FROM cleaned_users_dim
    WHERE DATE_TRUNC('month', signup_timestamp::TIMESTAMP)
          IN (DATE '2026-02-01', DATE '2026-03-01')
),

month0_friction_events AS (
    SELECT
        cu.cohort_month,
        cu.device_os,
        l.event_name,
        COUNT(*) AS event_count
    FROM cleaned_user_engagement_logs l
    INNER JOIN cohort_users cu ON l.user_id = cu.user_id
    WHERE l.event_name IN ('KYC_Failed', 'Support_Ticket_Opened')
      AND l.event_timestamp::TIMESTAMP < cu.cohort_month + INTERVAL '30 days'
    GROUP BY cu.cohort_month, cu.device_os, l.event_name
),

month0_failed_transactions AS (
    SELECT
        cu.cohort_month,
        cu.device_os,
        'Failed_Transaction' AS event_name,
        COUNT(*) AS event_count
    FROM cleaned_transactions_fact t
    INNER JOIN cohort_users cu ON t.user_id = cu.user_id
    WHERE t.status = 'Failed'
      AND t.transaction_timestamp::TIMESTAMP < cu.cohort_month + INTERVAL '30 days'
    GROUP BY cu.cohort_month, cu.device_os
),

combined_friction AS (
    SELECT * FROM month0_friction_events
    UNION ALL
    SELECT * FROM month0_failed_transactions
),

cohort_device_population AS (
    SELECT
        cohort_month,
        device_os,
        COUNT(DISTINCT user_id) AS users_in_segment
    FROM cohort_users
    GROUP BY cohort_month, device_os
)

SELECT
    cf.cohort_month,
    cf.device_os,
    cdp.users_in_segment,
    cf.event_name,
    cf.event_count,
    ROUND(100.0 * cf.event_count / cdp.users_in_segment, 2) AS event_rate_per_100_users

FROM combined_friction cf
INNER JOIN cohort_device_population cdp
    ON cf.cohort_month = cdp.cohort_month
    AND cf.device_os   = cdp.device_os

ORDER BY cf.event_name, cf.device_os, cf.cohort_month
"""

result2 = con.execute(query2).fetchdf()
result2.to_csv(f"{OUTPUT_DIR}/q2_march2026_diagnostic.csv", index=False)

print(f"Rows returned: {len(result2)}")
print("\nFull diagnostic output:")
print(result2.to_string(index=False))
print(f"\nFull result saved to: {OUTPUT_DIR}/q2_march2026_diagnostic.csv")

# --------------------------------------------------------------------------
# QUERY 3: CHURN VALUE & REVENUE RECOVERY ESTIMATION
# --------------------------------------------------------------------------
print("\n" + "-" * 60)
print("Running Query 3: Churn Value & Revenue Recovery Estimation...")

query3 = """
WITH onboarded_users AS (
    SELECT
        user_id,
        DATE_TRUNC('month', signup_timestamp::TIMESTAMP) AS cohort_month
    FROM cleaned_users_dim
    WHERE onboarding_completed = TRUE
),

activity_after_month0 AS (
    SELECT DISTINCT ou.user_id
    FROM onboarded_users ou
    INNER JOIN cleaned_user_engagement_logs l ON ou.user_id = l.user_id
    WHERE l.event_timestamp::TIMESTAMP >= ou.cohort_month + INTERVAL '30 days'

    UNION

    SELECT DISTINCT ou.user_id
    FROM onboarded_users ou
    INNER JOIN cleaned_transactions_fact t ON ou.user_id = t.user_id
    WHERE t.transaction_timestamp::TIMESTAMP >= ou.cohort_month + INTERVAL '30 days'
),

user_segments AS (
    SELECT
        ou.user_id,
        CASE
            WHEN aam.user_id IS NOT NULL THEN 'Active/Healthy User'
            ELSE 'Early Churned User'
        END AS user_segment
    FROM onboarded_users ou
    LEFT JOIN activity_after_month0 aam ON ou.user_id = aam.user_id
),

user_transaction_summary AS (
    SELECT
        user_id,
        COUNT(*)     AS total_transactions,
        SUM(amount)  AS total_amount
    FROM cleaned_transactions_fact
    WHERE status = 'Success'
    GROUP BY user_id
)

SELECT
    us.user_segment,
    COUNT(DISTINCT us.user_id)                                          AS total_users,
    ROUND(AVG(COALESCE(uts.total_amount,       0)), 2)                  AS avg_total_spend,
    ROUND(AVG(COALESCE(uts.total_transactions, 0)), 2)                  AS avg_txn_count,
    ROUND(
        SUM(COALESCE(uts.total_amount, 0))
        / NULLIF(SUM(COALESCE(uts.total_transactions, 0)), 0),
        2
    )                                                                   AS avg_value_per_txn

FROM user_segments us
LEFT JOIN user_transaction_summary uts ON us.user_id = uts.user_id

GROUP BY us.user_segment
ORDER BY us.user_segment
"""

result3 = con.execute(query3).fetchdf()
result3.to_csv(f"{OUTPUT_DIR}/q3_churn_value_estimation.csv", index=False)

print(f"Rows returned: {len(result3)}")
print("\nChurn vs Active User Value:")
print(result3.to_string(index=False))

# Revenue gap calculation
if "Active/Healthy User" in result3["user_segment"].values and \
   "Early Churned User"  in result3["user_segment"].values:
    active_spend = result3.loc[
        result3["user_segment"] == "Active/Healthy User", "avg_total_spend"
    ].values[0]
    churned_spend = result3.loc[
        result3["user_segment"] == "Early Churned User", "avg_total_spend"
    ].values[0]
    gap = active_spend - churned_spend
    print(f"\n  Revenue gap per churned user : ${gap:,.2f}")
    print(f"  Active user avg spend        : ${active_spend:,.2f}")
    print(f"  Churned user avg spend       : ${churned_spend:,.2f}")

print(f"\nFull result saved to: {OUTPUT_DIR}/q3_churn_value_estimation.csv")

# --------------------------------------------------------------------------
# SUMMARY
# --------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PHASE 3 SQL EXECUTION COMPLETE")
print("=" * 60)
print(f"  q1_cohort_retention_matrix.csv  -> {len(result1):,} rows")
print(f"  q2_march2026_diagnostic.csv     -> {len(result2):,} rows")
print(f"  q3_churn_value_estimation.csv   -> {len(result3):,} rows")
print(f"\nAll outputs saved to: {OUTPUT_DIR}/")

con.close()