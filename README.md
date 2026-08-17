# RiskPulse

**Team Hyphen · Smart India Hackathon 2026 · Problem Statement S21**
*Dynamic transaction-risk scoring for adaptive verification.*

RiskPulse scores every transaction on five signal families (transaction
context, historical behavior, device signals, beneficiary history,
spending patterns), returns a calibrated 0-1 risk score with real SHAP
explanations, and routes it through three-tier adaptive verification
(auto-approve / step-up / block) instead of treating every transaction
equally. Its headline novelty is **puppet/coercion signature detection**
— catching "digital arrest" scams where a victim is walked through a
scripted sequence of mechanical transfers — computed live on every
transaction, not just a canned demo scenario.

See `BUILD_CHECKLIST.md` for the full scope breakdown (what's built vs.
what's intentionally deferred).

## Architecture

```
riskpulse-dashboard/
├── frontend/     Vite + React + TypeScript console (Score & Decide panel,
│                 live feed, SHAP breakdown, thresholds, workbench, ...)
├── backend/      FastAPI scoring API — auth, feature assembly, decision
│                 engine, puppet detection, SQLite audit trail
├── ml/           Training pipeline: IEEE-CIS feature engineering,
│                 SMOTE + ensemble model + SHAP explainer
└── data/raw/     IEEE-CIS Fraud Detection CSVs (gitignored — see
                  test_data or fetch from Kaggle yourself)
```

```
 ┌──────────┐   POST /api/v1/score    ┌──────────────┐    joblib.load   ┌──────────────┐
 │ frontend │ ───────────────────────▶│   backend     │◀────────────────│  ml/train.py │
 │ (Vite)   │◀─────────────────────── │   (FastAPI)   │                  │  (offline)   │
 └──────────┘   risk_score + SHAP     └──────┬───────┘                  └──────────────┘
                                              │
                              ┌───────────────┼────────────────┐
                              ▼               ▼                ▼
                        feature store    SQLite audit     model artifacts
                     (fakeredis/Redis)   (SQLAlchemy)      (backend/models/)
```

## Quick start (local, no Docker)

### 1. Train the model (one-time, produces backend/models/*)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
# Place train_transaction.csv + train_identity.csv in data/raw/ first.
python ml/train.py
```

This prints honest F1/precision/recall/FPR on a held-out test set and
writes `backend/models/metrics.json` + the trained artifacts (gitignored
— never committed, regenerate locally).

### 2. Run the backend

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Demo credential for JWT auth: `demo_admin` / `riskpulse-demo`
  (`POST /api/v1/auth/token`, form-encoded, OAuth2 password flow)

Run tests: `cd backend && pytest`

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The console's live feed and Score & Decide
panel call the real backend (`VITE_API_BASE_URL`, default
`http://localhost:8000`); if the backend isn't reachable it falls back to
the built-in simulator automatically, so the UI never crashes standalone.

## Docker Compose (backend + Postgres + Redis + frontend)

```bash
cp .env.example .env   # adjust if needed
docker compose up --build
```

Requires `backend/models/` to already contain trained artifacts (run
`python ml/train.py` first) — the API still starts and serves a
rule-based fallback score without them, but for the real model you need
the training step done at least once.

## What's built vs. deferred

Per `BUILD_CHECKLIST.md`: **Layer 0 (foundation) + Layer 1 (must-have to
satisfy S21) + Layer 3.1 (puppet detection)** are built in full. Layers 2
(deployability extras like Redis-backed p95 latency proof, rule engine
CRUD, feedback/retraining loop), 3.2-3.4 (UPI-specific deep features
beyond the demo pair, graph evolution, contagion modeling), and 4 (most
UI beyond wiring the existing mockup to real data) are explicitly not
started yet — see the checklist for the reasoning and recommended build
order.

### Known limitation: XGBoost falls back to GradientBoostingClassifier

The trained model on this dev machine uses
`sklearn.ensemble.GradientBoostingClassifier`, not XGBoost. XGBoost's
compiled wheel needs `libomp.dylib` on macOS (normally
`brew install libomp`), and this machine has no Homebrew installed at
all, so that fix isn't a safe one-liner here. `ml/train.py` tries
XGBoost first and falls back cleanly — see `try_import_xgboost()`. A
Linux environment (including the Docker image in this repo, which
installs `libgomp1`) does not have this problem.
