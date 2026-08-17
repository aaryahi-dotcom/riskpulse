import type { RiskPulse, Layout, Frame } from '../../../state/useRiskPulse';
import { LayoutA } from './LayoutA';
import { LayoutB } from './LayoutB';
import { LayoutC } from './LayoutC';

export function Dashboard({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>Layout direction</span>
        <div className="seg">
          {rp.layoutOpts.map((l) => (
            <button key={l.key} type="button" onClick={() => rp.setLayout(l.key as Layout)} style={{ padding: '7px 14px', fontSize: 12.5, border: 0, borderLeft: '1px solid var(--color-divider)', background: l.bg, color: l.fg, cursor: 'pointer', whiteSpace: 'nowrap', fontFamily: 'var(--font-heading)', letterSpacing: '.06em', textTransform: 'uppercase' }}>{l.t}</button>
          ))}
        </div>
        <span style={{ flex: '1 1 180px', minWidth: 0, fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{rp.layoutNote}</span>
        <span style={{ fontSize: 11, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>Frame</span>
        <div className="seg">
          {rp.frameOpts.map((f) => (
            <button key={f.key} type="button" onClick={() => rp.setFrame(f.key as Frame)} style={{ padding: '7px 13px', fontSize: 12.5, border: 0, borderLeft: '1px solid var(--color-divider)', background: f.bg, color: f.fg, cursor: 'pointer', whiteSpace: 'nowrap', fontFamily: 'var(--font-heading)', letterSpacing: '.06em', textTransform: 'uppercase' }}>{f.t}</button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(158px,1fr))', border: '1px solid var(--color-divider)' }}>
        {rp.kpis.map((k) => (
          <div key={k.k} style={{ padding: '14px 16px', borderLeft: '1px solid var(--color-divider)' }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{k.k}</span>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: 7, marginTop: 5 }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 29, lineHeight: 1, fontFeatureSettings: "'tnum' 1", whiteSpace: 'nowrap', color: k.c }}>{k.v}</span>
              <span style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{k.d}</span>
            </span>
            <svg viewBox="0 0 120 22" preserveAspectRatio="none" style={{ width: '100%', height: 22, marginTop: 8 }}>
              <path d={k.spark} fill="none" stroke={k.c} strokeWidth="1.4" opacity="0.75" />
            </svg>
          </div>
        ))}
      </div>

      {rp.layout === 'A' && <LayoutA rp={rp} />}
      {rp.layout === 'B' && <LayoutB rp={rp} />}
      {rp.layout === 'C' && <LayoutC rp={rp} />}
    </div>
  );
}
