"""
PotholeAlert — Authority Mapping Service.

PROTOTYPE NOTICE / DISCLAIMER:
This module uses a deterministic prototype mapping based on road classification rules
and geographic bounding boxes in the Delhi NCR region. 

IMPORTANT: Road ownership and jurisdictional maintenance responsibility cannot be
accurately determined from GPS coordinates alone. In a production municipal system,
official cadastral GIS road ownership datasets and polygon overlay queries (e.g. from
Delhi GeoSpatial Data Infrastructure / MCD / PWD / NHAI road asset registers) would
be strictly required.
"""

import json
from pathlib import Path
import re
from typing import Any, TypedDict

AUTHORITIES_FILE = Path(__file__).resolve().parent.parent / "data" / "authorities.json"


class AuthorityInfo(TypedDict):
    name: str
    shortName: str
    email: str


_cached_authorities: list[dict[str, Any]] | None = None


def load_authorities() -> list[dict[str, Any]]:
    """Load authority configurations from data/authorities.json."""
    global _cached_authorities
    if _cached_authorities is None:
        if not AUTHORITIES_FILE.exists():
            raise FileNotFoundError(f"Authorities file not found: {AUTHORITIES_FILE}")
        with open(AUTHORITIES_FILE, "r", encoding="utf-8") as f:
            _cached_authorities = json.load(f)
    return _cached_authorities


def get_authority_by_short_name(short_name: str) -> AuthorityInfo:
    """Retrieve an authority by shortName (MCD, PWD, NHAI, UNKNOWN)."""
    authorities = load_authorities()
    for auth in authorities:
        if auth.get("shortName") == short_name:
            return {
                "name": auth["name"],
                "shortName": auth["shortName"],
                "email": auth["email"],
            }
    return {
        "name": "Unassigned Road Authority",
        "shortName": "UNKNOWN",
        "email": "unassigned@example.com",
    }


def get_unknown_authority() -> AuthorityInfo:
    """Return fallback UNKNOWN authority."""
    return get_authority_by_short_name("UNKNOWN")


def get_authority_for_location(
    latitude: float | None,
    longitude: float | None,
    road_name: str | None = None,
    road_type: str | None = None,
) -> AuthorityInfo:
    """
    Determine the responsible road authority using hierarchical priority:

    Priority 1: Explicit road classification if roadName or roadType is provided
      - NH, National Highway, Expressway -> NHAI
      - PWD, Arterial, State Highway, Ring Road -> PWD
      - MCD, Colony, Ward -> MCD

    Priority 2: Specific geographic bounds before broad fallback bounds
      - MCD (Central / Urban Delhi Core: e.g. 28.6139, 77.2090)
      - PWD (NCT Arterial & Greater Delhi bounds)
      - NHAI (Outer Highway / Expressway corridors)

    Priority 3: Fallback UNKNOWN if coordinates are missing or out-of-bounds.
    """
    combined_road_str = f"{road_name or ''} {road_type or ''}".strip().lower()

    # Priority 1: Explicit road classification
    if combined_road_str:
        # Check NHAI patterns
        if re.search(r"\b(nh|nh-\d+|national\s*highway|expressway|ne-\d+)\b", combined_road_str):
            return get_authority_by_short_name("NHAI")

        # Check PWD patterns
        if re.search(r"\b(pwd|arterial|state\s*highway|ring\s*road|flyover)\b", combined_road_str):
            return get_authority_by_short_name("PWD")

        # Check MCD patterns
        if re.search(r"\b(mcd|ward|colony|sector|lane|gali|market)\b", combined_road_str):
            return get_authority_by_short_name("MCD")

    # If coordinates are missing, fallback to UNKNOWN
    if latitude is None or longitude is None:
        return get_unknown_authority()

    # Priority 2: Specific geographic bounds in deterministic order
    authorities = load_authorities()

    for auth in authorities:
        bounds = auth.get("bounds")
        if not bounds:
            continue

        min_lat = bounds.get("minLat", -90.0)
        max_lat = bounds.get("maxLat", 90.0)
        min_lng = bounds.get("minLng", -180.0)
        max_lng = bounds.get("maxLng", 180.0)

        if min_lat <= latitude <= max_lat and min_lng <= longitude <= max_lng:
            return {
                "name": auth["name"],
                "shortName": auth["shortName"],
                "email": auth["email"],
            }

    # Priority 3: Fallback
    return get_unknown_authority()
