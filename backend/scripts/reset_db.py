"""
PotholeAlert — Reset Database.

Purges all pothole records from the database, resetting the incident feed
to zero so the system starts fresh for live detection.
"""

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db import get_db, ping_db


def reset_database() -> int:
    print("=" * 60)
    print("PotholeAlert — Database Reset")
    print("=" * 60)

    try:
        ping_db()
    except Exception as exc:
        print(f"[FAIL] Cannot connect to MongoDB: {exc}")
        return 1

    db = get_db()
    collection = db["potholes"]

    total_before = collection.count_documents({})
    res = collection.delete_many({})
    total_after = collection.count_documents({})

    print(f"[INFO] Deleted {res.deleted_count} incident records.")
    print(f"[INFO] Total records in DB: {total_before} -> {total_after} (clean zero state)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(reset_database())
