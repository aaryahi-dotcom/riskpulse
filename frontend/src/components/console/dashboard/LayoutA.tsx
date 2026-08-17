import { Blueprint } from '../../ui/Blueprint';
import type { RiskPulse } from '../../../state/useRiskPulse';

export function LayoutA({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 300px', gap: 22 }}>
        <Blueprint style={{ padding: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', borderBottom: '1px solid var(--color-divider)' }}>
            <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 13, letterSpacing: '.1em', textTransform: 'uppercase' }}>Live transaction feed</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>WS /ws/transactions · click a row to explain</span>
          </div>
          <div className="rp-scroll" style={{ maxHeight: 404, overflow: 'auto' }}>
            <table className="table" style={{ fontSize: 13 }}>
              <thead><tr><th>Txn</th><th>Time</th><th>Sender → Beneficiary</th><th style={{ textAlign: 'right' }}>Amount</th><th style={{ width: 150 }}>Score</th><th>Decision</th></tr></thead>
              <tbody>
                {rp.feed.map((t) => (
                  <tr key={t.id} onClick={() => rp.pickTxn(t.id)} style={{ cursor: 'pointer', background: t.selected ? 'color-mix(in srgb, var(--color-accent) 12%, transparent)' : 'transparent' }}>
                    <td style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5 }}>{t.id}</td>
                    <td style={{ fontFeatureSettings: "'tnum' 1", color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{t.time}</td>
                    <td style={{ fontSize: 12 }}><span style={{ fontFamily: 'ui-monospace,Menlo,monospace' }}>{t.from}</span> → <span style={{ fontFamily: 'ui-monospace,Menlo,monospace', color: t.color }}>{t.to}</span></td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-heading)', fontSize: 15, fontFeatureSettings: "'tnum' 1" }}>{t.amt}</td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ flex: 1, height: 6, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 6, width: t.pct, background: t.color }} /></span>
                        <span style={{ fontFamily: 'var(--font-heading)', fontSize: 14, fontFeatureSettings: "'tnum' 1", width: 32 }}>{t.score}</span>
                      </span>
                    </td>
                    <td><span className="tag" style={{ background: t.tint, color: t.color, fontWeight: 500 }}>{t.dec}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Blueprint>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Blueprint style={{ padding: 18, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ alignSelf: 'flex-start', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Selected · {rp.sel.id}</span>
            <div style={{ position: 'relative', width: '100%', maxWidth: 200, marginTop: 6 }}>
              <svg viewBox="0 0 160 96" style={{ width: '100%', display: 'block' }}>
                <path d="M18 88 A62 62 0 0 1 142 88" fill="none" stroke="color-mix(in srgb, currentColor 12%, transparent)" strokeWidth="13" strokeLinecap="butt" />
                <path d="M18 88 A62 62 0 0 1 142 88" fill="none" stroke={rp.sel.color} strokeWidth="13" strokeLinecap="butt" strokeDasharray={rp.sel.dash} />
              </svg>
              <span style={{ position: 'absolute', left: 0, right: 0, bottom: '8%', textAlign: 'center', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 38, lineHeight: 1, fontFeatureSettings: "'tnum' 1", whiteSpace: 'nowrap' }}>{rp.sel.score}</span>
            </div>
            <span className="tag" style={{ background: rp.sel.tint, color: rp.sel.color, marginTop: 2 }}>{rp.sel.dec} · {rp.sel.band}</span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 12 }}>
              {rp.sel.flags.map((f) => <span key={f} className="tag tag-outline" style={{ fontSize: 10 }}>{f}</span>)}
            </div>
          </Blueprint>
          <Blueprint style={{ padding: 18 }}>
            <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 14 }}>Decision split · 24h</span>
            {rp.split.map((s) => (
              <div key={s.k} style={{ marginBottom: 12 }}>
                <span style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}><span>{s.k}</span><span style={{ fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1" }}>{s.v}</span></span>
                <span style={{ display: 'block', height: 8, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 8, width: s.w, background: s.c }} /></span>
              </div>
            ))}
          </Blueprint>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,7fr) minmax(0,5fr)', gap: 22 }}>
        <Blueprint style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
            <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Volume &amp; flagged rate · 24h</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 14, fontSize: 11 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: 'var(--color-accent)' }} />Scored</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: '#c2604c' }} />Flagged</span>
            </span>
          </div>
          <svg viewBox="0 0 600 190" preserveAspectRatio="none" style={{ width: '100%', height: 190 }}>
            {rp.gridLines.map((g) => <line key={g.y} x1="0" y1={g.y} x2="600" y2={g.y} stroke="color-mix(in srgb, currentColor 10%, transparent)" strokeWidth="1" />)}
            <path d={rp.volArea} fill="var(--color-accent)" opacity="0.14" />
            <path d={rp.volLine} fill="none" stroke="var(--color-accent)" strokeWidth="2" />
            <path d={rp.flagLine} fill="none" stroke="#c2604c" strokeWidth="2" strokeDasharray="5 3" />
          </svg>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, fontFeatureSettings: "'tnum' 1", color: 'color-mix(in srgb,var(--color-text) 52%,transparent)', marginTop: 6 }}>
            <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:59</span>
          </div>
        </Blueprint>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 6 }}>SHAP contribution · {rp.sel.id}</span>
          {rp.shap.map((s) => (
            <div key={s.n} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,150px) 1fr 44px', alignItems: 'center', gap: 10, padding: '5px 0' }}>
              <span style={{ fontSize: 11.5, fontFamily: 'ui-monospace,Menlo,monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.n}</span>
              <span style={{ position: 'relative', display: 'block', height: 12, background: 'color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <span style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'color-mix(in srgb,currentColor 25%,transparent)' }} />
                <span style={{ position: 'absolute', top: 0, height: 12, left: s.left, width: s.w, background: s.c }} />
              </span>
              <span style={{ fontSize: 11.5, fontFeatureSettings: "'tnum' 1", textAlign: 'right', color: s.c }}>{s.v}</span>
            </div>
          ))}
          <p style={{ margin: '12px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>Base value {rp.shapBase} → output {rp.sel.score}. TreeExplainer, computed in the response path (~4 ms).</p>
        </Blueprint>
      </div>
    </div>
  );
}
