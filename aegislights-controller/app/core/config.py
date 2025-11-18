from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide configuration."""

    database_url: str = Field(default="sqlite:///./aegislights.db")
    simulator_base_url: str = Field(default="http://localhost:9001")
    simulator_snapshot_path: str = Field(default="/api/v1/controller/snapshot")
    simulator_plan_path: str = Field(default="/api/v1/controller/intersections/{intersection_id}/plan")
    simulator_api_key: str | None = Field(default=None)
    rollback_utility_threshold: float = Field(default=0.35, ge=0.0, le=1.0)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
