from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db, utcnow
from ..models import (
    Alert,
    AuditEvent,
    DecisionRecord,
    Device,
    Patient,
    Prescription,
    TelemetrySample,
    TherapySession,
)
from ..schemas import (
    ActorContext,
    AlertRead,
    AuditRead,
    DashboardCounts,
    DashboardSnapshot,
    DecisionEvaluateRequest,
    DecisionRead,
    DeviceCreate,
    DeviceRead,
    DeviceUpdate,
    HealthResponse,
    MetaResponse,
    PatientCreate,
    PatientRead,
    PatientUpdate,
    PrescriptionCreate,
    PrescriptionRead,
    PrescriptionUpdate,
    ScenarioRequest,
    SessionCreate,
    SessionDetail,
    SessionRead,
    SessionSnapshot,
    SessionStop,
    SimulatorStartRequest,
    SimulatorStatus,
    TelemetryDecisionResponse,
    TelemetryIn,
    TelemetryRead,
)
from ..services.audit import add_audit_event
from ..services.fhir import build_all_bundle, build_patient_bundle, build_session_bundle
from ..services.presentation import websocket_telemetry_event
from ..services.readiness import assess_readiness, validate_prescription_interval
from ..services.telemetry import IngestionError, ingest_telemetry
from .dependencies import get_actor


router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[ActorContext, Depends(get_actor)]
ModelT = TypeVar("ModelT")


def _not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{resource} not found")


def _get(db: Session, model: type[ModelT], entity_id: str, resource: str) -> ModelT:
    entity = db.get(model, entity_id)
    if entity is None:
        raise _not_found(resource)
    return entity


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_message) from exc


def _flush(db: Session, conflict_message: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_message) from exc


def _latest_telemetry(db: Session, session_id: str) -> TelemetrySample | None:
    return db.scalar(
        select(TelemetrySample)
        .where(TelemetrySample.session_id == session_id)
        .order_by(desc(TelemetrySample.sequence))
        .limit(1)
    )


def _latest_decision(db: Session, session_id: str) -> DecisionRecord | None:
    return db.scalar(
        select(DecisionRecord)
        .where(DecisionRecord.session_id == session_id)
        .order_by(desc(DecisionRecord.created_at))
        .limit(1)
    )


def _session_snapshot(db: Session, session: TherapySession) -> SessionSnapshot:
    return SessionSnapshot(
        session=SessionRead.model_validate(session),
        latest_telemetry=(
            TelemetryRead.model_validate(item)
            if (item := _latest_telemetry(db, session.id)) is not None
            else None
        ),
        latest_decision=(
            DecisionRead.model_validate(item)
            if (item := _latest_decision(db, session.id)) is not None
            else None
        ),
    )


def _raise_if_not_ready(issues: list[Any]) -> None:
    if issues:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SESSION_NOT_READY",
                "issues": [issue.as_detail() for issue in issues],
            },
        )


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(request: Request, db: Db) -> HealthResponse:
    db.execute(text("SELECT 1"))
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok", database="ok", version=settings.app_version, timestamp=utcnow()
    )


@router.get("/meta", response_model=MetaResponse, tags=["system"])
def metadata(request: Request) -> MetaResponse:
    settings: Settings = request.app.state.settings
    return MetaResponse(
        name=settings.app_name,
        version=settings.app_version,
        research_use_only=True,
        disclaimer=(
            "Research and software-demonstration system. Protocol thresholds, decisions, alerts, "
            "simulated data, and exports are not validated for diagnosis or treatment."
        ),
        authentication=(
            "X-Actor and X-Role are audit labels only; this demonstrator does not implement "
            "production authentication or authorization."
        ),
        protocol_classification="research-demo",
        simulator_execution_model=(
            "single worker enforced by an exclusive lock per SQLite database"
        ),
    )


def _dashboard(db: Session) -> DashboardSnapshot:
    running = list(
        db.scalars(
            select(TherapySession)
            .where(TherapySession.status == "running")
            .order_by(desc(TherapySession.started_at))
        )
    )
    recent_alerts = list(db.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(10)))
    return DashboardSnapshot(
        generated_at=utcnow(),
        counts=DashboardCounts(
            patients=db.scalar(select(func.count()).select_from(Patient)) or 0,
            devices=db.scalar(select(func.count()).select_from(Device)) or 0,
            prescriptions=db.scalar(select(func.count()).select_from(Prescription)) or 0,
            sessions=db.scalar(select(func.count()).select_from(TherapySession)) or 0,
            running_sessions=len(running),
            open_alerts=(
                db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "open")) or 0
            ),
        ),
        active_sessions=[_session_snapshot(db, item) for item in running],
        recent_alerts=[AlertRead.model_validate(item) for item in recent_alerts],
    )


@router.get("/dashboard", response_model=DashboardSnapshot, tags=["dashboard"])
def dashboard(db: Db) -> DashboardSnapshot:
    return _dashboard(db)


@router.get("/overview", response_model=DashboardSnapshot, tags=["dashboard"])
def overview(db: Db) -> DashboardSnapshot:
    return _dashboard(db)


@router.get("/patients", response_model=list[PatientRead], tags=["patients"])
def list_patients(
    db: Db,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.family_name, Patient.given_name).offset(offset).limit(limit)))


@router.post(
    "/patients", response_model=PatientRead, status_code=status.HTTP_201_CREATED, tags=["patients"]
)
def create_patient(payload: PatientCreate, db: Db, actor: Actor) -> Patient:
    patient = Patient(**payload.model_dump())
    db.add(patient)
    _flush(db, "A patient with this medical record number already exists")
    add_audit_event(db, actor, event_type="patient.created", entity_type="patient", entity_id=patient.id)
    _commit(db, "A patient with this medical record number already exists")
    db.refresh(patient)
    return patient


@router.get("/patients/{patient_id}", response_model=PatientRead, tags=["patients"])
def get_patient(patient_id: str, db: Db) -> Patient:
    return _get(db, Patient, patient_id, "Patient")


@router.patch("/patients/{patient_id}", response_model=PatientRead, tags=["patients"])
def update_patient(patient_id: str, payload: PatientUpdate, db: Db, actor: Actor) -> Patient:
    patient = _get(db, Patient, patient_id, "Patient")
    changed = payload.model_dump(exclude_unset=True)
    for key, value in changed.items():
        setattr(patient, key, value)
    add_audit_event(
        db, actor, event_type="patient.updated", entity_type="patient", entity_id=patient.id,
        details={"fields": sorted(changed)},
    )
    _commit(db, "Patient update conflicts with an existing record")
    db.refresh(patient)
    return patient


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["patients"])
def delete_patient(patient_id: str, db: Db, actor: Actor) -> Response:
    patient = _get(db, Patient, patient_id, "Patient")
    add_audit_event(db, actor, event_type="patient.deleted", entity_type="patient", entity_id=patient.id)
    db.delete(patient)
    _commit(db, "Patient cannot be deleted while related records exist")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices", response_model=list[DeviceRead], tags=["devices"])
def list_devices(
    db: Db,
    patient_id: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Device]:
    query = select(Device)
    if patient_id:
        query = query.where(Device.patient_id == patient_id)
    if status_filter:
        query = query.where(Device.status == status_filter)
    return list(db.scalars(query.order_by(Device.serial_number).offset(offset).limit(limit)))


@router.post(
    "/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED, tags=["devices"]
)
def create_device(payload: DeviceCreate, db: Db, actor: Actor) -> Device:
    if payload.patient_id:
        _get(db, Patient, payload.patient_id, "Patient")
    device = Device(**payload.model_dump())
    db.add(device)
    _flush(db, "A device with this serial number already exists")
    add_audit_event(db, actor, event_type="device.created", entity_type="device", entity_id=device.id)
    _commit(db, "A device with this serial number already exists")
    db.refresh(device)
    return device


@router.get("/devices/{device_id}", response_model=DeviceRead, tags=["devices"])
def get_device(device_id: str, db: Db) -> Device:
    return _get(db, Device, device_id, "Device")


@router.patch("/devices/{device_id}", response_model=DeviceRead, tags=["devices"])
def update_device(device_id: str, payload: DeviceUpdate, db: Db, actor: Actor) -> Device:
    device = _get(db, Device, device_id, "Device")
    changed = payload.model_dump(exclude_unset=True)
    if "patient_id" in changed and changed["patient_id"]:
        _get(db, Patient, changed["patient_id"], "Patient")
    for key, value in changed.items():
        setattr(device, key, value)
    add_audit_event(
        db, actor, event_type="device.updated", entity_type="device", entity_id=device.id,
        details={"fields": sorted(changed)},
    )
    _commit(db, "Device update conflicts with an existing record")
    db.refresh(device)
    return device


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["devices"])
def delete_device(device_id: str, db: Db, actor: Actor) -> Response:
    device = _get(db, Device, device_id, "Device")
    add_audit_event(db, actor, event_type="device.deleted", entity_type="device", entity_id=device.id)
    db.delete(device)
    _commit(db, "Device cannot be deleted while related records exist")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _prescription_query(patient_id: str | None, active_only: bool) -> Any:
    query = select(Prescription)
    if patient_id:
        query = query.where(Prescription.patient_id == patient_id)
    if active_only:
        query = query.where(Prescription.status == "active")
    return query.order_by(desc(Prescription.created_at))


@router.get("/prescriptions", response_model=list[PrescriptionRead], tags=["prescriptions"])
def list_prescriptions(
    db: Db,
    patient_id: str | None = None,
    active_only: bool = False,
) -> list[Prescription]:
    return list(db.scalars(_prescription_query(patient_id, active_only)))


@router.get("/protocols", response_model=list[PrescriptionRead], tags=["prescriptions"])
def list_protocols(
    db: Db,
    patient_id: str | None = None,
    active_only: bool = False,
) -> list[Prescription]:
    return list(db.scalars(_prescription_query(patient_id, active_only)))


@router.post(
    "/prescriptions",
    response_model=PrescriptionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["prescriptions"],
)
def create_prescription(payload: PrescriptionCreate, db: Db, actor: Actor) -> Prescription:
    _get(db, Patient, payload.patient_id, "Patient")
    if payload.device_id:
        device = _get(db, Device, payload.device_id, "Device")
        if device.patient_id not in (None, payload.patient_id):
            raise HTTPException(status_code=409, detail="Device is assigned to another patient")
    values = payload.model_dump(exclude_none=True)
    effective_valid_from = payload.valid_from or utcnow()
    interval_issue = validate_prescription_interval(effective_valid_from, payload.valid_until)
    if interval_issue:
        raise HTTPException(status_code=422, detail=interval_issue.as_detail())
    values["valid_from"] = effective_valid_from
    maximum_dose = values.get("max_session_dose_j_cm2")
    if maximum_dose is None:
        values["max_session_dose_j_cm2"] = round(payload.target_dose_j_cm2 * 1.25, 6)
    elif maximum_dose < payload.target_dose_j_cm2:
        raise HTTPException(status_code=422, detail="Dose ceiling must equal or exceed target dose")
    prescription = Prescription(**values)
    db.add(prescription)
    _flush(db, "Prescription could not be created")
    add_audit_event(
        db, actor, event_type="prescription.created", entity_type="prescription",
        entity_id=prescription.id, details={"research_use_only": True},
    )
    _commit(db, "Prescription could not be created")
    db.refresh(prescription)
    return prescription


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionRead, tags=["prescriptions"])
def get_prescription(prescription_id: str, db: Db) -> Prescription:
    return _get(db, Prescription, prescription_id, "Prescription")


@router.get("/protocols/{prescription_id}", response_model=PrescriptionRead, tags=["prescriptions"])
def get_protocol(prescription_id: str, db: Db) -> Prescription:
    return _get(db, Prescription, prescription_id, "Prescription")


@router.patch("/prescriptions/{prescription_id}", response_model=PrescriptionRead, tags=["prescriptions"])
def update_prescription(
    prescription_id: str, payload: PrescriptionUpdate, db: Db, actor: Actor
) -> Prescription:
    prescription = _get(db, Prescription, prescription_id, "Prescription")
    changed = payload.model_dump(exclude_unset=True)
    if changed.get("max_session_dose_j_cm2") is None:
        changed.pop("max_session_dose_j_cm2", None)
    effective_target = changed.get("target_dose_j_cm2", prescription.target_dose_j_cm2)
    effective_maximum = changed.get(
        "max_session_dose_j_cm2", prescription.max_session_dose_j_cm2
    )
    if effective_maximum < effective_target:
        raise HTTPException(status_code=422, detail="Dose ceiling must equal or exceed target dose")
    effective_valid_from = changed.get("valid_from", prescription.valid_from)
    effective_valid_until = changed.get("valid_until", prescription.valid_until)
    if effective_valid_from is None:
        raise HTTPException(status_code=422, detail="valid_from cannot be null")
    interval_issue = validate_prescription_interval(effective_valid_from, effective_valid_until)
    if interval_issue:
        raise HTTPException(status_code=422, detail=interval_issue.as_detail())
    if changed.get("device_id"):
        device = _get(db, Device, changed["device_id"], "Device")
        if device.patient_id not in (None, prescription.patient_id):
            raise HTTPException(status_code=409, detail="Device is assigned to another patient")
    for key, value in changed.items():
        setattr(prescription, key, value)
    add_audit_event(
        db, actor, event_type="prescription.updated", entity_type="prescription",
        entity_id=prescription.id, details={"fields": sorted(changed)},
    )
    _commit(db, "Prescription update conflicts with existing data")
    db.refresh(prescription)
    return prescription


@router.delete(
    "/prescriptions/{prescription_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["prescriptions"]
)
def delete_prescription(prescription_id: str, db: Db, actor: Actor) -> Response:
    prescription = _get(db, Prescription, prescription_id, "Prescription")
    add_audit_event(
        db, actor, event_type="prescription.deleted", entity_type="prescription",
        entity_id=prescription.id,
    )
    db.delete(prescription)
    _commit(db, "Prescription cannot be deleted while sessions reference it")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions", response_model=list[SessionRead], tags=["sessions"])
def list_sessions(
    db: Db,
    patient_id: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TherapySession]:
    query = select(TherapySession)
    if patient_id:
        query = query.where(TherapySession.patient_id == patient_id)
    if status_filter:
        query = query.where(TherapySession.status == status_filter)
    return list(db.scalars(query.order_by(desc(TherapySession.created_at)).limit(limit)))


@router.post(
    "/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED, tags=["sessions"]
)
def create_session(payload: SessionCreate, db: Db, actor: Actor) -> TherapySession:
    patient = _get(db, Patient, payload.patient_id, "Patient")
    device = _get(db, Device, payload.device_id, "Device")
    prescription = _get(db, Prescription, payload.prescription_id, "Prescription")
    _raise_if_not_ready(
        assess_readiness(
            db, patient=patient, device=device, prescription=prescription
        )
    )
    planned_duration = payload.planned_duration_seconds or prescription.max_duration_seconds
    if planned_duration > prescription.max_duration_seconds:
        raise HTTPException(
            status_code=422, detail="Planned duration exceeds the research protocol maximum"
        )
    session = TherapySession(
        patient_id=patient.id,
        device_id=device.id,
        prescription_id=prescription.id,
        planned_duration_seconds=planned_duration,
        simulator_seed=payload.simulator_seed,
    )
    db.add(session)
    _flush(db, "Session could not be created")
    add_audit_event(
        db, actor, event_type="session.created", entity_type="therapy_session",
        entity_id=session.id, details={"research_use_only": True},
    )
    _commit(db, "Session could not be created")
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=SessionDetail, tags=["sessions"])
def get_session(session_id: str, db: Db, history_limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> SessionDetail:
    session = _get(db, TherapySession, session_id, "Session")
    telemetry = list(
        db.scalars(
            select(TelemetrySample).where(TelemetrySample.session_id == session.id)
            .order_by(desc(TelemetrySample.sequence)).limit(history_limit)
        )
    )
    decisions = list(
        db.scalars(
            select(DecisionRecord).where(DecisionRecord.session_id == session.id)
            .order_by(desc(DecisionRecord.created_at)).limit(history_limit)
        )
    )
    alerts = list(
        db.scalars(select(Alert).where(Alert.session_id == session.id).order_by(desc(Alert.created_at)))
    )
    snapshot = _session_snapshot(db, session)
    return SessionDetail(
        **snapshot.model_dump(),
        telemetry=[TelemetryRead.model_validate(item) for item in reversed(telemetry)],
        decisions=[DecisionRead.model_validate(item) for item in reversed(decisions)],
        alerts=[AlertRead.model_validate(item) for item in alerts],
    )


@router.post("/sessions/{session_id}/start", response_model=SessionRead, tags=["sessions"])
def start_session(session_id: str, db: Db, actor: Actor) -> TherapySession:
    session = _get(db, TherapySession, session_id, "Session")
    if session.status != "planned":
        raise HTTPException(status_code=409, detail="Only a planned session can be started")
    patient = _get(db, Patient, session.patient_id, "Patient")
    device = _get(db, Device, session.device_id, "Device")
    prescription = _get(db, Prescription, session.prescription_id, "Prescription")
    _raise_if_not_ready(
        assess_readiness(
            db,
            patient=patient,
            device=device,
            prescription=prescription,
            exclude_session_id=session.id,
        )
    )
    session.status = "running"
    session.started_at = utcnow()
    device.status = "assigned"
    add_audit_event(
        db, actor, event_type="session.started", entity_type="therapy_session", entity_id=session.id
    )
    _commit(db, "Another running session already uses this patient or device")
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/stop", response_model=SessionRead, tags=["sessions"])
async def stop_session(session_id: str, payload: SessionStop, request: Request, db: Db, actor: Actor) -> TherapySession:
    session = _get(db, TherapySession, session_id, "Session")
    if session.status == "safety_hold":
        raise HTTPException(
            status_code=409,
            detail="A safety-held session retains its causal state and cannot be stopped",
        )
    if session.status in {"completed", "stopped"}:
        raise HTTPException(status_code=409, detail="Session is already terminal")
    await request.app.state.simulator.stop(session_id)
    session.status = "stopped"
    session.ended_at = utcnow()
    session.stop_reason = payload.reason
    add_audit_event(
        db, actor, event_type="session.stopped", entity_type="therapy_session", entity_id=session.id,
        details={"reason": payload.reason},
    )
    db.commit()
    db.refresh(session)
    return session


async def _ingest_and_broadcast(
    request: Request,
    db: Session,
    session: TherapySession,
    payload: TelemetryIn,
    actor: ActorContext,
) -> TelemetryDecisionResponse:
    try:
        result = ingest_telemetry(
            db,
            session=session,
            payload=payload,
            actor=actor,
            adapter=request.app.state.decision_adapter,
            future_tolerance_seconds=request.app.state.settings.telemetry_future_tolerance_seconds,
        )
    except IngestionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Telemetry sequence already exists") from exc
    await request.app.state.connections.broadcast(session.id, websocket_telemetry_event(result))
    return TelemetryDecisionResponse(
        telemetry=TelemetryRead.model_validate(result.telemetry),
        decision=DecisionRead.model_validate(result.decision),
        alerts_created=[alert.id for alert in result.alerts],
    )


@router.post(
    "/sessions/{session_id}/telemetry",
    response_model=TelemetryDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["telemetry"],
)
async def create_telemetry(
    session_id: str, payload: TelemetryIn, request: Request, db: Db, actor: Actor
) -> TelemetryDecisionResponse:
    session = _get(db, TherapySession, session_id, "Session")
    return await _ingest_and_broadcast(request, db, session, payload, actor)


@router.get("/sessions/{session_id}/telemetry", response_model=list[TelemetryRead], tags=["telemetry"])
def list_telemetry(
    session_id: str, db: Db, limit: Annotated[int, Query(ge=1, le=5000)] = 500
) -> list[TelemetrySample]:
    _get(db, TherapySession, session_id, "Session")
    return list(
        db.scalars(
            select(TelemetrySample).where(TelemetrySample.session_id == session_id)
            .order_by(desc(TelemetrySample.sequence)).limit(limit)
        )
    )[::-1]


@router.post("/decision/evaluate", response_model=TelemetryDecisionResponse, tags=["decisions"])
async def evaluate_decision(
    payload: DecisionEvaluateRequest, request: Request, db: Db, actor: Actor
) -> TelemetryDecisionResponse:
    session = _get(db, TherapySession, payload.session_id, "Session")
    return await _ingest_and_broadcast(request, db, session, payload.telemetry, actor)


@router.get(
    "/sessions/{session_id}/decision/latest", response_model=DecisionRead, tags=["decisions"]
)
def latest_decision(session_id: str, db: Db) -> DecisionRecord:
    _get(db, TherapySession, session_id, "Session")
    decision = _latest_decision(db, session_id)
    if decision is None:
        raise _not_found("Decision")
    return decision


@router.get("/alerts", response_model=list[AlertRead], tags=["alerts"])
def list_alerts(
    db: Db,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    patient_id: str | None = None,
    session_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[Alert]:
    query = select(Alert)
    if status_filter:
        query = query.where(Alert.status == status_filter)
    if patient_id:
        query = query.where(Alert.patient_id == patient_id)
    if session_id:
        query = query.where(Alert.session_id == session_id)
    return list(db.scalars(query.order_by(desc(Alert.created_at)).limit(limit)))


def _acknowledge_alert(alert_id: str, db: Session, actor: ActorContext) -> Alert:
    alert = _get(db, Alert, alert_id, "Alert")
    if alert.status != "acknowledged":
        alert.status = "acknowledged"
        alert.acknowledged_at = utcnow()
        alert.acknowledged_by = actor.actor_id
        add_audit_event(
            db, actor, event_type="alert.acknowledged", entity_type="alert", entity_id=alert.id
        )
        db.commit()
        db.refresh(alert)
    return alert


@router.post("/alerts/{alert_id}/ack", response_model=AlertRead, tags=["alerts"])
def acknowledge_alert(alert_id: str, db: Db, actor: Actor) -> Alert:
    return _acknowledge_alert(alert_id, db, actor)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead, tags=["alerts"])
def acknowledge_alert_alias(alert_id: str, db: Db, actor: Actor) -> Alert:
    return _acknowledge_alert(alert_id, db, actor)


@router.get("/audit", response_model=list[AuditRead], tags=["audit"])
def list_audit_events(
    db: Db,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[AuditEvent]:
    query = select(AuditEvent)
    for column, value in (
        (AuditEvent.entity_type, entity_type),
        (AuditEvent.entity_id, entity_id),
        (AuditEvent.actor_id, actor_id),
        (AuditEvent.event_type, event_type),
    ):
        if value:
            query = query.where(column == value)
    if since:
        query = query.where(AuditEvent.occurred_at >= since)
    return list(db.scalars(query.order_by(desc(AuditEvent.occurred_at)).limit(limit)))


@router.post("/sessions/{session_id}/simulator/start", response_model=SimulatorStatus, tags=["simulator"])
async def start_simulator(
    session_id: str, payload: SimulatorStartRequest, request: Request, db: Db, actor: Actor
) -> dict[str, object]:
    session = _get(db, TherapySession, session_id, "Session")
    try:
        request.app.state.simulator.ensure_startable(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    patient = _get(db, Patient, session.patient_id, "Patient")
    device = _get(db, Device, session.device_id, "Device")
    prescription = _get(db, Prescription, session.prescription_id, "Prescription")
    _raise_if_not_ready(
        assess_readiness(
            db,
            patient=patient,
            device=device,
            prescription=prescription,
            exclude_session_id=session.id,
        )
    )
    if session.status == "planned":
        session.status = "running"
        session.started_at = utcnow()
    elif session.status != "running":
        raise HTTPException(status_code=409, detail="Simulator requires a planned or running session")
    session.active_scenario = payload.scenario
    add_audit_event(
        db, actor, event_type="simulator.started", entity_type="therapy_session", entity_id=session.id,
        details={"scenario": payload.scenario, "deterministic": True},
    )
    _commit(db, "Another running session already uses this patient or device")
    try:
        await request.app.state.simulator.start(
            session_id,
            scenario=payload.scenario,
            interval_seconds=payload.interval_seconds,
            max_samples=payload.max_samples,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return request.app.state.simulator.status(session_id, payload.scenario)


@router.post("/sessions/{session_id}/simulator/stop", response_model=SimulatorStatus, tags=["simulator"])
async def stop_simulator(session_id: str, request: Request, db: Db, actor: Actor) -> dict[str, object]:
    session = _get(db, TherapySession, session_id, "Session")
    await request.app.state.simulator.stop(session_id)
    add_audit_event(
        db, actor, event_type="simulator.stopped", entity_type="therapy_session", entity_id=session.id
    )
    db.commit()
    return request.app.state.simulator.status(session_id, session.active_scenario)


@router.get("/sessions/{session_id}/simulator", response_model=SimulatorStatus, tags=["simulator"])
def simulator_status(session_id: str, request: Request, db: Db) -> dict[str, object]:
    session = _get(db, TherapySession, session_id, "Session")
    return request.app.state.simulator.status(session_id, session.active_scenario)


@router.post(
    "/sessions/{session_id}/simulator/step",
    response_model=TelemetryDecisionResponse,
    tags=["simulator"],
)
async def simulator_step(session_id: str, request: Request, db: Db) -> TelemetryDecisionResponse:
    session = _get(db, TherapySession, session_id, "Session")
    if session.status == "planned":
        patient = _get(db, Patient, session.patient_id, "Patient")
        device = _get(db, Device, session.device_id, "Device")
        prescription = _get(db, Prescription, session.prescription_id, "Prescription")
        _raise_if_not_ready(
            assess_readiness(
                db,
                patient=patient,
                device=device,
                prescription=prescription,
                exclude_session_id=session.id,
            )
        )
        session.status = "running"
        session.started_at = utcnow()
        _commit(db, "Another running session already uses this patient or device")
    try:
        result = await request.app.state.simulator.step(session_id)
    except (LookupError, IngestionError, ValueError, IntegrityError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TelemetryDecisionResponse(
        telemetry=TelemetryRead.model_validate(result.telemetry),
        decision=DecisionRead.model_validate(result.decision),
        alerts_created=[item.id for item in result.alerts],
    )


@router.post("/sessions/{session_id}/inject-scenario", response_model=SimulatorStatus, tags=["simulator"])
def inject_scenario(
    session_id: str, payload: ScenarioRequest, request: Request, db: Db, actor: Actor
) -> dict[str, object]:
    session = _get(db, TherapySession, session_id, "Session")
    if session.status != "running":
        raise HTTPException(
            status_code=409,
            detail="A scenario can be injected only into a running session",
        )
    session.active_scenario = payload.scenario
    add_audit_event(
        db, actor, event_type="simulator.scenario_injected", entity_type="therapy_session",
        entity_id=session.id, details={"scenario": payload.scenario},
    )
    db.commit()
    request.app.state.simulator.set_scenario(session_id, payload.scenario)
    return request.app.state.simulator.status(session_id, payload.scenario)


@router.get("/patients/{patient_id}/fhir", tags=["interoperability"])
def export_patient_fhir(patient_id: str, db: Db) -> JSONResponse:
    patient = _get(db, Patient, patient_id, "Patient")
    return JSONResponse(build_patient_bundle(db, patient), media_type="application/fhir+json")


@router.get("/sessions/{session_id}/fhir", tags=["interoperability"])
def export_session_fhir(session_id: str, db: Db) -> JSONResponse:
    session = _get(db, TherapySession, session_id, "Session")
    return JSONResponse(build_session_bundle(db, session), media_type="application/fhir+json")


@router.get("/interop/fhir/export", tags=["interoperability"])
def export_fhir(
    db: Db, patient_id: str | None = None, session_id: str | None = None
) -> JSONResponse:
    if patient_id and session_id:
        raise HTTPException(status_code=422, detail="Specify patient_id or session_id, not both")
    if patient_id:
        patient = _get(db, Patient, patient_id, "Patient")
        bundle = build_patient_bundle(db, patient)
    elif session_id:
        session = _get(db, TherapySession, session_id, "Session")
        bundle = build_session_bundle(db, session)
    else:
        bundle = build_all_bundle(db)
    return JSONResponse(bundle, media_type="application/fhir+json")


async def session_websocket(websocket: WebSocket, session_id: str) -> None:
    app = websocket.app
    with app.state.session_factory() as db:
        if db.get(TherapySession, session_id) is None:
            await websocket.close(code=4404, reason="Session not found")
            return
    await app.state.connections.connect(session_id, websocket)
    await websocket.send_json(
        {
            "type": "connected",
            "session_id": session_id,
            "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
            "research_use_only": True,
        }
    )
    try:
        while True:
            message = await websocket.receive_text()
            if message.lower() == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
                    }
                )
    except WebSocketDisconnect:
        await app.state.connections.disconnect(session_id, websocket)
