"""
PotholeAlert — Unit Tests (Zero External Dependencies).

Requires NO MongoDB instance.
Tests:
- Authority matching priority (roadName / roadType classification)
- Authority geographic bounds matching (MCD, PWD, NHAI)
- Unknown authority fallback
- Haversine distance calculation
- Duplicate detection algorithm
- Status, severity, and reportStatus validations
- Document creation and status history formatting
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import MagicMock

from bson import ObjectId
import pytest

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from models.pothole import (
    ALLOWED_STATUSES,
    create_pothole_document,
    validate_report_status,
    validate_severity,
    validate_status,
)
from repositories.pothole_repository import PotholeRepository
from services.authority import get_authority_for_location, get_unknown_authority
from services.geo import haversine_distance


# ----------------------------------------------------------------------
# 1. Authority Matching: Road Classification Priority & Bounds
# ----------------------------------------------------------------------
def test_authority_priority_road_classification_nhai():
    # Priority 1: roadName with "NH" should map to NHAI even if inside city coordinates
    auth = get_authority_for_location(
        latitude=28.6139,
        longitude=77.2090,
        road_name="NH-48 Urban Bypass",
        road_type="National Highway",
    )
    assert auth["shortName"] == "NHAI"
    assert "National Highways Authority of India" in auth["name"]


def test_authority_priority_road_classification_pwd():
    # Priority 1: roadName with "Ring Road" or "Arterial" -> PWD
    auth = get_authority_for_location(
        latitude=28.6139,
        longitude=77.2090,
        road_name="Mahatma Gandhi Ring Road",
        road_type="arterial",
    )
    assert auth["shortName"] == "PWD"
    assert "Public Works Department" in auth["name"]


def test_authority_priority_road_classification_mcd():
    # Priority 1: roadType "colony" or "ward" -> MCD
    auth = get_authority_for_location(
        latitude=28.3600,
        longitude=76.8500,
        road_name="Ward 14 Residential Gali",
        road_type="colony",
    )
    assert auth["shortName"] == "MCD"
    assert "Municipal Corporation of Delhi" in auth["name"]


def test_authority_matching_mcd_coordinates():
    # Delhi central demo coordinates (28.6139, 77.2090) without road name -> MCD
    auth = get_authority_for_location(28.6139, 77.2090)
    assert auth["shortName"] == "MCD"
    assert "Municipal Corporation of Delhi" in auth["name"]


def test_authority_matching_pwd_coordinates():
    # Greater Delhi / NCT coordinates outside MCD core -> PWD
    auth = get_authority_for_location(28.5000, 77.0000)
    assert auth["shortName"] == "PWD"
    assert "Public Works Department" in auth["name"]


def test_authority_matching_nhai_coordinates():
    # Gurugram-Manesar expressway corridor outside PWD bounds -> NHAI
    auth = get_authority_for_location(28.3600, 76.8500)
    assert auth["shortName"] == "NHAI"
    assert "National Highways Authority of India" in auth["name"]


def test_authority_unknown_fallback():
    # Mumbai coordinates outside Delhi NCR -> UNKNOWN
    auth_mumbai = get_authority_for_location(19.0760, 72.8777)
    assert auth_mumbai["shortName"] == "UNKNOWN"

    # Missing coordinates -> UNKNOWN
    auth_none = get_authority_for_location(None, None)
    assert auth_none["shortName"] == "UNKNOWN"

    auth_lat_none = get_authority_for_location(None, 77.2090)
    assert auth_lat_none["shortName"] == "UNKNOWN"


# ----------------------------------------------------------------------
# 2. Haversine Distance Calculation
# ----------------------------------------------------------------------
def test_haversine_distance_identical():
    dist = haversine_distance(28.6139, 77.2090, 28.6139, 77.2090)
    assert dist == pytest.approx(0.0, abs=1e-3)


def test_haversine_distance_short():
    # 0.0003 deg latitude offset is approx 33.3 meters
    dist = haversine_distance(28.6139, 77.2090, 28.6142, 77.2090)
    assert 30.0 < dist < 36.0


def test_haversine_distance_known_landmarks():
    # Connaught Place to India Gate (~2.2 - 2.4 km)
    dist = haversine_distance(28.6315, 77.2167, 28.6129, 77.2295)
    assert 2000.0 < dist < 2600.0


# ----------------------------------------------------------------------
# 3. Duplicate Detection Logic (Using Mock Collection)
# ----------------------------------------------------------------------
class MockCursor:
    def __init__(self, data):
        self.data = list(data)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self.data[:n]

    def __iter__(self):
        return iter(self.data)


class MockCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find(self, query=None):
        filtered = self.docs
        if query and "status" in query and isinstance(query["status"], dict) and "$ne" in query["status"]:
            excluded = query["status"]["$ne"]
            filtered = [d for d in filtered if d.get("status") != excluded]
        return MockCursor(filtered)

    def find_one(self, filter):
        target_id = filter.get("_id")
        for doc in self.docs:
            if doc.get("_id") == target_id:
                return dict(doc)
        return None

    def find_one_and_update(self, filter, update, return_document=None):
        target_id = filter.get("_id")
        for doc in self.docs:
            if doc.get("_id") == target_id:
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + v
                if "$set" in update:
                    for k, v in update["$set"].items():
                        doc[k] = v
                if "$push" in update:
                    for k, v in update["$push"].items():
                        doc.setdefault(k, []).append(v)
                return dict(doc)
        return None


def test_duplicate_detection_repeated_every_three_seconds():
    now = datetime.now(timezone.utc)
    existing_doc = {
        "_id": ObjectId(),
        "latitude": 28.61390,
        "longitude": 77.20900,
        "detectedAt": (now - timedelta(seconds=3)).isoformat(),
        "confidence": 0.88,
        "severity": "high",
        "authority": {"name": "MCD", "shortName": "MCD"},
        "status": "reported",
        "reportStatus": "dashboard_ticket_created",
        "detectionCount": 1,
    }
    repo = PotholeRepository(collection=MockCollection([existing_doc]))

    # Detection 3 seconds later at same spot
    dup = repo.find_nearby_unresolved(
        latitude=28.61391,
        longitude=77.20901,
        max_distance=50.0,
    )
    assert dup is not None
    assert dup["_id"] == str(existing_doc["_id"])

    updated = repo.record_duplicate_detection(dup["_id"], detected_at=now.isoformat())
    assert updated["detectionCount"] == 2
    assert updated["statusHistory"][-1]["note"] == "Duplicate detection merged"


def test_duplicate_detection_repeated_after_one_minute():
    now = datetime.now(timezone.utc)
    existing_doc = {
        "_id": ObjectId(),
        "latitude": 28.61390,
        "longitude": 77.20900,
        "detectedAt": (now - timedelta(seconds=60)).isoformat(),
        "confidence": 0.88,
        "severity": "high",
        "authority": {"name": "MCD", "shortName": "MCD"},
        "status": "reported",
        "reportStatus": "dashboard_ticket_created",
        "detectionCount": 1,
    }
    repo = PotholeRepository(collection=MockCollection([existing_doc]))

    # Detection 60 seconds later at same spot (< 50m) still merges into existing unresolved incident
    dup = repo.find_nearby_unresolved(
        latitude=28.61392,
        longitude=77.20900,
        max_distance=50.0,
    )
    assert dup is not None
    assert dup["_id"] == str(existing_doc["_id"])


def test_duplicate_detection_nearby_unresolved():
    now = datetime.now(timezone.utc)
    existing_doc = {
        "_id": ObjectId(),
        "latitude": 28.61390,
        "longitude": 77.20900,
        "detectedAt": now.isoformat(),
        "status": "in_progress",
    }
    repo = PotholeRepository(collection=MockCollection([existing_doc]))

    # Point ~20m away and unresolved -> matches duplicate
    dup = repo.find_nearby_unresolved(
        latitude=28.61405,
        longitude=77.20900,
        max_distance=50.0,
    )
    assert dup is not None
    assert dup["_id"] == str(existing_doc["_id"])


def test_duplicate_detection_nearby_resolved_creates_new():
    now = datetime.now(timezone.utc)
    existing_doc = {
        "_id": ObjectId(),
        "latitude": 28.61390,
        "longitude": 77.20900,
        "detectedAt": now.isoformat(),
        "status": "resolved",  # Resolved pothole must not block a new incident
    }
    repo = PotholeRepository(collection=MockCollection([existing_doc]))

    # Resolved nearby pothole should return None so a new incident can be created
    dup = repo.find_nearby_unresolved(
        latitude=28.61390,
        longitude=77.20900,
        max_distance=50.0,
    )
    assert dup is None


def test_duplicate_detection_different_pothole_more_than_50m():
    now = datetime.now(timezone.utc)
    existing_doc = {
        "_id": ObjectId(),
        "latitude": 28.61390,
        "longitude": 77.20900,
        "detectedAt": now.isoformat(),
        "status": "reported",
    }
    repo = PotholeRepository(collection=MockCollection([existing_doc]))

    # > 50 meters away -> returns None so new incident is created
    dup = repo.find_nearby_unresolved(
        latitude=28.61850,
        longitude=77.20900,
        max_distance=50.0,
    )
    assert dup is None


def test_duplicate_detection_missing_gps():
    repo = PotholeRepository(collection=MockCollection())
    assert repo.find_nearby_unresolved(None, None) is None
    assert repo.find_nearby_unresolved(28.6139, None) is None


# ----------------------------------------------------------------------
# 4. Status, Severity, and Document Structure Validation
# ----------------------------------------------------------------------
def test_status_validation():
    for valid in ALLOWED_STATUSES:
        validate_status(valid)

    with pytest.raises(ValueError, match="Invalid status"):
        validate_status("closed")


def test_severity_validation():
    for valid in ["low", "medium", "high"]:
        validate_severity(valid)

    with pytest.raises(ValueError, match="Invalid severity"):
        validate_severity("extreme")


def test_report_status_validation():
    for valid in ["pending", "sent", "simulated", "failed"]:
        validate_report_status(valid)

    with pytest.raises(ValueError, match="Invalid reportStatus"):
        validate_report_status("archived")


def test_create_pothole_document():
    doc = create_pothole_document(
        latitude=28.6139,
        longitude=77.2090,
        confidence=0.8613,
        severity="high",
        bbox={"x1": 10.0, "y1": 20.0, "x2": 150.0, "y2": 120.0},
        authority={"name": "MCD", "shortName": "MCD", "email": "demo-mcd@example.com"},
        source="upload",
        initial_note="Test note",
    )
    assert doc["status"] == "reported"
    assert doc["reportStatus"] == "pending"
    assert len(doc["statusHistory"]) == 1
    assert doc["statusHistory"][0]["status"] == "reported"
    assert doc["statusHistory"][0]["note"] == "Test note"
    assert "createdAt" in doc
    assert "updatedAt" in doc


# ----------------------------------------------------------------------
# 5. Geocoding Unit Tests
# ----------------------------------------------------------------------
def test_geocoding_success(monkeypatch):
    from unittest.mock import MagicMock
    import services.geocoding as geocoding_module

    # Clear any cached live results from previous runs
    geocoding_module._GEOCODE_CACHE.clear()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "address": {
            "road": "Barakhamba Road",
            "suburb": "Connaught Place",
            "city": "New Delhi",
            "postcode": "110001",
        }
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_resp
    monkeypatch.setattr(geocoding_module.httpx, "Client", lambda **kwargs: mock_client)

    address = geocoding_module.reverse_geocode(28.6315, 77.2167)
    assert "Barakhamba Road" in address
    assert "Connaught Place" in address


def test_geocoding_failure_fallback(monkeypatch):
    import services.geocoding as geocoding_module

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.side_effect = Exception("Connection timed out")
    monkeypatch.setattr(geocoding_module.httpx, "Client", lambda **kwargs: mock_client)

    address = geocoding_module.reverse_geocode(99.9999, 99.9999)
    assert address == "Address unavailable"


def test_geocoding_missing_coords():
    from services.geocoding import reverse_geocode
    assert reverse_geocode(None, None) == ""
    assert reverse_geocode(28.6139, None) == ""


# ----------------------------------------------------------------------
# 6. Reporting Service Unit Tests
# ----------------------------------------------------------------------
def test_reporting_demo_mode(monkeypatch):
    from services.reporting import dispatch_report
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)

    pothole = {
        "_id": "6aa4528309ff3816f6c10f54",
        "authority": {"name": "MCD", "email": "demo-mcd@example.com"},
        "latitude": 28.6139,
        "longitude": 77.2090,
        "address": "Connaught Place",
        "severity": "high",
        "confidence": 0.86,
        "detectedAt": "2026-09-12T00:00:00Z",
        "imageUrl": "/uploads/test.jpg",
        "status": "reported",
    }

    result = dispatch_report(pothole)
    assert result["success"] is True
    assert result["simulated"] is True
    assert result["reportStatus"] == "simulated"
    assert result["report"]["potholeId"] == "6aa4528309ff3816f6c10f54"


def test_reporting_smtp_failure_mocked(monkeypatch):
    from unittest.mock import MagicMock
    import services.reporting as reporting_module

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("REPORT_FROM_EMAIL", "alerts@potholealert.local")

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value.send_message.side_effect = Exception("SMTP relay refused")
    monkeypatch.setattr(reporting_module.smtplib, "SMTP", lambda *args, **kwargs: mock_smtp)

    pothole = {
        "_id": "6aa4528309ff3816f6c10f54",
        "authority": {"name": "PWD", "email": "demo-pwd@example.com"},
        "latitude": 28.50,
        "longitude": 77.00,
        "severity": "medium",
        "confidence": 0.75,
        "status": "reported",
    }

    result = reporting_module.dispatch_report(pothole)
    assert result["success"] is False
    assert result["simulated"] is False
    assert result["reportStatus"] == "failed"
    assert "SMTP relay refused" in result["error"]

