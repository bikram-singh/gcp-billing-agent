"""
GCP Organization Billing Agent using Google ADK + BigQuery
Fetches billing reports, detects anomalies, sends Slack reports with Excel/CSV attachments
"""

import os
import asyncio
from datetime import datetime
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
You are a GCP Billing Intelligence Agent.
You have 8 tools. Call them ALL in this exact order. Never stop early.

1. fetch_org_billing_summary
2. fetch_project_billing_detail
3. fetch_service_cost_breakdown
4. detect_billing_anomalies
5. fetch_top_cost_drivers
6. generate_excel_report
7. generate_csv_report
8. send_slack_report

Rules:
- Call all 8 tools. Do not skip any.
- Pass results from earlier tools as JSON strings to later tools.
- Never write code. Never stop before tool 8 is called.
"""

billing_agent = Agent(
    name="gcp_billing_agent",
    model="gemini-2.5-flash-lite",
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

    today = datetime.now().strftime('%Y%m%d')
    period_str = report_month if report_month else f"last {days_back} days"

    prompt = f"""
    Run GCP billing analysis for {period_str} using days_back={days_back}.

    Call all 8 tools in order:
    1. fetch_org_billing_summary(days_back={days_back})
    2. fetch_project_billing_detail(days_back={days_back})
    3. fetch_service_cost_breakdown(days_back={days_back})
    4. detect_billing_anomalies(days_back={days_back}, threshold_pct=20)
    5. fetch_top_cost_drivers(days_back={days_back}, top_n=10)
    6. generate_excel_report(filename="billing_report_{today}.xlsx", pass all results as JSON strings)
    7. generate_csv_report(filename="billing_report_{today}.csv", pass results as JSON strings)
    8. send_slack_report(pass all JSON strings and filepaths from steps 6 and 7)
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
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    print(f"[FUNCTION CALL] {fc.name} → {str(fc.args)[:150]}")
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    print(f"[FUNCTION RESPONSE] {fr.name} → {str(fr.response)[:150]}...")

    print(f"[{datetime.now().isoformat()}] Billing Agent run complete.")


if __name__ == "__main__":
    asyncio.run(run_billing_agent())
