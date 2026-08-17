import type { RiskPulse } from '../../state/useRiskPulse';

export function Header({ rp }: { rp: RiskPulse }) {
  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 20, display: 'flex', alignItems: 'center', gap: 16, padding: '13px 24px', background: 'var(--color-bg)', borderBottom: '1px solid var(--color-divider)' }}>
      <span style={{ fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>Console /</span>
      <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 20, textTransform: 'uppercase', letterSpacing: '.02em' }}>{rp.screenTitle}</span>
      <span className="tag tag-neutral" style={{ marginLeft: 4 }}>{rp.screenNote}</span>
      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#c2604c', animation: rp.live ? 'rp-pulse 1.4s infinite' : 'none', opacity: rp.live ? 1 : 0.35 }} />
        {rp.liveLabel}
      </span>
      <button type="button" className="btn btn-secondary" onClick={rp.toggleLive} style={{ fontSize: 12 }}>{rp.liveCta}</button>
      <button type="button" className="btn btn-primary" onClick={rp.goSim} style={{ fontSize: 12 }}>Run scenario</button>
    </header>
  );
}
