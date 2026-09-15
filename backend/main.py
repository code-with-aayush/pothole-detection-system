"""
PotholeAlert — FastAPI backend (Milestone 3).

Endpoints:
  GET   /health                   → liveness check
  POST  /api/detect               → pothole detection, image evidence storage, reverse geocoding, authority mapping, DB persistence
  GET   /api/potholes             → list potholes (with filters & limit)
  GET   /api/potholes/{id}        → get single pothole details
  PATCH /api/potholes/{id}/status → update pothole status with history log
  POST  /api/potholes/{id}/report → generate and dispatch/simulate authority repair report
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import io
import logging
import os
from pathlib import Path
from typing import Any
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from db import ensure_indexes, is_mongodb_available
from models.pothole import (
    ALLOWED_STATUSES,
    StatusUpdateRequest,
    create_pothole_document,
    validate_status,
)
from repositories.pothole_repository import PotholeRepository
from services.authority import get_authority_for_location
from services.detection import detect_potholes
from services.geocoding import reverse_geocode
from services.reporting import dispatch_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("potholealert")

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database indexes on startup if MongoDB is reachable."""
    try:
        ensure_indexes()
        logger.info("MongoDB indexes ensured on startup.")
    except Exception as exc:
        logger.warning("Database startup check skipped or deferred: %s", exc)
    yield


app = FastAPI(
    title="PotholeAlert API",
    version="0.3.0",
    description="Pothole detection, dispatch, and reporting backend — internship prototype",
    lifespan=lifespan,
)

# Configure CORS with configurable origins
cors_env = os.getenv("CORS_ORIGINS", "").strip()
if cors_env:
    allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Expose uploaded evidence images via static route
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

_repo = PotholeRepository()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/authority")
async def get_authority(
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    roadName: str | None = Query(None),
    roadType: str | None = Query(None),
):
    """Query the responsible road authority for a given GPS coordinate or road classification."""
    authority = get_authority_for_location(
        latitude=latitude,
        longitude=longitude,
        road_name=roadName,
        road_type=roadType,
    )
    address = reverse_geocode(latitude, longitude) if latitude is not None and longitude is not None else ""
    return {
        "authority": authority,
        "address": address,
        "coordinates": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
    }


@app.post("/api/infer")
async def infer(
    file: UploadFile = File(...),
):
    """
    Lightweight inference-only endpoint for real-time camera detection.

    Runs YOLO model on the uploaded image and returns detections with
    bounding boxes, confidence scores, and severity estimates.

    Does NOT write to the database, resolve authority, reverse-geocode,
    create reports, or send email. GPS is not accepted here — use
    GET /api/authority separately when a detection is confirmed.
    """
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected an image file, got {file.content_type}",
        )

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit",
        )

    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decode image: {exc}",
        )

    try:
        detections = detect_potholes(image)
    except FileNotFoundError as exc:
        logger.error("Model not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Model inference failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model inference failed. Check server logs.",
        )

    return {
        "detected": len(detections) > 0,
        "detections": detections,
        "count": len(detections),
        "imageWidth": image.width,
        "imageHeight": image.height,
    }


@app.post("/api/detections/ingest")
async def ingest_detection(
    file: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    source: str = Form("mobile_camera"),
    timestamp: str | None = Form(None),
    roadName: str | None = Form(None),
    roadType: str | None = Form(None),
):
    """
    Automatic ingestion endpoint for confirmed camera detections:
    1. Validates the image.
    2. Runs YOLO model independently on the backend (never trusting client bounding boxes).
    3. If no pothole detected: returns detected=False without DB write or report dispatch.
    4. If detected: resolves address & authority, checks nearby unresolved duplicate within ~50m.
       - If duplicate: updates existing incident (increments detectionCount, updates lastDetectedAt,
         appends audit event 'Duplicate detection merged') without re-dispatching email.
       - If new: creates MongoDB incident record, creates dashboard ticket,
         automatically attempts report dispatch (or simulates if SMTP unconfigured),
         records audit trail, and returns complete structured result.
    """
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected an image file, got {file.content_type}",
        )

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit",
        )

    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decode image: {exc}",
        )

    # 1. Run inference independently on backend
    try:
        detections = detect_potholes(image)
    except FileNotFoundError as exc:
        logger.error("Model not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Model inference failed during ingestion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model inference failed. Check server logs.",
        )

    ts = timestamp or datetime.now(timezone.utc).isoformat()

    # 2. Handle No-Detection Case
    if not detections:
        return {
            "detected": False,
            "message": "No pothole detected in the submitted frame.",
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "timestamp": ts,
        }

    # 3. Model Results & Geographic Resolution
    best = max(detections, key=lambda d: d["confidence"])
    authority = get_authority_for_location(
        latitude,
        longitude,
        road_name=roadName,
        road_type=roadType,
    )
    address = reverse_geocode(latitude, longitude)

    # 4. Check for Existing Nearby Unresolved Incident (within ~50m)
    try:
        duplicate = _repo.find_nearby_unresolved(
            latitude=latitude,
            longitude=longitude,
            max_distance=50.0,
        )
    except Exception as exc:
        logger.warning("Duplicate check failed in ingest: %s", exc)
        duplicate = None

    if duplicate:
        logger.info(
            "Ingestion merged duplicate into existing incident %s (nearby unresolved within 50m)",
            duplicate["_id"],
        )
        updated_duplicate = _repo.record_duplicate_detection(
            pothole_id=duplicate["_id"],
            detected_at=ts,
            note="Duplicate detection merged",
        )
        dup_authority = duplicate.get("authority") or authority
        return {
            "detected": True,
            "potholeId": duplicate["_id"],
            "isDuplicate": True,
            "authority": {
                "name": dup_authority.get("name", authority["name"]),
                "shortName": dup_authority.get("shortName", authority["shortName"]),
                "email": dup_authority.get("email", authority["email"]),
            },
            "severity": duplicate.get("severity", best["severity"]),
            "confidence": duplicate.get("confidence", best["confidence"]),
            "status": duplicate.get("status", "reported"),
            "reportStatus": duplicate.get("reportStatus", "dashboard_ticket_created"),
            "reportChannel": duplicate.get("reportChannel", "dashboard_ticket"),
            "coordinates": {
                "latitude": duplicate.get("latitude", latitude),
                "longitude": duplicate.get("longitude", longitude),
            },
            "imageUrl": duplicate.get("imageUrl") or "",
            "address": duplicate.get("address") or address,
            "detectionCount": updated_duplicate.get("detectionCount", 2) if updated_duplicate else duplicate.get("detectionCount", 1) + 1,
            "lastDetectedAt": ts,
            "message": "Duplicate detection merged into existing unresolved incident.",
        }

    # 5. Save Evidence Image for New Incident
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"
    unique_filename = f"pothole_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}{ext}"
    evidence_file_path = UPLOADS_DIR / unique_filename
    evidence_file_path.write_bytes(raw)
    image_url = f"/uploads/{unique_filename}"

    # 6. Assemble Document with Structured Audit Events
    audit_notes = [
        "Pothole detected",
        "Incident saved",
        "Dashboard ticket created",
    ]
    doc = create_pothole_document(
        latitude=latitude,
        longitude=longitude,
        confidence=best["confidence"],
        severity=best["severity"],
        bbox=best["bbox"],
        authority=authority,
        address=address,
        image_url=image_url,
        detected_at=ts,
        source=source or "mobile_camera",
        status="reported",
        report_status="dashboard_ticket_created",
        report_channel="dashboard_ticket",
        initial_notes=audit_notes,
    )

    try:
        created = _repo.create(doc)
        pothole_id = created["_id"]
    except Exception as exc:
        logger.error("Failed to persist pothole to MongoDB in ingest: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database insertion failed: {exc}",
        )

    # 7. Automatically Attempt Report Delivery (SMTP or Simulation)
    dispatch_res = dispatch_report(created)
    delivery_status = dispatch_res["reportStatus"]  # "sent", "simulated", or "failed"

    if delivery_status == "sent":
        delivery_note = "Email sent successfully"
        reported_at = datetime.now(timezone.utc).isoformat()
    elif delivery_status == "simulated":
        delivery_note = "Demo report generated"
        reported_at = None
    else:
        delivery_note = f"Report delivery failed: {dispatch_res.get('error', 'SMTP failure')}"
        reported_at = None

    try:
        updated = _repo.update_report_status(
            pothole_id=pothole_id,
            report_status=delivery_status,
            report_data=dispatch_res.get("report"),
            report_payload=dispatch_res.get("report"),
            report_attempts=1,
            last_report_attempt_at=datetime.now(timezone.utc).isoformat(),
            reported_at=reported_at,
            note=delivery_note,
        )
    except Exception as exc:
        logger.warning("Could not update report status in database: %s", exc)
        updated = created

    return {
        "detected": True,
        "potholeId": pothole_id,
        "isDuplicate": False,
        "authority": {
            "name": authority["name"],
            "shortName": authority["shortName"],
            "email": authority["email"],
        },
        "severity": best["severity"],
        "confidence": best["confidence"],
        "status": "reported",
        "reportStatus": delivery_status,
        "reportChannel": "dashboard_ticket",
        "coordinates": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "imageUrl": image_url,
        "address": address,
        "detectionCount": 1,
        "lastDetectedAt": ts,
        "message": dispatch_res["message"],
    }


@app.post("/api/detect")
async def detect(
    file: UploadFile = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    roadName: str | None = Form(None),
    roadType: str | None = Form(None),
    timestamp: str | None = Form(None),
    source: str | None = Form(None),
):
    # ------------------------------------------------------------------
    # 1. Validate uploaded file
    # ------------------------------------------------------------------
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected an image file, got {file.content_type}",
        )

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit",
        )

    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decode image: {exc}",
        )

    # ------------------------------------------------------------------
    # 2. Save evidence image under uploads/ with unique safe filename
    # ------------------------------------------------------------------
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"
    unique_filename = f"pothole_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}{ext}"
    evidence_file_path = UPLOADS_DIR / unique_filename
    evidence_file_path.write_bytes(raw)
    image_url = f"/uploads/{unique_filename}"

    # ------------------------------------------------------------------
    # 3. Run inference
    # ------------------------------------------------------------------
    try:
        detections = detect_potholes(image)
    except FileNotFoundError as exc:
        logger.error("Model not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Model inference failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model inference failed. Check server logs.",
        )

    # ------------------------------------------------------------------
    # 4. Handle No-Detection Case
    # ------------------------------------------------------------------
    ts = timestamp or datetime.now(timezone.utc).isoformat()

    if not detections:
        return {
            "detected": False,
            "message": "No pothole detected in the image",
            "imageUrl": image_url,
            "timestamp": ts,
        }

    # ------------------------------------------------------------------
    # 5. Process Best Detection & Authority Assignment
    # ------------------------------------------------------------------
    best = max(detections, key=lambda d: d["confidence"])
    authority = get_authority_for_location(
        latitude,
        longitude,
        road_name=roadName,
        road_type=roadType,
    )

    # Reverse geocode street address if coordinates are provided
    address = reverse_geocode(latitude, longitude) if latitude is not None and longitude is not None else ""

    # ------------------------------------------------------------------
    # 6. Handle Missing GPS: Return detection without persisting to DB
    # ------------------------------------------------------------------
    if latitude is None or longitude is None:
        return {
            "detected": True,
            "confidence": best["confidence"],
            "severity": best["severity"],
            "bbox": best["bbox"],
            "authority": {
                "name": authority["name"],
                "shortName": authority["shortName"],
            },
            "imageUrl": image_url,
            "address": "",
            "status": "detected",
            "reportStatus": "unreported",
            "message": "Detection successful. GPS coordinates required to create and persist official road maintenance report.",
            "allDetections": detections,
            "detectionCount": len(detections),
            "timestamp": ts,
            "coordinates": None,
        }

    # ------------------------------------------------------------------
    # 7. Check Database Reachability before saving
    # ------------------------------------------------------------------
    if not is_mongodb_available():
        logger.error("MongoDB is unavailable. Cannot persist pothole with GPS.")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "database_unavailable",
                "detail": "MongoDB is unreachable. Pothole report could not be persisted.",
                "detected": True,
                "confidence": best["confidence"],
                "severity": best["severity"],
                "bbox": best["bbox"],
                "authority": {
                    "name": authority["name"],
                    "shortName": authority["shortName"],
                },
                "imageUrl": image_url,
                "address": address,
                "status": "unpersisted",
                "reportStatus": "failed",
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "timestamp": ts,
            },
        )

    # ------------------------------------------------------------------
    # 8. Duplicate Check (within 50m and 10s)
    # ------------------------------------------------------------------
    try:
        duplicate = _repo.find_duplicate(
            latitude=latitude,
            longitude=longitude,
            detected_at=ts,
        )
    except Exception as exc:
        logger.warning("Duplicate check failed: %s", exc)
        duplicate = None

    if duplicate:
        logger.info("Found duplicate pothole %s within 50m and 10s", duplicate["_id"])
        return {
            "detected": True,
            "potholeId": duplicate["_id"],
            "confidence": duplicate.get("confidence", best["confidence"]),
            "severity": duplicate.get("severity", best["severity"]),
            "bbox": duplicate.get("bbox", best["bbox"]),
            "authority": {
                "name": duplicate.get("authority", {}).get("name", authority["name"]),
                "shortName": duplicate.get("authority", {}).get("shortName", authority["shortName"]),
            },
            "imageUrl": duplicate.get("imageUrl") or image_url,
            "address": duplicate.get("address") or address,
            "status": duplicate.get("status", "reported"),
            "reportStatus": duplicate.get("reportStatus", "pending"),
            "isDuplicate": True,
            "allDetections": detections,
            "detectionCount": len(detections),
            "timestamp": ts,
            "coordinates": {"latitude": latitude, "longitude": longitude},
        }

    # ------------------------------------------------------------------
    # 9. Create & Persist Database Record
    # ------------------------------------------------------------------
    doc = create_pothole_document(
        latitude=latitude,
        longitude=longitude,
        confidence=best["confidence"],
        severity=best["severity"],
        bbox=best["bbox"],
        authority=authority,
        address=address,
        image_url=image_url,
        detected_at=ts,
        source=source or "upload",
        status="reported",
        report_status="dashboard_ticket_created",
        report_channel="dashboard_ticket",
        initial_notes=[
            "Pothole detected",
            "Incident saved",
            "Dashboard ticket created",
        ],
    )

    try:
        created = _repo.create(doc)
        pothole_id = created["_id"]
    except Exception as exc:
        logger.error("Failed to persist pothole to MongoDB: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "database_unavailable",
                "detail": f"Database insertion failed: {exc}",
                "detected": True,
                "confidence": best["confidence"],
                "severity": best["severity"],
                "bbox": best["bbox"],
                "authority": {
                    "name": authority["name"],
                    "shortName": authority["shortName"],
                },
                "imageUrl": image_url,
                "address": address,
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "timestamp": ts,
            },
        )

    # ------------------------------------------------------------------
    # 10. Automatic Report Dispatch (SMTP or Simulation)
    # ------------------------------------------------------------------
    dispatch_res = dispatch_report(created)
    delivery_status = dispatch_res["reportStatus"]

    if delivery_status == "sent":
        delivery_note = "Email sent successfully"
        reported_at = datetime.now(timezone.utc).isoformat()
    elif delivery_status == "simulated":
        delivery_note = "Demo report generated"
        reported_at = None
    else:
        delivery_note = f"Report delivery failed: {dispatch_res.get('error', 'SMTP failure')}"
        reported_at = None

    try:
        _repo.update_report_status(
            pothole_id=pothole_id,
            report_status=delivery_status,
            report_data=dispatch_res.get("report"),
            report_payload=dispatch_res.get("report"),
            report_attempts=1,
            last_report_attempt_at=datetime.now(timezone.utc).isoformat(),
            reported_at=reported_at,
            note=delivery_note,
        )
    except Exception as exc:
        logger.warning("Could not update report status in database: %s", exc)

    # ------------------------------------------------------------------
    # 11. Return Created Result
    # ------------------------------------------------------------------
    return {
        "detected": True,
        "potholeId": pothole_id,
        "confidence": best["confidence"],
        "severity": best["severity"],
        "bbox": best["bbox"],
        "authority": {
            "name": authority["name"],
            "shortName": authority["shortName"],
        },
        "imageUrl": image_url,
        "address": address,
        "status": doc["status"],
        "reportStatus": delivery_status,
        "allDetections": detections,
        "detectionCount": len(detections),
        "timestamp": ts,
        "coordinates": {"latitude": latitude, "longitude": longitude},
    }


@app.get("/api/potholes")
async def list_potholes(
    status: str | None = Query(None, description="Filter by status (reported, acknowledged, in_progress, resolved)"),
    severity: str | None = Query(None, description="Filter by severity (low, medium, high)"),
    authority: str | None = Query(None, description="Filter by authority shortName or name (e.g. MCD, PWD, NHAI)"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    includeDemo: bool = Query(False, description="Whether to include seed demo data (default false for live-only records)"),
):
    """Return newest pothole records first with optional filtering."""
    try:
        records = _repo.list_all(
            status=status,
            severity=severity,
            authority=authority,
            limit=limit,
            include_demo=includeDemo,
        )
        return records
    except Exception as exc:
        logger.error("Failed to list potholes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database query failed: {exc}",
        )


@app.get("/api/potholes/{pothole_id}")
async def get_pothole(pothole_id: str):
    """Retrieve details for a single pothole by ID."""
    try:
        record = _repo.get_by_id(pothole_id)
    except Exception as exc:
        logger.error("Failed to get pothole %s: %s", pothole_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database query failed: {exc}",
        )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pothole '{pothole_id}' not found",
        )
    return record


@app.patch("/api/potholes/{pothole_id}/status")
async def update_pothole_status(
    pothole_id: str,
    payload: StatusUpdateRequest,
):
    """Update pothole status, log to statusHistory, and return updated record."""
    try:
        validate_status(payload.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    try:
        updated = _repo.update_status(
            pothole_id=pothole_id,
            new_status=payload.status,
            note=payload.note,
        )
    except Exception as exc:
        logger.error("Failed to update status for pothole %s: %s", pothole_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database update failed: {exc}",
        )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pothole '{pothole_id}' not found",
        )

    return updated


@app.post("/api/potholes/{pothole_id}/report")
async def report_pothole(pothole_id: str):
    """
    Generate and dispatch (or simulate in Demo Mode) an official repair report
    to the responsible road authority.
    """
    try:
        pothole = _repo.get_by_id(pothole_id)
    except Exception as exc:
        logger.error("Failed to fetch pothole %s for report: %s", pothole_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database query failed: {exc}",
        )

    if not pothole:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pothole '{pothole_id}' not found",
        )

    dispatch_res = dispatch_report(pothole)
    now_iso = datetime.now(timezone.utc).isoformat()
    reported_at = now_iso if dispatch_res["reportStatus"] == "sent" else None

    try:
        updated = _repo.update_report_status(
            pothole_id=pothole_id,
            report_status=dispatch_res["reportStatus"],
            report_data=dispatch_res.get("report"),
            report_payload=dispatch_res.get("report"),
            report_attempts=1,
            last_report_attempt_at=now_iso,
            reported_at=reported_at,
            note=dispatch_res["message"],
        )
    except Exception as exc:
        logger.warning("Could not update report status in database: %s", exc)
        updated = pothole
        updated["reportStatus"] = dispatch_res["reportStatus"]

    return {
        "success": dispatch_res["success"],
        "simulated": dispatch_res.get("simulated", False),
        "reportStatus": dispatch_res["reportStatus"],
        "message": dispatch_res["message"],
        "report": dispatch_res.get("report"),
        "pothole": updated,
    }
