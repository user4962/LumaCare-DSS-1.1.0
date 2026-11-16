from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


Action = Literal["ALLOW", "ADJUST", "COMPLETE", "HOLD"]
SessionStatus = Literal["planned", "running", "completed", "stopped", "safety_hold"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ActorContext(BaseModel):
    actor_id: str = "anonymous-research-user"
    actor_role: str = "researcher"


class PatientBase(BaseModel):
    medical_record_number: str = Field(min_length=1, max_length=64)
    given_name: str = Field(min_length=1, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    administrative_sex: Literal["female", "male", "other", "unknown"] = "unknown"
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    notes: str | None = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    medical_record_number: str | None = Field(default=None, min_length=1, max_length=64)
    given_name: str | None = Field(default=None, min_length=1, max_length=100)
    family_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    administrative_sex: Literal["female", "male", "other", "unknown"] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notes: str | None = None


class PatientRead(PatientBase, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class DeviceBase(BaseModel):
    patient_id: str | None = None
    serial_number: str = Field(min_length=1, max_length=100)
    manufacturer: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    firmware_version: str = Field(min_length=1, max_length=50)
    wavelength_nm: float = Field(gt=0, le=2000)
    status: Literal["available", "assigned", "maintenance", "retired"] = "available"
    connectivity: Literal["online", "offline", "degraded"] = "offline"
    last_seen_at: datetime | None = None
    calibration_due_at: datetime | None = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    patient_id: str | None = None
    serial_number: str | None = Field(default=None, min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, min_length=1, max_length=100)
    model_name: str | None = Field(default=None, min_length=1, max_length=100)
    firmware_version: str | None = Field(default=None, min_length=1, max_length=50)
    wavelength_nm: float | None = Field(default=None, gt=0, le=2000)
    status: Literal["available", "assigned", "maintenance", "retired"] | None = None
    connectivity: Literal["online", "offline", "degraded"] | None = None
    last_seen_at: datetime | None = None
    calibration_due_at: datetime | None = None


class DeviceRead(DeviceBase, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class PrescriptionBase(BaseModel):
    patient_id: str
    device_id: str | None = None
    protocol_name: str = Field(min_length=1, max_length=160)
    indication_code: str = Field(default="research-demo", max_length=80)
    target_wavelength_nm: float = Field(gt=0, le=2000)
    wavelength_tolerance_nm: float = Field(default=5.0, gt=0, le=100)
    target_irradiance_mw_cm2: float = Field(gt=0, le=1000)
    target_dose_j_cm2: float = Field(gt=0, le=10000)
    max_session_dose_j_cm2: float | None = Field(default=None, gt=0, le=10000)
    max_duration_seconds: int = Field(gt=0, le=86400)
    max_skin_temperature_c: float = Field(ge=35, le=45)
    min_spo2_percent: float = Field(ge=80, le=100)
    irradiance_tolerance_percent: float = Field(default=10.0, gt=0, le=100)
    status: Literal["draft", "active", "paused", "completed", "cancelled"] = "active"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    instructions: str | None = None
    research_use_only: bool = True
    protocol_version: str = Field(default="demo-1.0", max_length=32)

    @field_validator("research_use_only")
    @classmethod
    def enforce_research_label(cls, value: bool) -> bool:
        if not value:
            raise ValueError("This demonstrator only supports research_use_only=true")
        return value


class PrescriptionCreate(PrescriptionBase):
    pass


class PrescriptionUpdate(BaseModel):
    device_id: str | None = None
    protocol_name: str | None = Field(default=None, min_length=1, max_length=160)
    indication_code: str | None = Field(default=None, max_length=80)
    target_wavelength_nm: float | None = Field(default=None, gt=0, le=2000)
    wavelength_tolerance_nm: float | None = Field(default=None, gt=0, le=100)
    target_irradiance_mw_cm2: float | None = Field(default=None, gt=0, le=1000)
    target_dose_j_cm2: float | None = Field(default=None, gt=0, le=10000)
    max_session_dose_j_cm2: float | None = Field(default=None, gt=0, le=10000)
    max_duration_seconds: int | None = Field(default=None, gt=0, le=86400)
    max_skin_temperature_c: float | None = Field(default=None, ge=35, le=45)
    min_spo2_percent: float | None = Field(default=None, ge=80, le=100)
    irradiance_tolerance_percent: float | None = Field(default=None, gt=0, le=100)
    status: Literal["draft", "active", "paused", "completed", "cancelled"] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    instructions: str | None = None
    protocol_version: str | None = Field(default=None, max_length=32)


class PrescriptionRead(PrescriptionBase, ORMModel):
    id: str
    max_session_dose_j_cm2: float
    valid_from: datetime
    created_at: datetime
    updated_at: datetime


class SessionCreate(BaseModel):
    patient_id: str
    device_id: str
    prescription_id: str = Field(validation_alias=AliasChoices("prescription_id", "protocol_id"))
    planned_duration_seconds: int | None = Field(default=None, gt=0, le=86400)
    simulator_seed: int = 20260713


class SessionStop(BaseModel):
    reason: str = Field(default="operator_request", min_length=1, max_length=160)


class SessionRead(ORMModel):
    id: str
    patient_id: str
    device_id: str
    prescription_id: str
    status: SessionStatus
    started_at: datetime | None
    ended_at: datetime | None
    stop_reason: str | None
    planned_duration_seconds: int
    delivered_dose_j_cm2: float
    simulator_seed: int
    active_scenario: str
    created_at: datetime
    updated_at: datetime


class TelemetryIn(BaseModel):
    sequence: int | None = Field(default=None, ge=0)
    captured_at: datetime | None = None
    wavelength_nm: float = Field(gt=0, le=2000)
    irradiance_mw_cm2: float = Field(ge=0, le=1000)
    cumulative_dose_j_cm2: float = Field(ge=0, le=10000)
    skin_temperature_c: float = Field(ge=0, le=80)
    spo2_percent: float = Field(ge=0, le=100)
    contact_detected: bool
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    signal_quality: float | None = Field(default=None, ge=0, le=1)
    raw_payload: dict[str, Any] | None = None


class TelemetryRead(ORMModel):
    id: int
    session_id: str
    sequence: int
    captured_at: datetime
    wavelength_nm: float
    irradiance_mw_cm2: float
    cumulative_dose_j_cm2: float
    skin_temperature_c: float
    spo2_percent: float
    contact_detected: bool
    battery_percent: float | None
    signal_quality: float | None


class DecisionRead(ORMModel):
    id: str
    session_id: str
    telemetry_sample_id: int
    created_at: datetime
    action: Action
    risk_level: Literal["low", "moderate", "high", "critical"]
    risk_score: float
    confidence: float
    explanation: str
    reason_codes: list[str]
    fired_rules: list[dict[str, Any]]
    recommended_irradiance_mw_cm2: float
    recommended_duration_seconds: float
    estimated_additional_dose_j_cm2: float
    engine_version: str
    protocol_version: str
    research_use_only: bool


class TelemetryDecisionResponse(BaseModel):
    telemetry: TelemetryRead
    decision: DecisionRead
    alerts_created: list[str]


class AlertRead(ORMModel):
    id: str
    session_id: str | None
    patient_id: str
    severity: Literal["info", "warning", "high", "critical"]
    code: str
    message: str
    status: Literal["open", "acknowledged"]
    created_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class AuditRead(ORMModel):
    id: str
    actor_id: str
    actor_role: str
    event_type: str
    entity_type: str
    entity_id: str
    occurred_at: datetime
    details: dict[str, Any]


class ScenarioRequest(BaseModel):
    scenario: Literal[
        "nominal", "temperature_rise", "spo2_drop", "contact_loss", "irradiance_spike"
    ]


class SimulatorStartRequest(BaseModel):
    scenario: Literal[
        "nominal", "temperature_rise", "spo2_drop", "contact_loss", "irradiance_spike"
    ] = "nominal"
    interval_seconds: float | None = Field(default=None, ge=0.05, le=60)
    max_samples: int | None = Field(default=None, gt=0, le=10000)


class SimulatorStatus(BaseModel):
    session_id: str
    running: bool
    scenario: str
    samples_generated: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]
    version: str
    timestamp: datetime


class MetaResponse(BaseModel):
    name: str
    version: str
    research_use_only: bool
    disclaimer: str
    authentication: str
    protocol_classification: str
    simulator_execution_model: str


class DashboardCounts(BaseModel):
    patients: int
    devices: int
    prescriptions: int
    sessions: int
    running_sessions: int
    open_alerts: int


class SessionSnapshot(BaseModel):
    session: SessionRead
    latest_telemetry: TelemetryRead | None
    latest_decision: DecisionRead | None


class SessionDetail(SessionSnapshot):
    telemetry: list[TelemetryRead]
    decisions: list[DecisionRead]
    alerts: list[AlertRead]


class DecisionEvaluateRequest(BaseModel):
    session_id: str
    telemetry: TelemetryIn


class DashboardSnapshot(BaseModel):
    generated_at: datetime
    counts: DashboardCounts
    active_sessions: list[SessionSnapshot]
    recent_alerts: list[AlertRead]
    research_use_only: bool = True
