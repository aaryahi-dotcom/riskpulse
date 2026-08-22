import { useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { simLog as mockLog, simSeries, simStats as mockStats, line, area, RED, AMBER, GREEN } from '../../lib/mock';
import { scoreTransaction, type ScorePayload } from '../../lib/api';
import type { RiskPulse, ScenarioKey } from '../../state/useRiskPulse';

type LogRow = { t: string; m: string; c: string };
type StatRow = { k: string; v: string; c: string };

// checklist 4.12: scenarios inject real payloads into the same
// /api/v1/score the live feed uses (there is no separate
// /api/v1/simulate endpoint on the backend — one was never actually
// built, despite the checklist previously marking this item done). Each
// scenario is shaped to plausibly trip the corresponding detector:
// "arrest" bursts new beneficiaries with round repeated amounts off one
// sender (puppet signals), "mule" fans many senders into one fresh
// receiver (graph centrality), "smurf" parks many transfers just under
// the reporting band.
function buildScenario(key: ScenarioKey): ScorePayload[] {
  const runId = Math.random().toString(36).slice(2, 7);
  const now = Date.now();
  const iso = (offsetMs: number) => new Date(now + offsetMs).toISOString();

  if (key === 'arrest') {
    const sender = `sim-victim-${runId}@okhdfc`;
    return ['sim-mule1', 'sim-mule2', 'sim-mule3'].map((m, i) => ({
      amount: 248000, sender_id: sender, receiver_id: `${m}-${runId}@ybl`,
      timestamp: iso(i * 90_000), channel: 'UPI', vpa: `${m}-${runId}@ybl`,
    }));
  }
  if (key === 'mule') {
    const target = `sim-muletarget-${runId}@ybl`;
    return Array.from({ length: 9 }, (_, i) => ({
      amount: 15000 + i * 4000, sender_id: `sim-dormant${i}-${runId}@oksbi`, receiver_id: target,
      timestamp: iso(i * 4000), channel: 'UPI', vpa: target,
    }));
  }
  if (key === 'smurf') {
    const sender = `sim-smurf-${runId}@apl`;
    return Array.from({ length: 14 }, (_, i) => ({
      amount: 45000 + Math.floor(Math.random() * 4900), sender_id: sender,
      receiver_id: `sim-smurftgt${i % 4}-${runId}@paytm`, timestamp: iso(i * 3000), channel: 'UPI',
    }));
  }
  return Array.from({ length: 10 }, (_, i) => ({
    amount: 500 + Math.floor(Math.random() * 15000), sender_id: `sim-user${i}-${runId}@okhdfc`,
    receiver_id: `sim-merchant${i % 3}-${runId}@ybl`, timestamp: iso(i * 4000), channel: 'UPI',
  }));
}

const decisionColor = (d: string) => (d === 'block' ? RED : d === 'step_up' ? AMBER : GREEN);

export function Simulator({ rp }: { rp: RiskPulse }) {
  const [log, setLog] = useState<LogRow[] | null>(null);
  const [series, setSeries] = useState<number[]>([]);
  const [stats, setStats] = useState<StatRow[] | null>(null);
  const [running, setRunning] = useState(false);

  const runScenario = async (key: ScenarioKey) => {
    rp.runScenario(key);
    setRunning(true);
    setLog([]);
    setSeries([]);
    setStats(null);

    const payloads = buildScenario(key);
    const scores: number[] = [];
    let blocked = 0, stepUp = 0, maxPuppet = 0;
    const started = performance.now();

    for (const p of payloads) {
      const t = new Date().toTimeString().slice(0, 8);
      try {
        const resp = await scoreTransaction(p);
        scores.push(resp.risk_score);
        maxPuppet = Math.max(maxPuppet, resp.puppet_score);
        if (resp.decision === 'block') blocked++;
        else if (resp.decision === 'step_up') stepUp++;
        const c = decisionColor(resp.decision);
        const rows: LogRow[] = [{ t, m: `inject ${resp.txn_id} ₹${p.amount.toLocaleString('en-IN')} → score ${resp.risk_score.toFixed(2)} ${resp.decision.toUpperCase()}`, c }];
        if (resp.graph_flags.length) rows.push({ t, m: `graph_sim: ${resp.graph_flags.join(', ')}`, c: RED });
        if (resp.coercion_override) rows.push({ t, m: `puppet override · ${resp.coercion_reason ?? 'coercion'}`, c: RED });
        setLog((prev) => [...(prev ?? []), ...rows]);
        setSeries((prev) => [...prev, resp.risk_score]);
      } catch {
        setLog((prev) => [...(prev ?? []), { t, m: 'backend unreachable — injection stopped', c: RED }]);
        break;
      }
      await new Promise((r) => setTimeout(r, 160));
    }

    const elapsed = ((performance.now() - started) / 1000).toFixed(1);
    const avg = scores.length ? scores.reduce((s, v) => s + v, 0) / scores.length : 0;
    setStats([
      { k: 'Injected', v: String(scores.length), c: 'var(--color-accent-700)' },
      { k: 'Mean risk score', v: avg.toFixed(2), c: avg > 0.5 ? RED : GREEN },
      { k: 'Blocked', v: `${blocked} · ${scores.length ? Math.round((blocked / scores.length) * 100) : 0}%`, c: RED },
      { k: 'Step-up', v: `${stepUp} · ${scores.length ? Math.round((stepUp / scores.length) * 100) : 0}%`, c: AMBER },
      { k: 'Max puppet score', v: maxPuppet.toFixed(2), c: maxPuppet > 0.7 ? RED : 'inherit' },
      { k: 'Elapsed', v: `${elapsed}s`, c: 'inherit' },
    ]);
    setRunning(false);
  };

  const displayLog = log ?? mockLog;
  const displaySeries = series.length > 1 ? series : simSeries;
  const displayStats = stats ?? mockStats;
  const simLine = line(displaySeries, 260, 120, 6);
  const simArea = area(displaySeries, 260, 120, 6);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', border: '1px solid var(--color-divider)', background: 'var(--color-surface)' }}>
        <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 13, letterSpacing: '.09em', textTransform: 'uppercase' }}>Demo tool — not the product</span>
        <span style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Judges cannot wait for real fraud. The simulator injects scripted sequences into the same scoring API a bank would call.</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 20 }}>
        {rp.scenarios.map((s) => (
          <Blueprint key={s.key} style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10, borderLeft: `4px solid ${s.c}` }}>
            <span style={{ fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>{s.n}</span>
            <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 20, lineHeight: 1.1, textTransform: 'uppercase' }}>{s.t}</span>
            <span style={{ fontSize: 12.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 72%,transparent)' }}>{s.d}</span>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 38, marginTop: 4 }}>
              {s.bars.map((b, i) => <span key={i} style={{ flex: 1, height: b.h, background: s.c, opacity: 0.7 }} />)}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>
              <span>{s.txn} txn</span><span>·</span><span>{s.dur}</span>
            </div>
            <button type="button" className="btn btn-primary btn-block" disabled={running} onClick={() => runScenario(s.key as ScenarioKey)}>
              {running && rp.scenario === s.key ? 'Injecting…' : s.cta}
            </button>
          </Blueprint>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 22, alignItems: 'start' }}>
        <Blueprint style={{ padding: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', borderBottom: '1px solid var(--color-divider)' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: rp.simDotColor, animation: 'rp-pulse 1.4s infinite' }} />
            <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.1em', textTransform: 'uppercase' }}>Injection log</span>
            <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{log ? (running ? 'Injecting · live via /api/v1/score' : 'Done · live via /api/v1/score') : rp.simStatus}</span>
          </div>
          <div className="rp-scroll" style={{ padding: '14px 16px', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, lineHeight: 1.9, maxHeight: 340, overflow: 'auto' }}>
            {displayLog.map((l, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '66px 1fr', gap: 12 }}>
                <span style={{ color: 'color-mix(in srgb,var(--color-text) 50%,transparent)' }}>{l.t}</span>
                <span style={{ color: l.c }}>{l.m}</span>
              </div>
            ))}
          </div>
        </Blueprint>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 12 }}>Engine response during run</span>
          <svg viewBox="0 0 260 120" preserveAspectRatio="none" style={{ width: '100%', height: 120 }}>
            <path d={simArea} fill={RED} opacity="0.15" />
            <path d={simLine} fill="none" stroke={RED} strokeWidth="2" />
            <line x1="0" y1="36" x2="260" y2="36" stroke={RED} strokeDasharray="3 3" opacity="0.5" />
          </svg>
          <p style={{ margin: '10px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>Risk score per injected transaction, in order. Dashed line = block threshold {rp.blkLabel}.</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 14 }}>
            {displayStats.map((s) => (
              <span key={s.k} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12 }}><span style={{ color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{s.k}</span><span style={{ flex: 1, borderBottom: '1px dotted color-mix(in srgb,var(--color-text) 25%,transparent)' }} /><span style={{ fontFamily: 'var(--font-heading)', fontSize: 15, fontFeatureSettings: "'tnum' 1", color: s.c }}>{s.v}</span></span>
            ))}
          </div>
        </Blueprint>
      </div>
    </div>
  );
}
