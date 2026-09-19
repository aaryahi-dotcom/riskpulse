# RiskPulse Existing Code Summary

**Date**: 2026-09-19  
**Purpose**: Baseline understanding before adding the agent layer.

---

## Tech Stack

### Backend
- **Framework**: FastAPI 0.128.8 (Python 3.9)
- **Serving**: uvicorn
- **Auth**: JWT + passlib (bcrypt)
- **DB**: SQLAlchemy ORM
  - Local: SQLite (`backend/riskpulse.db`)
  - Production: Postgres (via docker-compose)
- **Feature Store**: Redis (real) or fakeredis (local dev)
- **Graph Analysis**: NetworkX 3.2.1 (transaction network, PageRank, cycle detection)

### Frontend
- **Framework**: Vite + React 18 + TypeScript
- **Port**: 5173 (dev)
- **Build**: Rolldown (ESM bundler)
- **State Management**: Zustand-style hooks (see `frontend/src/state/useRiskPulse.tsx`)

### ML
- **Models**: Ensemble of 3 classifiers
  - Primary: XGBoost 2.1.3 (with graceful fallback to sklearn.ensemble.GradientBoostingClassifier on macOS/no libomp)
  - Anomaly: IsolationForest
  - Calibration: sklearn.calibration.CalibratedClassifierCV
- **Features**: 30+ engineered signals across 5 families
- **Explainability**: SHAP 0.49.1 (TreeExplainer)
- **Imbalance Handling**: SMOTE via imbalanced-learn 0.12.4

---

## How to Run

### 1. Activate Virtual Environment
```bash
source .venv/bin/activate
```

### 2. Start Backend (Port 8000)
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Demo credentials: `demo_admin` / `riskpulse-demo` (OAuth2 password flow at `/api/v1/auth/token`)

### 3. Start Frontend (Port 5173)
```bash
cd frontend
npm install  # (one-time)
npm run dev
```
- Opens at http://localhost:5173
- Falls back to built-in simulator if backend is unreachable

### 4. Run Tests
```bash
cd backend
pytest
```

---

## Risk Score Computation

### Request Flow: `/api/v1/score` (in `backend/app/routers/score.py`)

1. **Idempotency Check**: If identical payload seen before, return cached response.

2. **Feature Assembly** (`app.feature_assembler.assemble(payload)` → `backend/app/features_online.py`)
   - Raw values extracted from payload + feature store history
   - Cold-start safe: defaults for missing data
   - Output: feature vector `X`, debug dict with raw values and puppet signals

3. **Puppet Signal Computation** (in `backend/app/puppet.py`)
   - Computed as part of feature assembly
   - 4 sub-signals combined into `puppet_score` (0–1):
     - `amount_regularity`: mechanical uniformity of recent amounts
     - `timing_regularity`: mechanical uniformity of recent txn timing
     - `new_beneficiary_burst`: multiple new payees in short window
     - `session_linearity`: scripted straight-to-transfer session pattern
   - Included in feature vector; contributes to ML score

4. **ML Scoring** (`app.model_service.score(X)` → `backend/app/model_service.py`)
   - Ensemble prediction: weighted combination of supervised + IsolationForest + calibration
   - Returns `ml_score` (0–1)

5. **SHAP Explanation** (`model_service.explain(X)`)
   - Per-feature contribution to ml_score
   - Converted to human-readable reason strings via `decision.shap_to_reasons()`
   - Top 5 reasons returned

6. **Graph Pre-Approval Simulation** (in `backend/app/graph_analysis.py`)
   - NetworkX DiGraph of all past transactions (sender/receiver nodes, agg edges)
   - Checks:
     - `CYCLE_DETECTED`: pre-existing path back from receiver to sender (layering/circular fund flow)
     - `PAGERANK_SPIKE`: receiver's importance score jumps unexpectedly
     - `BRIDGES_SUSPICIOUS_CLUSTERS`: sender bridges between unrelated transaction clusters
   - Flags returned; some are overrides, others add score deltas

7. **Contagion Exposure** (in `backend/app/contagion.py`)
   - When fraud confirmed via feedback, BFS spreads "exposure" score through the graph
   - Sender's exposure_score looked up from feature store (TTL-based decay)
   - Contributes additive delta to augmented_score

8. **Decision Aggregation** (`decision.aggregate_decision()` in `backend/app/decision.py`)
   - **Precedence order**:
     1. Rule-engine "override" rules (if any match, they set tier directly)
     2. Graph `CYCLE_DETECTED` flag (automatic block)
     3. ML score + rule "augment" actions + graph-flag deltas + contagion exposure → `augmented_score`
     4. Puppet override: if `puppet_score > puppet_threshold` AND `amount > ₹1,00,000`, escalate to step_up/block
   - **Decision tiers**:
     - `approve`: risk_score < approve_threshold (default ~0.35)
     - `step_up`: approve_threshold ≤ risk_score < block_threshold (default ~0.65)
     - `block`: risk_score ≥ block_threshold
   - **Thresholds**: Persisted in DB (`ThresholdConfig`), configurable via `/api/v1/admin/thresholds`

9. **Audit Trail Persistence**
   - Immutable row added to `ScoredTransaction` table
   - Includes full response JSON for forensics

10. **Feature Store Update**
    - Transaction recorded in Redis (or fakeredis) for future feature assembly
    - Used by velocity counts, beneficiary history, puppet signals

11. **Graph Incremental Update**
    - Transaction edge added to live NetworkX graph
    - Marked as "blocked" if tier == "block" for pre-approval simulation

12. **WebSocket Broadcast**
    - Score result sent to all connected clients on `/ws/transactions` (live dashboard feed)

---

## What Signals Are Computed

### Transaction Context (5 signals)
- `amount`: log-scaled or z-scored amount
- `channel`: UPI / NEFT / RTGS / card / other
- `device_type`: mobile / desktop / web / unknown
- `vpa` (UPI handle): beneficiary identifier
- `timestamp`: ISO 8601 UTC

### Historical Behavior (8 signals)
- `velocity_count_1h`, `velocity_count_24h`, `velocity_count_7d`: transaction frequency windows
- `first_time_beneficiary_flag`: boolean, is this VPA/account new?
- `new_beneficiary_burst`: count of brand-new payees in recent window
- `sender_receiver_pair_count`: historical transactions with this specific receiver
- `days_since_last_txn`: idle window before this transaction
- `sender_tx_count_so_far`: total historical transaction count

### Device Signals (3 signals)
- `new_device_flag`: device not seen before for this sender
- `device_change_velocity`: count of distinct devices used recently
- `has_identity_info`: boolean, were device/identity details captured?

### Beneficiary History (3 signals)
- `receiver_domain_freq`: how common is this VPA domain across all users?
- `receiver_is_free_email`: uses generic (Gmail, Hotmail, etc.)?
- `sender_days_since_first_seen`: sender account tenure

### Spending Patterns (4 signals)
- `amount_zscore`: statistical outlier vs. this sender's history
- `spike_flag`: amount is 3x+ the running average
- `is_night`: transaction in 23:00–05:00 UTC window
- `round_amount_flag`: suspiciously round figure (1000, 5000, 10000, etc.)

### Puppet Coercion Signals (4 sub-signals → 1 composite score)
- `amount_regularity`: mechanical uniformity (std dev of recent amounts near zero)
- `timing_regularity`: mechanical timing uniformity (e.g. exactly 2 minutes apart)
- `session_linearity`: activity pattern looks like a direct sequence to transfer (no backtracking)
- `new_beneficiary_burst`: multiple new payees in quick succession

### Graph & Contagion Signals (3 signals + flags)
- `exposure_score`: contagion spread from confirmed-fraud nodes (0–1)
- `graph_flags`: CYCLE_DETECTED, PAGERANK_SPIKE, BRIDGES_SUSPICIOUS_CLUSTERS

### UPI-Specific Features (2 signals, new in checklist 3.2)
- `vpa_entropy`: Shannon entropy of VPA local part (random handles rank higher)
- `time_deviation`: circular deviation from sender's median transaction hour

**Note**: Cold-start defaults apply when historical data is missing (new sender, new device, etc.) — see `backend/models/cold_start_defaults.json`.

---

## What the UI Shows

### Main Console (`frontend/src/components/console/Console.tsx`)
Multi-tab interface:

1. **Dashboard** (`dashboard/Dashboard.tsx`)
   - Overview of recent transactions, risk distribution
   - Shows aggregated statistics

2. **Score & Decide** (part of Dashboard)
   - Request pane: edit transaction fields (sender, receiver, amount, channel, device, etc.)
   - Response pane: risk_score, decision (approve/step_up/block), SHAP reasons, action (OTP / Analyst Alert / Pass Through)
   - Call the real `/api/v1/score` endpoint

3. **Live Feed** (WebSocket client)
   - Real-time stream of scored transactions
   - Shows tier, amount, parties, puppet_score, reason_code

4. **Simulator** (`Simulator.tsx`)
   - Generate mock transactions with configurable parameters
   - Useful for testing decision logic without real data

5. **Rules** (`Rules.tsx`)
   - CRUD interface for custom rules (`/api/v1/rules`)
   - Rule editor: condition (IF amount > X AND ...), action (override to "block" or augment score by +0.1)
   - Enable/disable rules, set priority order

6. **Alerts** (`Alerts.tsx`)
   - Grouped view of flagged transactions (via `/api/v1/alerts/grouped`)
   - Grouped by beneficiary or cross-beneficiary sender pattern
   - Priority calculated as: `total_amount_at_risk * avg_risk_score`

7. **Graph** (`GraphScreen.tsx` + `ForceGraph.tsx`)
   - Interactive force-directed visualization of transaction network
   - Nodes = accounts, edges = transactions
   - Shows PageRank, cluster membership, degree

8. **Health** (`Health.tsx`)
   - Model metrics: F1, precision, recall, FPR (on held-out test set)
   - Feature store status
   - Latency percentiles (p50/p95/p99)
   - Drift heuristic: >25% shift in mean amount or mean score over time

9. **Thresholds** (`Thresholds.tsx`)
   - Configure approve_threshold, block_threshold, puppet_threshold
   - Threshold preview: simulate decision changes if thresholds moved

10. **Workbench** (`Workbench.tsx`)
    - Deep-dive forensics on a single transaction
    - Full feature vector, SHAP breakdown, linked transactions (same sender or receiver)
    - Feedback form: label transaction as fraud/legit to retrain model

---

## Database Schema (Key Tables)

- **ScoredTransaction**: Immutable audit log of every `/api/v1/score` call
  - Fields: txn_id, request_hash, sender_id, receiver_id, amount, channel, vpa, timestamp, risk_score, decision, reason_code, puppet_score, model_version, shap_summary_json, full_response_json, rule_hits_json
  - Index on sender_id, receiver_id for quick history lookups

- **ThresholdConfig**: Current threshold settings (one "current" row via `order_by desc`)
  - Fields: approve_threshold, block_threshold, puppet_threshold, updated_by, updated_at

- **Rule**: Custom rule definitions (checklist 2.5)
  - Fields: priority, name, condition (JSON), action (override | augment), score_delta, forced_tier, active

- **Feedback**: User labels for retraining (checklist 2.6)
  - Fields: txn_id, confirmed_label (fraud | legit | manual_review), feedback_text, created_by, created_at

- **ModelVersion**: Archived trained models (checklist 2.6)
  - Fields: version, status (champion | challenger | archived), metrics_json, persisted_at

---

## Key Files & Modules

### Backend (`backend/app/`)
- **main.py**: FastAPI app setup, middleware, startup/shutdown (model load, graph init, feature store warm)
- **config.py**: Settings (DB URL, model path, thresholds, feature store type)
- **routers/score.py**: POST `/api/v1/score` endpoint
- **routers/rules.py**: CRUD for rules
- **routers/feedback.py**: POST feedback (triggers contagion BFS)
- **routers/admin.py**: Retrain, rollback, health, thresholds
- **decision.py**: Scoring logic, aggregation, puppet override, fallback scorer
- **model_service.py**: ML ensemble load, score, explain
- **feature_store.py**: Redis wrapper for feature persistence
- **features_online.py**: Feature assembly at score time
- **puppet.py**: Puppet signal sub-formulas
- **graph_analysis.py**: NetworkX graph, pre-approval simulation
- **contagion.py**: Fraud contagion spread (BFS)
- **rule_engine.py**: Dependency-free rule evaluator

### ML (`ml/`)
- **train.py**: Main training pipeline (data load → feature eng → train ensemble → SHAP explainer → persist)
- **features.py**: Batch feature engineering (used during training)
- **feature_registry.py**: Feature metadata (name, type, description)
- **puppet_signals.py**: Puppet signal formulas
- **data_loader.py**: Load IEEE-CIS CSVs, train/test split, SMOTE

### Frontend (`frontend/src/`)
- **state/useRiskPulse.tsx**: Global state (view, theme, auth, API calls)
- **components/console/Console.tsx**: Tab switcher
- **components/console/dashboard/Dashboard.tsx**: Main scoring UI
- **components/console/Simulator.tsx**: Mock transaction generator
- **components/console/Rules.tsx**: Rule CRUD
- **components/console/Alerts.tsx**: Grouped alerts
- **components/console/Workbench.tsx**: Single-transaction forensics
- **lib/api.ts**: HTTP client wrapping `/api/v1/` endpoints

---

## Current Limitations & Notes

1. **XGBoost Fallback**: This dev machine uses GradientBoostingClassifier (no libomp); Linux/Docker use real XGBoost.

2. **Model Artifact Commits**: Trained weights (*.pkl, *.json) are .gitignored; regenerate locally via `python ml/train.py`.

3. **Puppet Override Dual-Path**: The rule-engine has a seeded puppet rule row, but the *authoritative* enforcement still runs through `decision.apply_puppet_override()` independently. Unifying these is explicitly deferred (see README layer 2.5 notes).

4. **Drift Detection**: Heuristic only (>25% shift in mean amount/score), not a real statistical test (PSI/KS-test).

5. **Retrain Loop Incomplete**: Feedback is recorded but not yet fed back into training data; the retrain endpoint reuses the original IEEE-CIS CSVs.

6. **UPI Features Partial**: Only `vpa_entropy` and `time_deviation` implemented; `collect_pay_ratio`, `channel_switch_flag`, `interbank_ratio`, festival-season shift are deferred.

---

## Starting Point for Agent Layer

The scoring endpoint (`/api/v1/score`) currently:
1. Computes `ml_score` (0–1)
2. Applies rule engine, graph checks, contagion
3. Aggregates into final `augmented_score`
4. Applies puppet override
5. Thresholds augmented_score into {approve, step_up, block}

**Where agents fit**: Between step 3 (augmented_score) and step 5 (thresholding). If augmented_score falls into a **grey zone** (e.g., 0.35–0.75), invoke agent pipeline before deciding. Agents return explainable verdicts (ALLOW, COOL_OFF, ALERT, BLOCK) that replace the simple threshold logic.

---

## Configuration

### `.env` / `backend/app/config.py`
- `DATABASE_URL`: SQLite path or Postgres connection string
- `FEATURE_STORE_TYPE`: "redis" or "fakeredis"
- `REDIS_URL`: Redis connection (if redis chosen)
- `MODEL_PATH`: Path to trained artifacts (default `backend/models/`)
- `DEFAULT_APPROVE_THRESHOLD`, `DEFAULT_BLOCK_THRESHOLD`, `DEFAULT_PUPPET_THRESHOLD`
- `ANTHROPIC_API_KEY`: (not yet used; will be for agent LLM calls)

### See `.env.example` for full template.

---

**Next Steps**: Run app end-to-end to confirm; then plan agent layer integration points.
