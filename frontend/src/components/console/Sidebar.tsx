import type { RiskPulse } from '../../state/useRiskPulse';
import type { Screen } from '../../state/useRiskPulse';

export function Sidebar({ rp }: { rp: RiskPulse }) {
  return (
    <aside style={{ position: 'sticky', top: 0, height: '100vh', display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--color-divider)', background: 'var(--color-bg)' }}>
      <div style={{ padding: '18px 16px', borderBottom: '1px solid var(--color-divider)', cursor: 'pointer' }} onClick={rp.goLanding}>
        <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 19, textTransform: 'uppercase', letterSpacing: '.02em' }}>RiskPulse</span>
        <span style={{ display: 'block', fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>Federal Bank · Risk Ops</span>
      </div>
      <nav style={{ display: 'flex', flexDirection: 'column', padding: '8px 0' }}>
        {rp.navItems.map((n) => (
          <button
            key={n.key}
            type="button"
            onClick={() => rp.setScreen(n.key as Screen)}
            style={{
              display: 'grid', gridTemplateColumns: '24px 1fr auto', alignItems: 'center', gap: 8,
              textAlign: 'left', padding: '9px 16px', border: 0, borderLeft: `2px solid ${n.bar}`,
              background: n.bg, color: 'inherit', cursor: 'pointer', fontFamily: 'var(--font-heading)',
              fontWeight: 600, fontSize: 14, letterSpacing: '.05em', textTransform: 'uppercase',
            }}
          >
            <span style={{ fontSize: 10, fontFamily: 'var(--font-body)', letterSpacing: '.06em', color: 'color-mix(in srgb,var(--color-text) 50%,transparent)' }}>{n.n}</span>
            <span>{n.t}</span>
            <span className="tag tag-accent" style={{ fontSize: 9.5, padding: '1px 6px', display: n.badgeShow as 'inline-flex' | 'none' }}>{n.badge}</span>
          </button>
        ))}
      </nav>
      <div style={{ marginTop: 'auto', padding: '14px 16px', borderTop: '1px solid var(--color-divider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#5f9d84', animation: 'rp-pulse 2s infinite' }} />Engine online
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginTop: 10 }}>
          <span style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>xgb_v4 · p95 78ms</span>
          <button type="button" className="btn btn-secondary" onClick={rp.toggleTheme} style={{ width: 30, height: 30, padding: 0, fontSize: 12 }}>{rp.themeGlyph}</button>
        </div>
      </div>
    </aside>
  );
}
