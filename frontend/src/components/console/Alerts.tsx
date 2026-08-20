import { useEffect, useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { alertKpis as mockKpis, alertGroups as mockGroups, scatter, AMBER, GREEN, RED, money, tint } from '../../lib/mock';
import { getAlertsGrouped, type AlertCaseDTO } from '../../lib/api';

type DisplayGroup = typeof mockGroups[number];

const groupTitle = (c: AlertCaseDTO) =>
  c.group_type === 'proactive_exposure' ? `Likely next victim · ${c.group_key}`
    : c.group_type === 'sender_pattern' ? `Sender fan-out · ${c.group_key}`
    : `Case · ${c.group_key}`;
const groupRule = (c: AlertCaseDTO) =>
  c.group_type === 'proactive_exposure' ? 'Contagion exposure ≥ threshold'
    : c.group_type === 'sender_pattern' ? 'Same sender · ≥2 beneficiaries · 24h'
    : 'Same beneficiary · 24h window';
const priorityTier = (c: AlertCaseDTO): ['P1' | 'P2' | 'P3', string] =>
  c.avg_risk_score >= 0.7 || c.priority > 500000 ? ['P1', RED] : c.avg_risk_score >= 0.4 ? ['P2', AMBER] : ['P3', 'var(--color-accent)'];

function toDisplayGroup(c: AlertCaseDTO): DisplayGroup {
  const [pr, color] = priorityTier(c);
  return {
    t: groupTitle(c), pr, c: color, tint: tint(color), rule: groupRule(c),
    cells: [
      { k: 'Transactions', v: String(c.txn_count) },
      { k: 'Value at risk', v: money(c.total_amount_at_risk) },
      { k: 'Avg risk score', v: c.avg_risk_score.toFixed(2) },
      { k: 'Priority', v: c.priority.toFixed(0) },
    ],
    bars: Array.from({ length: 12 }, (_, i) => ({ h: Math.max(10, Math.min(100, (c.avg_risk_score * 100) - 20 + i * 3)) + '%' })),
  };
}

export function Alerts() {
  const [live, setLive] = useState<{ kpis: typeof mockKpis; groups: DisplayGroup[] } | null>(null);

  useEffect(() => {
    getAlertsGrouped()
      .then((data) => {
        const valueAtRisk = data.cases.reduce((s, c) => s + c.total_amount_at_risk, 0);
        setLive({
          kpis: [
            { k: 'Raw alerts · 24h', v: String(data.total_alerts), d: 'before grouping', c: 'var(--color-accent-700)' },
            { k: 'Grouped cases', v: String(data.total_cases), d: 'live from /alerts/grouped', c: AMBER },
            { k: 'Value at risk', v: money(valueAtRisk), d: 'across open cases', c: RED },
            { k: 'Highest priority', v: data.cases[0]?.group_key ?? '—', d: data.cases[0] ? priorityTier(data.cases[0])[0] : '—', c: GREEN },
          ],
          groups: data.cases.slice(0, 8).map(toDisplayGroup),
        });
      })
      .catch(() => setLive(null));
  }, []);

  const alertKpis = live?.kpis ?? mockKpis;
  const alertGroups = live && live.groups.length ? live.groups : mockGroups;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', border: '1px solid var(--color-divider)' }}>
        {alertKpis.map((k) => (
          <div key={k.k} style={{ padding: '14px 16px', borderLeft: '1px solid var(--color-divider)' }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{k.k}</span>
            <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 30, lineHeight: 1.1, fontFeatureSettings: "'tnum' 1", color: k.c }}>{k.v}</span>
            <span style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{k.d}</span>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 22, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {alertGroups.map((g) => (
            <Blueprint key={g.t} style={{ padding: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: '1px solid var(--color-divider)', borderLeft: `4px solid ${g.c}` }}>
                <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 17, textTransform: 'uppercase', letterSpacing: '.02em' }}>{g.t}</span>
                <span className="tag" style={{ background: g.tint, color: g.c, fontSize: 10 }}>{g.pr}</span>
                <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{g.rule}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr) 150px', alignItems: 'center' }}>
                {g.cells.map((c) => (
                  <div key={c.k} style={{ padding: '13px 16px', borderLeft: '1px solid var(--color-divider)' }}>
                    <span style={{ display: 'block', fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{c.k}</span>
                    <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 21, fontFeatureSettings: "'tnum' 1" }}>{c.v}</span>
                  </div>
                ))}
                <div style={{ padding: '13px 16px', borderLeft: '1px solid var(--color-divider)', display: 'flex', flexDirection: 'column', gap: 7 }}>
                  <span style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 34 }}>
                    {g.bars.map((b, i) => <span key={i} style={{ flex: 1, height: b.h, background: g.c, opacity: 0.75 }} />)}
                  </span>
                  <button type="button" className="btn btn-secondary" style={{ fontSize: 11.5, padding: '5px 10px' }}>Open case</button>
                </div>
              </div>
            </Blueprint>
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Blueprint style={{ padding: 16 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 12 }}>Grouping compression</span>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16 }}>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <span style={{ display: 'block', height: 120, background: 'color-mix(in srgb,var(--color-text) 12%,transparent)', position: 'relative' }}><span style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '100%', background: AMBER, opacity: 0.8 }} /></span>
                <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontSize: 20, marginTop: 6, fontFeatureSettings: "'tnum' 1" }}>512</span>
                <span style={{ display: 'block', fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>raw alerts</span>
              </div>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <span style={{ display: 'block', height: 120, background: 'color-mix(in srgb,var(--color-text) 12%,transparent)', position: 'relative' }}><span style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '6%', background: GREEN }} /></span>
                <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontSize: 20, marginTop: 6, fontFeatureSettings: "'tnum' 1" }}>30</span>
                <span style={{ display: 'block', fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>grouped cases</span>
              </div>
            </div>
            <p style={{ margin: '12px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>Same beneficiary within 24 h, same sender pattern, or same graph cluster collapse into one case.</p>
          </Blueprint>
          <Blueprint style={{ padding: 16 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 12 }}>Priority = loss × confidence</span>
            <svg viewBox="0 0 240 150" style={{ width: '100%' }}>
              <line x1="24" y1="126" x2="236" y2="126" stroke="color-mix(in srgb, currentColor 18%, transparent)" />
              <line x1="24" y1="8" x2="24" y2="126" stroke="color-mix(in srgb, currentColor 18%, transparent)" />
              {scatter.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={p.r} fill={p.c} opacity="0.65" />)}
              <text x="130" y="145" textAnchor="middle" style={{ fontSize: 9, fill: 'currentColor', opacity: 0.55, fontFamily: 'var(--font-body)' }}>confidence →</text>
            </svg>
          </Blueprint>
        </div>
      </div>
    </div>
  );
}
