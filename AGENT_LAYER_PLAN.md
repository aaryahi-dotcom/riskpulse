# Agent Layer Implementation Plan

**Status**: Ready for review  
**Build Start Order**: Follow the 8 stages below; commit after each.

---

## Design: Grey-Zone Gating

Currently, the decision engine maps `augmented_score` directly to tiers via thresholds:
- approve: score < 0.35
- step_up: 0.35 ≤ score < 0.65
- block: score ≥ 0.65

**New design**: Thresholds become a *two-stage gate*:
1. **Fast path** (existing): If score < grey_zone_lower (e.g., 0.35) → ALLOW (no agents)
   - If score ≥ grey_zone_upper (e.g., 0.75) → BLOCK/HOLD (no agents)
2. **Agent path** (new): If grey_zone_lower ≤ score < grey_zone_upper → run agent pipeline

**Why**: Most transactions are clear-cut (obvious fraud/legitimate). Agents only for ambiguous edge cases.

**Config**:
- `GREY_ZONE_LOWER` (default 0.35)
- `GREY_ZONE_UPPER` (default 0.75)
- Both configurable via `/api/v1/admin/thresholds` (extend ThresholdConfig)
- `MOCK_LLM` env var: if set, agents return canned responses (offline demo mode)

---

## LLM Architecture

### Prompts File
**New file**: `backend/app/agents/prompts.py`
- One Python module holding all LLM prompts
- Exported as structured functions (e.g., `prompt_signal_agent(signals: dict) -> str`)
- Each prompt is a docstring or template with placeholders
- Examples for mock responses built-in (e.g., if `MOCK_LLM=1`, return canned JSON)

### Agent Response Format
Every agent returns **strict JSON** + a one-line reasoning string.

**Standard JSON wrapper**:
```json
{
  "agent": "signal_agent",
  "status": "success",
  "output": { /* agent-specific */ },
  "reasoning": "One-line summary of why this output was produced."
}
```

### API Integration
- Read `ANTHROPIC_API_KEY` from `.env` (or raise error if not set)
- If `MOCK_LLM=1`, skip HTTP call, return canned response immediately
- Use Claude API (Messages) with a single system prompt + user message per call
- No streaming (for now); collect full response, parse JSON

---

## Five Agents (in priority order for implementation)

### 1. **Decision Agent** ⭐ (Implement First)
**Purpose**: Combines base risk score + eventual agent outputs → one explainable verdict.

**Input**:
```python
{
  "ml_score": 0.52,
  "augmented_score": 0.55,
  "puppet_score": 0.3,
  "amount": 50000,
  "channel": "upi",
  "sender_id": "user_123",
  "receiver_id": "user_456",
  "signals": { ... },  # placeholder for signal_agent output (if available)
  "scam_type": "...",  # placeholder for scam_pattern_agent output (if available)
  "friction_result": { ... }  # placeholder for friction_agent output (if available)
}
```

**Output**:
```json
{
  "verdict": "ALLOW" | "COOL_OFF" | "ALERT_TRUSTED_CONTACT" | "BLOCK",
  "explanation_en": "This transaction appears safe because...",
  "explanation_hi": "यह लेन-देन सुरक्षित दिखता है क्योंकि...",
  "factors": [
    { "name": "Low historical amount variance", "weight": 0.15, "direction": "positive" },
    { "name": "New beneficiary", "weight": 0.20, "direction": "negative" }
  ],
  "confidence": 0.85,
  "reasoning": "Risk score (0.55) is moderate; no coercion signals detected; new payee is only concern."
}
```

**Fallback**: If agents fail, use old three-tier thresholding (backward compat).

**Success Criteria**:
- Verdict is one of 4 expected strings
- explanation_en and explanation_hi are non-empty
- factors array has 3–5 items with name/weight/direction
- Visible in UI response

---

### 2. **Friction Agent** ⭐⭐ (Prioritize After Decision Agent)
**Purpose**: Holds a short adaptive conversation (3–4 turns max) to detect user coercion.

**Interaction Flow**:
1. Agent asks user a question (e.g., "Is someone on a call with you right now?")
2. User picks from options or types freeform
3. Agent evaluates answer; decides next question or final verdict
4. UI shows conversation; backend tracks coercion_likelihood (0–1)

**Backend Integration**:

Add to `/api/v1/score` response:
```python
"friction": {
  "enabled": True,  # if in grey zone
  "status": "not_started" | "in_progress" | "completed",
  "current_question": "...",  # if in_progress
  "options": ["Yes", "No", "Not sure"],  # if in_progress
  "conversation_history": [...],  # completed turns
  "coercion_likelihood": 0.75,  # final (if completed)
  "key_answers": ["Said not to tell family", "Police mentioned"],  # if completed
  "reasoning": "..."
}
```

**Agent Questions** (template examples for scam types):
- Digital arrest: "Did someone say you are under investigation or arrest?"
- Fake KYC: "Were you told your account will be blocked?"
- Sextortion: "Were you threatened with sharing private videos/images?"
- Generic: "Were you told to keep this secret from your family?"

**Important Design**: Questions should be **order-randomized** and **wording-varied** per turn so scammers coaching the victim can't predict them.

**Mock Mode** (`MOCK_LLM=1`):
- Return 2–3 pre-written questions in sequence
- Simulate user answers (backend chooses for demo)

**Success Criteria**:
- Conversation shows in UI
- User can select options
- Each turn produces a new question or final verdict
- Final `coercion_likelihood` influences Decision Agent output

---

### 3. **Signal Agent**
**Purpose**: Collects and normalises contextual signals into a structured object.

**Input**:
- Current transaction payload (amount, channel, payee, etc.)
- Device state toggles from UI (call active, screen-share open, etc.)
- Recent SMS/note text (optional, user-pasted)

**Output**:
```json
{
  "signals": {
    "active_call_during_payment": true,
    "remote_access_app_open": false,
    "new_or_first_time_payee": true,
    "amount_unusual_vs_history": 0.75,  // 0-1 score
    "unusual_time_of_day": false,
    "hesitation_signals": { "pin_retries": 2, "pauses_long": true, "navigation_backtrack": false },
    "payment_note_text": "Please send urgently",
    "recent_sms_snippet": "..."
  },
  "top_concerns": [
    "Active phone call during high-amount payment",
    "New beneficiary + first-time large transfer",
    "Note uses urgency language (send urgently)"
  ],
  "reasoning": "Multiple signals suggest potential external pressure or influence."
}
```

**Mock Mode**:
- Return canned signals based on scenario picker (see UI section)

---

### 4. **Scam-Pattern Agent**
**Purpose**: Classify the likely scam type from signals + payment note/SMS.

**Output**:
```json
{
  "scam_type": "digital_arrest" | "fake_kyc_update" | "electricity_bill" | "courier_item" | "task_based_investment" | "sextortion" | "relative_impersonation" | "none_or_unclear",
  "confidence": 0.85,
  "matched_cues": [
    "\"police\", \"cbi\", \"customs\"",
    "\"verify account\", \"confirm identity\"",
    "\"urgent\" language"
  ],
  "reasoning": "Multiple police/authority keywords + urgency + first-time payee pattern strongly suggests digital arrest scam."
}
```

**Scam Type List** (from brief):
1. Digital arrest / fake police-CBI-customs
2. Fake KYC update / account block
3. Electricity bill disconnection
4. Courier / parcel with illegal items
5. Task-based / investment / trading scam
6. Sextortion / blackmail
7. Relative-in-emergency impersonation
8. None / unclear

---

### 5. **Guardian Agent** (Nice-to-have, defer if time runs out)
**Purpose**: Drafts a message to a pre-set trusted contact if verdict is ALERT/BLOCK.

**Output**:
```json
{
  "message_en": "Your mother may be on a scam call trying to send ₹48,000 — please call her now.",
  "message_hi": "आपकी माँ को धोखाधड़ी की कॉल पर ₹48,000 भेजने की कोशिश की जा रही हो सकती है — अभी उसे कॉल करें।",
  "reasoning": "Digital arrest pattern detected; trusted contact is mother (stored in profile)."
}
```

**UI Mock**: Show in a notification panel; don't actually send.

---

## Backend Implementation Order

### Stage 1: Grey-Zone Gate + Decision Agent (Mock)
**Commit**: "Add grey-zone gating and Decision Agent with mock LLM mode"

1. Extend `ThresholdConfig` table to include `grey_zone_lower`, `grey_zone_upper`
2. Add `MOCK_LLM`, `ANTHROPIC_API_KEY` to `.env.example` and `config.py`
3. Create `backend/app/agents/` directory
4. Write `backend/app/agents/prompts.py` with:
   - `prompt_decision_agent(...)` function
   - Mock response for Decision Agent (canned JSON)
5. Modify `/api/v1/score` endpoint:
   - After `aggregate_decision()`, check if `augmented_score` in grey zone
   - If yes: call Decision Agent (mock for now)
   - If no: use old three-tier logic (backward compat)
6. Add Decision Agent response to `ScoreResponse` schema
7. Test: POST `/api/v1/score` with mid-range score (0.4–0.7), confirm agent is called

---

### Stage 2: Friction Agent in Backend (Mock)
**Commit**: "Add Friction Agent with multi-turn conversation support"

1. Create `backend/app/agents/friction.py` with stateful conversation manager
2. Store conversation state in `backend/models_db.py`: new table `FrictionSession`
   - Fields: session_id, txn_id, turn_count, conversation_json, coercion_likelihood, status
3. Add endpoints:
   - `POST /api/v1/score` with new optional body field `friction_turn=0` (or session_id)
   - `POST /api/v1/friction/{session_id}/answer` to submit user answer + move to next turn
4. Friction Agent returns question + options (mock for now; real LLM later)
5. Track conversation history; final turn returns `coercion_likelihood`
6. Add Friction response to `ScoreResponse`

---

### Stage 3: Right-Hand "Brain" Panel (UI + Backend Trace)
**Commit**: "Add live agent trace visualization to Score & Decide panel"

1. Extend `ScoreResponse` with agent trace:
   ```python
   "agent_trace": {
     "base_score": 0.52,
     "agents_run": [
       { "agent": "decision_agent", "status": "success", "reasoning": "..." },
       { "agent": "friction_agent", "status": "pending", "question": "..." }
     ],
     "final_verdict": { "verdict": "COOL_OFF", "explanation_en": "..." }
   }
   ```
2. Frontend: new component `BrainPanel` on right side of Score & Decide
   - Show base_score
   - Animate each agent lighting up as it completes (streaming simulation)
   - Display reasoning one-liner from each
   - Show live friction question + options
   - Final verdict card with explanation + factor bars

---

### Stage 4: Scenario Picker (UI + Mock Signals)
**Commit**: "Add 3-preset scenario picker for demo"

1. Frontend: new dropdown/modal with 3 buttons:
   - "Digital Arrest Victim" (sets fields for scam demo)
   - "Large New Payee, No Call" (sets fields for legitimate edge case)
   - "Fake KYC + Remote Access" (sets fields for sophisticated fraud)
2. Each scenario pre-fills:
   - Transaction fields (amount, receiver, vpa)
   - Signal toggles (call active, AnyDesk open, etc.)
   - Expected outcome annotation
3. One-click runs full pipeline

---

### Stage 5: Signal Agent (Mock)
**Commit**: "Add Signal Agent to detect coercion signals"

1. Add `backend/app/agents/signals.py`
2. Implement signal detection:
   - UI toggles converted to structured signals dict
   - Amount variance computed from feature store
   - Payment note analysis (keyword matching for urgency, threat, etc.)
3. Signal Agent LLM call (mock for now) returns `top_concerns`
4. Integrate into Decision Agent input

---

### Stage 6: Scam-Pattern Agent
**Commit**: "Add Scam-Pattern Agent to classify fraud type"

1. Add `backend/app/agents/scam_pattern.py`
2. Scam-pattern LLM call (mock for now)
3. Used by Friction Agent to select questions dynamically
4. Integrate into Decision Agent input

---

### Stage 7: Hindi Localization
**Commit**: "Add Hindi translations for friction questions and verdict"

1. All Friction Agent questions: EN/HI toggle support
2. Decision Agent explanations already have `explanation_hi`
3. Frontend: Language toggle in header

---

### Stage 8: Real LLM Integration (Replace Mock Mode)
**Commit**: "Integrate Claude API for all agents"

1. Implement real API calls in each agent (not just mock)
2. Add retries, error handling, timeout
3. Log API calls for audit trail
4. Remove `MOCK_LLM` override when `ANTHROPIC_API_KEY` is set

---

### Optional: Cool-Off Countdown + Guardian Mock Notification
**Commits**:
- "Add cool-off countdown timer for COOL_OFF verdicts"
- "Add mock guardian notification panel (no real sends)"

---

## Frontend Implementation (Parallel to Backend)

### Stage 1–3: UI Scaffolding
- Two-pane layout: left = payment form + demo controls, right = brain panel
- Mock controls drawer with signal toggles
- Brain panel skeleton (shows agent progression)

### Stage 4: Scenario Picker
- Dropdown with 3 presets
- One-click scenario loading

### Stage 5+: Integration
- Connect to live `/api/v1/score` responses
- Friction questions rendered with option buttons
- Live factor bars in verdict card

---

## Testing Strategy

1. **Unit Tests**:
   - Each agent's prompt formatting and mock response parsing
   - Grey-zone logic (stage 1)
   - Friction conversation state management (stage 2)

2. **Integration Tests**:
   - Full `/api/v1/score` flow with grey-zone transaction
   - Friction multi-turn conversation
   - Decision Agent output is valid

3. **Manual Tests** (after UI complete):
   - Use scenario picker to run each demo scenario
   - Watch live trace on right panel
   - Confirm friction questions appear/advance
   - Confirm final verdict is explainable

---

## Fallback & Safety

- If agents fail (API down, timeout, parse error): use old three-tier thresholding
- All agent responses logged in `ScoredTransaction.full_response_json` for audit
- Mock mode (`MOCK_LLM=1`) enables offline demo without API key

---

## Success Criteria (Hackathon Judges)

1. ✓ Grey-zone detection works (fast path for obvious cases)
2. ✓ Friction Agent holds a real conversation with the user
3. ✓ Decision Agent produces explainable verdict (factors + weights visible)
4. ✓ Demo UI shows agent trace "brain" lighting up in real-time
5. ✓ Scenario picker works: 3 presets run end-to-end
6. ✓ Hindi support for friction questions
7. ✓ Calmness & trustworthiness in UI (not alarming)

---

## Commit Message Template

```
{Title}: {Brief what changed}

{Body}: Why this was done. Link related stages.

Example:
  Stage 1: Add grey-zone gating and Decision Agent with mock LLM mode
  
  - Extend ThresholdConfig with grey_zone_lower/upper
  - Create agents/prompts.py with Decision Agent template
  - Backend /api/v1/score checks grey zone before old thresholds
  - Mock LLM mode for offline demo
  - Tests: score in grey zone → agent called
  
  Prerequisite: .env updated with MOCK_LLM=1 and (optionally) ANTHROPIC_API_KEY
```

---

**Ready to start Stage 1?** I'll begin with grey-zone gating + Decision Agent (mock).
