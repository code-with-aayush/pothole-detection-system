"""
PotholeAlert — Reporting & Dispatch Service.

Handles dispatch of pothole repair reports to responsible road authorities.
Supports:
1. Demo mode (default): Simulates report dispatch when SMTP credentials are absent.
2. SMTP mode: Sends an official formatted email notification when SMTP variables are configured.
"""

from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
from typing import Any

logger = logging.getLogger("potholealert.reporting")


def get_smtp_config() -> dict[str, Any] | None:
    """
    Retrieve SMTP configuration from environment variables.
    Returns None if essential SMTP variables are missing, triggering demo mode.
    """
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("REPORT_FROM_EMAIL", "").strip()
    port_str = os.getenv("SMTP_PORT", "587").strip()

    if not host or not user:
        return None

    try:
        port = int(port_str)
    except ValueError:
        port = 587

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email or user,
    }


def build_report_payload(pothole: dict[str, Any]) -> dict[str, Any]:
    """Assemble standardized incident report payload from pothole record."""
    authority = pothole.get("authority") or {}
    return {
        "potholeId": str(pothole.get("_id", "")),
        "authorityName": authority.get("name", "Unassigned Road Authority"),
        "authorityEmail": authority.get("email", "demo-authority@example.com"),
        "latitude": pothole.get("latitude"),
        "longitude": pothole.get("longitude"),
        "address": pothole.get("address") or "Address unavailable",
        "severity": pothole.get("severity", "medium"),
        "confidence": pothole.get("confidence", 0.0),
        "detectionTimestamp": pothole.get("detectedAt", ""),
        "evidenceImageUrl": pothole.get("imageUrl", ""),
        "currentStatus": pothole.get("status", "reported"),
        "reportChannel": pothole.get("reportChannel", "dashboard_ticket"),
        "reportedAt": datetime.now(timezone.utc).isoformat(),
    }


def format_report_email(payload: dict[str, Any]) -> tuple[str, str]:
    """Generate plaintext and HTML email content for the authority report."""
    subject = f"[PotholeAlert] Incident Notice #{payload['potholeId']} — {payload['severity'].upper()} Priority"

    body_text = f"""
POTHOLEALERT INCIDENT DISPATCH NOTICE
-------------------------------------
Authority      : {payload['authorityName']} ({payload['authorityEmail']})
Incident ID    : {payload['potholeId']}
Severity       : {payload['severity'].upper()}
Confidence     : {payload['confidence'] * 100:.1f}%
Detected At    : {payload['detectionTimestamp']}

Location:
  Latitude     : {payload['latitude']}
  Longitude    : {payload['longitude']}
  Address      : {payload['address']}

Status         : {payload['currentStatus'].upper()}
Channel        : {payload.get('reportChannel', 'dashboard_ticket').upper()}
Evidence Image : {payload['evidenceImageUrl']}

Please inspect and dispatch a maintenance team.
Generated automatically by PotholeAlert System.
"""

    return subject, body_text


def dispatch_report(pothole: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch or simulate report to the assigned authority.
    Returns result dictionary with reportStatus, payload, and status message.
    """
    payload = build_report_payload(pothole)
    smtp_config = get_smtp_config()

    # ------------------------------------------------------------------
    # 1. Demo Mode (SMTP not configured)
    # ------------------------------------------------------------------
    if not smtp_config:
        logger.info(
            "Demo Mode: SMTP credentials not set. Simulating report dispatch to %s <%s>",
            payload["authorityName"],
            payload["authorityEmail"],
        )
        return {
            "success": True,
            "simulated": True,
            "reportStatus": "simulated",
            "message": "Dashboard ticket created; email simulation mode active (Demo report generated)",
            "report": payload,
        }

    # ------------------------------------------------------------------
    # 2. SMTP Mode (SMTP credentials available)
    # ------------------------------------------------------------------
    subject, body_text = format_report_email(payload)
    recipient = payload["authorityEmail"]

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_config["from_email"]
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))

        with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=10) as server:
            server.starttls()
            if smtp_config["password"]:
                server.login(smtp_config["user"], smtp_config["password"])
            server.send_message(msg)

        logger.info("Email report successfully dispatched to %s via SMTP", recipient)
        return {
            "success": True,
            "simulated": False,
            "reportStatus": "sent",
            "message": "Email sent successfully",
            "report": payload,
        }

    except Exception as exc:
        logger.error("Failed to send SMTP report to %s: %s", recipient, exc)
        return {
            "success": False,
            "simulated": False,
            "reportStatus": "failed",
            "error": str(exc),
            "message": f"Email delivery failed: {exc}",
            "report": payload,
        }
