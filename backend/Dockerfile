# RiskPulse backend — FastAPI scoring API.
#
# Note for the team: this container is also the fix for the XGBoost/libomp
# problem we hit on macOS dev machines without Homebrew — libgomp1 on
# Debian ships the OpenMP runtime XGBoost needs, so `import xgboost`
# succeeds here even on a laptop where it falls back to
# GradientBoostingClassifier locally (see ml/train.py's try_import_xgboost).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
# Trained model artifacts (joblib .pkl / json) — produced by `python
# ml/train.py` and mounted or copied in; never baked from a stale build
# context assumption. Empty dir is fine — model_service.py degrades to
# the rule-based fallback scorer if artifacts aren't present.
COPY backend/models /app/models

ENV MODEL_DIR=/app/models
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
