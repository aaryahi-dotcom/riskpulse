"""
Environment-driven settings — checklist Layer 0: ".env.example (Redis URL,
PostgreSQL URL, model path) + secrets handling", and Layer 1's requirement
that thresholds be configurable, not hardcoded.

Every path/URL here has a sane local default so `uvicorn app.main:app`
works out of the box on a laptop with no .env file, but every one of them
is overridable via env var so the docker-compose path (real Postgres +
real Redis) is a config change, not a rewrite.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- DB: SQLite now, Postgres later via DATABASE_URL ---
    database_url: str = "sqlite:///./riskpulse.db"

    # --- Feature store: unset -> in-process/fakeredis fallback ---
    redis_url: str | None = None

    # --- Model artifacts ---
    model_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

    # --- JWT auth ---
    jwt_secret: str = "riskpulse-dev-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    demo_username: str = "demo_admin"
    demo_password: str = "riskpulse-demo"

    # --- Adaptive verification thresholds (defaults; live values in DB) ---
    default_approve_threshold: float = 0.30
    default_block_threshold: float = 0.70
    default_puppet_threshold: float = 0.70

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
