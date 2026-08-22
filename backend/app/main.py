"""
RiskPulse FastAPI application entrypoint.

Run locally: `uvicorn app.main:app --reload --port 8000` from backend/.
Swagger UI: http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import SessionLocal, init_db
from .feature_store import get_feature_store
from .features_online import OnlineFeatureAssembler
from .graph_analysis import get_graph_service
from .latency import SCORE_LATENCY_BUDGET_MS, LatencyTracker
from .model_service import get_model_service
from .routers import admin, alerts, auth, feedback, graph, health, rules, score, ws
from .routers.rules import seed_default_rules
from .routers.ws import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

# checklist 2.3: cap how many persisted transactions we replay into the
# feature store on startup, so a large audit log doesn't turn every
# restart into a long blocking pause.
FEATURE_STORE_WARM_LIMIT = 5000


def _warm_feature_store(feature_store, limit: int = FEATURE_STORE_WARM_LIMIT) -> int:
    """checklist 2.3: 'Warm [the feature store] from [the SQLite audit
    log] on startup' — without this, restarting the API resets every
    sender's rolling velocity/puppet history to cold-start, even though
    the audit trail (ScoredTransaction) already has it. Replays the most
    recent `limit` persisted transactions, oldest-first, through the same
    record_transaction() path /api/v1/score uses live."""
    from .models_db import ScoredTransaction

    db = SessionLocal()
    try:
        rows = (
            db.query(ScoredTransaction)
            .order_by(ScoredTransaction.created_at.asc())
            .limit(limit)
            .all()
        )
        for row in rows:
            try:
                ts = datetime.fromisoformat(row.timestamp)
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            feature_store.record_transaction(row.sender_id, row.receiver_id, row.amount, ts.timestamp(), None)
        return len(rows)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RiskPulse backend starting up...")
    init_db()

    db = SessionLocal()
    try:
        seed_default_rules(db)
    finally:
        db.close()

    feature_store = get_feature_store(settings.redis_url)
    warmed = _warm_feature_store(feature_store)

    model_service = get_model_service(settings.model_dir)
    model_service.load()

    assembler = OnlineFeatureAssembler(settings.model_dir, feature_store)
    if model_service.loaded:
        assembler.bind_artifacts(model_service.encoders, model_service.receiver_freq)

    # checklist 3.3: rebuild the in-memory transaction graph from the same
    # SQLite audit log the feature store warms from, above.
    graph_service = get_graph_service()
    db2 = SessionLocal()
    try:
        graph_warmed = graph_service.rebuild_from_db(db2)
    finally:
        db2.close()

    app.state.feature_store = feature_store
    app.state.model_service = model_service
    app.state.feature_assembler = assembler
    app.state.graph_service = graph_service
    app.state.latency_tracker = LatencyTracker()
    # checklist 4.1: scoring runs in a worker thread (score_transaction is
    # a sync def), so broadcasting to WS clients from there needs the
    # main event loop captured here, up front.
    app.state.ws_manager = ConnectionManager()
    app.state.event_loop = asyncio.get_running_loop()

    logger.info(
        "Startup complete. model_loaded=%s model_version=%s feature_store=%s feature_store_warmed=%d "
        "graph_warmed=%d",
        model_service.loaded, model_service.model_version, feature_store.backend_name, warmed, graph_warmed,
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


@app.middleware("http")
async def latency_logging_middleware(request: Request, call_next):
    """checklist 2.3: 'Per-request latency logged; prove p95 < 100ms'.
    Records every request's wall-clock time into app.state.latency_tracker
    (read back by GET /api/v1/admin/model-health), and logs a warning
    when /api/v1/score alone exceeds the documented 100ms budget."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    tracker = getattr(request.app.state, "latency_tracker", None)
    if tracker is not None:
        tracker.record(request.url.path, elapsed_ms)
        tracker.record("__all__", elapsed_ms)

    if request.url.path.startswith("/api/v1/score") and elapsed_ms > SCORE_LATENCY_BUDGET_MS:
        logger.warning("Score request exceeded %.0fms budget: %.1fms", SCORE_LATENCY_BUDGET_MS, elapsed_ms)
    else:
        logger.debug("%s %s -> %.1fms", request.method, request.url.path, elapsed_ms)

    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(score.router)
app.include_router(admin.router)
app.include_router(rules.router)
app.include_router(feedback.router)
app.include_router(alerts.router)
app.include_router(graph.router)
app.include_router(ws.router)
