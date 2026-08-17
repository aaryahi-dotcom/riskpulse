import { Blueprint } from '../ui/Blueprint';
import { healthKpis, healthLegend, healthSeries, deployMarks, importance, latency, versions, feedbackStats, AMBER, RED } from '../../lib/mock';
import type { RiskPulse } from '../../state/useRiskPulse';

export function Health({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(158px,1fr))', border: '1px solid var(--color-divider)' }}>
        {healthKpis.map((k) => (
          <div key={k.k} style={{ padding: '14px 16px', borderLeft: '1px solid var(--color-divider)' }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{k.k}</span>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}><span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 30, lineHeight: 1.15, fontFeatureSettings: "'tnum' 1", whiteSpace: 'nowrap', color: k.c }}>{k.v}</span><span style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{k.d}</span></span>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,7fr) minmax(0,5fr)', gap: 22 }}>
        <Blueprint style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 14 }}>
            <span style={{ fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Metrics from analyst feedback · 90 days</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 14, fontSize: 11 }}>
              {healthLegend.map((l) => (
                <span key={l.k} style={{ display: 'flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: l.c }} />{l.k}</span>
              ))}
            </span>
          </div>
          <svg viewBox="0 0 600 200" preserveAspectRatio="none" style={{ width: '100%', height: 200 }}>
            {rp.gridLines.map((g) => <line key={g.y} x1="0" y1={g.y} x2="600" y2={g.y} stroke="color-mix(in srgb, currentColor 10%, transparent)" />)}
            {healthSeries.map((s, i) => <path key={i} d={s.d} fill="none" stroke={s.c} strokeWidth="2" strokeDasharray={s.dash} />)}
            {deployMarks.map((m, i) => <line key={i} x1={m.x} y1="0" x2={m.x} y2="200" stroke="var(--color-accent)" strokeWidth="1" strokeDasharray="2 4" opacity="0.7" />)}
          </svg>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, marginTop: 6, color: 'color-mix(in srgb,var(--color-text) 52%,transparent)' }}><span>−90d</span><span>−60d</span><span>−30d</span><span>today</span></div>
        </Blueprint>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 12 }}>Feature importance &amp; drift</span>
          {importance.map((f) => (
            <div key={f.n} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,156px) 1fr 58px', alignItems: 'center', gap: 10, padding: '4px 0' }}>
              <span style={{ fontSize: 11, fontFamily: 'ui-monospace,Menlo,monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.n}</span>
              <span style={{ display: 'block', height: 10, background: 'color-mix(in srgb,var(--color-text) 8%,transparent)' }}><span style={{ display: 'block', height: 10, width: f.w, background: 'var(--color-accent)' }} /></span>
              <span style={{ fontSize: 11, textAlign: 'right', fontFeatureSettings: "'tnum' 1", color: f.c }}>{f.drift}</span>
            </div>
          ))}
          <p style={{ margin: '12px 0 0', fontSize: 11.5, lineHeight: 1.5, color: AMBER }}>Drift alert · device_type importance fell 40% over 30 days. Possible concept drift — schedule a retrain.</p>
        </Blueprint>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 22 }}>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 14 }}>Latency percentiles</span>
          {latency.map((l) => (
            <div key={l.k} style={{ display: 'grid', gridTemplateColumns: '38px 1fr 58px', alignItems: 'center', gap: 10, padding: '6px 0' }}>
              <span style={{ fontSize: 11.5, fontFamily: 'var(--font-heading)', letterSpacing: '.06em' }}>{l.k}</span>
              <span style={{ display: 'block', height: 12, background: 'color-mix(in srgb,var(--color-text) 8%,transparent)', position: 'relative' }}><span style={{ display: 'block', height: 12, width: l.w, background: l.c }} /><span style={{ position: 'absolute', top: -3, bottom: -3, left: l.budget, width: 1, background: RED }} /></span>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 15, textAlign: 'right', fontFeatureSettings: "'tnum' 1" }}>{l.v}</span>
            </div>
          ))}
          <p style={{ margin: '10px 0 0', fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>Red mark = 100 ms budget.</p>
        </Blueprint>
        <Blueprint style={{ padding: 0 }}>
          <span style={{ display: 'block', padding: '16px 18px 10px', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Model versions</span>
          <table className="table" style={{ fontSize: 12.5 }}>
            <thead><tr><th style={{ paddingLeft: 18 }}>Version</th><th>Deployed</th><th>F1</th><th style={{ paddingRight: 18 }}>State</th></tr></thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.n}>
                  <td style={{ paddingLeft: 18, fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11 }}>{v.n}</td>
                  <td style={{ color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{v.d}</td>
                  <td style={{ fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1" }}>{v.f1}</td>
                  <td style={{ paddingRight: 18 }}><span className="tag" style={{ background: v.tint, color: v.c, fontSize: 10 }}>{v.s}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Blueprint>
        <Blueprint style={{ padding: 18, display: 'flex', flexDirection: 'column' }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 12 }}>Feedback loop</span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {feedbackStats.map((f) => (
              <div key={f.k} style={{ padding: 10, border: '1px solid var(--color-divider)' }}>
                <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 22, fontFeatureSettings: "'tnum' 1", color: f.c }}>{f.v}</span>
                <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{f.k}</span>
              </div>
            ))}
          </div>
          <p style={{ margin: '14px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>1,412 labelled points since xgb_v4. Retrain triggers at 1,500 or on demand.</p>
          <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 'auto' }}>Retrain now</button>
        </Blueprint>
      </div>
    </div>
  );
}
