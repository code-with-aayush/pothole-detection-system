"""
PotholeAlert — API Route Tests with Mocked Dependencies.

Tests HTTP API contracts independently of live external databases:
- POST /api/detect with no pothole detected
- POST /api/detect without GPS coordinates (detection returned, DB skipped)
- POST /api/detect with GPS and database available (persisted, potholeId returned)
- POST /api/detect with GPS and database unavailable (explicit 503 with detection details, no fake ID)
- POST /api/detect with explicit road classification (roadName="NH-48" maps to NHAI)
- GET /api/potholes list
- GET /api/potholes/{id} not found (404)
- PATCH /api/potholes/{id}/status validation (400 on invalid status)
"""

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app

# Minimal 1x1 PNG bytes for testing file uploads
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def client():
    return TestClient(app)


def test_api_detect_no_pothole(client):
    with patch("main.detect_potholes", return_value=[]):
        resp = client.post(
            "/api/detect",
            files={"file": ("test.png", TINY_PNG, "image/png")},
            data={"latitude": "28.6139", "longitude": "77.2090"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is False
        assert "No pothole detected" in data["message"]


def test_api_detect_without_gps(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.8613,
            "severity": "high",
            "bbox": {"x1": 100.0, "y1": 80.0, "x2": 430.0, "y2": 290.0},
        }
    ]

    with patch("main.detect_potholes", return_value=mock_detection):
        resp = client.post(
            "/api/detect",
            files={"file": ("test.png", TINY_PNG, "image/png")},
            # No GPS coordinates provided
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is True
        assert data["confidence"] == 0.8613
        assert data["coordinates"] is None
        assert "potholeId" not in data  # No database record created without GPS
        assert data["authority"]["shortName"] == "UNKNOWN"
        assert "GPS coordinates required" in data["message"]


def test_api_detect_with_gps_and_db_available(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.8613,
            "severity": "high",
            "bbox": {"x1": 100.0, "y1": 80.0, "x2": 430.0, "y2": 290.0},
        }
    ]

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main.is_mongodb_available", return_value=True), \
         patch("main._repo.find_duplicate", return_value=None), \
         patch("main._repo.create", return_value={"_id": "mock_pothole_id_123"}), \
         patch("main.dispatch_report", return_value={
             "success": True, "simulated": True, "reportStatus": "simulated",
             "message": "Demo report generated", "report": {},
         }), \
         patch("main._repo.update_report_status", return_value=None):

        resp = client.post(
            "/api/detect",
            files={"file": ("test.png", TINY_PNG, "image/png")},
            data={"latitude": "28.6139", "longitude": "77.2090", "source": "upload"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is True
        assert data["potholeId"] == "mock_pothole_id_123"
        assert data["authority"]["shortName"] == "MCD"
        assert data["status"] == "reported"
        assert data["reportStatus"] == "simulated"


def test_api_detect_with_gps_and_db_unavailable(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.8613,
            "severity": "high",
            "bbox": {"x1": 100.0, "y1": 80.0, "x2": 430.0, "y2": 290.0},
        }
    ]

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main.is_mongodb_available", return_value=False):

        resp = client.post(
            "/api/detect",
            files={"file": ("test.png", TINY_PNG, "image/png")},
            data={"latitude": "28.6139", "longitude": "77.2090"},
        )
        # Must return explicit 503 database unavailable
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"] == "database_unavailable"
        assert "MongoDB is unreachable" in data["detail"]
        assert data["detected"] is True
        assert data["confidence"] == 0.8613
        assert "potholeId" not in data  # No fake ID returned


def test_api_detect_with_road_name_classification(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.85,
            "severity": "high",
            "bbox": {"x1": 50.0, "y1": 50.0, "x2": 200.0, "y2": 200.0},
        }
    ]

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main.is_mongodb_available", return_value=True), \
         patch("main._repo.find_duplicate", return_value=None), \
         patch("main._repo.create", return_value={"_id": "mock_id_nhai"}):

        resp = client.post(
            "/api/detect",
            files={"file": ("test.png", TINY_PNG, "image/png")},
            data={
                "latitude": "28.6139",
                "longitude": "77.2090",
                "roadName": "NH-48 Express Corridor",
                "roadType": "National Highway",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authority"]["shortName"] == "NHAI"


def test_api_get_pothole_not_found(client):
    with patch("main._repo.get_by_id", return_value=None):
        resp = client.get("/api/potholes/nonexistent_id")
        assert resp.status_code == 404


def test_api_patch_status_invalid(client):
    resp = client.patch(
        "/api/potholes/any_id/status",
        json={"status": "invalid_status", "note": "Test note"},
    )
    assert resp.status_code == 400
    assert "Invalid status" in resp.json()["detail"]


def test_api_detect_stores_image_and_serves_static(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.86,
            "severity": "high",
            "bbox": {"x1": 10.0, "y1": 10.0, "x2": 100.0, "y2": 100.0},
        }
    ]

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main.is_mongodb_available", return_value=True), \
         patch("main._repo.find_duplicate", return_value=None), \
         patch("main._repo.create", return_value={"_id": "test_id_img"}):

        resp = client.post(
            "/api/detect",
            files={"file": ("evidence.png", TINY_PNG, "image/png")},
            data={"latitude": "28.6139", "longitude": "77.2090"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "imageUrl" in data
        assert data["imageUrl"].startswith("/uploads/")

        # Verify static file serves through FastAPI /uploads/ route
        static_resp = client.get(data["imageUrl"])
        assert static_resp.status_code == 200
        assert len(static_resp.content) == len(TINY_PNG)


def test_api_report_demo_mode(client):
    mock_pothole = {
        "_id": "6aa4528309ff3816f6c10f54",
        "authority": {"name": "MCD", "shortName": "MCD", "email": "demo-mcd@example.com"},
        "latitude": 28.6139,
        "longitude": 77.2090,
        "address": "Connaught Place, New Delhi",
        "severity": "high",
        "confidence": 0.86,
        "status": "reported",
        "reportStatus": "pending",
        "detectedAt": "2026-09-12T00:00:00Z",
    }

    with patch("main._repo.get_by_id", return_value=mock_pothole), \
         patch("main._repo.update_report_status", return_value={**mock_pothole, "reportStatus": "simulated"}):

        resp = client.post("/api/potholes/6aa4528309ff3816f6c10f54/report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["simulated"] is True
        assert data["reportStatus"] == "simulated"
        assert "Demo report generated" in data["message"]
        assert "report" in data
        assert data["report"]["potholeId"] == "6aa4528309ff3816f6c10f54"


def test_api_report_not_found(client):
    with patch("main._repo.get_by_id", return_value=None):
        resp = client.post("/api/potholes/000000000000000000000000/report")
        assert resp.status_code == 404


def test_api_detect_duplicate_detection(client):
    """Test duplicate detection prevents creating a second MongoDB record."""
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.88,
            "severity": "high",
            "bbox": {"x1": 50.0, "y1": 50.0, "x2": 250.0, "y2": 250.0},
        }
    ]
    existing_duplicate = {
        "_id": "existing_duplicate_pothole_id",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "confidence": 0.85,
        "severity": "high",
        "bbox": {"x1": 50.0, "y1": 50.0, "x2": 250.0, "y2": 250.0},
        "authority": {"name": "Municipal Corporation of Delhi", "shortName": "MCD"},
        "imageUrl": "/uploads/existing.jpg",
        "address": "Connaught Place, New Delhi",
        "status": "reported",
        "reportStatus": "pending",
    }

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main.is_mongodb_available", return_value=True), \
         patch("main._repo.find_duplicate", return_value=existing_duplicate), \
         patch("main._repo.create") as mock_create:

        resp = client.post(
            "/api/detect",
            files={"file": ("frame.png", TINY_PNG, "image/png")},
            data={"latitude": "28.6139", "longitude": "77.2090", "source": "mobile_camera"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is True
        assert data["isDuplicate"] is True
        assert data["potholeId"] == "existing_duplicate_pothole_id"
        # Must NOT call create to insert a duplicate record
        mock_create.assert_not_called()


def test_api_report_failed_mode(client, monkeypatch):
    """Test failed reporting mode when SMTP fails."""
    mock_pothole = {
        "_id": "6aa4528309ff3816f6c10f55",
        "authority": {"name": "PWD", "shortName": "PWD", "email": "demo-pwd@example.com"},
        "latitude": 28.5500,
        "longitude": 77.2500,
        "address": "Nehru Place, New Delhi",
        "severity": "high",
        "confidence": 0.92,
        "status": "reported",
        "reportStatus": "pending",
        "detectedAt": "2026-09-12T00:00:00Z",
    }

    import services.reporting as reporting_module
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid.domain")
    monkeypatch.setenv("SMTP_USER", "invalid_user")

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value.send_message.side_effect = Exception("Connection refused")
    monkeypatch.setattr(reporting_module.smtplib, "SMTP", lambda *args, **kwargs: mock_smtp)

    with patch("main._repo.get_by_id", return_value=mock_pothole), \
         patch("main._repo.update_report_status", return_value={**mock_pothole, "reportStatus": "failed"}):

        resp = client.post("/api/potholes/6aa4528309ff3816f6c10f55/report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["reportStatus"] == "failed"
        assert "Email delivery failed" in data["message"]


def test_api_list_potholes_live_only_filtering(client):
    """Test dashboard live-only filtering via includeDemo=false."""
    with patch("main._repo.list_all") as mock_list_all:
        mock_list_all.return_value = [
            {"_id": "live_01", "source": "mobile_camera", "isDemo": False},
            {"_id": "live_02", "source": "upload", "isDemo": False},
        ]

        resp = client.get("/api/potholes?includeDemo=false")
        assert resp.status_code == 200
        mock_list_all.assert_called_once_with(
            status=None,
            severity=None,
            authority=None,
            limit=50,
            include_demo=False,
        )


def test_api_full_detection_and_report_flow(client):
    """End-to-end simulation: camera frame detect -> MongoDB record created -> report dispatched."""
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.892,
            "severity": "high",
            "bbox": {"x1": 120.0, "y1": 95.0, "x2": 450.0, "y2": 310.0},
        }
    ]
    created_doc = {
        "_id": "67890abcdef1234567890123",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "authority": {"name": "Municipal Corporation of Delhi", "shortName": "MCD", "email": "mcd@example.com"},
        "severity": "high",
        "confidence": 0.892,
        "address": "Connaught Place, New Delhi",
        "imageUrl": "/uploads/pothole_e2e_test.jpg",
        "status": "reported",
        "reportStatus": "pending",
        "source": "mobile_camera",
        "detectedAt": "2026-09-12T12:00:00Z",
    }

    # Step 1: POST /api/detect with GPS from mobile_camera
    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main.is_mongodb_available", return_value=True), \
         patch("main._repo.find_duplicate", return_value=None), \
         patch("main._repo.create", return_value=created_doc):

        detect_resp = client.post(
            "/api/detect",
            files={"file": ("frame.jpg", TINY_PNG, "image/jpeg")},
            data={
                "latitude": "28.6315",
                "longitude": "77.2167",
                "source": "mobile_camera",
            },
        )
        assert detect_resp.status_code == 200
        detect_data = detect_resp.json()
        assert detect_data["detected"] is True
        assert detect_data["potholeId"] == "67890abcdef1234567890123"
        pothole_id = detect_data["potholeId"]

    # Step 2: POST /api/potholes/{potholeId}/report
    with patch("main._repo.get_by_id", return_value=created_doc), \
         patch("main._repo.update_report_status", return_value={**created_doc, "reportStatus": "simulated"}):

        report_resp = client.post(f"/api/potholes/{pothole_id}/report")
        assert report_resp.status_code == 200
        report_data = report_resp.json()
        assert report_data["success"] is True
        assert report_data["simulated"] is True
        assert report_data["reportStatus"] == "simulated"
        assert "simulation mode active" in report_data["message"]
        assert report_data["report"]["potholeId"] == pothole_id


def test_api_ingest_no_pothole(client):
    with patch("main.detect_potholes", return_value=[]):
        resp = client.post(
            "/api/detections/ingest",
            files={"file": ("frame.jpg", TINY_PNG, "image/jpeg")},
            data={"latitude": "28.6139", "longitude": "77.2090", "source": "mobile_camera"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is False
        assert "No pothole detected" in data["message"]
        assert "potholeId" not in data


def test_api_ingest_positive_new_incident(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.895,
            "severity": "high",
            "bbox": {"x1": 110.0, "y1": 90.0, "x2": 420.0, "y2": 310.0},
        }
    ]
    created_doc = {
        "_id": "67890abcdef1234567890999",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "authority": {"name": "Municipal Corporation of Delhi", "shortName": "MCD", "email": "mcd@example.com"},
        "severity": "high",
        "confidence": 0.895,
        "address": "Kartavya Path, New Delhi",
        "imageUrl": "/uploads/pothole_test_ingest.jpg",
        "status": "reported",
        "reportStatus": "dashboard_ticket_created",
        "reportChannel": "dashboard_ticket",
        "source": "mobile_camera",
        "detectedAt": "2026-09-14T12:00:00Z",
    }

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main._repo.find_nearby_unresolved", return_value=None), \
         patch("main._repo.create", return_value=created_doc), \
         patch("main.dispatch_report", return_value={
             "success": True,
             "simulated": True,
             "reportStatus": "simulated",
             "message": "Dashboard ticket created; email simulation mode active",
             "report": {"potholeId": "67890abcdef1234567890999"},
         }), \
         patch("main._repo.update_report_status", return_value=created_doc):

        resp = client.post(
            "/api/detections/ingest",
            files={"file": ("frame.jpg", TINY_PNG, "image/jpeg")},
            data={"latitude": "28.6139", "longitude": "77.2090", "source": "mobile_camera"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is True
        assert data["potholeId"] == "67890abcdef1234567890999"
        assert data["isDuplicate"] is False
        assert data["reportStatus"] == "simulated"
        assert data["reportChannel"] == "dashboard_ticket"
        assert data["severity"] == "high"
        assert data["confidence"] == 0.895
        assert data["coordinates"]["latitude"] == 28.6139


def test_api_ingest_positive_duplicate_merges(client):
    mock_detection = [
        {
            "detected": True,
            "confidence": 0.88,
            "severity": "high",
            "bbox": {"x1": 100.0, "y1": 80.0, "x2": 400.0, "y2": 300.0},
        }
    ]
    existing_duplicate = {
        "_id": "67890abcdef1234567890111",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "authority": {"name": "Municipal Corporation of Delhi", "shortName": "MCD", "email": "mcd@example.com"},
        "severity": "high",
        "confidence": 0.88,
        "address": "Kartavya Path, New Delhi",
        "imageUrl": "/uploads/pothole_existing.jpg",
        "status": "reported",
        "reportStatus": "dashboard_ticket_created",
        "reportChannel": "dashboard_ticket",
        "detectionCount": 1,
    }

    with patch("main.detect_potholes", return_value=mock_detection), \
         patch("main._repo.find_nearby_unresolved", return_value=existing_duplicate), \
         patch("main._repo.record_duplicate_detection", return_value={**existing_duplicate, "detectionCount": 2}):

        resp = client.post(
            "/api/detections/ingest",
            files={"file": ("frame.jpg", TINY_PNG, "image/jpeg")},
            data={"latitude": "28.6139", "longitude": "77.2090", "source": "mobile_camera"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is True
        assert data["potholeId"] == "67890abcdef1234567890111"
        assert data["isDuplicate"] is True
        assert data["detectionCount"] == 2
        assert "Duplicate detection merged" in data["message"]



