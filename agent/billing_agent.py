"""
GCP Organization Billing Agent using Google ADK + BigQuery
Fetches billing reports, detects anomalies, sends Slack reports with Excel/CSV attachments
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

# CRITICAL: Set Vertex AI mode BEFORE any ADK imports (same pattern as CloudSentinel)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GCP_PROJECT_ID", "")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GCP_REGION", "us-central1")

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types as genai_types

from agent.bigquery_tools import (
    fetch_org_billing_summary,
    fetch_project_billing_detail,
    fetch_service_cost_breakdown,
    detect_billing_anomalies,
    fetch_top_cost_drivers,
)
from agent.report_tools import (
    generate_excel_report,
    generate_csv_report,
)
from agent.slack_tools import send_slack_report


# ---------------------------------------------------------------------------
# ADK Agent Definition
# ---------------------------------------------------------------------------

AGENT_INSTRUCTION = """
You are a GCP Billing Intelligence Agent. Use your available tools directly.

DO NOT write Python code. DO NOT use import statements.
Call tools directly in sequence:

1. Call fetch_org_billing_summary with days_back
2. Call fetch_project_billing_detail with days_back
3. Call fetch_service_cost_breakdown with days_back
4. Call detect_billing_anomalies with threshold_pct=20 and days_back
5. Call fetch_top_cost_drivers with days_back and top_n=10
6. Call generate_excel_report with filename and JSON strings from previous results
7. Call generate_csv_report with filename and JSON strings from previous results
8. Call send_slack_report with JSON strings and file paths from steps 6 and 7

Always call tools one at a time. Never write code blocks.
"""

billing_agent = Agent(
    name="gcp_billing_agent",
    model="gemini-2.5-flash",
    instruction=AGENT_INSTRUCTION,
    tools=[
        FunctionTool(func=fetch_org_billing_summary),
        FunctionTool(func=fetch_project_billing_detail),
        FunctionTool(func=fetch_service_cost_breakdown),
        FunctionTool(func=detect_billing_anomalies),
        FunctionTool(func=fetch_top_cost_drivers),
        FunctionTool(func=generate_excel_report),
        FunctionTool(func=generate_csv_report),
        FunctionTool(func=send_slack_report),
    ],
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_billing_agent(days_back: int = 30, report_month: Optional[str] = None):
    """
    Main entry point - run the billing agent for the given period.
    days_back: number of days to look back (default 30)
    report_month: optional YYYY-MM string to target a specific month
    """
    session_service = InMemorySessionService()
    runner = Runner(
        agent=billing_agent,
        app_name="gcp_billing_agent",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="gcp_billing_agent",
        user_id="github-actions",
    )

    period_str = report_month if report_month else f"last {days_back} days"
    prompt = f"""
    Run a full GCP billing analysis for the {period_str}.

    Steps:
    1. Fetch organization billing summary (days_back={days_back})
    2. Fetch per-project billing detail (days_back={days_back})
    3. Fetch service-level cost breakdown (days_back={days_back})
    4. Detect billing anomalies (threshold_pct=20, days_back={days_back})
    5. Fetch top 10 cost drivers (days_back={days_back})
    6. Generate Excel report with all data (filename="billing_report_{datetime.now().strftime('%Y%m%d')}.xlsx")
    7. Generate CSV report (filename="billing_report_{datetime.now().strftime('%Y%m%d')}.csv")
    8. Send Slack report with summary, anomalies, and attach both files

    Be thorough and include all findings in the Slack message.
    """

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    print(f"[{datetime.now().isoformat()}] Starting GCP Billing Agent run...")
    async for event in runner.run_async(
        user_id="github-actions",
        session_id=session.id,
        new_message=content,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(f"Agent: {part.text}")

    print(f"[{datetime.now().isoformat()}] Billing Agent run complete.")


if __name__ == "__main__":
    asyncio.run(run_billing_agent())
