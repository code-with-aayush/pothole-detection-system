"""
PotholeAlert — Seed Demo Data.

Inserts realistic sample pothole records in Delhi NCR across various authorities
(MCD, PWD, NHAI), severities (high, medium, low), and statuses (reported, in_progress, resolved).

Idempotent: Checks for existing seed records before inserting to avoid duplicates.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db import ensure_indexes, get_db, ping_db
from services.authority import get_authority_for_location

# 5 Realistic Delhi NCR sample locations (marked as seed demo data)
SEED_RECORDS = [
    {
        "seed_key": "seed_delhi_cp_01",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "address": "Barakhamba Road, Connaught Place, New Delhi",
        "confidence": 0.8920,
        "severity": "high",
        "status": "reported",
        "reportStatus": "pending",
        "source": "seed_demo",
        "isDemo": True,
        "bbox": {"x1": 120.0, "y1": 95.0, "x2": 450.0, "y2": 310.0},
        "days_ago": 0.1,  # few hours ago
        "notes": ["Initial pothole detection on inner circle feeder road"],
    },
    {
        "seed_key": "seed_delhi_chandni_chowk_02",
        "latitude": 28.6506,
        "longitude": 77.2303,
        "address": "Netaji Subhash Marg, Chandni Chowk, Old Delhi",
        "confidence": 0.7650,
        "severity": "medium",
        "status": "acknowledged",
        "reportStatus": "sent",
        "source": "seed_demo",
        "isDemo": True,
        "bbox": {"x1": 80.0, "y1": 110.0, "x2": 320.0, "y2": 260.0},
        "days_ago": 1.2,
        "notes": [
            "Pothole reported near Red Fort crossing",
            "Ward inspector acknowledged and scheduled inspection",
        ],
    },
    {
        "seed_key": "seed_delhi_nehru_place_03",
        "latitude": 28.5494,
        "longitude": 77.2536,
        "address": "Outer Ring Road, Nehru Place Flyover Descent, South Delhi",
        "confidence": 0.9410,
        "severity": "high",
        "status": "in_progress",
        "reportStatus": "sent",
        "source": "seed_demo",
        "isDemo": True,
        "bbox": {"x1": 150.0, "y1": 130.0, "x2": 520.0, "y2": 380.0},
        "days_ago": 2.5,
        "notes": [
            "Severe pothole on arterial flyover descent causing lane bottleneck",
            "PWD emergency response team deployed cold mix patch crew",
        ],
    },
    {
        "seed_key": "seed_delhi_vikas_marg_04",
        "latitude": 28.6328,
        "longitude": 77.2910,
        "address": "Vikas Marg, Laxmi Nagar Corridor, East Delhi",
        "confidence": 0.6840,
        "severity": "medium",
        "status": "reported",
        "reportStatus": "pending",
        "source": "seed_demo",
        "isDemo": True,
        "bbox": {"x1": 110.0, "y1": 140.0, "x2": 360.0, "y2": 290.0},
        "days_ago": 0.5,
        "notes": ["Moderate asphalt depression detected by commuter upload"],
    },
    {
        "seed_key": "seed_delhi_nh48_mahipalpur_05",
        "latitude": 28.3600,
        "longitude": 76.8500,
        "address": "NH-48 Delhi-Jaipur Expressway, Manesar Toll Corridor",
        "confidence": 0.5120,
        "severity": "low",
        "status": "resolved",
        "reportStatus": "sent",
        "source": "seed_demo",
        "isDemo": True,
        "bbox": {"x1": 200.0, "y1": 180.0, "x2": 340.0, "y2": 270.0},
        "days_ago": 5.0,
        "notes": [
            "Minor surface wear on highway shoulder",
            "NHAI highway maintenance unit patched and closed issue",
        ],
    },
]


def seed_database() -> int:
    print("=" * 60)
    print("PotholeAlert — Database Seed Script")
    print("=" * 60)

    try:
        ping_db()
    except Exception as exc:
        print(f"[FAIL] Cannot connect to MongoDB: {exc}")
        return 1

    ensure_indexes()
    db = get_db()
    collection = db["potholes"]

    now = datetime.now(timezone.utc)
    inserted_count = 0
    updated_count = 0

    for item in SEED_RECORDS:
        key = item["seed_key"]
        lat = item["latitude"]
        lng = item["longitude"]
        authority = get_authority_for_location(lat, lng)

        detected_dt = now - timedelta(days=item["days_ago"])
        detected_iso = detected_dt.isoformat()

        # Build status history
        history = []
        statuses = ["reported"]
        if item["status"] in ("acknowledged", "in_progress", "resolved"):
            statuses.append(item["status"])

        for i, note in enumerate(item["notes"]):
            hist_dt = detected_dt + timedelta(hours=i * 6)
            st = statuses[min(i, len(statuses) - 1)]
            history.append({
                "status": st,
                "changedAt": hist_dt.isoformat(),
                "note": note,
            })

        doc = {
            "seedKey": key,
            "isDemo": True,
            "latitude": lat,
            "longitude": lng,
            "address": item["address"],
            "imageUrl": f"/sample-data/seed_{key}.jpg",
            "detectedAt": detected_iso,
            "confidence": item["confidence"],
            "severity": item["severity"],
            "authority": authority,
            "status": item["status"],
            "reportStatus": item["reportStatus"],
            "source": item.get("source", "seed_demo"),
            "bbox": item["bbox"],
            "statusHistory": history,
            "createdAt": detected_iso,
            "updatedAt": now.isoformat(),
        }

        # Idempotent upsert based on seedKey
        existing = collection.find_one({"seedKey": key})
        if existing:
            collection.update_one({"seedKey": key}, {"$set": doc})
            updated_count += 1
            print(f"  [UPDATED] {key} -> Authority: {authority['shortName']} | Status: {item['status']}")
        else:
            collection.insert_one(doc)
            inserted_count += 1
            print(f"  [INSERTED] {key} -> Authority: {authority['shortName']} | Status: {item['status']}")

    total = collection.count_documents({})
    print("=" * 60)
    print(f"[SUMMARY] Seed completed: {inserted_count} inserted, {updated_count} updated. Total potholes in DB: {total}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(seed_database())
