"""
PotholeAlert — Remove Seed & Demo Records.

Purges all synthetic seed records (marked with isDemo=True, seedKey, or source='seed_demo')
from MongoDB, ensuring only genuine live detections remain in the database.
"""

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db import get_db, ping_db


def clean_seed_data() -> int:
    print("=" * 60)
    print("PotholeAlert — Clean Seed & Demo Data")
    print("=" * 60)

    try:
        ping_db()
    except Exception as exc:
        print(f"[FAIL] Cannot connect to MongoDB: {exc}")
        return 1

    db = get_db()
    collection = db["potholes"]

    query = {
        "$or": [
            {"isDemo": True},
            {"seedKey": {"$exists": True}},
            {"source": "seed_demo"},
        ]
    }

    total_before = collection.count_documents({})
    result = collection.delete_many(query)
    total_after = collection.count_documents({})

    print(f"[INFO] Deleted {result.deleted_count} seed/demo records.")
    print(f"[INFO] Total records in DB: {total_before} -> {total_after} (all real data)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(clean_seed_data())
