# Update Report — Layer 4 explainability close-out

**Date:** 2026-08-22
**Scope:** Closing the last two open items under `BUILD_CHECKLIST.md` § 4.4 (Explainability visuals) — SHAP waterfall and plain-English driver summary.

## Summary

`BUILD_CHECKLIST.md` § 4.4 had two unchecked boxes:

- `[ ] SHAP waterfall per single decision`
- `[ ] Plain-English driver summary`

Auditing the code found the waterfall already existed (diverging per-feature
bars from a shared center baseline, in both the Score & Decide panel and the
Analyst Workbench) — it was just never checked off. The real gap was the
driver summary: the backend already computed human-readable reason
sentences (`shap_to_reasons()` in `backend/app/decision.py`) but only used
them internally to build OTP/block action messages. They never reached the
UI as a standalone summary.

## Changes

### Backend
- `backend/app/routers/score.py` — added `shap_reasons` (serialized via
  `.model_dump()`) to the `/ws/transactions` broadcast payload, alongside
  the existing `shap_values`. Previously only the direct HTTP response
  carried reason text; live-feed rows arriving over the socket had none.

### Frontend
- `frontend/src/state/useRiskPulse.ts` — added `shapReasonsMap` state
  (parallel to the existing `shapMap`), populated from both the WS handler
  and the HTTP fallback path. Added a `shapReasons` memo: real reason
  sentences for the selected transaction when available, else a
  mock-name → sentence lookup for the illustrative demo rows.
- `frontend/src/lib/mock.ts` — added `MOCK_SHAP_REASONS`, a small
  feature-name → sentence table covering the fixed demo `SHAP` array, so
  mock/illustrative rows show real sentences instead of raw feature names.
- `frontend/src/components/console/dashboard/LayoutA.tsx` and
  `frontend/src/components/console/Workbench.tsx` — render `rp.shapReasons`
  as a sentence list under the SHAP waterfall.

### Tests
- `backend/tests/test_ws_shap_reasons.py` (new) — opens a real WebSocket
  connection, triggers a score, and asserts the broadcast frame's
  `shap_reasons` matches the HTTP response exactly. This closes a real gap:
  the WS broadcast call is wrapped in a silent `try/except`, so a
  serialization bug there would never have failed the existing suite — it
  would just quietly drop reason text from the live feed with nothing
  surfacing the failure.

### Docs
- `BUILD_CHECKLIST.md` — checked off both § 4.4 boxes with a note on what
  each now does.

## Verification

- `npx tsc -b` — clean
- `npm run build` (vite) — clean, 355 KB bundle (99.97 KB gzip)
- `python -m pytest -q` — **106/106 passing** (105 pre-existing + 1 new WS
  regression test)

## Not changed

The rest of § 4.11 (consistent colors/spacing/typography, loading/empty/
error states everywhere, responsive layout) is still open. Every screen
already degrades gracefully to mock/illustrative data on fetch failure
rather than showing a blank or broken state, so nothing is concretely
broken today — but a full audit of those three boxes hasn't been done and
isn't claimed here.

## Status

All changes are complete and verified but **not committed** — awaiting
explicit go-ahead to commit and push.
