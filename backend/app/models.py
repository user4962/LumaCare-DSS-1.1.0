from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, UTCDateTime, utcnow


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    medical_record_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    given_name: Mapped[str] = mapped_column(String(100))
    family_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    administrative_sex: Mapped[str] = mapped_column(String(24), default="unknown")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    devices: Mapped[list[Device]] = relationship(back_populates="patient")
    prescriptions: Mapped[list[Prescription]] = relationship(back_populates="patient")
    sessions: Mapped[list[TherapySession]] = relationship(back_populates="patient")


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    manufacturer: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(100))
    firmware_version: Mapped[str] = mapped_column(String(50))
    wavelength_nm: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="available", index=True)
    connectivity: Mapped[str] = mapped_column(String(32), default="offline")
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    calibration_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    patient: Mapped[Patient | None] = relationship(back_populates="devices")
    prescriptions: Mapped[list[Prescription]] = relationship(back_populates="device")
    sessions: Mapped[list[TherapySession]] = relationship(back_populates="device")


class Prescription(Base, TimestampMixin):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    protocol_name: Mapped[str] = mapped_column(String(160))
    indication_code: Mapped[str] = mapped_column(String(80), default="research-demo")
    target_wavelength_nm: Mapped[float] = mapped_column(Float)
    wavelength_tolerance_nm: Mapped[float] = mapped_column(Float, default=5.0)
    target_irradiance_mw_cm2: Mapped[float] = mapped_column(Float)
    target_dose_j_cm2: Mapped[float] = mapped_column(Float)
    max_session_dose_j_cm2: Mapped[float] = mapped_column(Float)
    max_duration_seconds: Mapped[int] = mapped_column(Integer)
    max_skin_temperature_c: Mapped[float] = mapped_column(Float)
    min_spo2_percent: Mapped[float] = mapped_column(Float)
    irradiance_tolerance_percent: Mapped[float] = mapped_column(Float, default=10.0)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_use_only: Mapped[bool] = mapped_column(Boolean, default=True)
    protocol_version: Mapped[str] = mapped_column(String(32), default="demo-1.0")

    patient: Mapped[Patient] = relationship(back_populates="prescriptions")
    device: Mapped[Device | None] = relationship(back_populates="prescriptions")
    sessions: Mapped[list[TherapySession]] = relationship(back_populates="prescription")


class TherapySession(Base, TimestampMixin):
    __tablename__ = "therapy_sessions"
    __table_args__ = (
        Index(
            "uq_running_session_device",
            "device_id",
            unique=True,
            sqlite_where=text("status = 'running'"),
        ),
        Index(
            "uq_running_session_patient",
            "patient_id",
            unique=True,
            sqlite_where=text("status = 'running'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), index=True
    )
    prescription_id: Mapped[str] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="planned", index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    planned_duration_seconds: Mapped[int] = mapped_column(Integer)
    delivered_dose_j_cm2: Mapped[float] = mapped_column(Float, default=0.0)
    simulator_seed: Mapped[int] = mapped_column(Integer, default=20260713)
    active_scenario: Mapped[str] = mapped_column(String(40), default="nominal")

    patient: Mapped[Patient] = relationship(back_populates="sessions")
    device: Mapped[Device] = relationship(back_populates="sessions")
    prescription: Mapped[Prescription] = relationship(back_populates="sessions")
    telemetry_samples: Mapped[list[TelemetrySample]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    decisions: Mapped[list[DecisionRecord]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(back_populates="session")


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_telemetry_session_sequence"),
        Index("ix_telemetry_session_captured", "session_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("therapy_sessions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    wavelength_nm: Mapped[float] = mapped_column(Float)
    irradiance_mw_cm2: Mapped[float] = mapped_column(Float)
    cumulative_dose_j_cm2: Mapped[float] = mapped_column(Float)
    skin_temperature_c: Mapped[float] = mapped_column(Float)
    spo2_percent: Mapped[float] = mapped_column(Float)
    contact_detected: Mapped[bool] = mapped_column(Boolean)
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    session: Mapped[TherapySession] = relationship(back_populates="telemetry_samples")
    decision: Mapped[DecisionRecord | None] = relationship(back_populates="telemetry_sample")


class DecisionRecord(Base):
    __tablename__ = "decision_records"
    __table_args__ = (Index("ix_decision_session_created", "session_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("therapy_sessions.id", ondelete="CASCADE"), index=True
    )
    telemetry_sample_id: Mapped[int] = mapped_column(
        ForeignKey("telemetry_samples.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    action: Mapped[str] = mapped_column(String(16), index=True)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    fired_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    recommended_irradiance_mw_cm2: Mapped[float] = mapped_column(Float)
    recommended_duration_seconds: Mapped[float] = mapped_column(Float)
    estimated_additional_dose_j_cm2: Mapped[float] = mapped_column(Float, default=0.0)
    engine_version: Mapped[str] = mapped_column(String(40), default="adapter-fallback-1.0")
    protocol_version: Mapped[str] = mapped_column(String(32))
    research_use_only: Mapped[bool] = mapped_column(Boolean, default=True)

    session: Mapped[TherapySession] = relationship(back_populates="decisions")
    telemetry_sample: Mapped[TelemetrySample] = relationship(back_populates="decision")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("therapy_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    severity: Mapped[str] = mapped_column(String(16), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    session: Mapped[TherapySession | None] = relationship(back_populates="alerts")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_occurred", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(String(100), default="anonymous-research-user")
    actor_role: Mapped[str] = mapped_column(String(80), default="researcher")
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
