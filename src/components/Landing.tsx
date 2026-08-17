import { Blueprint } from './ui/Blueprint';
import { specRows, stages, capabilities, plugSteps, endpoints } from '../lib/mock';
import type { RiskPulse } from '../state/useRiskPulse';

export function Landing({ rp }: { rp: RiskPulse }) {
  return (
    <div>
      <nav style={{ position: 'sticky', top: 0, zIndex: 30, display: 'flex', alignItems: 'center', gap: 28, padding: '14px max(24px,calc((100% - 1240px)/2))', background: 'var(--color-bg)', borderBottom: '1px solid var(--color-divider)' }}>
        <span style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginRight: 'auto' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 21, letterSpacing: '.02em', textTransform: 'uppercase' }}>RiskPulse</span>
          <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>S21 · Team Hyphen</span>
        </span>
        <a href="#capability" style={{ fontSize: 13, letterSpacing: '.06em', textTransform: 'uppercase', textDecoration: 'none', color: 'inherit', fontFamily: 'var(--font-heading)' }}>Capabilities</a>
        <a href="#pipeline" style={{ fontSize: 13, letterSpacing: '.06em', textTransform: 'uppercase', textDecoration: 'none', color: 'inherit', fontFamily: 'var(--font-heading)' }}>Pipeline</a>
        <a href="#api" style={{ fontSize: 13, letterSpacing: '.06em', textTransform: 'uppercase', textDecoration: 'none', color: 'inherit', fontFamily: 'var(--font-heading)' }}>API</a>
        <button type="button" className="btn btn-secondary" onClick={rp.toggleTheme} style={{ width: 34, height: 34, padding: 0 }}>{rp.themeGlyph}</button>
        <button type="button" className="btn btn-secondary" onClick={rp.goAuthIn}>Sign in</button>
        <button type="button" className="btn btn-primary" onClick={rp.goAuthUp}>Request access</button>
      </nav>

      <div style={{ padding: '0 max(24px,calc((100% - 1240px)/2))' }}>
        <section style={{ display: 'grid', gridTemplateColumns: 'minmax(0,7fr) minmax(0,5fr)', gap: 56, alignItems: 'center', padding: '76px 0 64px' }}>
          <div>
            <span style={{ display: 'block', fontSize: 12, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--color-accent-700)', marginBottom: 12 }}>Real-time transaction risk scoring engine</span>
            <hr style={{ height: 1, border: 0, background: 'var(--color-divider)', margin: '0 0 24px' }} />
            <h1 style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 'clamp(44px,5.4vw,80px)', lineHeight: 1.04, letterSpacing: '.01em', textTransform: 'uppercase', margin: 0 }}>
              <span style={{ display: 'block' }}>Score the fraud</span>
              <span style={{ display: 'block' }}>before the money</span>
              <span style={{ display: 'block', color: 'var(--color-accent-700)' }}>leaves the rail.</span>
            </h1>
            <p style={{ fontSize: 17, lineHeight: 1.6, maxWidth: '56ch', margin: '26px 0 0', color: 'color-mix(in srgb,var(--color-text) 80%,transparent)' }}>
              A bank POSTs a transaction. RiskPulse returns a risk score, a three-tier decision and a full SHAP explanation — under 100&nbsp;ms. Not a simulator: a deployable microservice with a trained model, an analyst workbench and Docker Compose deployment.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 30 }}>
              <button type="button" className="btn btn-primary" onClick={rp.goAuthUp} style={{ padding: '11px 22px', fontSize: 15 }}>Open the console</button>
              <button type="button" className="btn btn-secondary" onClick={rp.goApp} style={{ padding: '11px 22px', fontSize: 15 }}>View live demo →</button>
            </div>
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 26 }}>
              <span className="tag tag-accent">IEEE-CIS · 590K labelled</span>
              <span className="tag tag-neutral">XGBoost + Isolation Forest</span>
              <span className="tag tag-neutral">SHAP explainable</span>
              <span className="tag tag-neutral">docker-compose up</span>
            </div>
          </div>
          <Blueprint style={{ padding: 0, background: 'var(--color-surface)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: '1px solid var(--color-divider)', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', fontFamily: 'var(--font-heading)' }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#c2604c', animation: 'rp-pulse 1.6s infinite' }} />
              POST /api/v1/score
              <span style={{ marginLeft: 'auto', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>78 ms</span>
            </div>
            <pre style={{ margin: 0, padding: '16px 14px', font: '12px/1.75 ui-monospace,Menlo,monospace', overflow: 'auto', color: 'color-mix(in srgb,var(--color-text) 85%,transparent)' }}>{`{
  "transaction_id": "TXN-88412",
  "amount": 248000,
  "sender_id": "arya@okhdfc",
  "receiver_id": "x8k2m@ybl",
  "channel": "UPI"
}
`}<span style={{ color: 'var(--color-accent-700)' }}>→ 200 OK</span>{`
{
  "risk_score": `}<span style={{ color: '#c2604c' }}>0.91</span>{`,
  "decision": `}<span style={{ color: '#c2604c' }}>"block"</span>{`,
  "puppet_score": 0.83,
  "graph_flags": ["cycle_2hop", "mule_cluster"],
  "shap": { "new_beneficiary_burst": +0.22,
            "amount_regularity": +0.19,
            "vpa_entropy": +0.11,
            "beneficiary_age": -0.04 }
}`}</pre>
          </Blueprint>
        </section>

        <section style={{ padding: '12px 0 64px' }}>
          <Blueprint style={{ padding: 0 }}>
            <header style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid var(--color-divider)', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 13, letterSpacing: '.08em', textTransform: 'uppercase' }}>
              <span style={{ flex: 1, minWidth: '16ch', padding: '12px 24px' }}>RiskPulse — engine performance data</span>
              <span style={{ padding: '12px 24px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>RP-100</span>
              <span style={{ padding: '12px 24px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Rev C</span>
              <span style={{ padding: '12px 24px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Sheet 01 of 04</span>
            </header>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)' }}>
              {specRows.map((r) => (
                <div key={r.n} style={{ padding: '22px 24px', borderLeft: '1px solid var(--color-divider)' }}>
                  <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', color: 'var(--color-accent-700)', fontWeight: 600 }}>{r.n}</span>
                  <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 40, lineHeight: 1.05, letterSpacing: '.01em', fontFeatureSettings: "'tnum' 1", marginTop: 8 }}>{r.v}</span>
                  <span style={{ display: 'block', fontSize: 13, lineHeight: 1.5, marginTop: 6, color: 'color-mix(in srgb,var(--color-text) 72%,transparent)' }}>{r.k}</span>
                </div>
              ))}
            </div>
            <p style={{ margin: 0, padding: '12px 24px', borderTop: '1px solid var(--color-divider)', fontSize: 13, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>p95 measured end-to-end on a laptop Docker Compose stack. Model metrics from a stratified hold-out of IEEE-CIS.</p>
          </Blueprint>
        </section>

        <section id="pipeline" style={{ padding: '0 0 68px' }}>
          <span style={{ display: 'block', fontSize: 12, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--color-accent-700)', marginBottom: 12 }}>02 · The pipeline</span>
          <hr style={{ height: 1, border: 0, background: 'var(--color-divider)', margin: '0 0 30px' }} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 26 }}>
            {stages.map((s) => (
              <Blueprint key={s.n} style={{ padding: '16px 14px 14px', display: 'flex', flexDirection: 'column', gap: 8, minHeight: 150 }}>
                <span style={{ fontSize: 11, letterSpacing: '.1em', color: 'var(--color-accent-700)', fontWeight: 600 }}>{s.n}</span>
                <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 18, lineHeight: 1.1, textTransform: 'uppercase' }}>{s.t}</span>
                <span style={{ fontSize: 12, lineHeight: 1.45, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>{s.d}</span>
                <span style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ height: 3, flex: 1, background: 'var(--color-accent)', opacity: s.o }} />
                  <span style={{ fontFamily: 'var(--font-heading)', fontSize: 15, fontFeatureSettings: "'tnum' 1" }}>{s.ms}</span>
                </span>
              </Blueprint>
            ))}
          </div>
        </section>

        <section id="capability" style={{ padding: '0 0 68px' }}>
          <span style={{ display: 'block', fontSize: 12, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--color-accent-700)', marginBottom: 12 }}>03 · What no other team builds</span>
          <hr style={{ height: 1, border: 0, background: 'var(--color-divider)', margin: '0 0 34px' }} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 34 }}>
            {capabilities.map((c) => (
              <Blueprint key={c.n} style={{ padding: 24 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 13, letterSpacing: '.1em', color: 'var(--color-accent-700)' }}>{c.n}</span>
                  <h2 style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 24, lineHeight: 1.1, textTransform: 'uppercase', margin: 0 }}>{c.t}</h2>
                </div>
                <p style={{ fontSize: 14, lineHeight: 1.6, margin: '14px 0 0', color: 'color-mix(in srgb,var(--color-text) 78%,transparent)' }}>{c.d}</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
                  {c.tags.map((t) => <span key={t} className="tag tag-neutral">{t}</span>)}
                </div>
              </Blueprint>
            ))}
          </div>
        </section>

        <section id="api" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,5fr) minmax(0,7fr)', gap: 48, alignItems: 'start', padding: '0 0 72px' }}>
          <div>
            <span style={{ display: 'block', fontSize: 12, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--color-accent-700)', marginBottom: 12 }}>04 · How a bank plugs in</span>
            <hr style={{ height: 1, border: 0, background: 'var(--color-divider)', margin: '0 0 26px' }} />
            {plugSteps.map((p) => (
              <div key={p.n} style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 14, padding: '16px 0', borderBottom: '1px solid var(--color-divider)' }}>
                <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 26, lineHeight: 1, color: 'var(--color-accent-700)', fontFeatureSettings: "'tnum' 1" }}>{p.n}</span>
                <span>
                  <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 18, textTransform: 'uppercase', lineHeight: 1.15 }}>{p.t}</span>
                  <span style={{ display: 'block', fontSize: 13.5, lineHeight: 1.55, marginTop: 4, color: 'color-mix(in srgb,var(--color-text) 74%,transparent)' }}>{p.d}</span>
                </span>
              </div>
            ))}
          </div>
          <Blueprint style={{ padding: 0, background: 'var(--color-surface)' }}>
            <div style={{ padding: '11px 16px', borderBottom: '1px solid var(--color-divider)', fontFamily: 'var(--font-heading)', fontSize: 12, letterSpacing: '.1em', textTransform: 'uppercase' }}>Endpoint register</div>
            <table className="table" style={{ fontSize: 13 }}>
              <tbody>
                {endpoints.map((e) => (
                  <tr key={e.p}>
                    <td style={{ width: 64 }}><span className="tag tag-outline" style={{ fontSize: 10 }}>{e.m}</span></td>
                    <td style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 12 }}>{e.p}</td>
                    <td style={{ color: 'color-mix(in srgb,var(--color-text) 68%,transparent)' }}>{e.d}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Blueprint>
        </section>

        <section style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 32, flexWrap: 'wrap', padding: '44px 0 40px', borderTop: '1px solid var(--color-divider)' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 34, textTransform: 'uppercase', margin: 0, lineHeight: 1.08 }}>Point your stream at it.</h3>
            <p style={{ fontSize: 15, margin: '10px 0 0', maxWidth: '52ch', color: 'color-mix(in srgb,var(--color-text) 76%,transparent)' }}>Standard REST, JWT auth, Swagger at /docs. The pipeline is ready — it is waiting for the data.</p>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button type="button" className="btn btn-secondary" onClick={rp.goAuthIn} style={{ padding: '11px 20px' }}>Sign in</button>
            <button type="button" className="btn btn-primary" onClick={rp.goAuthUp} style={{ padding: '11px 20px' }}>Request access</button>
          </div>
        </section>
        <footer style={{ padding: '20px 0 40px', borderTop: '1px solid var(--color-divider)', fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>RiskPulse · Team Hyphen · Smart India Hackathon 2026 · Problem Statement S21 — mockup, not production copy.</footer>
      </div>
    </div>
  );
}
