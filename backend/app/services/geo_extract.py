"""
Extract GPS coordinates from image EXIF metadata.

Works on:
  - JPEG photos with GPS EXIF (phones, DJI stills, any geo-tagged photo)
  - Any file supported by Pillow that carries standard EXIF GPS tags

Returns (lat, lon) in decimal degrees, or None if no GPS present / unreadable.
Positive lat = North, positive lon = East (WGS84 standard).

If an image has GPS, callers use synthesize_aoi(lat, lon) to build a small
AOI polygon centered on that point so the ingest pipeline can geo-reference
detections onto real-world coordinates instead of the default Bangalore AOI.
"""

from __future__ import annotations

import io
import logging
from math import cos, radians

log = logging.getLogger("astra.geo_extract")


def extract_gps(image_bytes: bytes) -> tuple[float, float] | None:
    """Parse EXIF and return (lat_deg, lon_deg) or None. Never raises."""
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
    except ImportError:
        return None

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Pillow 10+ deprecates _getexif() in favor of getexif()
            try:
                exif_data = img.getexif()
            except AttributeError:
                exif_data = img._getexif()  # type: ignore
            if not exif_data:
                return None

            # Find GPSInfo block
            gps_ifd = None
            for tag_id, value in exif_data.items():
                if TAGS.get(tag_id) == "GPSInfo":
                    # On Pillow 10+, GPSInfo may be a raw IFD pointer
                    if isinstance(value, int):
                        gps_ifd = exif_data.get_ifd(tag_id)
                    else:
                        gps_ifd = value
                    break
            if not gps_ifd:
                return None

            gps = {GPSTAGS.get(k, k): v for k, v in dict(gps_ifd).items()}

            lat_dms = gps.get("GPSLatitude")
            lat_ref = gps.get("GPSLatitudeRef")
            lon_dms = gps.get("GPSLongitude")
            lon_ref = gps.get("GPSLongitudeRef")
            if not (lat_dms and lon_dms and lat_ref and lon_ref):
                return None

            lat = _dms_to_decimal(lat_dms, lat_ref)
            lon = _dms_to_decimal(lon_dms, lon_ref)
            if lat is None or lon is None:
                return None
            # Sanity
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                return None
            return lat, lon
    except Exception as exc:
        log.debug("EXIF parse failed: %s", exc)
        return None


def _dms_to_decimal(dms, ref) -> float | None:
    """Convert (deg, min, sec) tuple (possibly rational numbers) + N/S/E/W ref to decimal."""
    try:
        d = float(dms[0])
        m = float(dms[1])
        s = float(dms[2])
        decimal = d + m / 60.0 + s / 3600.0
        if str(ref).strip().upper() in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def synthesize_aoi(lat: float, lon: float, size_m: float = 400.0) -> dict:
    """Build a square AOI of side `size_m` meters centered on (lat, lon),
    returned in the same dict shape as the AoiCorners schema.

    Uses equirectangular approximation — accurate to ~meters for sub-km boxes.
    """
    half = size_m / 2.0
    # 1 degree latitude ≈ 110,540 m; 1 degree longitude ≈ 111,320 * cos(lat) m
    dlat = half / 110540.0
    dlon = half / (111320.0 * max(0.01, cos(radians(lat))))
    return {
        "top_left":     [lat + dlat, lon - dlon],
        "top_right":    [lat + dlat, lon + dlon],
        "bottom_right": [lat - dlat, lon + dlon],
        "bottom_left":  [lat - dlat, lon - dlon],
    }
