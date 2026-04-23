from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Detections ────────────────────────────────────────────────────────────

class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_id: int
    frame_index: int
    frame_timestamp_ms: int
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    lat: float | None = None
    lon: float | None = None
    track_id: int | None = None
    created_at: datetime


# ── Alerts ────────────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    class_term: float
    proximity_term: float
    motion_term: float
    count_term: float
    confidence_term: float
    distance_km: float | None = None
    nearest_asset: str | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_id: int
    detection_id: int
    threat_score: float
    score_breakdown: ScoreBreakdown
    status: Literal["pending", "confirmed", "rejected", "escalated"]
    operator_id: str | None
    narrative: str | None
    created_at: datetime
    updated_at: datetime


class AlertActionIn(BaseModel):
    action: Literal["confirm", "reject", "reclassify", "escalate"]
    operator_id: str = Field(..., min_length=1, max_length=64)
    new_class_id: int | None = None
    reason: str | None = None


class WeightsIn(BaseModel):
    w_class: float = Field(0.35, ge=0.0, le=1.0)
    w_prox: float = Field(0.25, ge=0.0, le=1.0)
    w_motion: float = Field(0.20, ge=0.0, le=1.0)
    w_count: float = Field(0.10, ge=0.0, le=1.0)
    w_conf: float = Field(0.10, ge=0.0, le=1.0)
    class_weights: dict[str, float] | None = None
    operator_id: str = Field(..., min_length=1, max_length=64)


# ── Missions / Ingest ─────────────────────────────────────────────────────

class AoiCorners(BaseModel):
    """Four corner lat/lons of the imagery frame, in TL-TR-BR-BL order."""
    top_left: tuple[float, float]
    top_right: tuple[float, float]
    bottom_right: tuple[float, float]
    bottom_left: tuple[float, float]


class MissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_path: str
    created_at: datetime


# ── Audit ─────────────────────────────────────────────────────────────────

class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    operator_id: str | None
    mission_id: int | None
    alert_id: int | None
    payload_json: dict | None
    created_at: datetime
