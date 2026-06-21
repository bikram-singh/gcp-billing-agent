"""
GCP Organization Billing Agent using Google ADK + BigQuery
Fetches billing reports, detects anomalies, sends Slack reports with Excel/CSV attachments
"""

import os
import json
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
You are a GCP Billing Intelligence Agent. You MUST call ALL 8 tools in strict order.
Do NOT stop after fetching data. Do NOT summarize early. Do NOT skip any step.

MANDATORY SEQUENCE - complete ALL 8 steps without stopping:

STEP 1: Call fetch_org_billing_summary with days_back
STEP 2: Call fetch_project_billing_detail with days_back
STEP 3: Call fetch_service_cost_breakdown with days_back
STEP 4: Call detect_billing_anomalies with threshold_pct=20 and days_back
STEP 5: Call fetch_top_cost_drivers with days_back and top_n=10
STEP 6: Call generate_excel_report with filename and all previous results as JSON strings
STEP 7: Call generate_csv_report with filename and results as JSON strings
STEP 8: Call send_slack_report with all JSON strings and filepaths from steps 6 and 7

RULES:
- You MUST call generate_excel_report after step 5. This is mandatory.
- You MUST call generate_csv_report after step 6. This is mandatory.
- You MUST call send_slack_report after step 7. This is mandatory.
- Do NOT write Python code or import statements.
- Call tools one at a time only.
- After ALL 8 steps are complete, provide a brief summary.
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

    today = datetime.now().strftime('%Y%m%d')
    period_str = report_month if report_month else f"last {days_back} days"

    prompt = f"""
    Run a full GCP billing analysis for the {period_str}.

    You MUST complete ALL 8 steps below in order. Do not stop early.

    STEP 1: Call fetch_org_billing_summary with days_back={days_back}
    STEP 2: Call fetch_project_billing_detail with days_back={days_back}
    STEP 3: Call fetch_service_cost_breakdown with days_back={days_back}
    STEP 4: Call detect_billing_anomalies with threshold_pct=20, days_back={days_back}
    STEP 5: Call fetch_top_cost_drivers with days_back={days_back}, top_n=10
    STEP 6: Call generate_excel_report with:
            - filename="billing_report_{today}.xlsx"
            - org_summary=<JSON string from step 1>
            - project_detail=<JSON string from step 2>
            - service_breakdown=<JSON string from step 3>
            - anomalies=<JSON string from step 4>
            - top_drivers=<JSON string from step 5>
    STEP 7: Call generate_csv_report with:
            - filename="billing_report_{today}.csv"
            - org_summary=<JSON string from step 1>
            - anomalies=<JSON string from step 4>
            - top_drivers=<JSON string from step 5>
    STEP 8: Call send_slack_report with:
            - org_summary=<JSON string from step 1>
            - anomaly_summary=<JSON string from step 4>
            - top_drivers=<JSON string from step 5>
            - excel_filepath=<filepath from step 6>
            - csv_filepath=<filepath from step 7>

    All 8 steps are MANDATORY. Complete every step before finishing.
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
        # Log agent text responses
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(f"Agent: {part.text}")

        # Log tool calls
        if hasattr(event, "tool_calls") and event.tool_calls:
            for tc in event.tool_calls:
                print(f"[TOOL CALL] {tc.name} → args: {tc.args}")

        # Log tool results
        if hasattr(event, "tool_results") and event.tool_results:
            for tr in event.tool_results:
                result_str = str(tr.result)[:200]
                print(f"[TOOL RESULT] {tr.name} → {result_str}...")

        # Log function calls from content parts
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    print(f"[FUNCTION CALL] {fc.name} → {str(fc.args)[:200]}")
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    print(f"[FUNCTION RESPONSE] {fr.name} → {str(fr.response)[:200]}...")

    print(f"[{datetime.now().isoformat()}] Billing Agent run complete.")


if __name__ == "__main__":
    asyncio.run(run_billing_agent())
