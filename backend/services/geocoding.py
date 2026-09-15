"""
PotholeAlert — Reverse Geocoding Service.

Queries OpenStreetMap Nominatim reverse geocoding API to resolve readable street
addresses from GPS coordinates. Includes in-memory coordinate caching and graceful
fallback on network errors or timeouts.

NOTE: This service is solely used for human-readable street addresses. Authority
assignment is independently handled by the deterministic authority mapping service.
"""

import logging
from typing import Any
import httpx

logger = logging.getLogger("potholealert.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "PotholeAlert-Internship-Project/1.0 (contact: demo-alert@potholealert.local)"
REQUEST_TIMEOUT_SECONDS = 3.0

# In-memory coordinate cache: key = "lat_4dec,lon_4dec" (~11m precision)
_GEOCODE_CACHE: dict[str, str] = {}


def _get_cache_key(latitude: float, longitude: float) -> str:
    """Round coordinates to 4 decimal places (~11 meters) for spatial caching."""
    return f"{round(latitude, 4):.4f},{round(longitude, 4):.4f}"


def format_address_from_nominatim(data: dict[str, Any]) -> str:
    """Format a clean, concise address from Nominatim response data."""
    address = data.get("address", {})
    parts: list[str] = []

    # Road / Street
    road = address.get("road") or address.get("pedestrian") or address.get("street")
    if road:
        parts.append(road)

    # Suburb / Neighbourhood / Locality
    suburb = (
        address.get("suburb")
        or address.get("neighbourhood")
        or address.get("residential")
        or address.get("commercial")
    )
    if suburb and suburb not in parts:
        parts.append(suburb)

    # City district / City
    city = address.get("city") or address.get("town") or address.get("city_district") or address.get("state_district")
    if city and city not in parts:
        parts.append(city)

    # Postal code
    postcode = address.get("postcode")
    if postcode:
        parts.append(postcode)

    if parts:
        return ", ".join(parts)

    # Fallback to full display_name if address dict components are sparse
    display_name = data.get("display_name", "")
    if display_name:
        # Take first 3 segments of comma-separated display name
        segments = [s.strip() for s in display_name.split(",") if s.strip()]
        return ", ".join(segments[:3])

    return "Address unavailable"


def reverse_geocode(latitude: float | None, longitude: float | None) -> str:
    """
    Resolve human-readable street address for given latitude and longitude.
    Uses in-memory cache to prevent redundant HTTP requests.
    Returns 'Address unavailable' on timeout or failure without raising exceptions.
    """
    if latitude is None or longitude is None:
        return ""

    cache_key = _get_cache_key(latitude, longitude)
    if cache_key in _GEOCODE_CACHE:
        logger.debug("Geocoding cache hit for %s: %s", cache_key, _GEOCODE_CACHE[cache_key])
        return _GEOCODE_CACHE[cache_key]

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 18,
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.get(NOMINATIM_URL, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                address = format_address_from_nominatim(data)
                _GEOCODE_CACHE[cache_key] = address
                logger.info("Geocoded %s -> %s", cache_key, address)
                return address
            else:
                logger.warning(
                    "Nominatim geocoding returned HTTP %d for %s",
                    response.status_code,
                    cache_key,
                )
    except Exception as exc:
        logger.warning("Reverse geocoding failed for (%s, %s): %s", latitude, longitude, exc)

    fallback = "Address unavailable"
    _GEOCODE_CACHE[cache_key] = fallback
    return fallback
