from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="LUMACARE_",
        env_file=(BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    app_name: str = "Light Therapy Research Decision Support API"
    app_version: str = "1.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'light_therapy.db'}"
    seed_demo_data: bool = True
    simulator_interval_seconds: float = Field(default=1.0, ge=0.05, le=60.0)
    telemetry_future_tolerance_seconds: float = Field(default=5.0, ge=0.0, le=60.0)
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:4173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5173",
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
