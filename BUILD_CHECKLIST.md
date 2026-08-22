# RiskPulse — Master Build Checklist (v2, brief-aligned)
### S21 · Dynamic Transaction-Risk Engine · Team HYPHEN · SIH 2026

**Status legend**
- `[x]` Built & working in the Day-1 prototype
- `[~]` Stub / placeholder exists — needs production upgrade
- `[ ]` Not started

**Owners** (from brief): Arya = backend/API · Aaryahi = ML/model · Kaysha = features/EDA/scenarios · Nihanshi = React · Bhoomi = design/UX · Paridhi = styling/rules-UI/validation

> **Framing that wins Q&A:** RiskPulse is a *deployable microservice*, not a research demo. The **product** is the scoring API + ops dashboard. The **simulator** is only a demo tool (judges can't wait for real fraud live). Keep that line straight in every answer.

> **Attack order:** Layer 1 (satisfy the PS) → Layer 2 (innovation / deployability) → Layer 3 (novelty / the 4 differentiators) → Layer 4 (UI/UX). Do not start Layer 3 until every Layer 1 box is `[x]`.

---

## LAYER 0 — Foundation (Phase 0 setup, do once)
*Owners: Arya + Aaryahi*

- [x] Git repo + branch-per-feature
- [x] FastAPI app skeleton
- [x] React frontend scaffold
- [ ] Repo structure: `backend/` · `ml/` · `frontend/` · `docker-compose.yml` · `.env`
- [ ] `docker-compose.yml` — FastAPI + Redis + PostgreSQL + React (one-command up)
- [ ] `.env.example` (Redis URL, PostgreSQL URL, model path) + secrets handling
- [ ] `/health` endpoint
- [ ] Pinned deps (`requirements.txt` / `pyproject.toml`)
- [ ] `pytest` harness + first passing test
- [ ] Swagger UI reachable at `/docs`
- [ ] Seed script (warm Redis from Postgres on startup)
- [ ] README: architecture diagram + run instructions

---

## LAYER 1 — MINIMUM REQUIREMENTS (satisfy S21) — MUST HAVE

> **PS text:** *"dynamic risk scores using transaction context, historical behavior, device signals, beneficiary history and spending patterns, enabling adaptive verification instead of treating every transaction equally."*
> All five named signal families must be visibly computed, or judges rule the PS unmet.

### 1.1 Scoring endpoint — `POST /api/v1/score`
*Owners: Arya + Aaryahi*
- [x] Accepts transaction JSON, returns risk score
- [x] Returns genuine SHAP values
- [~] Response contract → lock to `{ risk_score, decision, shap_values, puppet_score, graph_flags }`
- [ ] Input schema locked to brief: `amount, sender_id, receiver_id, timestamp, channel, vpa`
- [ ] Load models at startup (FastAPI lifespan event)
- [ ] Log `model_version` on every response
- [ ] Idempotency (same txn ⇒ same result)
- [ ] JWT token auth on the endpoint
- [ ] `GET /api/v1/score/history/{user_id}` — last N scored txns

### 1.2 Feature families — ALL FIVE named in the PS
*Owners: Kaysha (design) + Arya (Redis) + Aaryahi (into model)*
- [~] **Transaction context** — amount, timestamp, channel, hour, weekend flag
- [ ] **Historical behavior** — sender past-txn count, days since first seen, prior decisions
- [ ] **Device signals** — device seen-before flag, new-device flag, device-change velocity
- [ ] **Beneficiary history** — first-time-to-receiver flag, receiver age, sender↔receiver pair count, receiver prior-fraud flag
- [~] **Spending patterns** — velocity (tx_count_1h / 24h / 7d), amount z-score vs history, spike flag
- [ ] Feature assembler guarantees all 5 families populate every call
- [ ] Cold-start defaults for unknown sender/receiver (no crash on first-seen)
- [ ] Train/serve feature parity check (no skew/leakage)

### 1.3 Dynamic risk score
*Owners: Aaryahi + Kaysha*
- [x] Continuous score in `[0,1]`
- [~] Trained classifier present *(GradientBoosting on synthetic → upgrade in 2.1)*
- [ ] Calibrated probability (0.7 ≈ 70% risk)
- [ ] Deterministic + versioned

### 1.4 Adaptive verification ("don't treat every txn equally" — the core ask)
*Owners: Arya + Aaryahi*
- [x] Three-tier outcome: approve / step-up / block
- [x] Threshold routing (approve `<0.3`, step-up `0.3–0.7`, block `>0.7`)
- [ ] Distinct action payload per tier (approve=pass · step-up=OTP challenge object · block=reason + analyst alert)
- [ ] Reason code on every decision
- [ ] "Why not auto-approved" message for step-up/block

### 1.5 Explainability (judges always ask "why?")
*Owners: Aaryahi + Nihanshi*
- [x] SHAP contributions per transaction returned
- [x] Top risk drivers surfaced
- [ ] SHAP as `{ feature_name: contribution }` dict in response body
- [ ] Human-readable reason strings mapped from SHAP features

### 1.6 Configurable thresholds (bank policy, no ML expertise)
*Owners: Paridhi + Nihanshi*
- [x] Live threshold sliders (approve / block / puppet)
- [~] Re-decides on-screen instantly *(client-side only — persist server-side)*
- [ ] `POST /api/v1/admin/thresholds` — persist to Redis config
- [ ] Threshold change audited (who / when / old→new)

### 1.7 Persistence & audit (RBI-compliance story)
*Owners: Arya*
- [~] In-memory store *(replace with PostgreSQL)*
- [ ] Every decision → immutable Postgres audit row
- [ ] Queryable decision log
- [ ] Full audit trail export by txn_id

### 1.8 Real-data credibility
*Owners: Aaryahi + Kaysha*
- [~] Small synthetic dataset *(prototype stand-in)*
- [ ] Train on **IEEE-CIS** (590K txns, 394 features)
- [ ] Stratified train/test split + **SMOTE** (imbalanced-learn) on train only
- [ ] Tune XGBoost (learning_rate, max_depth, n_estimators, scale_pos_weight)
- [ ] Report F1 / precision / recall / FPR + confusion matrix (honest numbers)
- [ ] `joblib.dump` model + SHAP explainer, versioned with timestamp

**✅ Layer 1 exit:** one API call → all 5 signal families computed → calibrated 0–1 score + SHAP dict + one of 3 adaptive actions → persisted to Postgres → thresholds bank-configurable.

---

## LAYER 2 — INNOVATION / DEPLOYABILITY (the "ships Monday" layer) — SHOULD HAVE

*The brief's Section 6 operational layers = each is one FastAPI endpoint + one Postgres table + one React component. Backend/logic here; UI in Layer 4.*

### 2.1 ML ensemble
*Owners: Aaryahi*
- [~] Single classifier → **XGBoost** primary (predict_proba)
- [ ] **Isolation Forest** unsupervised anomaly score
- [ ] Ensemble combine (weighted avg or max of supervised + anomaly)
- [ ] Probability calibration

### 2.2 Feature engine — 30+ signals
*Owners: Kaysha*
- [ ] Reach **30+ engineered features** across the 5 families
- [ ] Feature registry (name / family / source / dtype)
- [ ] Unit tests per feature transform

### 2.3 Redis feature store + sub-100ms path
*Owners: Arya + Kaysha*
- [~] In-memory → **Redis**: `user:{id}:tx_count_1h|24h|7d` (TTL), `:avg_amount`, `:last_beneficiaries`, `:last_tx_time`
- [ ] Warm Redis from Postgres on startup
- [ ] Per-request latency logged; prove **p95 < 100ms**
- [ ] Latency budget honored: ingest ~5ms · features ~10ms · ML ~30ms · graph ~20ms · decision+SHAP ~15ms

### 2.4 Decision engine (aggregator)
*Owners: Arya*
- [ ] Merge ML score + Isolation Forest + graph flags + rule output → final decision
- [ ] Documented precedence order
- [ ] Every contributing signal echoed in response

### 2.5 Custom rule engine — `CRUD /api/v1/rules`
*Owners: Arya + Paridhi*
- [~] Puppet rule hardcoded → generalize to IF/AND/THEN evaluator
- [ ] Postgres `rules` table (condition_json, action, priority, active, created_by)
- [ ] Rules augment (+score) OR override (block regardless)
- [ ] Rule priority + conflict resolution
- [ ] Per-rule performance (catches, FPR)
- [ ] Deploy same-day, zero retraining (config not code)

### 2.6 Feedback loop + retraining — `POST /api/v1/feedback`
*Owners: Aaryahi + Arya*
- [ ] Analyst confirm/override → labeled row in Postgres
- [ ] Retrain trigger: "Retrain Now" button (or every N labels)
- [ ] Champion/challenger: new model vs old on recent data → promote if better
- [ ] Model registry + **hot-swap** (no downtime) + rollback

### 2.7 Alert grouping — `GET /api/v1/alerts/grouped`
*Owners: Kaysha*
- [ ] Group by same beneficiary (24h) / same sender pattern / same graph cluster
- [ ] Each group = case: summary, total-at-risk, txn count, priority = loss × confidence
- [ ] 500 alerts → ~30 cases story

### 2.8 Model health — `GET /api/v1/admin/model-health`
*Owners: Aaryahi*
- [ ] Postgres `model_metrics` (timestamp, version, f1, precision, recall, fpr)
- [ ] Metrics computed from feedback data
- [ ] Drift detection (feature-importance shift over time)
- [ ] System stats: API latency p50/p95/p99, volume, alert count

### 2.9 Threshold replay — `GET /api/v1/admin/threshold-preview`
*Owners: Paridhi*
- [ ] Replay last ~1000 scores at proposed thresholds
- [ ] Return approve/step-up/block distribution + estimated FPR

### 2.10 Resilience / fallbacks (huge for "deployable" credibility)
*Owners: Arya + Bhoomi*
- [ ] Redis down → fall back to Postgres
- [ ] Model missing → rule-based scorer
- [ ] WebSocket drop → auto-reconnect + polling
- [ ] Offline mode: full stack runs on a laptop via Docker Compose (zero cloud)

---

## LAYER 3 — NOVELTY (the 4 differentiators no other team builds) — HEADLINE

> Section 5 of the brief. Each is a feature-engineering module that feeds the existing pipeline — not a separate system. Judges reward one deep novel feature over three shallow ones. **5.1 puppet is your headline; ship it first and fully.**

### 3.1 Puppet signature detection (coercion / "digital arrest")
*Owners: Aaryahi + Kaysha*
- [x] Puppet rule live (Section 5.1) + puppet_score threshold slider + "digital arrest" scenario
- [ ] `amount_regularity` — std/mean of last 5 amounts (low = mechanical)
- [ ] `timing_regularity` — std of inter-txn intervals (low = puppet)
- [ ] `new_beneficiary_burst` — new beneficiaries in last 30 min
- [ ] `session_linearity` — transfers sequential, no browse/balance-check
- [ ] Combine → `puppet_score`, fed as a model feature AND evaluated by rule engine
- [ ] Rule: `puppet_score > 0.7 AND session_amount > ₹1,00,000` → force human review
- [ ] Coercion explanation surfaced to analyst
- [ ] puppet_score computed on every txn (not just the scenario)

### 3.2 UPI-specific deep features *(the pillar missing from v1)*
*Owners: Kaysha + Paridhi*
- [ ] `vpa_entropy` — Shannon entropy of VPA handle (random `x8k2m@ybl` = high)
- [ ] `collect_pay_ratio` — collect requests received / pay sent (target = high)
- [ ] `channel_switch_flag` — UPI→NEFT/IMPS jump for large amount (limit-bypass)
- [ ] `time_deviation` — hours from user's median txn time (3am to new payee = signal)
- [ ] `interbank_ratio` — % of txns crossing bank boundaries
- [ ] Festival-season baseline shift (Diwali/Holi) to cut false positives
- [ ] All fed into XGBoost as extra features
> Note: brief flags these as "CUT FIRST" beyond basics (hard to demo without real UPI data). Do `vpa_entropy` + `time_deviation` for the demo; leave the rest as "designed, production-ready."

### 3.3 Temporal graph evolution + pre-approval simulation
*Owners: Arya + Aaryahi*
- [~] Graph analysis is a **stub** today
- [ ] Build txn graph in **NetworkX** (accounts=nodes, txns=edges), init from Postgres
- [ ] Sliding-window metrics: PageRank, clustering coeff, degree over 1h/24h/7d
- [ ] Delta features: `pagerank_delta_24h`, `clustering_delta_7d`, `degree_delta_1h` (spike = mule activation)
- [ ] **Pre-approval sim:** temp `add_edge` → cycle check (`has_path` back to origin = layering) → local PageRank change → bridges two suspicious clusters? → `remove_edge`
- [ ] Local-neighborhood compute only, **~20ms** (no full recompute)
- [ ] Flags feed the aggregator; completes a circuit → block
- [ ] `GET /api/v1/graph/node/{user_id}` + `GET /api/v1/graph/subgraph/{user_id}?depth=2`

### 3.4 Fraud contagion modeling (epidemiology → fintech)
*Owners: Arya + Nihanshi*
- [~] Listed, **not built**
- [ ] Trigger: analyst confirms fraud → Celery `contagion_propagation(fraud_account_id)`
- [ ] **BFS from fraud node, depth 3**; `exposure = base × decay^distance × recency_weight`
- [ ] Store `user:{id}:exposure_score` in Redis → raises next-txn base score
- [ ] Proactive "likely-next-victim" alert
- [ ] Model as SIR (Susceptible→Infected→Recovered)

**⭐ Layer 3 exit:** "digital arrest" fires puppet (3.1); "mule ring" fires graph+contagion (3.3/3.4). You can point to the exact signal that caught each.

---

## LAYER 4 — DYNAMIC WEBSITE UI/UX

### 4.1 Real-time core
*Owners: Nihanshi + Bhoomi*
- [x] Overview dashboard with live pipeline status + counters (scored / blocked / avg)
- [x] "Start live traffic" simulator → wire to real feed
- [x] `WS /ws/transactions` WebSocket feed (replace Axios 2s polling)
- [x] Notification toasts for high-risk alerts
- [x] Connection status + auto-reconnect

### 4.2 Score & Decide panel
*Owners: Nihanshi*
- [x] Manual score form (sender, receiver, amount, channel, timestamp)
- [x] Live preview slider
- [x] Result card with approve/step-up/block bar
- [ ] Full reason codes + which subsystem fired
- [x] Risk gauge (doughnut, SVG)
- [x] Copy request/response as JSON (judge-friendly)

### 4.3 Live transaction feed
*Owners: Nihanshi*
- [x] Feed table (time / sender / receiver / amount / channel / score / decision)
- [x] Color-coded rows (green/yellow/red)
- [x] Row click → full explanation drill-down
- [x] Filters (channel, decision, score range)

### 4.4 Explainability visuals
*Owners: Nihanshi + Bhoomi*
- [x] SHAP contribution bars + "what's driving risk" (avg |SHAP|)
- [ ] **SHAP waterfall** per single decision
- [ ] Plain-English driver summary

### 4.5 Transaction graph viz ("wow" visual)
*Owners: Nihanshi + Paridhi*
- [x] **React Force Graph / D3** force-directed network (d3-force)
- [x] Nodes colored by risk (green/yellow/red)
- [x] Click node → details + recent txns + metrics
- [x] Highlight detected cycles / mule clusters (Tarjan SCC + fan-in, client-side over the live subgraph)
- [x] Pre-approval sim animation (new edge → re-decide) — `POST /api/v1/graph/simulate-edge`, non-mutating, animated ghost edge; reports the real, documented graph-flag effect (CYCLE_DETECTED forces block) without faking an ML re-score

### 4.6 Analyst Workbench (Section 6.1)
*Owners: Nihanshi + Arya + Bhoomi*
- [x] Flagged-txn list, expandable cards
- [x] Card: details + risk gauge + SHAP waterfall + graph neighborhood mini-view
- [x] Buttons: "Confirm Fraud" / "Override–Approve" + reason dropdown → `POST /feedback`
- [x] Override tracking (analyst accuracy, live from `/api/v1/feedback/stats`)
- [x] Case linking (grouped related txns, live from `/api/v1/score/linked/{txn_id}`)

### 4.7 Threshold Control Panel (Section 6.2)
*Owners: Nihanshi + Paridhi*
- [x] Sliders exist on overview
- [x] Dedicated admin panel with **live preview chart** (pie: approve/step-up/block at proposed thresholds)
- [x] Seasonal presets: "Festival mode" widens approve band, "High alert" tightens
- [x] Persist to server + guardrail (block can't be < approve)

### 4.8 Custom Rule Builder UI (Section 6.3)
*Owners: Paridhi + Bhoomi*
- [x] Form with dropdowns: field / operator / value / action
- [x] Enable-disable + priority ordering
- [x] Preview how many past txns a rule would catch (`POST /api/v1/rules/preview`)
- [x] Push live (no redeploy)

### 4.9 Fraud Contagion Heatmap (Section 5.4 viz)
*Owners: Nihanshi*
- [x] Graph nodes colored by exposure score, hop-distance shading (1→3, live from `/api/v1/graph/exposed`; also drives ForceGraph node color in contagion mode)
- [x] "Watch fraud spread" animation — manual replay of the real per-hop exposure data (no persisted per-event timeline exists to auto-trigger on confirm-fraud, so this is an honest replay button, not a live event hook)
- [x] Toggle contagion overlay on the graph (now applies to the live force-directed graph, not just the decorative fallback)

### 4.10 Model Health Monitor page (Section 6.6)
*Owners: Nihanshi + Bhoomi*
- [x] Line graphs: F1 / precision / recall / FPR over each recorded evaluation, live from `metrics_history` (falls back to the illustrative 90d mock until ≥2 retrains exist)
- [x] Drift indicator
- [x] System panel: latency p50/p95/p99, volume, alert count
- [x] Model version history + comparison

### 4.11 Existing analytics (keep + polish)
*Owners: Bhoomi + Paridhi*
- [x] Risk trend · decisions breakdown · traffic by channel · risk-vs-amount scatter · senders-to-watch
- [ ] Consistent colors / spacing / typography across all pages
- [ ] Loading + empty + error states everywhere
- [ ] Responsive / laptop-projector-safe layout

### 4.12 Demo tooling
*Owners: Kaysha + Arya*
- [x] Scenarios: normal_traffic · digital_arrest · mule_ring — injected as real payloads into `POST /api/v1/score` (no separate `/simulate` endpoint exists or is needed)
- [x] Add **smurfing** (many small amounts under reporting threshold)
- [x] "Run scenario" → plays out live against the real scoring pipeline
- [x] One-click reset / guided demo mode
- [ ] Keep the honesty modal updated per phase

---

## Recommended build order (dependency-based, no timelines)

1. **Layer 0 + Layer 1** — deployable scoring API, Docker Compose, IEEE-CIS model, 5 signal families, adaptive decision, SHAP, Postgres audit. *Pass/fail for the PS.*
2. **2.1 + 2.3** — XGBoost + Isolation Forest, Redis, prove p95<100ms. *Makes "real-time" true.*
3. **3.1 puppet (all 4 sub-signals)** — headline novelty, already half-built.
4. **4.1 + 4.3 + 4.5** — WebSocket feed + graph viz. *The visual product.*
5. **3.3 graph sim** → **4.6 analyst workbench** → **2.6 feedback loop.** *Closes the learn loop.*
6. **3.4 contagion + 4.9 heatmap.** *Stunning but complex — nice-to-have.*
7. Everything else = polish / stretch.

## Cut order if time runs out (from the brief's priority matrix)
- **MUST:** scoring API + SHAP · Docker Compose · dashboard feed + gauge · ≥2 scenarios · **puppet detection**
- **SHOULD:** graph viz · pre-approval sim · analyst workbench · threshold panel
- **NICE:** contagion heatmap · rule-engine UI · alert grouping · model-health · WebSocket (polling is fine for demo)
- **CUT FIRST:** UPI features beyond basics · live retraining (show the button) · drift detection

> Golden rule from the brief: **a working Phase 0+1 with puppet detection beats an ambitious broken Phase 3 every time.**
