# GCP Organization Billing Agent

An AI agent built with **Google ADK + BigQuery + Vertex AI** that fetches your full GCP organization billing data, detects cost anomalies, generates Excel/CSV reports, and sends structured Slack alerts - scheduled daily via GitHub Actions.

Built on the same proven patterns as the CloudSentinel VM Inventory Agent (Vertex AI + WIF, no JSON keys).

---

## Architecture

```
GitHub Actions (cron: daily 9 AM IST)
        |
        v
  WIF Authentication
  (github-actions-pool / bikram-singh-provider)
        |
        v
  Google ADK Agent (Vertex AI / Gemini 2.0 Flash)
        |
   _____|______________________________
  |           |           |            |
  v           v           v            v
BigQuery   BigQuery   Report Gen    Slack SDK
Billing    Anomaly    (Excel/CSV)   (Message +
Queries    Detection  openpyxl      File Upload)
```

**Key components:**

- `agent/billing_agent.py` - ADK Agent definition + async runner
- `agent/bigquery_tools.py` - 5 BigQuery tools (summary, detail, services, anomalies, top drivers)
- `agent/report_tools.py` - Excel (multi-sheet, color-coded) + CSV generation
- `agent/slack_tools.py` - Slack message blocks + file upload
- `.github/workflows/billing_agent.yml` - Scheduled GitHub Actions workflow

---

## Step-by-Step Setup Guide

### Step 1 - Enable GCP Billing Export to BigQuery

This is the data source for the entire agent. You must do this first and wait 24h for data to populate.

**1.1 Open GCP Console**

```
GCP Console → Billing → (select your billing account) → Billing Export
```

**1.2 Enable Standard Usage Cost export**

- Click **Edit Settings** under "Standard usage cost"
- Select the GCP project where you want BigQuery data stored (use your agent's project)
- Create or select a BigQuery dataset - name it `billing_export`
- Click **Save**

GCP will auto-create: `YOUR_PROJECT.billing_export.gcp_billing_export_v1`

**1.3 (Optional) Enable for Organization**

If you have a GCP Organization and want ALL project costs in one table:

```
GCP Console → Billing → Billing Export
→ Enable "Standard usage cost" at the Organization Billing Account level
```

This exports data for every project under the org into the same table.

**1.4 Verify data is flowing (wait ~24 hours then run)**

```bash
bq query --use_legacy_sql=false '
SELECT COUNT(*) as rows,
       MIN(DATE(usage_start_time)) as earliest,
       MAX(DATE(usage_start_time)) as latest
FROM `YOUR_PROJECT.billing_export.gcp_billing_export_v1`'
```

---

### Step 2 - Enable Required GCP APIs

```bash
export PROJECT_ID="your-gcp-project-id"

gcloud config set project $PROJECT_ID

gcloud services enable \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  --project=$PROJECT_ID
```

---

### Step 3 - IAM Permissions for Service Account

Use your existing shared WIF service account (`github-actions-deploy@...`).

**3.1 Grant BigQuery permissions**

```bash
SA="github-actions-deploy@dhg-vaccine-rateauto-nonpord.iam.gserviceaccount.com"
PROJECT_ID="your-gcp-project-id"
BILLING_PROJECT="project-where-billing-bq-lives"

# BigQuery read access on the billing export dataset
gcloud projects add-iam-policy-binding $BILLING_PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/bigquery.dataViewer"

# BigQuery job runner (to execute queries)
gcloud projects add-iam-policy-binding $BILLING_PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/bigquery.jobUser"

# Vertex AI for ADK / Gemini inference
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/aiplatform.user"
```

**3.2 (Organization-level billing) Optional**

If billing data spans a GCP Organization, you may need:

```bash
# At the organization level
ORG_ID="123456789012"

gcloud organizations add-iam-policy-binding $ORG_ID \
  --member="serviceAccount:$SA" \
  --role="roles/billing.viewer"
```

---

### Step 4 - Set Up Slack App

**4.1 Create Slack App**

- Go to https://api.slack.com/apps → **Create New App** → **From Scratch**
- Name: `GCP Billing Agent`
- Select your workspace

**4.2 Add Bot Token Scopes**

Under **OAuth & Permissions** → **Scopes** → **Bot Token Scopes**, add:

```
chat:write
files:write
channels:read
```

**4.3 Install App to Workspace**

- Click **Install to Workspace** → **Allow**
- Copy the **Bot User OAuth Token** (starts with `xoxb-...`)

**4.4 Add bot to your Slack channel**

In Slack, open your `#gcp-billing-alerts` channel:
```
/invite @GCP Billing Agent
```

---

### Step 5 - GitHub Repository Setup

**5.1 Create the repository**

```bash
# Create repo (or use existing)
gh repo create gcp-billing-agent --private --description "GCP Org Billing Agent - ADK + BigQuery"
cd gcp-billing-agent

# Copy all agent files from this guide
# Push to main
git add .
git commit -m "feat: initial GCP billing agent setup"
git push origin main
```

**5.2 Add GitHub Secrets**

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|---|---|
| `GCP_WIF_PROVIDER_NONPROD` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/bikram-singh-provider` |
| `GCP_WIF_SERVICE_ACCOUNT_NONPROD` | `github-actions-deploy@dhg-vaccine-rateauto-nonpord.iam.gserviceaccount.com` |
| `GCP_PROJECT_ID` | Your GCP project ID |
| `BQ_BILLING_DATASET` | `billing_export` |
| `BQ_BILLING_TABLE` | `gcp_billing_export_v1` |
| `GCP_ORG_ID` | Your org ID (optional) |
| `SLACK_BOT_TOKEN` | `xoxb-your-token` |
| `SLACK_CHANNEL` | `#gcp-billing-alerts` |

**5.3 Add WIF binding for the new repo**

If this is a new repo, add it to your WIF pool's attribute condition:

```bash
# Check current attribute condition on your WIF provider
gcloud iam workload-identity-pools providers describe bikram-singh-provider \
  --workload-identity-pool=github-actions-pool \
  --location=global \
  --project=dhg-vaccine-rateauto-nonpord

# Grant the new repo SA impersonation rights
SA="github-actions-deploy@dhg-vaccine-rateauto-nonpord.iam.gserviceaccount.com"
POOL_PROJECT="dhg-vaccine-rateauto-nonpord"
POOL_NUMBER=$(gcloud projects describe $POOL_PROJECT --format='value(projectNumber)')
GITHUB_ORG="bikram-singh"
REPO="gcp-billing-agent"

gcloud iam service-accounts add-iam-policy-binding $SA \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$POOL_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/$GITHUB_ORG/$REPO" \
  --project=dhg-vaccine-rateauto-nonpord
```

---

### Step 6 - Local Testing

**6.1 Create virtualenv and install deps**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**6.2 Set environment variables**

```bash
cp .env.example .env
# Edit .env with your values
export $(cat .env | xargs)
```

**6.3 Authenticate locally (use your personal ADC)**

```bash
gcloud auth application-default login
# or if using a service account key for local dev only:
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

**6.4 Test BigQuery queries first**

```bash
# Verify billing data is accessible
bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID \
  "SELECT COUNT(*) FROM \`$GCP_PROJECT_ID.$BQ_BILLING_DATASET.$BQ_BILLING_TABLE\`"
```

**6.5 Run the agent**

```bash
# Default: last 30 days
python main.py

# Custom: last 7 days
python main.py --days-back 7

# Specific month
python main.py --month 2025-05
```

---

### Step 7 - GitHub Actions Deployment

**7.1 The workflow runs automatically**

The workflow file at `.github/workflows/billing_agent.yml` is configured with:

```yaml
schedule:
  - cron: "30 3 * * *"   # Daily at 3:30 AM UTC = 9:00 AM IST
```

**7.2 Manual trigger**

```
GitHub → Actions → GCP Billing Agent → Run workflow
```

Optional inputs:
- `days_back`: 30 (default) or any number
- `month`: `2025-06` for a specific month report

**7.3 Monitor runs**

```
GitHub → Actions → GCP Billing Agent - Scheduled Report
```

Reports are uploaded as GitHub artifacts (retained 90 days) AND sent to Slack.

---

### Step 8 - Validate the Slack Report

After a successful run, your `#gcp-billing-alerts` channel should receive:

```
📊 GCP Organization Billing Report
🔴 GCP Billing Report | 2025-06-14 03:30 UTC
Period: 2025-05-14 → 2025-06-14 | Total Spend: USD 12,847.33 | Projects: 8

🚨 Anomaly Detection
🔴 CRITICAL dhg-vaccine-rateauto-nonpord | Cloud SQL | 2025-06-13 | +87.3% ($234.12 vs avg $125.00)
🟡 WARNING  dhg-vaccine-rateauto-nonpord | GKE       | 2025-06-12 | +31.2% ($89.40 vs avg $68.14)

💸 Top 5 Cost Drivers
1. dhg-vaccine-rateauto-nonpord | Cloud SQL for PostgreSQL | $3,241.00
2. dhg-vaccine-rateauto-nonpord | Kubernetes Engine        | $2,887.50
3. dhg-vaccine-rateauto-dev     | Compute Engine           | $1,203.00
```

With `billing_report_20250614.xlsx` and `billing_report_20250614.csv` attached in thread.

---

## Excel Report Structure

| Sheet | Contents |
|---|---|
| **Executive Summary** | Period, total cost, project count, anomaly count, per-project table |
| **Project Detail** | Day-by-day cost per project per service |
| **Service Breakdown** | Total cost per GCP service across all projects |
| **Anomalies** | Color-coded 🔴 critical / 🟡 warning rows with % change vs 7-day avg |
| **Top Cost Drivers** | Ranked project+service+SKU combinations |

---

## Anomaly Detection Logic

The agent uses a **7-day rolling average** comparison:

```
pct_change = (today_cost - avg_7d_cost) / avg_7d_cost * 100

CRITICAL: pct_change >= 50%   (red in Excel, immediate alert)
WARNING:  pct_change >= 20%   (orange in Excel, informational)
```

Anomalies are detected per `(project, service)` pair, so a GKE spike in one project doesn't mask a Cloud SQL spike in another.

---

## Cron Schedule Reference

| Schedule | Cron | IST Time |
|---|---|---|
| Daily 9 AM IST | `30 3 * * *` | 09:00 AM |
| Daily 6 AM IST | `30 0 * * *` | 06:00 AM |
| Weekly Monday | `30 3 * * 1` | Mon 9 AM |
| Monthly 1st | `30 3 1 * *` | 1st of month 9 AM |

---

## Troubleshooting

**401 errors from Vertex AI**

Same issue as CloudSentinel - WIF OAuth tokens conflict with Gemini API key auth.

Fix: Ensure `GOOGLE_GENAI_USE_VERTEXAI=TRUE` is set BEFORE any ADK imports. This is already handled in `main.py` and `billing_agent.py`.

**No data in BigQuery**

Billing export takes 24h to start. Check:
```bash
bq ls --project_id=$GCP_PROJECT_ID billing_export
bq show --project_id=$GCP_PROJECT_ID billing_export.gcp_billing_export_v1
```

**Slack file upload fails**

Ensure the bot is in the channel:
```
/invite @GCP Billing Agent
```
And `files:write` scope is added to the Slack App.

**WIF permission denied**

New repo needs SA impersonation binding (Step 5.3 above).

---

## File Structure

```
gcp-billing-agent/
- agent/
  - billing_agent.py      # ADK Agent + async runner
  - bigquery_tools.py     # 5 BigQuery ADK tools
  - report_tools.py       # Excel + CSV generation
  - slack_tools.py        # Slack message + file upload
  - __init__.py
- sql/
  - billing_queries.sql   # Standalone SQL for manual testing
- .github/
  - workflows/
    - billing_agent.yml   # Scheduled GitHub Actions
- main.py                 # Entry point (argparse)
- requirements.txt
- .env.example
- README.md
```
