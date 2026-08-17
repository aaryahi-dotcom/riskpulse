// RiskPulse — client-side mock data + tiny SVG-path helpers.
// Mirrors the data shapes from the original design mockup; nothing here talks
// to a real backend. See CLAUDE-adjacent brief: "mockup, not production copy."

export const GREEN = '#4f8a72';
export const AMBER = '#b3872f';
export const RED = '#b0533f';

export const tint = (c: string) => `color-mix(in srgb, ${c} 16%, transparent)`;

export type RawTxn = [
  id: string,
  time: string,
  from: string,
  to: string,
  amount: number,
  score: number,
  puppet: number,
  flagLine: string,
];

export const RAW_SEED: RawTxn[] = [
  ['TXN-88412', '14:22:07', 'arya@okhdfc', 'x8k2m@ybl', 248000, 0.91, 0.83, 'cycle 2-hop · mule cluster'],
  ['TXN-88411', '14:21:58', 'n.desai@ybl', 'q4t7z@paytm', 199500, 0.86, 0.79, 'new benef burst'],
  ['TXN-88409', '14:21:40', 'kaysha@oksbi', 'r.mehta@ybl', 12400, 0.22, 0.11, '—'],
  ['TXN-88407', '14:21:12', 'bhoomi@apl', 'vend.kirana@sbi', 860, 0.08, 0.04, '—'],
  ['TXN-88404', '14:20:51', 'arya@okhdfc', 'x8k2m@ybl', 248000, 0.78, 0.81, 'repeat round amt'],
  ['TXN-88402', '14:20:33', 'p.rao@okaxis', 'm9v2k@ybl', 97000, 0.64, 0.42, 'centrality spike'],
  ['TXN-88399', '14:20:02', 's.iyer@ibl', 'fuel.hp@okhdfc', 3100, 0.14, 0.06, '—'],
  ['TXN-88396', '14:19:44', 'nihanshi@ybl', 'w2p8n@paytm', 49999, 0.71, 0.66, 'below-threshold split'],
  ['TXN-88393', '14:19:20', 'd.imrie@oksbi', 'rent.jain@ybl', 28000, 0.19, 0.09, '—'],
  ['TXN-88390', '14:18:57', 'aaryahi@apl', 'z6h1c@ybl', 150000, 0.83, 0.74, 'exposure 0.61'],
  ['TXN-88387', '14:18:31', 't.menon@okicici', 'grocer.day@ybl', 2240, 0.06, 0.03, '—'],
  ['TXN-88384', '14:18:04', 'paridhi@ybl', 'k3n9x@paytm', 75000, 0.58, 0.51, 'channel switch'],
  ['TXN-88381', '14:17:39', 'v.shah@oksbi', 'sal.acct@okhdfc', 64000, 0.11, 0.05, '—'],
  ['TXN-88377', '14:17:11', 'r.kaur@apl', 'y7b4d@ybl', 120000, 0.75, 0.69, '3am pattern'],
];

export const SHAP: [string, number][] = [
  ['new_beneficiary_burst', 0.22],
  ['amount_regularity', 0.19],
  ['timing_regularity', 0.14],
  ['vpa_entropy', 0.11],
  ['pagerank_delta_24h', 0.08],
  ['exposure_score', 0.05],
  ['beneficiary_age', -0.04],
  ['device_known', -0.07],
];

export const VOL = [180, 142, 96, 71, 58, 64, 110, 205, 320, 398, 432, 455, 470, 462, 441, 458, 489, 510, 548, 572, 530, 462, 368, 262];
export const FLG = [12, 9, 7, 5, 4, 5, 8, 14, 19, 22, 26, 24, 25, 23, 21, 24, 28, 31, 36, 41, 34, 27, 20, 15];

export function money(n: number): string {
  const s = String(Math.round(n));
  const l = s.length;
  if (l <= 3) return '₹' + s;
  let head = s.slice(0, l - 3);
  const tail = s.slice(l - 3);
  let out = '';
  while (head.length > 2) {
    out = ',' + head.slice(-2) + out;
    head = head.slice(0, -2);
  }
  return '₹' + head + out + ',' + tail;
}

export function line(v: number[], w: number, h: number, pad = 2): string {
  const mx = Math.max(...v);
  const mn = Math.min(...v);
  const r = mx - mn || 1;
  const sx = w / (v.length - 1);
  const ih = h - pad * 2;
  return v.map((y, i) => `${i ? 'L' : 'M'}${(i * sx).toFixed(1)} ${(pad + ih - ((y - mn) / r) * ih).toFixed(1)}`).join(' ');
}

export function area(v: number[], w: number, h: number, pad = 2): string {
  return line(v, w, h, pad) + ` L${w} ${h} L0 ${h} Z`;
}

// ---- Landing page ----
export const specRows = [
  { n: '01', v: '78 ms', k: 'p95 end-to-end, score to response' },
  { n: '02', v: '590K', k: 'labelled transactions in training' },
  { n: '03', v: '30+', k: 'engineered risk features per txn' },
  { n: '04', v: '0.91', k: 'F1 on stratified hold-out' },
];

export const stages = [
  { n: '01', t: 'Ingest', d: 'FastAPI receives JSON, Pydantic validates.', ms: '5 ms', o: 0.25 },
  { n: '02', t: 'Enrich', d: 'Redis profile + velocity counters.', ms: '10 ms', o: 0.4 },
  { n: '03', t: 'Score', d: 'XGBoost + Isolation Forest.', ms: '30 ms', o: 0.7 },
  { n: '04', t: 'Graph', d: 'NetworkX metrics + edge simulation.', ms: '20 ms', o: 0.55 },
  { n: '05', t: 'Decide', d: 'Rules, thresholds, SHAP.', ms: '15 ms', o: 0.45 },
  { n: '06', t: 'Emit', d: 'Response + WebSocket to console.', ms: '<1 ms', o: 0.2 },
];

export const capabilities = [
  {
    n: '01', t: 'Puppet signature detection',
    d: 'Coercion, caught live. Round repeated amounts, mechanical 90-second intervals, a burst of brand-new beneficiaries, a session that goes straight to transfer — four statistics on metadata the bank already holds, combined into one puppet_score.',
    tags: ['amount_regularity', 'timing_regularity', 'new_benef_burst', 'session_linearity'],
  },
  {
    n: '02', t: 'Pre-approval graph simulation',
    d: "The edge is added to the graph before the decision is returned. Does it close a cycle? Bridge two fraud-adjacent clusters? Spike the receiver's centrality? Then the edge is removed — 20 ms, local neighbourhood only.",
    tags: ['cycle detection', 'local PageRank', 'cluster bridging'],
  },
  {
    n: '03', t: 'Fraud contagion modelling',
    d: 'Epidemiology borrowed for fintech. A confirmed fraud propagates an exposure score outward by BFS with distance decay, so the next transaction of every connected account starts higher — and the bank can warn the likely next victim first.',
    tags: ['SIR model', 'BFS depth 3', 'exposure decay'],
  },
  {
    n: '04', t: 'UPI-specific deep features',
    d: "VPA entropy separates x8k2m@ybl from a person's name. Collect-to-pay ratio finds targets. Channel switching to NEFT flags limit evasion. Festival baselines stop the false positives everyone else ships in October.",
    tags: ['vpa_entropy', 'collect_pay_ratio', 'channel_switch', 'seasonal baseline'],
  },
];

export const plugSteps = [
  { n: '01', t: 'Connect', d: 'Point the transaction stream at the endpoint. Standard REST — anything that can POST integrates.' },
  { n: '02', t: 'Score', d: 'Risk score 0–1, a three-tier decision, and per-feature SHAP for the audit file.' },
  { n: '03', t: 'Tune', d: 'Admins move thresholds in the console with a live replay preview. No ML expertise required.' },
  { n: '04', t: 'Learn', d: "Analyst confirms and overrides become labels. The model retrains on the bank's own data." },
];

export const endpoints = [
  { m: 'POST', p: '/api/v1/score', d: 'Score a transaction' },
  { m: 'GET', p: '/api/v1/score/history/{user_id}', d: 'Last N scored' },
  { m: 'GET', p: '/api/v1/graph/subgraph/{id}?depth=2', d: '2-hop neighbourhood' },
  { m: 'POST', p: '/api/v1/feedback', d: 'Confirm fraud / override' },
  { m: 'POST', p: '/api/v1/admin/thresholds', d: 'Update thresholds' },
  { m: 'GET', p: '/api/v1/admin/threshold-preview', d: 'Replay at proposed bands' },
  { m: 'CRUD', p: '/api/v1/rules', d: 'Custom rule engine' },
  { m: 'GET', p: '/api/v1/admin/model-health', d: 'F1, precision, recall, FPR' },
  { m: 'WS', p: '/ws/transactions', d: 'Live scored feed' },
];

// ---- Auth ----
export const authStats = [
  { v: '1.8%', k: 'False positive rate', c: GREEN },
  { v: '312', k: 'Open cases', c: AMBER },
  { v: '78 ms', k: 'p95 latency', c: 'var(--color-accent-700)' },
];

export const services = [
  { n: 'scoring-api', v: 'healthy', c: GREEN },
  { n: 'redis-features', v: '0.4 ms', c: GREEN },
  { n: 'postgres-audit', v: 'healthy', c: GREEN },
  { n: 'graph-engine', v: '21 ms', c: AMBER },
  { n: 'celery-worker', v: '2 queued', c: GREEN },
];

// ---- Console nav ----
export const NAV_DEFS: [string, string, string][] = [
  ['dashboard', 'Dashboard', ''],
  ['workbench', 'Workbench', '18'],
  ['graph', 'Graph', ''],
  ['alerts', 'Alerts', '30'],
  ['thresholds', 'Thresholds', ''],
  ['rules', 'Rules', ''],
  ['health', 'Model health', ''],
  ['simulator', 'Simulator', ''],
];

export const SCREEN_TITLE: Record<string, string> = {
  dashboard: 'Dashboard', workbench: 'Analyst workbench', graph: 'Transaction graph',
  alerts: 'Alert queue', thresholds: 'Threshold control', rules: 'Rule engine',
  health: 'Model health', simulator: 'Scenario simulator',
};
export const SCREEN_NOTE: Record<string, string> = {
  dashboard: 'live', workbench: '18 in queue', graph: '2-hop · contagion',
  alerts: '30 grouped cases', thresholds: 'admin', rules: '4 active',
  health: 'xgb_v4', simulator: 'demo tool',
};

// ---- Workbench ----
export const analystStats = [
  { k: 'Overrides', v: '23', w: '46%', c: 'var(--color-accent)' },
  { k: 'Upheld', v: '11', w: '48%', c: GREEN },
  { k: 'Missed fraud', v: '1', w: '4%', c: RED },
];
export const linked = [
  { id: 'TXN-88404', amt: '₹2,48,000', s: '0.78', c: RED },
  { id: 'TXN-88411', amt: '₹1,99,500', s: '0.86', c: RED },
  { id: 'TXN-88390', amt: '₹1,50,000', s: '0.83', c: RED },
  { id: 'TXN-88377', amt: '₹1,20,000', s: '0.75', c: AMBER },
];
export const timeline = [
  { t: '14:14', d: 'Session opened · known device', c: 'var(--color-accent)' },
  { t: '14:16', d: 'Beneficiary x8k2m@ybl added', c: AMBER },
  { t: '14:18', d: '2 further new beneficiaries added', c: AMBER },
  { t: '14:20', d: '₹2,48,000 transfer · scored 0.78', c: RED },
  { t: '14:22', d: 'Identical amount repeated · blocked', c: RED },
];
const P9 = [[120, 85], [60, 40], [54, 130], [190, 40], [205, 120], [120, 155], [30, 85], [215, 20], [170, 155]];
export const miniNodes = ([[120, 85, 14, 2], [60, 40, 7, 3], [54, 130, 7, 3], [190, 40, 8, 1], [205, 120, 9, 2], [120, 155, 7, 0], [30, 85, 6, 0], [215, 20, 5, 1], [170, 155, 6, 1]] as const)
  .map((n) => ({ x: n[0], y: n[1], r: n[2], f: `color-mix(in srgb, ${n[3] === 2 ? RED : n[3] === 1 ? AMBER : 'var(--color-accent)'} 22%, transparent)`, c: n[3] === 2 ? RED : n[3] === 1 ? AMBER : 'var(--color-accent)' }));
export const miniLinks = ([[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [1, 6], [3, 7], [4, 8], [2, 6], [4, 3]] as const)
  .map(([a, b]) => ({ x1: P9[a][0], y1: P9[a][1], x2: P9[b][0], y2: P9[b][1] }));

// ---- Graph screen ----
export const GN: [number, number, number, number][] = [
  [110, 90, 9, 0], [90, 190, 8, 0], [160, 300, 9, 0], [230, 140, 11, 3], [250, 250, 10, 3],
  [330, 60, 8, 0], [380, 200, 17, 2], [470, 110, 12, 2], [520, 230, 13, 2], [610, 150, 10, 2],
  [660, 270, 9, 1], [560, 340, 11, 1], [430, 330, 10, 3], [300, 370, 8, 0], [700, 90, 7, 1],
  [180, 40, 7, 0], [640, 390, 8, 1], [480, 400, 7, 0], [120, 380, 7, 0], [720, 200, 8, 1],
];
export const GL: [number, number][] = [
  [0, 3], [1, 3], [15, 3], [2, 4], [13, 4], [18, 2], [3, 6], [4, 6], [12, 6], [6, 7],
  [6, 8], [7, 9], [8, 9], [8, 11], [9, 14], [9, 19], [10, 19], [11, 16], [8, 10], [6, 12], [17, 11], [5, 6], [7, 14], [16, 10],
];
export const nodeLabelDefs: [number, number, string][] = [
  [380, 244, 'x8k2m@ybl'], [230, 118, 'victim-1'], [520, 262, 'mule-3'], [610, 128, 'mule-7'],
];
export const exposed = [
  { a: 'r.mehta@ybl', h: '1', v: '0.78', w: '78%', c: RED, n: 'pre-flagged' },
  { a: 'q4t7z@paytm', h: '1', v: '0.71', w: '71%', c: RED, n: 'pre-flagged' },
  { a: 'w2p8n@paytm', h: '2', v: '0.44', w: '44%', c: AMBER, n: 'step-up' },
  { a: 'k3n9x@paytm', h: '2', v: '0.39', w: '39%', c: AMBER, n: 'step-up' },
  { a: 'nihanshi@ybl', h: '3', v: '0.21', w: '21%', c: 'var(--color-accent)', n: 'monitor' },
  { a: 'v.shah@oksbi', h: '3', v: '0.18', w: '18%', c: 'var(--color-accent)', n: 'monitor' },
];
export const nodeMetrics = [
  { k: 'PageRank', v: '0.049', c: RED }, { k: 'Δ 24 h', v: '+0.048', c: RED },
  { k: 'Clustering', v: '0.71', c: 'inherit' }, { k: 'Degree in / out', v: '9 : 1', c: AMBER },
  { k: 'Exposure', v: '0.92', c: RED }, { k: 'Account age', v: '94 d', c: 'inherit' },
];
export const prSeries = [0.001, 0.001, 0.002, 0.002, 0.003, 0.004, 0.009, 0.021, 0.038, 0.049];

// ---- Alerts ----
const bars = (a: number[]) => a.map((h) => ({ h: h + '%' }));
export const alertKpis = [
  { k: 'Raw alerts · 24h', v: '512', d: 'before grouping', c: 'var(--color-accent-700)' },
  { k: 'Grouped cases', v: '30', d: '17 unassigned', c: AMBER },
  { k: 'Value at risk', v: '₹8.1 Cr', d: 'across open cases', c: RED },
  { k: 'Median response', v: '4m 12s', d: 'analyst first touch', c: GREEN },
];
export const alertGroups = [
  { t: 'Mule ring · x8k2m@ybl', pr: 'P1', c: RED, tint: tint(RED), rule: 'Same beneficiary · 24 h window',
    cells: [{ k: 'Transactions', v: '14' }, { k: 'Value at risk', v: '₹31.4 L' }, { k: 'Senders', v: '9' }, { k: 'Confidence', v: '0.93' }],
    bars: bars([30, 45, 38, 62, 70, 55, 80, 92, 74, 88, 96, 70]) },
  { t: 'Digital arrest pattern · victim-1', pr: 'P1', c: RED, tint: tint(RED), rule: 'Puppet score > 0.7 · session',
    cells: [{ k: 'Transactions', v: '6' }, { k: 'Value at risk', v: '₹14.8 L' }, { k: 'Senders', v: '1' }, { k: 'Confidence', v: '0.88' }],
    bars: bars([20, 28, 44, 60, 72, 84, 90, 86, 78, 66, 52, 40]) },
  { t: 'Smurfing cluster · ₹49,999 band', pr: 'P2', c: AMBER, tint: tint(AMBER), rule: 'Below-threshold split · sender pattern',
    cells: [{ k: 'Transactions', v: '27' }, { k: 'Value at risk', v: '₹13.5 L' }, { k: 'Senders', v: '4' }, { k: 'Confidence', v: '0.71' }],
    bars: bars([40, 42, 46, 44, 50, 48, 54, 52, 58, 56, 60, 58]) },
  { t: 'Channel-switch anomalies', pr: 'P3', c: AMBER, tint: tint(AMBER), rule: 'UPI → NEFT within session',
    cells: [{ k: 'Transactions', v: '11' }, { k: 'Value at risk', v: '₹6.2 L' }, { k: 'Senders', v: '11' }, { k: 'Confidence', v: '0.58' }],
    bars: bars([18, 24, 20, 30, 26, 34, 28, 38, 32, 40, 36, 44]) },
];
export const scatter = ([[60, 96, 4], [88, 74, 6], [112, 58, 7], [140, 42, 9], [170, 30, 11], [196, 22, 7], [220, 16, 5], [74, 110, 4], [100, 88, 5], [132, 70, 6], [158, 54, 8], [184, 40, 6], [208, 32, 4], [46, 116, 3]] as const)
  .map((p) => ({ x: p[0], y: p[1], r: p[2], c: p[1] < 45 ? RED : p[1] < 80 ? AMBER : 'var(--color-accent)' }));

// ---- Rules ----
export const rules = [
  { name: 'Coercion session hold', action: 'Force review', c: RED, tint: tint(RED), pr: 1,
    cond: 'IF puppet_score > 0.7 AND session_total > ₹1,00,000 THEN flag for human review',
    stats: [{ k: 'Caught 7d', v: '41', w: '82%', c: RED }, { k: 'Precision', v: '0.88', w: '88%', c: GREEN }, { k: 'FPR', v: '1.2%', w: '12%', c: AMBER }] },
  { name: 'Night large new-VPA', action: '+0.30 score', c: AMBER, tint: tint(AMBER), pr: 2,
    cond: 'IF amount > ₹2,00,000 AND beneficiary_age < 1d AND hour BETWEEN 23 AND 5 THEN score += 0.30',
    stats: [{ k: 'Caught 7d', v: '64', w: '64%', c: AMBER }, { k: 'Precision', v: '0.62', w: '62%', c: AMBER }, { k: 'FPR', v: '2.1%', w: '21%', c: AMBER }] },
  { name: 'Cycle closure block', action: 'Block', c: RED, tint: tint(RED), pr: 1,
    cond: 'IF graph_sim.cycle_closed AND receiver_exposure > 0.5 THEN block regardless of score',
    stats: [{ k: 'Caught 7d', v: '14', w: '28%', c: RED }, { k: 'Precision', v: '0.95', w: '95%', c: GREEN }, { k: 'FPR', v: '0.3%', w: '3%', c: GREEN }] },
  { name: 'Smurfing band watch', action: '+0.15 score', c: 'var(--color-accent)', tint: 'color-mix(in srgb, var(--color-accent) 16%, transparent)', pr: 3,
    cond: 'IF count(amount BETWEEN ₹45,000 AND ₹50,000, 24h) >= 3 THEN score += 0.15',
    stats: [{ k: 'Caught 7d', v: '27', w: '54%', c: 'var(--color-accent)' }, { k: 'Precision', v: '0.54', w: '54%', c: AMBER }, { k: 'FPR', v: '3.4%', w: '34%', c: RED }] },
];
export const builderRows = [
  { fields: ['amount', 'puppet_score', 'beneficiary_age', 'vpa_entropy'], op: '>', val: '200000' },
  { fields: ['beneficiary_age', 'amount', 'exposure_score', 'hour'], op: '<', val: '1d' },
  { fields: ['hour', 'channel', 'interbank_ratio', 'collect_pay_ratio'], op: 'in', val: '23–05' },
];

// ---- Model health ----
export const healthKpis = [
  { k: 'F1', v: '0.91', d: '+0.01', c: GREEN }, { k: 'Precision', v: '0.89', d: 'stable', c: GREEN },
  { k: 'Recall', v: '0.87', d: '+0.01', c: GREEN }, { k: 'False positive', v: '1.8%', d: '−0.1 pt', c: GREEN },
  { k: 'Scored today', v: '1,84,203', d: '41/s', c: 'var(--color-accent-700)' },
];
export const healthLegend = [{ k: 'F1', c: 'var(--color-accent)' }, { k: 'Precision', c: GREEN }, { k: 'Recall', c: AMBER }, { k: 'FPR', c: RED }];
const H = {
  f1: [0.82, 0.83, 0.84, 0.83, 0.86, 0.87, 0.86, 0.88, 0.89, 0.90, 0.90, 0.91],
  prec: [0.78, 0.80, 0.79, 0.82, 0.83, 0.85, 0.84, 0.86, 0.87, 0.88, 0.88, 0.89],
  rec: [0.71, 0.73, 0.75, 0.74, 0.78, 0.79, 0.81, 0.82, 0.83, 0.84, 0.86, 0.87],
  fpr: [0.041, 0.038, 0.036, 0.034, 0.031, 0.029, 0.026, 0.024, 0.022, 0.020, 0.019, 0.018],
};
const norm = (v: number[], lo: number, hi: number) => v.map((x) => (x - lo) / (hi - lo));
const hp = (v: number[], lo: number, hi: number) => line(norm(v, lo, hi).map((x) => x * 100), 600, 200, 10);
export const healthSeries = [
  { d: hp(H.f1, 0.65, 0.95), c: 'var(--color-accent)', dash: '0' },
  { d: hp(H.prec, 0.65, 0.95), c: GREEN, dash: '0' },
  { d: hp(H.rec, 0.65, 0.95), c: AMBER, dash: '0' },
  { d: hp(H.fpr.map((x) => 1 - x * 8), 0.65, 0.95), c: RED, dash: '5 3' },
];
export const deployMarks = [{ x: 150 }, { x: 330 }, { x: 500 }];
export const importance = ([
  ['new_beneficiary_burst', 100, '+12%', GREEN], ['amount_regularity', 86, '+8%', GREEN],
  ['velocity_1h', 74, '−2%', 'inherit'], ['timing_regularity', 68, '+6%', GREEN],
  ['vpa_entropy', 55, '+4%', GREEN], ['pagerank_delta_24h', 47, '+9%', GREEN],
  ['exposure_score', 38, 'new', 'var(--color-accent-700)'], ['device_type', 22, '−40%', AMBER],
] as const).map((f) => ({ n: f[0], w: f[1] + '%', drift: f[2], c: f[3] }));
export const latency = [
  { k: 'p50', v: '32 ms', w: '23%', c: GREEN, budget: '71%' },
  { k: 'p95', v: '78 ms', w: '56%', c: GREEN, budget: '71%' },
  { k: 'p99', v: '128 ms', w: '91%', c: AMBER, budget: '71%' },
  { k: 'max', v: '214 ms', w: '100%', c: RED, budget: '71%' },
];
export const versions = [
  { n: 'xgb_v4', d: '12 Aug 2026', f1: '0.91', s: 'live', c: GREEN, tint: tint(GREEN) },
  { n: 'xgb_v3', d: '28 Jul 2026', f1: '0.88', s: 'archived', c: 'inherit', tint: 'color-mix(in srgb, currentColor 8%, transparent)' },
  { n: 'xgb_v2', d: '09 Jul 2026', f1: '0.84', s: 'archived', c: 'inherit', tint: 'color-mix(in srgb, currentColor 8%, transparent)' },
  { n: 'xgb_v5-rc', d: 'shadow', f1: '0.93', s: 'A/B 5%', c: AMBER, tint: tint(AMBER) },
];
export const feedbackStats = [
  { k: 'Confirmed fraud', v: '386', c: RED }, { k: 'Overrides', v: '204', c: AMBER },
  { k: 'Upheld blocks', v: '822', c: GREEN }, { k: 'Labels since v4', v: '1,412', c: 'var(--color-accent-700)' },
];

// ---- Simulator ----
export type ScenarioKey = 'normal' | 'arrest' | 'mule' | 'smurf';
export const scenarios: { n: string; t: string; d: string; c: string; txn: number; dur: string; cta: string; key: ScenarioKey; bars: { h: string }[] }[] = [
  { n: '01', t: 'Normal traffic', d: 'Benign retail and P2P mix, realistic amounts and timing. Establishes the baseline before anything else runs.', c: GREEN, txn: 100, dur: '~40 s', cta: 'Inject', key: 'normal', bars: bars([22, 28, 20, 26, 24, 30, 22, 26, 20, 28, 24, 22, 26, 24]) },
  { n: '02', t: 'Digital arrest', d: 'Puppet signature: three new beneficiaries, round repeated amounts, 90-second intervals, straight to transfer.', c: RED, txn: 6, dur: '~12 s', cta: 'Inject', key: 'arrest', bars: bars([20, 26, 40, 58, 72, 84, 92, 88, 80, 70, 58, 46, 38, 30]) },
  { n: '03', t: 'Mule ring activation', d: 'Nine dormant accounts burst simultaneously into one beneficiary. Centrality spikes, cycle closes at hop 2.', c: RED, txn: 14, dur: '~18 s', cta: 'Inject', key: 'mule', bars: bars([12, 16, 22, 36, 54, 68, 82, 90, 96, 86, 72, 60, 44, 32]) },
  { n: '04', t: 'Smurfing', d: 'Twenty-seven transfers parked just under the ₹50,000 reporting band across four senders.', c: AMBER, txn: 27, dur: '~24 s', cta: 'Inject', key: 'smurf', bars: bars([34, 36, 40, 38, 44, 42, 48, 46, 52, 50, 56, 54, 58, 56]) },
];
export const simStatusLabel: Record<ScenarioKey, string> = {
  normal: 'Running · normal_traffic', arrest: 'Running · digital_arrest_scenario',
  mule: 'Running · mule_ring_activation', smurf: 'Running · smurfing_pattern',
};
export const simLog = [
  { t: '14:22:07', m: 'POST /api/v1/simulate/digital_arrest → 202 accepted', c: 'var(--color-accent-700)' },
  { t: '14:22:07', m: 'inject TXN-88404 ₹2,48,000 → score 0.78 step-up', c: AMBER },
  { t: '14:22:08', m: 'puppet_score 0.81 · amount_regularity 0.94', c: RED },
  { t: '14:22:09', m: 'inject TXN-88411 ₹1,99,500 → score 0.86 BLOCK', c: RED },
  { t: '14:22:10', m: 'graph_sim: edge closes cycle at hop 2 → +0.09', c: RED },
  { t: '14:22:11', m: 'inject TXN-88412 ₹2,48,000 → score 0.91 BLOCK', c: RED },
  { t: '14:22:11', m: 'rule "Coercion session hold" fired → human review', c: RED },
  { t: '14:22:12', m: 'analyst confirm → contagion_propagation(depth 3) queued', c: 'var(--color-accent-700)' },
  { t: '14:22:13', m: '208 accounts exposure updated · heatmap refreshed', c: GREEN },
];
export const simSeries = [0.08, 0.11, 0.09, 0.24, 0.41, 0.58, 0.66, 0.74, 0.81, 0.88, 0.91, 0.86, 0.79, 0.72];
export const simStats = [
  { k: 'Injected', v: '6', c: 'inherit' }, { k: 'Blocked', v: '4', c: RED },
  { k: 'Mean score', v: '0.61', c: AMBER }, { k: 'Detection at txn', v: '#2', c: GREEN },
];

// ---- Live feed generator (keeps the console feeling alive) ----
const FROM_POOL = ['arya@okhdfc', 'n.desai@ybl', 'kaysha@oksbi', 'bhoomi@apl', 'p.rao@okaxis', 's.iyer@ibl', 'nihanshi@ybl', 'd.imrie@oksbi', 'aaryahi@apl', 't.menon@okicici', 'paridhi@ybl', 'v.shah@oksbi', 'r.kaur@apl'];
const TO_POOL = ['x8k2m@ybl', 'q4t7z@paytm', 'r.mehta@ybl', 'vend.kirana@sbi', 'm9v2k@ybl', 'fuel.hp@okhdfc', 'w2p8n@paytm', 'rent.jain@ybl', 'z6h1c@ybl', 'grocer.day@ybl', 'k3n9x@paytm', 'sal.acct@okhdfc', 'y7b4d@ybl'];
const RISK_FLAGS = ['cycle 2-hop · mule cluster', 'new benef burst', 'repeat round amt', 'centrality spike', 'below-threshold split', 'exposure 0.58', 'channel switch', '3am pattern'];

let txnCounter = 88413;
function pick<T>(arr: T[]): T { return arr[Math.floor(Math.random() * arr.length)]; }

export function genTxn(): RawTxn {
  const id = 'TXN-' + txnCounter++;
  const time = new Date().toTimeString().slice(0, 8);
  const from = pick(FROM_POOL);
  const to = pick(TO_POOL);
  const risky = Math.random() < 0.3;
  const amount = risky
    ? Math.round((45000 + Math.random() * 260000) / 100) * 100
    : Math.round((200 + Math.random() * 35000) / 10) * 10;
  const score = +(risky ? 0.5 + Math.random() * 0.45 : Math.random() * 0.48).toFixed(2);
  const puppet = +Math.max(0, score - 0.12 + (Math.random() * 0.2 - 0.1)).toFixed(2);
  const flagLine = score > 0.55 ? pick(RISK_FLAGS) : '—';
  return [id, time, from, to, amount, score, puppet, flagLine];
}
