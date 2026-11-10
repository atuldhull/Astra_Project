"""Local flat-earth helpers (accurate to well under 1 m over the few-km scale of a test scenario)."""

from __future__ import annotations

import math

M_PER_DEG_LAT = 111319.49079327357


def ne_to_latlon(lat0: float, lon0: float, north_m: float, east_m: float) -> tuple[float, float]:
    lat = lat0 + north_m / M_PER_DEG_LAT
    lon = lon0 + east_m / (M_PER_DEG_LAT * math.cos(math.radians(lat0)))
    return lat, lon


def latlon_to_ne(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    north = (lat - lat0) * M_PER_DEG_LAT
    east = (lon - lon0) * M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return north, east
