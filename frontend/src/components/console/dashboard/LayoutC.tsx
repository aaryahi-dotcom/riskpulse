import { Blueprint } from '../../ui/Blueprint';
import type { RiskPulse } from '../../../state/useRiskPulse';

export function LayoutC({ rp }: { rp: RiskPulse }) {
  return (
    <Blueprint style={{ padding: 0 }}>
      <header style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid var(--color-divider)', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.09em', textTransform: 'uppercase' }}>
        <span style={{ flex: 1, minWidth: '18ch', padding: '11px 20px' }}>Scoring log — {rp.today}</span>
        <span style={{ padding: '11px 20px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Model xgb_v4</span>
        <span style={{ padding: '11px 20px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Thresholds {rp.apprLabel} / {rp.blkLabel}</span>
        <span style={{ padding: '11px 20px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Sheet 01 of 01</span>
      </header>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', borderBottom: '1px solid var(--color-divider)' }}>
        <div style={{ padding: '16px 20px' }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Score distribution</span>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 82 }}>
            {rp.hist.map((h, i) => <span key={i} style={{ flex: 1, height: h.h, background: h.c, opacity: 0.85 }} />)}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginTop: 5, color: 'color-mix(in srgb,var(--color-text) 52%,transparent)' }}><span>0.0</span><span>0.5</span><span>1.0</span></div>
        </div>
        <div style={{ padding: '16px 20px', borderLeft: '1px solid var(--color-divider)' }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Hourly throughput</span>
          <svg viewBox="0 0 300 82" preserveAspectRatio="none" style={{ width: '100%', height: 82 }}>
            <path d={rp.volArea} fill="var(--color-accent)" opacity="0.16" />
            <path d={rp.volLine} fill="none" stroke="var(--color-accent)" strokeWidth="1.6" />
          </svg>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginTop: 5, color: 'color-mix(in srgb,var(--color-text) 52%,transparent)' }}><span>00:00</span><span>12:00</span><span>23:59</span></div>
        </div>
        <div style={{ padding: '16px 20px', borderLeft: '1px solid var(--color-divider)' }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Decision mix</span>
          <div style={{ display: 'flex', height: 22 }}>
            {rp.split.map((s) => <span key={s.k} style={{ width: s.w, background: s.c }} />)}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 12 }}>
            {rp.split.map((s) => (
              <span key={s.k} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5 }}><span style={{ width: 9, height: 9, background: s.c }} />{s.k}<span style={{ marginLeft: 'auto', fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1" }}>{s.v}</span></span>
            ))}
          </div>
        </div>
      </div>
      <table className="table" style={{ fontSize: 13 }}>
        <thead><tr><th style={{ paddingLeft: 20 }}>№</th><th>Txn</th><th>Time</th><th>Sender</th><th>Beneficiary</th><th style={{ textAlign: 'right' }}>Amount</th><th>Score</th><th>Puppet</th><th>Graph</th><th style={{ paddingRight: 20 }}>Decision</th></tr></thead>
        <tbody>
          {rp.feed.map((t) => (
            <tr key={t.id} onClick={() => rp.pickTxn(t.id)} style={{ cursor: 'pointer', background: t.selected ? 'color-mix(in srgb, var(--color-accent) 12%, transparent)' : 'transparent' }}>
              <td style={{ paddingLeft: 20, fontSize: 11, color: 'var(--color-accent-700)', fontWeight: 600 }}>{t.n}</td>
              <td style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5 }}>{t.id}</td>
              <td style={{ fontFeatureSettings: "'tnum' 1", color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{t.time}</td>
              <td style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5 }}>{t.from}</td>
              <td style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, color: t.color }}>{t.to}</td>
              <td style={{ textAlign: 'right', fontFamily: 'var(--font-heading)', fontSize: 15, fontFeatureSettings: "'tnum' 1" }}>{t.amt}</td>
              <td><span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 44, height: 5, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 5, width: t.pct, background: t.color }} /></span><span style={{ fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1" }}>{t.score}</span></span></td>
              <td style={{ fontFeatureSettings: "'tnum' 1", color: t.puppetColor }}>{t.puppet}</td>
              <td style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{t.flagLine}</td>
              <td style={{ paddingRight: 20 }}><span className="tag" style={{ background: t.tint, color: t.color }}>{t.dec}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ margin: 0, padding: '11px 20px', borderTop: '1px solid var(--color-divider)', fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 68%,transparent)' }}>Rows are immutable audit records. Overrides are appended in the workbench, never edited here.</p>
    </Blueprint>
  );
}
