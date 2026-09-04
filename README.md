# RiskPulse


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
satisfy S21) + Layer 2 (deployability) + Layer 3 (novelty — puppet
detection, graph evolution + pre-approval simulation, fraud contagion,
and the demo-scoped pair of UPI-specific features)** are built. Layer
3.2's remaining UPI features (`collect_pay_ratio`, `channel_switch_flag`,
`interbank_ratio`, festival-season baseline shift) are the checklist's
own "CUT FIRST" items and are still deferred, and Layer 4 (most UI
beyond wiring the existing mockup to real data — graph viz, contagion
heatmap, analyst workbench, rule-builder UI, model-health charts) is
not started yet — see the checklist for the reasoning and recommended
build order.

### Layer 3 — Novelty (the 4 differentiators)

| # | Item | Status |
|---|------|--------|
| 3.1 | Puppet signature detection | Done (pre-existing) — 4 sub-signals (`amount_regularity`, `timing_regularity`, `new_beneficiary_burst`, `session_linearity`) combined into `puppet_score`, computed on every transaction, rule-engine override at `puppet_score > 0.7 AND amount > ₹1,00,000` |
| 3.2 | UPI-specific deep features | Demo pair done — `vpa_entropy` (Shannon entropy of the VPA local-part) and `time_deviation` (circular deviation from the sender's median transaction hour), both fed into the model at train and serve time. The rest (`collect_pay_ratio`, `channel_switch_flag`, `interbank_ratio`, festival baseline shift) is deliberately deferred per the checklist's own "CUT FIRST" call |
| 3.3 | Temporal graph evolution + pre-approval simulation | Done — `backend/app/graph_analysis.py`: NetworkX `DiGraph` (accounts=nodes, aggregated txns=edges), rebuilt from the audit log at startup and updated incrementally; `GET /api/v1/graph/node/{user_id}` (PageRank/clustering/degree + windowed deltas) and `/subgraph/{user_id}`; `simulate_pre_approval()` runs on every `/api/v1/score` call, bounded to a small ego-neighborhood copy (cycle check, local PageRank-spike check, suspicious-cluster-bridging check) — never a full-graph recompute on the hot path |
| 3.4 | Fraud contagion modeling | Done — `backend/app/contagion.py`: confirming `POST /api/v1/feedback` with `confirmed_label="fraud"` triggers a `BackgroundTasks` BFS (depth 3) from the receiver over the transaction graph, `exposure = 1.0 * 0.5**hop`, persisted as `user:{id}:exposure_score` in the feature store (TTL-based decay standing in for SIR's "Recovered" state) and folded into the next score for that account; `likely_next_victims()` surfaces the proactive alert list |

### Layer 2 — Innovation / Deployability

| # | Item | Status |
|---|------|--------|
| 2.1 | ML ensemble (supervised + IsolationForest + calibration) | Done (pre-existing) |
| 2.2 | Feature engine — 30+ signals, registry, unit tests | Done — added `backend/tests/test_feature_transforms.py` covering velocity counts, amount z-score, device-change velocity, new_beneficiary_burst, round_amount_flag, is_night, first_time_beneficiary_flag, cold-start defaults, and the puppet sub-signal formulas |
| 2.3 | Redis feature store + sub-100ms path | Done — `backend/app/latency.py` + a FastAPI middleware log every request's latency and expose p50/p95/p99 via `/api/v1/admin/model-health`; the feature store is warmed from `ScoredTransaction` on startup (capped at the last 5,000 rows so a large audit log can't turn a restart into a long pause) |
| 2.4 | Decision engine aggregator | Done — `decision.aggregate_decision()` formalizes the merge of ml_score + rule engine + graph_flags (placeholder) + puppet override, with a documented precedence order; `ScoreResponse` now also echoes `ml_score` and `rule_hits` |
| 2.5 | Custom rule engine — CRUD `/api/v1/rules` | Done — `backend/app/rule_engine.py` (dependency-free IF/AND/THEN evaluator), full CRUD + `/api/v1/rules/{id}/stats`, and the puppet override generalized into one seeded rule row (see `routers/rules.py::seed_default_rules` for why the *live* puppet enforcement still also runs through the original, independently-tunable `decision.apply_puppet_override` path) |
| 2.6 | Feedback loop + retraining | Done — `POST /api/v1/feedback`, `POST /api/v1/admin/retrain` (champion/challenger promotion by F1, versioned archive + `POST /api/v1/admin/rollback`), `ml/train.py` refactored into importable `train_and_evaluate()`/`persist_artifacts()` functions reused by both the CLI and the retrain endpoint |
| 2.7 | Alert grouping — `GET /api/v1/alerts/grouped` | Done — groups by beneficiary and by cross-beneficiary sender pattern, `priority = total_amount_at_risk * avg_risk_score` |
| 2.8 | Model health — `GET /api/v1/admin/model-health` | Done, with a **deliberately scoped-down** drift heuristic (see below) |
| 2.9 | Threshold replay — `GET /api/v1/admin/threshold-preview` | Done — replays the last N persisted risk scores against proposed thresholds; estimated FPR is cold-start-safe (null until feedback exists) |
| 2.10 | Resilience / fallbacks | Done — added explicit test coverage for both the model-missing and feature-store-fallback paths, and **fixed a real bug found while writing that coverage**: `FeatureStore` never reset `self._client` to `None` after a failed real-Redis connection, so it silently kept a dead connection instead of falling back to fakeredis. `docker-compose.yml` was read and sanity-checked (env vars line up with `config.Settings`, no real cloud dependency) — no changes were needed. |

**Explicitly scoped down, not just deferred:**
- **Drift detection (2.8)** is the checklist's own "CUT FIRST" item. The
  implementation here is a documented heuristic — split the most recent
  scored transactions into a "recent" and "older" half and flag a >25%
  relative shift in mean amount or mean risk score — not a real
  statistical test (no PSI/KS-test/feature-importance-shift-over-time).
- **The generalized puppet rule (2.5)** is a seeded, CRUD-visible `rules`
  table row, but the *authoritative* enforcement still runs through the
  original `decision.apply_puppet_override()` against the independently
  tunable `ThresholdConfig.puppet_threshold` — unifying those into one
  threshold source would be a bigger refactor than this pass's mandate
  to generalize without regressing the existing, tested puppet behavior.
- **Retrain-with-feedback-labels (2.6)**: the retrain endpoint reuses
  `ml/train.py`'s pipeline as-is against the IEEE-CIS CSVs; it does not
  yet fold `Feedback` rows back in as additional training labels — the
  feedback table and endpoint exist and are used by 2.5's rule stats and
  2.9's estimated FPR, but closing the loop into the training set itself
  is a further step not attempted this pass.

### Known limitation: XGBoost falls back to GradientBoostingClassifier

The trained model on this dev machine uses
`sklearn.ensemble.GradientBoostingClassifier`, not XGBoost. XGBoost's
compiled wheel needs `libomp.dylib` on macOS (normally
`brew install libomp`), and this machine has no Homebrew installed at
all, so that fix isn't a safe one-liner here. `ml/train.py` tries
XGBoost first and falls back cleanly — see `try_import_xgboost()`. A
Linux environment (including the Docker image in this repo, which
installs `libgomp1`) does not have this problem.
