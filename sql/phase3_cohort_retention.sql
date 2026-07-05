-- ============================================================================
-- PHASE 3: CORE DATA MODELING & COHORT RETENTION GENERATION
-- Digital Wallet Cohort & Retention Project
--
-- Database : digital_wallet_analytics (MySQL)
-- Tables   : cleaned_users_dim
--            cleaned_user_engagement_logs
--            cleaned_transactions_fact
--
-- Run each query block separately in VS Code SQL Tools
-- Select the query you want → Ctrl + Enter to execute
-- ============================================================================

USE digital_wallet_analytics;

show tables;

-- ============================================================================
-- QUERY 1: MONTHLY USER RETENTION MATRIX
-- ============================================================================
-- Purpose: Builds the standard cohort retention table.
-- Cohort month on rows, months since signup (0,1,2,3...) on columns.
-- Retention % in each cell.
-- The March 2026 row will visually stand out below the rest.
-- ============================================================================

WITH user_cohorts AS (
    SELECT
        user_id,
        DATE_FORMAT(signup_timestamp, '%Y-%m-01') AS cohort_month
    FROM cleaned_users_dim
    WHERE onboarding_completed = 1

),

user_activity AS (
    SELECT DISTINCT
        user_id,
        DATE_FORMAT(event_timestamp, '%Y-%m-01') AS activity_month
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
        (YEAR(ua.activity_month)  - YEAR(uc.cohort_month))  * 12
      + (MONTH(ua.activity_month) - MONTH(uc.cohort_month))
    ) AS month_number,

    COUNT(DISTINCT ua.user_id) AS active_users,

    ROUND(
        100.0 * COUNT(DISTINCT ua.user_id) / cs.cohort_size,
        2
    ) AS retention_pct

FROM user_cohorts uc
INNER JOIN user_activity ua
    ON uc.user_id = ua.user_id
INNER JOIN cohort_sizes cs
    ON uc.cohort_month = cs.cohort_month

GROUP BY
    uc.cohort_month,
    cs.cohort_size,
    month_number

ORDER BY
    uc.cohort_month,
    month_number;


-- ============================================================================
-- QUERY 2: MARCH 2026 DEEP DIVE DIAGNOSTIC
-- ============================================================================
-- Purpose: Isolates what broke in March 2026 vs February 2026 control.
-- Cross-tabs friction events against device_os to find if the issue
-- is platform-specific (Android vs iOS) or across the board.
--
-- How to read results:
--   If March Android rate >> March iOS rate  = platform bug
--   If both platforms drop equally           = backend or UX issue
--   If channel mix shifted                   = acquisition quality problem
-- ============================================================================

WITH cohort_users AS (

    SELECT
        user_id,
        device_os,
        DATE_FORMAT(signup_timestamp, '%Y-%m-01') AS cohort_month
    FROM cleaned_users_dim
    WHERE DATE_FORMAT(signup_timestamp, '%Y-%m-01')
          IN ('2026-02-01', '2026-03-01')

),

month0_friction_events AS (
    SELECT
        cu.cohort_month,
        cu.device_os,
        l.event_name,
        COUNT(*) AS event_count
    FROM cleaned_user_engagement_logs l
    INNER JOIN cohort_users cu
        ON l.user_id = cu.user_id
    WHERE l.event_name IN ('KYC_Failed', 'Support_Ticket_Opened')
      AND l.event_timestamp < DATE_ADD(cu.cohort_month, INTERVAL 30 DAY)
    GROUP BY
        cu.cohort_month,
        cu.device_os,
        l.event_name

),

month0_failed_transactions AS (
    SELECT
        cu.cohort_month,
        cu.device_os,
        'Failed_Transaction' AS event_name,
        COUNT(*) AS event_count
    FROM cleaned_transactions_fact t
    INNER JOIN cohort_users cu
        ON t.user_id = cu.user_id
    WHERE t.status = 'Failed'
      AND t.transaction_timestamp < DATE_ADD(cu.cohort_month, INTERVAL 30 DAY)
    GROUP BY
        cu.cohort_month,
        cu.device_os

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
    ROUND(
        100.0 * cf.event_count / cdp.users_in_segment,
        2
    ) AS event_rate_per_100_users

FROM combined_friction cf
INNER JOIN cohort_device_population cdp
    ON  cf.cohort_month = cdp.cohort_month
    AND cf.device_os    = cdp.device_os

ORDER BY
    cf.event_name,
    cf.device_os,
    cf.cohort_month;


-- ============================================================================
-- QUERY 3: CHURN VALUE & REVENUE RECOVERY ESTIMATION
-- ============================================================================
-- Purpose: Puts a dollar figure on early churn for leadership.
-- Segments onboarded users into Active/Healthy vs Early Churned.
-- Compares average spend and transaction frequency between groups.
--
-- Revenue gap per user = Active avg spend minus Churned avg spend
-- Multiply by churned user count to get total revenue lost
-- ============================================================================

WITH onboarded_users AS (

    SELECT
        user_id,
        DATE_FORMAT(signup_timestamp, '%Y-%m-01') AS cohort_month
    FROM cleaned_users_dim
    WHERE onboarding_completed = 1

),

activity_after_month0 AS (
    SELECT DISTINCT ou.user_id
    FROM onboarded_users ou
    INNER JOIN cleaned_user_engagement_logs l
        ON ou.user_id = l.user_id
    WHERE l.event_timestamp >= DATE_ADD(ou.cohort_month, INTERVAL 30 DAY)
    UNION
    SELECT DISTINCT ou.user_id
    FROM onboarded_users ou
    INNER JOIN cleaned_transactions_fact t
        ON ou.user_id = t.user_id
    WHERE t.transaction_timestamp >= DATE_ADD(ou.cohort_month, INTERVAL 30 DAY)

),

user_segments AS (

    SELECT
        ou.user_id,
        CASE
            WHEN aam.user_id IS NOT NULL THEN 'Active/Healthy User'
            ELSE 'Early Churned User'
        END AS user_segment
    FROM onboarded_users ou
    LEFT JOIN activity_after_month0 aam
        ON ou.user_id = aam.user_id

),

user_transaction_summary AS (
    SELECT
        user_id,
        COUNT(*)    AS total_transactions,
        SUM(amount) AS total_amount
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
LEFT JOIN user_transaction_summary uts
    ON us.user_id = uts.user_id

GROUP BY us.user_segment
ORDER BY us.user_segment;