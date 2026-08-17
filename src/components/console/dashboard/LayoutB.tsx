import { Blueprint } from '../../ui/Blueprint';
import type { RiskPulse } from '../../../state/useRiskPulse';

export function LayoutB({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '296px minmax(0,1fr) 240px', gap: 20, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Risk score · {rp.sel.id}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 12 }}>
            <div style={{ position: 'relative', width: 104, height: 104, flex: 'none' }}>
              <svg viewBox="0 0 120 120" style={{ width: 104, height: 104, display: 'block' }}>
                <circle cx="60" cy="60" r="48" fill="none" stroke="color-mix(in srgb, currentColor 12%, transparent)" strokeWidth="12" />
                <circle cx="60" cy="60" r="48" fill="none" stroke={rp.sel.color} strokeWidth="12" strokeDasharray={rp.sel.ringDash} transform="rotate(-90 60 60)" />
              </svg>
              <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 30, fontFeatureSettings: "'tnum' 1" }}>{rp.sel.score}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span className="tag" style={{ background: rp.sel.tint, color: rp.sel.color, alignSelf: 'flex-start' }}>{rp.sel.dec}</span>
              <span style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 68%,transparent)' }}>{rp.sel.band}</span>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 20, fontFeatureSettings: "'tnum' 1" }}>{rp.sel.amt}</span>
              <span style={{ fontSize: 11, fontFamily: 'ui-monospace,Menlo,monospace', color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{rp.sel.to}</span>
            </div>
          </div>
        </Blueprint>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 8 }}>Why it scored</span>
          {rp.shap.map((s) => (
            <div key={s.n} style={{ padding: '6px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
              <span style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 4 }}><span style={{ fontFamily: 'ui-monospace,Menlo,monospace' }}>{s.n}</span><span style={{ color: s.c, fontFeatureSettings: "'tnum' 1" }}>{s.v}</span></span>
              <span style={{ position: 'relative', display: 'block', height: 8, background: 'color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <span style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'color-mix(in srgb,currentColor 25%,transparent)' }} />
                <span style={{ position: 'absolute', top: 0, height: 8, left: s.left, width: s.w, background: s.c }} />
              </span>
            </div>
          ))}
        </Blueprint>
      </div>
      <Blueprint style={{ padding: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', borderBottom: '1px solid var(--color-divider)' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 13, letterSpacing: '.1em', textTransform: 'uppercase' }}>Stream</span>
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{rp.feed.length} in window</span>
        </div>
        <div className="rp-scroll" style={{ maxHeight: 620, overflow: 'auto' }}>
          {rp.feed.map((t) => (
            <div key={t.id} onClick={() => rp.pickTxn(t.id)} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 14px', padding: '13px 16px', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 8%,transparent)', cursor: 'pointer', background: t.selected ? 'color-mix(in srgb, var(--color-accent) 12%, transparent)' : 'transparent', borderLeft: `3px solid ${t.color}` }}>
              <span style={{ display: 'flex', alignItems: 'baseline', gap: 9 }}>
                <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 22, lineHeight: 1, fontFeatureSettings: "'tnum' 1", color: t.color }}>{t.score}</span>
                <span style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5 }}>{t.id}</span>
                <span className="tag" style={{ background: t.tint, color: t.color, fontSize: 10 }}>{t.dec}</span>
              </span>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 19, fontFeatureSettings: "'tnum' 1", textAlign: 'right' }}>{t.amt}</span>
              <span style={{ fontSize: 11.5, fontFamily: 'ui-monospace,Menlo,monospace', color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{t.from} → {t.to}</span>
              <span style={{ fontSize: 11, fontFeatureSettings: "'tnum' 1", textAlign: 'right', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{t.time} · {t.flagLine}</span>
            </div>
          ))}
        </div>
      </Blueprint>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {rp.miniCharts.map((m) => (
          <Blueprint key={m.k} style={{ padding: 14 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{m.k}</span>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: 6, margin: '4px 0 6px' }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 26, lineHeight: 1, fontFeatureSettings: "'tnum' 1", color: m.c }}>{m.v}</span>
              <span style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{m.d}</span>
            </span>
            <svg viewBox="0 0 200 44" preserveAspectRatio="none" style={{ width: '100%', height: 44 }}>
              <path d={m.area} fill={m.c} opacity="0.14" />
              <path d={m.line} fill="none" stroke={m.c} strokeWidth="1.6" />
            </svg>
          </Blueprint>
        ))}
      </div>
    </div>
  );
}
