"""
GCP Organization Billing Agent using Google ADK + BigQuery
Hybrid approach:
  - LLM (ADK) handles BigQuery data fetching (steps 1-5)
  - Python directly handles Excel, CSV, Slack (steps 6-8)
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional

# CRITICAL: Set Vertex AI mode BEFORE any ADK imports
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
# ADK Agent - Only responsible for BigQuery data fetching (steps 1-5)
# ---------------------------------------------------------------------------

AGENT_INSTRUCTION = """
You are a GCP Billing Data Fetcher.
Call these 5 tools in order. Do not skip any.

1. fetch_org_billing_summary
2. fetch_project_billing_detail
3. fetch_service_cost_breakdown
4. detect_billing_anomalies
5. fetch_top_cost_drivers

After all 5 tools complete, stop. Do not call any other tools.
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
    ],
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_billing_agent(days_back: int = 30, report_month: Optional[str] = None):
    """
    Hybrid approach:
    - ADK Agent fetches BigQuery data (steps 1-5)
    - Python directly calls report + Slack tools (steps 6-8)
    Works for both local ADK Web and GitHub Actions.
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

    today      = datetime.now().strftime('%Y%m%d')
    period_str = report_month if report_month else f"last {days_back} days"

    prompt = f"""
    Fetch GCP billing data for {period_str}.
    Call all 5 tools in order with days_back={days_back}.
    For detect_billing_anomalies use threshold_pct=20.
    For fetch_top_cost_drivers use top_n=10.
    """

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    print(f"[{datetime.now().isoformat()}] Starting GCP Billing Agent run...")
    print(f"[{datetime.now().isoformat()}] Step 1-5: Fetching BigQuery data via ADK...")

    # ── Steps 1-5: ADK fetches BigQuery data ──────────────────────────────
    tool_results = {}

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
                    tool_results[fr.name] = fr.response
                    print(f"[FUNCTION RESPONSE] {fr.name} → {str(fr.response)[:150]}...")

    print(f"[{datetime.now().isoformat()}] ADK data fetching complete.")
    print(f"[{datetime.now().isoformat()}] Tools collected: {list(tool_results.keys())}")

    # ── Fallback: call BigQuery tools directly if ADK didn't capture results
    required = [
        "fetch_org_billing_summary",
        "fetch_project_billing_detail",
        "fetch_service_cost_breakdown",
        "detect_billing_anomalies",
        "fetch_top_cost_drivers",
    ]
    missing = [t for t in required if t not in tool_results]
    if missing:
        print(f"[INFO] Missing results for: {missing} - calling directly...")
        if "fetch_org_billing_summary" not in tool_results:
            tool_results["fetch_org_billing_summary"] = fetch_org_billing_summary(days_back=days_back)
        if "fetch_project_billing_detail" not in tool_results:
            tool_results["fetch_project_billing_detail"] = fetch_project_billing_detail(days_back=days_back)
        if "fetch_service_cost_breakdown" not in tool_results:
            tool_results["fetch_service_cost_breakdown"] = fetch_service_cost_breakdown(days_back=days_back)
        if "detect_billing_anomalies" not in tool_results:
            tool_results["detect_billing_anomalies"] = detect_billing_anomalies(threshold_pct=20, days_back=days_back)
        if "fetch_top_cost_drivers" not in tool_results:
            tool_results["fetch_top_cost_drivers"] = fetch_top_cost_drivers(days_back=days_back, top_n=10)
        print(f"[INFO] Direct BigQuery calls complete.")

    # ── Helper: convert result to JSON string ──────────────────────────────
    def to_json(key: str) -> str:
        val = tool_results.get(key, {})
        if isinstance(val, str):
            return val
        try:
            return json.dumps(val)
        except Exception:
            return "{}"

    # ── Step 6: Generate Excel report (Python direct call) ─────────────────
    excel_filename = f"billing_report_{today}.xlsx"
    print(f"[{datetime.now().isoformat()}] Step 6: Generating Excel report: {excel_filename}")
    excel_result = generate_excel_report(
        filename=excel_filename,
        org_summary=to_json("fetch_org_billing_summary"),
        project_detail=to_json("fetch_project_billing_detail"),
        service_breakdown=to_json("fetch_service_cost_breakdown"),
        anomalies=to_json("detect_billing_anomalies"),
        top_drivers=to_json("fetch_top_cost_drivers"),
    )
    print(f"[EXCEL] {excel_result.get('filepath')} ({excel_result.get('size_bytes', 0)} bytes)")

    # ── Step 7: Generate CSV report (Python direct call) ───────────────────
    csv_filename = f"billing_report_{today}.csv"
    print(f"[{datetime.now().isoformat()}] Step 7: Generating CSV report: {csv_filename}")
    csv_result = generate_csv_report(
        filename=csv_filename,
        org_summary=to_json("fetch_org_billing_summary"),
        anomalies=to_json("detect_billing_anomalies"),
        top_drivers=to_json("fetch_top_cost_drivers"),
    )
    print(f"[CSV] {csv_result.get('filepath')} ({csv_result.get('size_bytes', 0)} bytes)")

    # ── Step 8: Send Slack report (Python direct call) ─────────────────────
    print(f"[{datetime.now().isoformat()}] Step 8: Sending Slack report...")
    slack_result = send_slack_report(
        org_summary=to_json("fetch_org_billing_summary"),
        anomaly_summary=to_json("detect_billing_anomalies"),
        top_drivers=to_json("fetch_top_cost_drivers"),
        excel_filepath=excel_result.get("filepath", ""),
        csv_filepath=csv_result.get("filepath", ""),
    )
    print(f"[SLACK] {slack_result}")
    print(f"[{datetime.now().isoformat()}] Billing Agent run complete.")


if __name__ == "__main__":
    asyncio.run(run_billing_agent())
