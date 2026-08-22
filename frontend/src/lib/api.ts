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

// checklist 4.1: same host as API_BASE_URL, ws(s):// instead of http(s)://
export const WS_BASE_URL: string = API_BASE_URL.replace(/^http/, 'ws');

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

// ---------------------------------------------------------------------
// Generic authed JSON helper — shared by every Layer 4 read/write below.
// Same auth-retry-once + timeout + BackendUnavailableError contract as
// scoreTransaction, factored out so each endpoint call site stays a
// one-liner.
// ---------------------------------------------------------------------
async function authedJson<T>(path: string, init?: RequestInit): Promise<T> {
  let token: string;
  try {
    token = await getToken();
  } catch (e) {
    throw new BackendUnavailableError(`could not authenticate with backend: ${e}`);
  }

  const doCall = async (bearer: string) => {
    const { signal, cancel } = withTimeout(REQUEST_TIMEOUT_MS);
    try {
      return await fetch(`${API_BASE_URL}${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}), Authorization: `Bearer ${bearer}` },
        signal,
      });
    } finally {
      cancel();
    }
  };

  try {
    let res = await doCall(token);
    if (res.status === 401) {
      token = await getToken(true);
      res = await doCall(token);
    }
    if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
    return (await res.json()) as T;
  } catch (e) {
    throw new BackendUnavailableError(`${path} failed: ${e}`);
  }
}

export interface RuleDTO {
  id: string;
  name: string;
  description: string;
  condition_json: Record<string, unknown>;
  action: 'augment' | 'override';
  score_delta: number | null;
  forced_tier: string | null;
  priority: number;
  active: boolean;
}

export interface RuleStatsDTO {
  rule_id: string;
  rule_name: string;
  total_scored_sampled: number;
  fired_count: number;
  fire_rate: number;
  feedback_coverage: number;
  confirmed_fraud: number;
  confirmed_legit: number;
  precision_estimate: number | null;
}

export function listRules(): Promise<RuleDTO[]> {
  return authedJson<RuleDTO[]>('/api/v1/rules');
}

export function getRuleStats(ruleId: string): Promise<RuleStatsDTO> {
  return authedJson<RuleStatsDTO>(`/api/v1/rules/${ruleId}/stats`);
}

export interface RuleCreatePayload {
  name: string;
  description?: string;
  condition_json: Record<string, unknown>;
  action: 'augment' | 'override';
  score_delta?: number | null;
  forced_tier?: string | null;
  priority?: number;
}

export function createRule(payload: RuleCreatePayload): Promise<RuleDTO> {
  return authedJson<RuleDTO>('/api/v1/rules', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateRule(ruleId: string, patch: { active?: boolean; priority?: number }): Promise<RuleDTO> {
  return authedJson<RuleDTO>(`/api/v1/rules/${ruleId}`, { method: 'PATCH', body: JSON.stringify(patch) });
}

export interface RulePreviewDTO {
  sampled: number;
  matched: number;
  match_rate: number;
}

export function previewRule(conditionJson: Record<string, unknown>, n = 500): Promise<RulePreviewDTO> {
  return authedJson<RulePreviewDTO>('/api/v1/rules/preview', {
    method: 'POST',
    body: JSON.stringify({ condition_json: conditionJson, n }),
  });
}

export interface AlertCaseDTO {
  case_id: string;
  group_type: string;
  group_key: string;
  txn_count: number;
  total_amount_at_risk: number;
  avg_risk_score: number;
  priority: number;
  member_txn_ids: string[];
  exposure_score?: number;
}

export interface AlertsGroupedDTO {
  total_alerts: number;
  total_cases: number;
  cases: AlertCaseDTO[];
}

export function getAlertsGrouped(windowHours = 24): Promise<AlertsGroupedDTO> {
  return authedJson<AlertsGroupedDTO>(`/api/v1/alerts/grouped?window_hours=${windowHours}`);
}

export interface ModelHealthDTO {
  current_model_version: string;
  model_loaded: boolean;
  metrics_history: {
    model_version: string; f1: number; precision: number; recall: number;
    false_positive_rate: number; n_test_rows: number; promoted: boolean;
    trained_at: string; recorded_at: string;
  }[];
  drift: Record<string, unknown>;
  latency_ms: { count: number; p50_ms: number | null; p95_ms: number | null; p99_ms: number | null };
  request_volume: number;
  alert_count: number;
}

export function getModelHealth(): Promise<ModelHealthDTO> {
  return authedJson<ModelHealthDTO>('/api/v1/admin/model-health');
}

export interface ThresholdsDTO {
  approve_threshold: number;
  block_threshold: number;
  puppet_threshold: number;
  updated_at: string;
  updated_by: string;
}

export function getThresholds(): Promise<ThresholdsDTO> {
  return authedJson<ThresholdsDTO>('/api/v1/admin/thresholds');
}

export function updateThresholds(approve: number, block: number, puppet: number): Promise<ThresholdsDTO> {
  return authedJson<ThresholdsDTO>('/api/v1/admin/thresholds', {
    method: 'POST',
    body: JSON.stringify({ approve_threshold: approve, block_threshold: block, puppet_threshold: puppet }),
  });
}

export interface ThresholdPreviewDTO {
  sample_size: number;
  proposed_approve_threshold: number;
  proposed_block_threshold: number;
  distribution: { approve: number; step_up: number; block: number };
  estimated_fpr: number | null;
  feedback_coverage: number;
}

export function getThresholdPreview(approve: number, block: number, n = 1000): Promise<ThresholdPreviewDTO> {
  return authedJson<ThresholdPreviewDTO>(`/api/v1/admin/threshold-preview?approve=${approve}&block=${block}&n=${n}`);
}

export interface FeedbackDTO {
  id: string;
  txn_id: string;
  confirmed_label: 'fraud' | 'legit';
  analyst_note: string | null;
  overridden_decision: boolean;
}

export function submitFeedback(txnId: string, confirmedLabel: 'fraud' | 'legit', overriddenDecision = false): Promise<FeedbackDTO> {
  return authedJson<FeedbackDTO>('/api/v1/feedback', {
    method: 'POST',
    body: JSON.stringify({ txn_id: txnId, confirmed_label: confirmedLabel, overridden_decision: overriddenDecision }),
  });
}

export function getFeedbackForTxn(txnId: string): Promise<FeedbackDTO[]> {
  return authedJson<FeedbackDTO[]>(`/api/v1/feedback?txn_id=${encodeURIComponent(txnId)}`);
}

export interface FeedbackStatsDTO {
  analyst: string;
  total_reviewed: number;
  overrides: number;
  fraud_confirmed: number;
  agreement_rate: number;
}

export function getFeedbackStats(): Promise<FeedbackStatsDTO> {
  return authedJson<FeedbackStatsDTO>('/api/v1/feedback/stats');
}

export interface ExposedAccountDTO {
  user_id: string;
  exposure_score: number;
  approx_hop: number | null;
}

export function getExposedAccounts(threshold = 0.01, limit = 50): Promise<{ accounts: ExposedAccountDTO[] }> {
  return authedJson<{ accounts: ExposedAccountDTO[] }>(`/api/v1/graph/exposed?threshold=${threshold}&limit=${limit}`);
}

export interface LinkedTransactionDTO {
  txn_id: string;
  sender_id: string;
  receiver_id: string;
  amount: number;
  channel: string;
  risk_score: number;
  decision: string;
  puppet_score: number;
  model_version: string;
  created_at: string;
}

export function getLinkedTransactions(txnId: string, n = 10): Promise<LinkedTransactionDTO[]> {
  return authedJson<LinkedTransactionDTO[]>(`/api/v1/score/linked/${encodeURIComponent(txnId)}?n=${n}`);
}

export interface AuditDTO {
  txn_id: string;
  created_at: string;
  decision: string;
  risk_score: number;
}

export function getAudit(txnId: string): Promise<AuditDTO> {
  return authedJson<AuditDTO>(`/api/v1/score/audit/${encodeURIComponent(txnId)}`);
}

export interface GraphNodeDTO {
  user_id: string;
  present: boolean;
  pagerank: number;
  clustering_coefficient: number;
  degree: number;
  pagerank_delta_24h: number;
  clustering_delta_7d: number;
  degree_delta_1h: number;
}

export function getGraphNode(userId: string): Promise<GraphNodeDTO> {
  return authedJson<GraphNodeDTO>(`/api/v1/graph/node/${encodeURIComponent(userId)}`);
}

export interface SubgraphNodeDTO {
  id: string;
  suspicious: boolean;
}

export interface SubgraphEdgeDTO {
  source: string;
  target: string;
  count: number;
  total_amount: number;
}

export interface SubgraphDTO {
  user_id: string;
  depth: number;
  nodes: SubgraphNodeDTO[];
  edges: SubgraphEdgeDTO[];
}

export function getSubgraph(userId: string, depth = 2): Promise<SubgraphDTO> {
  return authedJson<SubgraphDTO>(`/api/v1/graph/subgraph/${encodeURIComponent(userId)}?depth=${depth}`);
}

export function retrainModel(): Promise<{ status: string }> {
  return authedJson<{ status: string }>('/api/v1/admin/retrain', { method: 'POST', body: JSON.stringify({}) });
}
