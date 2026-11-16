from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..models import Prescription, TelemetrySample, TherapySession
from ..schemas import ActorContext, TelemetryIn
from .decision_adapter import DecisionEngineAdapter
from .presentation import websocket_telemetry_event
from .telemetry import IngestionError, IngestionResult, ingest_telemetry
from .websocket import SessionConnectionManager


NOMINAL_WARMING_C = 0.6
NOMINAL_WARMING_SAMPLES = 60.0
TEMPERATURE_RISE_STEP_C = 1.05
SPO2_DROP_STEP_PERCENT = 1.5

SCENARIOS = {
    "nominal",
    "temperature_rise",
    "spo2_drop",
    "contact_loss",
    "irradiance_spike",
}


@dataclass(slots=True)
class SimulationRun:
    task: asyncio.Task[None]
    scenario: str
    interval_seconds: float
    max_samples: int | None
    samples_generated: int = 0


class SimulatorManager:
    """Manage deterministic, session-scoped telemetry generators."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        connections: SessionConnectionManager,
        adapter: DecisionEngineAdapter,
        default_interval_seconds: float,
        future_tolerance_seconds: float = 5.0,
    ) -> None:
        self._session_factory = session_factory
        self._connections = connections
        self._adapter = adapter
        self._default_interval = default_interval_seconds
        self._future_tolerance = future_tolerance_seconds
        self._runs: dict[str, SimulationRun] = {}

    def ensure_startable(self, session_id: str) -> None:
        current = self._runs.get(session_id)
        if current and not current.task.done():
            raise ValueError("Simulator is already running for this session")

    async def start(
        self,
        session_id: str,
        *,
        scenario: str,
        interval_seconds: float | None = None,
        max_samples: int | None = None,
    ) -> None:
        if scenario not in SCENARIOS:
            raise ValueError("Unknown simulator scenario")
        self.ensure_startable(session_id)
        interval = interval_seconds or self._default_interval
        task = asyncio.create_task(
            self._run(session_id, interval, max_samples),
            name=f"light-dss-simulator-{session_id}",
        )
        self._runs[session_id] = SimulationRun(task, scenario, interval, max_samples)

    async def stop(self, session_id: str) -> None:
        run = self._runs.get(session_id)
        if run is None or run.task.done():
            return
        run.task.cancel()
        try:
            await run.task
        except asyncio.CancelledError:
            pass

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.stop(session_id) for session_id in tuple(self._runs)))

    def set_scenario(self, session_id: str, scenario: str) -> None:
        if scenario not in SCENARIOS:
            raise ValueError("Unknown simulator scenario")
        run = self._runs.get(session_id)
        if run is not None:
            run.scenario = scenario

    def status(self, session_id: str, fallback_scenario: str = "nominal") -> dict[str, object]:
        run = self._runs.get(session_id)
        return {
            "session_id": session_id,
            "running": bool(run and not run.task.done()),
            "scenario": run.scenario if run else fallback_scenario,
            "samples_generated": run.samples_generated if run else 0,
        }

    async def step(
        self,
        session_id: str,
        scenario: str | None = None,
        interval_seconds: float | None = None,
    ) -> IngestionResult:
        with self._session_factory() as db:
            session = db.get(TherapySession, session_id)
            if session is None:
                raise LookupError("Session not found")
            if scenario is not None:
                if scenario not in SCENARIOS:
                    raise ValueError("Unknown simulator scenario")
                session.active_scenario = scenario
                db.commit()
            result = self._generate_one(db, session, interval_seconds or self._default_interval)
        await self._connections.broadcast(session_id, websocket_telemetry_event(result))
        return result

    async def _run(
        self,
        session_id: str,
        interval_seconds: float,
        max_samples: int | None,
    ) -> None:
        try:
            while True:
                run = self._runs[session_id]
                if max_samples is not None and run.samples_generated >= max_samples:
                    return
                try:
                    result = await self.step(session_id, None, interval_seconds)
                except (LookupError, IngestionError, IntegrityError):
                    return
                run.samples_generated += 1
                if result.decision.action == "HOLD" or result.session_status != "running":
                    return
                await asyncio.sleep(interval_seconds)
        finally:
            # Preserve the completed run for observable status and sample count.
            pass

    def _generate_one(
        self, db: Session, session: TherapySession, interval_seconds: float
    ) -> IngestionResult:
        prescription = db.get(Prescription, session.prescription_id)
        if prescription is None:
            raise IngestionError("Prescription not found")
        next_sequence = int(
            db.scalar(
                select(func.coalesce(func.max(TelemetrySample.sequence), -1) + 1).where(
                    TelemetrySample.session_id == session.id
                )
            )
            or 0
        )
        previous_dose = float(
            db.scalar(
                select(func.max(TelemetrySample.cumulative_dose_j_cm2)).where(
                    TelemetrySample.session_id == session.id
                )
            )
            or 0.0
        )
        previous = db.scalars(
            select(TelemetrySample)
            .where(TelemetrySample.session_id == session.id)
            .order_by(TelemetrySample.sequence.desc())
            .limit(1)
        ).first()
        scenario = session.active_scenario
        phase = next_sequence + (session.simulator_seed % 17) / 17.0
        irradiance = prescription.target_irradiance_mw_cm2 * (
            1.0 + 0.015 * math.sin(phase * 0.7)
        )
        # Nominal skin warming approaches a plateau 0.6 degC above the start value.
        temperature = (
            36.4
            + NOMINAL_WARMING_C * (1.0 - math.exp(-next_sequence / NOMINAL_WARMING_SAMPLES))
            + 0.08 * math.sin(phase * 0.4)
        )
        spo2 = 98.0 - 0.2 * (1.0 + math.sin(phase * 0.5))
        contact = True

        # Deviation scenarios start from the last recorded value, so a scenario
        # injected in the middle of a session produces a ramp instead of a jump.
        if scenario == "temperature_rise":
            start = previous.skin_temperature_c if previous is not None else temperature
            temperature = start + TEMPERATURE_RISE_STEP_C
        elif scenario == "spo2_drop":
            start = previous.spo2_percent if previous is not None else spo2
            spo2 = start - SPO2_DROP_STEP_PERCENT
        elif scenario == "contact_loss" and next_sequence >= 2:
            contact = False
        elif scenario == "irradiance_spike" and next_sequence >= 2:
            irradiance = prescription.target_irradiance_mw_cm2 * 1.5

        dose_increment = irradiance * interval_seconds / 1000.0
        payload = TelemetryIn(
            sequence=next_sequence,
            wavelength_nm=prescription.target_wavelength_nm,
            irradiance_mw_cm2=round(irradiance, 4),
            cumulative_dose_j_cm2=round(previous_dose + dose_increment, 6),
            skin_temperature_c=round(temperature, 3),
            spo2_percent=round(max(0.0, spo2), 3),
            contact_detected=contact,
            battery_percent=max(0.0, round(96.0 - next_sequence * 0.08, 2)),
            signal_quality=0.99 if contact else 0.2,
            raw_payload={"source": "deterministic-simulator", "scenario": scenario},
        )
        return ingest_telemetry(
            db,
            session=session,
            payload=payload,
            actor=ActorContext(actor_id="deterministic-simulator", actor_role="system"),
            adapter=self._adapter,
            future_tolerance_seconds=self._future_tolerance,
        )
