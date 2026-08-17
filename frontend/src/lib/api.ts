// RiskPulse — real backend client for the score/decide + live feed path.
//
// Talks to the FastAPI backend's POST /api/v1/score. Every call is
// wrapped so a caller can fall back to the existing simulated behavior
// (see mock.ts's genTxn) if the backend isn't reachable — this keeps the
// console usable standalone for demo purposes even with no backend
// running, matching the brief's own resilience philosophy.

export const API_BASE_URL: string =
  (import.meta as unknown as { env: Record<string, string | undefined> }).env.VITE_API_BASE_URL ||
  'http://localhost:8000';

// Fixed demo credential — matches the backend's default DEMO_USERNAME /
// DEMO_PASSWORD (backend/app/config.py). There's no real user system yet;
// this is enough to exercise genuine JWT issuance + verification end to end.
const DEMO_USERNAME = 'demo_admin';
const DEMO_PASSWORD = 'riskpulse-demo';

const REQUEST_TIMEOUT_MS = 4000;

export interface ScorePayload {
  amount: number;
  sender_id: string;
  receiver_id: string;
  timestamp: string;
  channel: string;
  vpa?: string;
  device_type?: string;
  device_info?: string;
  browser?: string;
  os?: string;
}

export interface ShapReasonDTO {
  feature: string;
  contribution: number;
  reason: string;
}

export interface ScoreResponseDTO {
  txn_id: string;
  risk_score: number;
  decision: 'approve' | 'step_up' | 'block';
  shap_values: Record<string, number>;
  shap_reasons: ShapReasonDTO[];
  puppet_score: number;
  graph_flags: string[];
  model_version: string;
  reason_code: string;
  coercion_override: boolean;
  coercion_reason: string | null;
  action: Record<string, unknown>;
  idempotent_replay: boolean;
}

function withTimeout(ms: number): { signal: AbortSignal; cancel: () => void } {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, cancel: () => clearTimeout(id) };
}

let cachedToken: string | null = null;
let tokenPromise: Promise<string> | null = null;

async function fetchToken(): Promise<string> {
  const { signal, cancel } = withTimeout(REQUEST_TIMEOUT_MS);
  try {
    const body = new URLSearchParams({ username: DEMO_USERNAME, password: DEMO_PASSWORD });
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
      signal,
    });
    if (!res.ok) throw new Error(`auth/token failed: ${res.status}`);
    const json = (await res.json()) as { access_token: string };
    return json.access_token;
  } finally {
    cancel();
  }
}

async function getToken(forceRefresh = false): Promise<string> {
  if (cachedToken && !forceRefresh) return cachedToken;
  if (!tokenPromise || forceRefresh) {
    tokenPromise = fetchToken().then((t) => {
      cachedToken = t;
      return t;
    });
  }
  return tokenPromise;
}

/** Backend unreachable, CORS failure, timeout, non-2xx, etc. — callers
 * should catch this and fall back to the existing simulated behavior. */
export class BackendUnavailableError extends Error {}

export async function scoreTransaction(payload: ScorePayload): Promise<ScoreResponseDTO> {
  let token: string;
  try {
    token = await getToken();
  } catch (e) {
    throw new BackendUnavailableError(`could not authenticate with backend: ${e}`);
  }

  const doScore = async (bearer: string) => {
    const { signal, cancel } = withTimeout(REQUEST_TIMEOUT_MS);
    try {
      return await fetch(`${API_BASE_URL}/api/v1/score`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${bearer}`,
        },
        body: JSON.stringify(payload),
        signal,
      });
    } finally {
      cancel();
    }
  };

  try {
    let res = await doScore(token);
    if (res.status === 401) {
      // token may have expired; refresh once and retry
      token = await getToken(true);
      res = await doScore(token);
    }
    if (!res.ok) {
      throw new Error(`score failed: ${res.status}`);
    }
    return (await res.json()) as ScoreResponseDTO;
  } catch (e) {
    throw new BackendUnavailableError(`scoreTransaction failed: ${e}`);
  }
}
