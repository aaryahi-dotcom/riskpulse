from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    model_service = request.app.state.model_service
    return {
        "status": "ok",
        "model_loaded": model_service.loaded,
        "model_version": model_service.model_version,
        "feature_store_backend": request.app.state.feature_store.backend_name,
    }
