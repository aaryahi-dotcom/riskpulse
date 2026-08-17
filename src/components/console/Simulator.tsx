import { Blueprint } from '../ui/Blueprint';
import { simLog, simSeries, simStats, line, area, RED } from '../../lib/mock';
import type { RiskPulse, ScenarioKey } from '../../state/useRiskPulse';

const simLine = line(simSeries, 260, 120, 6);
const simArea = area(simSeries, 260, 120, 6);

export function Simulator({ rp }: { rp: RiskPulse }) {
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
            <button type="button" className="btn btn-primary btn-block" onClick={() => rp.runScenario(s.key as ScenarioKey)}>{s.cta}</button>
          </Blueprint>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 22, alignItems: 'start' }}>
        <Blueprint style={{ padding: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', borderBottom: '1px solid var(--color-divider)' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: rp.simDotColor, animation: 'rp-pulse 1.4s infinite' }} />
            <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.1em', textTransform: 'uppercase' }}>Injection log</span>
            <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{rp.simStatus}</span>
          </div>
          <div style={{ padding: '14px 16px', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, lineHeight: 1.9 }}>
            {simLog.map((l, i) => (
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
          <p style={{ margin: '10px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>Mean risk score across injected transactions. Dashed line = block threshold {rp.blkLabel}.</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 14 }}>
            {simStats.map((s) => (
              <span key={s.k} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12 }}><span style={{ color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{s.k}</span><span style={{ flex: 1, borderBottom: '1px dotted color-mix(in srgb,var(--color-text) 25%,transparent)' }} /><span style={{ fontFamily: 'var(--font-heading)', fontSize: 15, fontFeatureSettings: "'tnum' 1", color: s.c }}>{s.v}</span></span>
            ))}
          </div>
        </Blueprint>
      </div>
    </div>
  );
}
