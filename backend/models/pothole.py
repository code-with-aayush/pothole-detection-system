"""
PotholeAlert — Pothole Data Model & Validation.

Defines schemas, allowed status/severity/reportStatus enumerations,
and record creation factories matching Milestone 2 PRD specifications.
"""

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# Allowed Values
# ----------------------------------------------------------------------
ALLOWED_SEVERITIES = {"low", "medium", "high"}
ALLOWED_STATUSES = {"reported", "acknowledged", "in_progress", "resolved"}
ALLOWED_REPORT_STATUSES = {
    "pending",
    "sent",
    "simulated",
    "failed",
    "queued",
    "dashboard_ticket_created",
}

SeverityType = Literal["low", "medium", "high"]
StatusType = Literal["reported", "acknowledged", "in_progress", "resolved"]
ReportStatusType = Literal[
    "pending",
    "sent",
    "simulated",
    "failed",
    "queued",
    "dashboard_ticket_created",
]


def validate_status(status: str) -> None:
    """Validate that status is in ALLOWED_STATUSES."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Allowed statuses: {sorted(ALLOWED_STATUSES)}"
        )


def validate_severity(severity: str) -> None:
    """Validate that severity is in ALLOWED_SEVERITIES."""
    if severity not in ALLOWED_SEVERITIES:
        raise ValueError(
            f"Invalid severity '{severity}'. Allowed severities: {sorted(ALLOWED_SEVERITIES)}"
        )


def validate_report_status(report_status: str) -> None:
    """Validate that reportStatus is in ALLOWED_REPORT_STATUSES."""
    if report_status not in ALLOWED_REPORT_STATUSES:
        raise ValueError(
            f"Invalid reportStatus '{report_status}'. Allowed values: {sorted(ALLOWED_REPORT_STATUSES)}"
        )


# ----------------------------------------------------------------------
# Pydantic Schemas for Validation & API responses
# ----------------------------------------------------------------------
class BBoxModel(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class AuthorityModel(BaseModel):
    name: str
    shortName: str
    email: str | None = None


class StatusHistoryEntry(BaseModel):
    status: str
    changedAt: str
    note: str = ""


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status")
    note: str = Field(default="", description="Optional note describing the status change")


class PotholeResponse(BaseModel):
    id: str = Field(..., alias="_id")
    latitude: float | None = None
    longitude: float | None = None
    address: str = ""
    imageUrl: str = ""
    detectedAt: str
    confidence: float
    severity: str
    authority: AuthorityModel
    status: str
    reportStatus: str
    reportChannel: str = "dashboard_ticket"
    reportPayload: dict[str, Any] = Field(default_factory=dict)
    reportAttempts: int = 0
    lastReportAttemptAt: str | None = None
    reportedAt: str | None = None
    lastDetectedAt: str | None = None
    detectionCount: int = 1
    isDemo: bool = False
    source: str = "mobile_camera"
    bbox: BBoxModel
    statusHistory: list[StatusHistoryEntry] = Field(default_factory=list)
    createdAt: str
    updatedAt: str

    model_config = {
        "populate_by_name": True,
    }


def create_pothole_document(
    *,
    latitude: float | None,
    longitude: float | None,
    confidence: float,
    severity: str,
    bbox: dict[str, float],
    authority: dict[str, Any],
    address: str = "",
    image_url: str = "",
    detected_at: str | None = None,
    source: str = "mobile_camera",
    status: str = "reported",
    report_status: str = "pending",
    report_channel: str = "dashboard_ticket",
    report_payload: dict[str, Any] | None = None,
    report_attempts: int = 0,
    last_report_attempt_at: str | None = None,
    reported_at: str | None = None,
    last_detected_at: str | None = None,
    detection_count: int = 1,
    is_demo: bool = False,
    initial_note: str = "Pothole detected",
    initial_notes: list[str] | None = None,
) -> dict[str, Any]:
    """
    Factory function to create a new pothole dictionary for MongoDB storage.
    Validates all enumeration fields and generates standard timestamps.
    """
    validate_severity(severity)
    validate_status(status)
    validate_report_status(report_status)

    now_iso = datetime.now(timezone.utc).isoformat()
    dt_iso = detected_at or now_iso
    last_dt_iso = last_detected_at or dt_iso

    history_notes = initial_notes if initial_notes is not None else [initial_note]
    status_history = [
        {
            "status": status,
            "changedAt": dt_iso,
            "note": note,
        }
        for note in history_notes
    ]

    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "imageUrl": image_url,
        "detectedAt": dt_iso,
        "lastDetectedAt": last_dt_iso,
        "detectionCount": max(1, int(detection_count)),
        "confidence": round(float(confidence), 4),
        "severity": severity,
        "authority": {
            "name": authority.get("name", "Unassigned Road Authority"),
            "shortName": authority.get("shortName", "UNKNOWN"),
            "email": authority.get("email", "unassigned@example.com"),
        },
        "status": status,
        "reportStatus": report_status,
        "reportChannel": report_channel,
        "reportPayload": report_payload or {},
        "reportAttempts": int(report_attempts),
        "lastReportAttemptAt": last_report_attempt_at,
        "reportedAt": reported_at,
        "isDemo": bool(is_demo),
        "source": source or "mobile_camera",
        "bbox": {
            "x1": round(float(bbox.get("x1", 0.0)), 2),
            "y1": round(float(bbox.get("y1", 0.0)), 2),
            "x2": round(float(bbox.get("x2", 0.0)), 2),
            "y2": round(float(bbox.get("y2", 0.0)), 2),
        },
        "statusHistory": status_history,
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }
