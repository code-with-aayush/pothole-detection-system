"""
PotholeAlert — Database Connection & Lifecycle Management.

Provides MongoDB connectivity via PyMongo with safe initialization,
ping verification, and collection index creation.
"""

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError, ServerSelectionTimeoutError

logger = logging.getLogger("potholealert.db")

# Automatically load environment variables from backend/.env or root .env
env_paths = [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()

DEFAULT_DB_NAME = "pothole_alert"

_client: MongoClient[dict[str, Any]] | None = None


def get_mongodb_uri() -> str:
    """Retrieve MONGODB_URI from environment variables."""
    uri = os.getenv("MONGODB_URI", "").strip()
    return uri


def get_mongodb_db_name() -> str:
    """Retrieve MONGODB_DB_NAME from environment variables, fallback to default."""
    db_name = os.getenv("MONGODB_DB_NAME", "").strip()
    return db_name if db_name else DEFAULT_DB_NAME


def get_client() -> MongoClient[dict[str, Any]]:
    """
    Get or initialize the MongoClient instance.
    Does not crash on import if database is unavailable.
    Raises ValueError if MONGODB_URI is not set.
    """
    global _client
    if _client is None:
        uri = get_mongodb_uri()
        if not uri:
            raise ValueError(
                "MONGODB_URI environment variable is not set. "
                "Set MONGODB_URI=mongodb://localhost:27017 in your .env file."
            )
        try:
            _client = MongoClient(
                uri,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
            )
        except (ConfigurationError, Exception) as exc:
            raise ValueError(f"Invalid MONGODB_URI '{uri}': {exc}") from exc
    return _client


def get_db() -> Database[dict[str, Any]]:
    """Get the active MongoDB database."""
    client = get_client()
    db_name = get_mongodb_db_name()
    return client[db_name]


def ping_db() -> dict[str, Any]:
    """
    Ping the database to verify connectivity.
    Returns status dict if successful, raises ConnectionFailure/ServerSelectionTimeoutError on failure.
    """
    client = get_client()
    # admin.command("ping") will trigger server selection
    client.admin.command("ping")
    db_name = get_mongodb_db_name()
    return {
        "status": "connected",
        "database": db_name,
    }


def is_mongodb_available(timeout_ms: int = 2000) -> bool:
    """
    Fast boolean check for MongoDB reachability.
    Returns False without throwing if the database is unreachable or URI is missing.
    """
    uri = get_mongodb_uri()
    if not uri:
        return False
    try:
        # Create a transient lightweight client with custom short timeout
        test_client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
        test_client.admin.command("ping")
        test_client.close()
        return True
    except Exception as exc:
        logger.debug("MongoDB reachability check failed: %s", exc)
        return False



def ensure_indexes() -> list[str]:
    """
    Ensure required indexes on the 'potholes' collection:
    - detectedAt (descending)
    - status (ascending)
    - severity (ascending)
    - latitude, longitude (compound)
    """
    db = get_db()
    collection = db["potholes"]

    indexes = [
        IndexModel([("detectedAt", DESCENDING)], name="idx_detectedAt"),
        IndexModel([("status", ASCENDING)], name="idx_status"),
        IndexModel([("severity", ASCENDING)], name="idx_severity"),
        IndexModel(
            [("latitude", ASCENDING), ("longitude", ASCENDING)],
            name="idx_lat_lng",
            sparse=True,
        ),
    ]

    created = collection.create_indexes(indexes)
    logger.info("Ensured indexes on 'potholes': %s", created)
    return created


def close_connection() -> None:
    """Close the active MongoClient instance."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
