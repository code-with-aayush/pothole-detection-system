"""
PotholeAlert — Check Database Connection.

Runs a diagnostic connection check against MongoDB, reports URI and database name,
verifies ping, and checks or creates indexes on the 'potholes' collection.
"""

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db import ensure_indexes, get_mongodb_db_name, get_mongodb_uri, ping_db


def main() -> int:
    print("=" * 60)
    print("PotholeAlert — MongoDB Diagnostic Check")
    print("=" * 60)

    uri = get_mongodb_uri()
    db_name = get_mongodb_db_name()

    if not uri:
        print("[FAIL] MONGODB_URI is not set in environment or .env file.")
        print("       Please set MONGODB_URI=mongodb://localhost:27017")
        return 1

    # Mask credentials if present in URI
    masked_uri = uri
    if "@" in uri:
        prefix = uri.split("@")[0]
        schema_and_creds = prefix.split("://")
        if len(schema_and_creds) == 2:
            schema = schema_and_creds[0]
            host_part = uri.split("@")[1]
            masked_uri = f"{schema}://***:***@{host_part}"

    print(f"Target URI      : {masked_uri}")
    print(f"Target Database : {db_name}")

    try:
        print("Pinging MongoDB server...")
        res = ping_db()
        print(f"[OK] Successfully connected to MongoDB! Status: {res['status']}")

        print("Ensuring collection indexes...")
        created_indexes = ensure_indexes()
        print(f"[OK] Indexes configured on 'potholes' collection:")
        for idx in created_indexes:
            print(f"     - {idx}")

        print("=" * 60)
        print("[SUCCESS] MongoDB check passed.")
        print("=" * 60)
        return 0

    except Exception as exc:
        print(f"[FAIL] MongoDB connection failed: {exc}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
