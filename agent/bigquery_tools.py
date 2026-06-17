"""
BigQuery tools for GCP Billing Agent
Queries the GCP Billing Export table in BigQuery
"""

import os
from datetime import datetime, timedelta
from typing import Any
from google.cloud import bigquery

# BigQuery config - set via environment variables
BQ_PROJECT    = os.environ.get("BQ_PROJECT_ID", os.environ.get("GCP_PROJECT_ID", ""))
BQ_DATASET    = os.environ.get("BQ_BILLING_DATASET", "billing_export")
BQ_TABLE      = os.environ.get("BQ_BILLING_TABLE", "gcp_billing_export_v1")
ORG_ID        = os.environ.get("GCP_ORG_ID", "")

_client: bigquery.Client | None = None


def _bq() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=BQ_PROJECT)
    return _client


def _date_range(days_back: int) -> tuple[str, str]:
    end   = datetime.utcnow().date()
    start = end - timedelta(days=days_back)
    return str(start), str(end)


# ---------------------------------------------------------------------------
# Tool 1: Organization billing summary
# ---------------------------------------------------------------------------

def fetch_org_billing_summary(days_back: int = 30) -> dict[str, Any]:
    """
    Fetch total cost summary across ALL projects in the organization
    grouped by project, for the last N days.

    Args:
        days_back: Number of days to look back from today

    Returns:
        dict with 'total_cost', 'currency', 'period', 'projects' list
    """
    start, end = _date_range(days_back)
    query = f"""
    SELECT
        project.id                          AS project_id,
        project.name                        AS project_name,
        ROUND(SUM(cost), 2)                 AS total_cost,
        currency,
        MIN(DATE(usage_start_time))         AS period_start,
        MAX(DATE(usage_end_time))           AS period_end
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
    WHERE DATE(usage_start_time) BETWEEN '{start}' AND '{end}'
    GROUP BY project_id, project_name, currency
    ORDER BY total_cost DESC
    """
    rows = list(_bq().query(query).result())
    projects = [dict(r) for r in rows]
    total    = round(sum(p["total_cost"] for p in projects), 2)
    currency = projects[0]["currency"] if projects else "USD"

    return {
        "total_cost": total,
        "currency":   currency,
        "period":     {"start": start, "end": end},
        "projects":   projects,
        "project_count": len(projects),
    }


# ---------------------------------------------------------------------------
# Tool 2: Per-project billing detail
# ---------------------------------------------------------------------------

def fetch_project_billing_detail(
    days_back: int = 30,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Fetch day-by-day cost breakdown per project (optionally filtered to one project).

    Args:
        days_back:  Number of days to look back
        project_id: Optional GCP project ID to filter

    Returns:
        dict with 'rows' list of daily cost records
    """
    start, end = _date_range(days_back)
    project_filter = f"AND project.id = '{project_id}'" if project_id else ""
    query = f"""
    SELECT
        project.id                      AS project_id,
        project.name                    AS project_name,
        DATE(usage_start_time)          AS usage_date,
        service.description             AS service,
        ROUND(SUM(cost), 4)             AS daily_cost,
        currency
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
    WHERE DATE(usage_start_time) BETWEEN '{start}' AND '{end}'
    {project_filter}
    GROUP BY project_id, project_name, usage_date, service, currency
    ORDER BY usage_date DESC, daily_cost DESC
    """
    rows = [dict(r) for r in _bq().query(query).result()]
    return {"rows": rows, "record_count": len(rows), "period": {"start": start, "end": end}}


# ---------------------------------------------------------------------------
# Tool 3: Service-level cost breakdown
# ---------------------------------------------------------------------------

def fetch_service_cost_breakdown(days_back: int = 30) -> dict[str, Any]:
    """
    Fetch total costs grouped by GCP service across all projects.

    Args:
        days_back: Number of days to look back

    Returns:
        dict with 'services' list sorted by cost descending
    """
    start, end = _date_range(days_back)
    query = f"""
    SELECT
        service.id                      AS service_id,
        service.description             AS service_name,
        ROUND(SUM(cost), 2)             AS total_cost,
        currency,
        COUNT(DISTINCT project.id)      AS project_count
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
    WHERE DATE(usage_start_time) BETWEEN '{start}' AND '{end}'
    GROUP BY service_id, service_name, currency
    ORDER BY total_cost DESC
    """
    rows = [dict(r) for r in _bq().query(query).result()]
    return {"services": rows, "period": {"start": start, "end": end}}


# ---------------------------------------------------------------------------
# Tool 4: Anomaly Detection
# ---------------------------------------------------------------------------

def detect_billing_anomalies(
    threshold_pct: float = 20.0,
    days_back: int = 30,
) -> dict[str, Any]:
    """
    Detect billing anomalies: projects/services where cost spiked by more than
    threshold_pct% vs the prior 7-day average.

    Args:
        threshold_pct: Percentage increase that flags an anomaly (default 20%)
        days_back:     Window to scan for anomalies

    Returns:
        dict with 'anomalies' list and 'summary'
    """
    start, end = _date_range(days_back)
    # Compare each day's cost vs 7-day rolling avg for each project+service
    query = f"""
    WITH daily AS (
        SELECT
            project.id              AS project_id,
            project.name            AS project_name,
            service.description     AS service,
            DATE(usage_start_time)  AS usage_date,
            ROUND(SUM(cost), 4)     AS daily_cost,
            currency
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE DATE(usage_start_time) BETWEEN
            DATE_SUB('{start}', INTERVAL 14 DAY) AND '{end}'
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
        ROUND(avg_7d, 4)    AS avg_7d_cost,
        ROUND(
            SAFE_DIVIDE(daily_cost - avg_7d, avg_7d) * 100, 1
        )                   AS pct_change,
        currency
    FROM rolling
    WHERE
        usage_date BETWEEN '{start}' AND '{end}'
        AND avg_7d IS NOT NULL
        AND avg_7d > 0
        AND daily_cost > avg_7d * (1 + {threshold_pct}/100)
    ORDER BY pct_change DESC
    LIMIT 50
    """
    rows = [dict(r) for r in _bq().query(query).result()]

    critical = [r for r in rows if r.get("pct_change", 0) >= 50]
    warning  = [r for r in rows if 20 <= r.get("pct_change", 0) < 50]

    return {
        "anomalies":         rows,
        "anomaly_count":     len(rows),
        "critical_count":    len(critical),
        "warning_count":     len(warning),
        "threshold_pct":     threshold_pct,
        "period":            {"start": start, "end": end},
        "summary":           (
            f"{len(rows)} anomalies detected "
            f"({len(critical)} critical, {len(warning)} warning)"
        ),
    }


# ---------------------------------------------------------------------------
# Tool 5: Top cost drivers
# ---------------------------------------------------------------------------

def fetch_top_cost_drivers(
    days_back: int = 30,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Fetch top N cost drivers (project + service combinations) for the period.

    Args:
        days_back: Number of days to look back
        top_n:     Number of top drivers to return (default 10)

    Returns:
        dict with 'drivers' list
    """
    start, end = _date_range(days_back)
    query = f"""
    SELECT
        project.id              AS project_id,
        project.name            AS project_name,
        service.description     AS service,
        sku.description         AS sku,
        ROUND(SUM(cost), 2)     AS total_cost,
        currency
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
    WHERE DATE(usage_start_time) BETWEEN '{start}' AND '{end}'
    GROUP BY project_id, project_name, service, sku, currency
    ORDER BY total_cost DESC
    LIMIT {top_n}
    """
    rows = [dict(r) for r in _bq().query(query).result()]
    return {"drivers": rows, "top_n": top_n, "period": {"start": start, "end": end}}
