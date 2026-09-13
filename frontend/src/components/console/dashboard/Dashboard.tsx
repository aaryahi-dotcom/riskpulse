import type { RiskPulse } from '../../../state/useRiskPulse';
import { LayoutA } from './LayoutA';

export function Dashboard({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
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

      <LayoutA rp={rp} />
    </div>
  );
}
