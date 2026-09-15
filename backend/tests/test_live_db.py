"""
PotholeAlert — Live MongoDB Integration Smoke Tests.

Runs only when MongoDB is reachable at MONGODB_URI.
Automatically skips if MongoDB is unavailable, without failing the overall test suite.
"""

from pathlib import Path
import sys

from bson import ObjectId
import pytest

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db import get_db, is_mongodb_available, ping_db
from models.pothole import create_pothole_document
from repositories.pothole_repository import PotholeRepository

# Evaluate MongoDB reachability once for the test module
_live_db_ready = is_mongodb_available(timeout_ms=1500)

pytestmark = pytest.mark.skipif(
    not _live_db_ready,
    reason="Live MongoDB is unreachable at MONGODB_URI (skipped without failure)",
)


def test_live_ping():
    """Verify live database ping command."""
    res = ping_db()
    assert res["status"] == "connected"
    assert "database" in res


def test_live_crud_lifecycle():
    """Verify live record creation, retrieval, status update, and cleanup."""
    repo = PotholeRepository()
    test_doc = create_pothole_document(
        latitude=28.6139,
        longitude=77.2090,
        confidence=0.8950,
        severity="high",
        bbox={"x1": 50.0, "y1": 50.0, "x2": 200.0, "y2": 200.0},
        authority={"name": "MCD Test", "shortName": "MCD", "email": "test@mcd.gov"},
        initial_note="Automated live integration test",
    )

    # 1. Insert record
    created = repo.create(test_doc)
    pothole_id = created["_id"]
    assert pothole_id is not None
    assert ObjectId.is_valid(pothole_id)

    try:
        # 2. Retrieve record
        fetched = repo.get_by_id(pothole_id)
        assert fetched is not None
        assert fetched["_id"] == pothole_id
        assert fetched["status"] == "reported"
        assert fetched["confidence"] == 0.8950

        # 3. Update record status
        updated = repo.update_status(
            pothole_id=pothole_id,
            new_status="in_progress",
            note="Maintenance crew deployed in integration test",
        )
        assert updated is not None
        assert updated["status"] == "in_progress"
        assert len(updated["statusHistory"]) == 2
        assert updated["statusHistory"][1]["status"] == "in_progress"
        assert updated["statusHistory"][1]["note"] == "Maintenance crew deployed in integration test"

        # 4. Verify in list_all
        all_records = repo.list_all(limit=20)
        assert any(r["_id"] == pothole_id for r in all_records)

    finally:
        # 5. Clean up test record
        db = get_db()
        db["potholes"].delete_one({"_id": ObjectId(pothole_id)})
