"""
Pixel → lat/lon for a rectangular AOI defined by its four image-corner lat/lons.

This is a bilinear interpolation in (lat, lon) over normalized (u, v) image
coordinates. It ignores Earth curvature and is accurate to ~tens of meters
for AOIs up to a few km — fine for a drone-altitude demo, not fine for
theater-scale satellite imagery.

For the demo: the operator uploads a clip with known AOI corners via
`aoi_corners` on POST /api/v1/ingest. No GPS telemetry required.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AoiCorners:
    """Corner lat/lons in (TL, TR, BR, BL) order, each as (lat, lon)."""
    top_left: tuple[float, float]
    top_right: tuple[float, float]
    bottom_right: tuple[float, float]
    bottom_left: tuple[float, float]


def pixel_to_latlon(
    px: float,
    py: float,
    img_w: float,
    img_h: float,
    corners: AoiCorners,
) -> tuple[float, float]:
    """Bilinearly interpolate (lat, lon) for a pixel (px, py) in an image of
    size (img_w, img_h) whose corners are labeled per AoiCorners."""
    if img_w <= 0 or img_h <= 0:
        raise ValueError("img_w and img_h must be positive")
    u = max(0.0, min(1.0, px / img_w))
    v = max(0.0, min(1.0, py / img_h))

    # Top edge interpolation
    top_lat = (1 - u) * corners.top_left[0] + u * corners.top_right[0]
    top_lon = (1 - u) * corners.top_left[1] + u * corners.top_right[1]
    # Bottom edge interpolation
    bot_lat = (1 - u) * corners.bottom_left[0] + u * corners.bottom_right[0]
    bot_lon = (1 - u) * corners.bottom_left[1] + u * corners.bottom_right[1]
    # Vertical blend
    lat = (1 - v) * top_lat + v * bot_lat
    lon = (1 - v) * top_lon + v * bot_lon
    return lat, lon


def haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    from math import asin, cos, radians, sin, sqrt
    R = 6371.0088
    lat1, lon1 = map(radians, p1)
    lat2, lon2 = map(radians, p2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))
