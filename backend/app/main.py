"""
RiskPulse FastAPI application entrypoint.

Run locally: `uvicorn app.main:app --reload --port 8000` from backend/.
Swagger UI: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .feature_store import get_feature_store
from .features_online import OnlineFeatureAssembler
from .model_service import get_model_service
from .routers import admin, auth, health, score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RiskPulse backend starting up...")
    init_db()

    feature_store = get_feature_store(settings.redis_url)
    model_service = get_model_service(settings.model_dir)
    model_service.load()

    assembler = OnlineFeatureAssembler(settings.model_dir, feature_store)
    if model_service.loaded:
        assembler.bind_artifacts(model_service.encoders, model_service.receiver_freq)

    app.state.feature_store = feature_store
    app.state.model_service = model_service
    app.state.feature_assembler = assembler

    logger.info(
        "Startup complete. model_loaded=%s model_version=%s feature_store=%s",
        model_service.loaded, model_service.model_version, feature_store.backend_name,
    )
    yield
    logger.info("RiskPulse backend shutting down.")


app = FastAPI(
    title="RiskPulse — Dynamic Transaction Risk Scoring API",
    description="Team Hyphen · SIH 2026 · Problem Statement S21",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(score.router)
app.include_router(admin.router)
