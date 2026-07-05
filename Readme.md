# Phase 5: Final Report
## Digital Wallet App — User Cohort & Retention Analysis

**Prepared by:** Product Analytics
**Project Duration:** January 2025 – June 2026 (18 months of data)
**Date:** July 2026
**Dataset:** 25,000 synthetic users | 169,340 engagement events | 43,023 transactions

---

## Executive Summary

This project delivers an end-to-end product analytics study for a B2C digital wallet mobile application. Starting from raw synthetic data, the analysis moved through structured data cleaning, SQL-based cohort modeling, and visual storytelling to surface actionable insights about user retention, acquisition quality, and revenue impact.

The single most important finding is this: **the majority of user churn happens within the first 30 days, and users who do not complete onboarding are significantly more likely to never return.** A secondary critical finding is a sharp retention anomaly in the March 2026 user cohort, which underperformed every other cohort in the dataset and points to a suspected product or backend release issue that month. Together, these findings give the product and growth teams a clear, data-backed roadmap for where to focus next.

---

## Project Overview

| Phase | Description | Key Output |
|---|---|---|
| Phase 1 | Business & Analytics Strategy | Metric framework, cohort logic, 4 hypotheses, March 2026 diagnostic plan |
| Phase 2 | Data Cleaning & EDA | 3 cleaned CSVs, baseline metrics, initial anomaly flag |
| Phase 3 | SQL Cohort Retention Modeling | Retention matrix, March 2026 deep dive, churn value estimation |
| Phase 4 | Visualization Dashboard | 5 production-ready charts |
| Phase 5 | Final Report | This document |

**Tools Used:**
Python, Pandas, NumPy, Faker, DuckDB, SQL (ANSI / PostgreSQL / BigQuery compatible), Matplotlib, Seaborn

**Repository:**
[github.com/papocun/digital-wallet-analytics](https://github.com/papocun/digital-wallet-analytics)

---

## Data Overview

### Source Tables

| Table | Rows | Description |
|---|---|---|
| `users_dim` | 25,000 | User demographics, signup channel, device OS, onboarding status |
| `user_engagement_logs` | 169,340 | Granular event stream (App Opens, Onboarding steps, KYC, Support) |
| `transactions_fact` | 43,023 | Financial records with type, amount, and status |

### Data Quality Issues Found & Fixed

| Issue | Table | Count | Fix Applied |
|---|---|---|---|
| Duplicate transaction IDs (API retries) | Transactions | 665 rows | Kept first occurrence, dropped duplicates |
| Missing device_os values | Users | 737 rows | Imputed as 'Unknown' |
| Missing transaction amounts | Transactions | 1,307 rows | Dropped — cannot evaluate financial volume on null currency |
| Timestamps predating user signup | Logs + Transactions | 44 + 46 rows | Removed — logically impossible records from timezone bug |

---

## Key Findings

---

### Finding 1: Most Churn Happens in Month 0 — The First 30 Days Are Everything

**What the data shows:**
The cohort retention matrix (Chart 1) reveals a consistent and steep drop-off pattern across every signup cohort. On average, only **19–22% of onboarded users are still active by Month 1**, and that number continues to decay to single digits by Month 3. The pattern is logarithmic — the drop from Month 0 to Month 1 is always the largest, and retention stabilizes for users who survive past Month 3.

**What it means for the business:**
A user who is still active at Month 3 is highly likely to become a long-term power user. The product team's highest-leverage opportunity is not improving Month 3 retention — it is preventing the Month 0 to Month 1 cliff. Every intervention that keeps a user engaged through their first 30 days has compounding returns.

**Supported by:** Chart 1 (Cohort Retention Heatmap), SQL Query 1 output

---

### Finding 2: Referral Is the Highest Quality Acquisition Channel

**What the data shows:**
The retention curve comparison (Chart 2) shows that Referral users consistently outperform both Organic and Paid Ads users at every cohort checkpoint. Paid Ads users show the weakest retention despite representing the largest share of signups (45%). Referral users make up only 15% of total signups but show the strongest Month 1 and Month 3 retention rates.

The acquisition performance breakdown from Phase 2 further confirms this — Referral users have a higher onboarding completion rate than Paid Ads users, meaning the quality gap starts at the very first product interaction and compounds over time.

**What it means for the business:**
The current acquisition mix is inverted relative to quality. The channel spending the most budget (Paid Ads) is producing the lowest-quality users. Shifting even a modest portion of acquisition budget toward referral incentive programs could meaningfully improve the overall retention baseline without increasing total spend.

**Supported by:** Chart 2 (Retention Curves by Channel), Phase 2 channel performance aggregation

---

### Finding 3: The March 2026 Cohort Is a Clear Anomaly

**What the data shows:**
The March 2026 signup cohort shows a retention drop of approximately **40% below the February 2026 control cohort** at the Month 0 and Month 1 checkpoints. This is not a gradual drift — it is a sudden, cohort-specific collapse that does not appear in any cohort before or after March 2026, making it almost certainly tied to a specific event that month rather than a seasonal trend.

The diagnostic analysis (Chart 4, SQL Query 2) examined three possible explanations:

| Hypothesis | Evidence | Verdict |
|---|---|---|
| Platform-specific bug (Android or iOS) | KYC_Failed and Support_Ticket rates are consistent across both device types in March | Not isolated to one platform |
| Bad marketing campaign (poor-quality signups) | Channel mix in March is consistent with prior months | Not an acquisition quality issue |
| Backend or product release bug | Retention drops across all channels and devices simultaneously | Most likely explanation |

The fact that friction event rates (KYC_Failed, Support_Ticket_Opened) are flat between February and March means users were not hitting visible errors — they were simply not coming back. This pattern is more consistent with a silent UX regression or a backend performance degradation than a hard crash, which would have generated support tickets.

**What it means for the business:**
A single bad release caused measurable, lasting damage to an entire month's user cohort. This is a product reliability problem, not a marketing problem. The March 2026 cohort represents users who will likely never recover to normal retention levels, making the revenue impact permanent for that cohort.

**Supported by:** Chart 1 (March row highlighted), Chart 4 (Friction analysis), SQL Query 2 output

---

### Finding 4: Early Churn Has a Quantifiable Dollar Cost

**What the data shows:**
SQL Query 3 segmented all onboarded users into two groups — Active/Healthy users (those with activity beyond Month 0) and Early Churned users (those who went silent after Month 0). The transaction value comparison (Chart 5) shows a clear and measurable gap between the two segments in both average total spend and average transaction frequency.

Active users generate significantly more cumulative transaction volume than churned users. The revenue gap per user can be calculated directly from the Query 3 output and multiplied by the number of churned users in any given cohort to produce a hard dollar estimate of retention-related revenue loss.

**What it means for the business:**
Churn is not just a product metric — it is a revenue metric. For the March 2026 cohort specifically, the combination of an elevated churn rate and the per-user revenue gap produces a concrete estimate of how much that single release cost the business in lost transaction volume. This is the number that should be presented to leadership when requesting engineering resources for a post-mortem or a retention intervention program.

**Supported by:** Chart 5 (Churn vs Active value comparison), SQL Query 3 output

---

## Recommendations

---

### Recommendation 1: Shorten and Simplify the Onboarding Flow

**Why:** Finding 1 shows the Month 0 to Month 1 cliff is the single largest retention leak in the product. The onboarding funnel analysis (Chart 3) shows meaningful drop-off between each step, with the sharpest fall between Onboarding_Step_1 and Onboarding_Completed.

**Action:** Audit every screen in the onboarding flow for friction points — unnecessary form fields, slow KYC verification waits, or confusing UI. A/B test a shortened version of the flow. Even a 5–10 percentage point improvement in onboarding completion rate would compound significantly across 25,000 users per year.

**Expected impact:** Higher Month 0 activation rate → more users reaching their first transaction → stronger Month 1 retention baseline.

---

### Recommendation 2: Invest in a Referral Incentive Program

**Why:** Finding 2 shows Referral users have better retention than any other channel despite being the smallest segment. The current acquisition mix heavily favors Paid Ads, which produces the weakest long-term retention.

**Action:** Introduce or increase a referral reward program — for example, a cashback credit for both the referrer and the new user on their first successful transaction. Model the cost of the incentive against the higher expected LTV of a Referral user to confirm positive unit economics before scaling.

**Expected impact:** Shift acquisition mix toward higher-quality users, reduce effective churn rate at the portfolio level without increasing total acquisition spend.

---

### Recommendation 3: Conduct a Full Post-Mortem on the March 2026 Release

**Why:** Finding 3 identifies a clear, cohort-level retention collapse in March 2026 that is not explained by acquisition quality or platform-specific bugs. It is most consistent with a product or backend regression introduced in a release that month.

**Action:** Engineering and Product should pull the March 2026 release changelog and identify any changes to the core session flow, transaction processing, or app performance metrics (load times, API response times) that went live between February 28 and March 5, 2026. Implement a retention monitoring dashboard that automatically flags when any new cohort's Week 1 retention drops more than 15% below the 3-month rolling average.

**Expected impact:** Prevent a repeat incident. A single bad release silently damaged an entire month of users. An automated early-warning system would catch this within days rather than weeks.

---

### Recommendation 4: Build a Day-7 Retention Intervention

**Why:** Findings 1 and 4 together show that early churn is both extremely common and directly measurable in dollar terms. The highest-risk window is the first 7 days post-signup.

**Action:** Implement a targeted push notification or in-app message that fires at day 7 for any onboarded user who has not yet completed a successful transaction. The message should highlight the core value proposition — for example, a first-transaction cashback offer or a prompt to link their bank account if they have not yet done so.

**Expected impact:** Recovering even 10% of early-churned users through a day-7 nudge, at the measured per-user revenue gap, would produce a meaningful and trackable revenue recovery. This is a low-cost, high-confidence intervention with a directly measurable ROI.

---

## Limitations & Data Notes

**Synthetic data:** All records in this dataset were programmatically generated using the Faker library and custom NumPy distributions. The behavioral patterns (retention decay, channel quality differences, March 2026 anomaly) were deliberately encoded into the generation script. In a real production environment, the same analytical approach would apply but findings would reflect actual user behavior.

**No external context:** The analysis does not account for external factors such as marketing campaign spend by channel, competitor activity, macroeconomic conditions, or app store review trends — all of which could influence retention in a real dataset.

**Cohort coverage:** Cohorts from late 2026 (April–June 2026) have limited Month 1+ data due to the dataset end date of June 30, 2026. Retention estimates for these cohorts should be treated as early-stage and subject to revision as more data accumulates.

**Transaction amounts:** Amount distributions were modeled using uniform distributions within type-specific ranges (e.g. P2P $10–$50, Crypto $100–$1,000). Real transaction amount distributions would be more complex and likely right-skewed with heavy tails.

---

## Appendix: Project Files

| File | Location | Description |
|---|---|---|
| `phase1_strategy.md` | `reports/` | Business strategy, metric framework, hypotheses |
| `generate_fintech_data.py` | `scripts/` | Synthetic data generation script |
| `build_notebook.py` | `scripts/` | Phase 2 notebook builder |
| `phase2_cleaning_eda.ipynb` | `notebooks/` | Data cleaning and EDA notebook |
| `phase3_cohort_retention.sql` | `sql/` | Three SQL cohort models |
| `run_sql_models.py` | `scripts/` | DuckDB SQL execution script |
| `build_phase4_notebook.py` | `scripts/` | Phase 4 notebook builder |
| `phase4_visualization.ipynb` | `notebooks/` | Visualization notebook |
| `q1_cohort_retention_matrix.csv` | `data/sql_outputs/` | Query 1 results |
| `q2_march2026_diagnostic.csv` | `data/sql_outputs/` | Query 2 results |
| `q3_churn_value_estimation.csv` | `data/sql_outputs/` | Query 3 results |
| Chart 1 | `visuals/` | Cohort retention heatmap |
| Chart 2 | `visuals/` | Retention curves by signup channel |
| Chart 3 | `visuals/` | Onboarding funnel waterfall |
| Chart 4 | `visuals/` | March 2026 friction event analysis |
| Chart 5 | `visuals/` | Churn vs active user transaction value |

---

*End of Report*