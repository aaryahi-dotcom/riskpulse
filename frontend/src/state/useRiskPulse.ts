import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  GREEN, AMBER, RED, tint, money, line, area,
  RAW_SEED, SHAP, MOCK_SHAP_REASONS, VOL, FLG, genTxn,
  FROM_POOL, TO_POOL, pick, genLiveAmount, genChannel,
  NAV_DEFS, SCREEN_TITLE, SCREEN_NOTE,
  GN, GL, nodeLabelDefs, prSeries,
  scenarios as SCENARIOS, simStatusLabel,
  type RawTxn, type ScenarioKey,
} from '../lib/mock';
import { scoreTransaction, getThresholds, updateThresholds, getThresholdPreview, WS_BASE_URL, type ThresholdPreviewDTO, type ShapReasonDTO } from '../lib/api';

export type { ScenarioKey } from '../lib/mock';

export type View = 'landing' | 'auth' | 'app';
export type Screen = 'dashboard' | 'workbench' | 'graph' | 'alerts' | 'thresholds' | 'rules' | 'health' | 'simulator';
export type Layout = 'A' | 'B' | 'C';
export type Frame = 'brackets' | 'plain' | 'tab';
export type AuthMode = 'in' | 'up';
export type GraphMode = 'network' | 'contagion';

function decide(score: number, appr: number, blk: number): [string, string] {
  if (score >= blk) return ['Block', RED];
  if (score >= appr) return ['Step-up', AMBER];
  return ['Approve', GREEN];
}

export function useRiskPulse() {
  const [view, setView] = useState<View>('landing');
  const [screen, setScreen] = useState<Screen>('dashboard');
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [layout, setLayout] = useState<Layout>('A');
  const [frame, setFrame] = useState<Frame>('brackets');
  const [authMode, setAuthMode] = useState<AuthMode>('in');
  const [live, setLive] = useState(true);
  const [appr, setApprRaw] = useState(0.30);
  const [blk, setBlkRaw] = useState(0.70);
  const [gmode, setGmode] = useState<GraphMode>('network');
  const [scenario, setScenario] = useState<ScenarioKey | null>(null);
  const [feed, setFeed] = useState<RawTxn[]>(RAW_SEED);
  const [selId, setSelId] = useState<string | null>(null);
  // Real per-transaction SHAP values, keyed by txn id, populated whenever
  // the live feed successfully scores a transaction against the real
  // backend. Rows scored via the mock fallback simply have no entry here,
  // so the SHAP panel falls back to the static demo array for them.
  const [shapMap, setShapMap] = useState<Record<string, [string, number][]>>({});
  // Server-computed plain-English reason strings per feature (checklist
  // 4.4/1.5), keyed by txn id, alongside the raw shapMap values above —
  // same real/mock-fallback split, just carrying the human-readable text
  // instead of raw feature names.
  const [shapReasonsMap, setShapReasonsMap] = useState<Record<string, ShapReasonDTO[]>>({});
  const [liveReplay, setLiveReplay] = useState<ThresholdPreviewDTO | null>(null);
  const [publishMsg, setPublishMsg] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const puppetThresholdRef = useRef(0.7);
  const [wsConnected, setWsConnected] = useState(false);
  const wsConnectedRef = useRef(false);
  const seenTxnIds = useRef<Set<string>>(new Set());
  // ---- checklist 4.3: feed filters (channel / decision / min score) ----
  const [filterChannel, setFilterChannel] = useState<'all' | string>('all');
  const [filterDecision, setFilterDecision] = useState<'all' | 'Approve' | 'Step-up' | 'Block'>('all');
  const [filterMinScore, setFilterMinScore] = useState(0);
  // ---- checklist 4.1: toast notifications for high-risk (block) alerts ----
  const [toasts, setToasts] = useState<{ id: string; msg: string; c: string }[]>([]);
  const pushToast = useCallback((id: string, msg: string, c: string) => {
    setToasts((prev) => [...prev, { id, msg, c }].slice(-4));
    window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  }, []);
  const dismissToast = useCallback((id: string) => setToasts((prev) => prev.filter((t) => t.id !== id)), []);

  // ---- seed thresholds from the server once on mount, so a fresh
  // session shows whatever an admin last persisted via POST
  // /admin/thresholds instead of always restarting at the hardcoded
  // 0.30/0.70 default ----
  useEffect(() => {
    getThresholds()
      .then((t) => {
        setApprRaw(t.approve_threshold);
        setBlkRaw(t.block_threshold);
        puppetThresholdRef.current = t.puppet_threshold;
      })
      .catch(() => {});
  }, []);

  // ---- live threshold-replay preview: debounced so dragging a slider
  // doesn't fire a request per pixel ----
  useEffect(() => {
    const id = window.setTimeout(() => {
      getThresholdPreview(appr, blk).then(setLiveReplay).catch(() => setLiveReplay(null));
    }, 400);
    return () => window.clearTimeout(id);
  }, [appr, blk]);

  const publishThresholds = useCallback(() => {
    setPublishing(true);
    setPublishMsg(null);
    updateThresholds(appr, blk, puppetThresholdRef.current)
      .then(() => setPublishMsg('Published — persisted server-side.'))
      .catch(() => setPublishMsg('Backend unreachable — not published.'))
      .finally(() => setPublishing(false));
  }, [appr, blk]);

  // ---- checklist 4.1: persistent WebSocket to the backend's live
  // transaction feed. Every transaction scored by ANY connected client
  // is broadcast here — this is what lets two analyst tabs watch the
  // same stream instead of each polling on its own timer. Auto-reconnects
  // with a fixed backoff if the backend restarts or drops the socket. ----
  useEffect(() => {
    let ws: WebSocket | null = null;
    let closedByUs = false;
    let reconnectTimer: number | null = null;

    const connect = () => {
      try {
        ws = new WebSocket(`${WS_BASE_URL}/ws/transactions`);
      } catch {
        reconnectTimer = window.setTimeout(connect, 3000);
        return;
      }
      ws.onopen = () => { wsConnectedRef.current = true; setWsConnected(true); };
      ws.onclose = () => {
        wsConnectedRef.current = false;
        setWsConnected(false);
        if (!closedByUs) reconnectTimer = window.setTimeout(connect, 3000);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type !== 'score' || seenTxnIds.current.has(msg.txn_id)) return;
          seenTxnIds.current.add(msg.txn_id);
          const time = new Date().toTimeString().slice(0, 8);
          const flagLine = msg.reason_code && msg.reason_code !== 'none' ? String(msg.reason_code).replace(/_/g, ' ') : '—';
          const row: RawTxn = [msg.txn_id, time, msg.sender_id, msg.receiver_id, msg.amount, msg.risk_score, msg.puppet_score, flagLine, msg.channel ?? 'UPI'];
          if (msg.shap_values) {
            setShapMap((prev) => ({ ...prev, [msg.txn_id]: Object.entries(msg.shap_values) as [string, number][] }));
          }
          if (msg.shap_reasons) {
            setShapReasonsMap((prev) => ({ ...prev, [msg.txn_id]: msg.shap_reasons as ShapReasonDTO[] }));
          }
          setFeed((prev) => [row, ...prev].slice(0, 14));
          if (msg.decision === 'block') {
            pushToast(msg.txn_id, `${msg.txn_id} blocked · risk ${Number(msg.risk_score).toFixed(2)} · ${msg.sender_id} → ${msg.receiver_id}`, RED);
          }
        } catch {
          // malformed frame — ignore, the feed just misses this update
        }
      };
    };
    connect();
    return () => {
      closedByUs = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  // ---- live feed: real backend scoring generates traffic; the resulting
  // row normally arrives back via the WS broadcast above (so it's
  // consistent with what any other connected tab sees). If the socket is
  // down, fall back to pushing the row from the direct HTTP response so
  // the feed doesn't stall; if the backend itself is unreachable, fall
  // back further to the local simulator so the console still works
  // standalone for demos. ----
  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    const id = window.setInterval(() => {
      const from = pick(FROM_POOL);
      const to = pick(TO_POOL);
      const amount = genLiveAmount();
      const channel = genChannel();
      const nowIso = new Date().toISOString();

      scoreTransaction({ amount, sender_id: from, receiver_id: to, timestamp: nowIso, channel, vpa: to })
        .then((resp) => {
          if (cancelled) return;
          setShapMap((prev) => ({
            ...prev,
            [resp.txn_id]: Object.entries(resp.shap_values) as [string, number][],
          }));
          setShapReasonsMap((prev) => ({ ...prev, [resp.txn_id]: resp.shap_reasons }));
          if (!wsConnectedRef.current && !seenTxnIds.current.has(resp.txn_id)) {
            seenTxnIds.current.add(resp.txn_id);
            const time = new Date().toTimeString().slice(0, 8);
            const topReason = resp.shap_reasons[0];
            const flagLine = resp.coercion_override
              ? 'puppet override · coercion'
              : resp.risk_score > 0.55 && topReason
                ? topReason.feature.replace(/_/g, ' ')
                : '—';
            const row: RawTxn = [resp.txn_id, time, from, to, amount, resp.risk_score, resp.puppet_score, flagLine, channel];
            setFeed((prev) => [row, ...prev].slice(0, 14));
            if (resp.decision === 'block') {
              pushToast(resp.txn_id, `${resp.txn_id} blocked · risk ${resp.risk_score.toFixed(2)} · ${from} → ${to}`, RED);
            }
          }
        })
        .catch(() => {
          if (cancelled) return;
          setFeed((prev) => [genTxn(), ...prev].slice(0, 14));
        });
    }, 2600);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [live]);

  // refs so the clamping below always reads the latest paired value
  const apprRef = useRef(appr);
  const blkRef = useRef(blk);
  apprRef.current = appr;
  blkRef.current = blk;

  const setAppr = useCallback((v: number) => {
    setApprRaw(Math.min(v, blkRef.current - 0.05));
  }, []);
  const setBlk = useCallback((v: number) => {
    setBlkRaw(Math.max(v, apprRef.current + 0.05));
  }, []);

  const toggleTheme = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);
  const toggleLive = useCallback(() => setLive((l) => !l), []);

  const goLanding = useCallback(() => setView('landing'), []);
  const goApp = useCallback(() => { setView('app'); setScreen('dashboard'); }, []);
  const goAuthIn = useCallback(() => { setView('auth'); setAuthMode('in'); }, []);
  const goAuthUp = useCallback(() => { setView('auth'); setAuthMode('up'); }, []);
  const goSim = useCallback(() => { setView('app'); setScreen('simulator'); }, []);
  const swapAuth = useCallback(() => setAuthMode((m) => (m === 'up' ? 'in' : 'up')), []);

  const runScenario = useCallback((k: ScenarioKey) => {
    setScenario(k);
    setScreen('simulator');
  }, []);

  const setPreset = useCallback((a: number, b: number) => { setApprRaw(a); setBlkRaw(b); }, []);

  // ---- derived: feed rows + selection ----
  const allFeedRows = useMemo(() => {
    return feed.map((r) => {
      const [dec, color] = decide(r[5], appr, blk);
      return {
        raw: r,
        n: '', id: r[0], time: r[1], from: r[2], to: r[3],
        amt: money(r[4]), score: r[5].toFixed(2), pct: (r[5] * 100).toFixed(0) + '%',
        puppet: r[6].toFixed(2), puppetColor: r[6] > 0.7 ? RED : r[6] > 0.4 ? AMBER : 'inherit',
        flagLine: r[7], channel: r[8], dec, color, tint: tint(color),
        selected: r[0] === (selId ?? feed[0]?.[0]),
      };
    }).map((row, i) => ({ ...row, n: String(i + 1).padStart(2, '0') }));
  }, [feed, appr, blk, selId]);

  const availableChannels = useMemo(
    () => Array.from(new Set(feed.map((r) => r[8]))).sort(),
    [feed],
  );

  const feedRows = useMemo(() => allFeedRows.filter((row) =>
    (filterChannel === 'all' || row.channel === filterChannel) &&
    (filterDecision === 'all' || row.dec === filterDecision) &&
    row.raw[5] >= filterMinScore,
  ), [allFeedRows, filterChannel, filterDecision, filterMinScore]);

  const selectedRow = allFeedRows.find((r) => r.selected) ?? allFeedRows[0];
  const pickTxn = useCallback((id: string) => setSelId(id), []);

  const sel = useMemo(() => {
    const r = selectedRow?.raw ?? RAW_SEED[0];
    const [selDec, selColor] = decide(r[5], appr, blk);
    return {
      id: r[0], score: r[5].toFixed(2), dec: selDec, color: selColor, tint: tint(selColor),
      band: r[5] >= blk ? 'above block threshold' : r[5] >= appr ? 'in step-up band' : 'below approve threshold',
      dash: `${(r[5] * 194.8).toFixed(1)} 400`, ringDash: `${(r[5] * 301.6).toFixed(1)} 400`,
      amt: money(r[4]), to: r[3], from: r[2], channel: r[8], puppet: r[6].toFixed(2),
      flags: r[7] === '—' ? ['no graph flags'] : r[7].split(' · '),
    };
  }, [selectedRow, appr, blk]);

  const [copyMsg, setCopyMsg] = useState<string | null>(null);
  const copySelJson = useCallback(() => {
    const realShap = shapMap[sel.id];
    const payload = {
      request: { sender_id: sel.from, receiver_id: sel.to, amount: sel.amt, channel: sel.channel },
      response: {
        txn_id: sel.id, risk_score: Number(sel.score), puppet_score: Number(sel.puppet),
        decision: sel.dec, graph_flags: sel.flags,
        shap_values: realShap ? Object.fromEntries(realShap) : undefined,
      },
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
      .then(() => setCopyMsg('Copied'))
      .catch(() => setCopyMsg('Copy failed'));
    window.setTimeout(() => setCopyMsg(null), 2000);
  }, [sel, shapMap]);

  const split = useMemo(() => {
    const counts = [0, 0, 0];
    feed.forEach((r) => { const d = decide(r[5], appr, blk)[0]; counts[d === 'Approve' ? 0 : d === 'Step-up' ? 1 : 2]++; });
    const tot = feed.length || 1;
    return [
      { k: 'Auto-approve', v: counts[0] + ' · ' + Math.round((counts[0] / tot) * 100) + '%', w: (counts[0] / tot) * 100 + '%', c: GREEN },
      { k: 'Step-up auth', v: counts[1] + ' · ' + Math.round((counts[1] / tot) * 100) + '%', w: (counts[1] / tot) * 100 + '%', c: AMBER },
      { k: 'Blocked', v: counts[2] + ' · ' + Math.round((counts[2] / tot) * 100) + '%', w: (counts[2] / tot) * 100 + '%', c: RED },
    ];
  }, [feed, appr, blk]);

  const hist = useMemo(() => {
    return Array.from({ length: 20 }, (_, i) => {
      const x = (i + 0.5) / 20;
      const v = Math.exp(-Math.pow((x - 0.14) / 0.13, 2)) * 100 + Math.exp(-Math.pow((x - 0.82) / 0.1, 2)) * 22 + 2;
      const c = x >= blk ? RED : x >= appr ? AMBER : GREEN;
      return { h: Math.max(4, (v / 102) * 100).toFixed(0) + '%', c };
    });
  }, [appr, blk]);

  const shap = useMemo(() => {
    const realId = selectedRow?.raw[0];
    const real = realId ? shapMap[realId] : undefined;
    const source: [string, number][] = real && real.length ? real : SHAP;
    const shapMax = Math.max(0.01, ...source.map(([, v]) => Math.abs(v)));
    return source.map(([n, v]) => ({
      n, v: (v > 0 ? '+' : '') + v.toFixed(2),
      w: (Math.abs(v) / shapMax) * 50 + '%',
      left: v > 0 ? '50%' : (50 - (Math.abs(v) / shapMax) * 50) + '%',
      c: v > 0 ? RED : GREEN,
    }));
  }, [selectedRow, shapMap]);

  // checklist 4.4: plain-English driver summary — the top real reasons from
  // the backend's shap_to_reasons() for this txn if we have them, else the
  // fixed mock-name -> sentence mapping for the illustrative demo SHAP set.
  const shapReasons = useMemo(() => {
    const realId = selectedRow?.raw[0];
    const real = realId ? shapReasonsMap[realId] : undefined;
    if (real && real.length) return real.slice(0, 4).map((r) => r.reason);
    return SHAP.slice(0, 4).map(([n]) => MOCK_SHAP_REASONS[n] ?? `${n.replace(/_/g, ' ')} contributed to this score.`);
  }, [selectedRow, shapReasonsMap]);

  const kpis = useMemo(() => [
    { k: 'Scored today', v: '1,84,203', d: '+6.2%', c: 'var(--color-accent-700)', spark: line(VOL, 120, 22) },
    { k: 'Flagged', v: '2,118', d: '1.15%', c: RED, spark: line(FLG, 120, 22) },
    { k: 'Blocked value', v: '₹4.62 Cr', d: 'today', c: RED, spark: line([12, 18, 15, 24, 31, 28, 42, 46], 120, 22) },
    { k: 'p95 latency', v: '78 ms', d: 'budget 100', c: GREEN, spark: line([71, 74, 69, 80, 77, 82, 76, 78], 120, 22) },
    { k: 'False positive', v: '1.8%', d: '−0.3 pt', c: GREEN, spark: line([26, 24, 25, 22, 21, 19, 19, 18], 120, 22) },
  ], []);

  const gridLines = useMemo(() => [38, 76, 114, 152].map((y) => ({ y })), []);
  const volLine = useMemo(() => line(VOL, 600, 190, 6), []);
  const volArea = useMemo(() => area(VOL, 600, 190, 6), []);
  const flagLine = useMemo(() => line(FLG, 600, 190, 6), []);
  const miniCharts = useMemo(() => [
    { k: 'Puppet flags · 6h', v: '37', d: 'sessions', c: RED, line: line([2, 4, 3, 7, 6, 9, 8, 11], 200, 44, 3), area: area([2, 4, 3, 7, 6, 9, 8, 11], 200, 44, 3) },
    { k: 'Graph blocks · 6h', v: '14', d: 'cycles closed', c: AMBER, line: line([1, 1, 3, 2, 4, 3, 5, 4], 200, 44, 3), area: area([1, 1, 3, 2, 4, 3, 5, 4], 200, 44, 3) },
    { k: 'Exposure > 0.5', v: '208', d: 'accounts', c: 'var(--color-accent-700)', line: line([120, 138, 132, 160, 174, 188, 196, 208], 200, 44, 3), area: area([120, 138, 132, 160, 174, 188, 196, 208], 200, 44, 3) },
    { k: 'Analyst overrides', v: '23', d: '11 upheld', c: GREEN, line: line([6, 8, 5, 9, 12, 10, 14, 11], 200, 44, 3), area: area([6, 8, 5, 9, 12, 10, 14, 11], 200, 44, 3) },
  ], []);

  const today = useMemo(() => new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }), []);

  // ---- nav / header derived ----
  const navItems = useMemo(() => NAV_DEFS.map(([key, label, badge], i) => ({
    key, n: String(i + 1).padStart(2, '0'), t: label, badge, badgeShow: badge ? 'inline-flex' : 'none',
    active: screen === key,
    bar: screen === key ? 'var(--color-accent)' : 'transparent',
    bg: screen === key ? 'color-mix(in srgb, var(--color-accent) 14%, transparent)' : 'transparent',
  })), [screen]);

  const screenTitle = SCREEN_TITLE[screen];
  const screenNote = SCREEN_NOTE[screen];
  const liveLabel = !live ? 'Stream paused' : wsConnected ? 'Streaming · live via WS' : 'Streaming · WS reconnecting…';
  const liveCta = live ? 'Pause' : 'Resume';

  const layoutOpts = useMemo(() => (['A', 'B', 'C'] as Layout[]).map((l) => ({
    key: l,
    t: l === 'A' ? 'A · Command grid' : l === 'B' ? 'B · Split console' : 'C · Scoring sheet',
    bg: layout === l ? 'var(--color-accent)' : 'transparent',
    fg: layout === l ? 'var(--color-bg)' : 'inherit',
  })), [layout]);
  const layoutNote = { A: 'Feed centre, explanation rail right — the balanced default.', B: 'Explanation-first: score and SHAP pinned left, stream as cards.', C: 'One audit sheet: dense tabular log with inline figures.' }[layout];

  const frameOpts = useMemo(() => ([['brackets', '1 · Brackets'], ['plain', '2 · Hairline'], ['tab', '3 · Index tab']] as [Frame, string][]).map(([key, t]) => ({
    key, t,
    bg: frame === key ? 'var(--color-accent)' : 'transparent',
    fg: frame === key ? 'var(--color-bg)' : 'inherit',
  })), [frame]);

  // ---- graph screen derived ----
  const graphDerived = useMemo(() => {
    const adj: number[][] = GN.map(() => []);
    GL.forEach(([a, b]) => { adj[a].push(b); adj[b].push(a); });
    const hop = GN.map(() => 99);
    hop[6] = 0;
    let frontier = [6];
    while (frontier.length) {
      const next: number[] = [];
      frontier.forEach((n) => adj[n].forEach((m) => { if (hop[m] > hop[n] + 1) { hop[m] = hop[n] + 1; next.push(m); } }));
      frontier = next;
    }
    const typeColor = (t: number) => (t === 2 ? RED : t === 1 ? AMBER : t === 3 ? 'var(--color-accent)' : 'color-mix(in srgb, currentColor 45%, transparent)');
    const expo = (h: number) => Math.max(0, 0.92 * Math.pow(0.52, h));
    const contagion = gmode === 'contagion';

    const nodes = GN.map((n, i) => {
      const e = expo(hop[i]);
      return {
        x: n[0], y: n[1], r: n[2],
        f: contagion ? `color-mix(in srgb, ${RED} ${(e * 100).toFixed(0)}%, transparent)` : `color-mix(in srgb, ${typeColor(n[3])} 22%, transparent)`,
        c: contagion ? (e > 0.4 ? RED : 'color-mix(in srgb, currentColor 35%, transparent)') : typeColor(n[3]),
      };
    });
    const links = GL.map(([a, b]) => {
      const fraud = GN[a][3] === 2 && GN[b][3] === 2;
      return { x1: GN[a][0], y1: GN[a][1], x2: GN[b][0], y2: GN[b][1], c: fraud ? RED : 'color-mix(in srgb, currentColor 22%, transparent)', w: fraud ? 2 : 1 };
    });
    const heat: { bg: string }[] = [];
    for (let r = 1; r <= 4; r++) {
      for (let h = 0; h < 14; h++) {
        const v = expo(r) * (0.35 + 0.65 * (h / 13)) * (r === 1 ? 1 : 0.9);
        heat.push({ bg: `color-mix(in srgb, ${RED} ${(v * 100).toFixed(0)}%, color-mix(in srgb, var(--color-accent) 8%, transparent))` });
      }
    }
    const nodeLabels = nodeLabelDefs.map(([x, y, t]) => ({ l: (x / 760 * 100).toFixed(2) + '%', t2: (y / 420 * 100).toFixed(2) + '%', t }));
    const graphNote = contagion
      ? 'SIR propagation from the confirmed fraud node, BFS depth 3, exposure decayed 0.52 per hop and weighted by recency. 208 accounts now carry exposure > 0.5.'
      : "In-memory NetworkX graph, updated on every scored transaction. Edge x8k2m@ybl → mule-3 closed a 2-hop cycle during pre-approval simulation and was blocked.";
    const graphLegend = contagion
      ? [{ k: 'Source', c: RED }, { k: '1 hop', c: `color-mix(in srgb, ${RED} 48%, transparent)` }, { k: '2 hop', c: `color-mix(in srgb, ${RED} 25%, transparent)` }, { k: '3+ hop', c: `color-mix(in srgb, ${RED} 12%, transparent)` }]
      : [{ k: 'Clean', c: 'color-mix(in srgb, currentColor 45%, transparent)' }, { k: 'Suspicious', c: AMBER }, { k: 'Confirmed fraud', c: RED }, { k: 'Exposed', c: 'var(--color-accent)' }];

    return { nodes, links, heat, nodeLabels, graphNote, graphLegend };
  }, [gmode]);

  const graphModes = useMemo(() => (['network', 'contagion'] as GraphMode[]).map((m) => ({
    key: m, t: m === 'network' ? 'Network' : 'Contagion',
    bg: gmode === m ? 'var(--color-accent)' : 'transparent',
    fg: gmode === m ? 'var(--color-bg)' : 'inherit',
  })), [gmode]);

  const prLine = useMemo(() => line(prSeries, 240, 90, 5), []);
  const prArea = useMemo(() => area(prSeries, 240, 90, 5), []);

  // ---- threshold screen derived ----
  const bandApprove = (appr * 100) + '%';
  const bandStep = ((blk - appr) * 100) + '%';
  const bandBlock = ((1 - blk) * 100) + '%';
  const apprLabel = appr.toFixed(2);
  const blkLabel = blk.toFixed(2);

  const donut = useMemo(() => {
    const dsum = 326.7;
    const dvals = [0.94, 0.048, 0.012];
    let acc = 0;
    return dvals.map((v, i) => {
      const seg = { c: [GREEN, AMBER, RED][i], dash: `${(v * dsum).toFixed(1)} ${dsum}`, off: (-acc * dsum).toFixed(1) };
      acc += v;
      return seg;
    });
  }, []);
  const fprLabel = liveReplay?.estimated_fpr != null
    ? (liveReplay.estimated_fpr * 100).toFixed(1) + '%'
    : (1.2 + (0.7 - blk) * 4).toFixed(1) + '%';
  const previewRows = useMemo(() => {
    if (liveReplay && liveReplay.sample_size > 0) {
      const { approve, step_up, block } = liveReplay.distribution;
      const total = approve + step_up + block || 1;
      return [
        { k: 'Auto-approved', v: ((approve / total) * 100).toFixed(1) + '%', c: GREEN },
        { k: 'Step-up auth', v: ((step_up / total) * 100).toFixed(1) + '%', c: AMBER },
        { k: 'Blocked', v: ((block / total) * 100).toFixed(1) + '%', c: RED },
      ];
    }
    return [
      { k: 'Auto-approved', v: (86 + appr * 24).toFixed(1) + '%', c: GREEN },
      { k: 'Step-up auth', v: Math.max(1, (blk - appr) * 22).toFixed(1) + '%', c: AMBER },
      { k: 'Blocked', v: ((1 - blk) * 4.2).toFixed(1) + '%', c: RED },
    ];
  }, [appr, blk, liveReplay]);
  const roc: [number, number][] = [[10, 120], [40, 72], [70, 50], [110, 36], [150, 26], [190, 19], [230, 13], [250, 10]];
  const rocPath = useMemo(() => roc.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' '), []);
  const rocIdx = Math.min(roc.length - 1, Math.max(0, Math.round((0.95 - blk) / 0.55 * 6)));
  const rocX = roc[rocIdx][0];
  const rocY = roc[rocIdx][1];
  const catchDelta = ((0.7 - blk) * 100 + 6).toFixed(0) + '%';
  const fprDelta = ((0.7 - blk) * 4 + 0.4).toFixed(1) + ' pt';
  const presets = [
    { t: 'Baseline', a: 0.30, b: 0.70 },
    { t: 'Festival mode', a: 0.42, b: 0.80 },
    { t: 'High alert', a: 0.18, b: 0.55 },
    { t: 'Audit week', a: 0.25, b: 0.62 },
  ];

  // ---- simulator derived ----
  const simDotColor = scenario ? RED : GREEN;
  const simStatus = scenario ? simStatusLabel[scenario] : 'Idle · pick a scenario';

  return {
    // core state
    view, screen, theme, layout, frame, authMode, live, appr, blk, gmode, scenario, today,
    // setters / handlers
    setView, setScreen, toggleTheme, setLayout, setFrame, setAuthMode, swapAuth, toggleLive,
    setAppr, setBlk, setPreset, setGmode, runScenario,
    goLanding, goApp, goAuthIn, goAuthUp, goSim,
    themeGlyph: theme === 'dark' ? '☀' : '☾',
    // feed / selection
    feed: feedRows, pickTxn, sel, split, hist, shap, shapReasons,
    // feed filters (4.3)
    filterChannel, setFilterChannel, filterDecision, setFilterDecision, filterMinScore, setFilterMinScore,
    availableChannels, feedTotal: allFeedRows.length,
    // toasts (4.1)
    toasts, dismissToast,
    // copy request/response JSON (4.2)
    copySelJson, copyMsg,
    // dashboard
    kpis, gridLines, volLine, volArea, flagLine, miniCharts, shapBase: '0.031',
    navItems, screenTitle, screenNote, liveLabel, liveCta, wsConnected,
    layoutOpts, layoutNote, frameOpts,
    // graph
    ...graphDerived, graphModes, prLine, prArea,
    // thresholds
    bandApprove, bandStep, bandBlock, apprLabel, blkLabel, donut, fprLabel, previewRows,
    rocPath, rocX, rocY, catchDelta, fprDelta, presets,
    publishThresholds, publishing, publishMsg, replaySampleSize: liveReplay?.sample_size ?? 0,
    // simulator
    simDotColor, simStatus, scenarios: SCENARIOS,
  };
}

export type RiskPulse = ReturnType<typeof useRiskPulse>;
