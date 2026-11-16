from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from fastapi import Request
from sqlalchemy import DateTime, Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC values in SQLite and always restore timezone information."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    pool_kwargs = {"poolclass": StaticPool} if database_url in {"sqlite://", "sqlite:///:memory:"} else {}
    engine = create_engine(
        database_url, connect_args=connect_args, pool_pre_ping=True, **pool_kwargs
    )

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def apply_sqlite_compatibility_migrations(engine: Engine) -> None:
    """Apply additive SQLite columns required by persisted demonstrator databases."""

    if not engine.url.drivername.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "prescriptions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("prescriptions")}
    if "wavelength_tolerance_nm" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE prescriptions ADD COLUMN wavelength_tolerance_nm "
                    "FLOAT NOT NULL DEFAULT 5.0"
                )
            )
    session_indexes = {
        index["name"] for index in inspector.get_indexes("therapy_sessions")
    } if "therapy_sessions" in inspector.get_table_names() else set()
    with engine.begin() as connection:
        if "uq_running_session_device" not in session_indexes:
            connection.execute(text(
                "CREATE UNIQUE INDEX uq_running_session_device ON therapy_sessions (device_id) "
                "WHERE status = 'running'"
            ))
        if "uq_running_session_patient" not in session_indexes:
            connection.execute(text(
                "CREATE UNIQUE INDEX uq_running_session_patient ON therapy_sessions (patient_id) "
                "WHERE status = 'running'"
            ))


def get_db(request: Request) -> Iterator[Session]:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
