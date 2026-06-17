import os

# CRITICAL: Set Vertex AI BEFORE any ADK imports
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GCP_PROJECT_ID", "dhg-vaccine-rateauto-nonpord")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GCP_REGION", "us-central1")

from agent.billing_agent import billing_agent

# ADK Web requires root_agent to discover the agent
root_agent = billing_agent
