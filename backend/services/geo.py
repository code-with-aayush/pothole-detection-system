"""
PotholeAlert — Geographic Utilities.

Provides Haversine distance calculation in meters between two GPS coordinates.
"""

import math


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate the great circle distance in meters between two points
    on the Earth's surface using the Haversine formula.
    """
    # Earth radius in meters
    r = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    # Clamp a to avoid numerical precision errors outside [0, 1]
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return r * c
