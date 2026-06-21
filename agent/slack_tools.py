"""
Slack reporting tool - sends billing summary + uploads Excel/CSV files
"""

import os
import json
from datetime import datetime
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL   = os.environ.get("SLACK_CHANNEL", "#gcp-billing-alerts")
REPORTS_DIR     = Path(os.environ.get("REPORTS_DIR", "/tmp/billing_reports"))

# ── Currency symbol mapper ─────────────────────────────────────────────────
CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "SGD": "S$",
}


def _currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency)


def _parse(s):
    if not s:
        return None
    try:
        return json.loads(s) if isinstance(s, str) else s
    except Exception:
        return None


def _emoji_severity(critical, warning):
    if critical > 0:
        return "🔴"
    if warning > 0:
        return "🟡"
    return "🟢"


def send_slack_report(
    org_summary: str = "",
    anomaly_summary: str = "",
    top_drivers: str = "",
    excel_filepath: str = "",
    csv_filepath: str = "",
) -> dict:
    """
    Send a structured Slack billing report with Excel and CSV file attachments.

    Args:
        org_summary:     JSON string from fetch_org_billing_summary
        anomaly_summary: JSON string from detect_billing_anomalies
        top_drivers:     JSON string from fetch_top_cost_drivers
        excel_filepath:  Path to Excel report file
        csv_filepath:    Path to CSV report file

    Returns:
        dict with success, message_ts, files_uploaded
    """
    org     = _parse(org_summary)
    anom    = _parse(anomaly_summary)
    drivers = _parse(top_drivers)

    client  = WebClient(token=SLACK_BOT_TOKEN)
    run_ts  = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    # ── Currency symbol from billing data ──────────────────────────────────
    raw_currency = org.get("currency", "INR") if org else "INR"
    currency     = _currency_symbol(raw_currency)

    critical  = anom.get("critical_count", 0) if anom else 0
    warning   = anom.get("warning_count",  0) if anom else 0
    sev_emoji = _emoji_severity(critical, warning)

    total_cost = f"{currency}{org.get('total_cost', 0):,.2f}" if org else "N/A"
    period     = (
        f"{org.get('period', {}).get('start')} → {org.get('period', {}).get('end')}"
        if org else "N/A"
    )
    proj_count = org.get("project_count", 0) if org else 0

    header_text = (
        f"{sev_emoji} *GCP Billing Report* | {run_ts}\n"
        f"*Period:* {period} | *Total Spend:* `{total_cost}` | *Projects:* {proj_count}"
    )

    # ── Anomaly lines ──────────────────────────────────────────────────────
    anomaly_lines = []
    if anom and anom.get("anomalies"):
        for a in anom["anomalies"][:5]:
            sev        = "🔴 CRITICAL" if a.get("pct_change", 0) >= 50 else "🟡 WARNING"
            a_currency = _currency_symbol(a.get("currency", raw_currency))
            line = (
                f"{sev} `{a.get('project_id')}` | {a.get('service')} | "
                f"{a.get('usage_date')} | +{a.get('pct_change')}% "
                f"({a_currency}{a.get('daily_cost', 0):,.2f} vs avg {a_currency}{a.get('avg_7d_cost', 0):,.2f})"
            )
            anomaly_lines.append(line)
        if len(anom["anomalies"]) > 5:
            anomaly_lines.append(f"_...and {len(anom['anomalies'])-5} more (see attached report)_")
    else:
        anomaly_lines.append("✅ No anomalies detected")

    # ── Top drivers lines ──────────────────────────────────────────────────
    driver_lines = []
    if drivers and drivers.get("drivers"):
        for i, d in enumerate(drivers["drivers"][:5], 1):
            d_currency = _currency_symbol(d.get("currency", raw_currency))
            driver_lines.append(
                f"{i}. `{d.get('project_name')}` | {d.get('service')} | "
                f"*{d_currency}{d.get('total_cost', 0):,.2f}*"
            )

    # ── Slack blocks ───────────────────────────────────────────────────────
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📊 GCP Organization Billing Report", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header_text},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🚨 Anomaly Detection*\n" + "\n".join(anomaly_lines)},
        },
    ]

    if driver_lines:
        blocks += [
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*💸 Top 5 Cost Drivers*\n" + "\n".join(driver_lines)},
            },
        ]

    if critical > 0:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":rotating_light: *Action Required:* {critical} critical anomalies need immediate review.",
            },
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by GCP Billing Agent | {run_ts} | Reports attached below"},
            ],
        },
    ]

    # ── Post Slack message ─────────────────────────────────────────────────
    try:
        msg_resp = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            blocks=blocks,
            text=(
                f"GCP Billing Report {run_ts} | "
                f"Spend: {total_cost} | "
                f"Anomalies: {critical} critical, {warning} warning"
            ),
        )
        message_ts = msg_resp["ts"]
    except SlackApiError as e:
        return {"success": False, "error": str(e), "files_uploaded": []}

    # ── Upload Excel and CSV as thread attachments ─────────────────────────
    files_uploaded = []
    for fpath_str, ftype in [(excel_filepath, "xlsx"), (csv_filepath, "csv")]:
        if not fpath_str:
            continue
        fpath = Path(fpath_str)
        if not fpath.exists():
            fpath = REPORTS_DIR / fpath.name
        if not fpath.exists():
            continue
        try:
            up_resp = client.files_upload_v2(
                channel=SLACK_CHANNEL,
                file=str(fpath),
                filename=fpath.name,
                title=f"GCP Billing Report ({ftype.upper()}) - {run_ts}",
                thread_ts=message_ts,
            )
            files_uploaded.append({"filename": fpath.name, "type": ftype, "ok": up_resp["ok"]})
        except SlackApiError as e:
            files_uploaded.append({"filename": str(fpath), "type": ftype, "error": str(e)})

    return {
        "success":        True,
        "message_ts":     message_ts,
        "channel":        SLACK_CHANNEL,
        "files_uploaded": files_uploaded,
        "anomaly_count":  critical + warning,
    }
