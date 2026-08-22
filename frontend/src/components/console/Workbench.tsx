import { useEffect, useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { analystStats, linked, timeline, miniNodes, miniLinks, RED, AMBER, GREEN, money } from '../../lib/mock';
import {
  submitFeedback, getFeedbackStats, getLinkedTransactions, getFeedbackForTxn, getAudit,
  type FeedbackStatsDTO, type LinkedTransactionDTO, type FeedbackDTO,
} from '../../lib/api';
import type { RiskPulse } from '../../state/useRiskPulse';

type TimelineEvent = { t: string; d: string; c: string };

function toAnalystStats(s: FeedbackStatsDTO) {
  return [
    { k: 'Reviewed', v: String(s.total_reviewed), w: '100%', c: 'var(--color-accent)' },
    { k: 'Overrides', v: String(s.overrides), w: (s.total_reviewed ? (s.overrides / s.total_reviewed) * 100 : 0) + '%', c: AMBER },
    { k: 'Model agreement', v: Math.round(s.agreement_rate * 100) + '%', w: Math.round(s.agreement_rate * 100) + '%', c: GREEN },
  ];
}

function toLinkedRows(rows: LinkedTransactionDTO[]) {
  return rows.slice(0, 6).map((r) => ({
    id: r.txn_id, amt: money(r.amount), s: r.risk_score.toFixed(2),
    c: r.decision === 'block' ? RED : r.decision === 'step_up' ? AMBER : GREEN,
  }));
}

async function buildTimeline(txnId: string): Promise<TimelineEvent[]> {
  const [audit, fb] = await Promise.all([getAudit(txnId), getFeedbackForTxn(txnId)]);
  const events: TimelineEvent[] = [{
    t: new Date(audit.created_at).toTimeString().slice(0, 5),
    d: `Scored ${audit.risk_score.toFixed(2)} · ${audit.decision.replace('_', '-')}`,
    c: audit.decision === 'block' ? RED : audit.decision === 'step_up' ? AMBER : GREEN,
  }];
  (fb as FeedbackDTO[]).forEach((f) => {
    events.push({
      t: new Date().toTimeString().slice(0, 5),
      d: f.overridden_decision ? `Analyst override → ${f.confirmed_label}` : `Analyst confirmed ${f.confirmed_label}`,
      c: f.confirmed_label === 'fraud' ? RED : GREEN,
    });
  });
  return events;
}

export function Workbench({ rp }: { rp: RiskPulse }) {
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [liveStats, setLiveStats] = useState<FeedbackStatsDTO | null>(null);
  const [liveLinked, setLiveLinked] = useState<LinkedTransactionDTO[] | null>(null);
  const [liveTimeline, setLiveTimeline] = useState<TimelineEvent[] | null>(null);

  useEffect(() => {
    getFeedbackStats().then(setLiveStats).catch(() => setLiveStats(null));
  }, [feedbackMsg]);

  useEffect(() => {
    getLinkedTransactions(rp.sel.id).then(setLiveLinked).catch(() => setLiveLinked(null));
    buildTimeline(rp.sel.id).then(setLiveTimeline).catch(() => setLiveTimeline(null));
  }, [rp.sel.id]);

  const displayAnalystStats = liveStats && liveStats.total_reviewed > 0 ? toAnalystStats(liveStats) : analystStats;
  const displayLinked = liveLinked && liveLinked.length > 0 ? toLinkedRows(liveLinked) : linked;
  const displayTimeline = liveTimeline && liveTimeline.length > 0 ? liveTimeline : timeline;

  const sendFeedback = async (label: 'fraud' | 'legit') => {
    setSubmitting(true);
    setFeedbackMsg(null);
    try {
      await submitFeedback(rp.sel.id, label, label === 'legit' && rp.sel.dec !== 'Approve');
      setFeedbackMsg(
        label === 'fraud'
          ? `Confirmed fraud on ${rp.sel.id} — contagion propagation queued.`
          : `Recorded override — approve on ${rp.sel.id}.`,
      );
      buildTimeline(rp.sel.id).then(setLiveTimeline).catch(() => {});
    } catch {
      setFeedbackMsg('Backend unreachable — feedback not recorded.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '290px minmax(0,1fr)', gap: 22, alignItems: 'start' }}>
      <Blueprint style={{ padding: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '11px 14px', borderBottom: '1px solid var(--color-divider)' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.1em', textTransform: 'uppercase' }}>Queue</span>
          <span className="tag tag-accent" style={{ marginLeft: 'auto', fontSize: 10 }}>18 open</span>
        </div>
        <div className="rp-scroll" style={{ maxHeight: 620, overflow: 'auto' }}>
          {rp.feed.map((t) => (
            <div key={t.id} onClick={() => rp.pickTxn(t.id)} style={{ padding: '11px 14px', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 8%,transparent)', cursor: 'pointer', background: t.selected ? 'color-mix(in srgb, var(--color-accent) 12%, transparent)' : 'transparent', borderLeft: `3px solid ${t.color}` }}>
              <span style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 18, fontFeatureSettings: "'tnum' 1", color: t.color }}>{t.score}</span>
                <span style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11 }}>{t.id}</span>
                <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-heading)', fontSize: 14, fontFeatureSettings: "'tnum' 1" }}>{t.amt}</span>
              </span>
              <span style={{ display: 'block', fontSize: 11, marginTop: 3, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{t.flagLine}</span>
            </div>
          ))}
        </div>
      </Blueprint>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        <Blueprint style={{ padding: 0 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid var(--color-divider)', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.09em', textTransform: 'uppercase' }}>
            <span style={{ flex: 1, minWidth: '14ch', padding: '11px 18px' }}>Case {rp.sel.id}</span>
            <span style={{ padding: '11px 18px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Assigned · Priya N.</span>
            <span style={{ padding: '11px 18px', borderLeft: '1px solid var(--color-divider)', color: rp.sel.color }}>{rp.sel.dec}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(258px,1fr))' }}>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
              <div style={{ position: 'relative', width: 130, height: 130 }}>
                <svg viewBox="0 0 120 120" style={{ width: 130, height: 130, display: 'block' }}>
                  <circle cx="60" cy="60" r="48" fill="none" stroke="color-mix(in srgb, currentColor 12%, transparent)" strokeWidth="12" />
                  <circle cx="60" cy="60" r="48" fill="none" stroke={rp.sel.color} strokeWidth="12" strokeDasharray={rp.sel.ringDash} transform="rotate(-90 60 60)" />
                </svg>
                <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 32, fontFeatureSettings: "'tnum' 1" }}>{rp.sel.score}</span>
              </div>
              <span style={{ fontSize: 11.5, textAlign: 'center', color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{rp.sel.band}</span>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 24, fontFeatureSettings: "'tnum' 1" }}>{rp.sel.amt}</span>
              <span style={{ fontSize: 11, fontFamily: 'ui-monospace,Menlo,monospace', color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>→ {rp.sel.to}</span>
            </div>
            <div style={{ padding: 18, borderLeft: '1px solid var(--color-divider)' }}>
              <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 8 }}>SHAP waterfall</span>
              {rp.shap.map((s) => (
                <div key={s.n} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,148px) 1fr 44px', alignItems: 'center', gap: 10, padding: '4px 0' }}>
                  <span style={{ fontSize: 11, fontFamily: 'ui-monospace,Menlo,monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.n}</span>
                  <span style={{ position: 'relative', display: 'block', height: 11, background: 'color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                    <span style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'color-mix(in srgb,currentColor 25%,transparent)' }} />
                    <span style={{ position: 'absolute', top: 0, height: 11, left: s.left, width: s.w, background: s.c }} />
                  </span>
                  <span style={{ fontSize: 11, fontFeatureSettings: "'tnum' 1", textAlign: 'right', color: s.c }}>{s.v}</span>
                </div>
              ))}
              <ul style={{ margin: '10px 0 0', padding: '8px 0 0 16px', borderTop: '1px solid var(--color-divider)', display: 'flex', flexDirection: 'column', gap: 3 }}>
                {rp.shapReasons.map((r, i) => (
                  <li key={i} style={{ fontSize: 10.5, lineHeight: 1.45, color: 'color-mix(in srgb,var(--color-text) 78%,transparent)' }}>{r}</li>
                ))}
              </ul>
            </div>
            <div style={{ padding: 18, borderLeft: '1px solid var(--color-divider)' }}>
              <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 8 }}>Neighbourhood · 2 hop</span>
              <svg viewBox="0 0 240 170" style={{ width: '100%' }}>
                {miniLinks.map((l, i) => <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="color-mix(in srgb, currentColor 22%, transparent)" strokeWidth="1" />)}
                {miniNodes.map((n, i) => <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.f} stroke={n.c} strokeWidth="1.5" />)}
              </svg>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 10, fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>
                <span>PageRank 0.049 · Δ24h +0.048</span>
                <span>Clustering 0.71 · degree in/out 9:1</span>
                <span>Cycle closed at hop 2 · mule cluster #14</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', padding: '14px 18px', borderTop: '1px solid var(--color-divider)' }}>
            <button type="button" className="btn" disabled={submitting} onClick={() => sendFeedback('fraud')} style={{ background: RED, color: 'var(--color-bg)', borderColor: RED, padding: '10px 18px' }}>Confirm fraud</button>
            <button type="button" className="btn btn-secondary" disabled={submitting} onClick={() => sendFeedback('legit')} style={{ padding: '10px 18px' }}>Override — approve</button>
            <select className="input" style={{ width: 220 }}>
              <option>Reason — known customer</option>
              <option>Expected purchase</option>
              <option>Verified by phone</option>
              <option>Merchant whitelisted</option>
            </select>
            <span style={{ marginLeft: 'auto', fontSize: 11.5, color: feedbackMsg ? (feedbackMsg.startsWith('Backend') ? RED : GREEN) : 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
              {feedbackMsg ?? 'Confirming fraud triggers contagion propagation (depth 3).'}
            </span>
          </div>
        </Blueprint>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 22 }}>
          <Blueprint style={{ padding: 16 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Analyst accuracy · {liveStats && liveStats.total_reviewed > 0 ? liveStats.analyst : 'Priya N.'}</span>
            {displayAnalystStats.map((a) => (
              <div key={a.k} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '5px 0', fontSize: 12 }}>
                <span style={{ width: 96 }}>{a.k}</span>
                <span style={{ flex: 1, height: 7, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 7, width: a.w, background: a.c }} /></span>
                <span style={{ fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1" }}>{a.v}</span>
              </div>
            ))}
          </Blueprint>
          <Blueprint style={{ padding: 16 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Linked transactions</span>
            <table className="table" style={{ fontSize: 12 }}>
              <tbody>
                {displayLinked.map((l) => (
                  <tr key={l.id}><td style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11 }}>{l.id}</td><td style={{ fontFeatureSettings: "'tnum' 1" }}>{l.amt}</td><td style={{ color: l.c }}>{l.s}</td></tr>
                ))}
              </tbody>
            </table>
          </Blueprint>
          <Blueprint style={{ padding: 16 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Session timeline</span>
            {displayTimeline.map((e, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '52px 1fr', gap: 10, padding: '4px 0', fontSize: 11.5 }}>
                <span style={{ fontFeatureSettings: "'tnum' 1", color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{e.t}</span>
                <span style={{ borderLeft: `2px solid ${e.c}`, paddingLeft: 9 }}>{e.d}</span>
              </div>
            ))}
          </Blueprint>
        </div>
      </div>
    </div>
  );
}
