"""
Entry point for GCP Billing Agent
Run: python main.py [--days-back 30] [--month 2025-06]
"""

import asyncio
import argparse
import sys
import os

# CRITICAL: Set Vertex AI BEFORE all imports (same as CloudSentinel pattern)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"


def parse_args():
    parser = argparse.ArgumentParser(description="GCP Organization Billing Agent")
    parser.add_argument(
        "--days-back", type=int, default=30,
        help="Number of days to look back (default: 30)"
    )
    parser.add_argument(
        "--month", type=str, default=None,
        help="Target month in YYYY-MM format (e.g. 2025-06)"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    # Validate required env vars
    required = ["GCP_PROJECT_ID", "SLACK_BOT_TOKEN", "BQ_BILLING_DATASET", "BQ_BILLING_TABLE"]
    missing  = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    from agent.billing_agent import run_billing_agent
    await run_billing_agent(days_back=args.days_back, report_month=args.month)


if __name__ == "__main__":
    asyncio.run(main())
