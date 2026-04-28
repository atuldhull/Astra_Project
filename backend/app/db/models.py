from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AlertStatus(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    ENGAGED = "engaged"   # Round-2: escalated + 2 distinct operator confirmations


class AuditEventType(str, PyEnum):
    INGEST_STARTED = "ingest_started"
    INGEST_COMPLETED = "ingest_completed"
    ALERT_CONFIRMED = "alert_confirmed"
    ALERT_REJECTED = "alert_rejected"
    ALERT_RECLASSIFIED = "alert_reclassified"
    ALERT_ESCALATED = "alert_escalated"
    ALERT_CONFIRMATION = "alert_confirmation"   # Round-2: dual-control partial confirm
    ALERT_ENGAGED = "alert_engaged"              # Round-2: dual-control complete (2 ops)
    WEIGHTS_CHANGED = "weights_changed"


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    source_path: Mapped[str] = mapped_column(String(512))
    aoi_corners_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Round-3 soft-delete: NULL = active, set timestamp = soft-deleted.
    # Hard-deleting would orphan detections/alerts and break the audit trail.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    detections: Mapped[list[Detection]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    alerts: Mapped[list[Alert]] = relationship(back_populates="mission", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    frame_index: Mapped[int] = mapped_column(Integer)
    frame_timestamp_ms: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int] = mapped_column(Integer, index=True)
    class_name: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    # pixel bbox
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    # geo (nullable — only set when AOI corners known)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    # track membership (nullable — set by tracker)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Round-2 extras: JSON-encoded auxiliary inference output. Today this carries
    # the MAR20 cascade result ({"airframe": "F-22", "airframe_confidence": 0.84})
    # and SAM OOD score; new producers can add keys without further migrations.
    extras_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mission: Mapped[Mission] = relationship(back_populates="detections")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id", ondelete="CASCADE"))
    threat_score: Mapped[float] = mapped_column(Float, index=True)
    score_breakdown_json: Mapped[str] = mapped_column(Text)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, values_callable=lambda e: [m.value for m in e]),
        default=AlertStatus.PENDING,
        index=True,
    )
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Round-2 dual-control: JSON list of {"operator_id": str, "ts": iso}
    # Required: 2 distinct operator IDs to transition ESCALATED → ENGAGED.
    confirmations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    mission: Mapped[Mission] = relationship(back_populates="alerts")


class ChatMessage(Base):
    """Persistent commander Q&A thread, optionally scoped to a mission.

    role='user' for operator turns, 'astra' for backend replies. Free-form
    notes posted via POST /chat/note also land here with role='user' and
    source='note' so the briefing can surface them under "OPERATOR NOTES".
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int | None] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), index=True)        # 'user' | 'astra'
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 'rule'|'llm'|'error'|'note'
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AuditEvent(Base):
    """Append-only log. Never UPDATE or DELETE rows here.

    Round-2 tamper-evident upgrade: each row carries a SHA-256 hash that
    chains to the previous row's hash. Any retroactive edit invalidates
    every subsequent hash — verifiable by re-walking the chain.
    """
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mission_id: Mapped[int | None] = mapped_column(ForeignKey("missions.id", ondelete="SET NULL"), nullable=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Round-2 chained hash. Computed in app.services.audit.log_event() as
    # SHA-256 of (prev_hash || canonical_json(this row's payload)). Genesis
    # row's prev_hash is "0"*64.
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
