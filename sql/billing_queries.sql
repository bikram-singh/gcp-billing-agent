-- =============================================================================
-- GCP Billing Export BigQuery Setup
-- Run these in BigQuery console or via bq CLI
-- =============================================================================

-- Step 1: Create the billing dataset (if not already created via GCP Console)
-- NOTE: In practice, GCP creates this dataset automatically when you enable
-- Cloud Billing export in the GCP Console. These are helper queries.

-- Step 2: Verify billing export table exists and has data
SELECT
    COUNT(*)                    AS total_rows,
    MIN(DATE(usage_start_time)) AS earliest_date,
    MAX(DATE(usage_start_time)) AS latest_date,
    COUNT(DISTINCT project.id)  AS project_count
FROM `YOUR_PROJECT_ID.YOUR_BILLING_DATASET.gcp_billing_export_v1`
WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY);

-- Step 3: Check available projects in billing data
SELECT
    project.id          AS project_id,
    project.name        AS project_name,
    COUNT(*)            AS row_count,
    ROUND(SUM(cost), 2) AS total_cost,
    currency
FROM `YOUR_PROJECT_ID.YOUR_BILLING_DATASET.gcp_billing_export_v1`
WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY project_id, project_name, currency
ORDER BY total_cost DESC;

-- Step 4: Test anomaly detection query manually
WITH daily AS (
    SELECT
        project.id              AS project_id,
        project.name            AS project_name,
        service.description     AS service,
        DATE(usage_start_time)  AS usage_date,
        ROUND(SUM(cost), 4)     AS daily_cost,
        currency
    FROM `YOUR_PROJECT_ID.YOUR_BILLING_DATASET.gcp_billing_export_v1`
    WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 44 DAY)
    GROUP BY project_id, project_name, service, usage_date, currency
),
rolling AS (
    SELECT
        *,
        AVG(daily_cost) OVER (
            PARTITION BY project_id, service
            ORDER BY usage_date
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS avg_7d
    FROM daily
)
SELECT
    project_id,
    project_name,
    service,
    usage_date,
    daily_cost,
    ROUND(avg_7d, 4)                                        AS avg_7d_cost,
    ROUND(SAFE_DIVIDE(daily_cost - avg_7d, avg_7d) * 100, 1) AS pct_change,
    currency
FROM rolling
WHERE
    usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND avg_7d IS NOT NULL
    AND avg_7d > 0
    AND daily_cost > avg_7d * 1.20   -- 20% threshold
ORDER BY pct_change DESC
LIMIT 20;

-- Step 5: Top cost drivers query test
SELECT
    project.id              AS project_id,
    project.name            AS project_name,
    service.description     AS service,
    sku.description         AS sku,
    ROUND(SUM(cost), 2)     AS total_cost,
    currency
FROM `YOUR_PROJECT_ID.YOUR_BILLING_DATASET.gcp_billing_export_v1`
WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY project_id, project_name, service, sku, currency
ORDER BY total_cost DESC
LIMIT 10;
