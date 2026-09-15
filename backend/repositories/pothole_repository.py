"""
PotholeAlert — Pothole Repository.

Encapsulates all database operations for the 'potholes' collection, including
creation, retrieval, filtering, status updates, and duplicate detection.
"""

from datetime import datetime, timezone
import logging
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING, ReturnDocument
from pymongo.collection import Collection

from db import get_db
from models.pothole import validate_status
from services.geo import haversine_distance

logger = logging.getLogger("potholealert.repository")

DUPLICATE_MAX_DISTANCE_METERS = 50.0
DUPLICATE_MAX_TIME_SECONDS = 10.0


def _get_collection() -> Collection[dict[str, Any]]:
    """Retrieve the potholes collection."""
    return get_db()["potholes"]


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Format MongoDB document for JSON serialization, converting ObjectId to str."""
    if doc is None:
        return None
    d = dict(doc)
    if "_id" in d and isinstance(d["_id"], ObjectId):
        d["_id"] = str(d["_id"])
    return d


def parse_iso_datetime(dt_str: str) -> datetime:
    """Safely parse an ISO datetime string into a timezone-aware UTC datetime."""
    # Replace trailing 'Z' with '+00:00' for standard fromisoformat parsing
    clean_str = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class PotholeRepository:
    """Repository managing Pothole collection persistence."""

    def __init__(self, collection: Collection[dict[str, Any]] | None = None):
        self._collection = collection

    @property
    def collection(self) -> Collection[dict[str, Any]]:
        if self._collection is not None:
            return self._collection
        return _get_collection()

    def find_nearby_unresolved(
        self,
        latitude: float | None,
        longitude: float | None,
        max_distance: float = DUPLICATE_MAX_DISTANCE_METERS,
    ) -> dict[str, Any] | None:
        """
        Search for an existing unresolved pothole record within approximately max_distance meters.
        Prefers unresolved records (status != 'resolved') so that repeat detections of the same
        pothole merge seamlessly into the existing active incident.
        """
        if latitude is None or longitude is None:
            return None

        candidates = self.collection.find(
            {
                "status": {"$ne": "resolved"},
                "latitude": {"$ne": None},
                "longitude": {"$ne": None},
            }
        ).sort("detectedAt", DESCENDING).limit(100)

        closest_candidate = None
        closest_distance = float("inf")

        for candidate in candidates:
            cand_lat = candidate.get("latitude")
            cand_lng = candidate.get("longitude")
            if cand_lat is None or cand_lng is None:
                continue

            dist = haversine_distance(latitude, longitude, float(cand_lat), float(cand_lng))
            if dist <= max_distance and dist < closest_distance:
                closest_distance = dist
                closest_candidate = candidate

        if closest_candidate:
            logger.info(
                "Nearby unresolved pothole found: %s (distance: %.1fm)",
                closest_candidate.get("_id"),
                closest_distance,
            )
            return serialize_doc(closest_candidate)

        return None

    def record_duplicate_detection(
        self,
        pothole_id: str,
        detected_at: str | datetime | None = None,
        note: str = "Duplicate detection merged",
    ) -> dict[str, Any] | None:
        """
        Record a repeat/duplicate detection for an existing incident:
        increments detectionCount, updates lastDetectedAt, appends an audit event to statusHistory,
        and refreshes updatedAt.
        """
        try:
            query = {"_id": ObjectId(pothole_id)}
        except InvalidId:
            query = {"_id": pothole_id}

        now_iso = datetime.now(timezone.utc).isoformat()
        if detected_at is None:
            dt_iso = now_iso
        elif isinstance(detected_at, datetime):
            dt_iso = detected_at.isoformat()
        else:
            dt_iso = str(detected_at)

        existing = self.collection.find_one(query)
        current_status = existing.get("status", "reported") if existing else "reported"

        update_ops: dict[str, Any] = {
            "$inc": {"detectionCount": 1},
            "$set": {
                "lastDetectedAt": dt_iso,
                "updatedAt": now_iso,
            },
            "$push": {
                "statusHistory": {
                    "status": current_status,
                    "changedAt": dt_iso,
                    "note": note,
                }
            },
        }

        updated = self.collection.find_one_and_update(
            query,
            update_ops,
            return_document=ReturnDocument.AFTER,
        )
        return serialize_doc(updated)

    def find_duplicate(
        self,
        latitude: float | None,
        longitude: float | None,
        detected_at: str | datetime | None = None,
        max_distance: float = DUPLICATE_MAX_DISTANCE_METERS,
        max_time_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Find duplicate pothole within max_distance meters.
        Prefers unresolved records within max_distance meters.
        If max_time_seconds is explicitly supplied (legacy caller), verifies time window;
        otherwise matches any unresolved pothole within distance regardless of elapsed time.
        """
        if latitude is None or longitude is None:
            return None

        # When time window is not constrained (standard assignment requirement),
        # use find_nearby_unresolved
        if max_time_seconds is None:
            return self.find_nearby_unresolved(latitude, longitude, max_distance=max_distance)

        # Legacy time-bounded search
        if detected_at is None:
            ref_dt = datetime.now(timezone.utc)
        elif isinstance(detected_at, datetime):
            ref_dt = detected_at if detected_at.tzinfo else detected_at.replace(tzinfo=timezone.utc)
        else:
            try:
                ref_dt = parse_iso_datetime(detected_at)
            except Exception:
                ref_dt = datetime.now(timezone.utc)

        candidates = self.collection.find(
            {"latitude": {"$ne": None}, "longitude": {"$ne": None}}
        ).sort("detectedAt", DESCENDING).limit(50)

        for candidate in candidates:
            cand_lat = candidate.get("latitude")
            cand_lng = candidate.get("longitude")
            cand_time_str = candidate.get("detectedAt")

            if cand_lat is None or cand_lng is None:
                continue

            if cand_time_str:
                try:
                    cand_dt = parse_iso_datetime(str(cand_time_str))
                    time_diff = abs((ref_dt - cand_dt).total_seconds())
                    if time_diff > max_time_seconds:
                        continue
                except Exception:
                    continue
            else:
                continue

            dist = haversine_distance(latitude, longitude, float(cand_lat), float(cand_lng))
            if dist <= max_distance:
                return serialize_doc(candidate)

        return None

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a new pothole document into MongoDB."""
        doc_copy = dict(document)
        result = self.collection.insert_one(doc_copy)
        doc_copy["_id"] = str(result.inserted_id)
        return doc_copy

    def get_by_id(self, pothole_id: str) -> dict[str, Any] | None:
        """Find a single pothole by string ID or ObjectId."""
        try:
            oid = ObjectId(pothole_id)
            doc = self.collection.find_one({"_id": oid})
        except InvalidId:
            doc = self.collection.find_one({"_id": pothole_id})

        return serialize_doc(doc)

    def list_all(
        self,
        status: str | None = None,
        severity: str | None = None,
        authority: str | None = None,
        limit: int = 50,
        include_demo: bool = False,
    ) -> list[dict[str, Any]]:
        """
        List potholes with optional filters for status, severity, authority, and demo exclusion.
        Always orders newest records first (detectedAt DESCENDING).
        """
        query: dict[str, Any] = {}
        if not include_demo:
            query["isDemo"] = {"$ne": True}
            query["seedKey"] = {"$exists": False}
            query["source"] = {"$ne": "seed_demo"}

        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        if authority:
            # Match shortName (e.g. "MCD") or full name case-insensitively
            query["$or"] = [
                {"authority.shortName": {"$regex": f"^{authority}$", "$options": "i"}},
                {"authority.name": {"$regex": authority, "$options": "i"}},
            ]

        safe_limit = max(1, min(limit, 200))
        cursor = self.collection.find(query).sort("detectedAt", DESCENDING).limit(safe_limit)
        return [serialize_doc(d) for d in cursor]

    def update_status(
        self,
        pothole_id: str,
        new_status: str,
        note: str = "",
    ) -> dict[str, Any] | None:
        """
        Update the status of a pothole, append an entry to statusHistory,
        and update the updatedAt timestamp.
        """
        validate_status(new_status)

        try:
            query = {"_id": ObjectId(pothole_id)}
        except InvalidId:
            query = {"_id": pothole_id}

        now_iso = datetime.now(timezone.utc).isoformat()
        history_item = {
            "status": new_status,
            "changedAt": now_iso,
            "note": note,
        }

        update_ops = {
            "$set": {
                "status": new_status,
                "updatedAt": now_iso,
            },
            "$push": {
                "statusHistory": history_item,
            },
        }

        updated = self.collection.find_one_and_update(
            query,
            update_ops,
            return_document=ReturnDocument.AFTER,
        )

        return serialize_doc(updated)

    def update_report_status(
        self,
        pothole_id: str,
        report_status: str,
        report_data: dict[str, Any] | None = None,
        note: str = "",
        report_payload: dict[str, Any] | None = None,
        report_attempts: int | None = None,
        last_report_attempt_at: str | None = None,
        reported_at: str | None = None,
    ) -> dict[str, Any] | None:
        """Update reportStatus, save report payload, update attempt counters, and log an entry in statusHistory."""
        from models.pothole import validate_report_status
        validate_report_status(report_status)

        try:
            query = {"_id": ObjectId(pothole_id)}
        except InvalidId:
            query = {"_id": pothole_id}

        now_iso = datetime.now(timezone.utc).isoformat()
        set_fields: dict[str, Any] = {
            "reportStatus": report_status,
            "updatedAt": now_iso,
        }
        if report_data is not None:
            set_fields["reportData"] = report_data
        if report_payload is not None:
            set_fields["reportPayload"] = report_payload
        if last_report_attempt_at is not None:
            set_fields["lastReportAttemptAt"] = last_report_attempt_at
        if reported_at is not None:
            set_fields["reportedAt"] = reported_at

        update_ops: dict[str, Any] = {"$set": set_fields}
        if report_attempts is not None:
            update_ops["$inc"] = {"reportAttempts": report_attempts}

        if note:
            existing = self.collection.find_one(query)
            current_status = existing.get("status", "reported") if existing else "reported"
            update_ops["$push"] = {
                "statusHistory": {
                    "status": current_status,
                    "changedAt": now_iso,
                    "note": note,
                }
            }

        updated = self.collection.find_one_and_update(
            query,
            update_ops,
            return_document=ReturnDocument.AFTER,
        )

        return serialize_doc(updated)

