<div align="center">

# 💰 GCP Billing Intelligence Agent

### AI-Powered Cost Monitoring · Google ADK · Vertex AI · BigQuery · Slack · GitHub Actions

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Google ADK](https://img.shields.io/badge/Google_ADK-Latest-4285F4?logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![Vertex AI](https://img.shields.io/badge/Vertex_AI-Gemini_2.5_Flash_Lite-8E44AD?logo=google-cloud&logoColor=white)](https://cloud.google.com/vertex-ai)
[![BigQuery](https://img.shields.io/badge/BigQuery-Billing_Export-34A853?logo=google-cloud&logoColor=white)](https://cloud.google.com/bigquery)
[![Slack](https://img.shields.io/badge/Slack-Notifications-4A154B?logo=slack&logoColor=white)](https://slack.com)
[![GitHub Actions](https://img.shields.io/badge/Scheduled-9:00_AM_IST_Daily-2088FF?logo=github-actions&logoColor=white)](https://github.com/bikram-singh/gcp-billing-agent/actions)
[![WIF](https://img.shields.io/badge/Auth-Workload_Identity_Federation-FF6D00?logo=googlecloud&logoColor=white)](https://cloud.google.com/iam/docs/workload-identity-federation)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

*An AI-powered GCP Organization Billing Intelligence Agent built with Google ADK and Vertex AI. Fetches billing data across all GCP projects, detects cost anomalies using 7-day rolling averages, generates color-coded Excel and CSV reports, and sends rich formatted alerts to Slack - triggered automatically every day at 9:00 AM IST via GitHub Actions. Zero stored credentials - powered by Workload Identity Federation.*

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Agent Tools](#-agent-tools)
- [Repository Structure](#-repository-structure)
- [Prerequisites](#-prerequisites)
- [BigQuery Billing Export Setup](#-bigquery-billing-export-setup)
- [GitHub Actions Setup](#-github-actions-setup)
- [Excel Report Structure](#-excel-report-structure)
- [Anomaly Detection Logic](#-anomaly-detection-logic)
- [Slack Notifications](#-slack-notifications)
- [Scheduled Pipeline](#-scheduled-pipeline)
- [Local Development - ADK Web UI](#-local-development---adk-web-ui)
- [Snapshots](#-snapshots)
- [Repository](#-repository)

---

## 🌐 Overview

The **GCP Billing Intelligence Agent** is a fully automated cost monitoring solution for GCP organizations. It uses **Google ADK** with **Vertex AI** to intelligently orchestrate billing data collection, anomaly detection, report generation, and Slack alerting - all without any stored credentials.

The pipeline runs automatically every day at **9:00 AM IST** via GitHub Actions - no manual trigger needed.

### 🔑 Key Facts

| Property | Value |
|---|---|
| 🤖 **Agent Framework** | Google Agent Development Kit (ADK) |
| 🧠 **LLM** | Gemini 2.5 Flash Lite via **Vertex AI** |
| ☁️ **Cloud Platform** | Google Cloud Platform |
| 🔐 **Authentication** | Workload Identity Federation (WIF) - zero JSON keys |
| 📊 **Data Source** | BigQuery Billing Export (`gcp_billing_export_v1`) |
| 📢 **Notifications** | Slack (Block Kit rich messages + file attachments) |
| 📁 **Output Format** | Excel (.xlsx) multi-sheet + CSV |
| 🐍 **Language** | Python 3.11+ |
| ⏰ **Scheduled Run** | GitHub Actions · Daily at 9:00 AM IST |
| 🔄 **CI/CD** | `billing_agent.yml` · `main.py` |

### ✨ What It Does

| Capability | Description |
|---|---|
| 📊 **Org Billing Summary** | Fetches total spend across ALL GCP projects |
| 📋 **Project Detail** | Day-by-day cost breakdown per project per service |
| 🔍 **Service Breakdown** | Total costs grouped by GCP service |
| 🚨 **Anomaly Detection** | Flags cost spikes vs 7-day rolling average |
| 📈 **Top Cost Drivers** | Ranks top 10 project + service + SKU combinations |
| 📊 **Excel Report** | 5-sheet color-coded report with critical/warning highlights |
| 📄 **CSV Report** | Flat report with org summary, anomalies, top drivers |
| 📣 **Slack Report** | Rich Block Kit message + Excel/CSV file attachments |
| ⏰ **Auto Schedule** | GitHub Actions cron - runs daily at 9:00 AM IST |

---

## 🏛️ Architecture

```
GitHub Actions (cron: 9:00 AM IST daily)
              │
              ▼
    WIF Authentication
    (github-actions-pool / bikram-singh-provider)
              │
              ▼
    Google ADK Agent
    (Gemini 2.5 Flash Lite via Vertex AI)
              │
    __________|____________________________
   |           |           |              |
   ▼           ▼           ▼              ▼
BigQuery    BigQuery    Report Gen     Slack SDK
Billing     Anomaly     (Excel/CSV)    (Message +
Queries     Detection   openpyxl       File Upload)
```

### 🔄 Layer Breakdown

| Layer | Components |
|---|---|
| **Trigger Layer** | GitHub Actions Cron (9:00 AM IST) · Developer / ADK Web UI |
| **Auth Layer** | Workload Identity Federation → OAuth token → Vertex AI + GCP APIs |
| **AI Agent Layer** | ADK Root Agent (`billing_agent.py`) · Gemini 2.5 Flash Lite via Vertex AI |
| **Data Layer** | BigQuery Billing Export · 5 Query Tools · Error Handling |
| **Report Layer** | Excel (5 sheets, color-coded) · CSV (flat report) |
| **Notification Layer** | Slack Block Kit messages · Excel + CSV file attachments |

### 🔄 Full Pipeline Flow

```
Step 1  fetch_org_billing_summary      →  Total spend across all projects
Step 2  fetch_project_billing_detail   →  Day-by-day breakdown per project
Step 3  fetch_service_cost_breakdown   →  Costs grouped by GCP service
Step 4  detect_billing_anomalies       →  7-day rolling avg spike detection
Step 5  fetch_top_cost_drivers         →  Top 10 project + service + SKU
Step 6  generate_excel_report          →  5-sheet color-coded Excel file
Step 7  generate_csv_report            →  Flat CSV report
Step 8  send_slack_report              →  Rich Slack message + file uploads
```

---

## 🛠️ Agent Tools

The agent exposes **8 tools** that Gemini (via Vertex AI) orchestrates automatically:

### 1️⃣ `fetch_org_billing_summary`
Fetches total cost summary across ALL projects in the organization grouped by project for the last N days.

### 2️⃣ `fetch_project_billing_detail`
Fetches day-by-day cost breakdown per project, optionally filtered to a specific project ID.

### 3️⃣ `fetch_service_cost_breakdown`
Fetches total costs grouped by GCP service (Compute Engine, Cloud SQL, GKE, etc.) across all projects.

### 4️⃣ `detect_billing_anomalies`
Detects cost spikes using a 7-day rolling average comparison:

| Severity | Condition |
|---|---|
| 🔴 **CRITICAL** | Daily cost > 50% above 7-day average |
| 🟡 **WARNING** | Daily cost 20-50% above 7-day average |
| ✅ **Normal** | Daily cost within 20% of 7-day average |

### 5️⃣ `fetch_top_cost_drivers`
Ranks the top N project + service + SKU combinations by total cost for the period.

### 6️⃣ `generate_excel_report`
Generates a multi-sheet color-coded Excel report with all billing data.

### 7️⃣ `generate_csv_report`
Generates a flat CSV report with org summary, anomalies, and top drivers.

### 8️⃣ `send_slack_report`
Sends a structured Slack Block Kit message and uploads Excel + CSV files as thread attachments.

---

## 📁 Repository Structure

```
gcp-billing-agent/
│
├── 📁 .github/
│   └── 📁 workflows/
│       └── 📄 billing_agent.yml        # GitHub Actions - 9:00 AM IST daily
│
├── 📁 agent/
│   ├── 📄 __init__.py                  # ADK Web UI entry point (root_agent)
│   ├── 📄 billing_agent.py             # ADK Agent definition + async runner
│   ├── 📄 bigquery_tools.py            # 5 BigQuery tools with error handling
│   ├── 📄 report_tools.py              # Excel + CSV report generation
│   └── 📄 slack_tools.py               # Slack Block Kit + file upload
│
├── 📁 sql/
│   └── 📄 billing_queries.sql          # Standalone SQL for manual testing
│
├── 📁 reports/                         # Local report output directory
│
├── 📄 main.py                          # CLI entry point (--days-back, --month)
├── 📄 requirements.txt                 # Python dependencies
├── 📄 .env.example                     # Environment variable template
└── 📄 README.md                        # This file
```

---

## ✅ Prerequisites

| Requirement | Details |
|---|---|
| 🐍 **Python** | 3.11 or higher |
| ☁️ **GCP Account** | With Billing Export enabled |
| 🔐 **WIF Setup** | Workload Identity Federation configured |
| 💬 **Slack Workspace** | With a Bot Token (`xoxb-...`) |
| 📊 **BigQuery** | Billing Export dataset (`billing_export`) |

### 🔌 GCP APIs Required

```bash
gcloud services enable \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  --project=YOUR_PROJECT_ID
```

### 🔐 IAM Roles Required for Service Account

| Role | Purpose |
|---|---|
| `roles/bigquery.dataViewer` | Read billing export dataset |
| `roles/bigquery.jobUser` | Run BigQuery query jobs |
| `roles/aiplatform.user` | Call Vertex AI (Gemini) models |
| `roles/billing.viewer` | View organization billing (optional) |
| `roles/iam.workloadIdentityUser` | Allow WIF authentication |

---

## 📊 BigQuery Billing Export Setup

### Step 1 - Enable Billing Export

```
GCP Console → Billing → Billing Export → BigQuery Export
→ Standard usage cost → Edit Settings
→ Project: your-gcp-project
→ Dataset: billing_export
→ Save
```

> ⚠️ **Important:** GCP auto-creates the dataset and table. Data takes **24-48 hours** to populate after enabling.

### Step 2 - Verify Export is Active

```bash
bq ls --project_id=YOUR_PROJECT_ID

# Expected output:
#  datasetId
#  ──────────────
#  billing_export
```

### Step 3 - Verify Table Exists

```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as rows,
          MIN(DATE(usage_start_time)) as earliest,
          MAX(DATE(usage_start_time)) as latest
   FROM `YOUR_PROJECT.billing_export.gcp_billing_export_v1`'
```

### Dataset Location

> ⚠️ **Critical:** GCP Billing Export tables are always stored in **US multi-region**, NOT `us-central1`. The agent is configured with `location="US"` to handle this correctly.

---

## ⚙️ GitHub Actions Setup

### 🔑 Required GitHub Secrets

Go to repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value |
|---|---|
| `GCP_PROJECT_ID` | `your-gcp-project-id` |
| `GCP_WIF_PROVIDER_NONPROD` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER` |
| `GCP_WIF_SERVICE_ACCOUNT_NONPROD` | `github-actions-deploy@PROJECT.iam.gserviceaccount.com` |
| `BQ_BILLING_DATASET` | `billing_export` |
| `BQ_BILLING_TABLE` | `gcp_billing_export_v1` |
| `GCP_ORG_ID` | `125899388883` |
| `SLACK_BOT_TOKEN` | `xoxb-your-token` |
| `SLACK_CHANNEL_ID` | `C0XXXXXXXXX` |

> **Note:** No `GOOGLE_API_KEY` needed - Vertex AI uses WIF OAuth token directly.

### 🔗 WIF Binding for This Repo

Run once in Cloud Shell to allow this repo to authenticate:

```bash
SA="github-actions-deploy@YOUR_PROJECT.iam.gserviceaccount.com"

POOL_NUMBER=$(gcloud projects describe YOUR_PROJECT \
  --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding $SA \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$POOL_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/bikram-singh/gcp-billing-agent" \
  --project=YOUR_PROJECT
```

### 🔐 Auth Flow

```
GitHub Actions
      ↓
WIF OIDC token (auto-generated per run)
      ↓
GCP validates → issues OAuth token
      ↓
Works for ALL services:
├── BigQuery API     ✅
├── Vertex AI        ✅
└── Cloud Billing    ✅
```

No JSON keys. No stored credentials. Tokens expire when the job ends.

### ⚡ Manual Trigger

```
GitHub → Actions → GCP Billing Agent - Scheduled Report
→ Run workflow
→ days_back: 30 (default)
→ month: 2025-06 (optional - for specific month report)
→ Run workflow
```

---

## 📊 Excel Report Structure

The generated Excel report contains **5 color-coded sheets**:

| Sheet | Contents | Color |
|---|---|---|
| **Executive Summary** | Period, total cost, project count, anomaly count, per-project table | Navy header |
| **Project Detail** | Day-by-day cost per project per service | Navy header |
| **Service Breakdown** | Total cost per GCP service across all projects | Blue header |
| **Anomalies** | Color-coded critical/warning rows with % change vs 7-day avg | Red header |
| **Top Cost Drivers** | Ranked project + service + SKU combinations | Blue header |

### Color Coding in Anomalies Sheet

| Color | Meaning |
|---|---|
| 🔴 Red row | CRITICAL - cost spike ≥ 50% above 7-day average |
| 🟡 Orange row | WARNING - cost spike 20-49% above 7-day average |
| ⬜ Alternating | Normal rows |

---

## 🔍 Anomaly Detection Logic

The agent uses a **7-day rolling average** comparison per `(project, service)` pair:

```sql
pct_change = (today_cost - avg_7d_cost) / avg_7d_cost * 100

CRITICAL: pct_change >= 50%   → Red in Excel, immediate Slack alert
WARNING:  pct_change >= 20%   → Orange in Excel, informational
Normal:   pct_change < 20%    → No flag
```

### Why Per (Project, Service) Pair?

A GKE spike in one project does not mask a Cloud SQL spike in another. Each project-service combination is evaluated independently against its own 7-day baseline.

---

## 📣 Slack Notifications

```
📊 GCP Organization Billing Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 GCP Billing Report | 2025-06-18 03:30 UTC
Period: 2025-05-18 → 2025-06-18 | Total Spend: USD 12,847.33 | Projects: 8

🚨 Anomaly Detection
🔴 CRITICAL dhg-vaccine-rateauto-nonpord | Cloud SQL | 2025-06-17 | +87.3%
            ($234.12 vs avg $125.00)
🟡 WARNING  dhg-vaccine-rateauto-dev | GKE | 2025-06-16 | +31.2%
            ($89.40 vs avg $68.14)

💸 Top 5 Cost Drivers
1. dhg-vaccine-rateauto-nonpord | Cloud SQL for PostgreSQL | $3,241.00
2. dhg-vaccine-rateauto-nonpord | Kubernetes Engine        | $2,887.50
3. dhg-vaccine-rateauto-dev     | Compute Engine           | $1,203.00
4. dhg-vaccine-rateauto-nonpord | Cloud Storage            | $892.00
5. dhg-vaccine-rateauto-dev     | Cloud SQL                | $654.00

🤖 Generated by GCP Billing Agent | Reports attached below
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 billing_report_20250618.xlsx   [Excel Spreadsheet]
📎 billing_report_20250618.csv    [CSV File]
```

### Failure Notification

```
❌ GCP Billing Agent FAILED
Workflow: GCP Billing Agent - Scheduled Report
Run: 1234567890
Triggered by: schedule
See: https://github.com/bikram-singh/gcp-billing-agent/actions/runs/...
```

---

## ⏰ Scheduled Pipeline

### How It Works

```
GitHub Actions Cron (9:00 AM IST daily)
         ↓
main.py --days-back 30
         ↓
ADK Agent → Vertex AI (Gemini 2.5 Flash Lite)
         ↓
Gemini orchestrates all 8 tools:
   Step 1 → fetch_org_billing_summary
   Step 2 → fetch_project_billing_detail
   Step 3 → fetch_service_cost_breakdown
   Step 4 → detect_billing_anomalies
   Step 5 → fetch_top_cost_drivers
   Step 6 → generate_excel_report
   Step 7 → generate_csv_report
   Step 8 → send_slack_report
         ↓
Excel + CSV artifacts saved in GitHub Actions (90 days)
Slack report delivered to #gcp-billing-alerts
```

### Schedule Configuration

| Setting | Value |
|---|---|
| **IST Time** | 9:00 AM |
| **UTC Time** | 3:30 AM |
| **Cron** | `30 3 * * *` |
| **Days** | Every day |
| **Workflow file** | `.github/workflows/billing_agent.yml` |

### Retry Logic

The workflow includes automatic retry with 60-second delays for Vertex AI quota recovery:

```yaml
for attempt in 1 2 3; do
  python main.py --days-back "$DAYS_BACK" && break
  echo "Retrying in 60 seconds..."
  sleep 60
done
```

---

## 💻 Local Development - ADK Web UI

### Step 1 - Set Environment Variables (PowerShell)

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "TRUE"
$env:GOOGLE_CLOUD_PROJECT = "your-gcp-project-id"
$env:GOOGLE_CLOUD_LOCATION = "us-central1"
$env:GCP_PROJECT_ID = "your-gcp-project-id"
$env:BQ_BILLING_DATASET = "billing_export"
$env:BQ_BILLING_TABLE = "gcp_billing_export_v1"
$env:GCP_ORG_ID = "125899388883"
$env:SLACK_BOT_TOKEN = "xoxb-your-token"
$env:SLACK_CHANNEL = "C0XXXXXXXXX"
$env:REPORTS_DIR = "D:\gcp-billing-agent\reports"
```

### Step 2 - Authenticate Locally

```bash
gcloud auth application-default login
```

### Step 3 - Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 - Run ADK Web UI

```bash
# Run from the parent folder (contains agent/ directory)
cd D:\gcp-billing-agent
adk web
```

### Step 5 - Open Browser

```
http://localhost:8000
```

Select **agent** from the dropdown and type:

```
Run full billing analysis for last 30 days
```

### Step 6 - Run via CLI

```bash
# Last 30 days (default)
python main.py

# Last 7 days
python main.py --days-back 7

# Specific month
python main.py --month 2025-05
```

---

## 🔧 Troubleshooting

### Vertex AI 404 NOT_FOUND

```
Model not found or project does not have access
```

**Fix:** Ensure `GOOGLE_GENAI_USE_VERTEXAI=TRUE` is set BEFORE any ADK imports. Already handled in `main.py` and `billing_agent.py`.

### BigQuery Table Not Found (us-central1)

```
Not found: Table *** was not found in location us-central1
```

**Fix:** Billing Export tables are always in **US multi-region**. The agent uses `location="US"` in the BigQuery client. Already fixed in `bigquery_tools.py`.

### WIF Permission Denied

New repo needs SA impersonation binding:

```bash
gcloud iam service-accounts add-iam-policy-binding $SA \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$POOL_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/bikram-singh/gcp-billing-agent"
```

### Slack File Upload Fails

Ensure the bot is invited to the channel:

```
/invite @GCP Billing Bot
```

And `files:write` scope is added to the Slack App.

### No Billing Data Yet

Billing Export takes **24-48 hours** to populate after enabling. Verify:

```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) FROM `YOUR_PROJECT.billing_export.gcp_billing_export_v1`'
```

---

## 📸 Snapshots

### 1️⃣ ADK Web UI - Agent Running
![ADK Web UI](docs/snapshots/1_adk_web_ui.png)

---

### 2️⃣ Full Pipeline Execution - All 8 Tools Chained
![Full Pipeline](docs/snapshots/2_full_pipeline_execution.png)

---

### 3️⃣ BigQuery Billing Export Table
![BigQuery Table](docs/snapshots/3_bigquery_table.png)

---

### 4️⃣ Slack Notification - Rich Block Kit Report + Excel/CSV Attachments
![Slack Notification](docs/snapshots/4_slack_notification.png)

---

### 5️⃣ GitHub Actions - Daily Scheduled Run
![GitHub Actions](docs/snapshots/5_github_actions_scheduled_run.png)

---

### 6️⃣ Excel Report - 5 Color-Coded Sheets
![Excel Report](docs/snapshots/6_excel_report.png)

---

## 🔗 Repository

| Repository | Purpose |
|---|---|
| [`gcp-billing-agent`](https://github.com/bikram-singh/gcp-billing-agent) | GCP Billing Intelligence Agent · ADK · Vertex AI · BigQuery · Slack |
| [`gcp-inventory-agent-vertexai`](https://github.com/bikram-singh/gcp-inventory-agent-vertexai) | GCP VM Inventory Agent · Vertex AI · WIF · GitHub Actions |

---

<div align="center">

**Maintained by Bikram Singh**

`dhg-vaccine-rateauto-nonpord` · `gcpcloudhub.shop` · `us-central1` · Google Cloud Platform

*Built with Google ADK · Vertex AI · BigQuery · Slack · GitHub Actions*

</div>
