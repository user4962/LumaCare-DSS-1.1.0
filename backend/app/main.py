from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router, session_websocket
from .config import Settings, get_settings
from .database import (
    Base,
    apply_sqlite_compatibility_migrations,
    create_database_engine,
    create_session_factory,
)
from .seed import seed_demo_data
from .services.decision_adapter import DecisionEngineAdapter
from .services.simulator import SimulatorManager
from .services.process_lock import SingleWorkerLock
from .services.websocket import SessionConnectionManager


OPENAPI_TAGS = [
    {"name": "system", "description": "Runtime status and explicit research-use metadata."},
    {"name": "dashboard", "description": "Aggregated operational snapshot."},
    {"name": "patients", "description": "Synthetic or research-participant records."},
    {"name": "devices", "description": "IoT light-device registry and connectivity state."},
    {
        "name": "prescriptions",
        "description": "Research protocol settings. Values require independent clinical validation.",
    },
    {"name": "sessions", "description": "Therapy-simulation session lifecycle."},
    {"name": "telemetry", "description": "Time-series ingestion and retrieval."},
    {"name": "decisions", "description": "Explainable deterministic research recommendations."},
    {"name": "alerts", "description": "Safety-rule notifications and acknowledgement."},
    {"name": "audit", "description": "Append-only application event trail."},
    {"name": "simulator", "description": "Deterministic research telemetry scenarios."},
    {
        "name": "interoperability",
        "description": "FHIR R4-aligned research bundles without a conformance claim.",
    },
]


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)
    session_factory = create_session_factory(engine)
    connections = SessionConnectionManager()
    decision_adapter = DecisionEngineAdapter()
    worker_lock = SingleWorkerLock(runtime_settings.database_url)
    simulator = SimulatorManager(
        session_factory,
        connections,
        decision_adapter,
        runtime_settings.simulator_interval_seconds,
        runtime_settings.telemetry_future_tolerance_seconds,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        worker_lock.acquire()
        try:
            Base.metadata.create_all(engine)
            apply_sqlite_compatibility_migrations(engine)
            if runtime_settings.seed_demo_data:
                with session_factory() as db:
                    seed_demo_data(db)
            yield
        finally:
            await simulator.shutdown()
            engine.dispose()
            worker_lock.release()

    application = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        summary="IoT-enabled light-therapy decision-support research demonstrator",
        description=(
            "A reproducible software research platform for device telemetry, protocol-bound "
            "decision support, alerting, auditability, deterministic simulation, and FHIR "
            "R4-aligned export. All thresholds and recommendations are research/demo artifacts. "
            "The API is not validated for diagnosis, treatment, or autonomous device control."
        ),
        contact={"name": "Research demonstrator maintainers"},
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.settings = runtime_settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.connections = connections
    application.state.decision_adapter = decision_adapter
    application.state.simulator = simulator
    application.include_router(router, prefix=runtime_settings.api_prefix)
    application.add_api_websocket_route("/ws/sessions/{session_id}", session_websocket)

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": runtime_settings.app_name,
            "docs": "/docs",
            "health": f"{runtime_settings.api_prefix}/health",
            "research_use_only": "true",
        }

    return application


app = create_app()
