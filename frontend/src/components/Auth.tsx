import { Blueprint } from './ui/Blueprint';
import { authStats, services, VOL, line, area } from '../lib/mock';
import type { RiskPulse } from '../state/useRiskPulse';

const authSpark = line(VOL, 220, 56, 3);
const authSparkArea = area(VOL, 220, 56, 3);

export function Auth({ rp }: { rp: RiskPulse }) {
  const isSignup = rp.authMode === 'up';
  const authKicker = isSignup ? 'Request tenant access' : 'Operator sign-in';
  const authTitle = isSignup ? 'Open a sandbox tenant.' : 'Back to the console.';
  const authSub = isSignup
    ? 'Sandbox tenants get a seeded transaction graph, the scenario simulator and a scoring key valid for 30 days.'
    : 'Analyst, admin and operator roles see different consoles. Your session resumes where you left the queue.';
  const authCta = isSignup ? 'Create tenant →' : 'Sign in →';
  const authSwapText = isSignup ? 'Already provisioned?' : 'No tenant yet?';
  const authSwapCta = isSignup ? 'Sign in' : 'Request access';

  return (
    <div style={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)' }}>
      <div style={{ padding: '40px max(28px,4vw)', display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--color-divider)' }}>
        <span style={{ display: 'flex', alignItems: 'baseline', gap: 8, cursor: 'pointer' }} onClick={rp.goLanding}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 20, textTransform: 'uppercase', letterSpacing: '.02em' }}>RiskPulse</span>
          <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>← back</span>
        </span>
        <div style={{ margin: 'auto 0', maxWidth: 400, width: '100%' }}>
          <span style={{ display: 'block', fontSize: 11, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>{authKicker}</span>
          <hr style={{ height: 1, border: 0, background: 'var(--color-divider)', margin: '12px 0 22px' }} />
          <h1 style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 38, lineHeight: 1.06, textTransform: 'uppercase', margin: 0 }}>{authTitle}</h1>
          <p style={{ fontSize: 14, lineHeight: 1.55, margin: '12px 0 26px', color: 'color-mix(in srgb,var(--color-text) 72%,transparent)' }}>{authSub}</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {isSignup && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="field"><label>Full name</label><input className="input" defaultValue="Priya Nandan" /></div>
                <div className="field"><label>Institution</label><input className="input" defaultValue="Federal Bank — Risk Ops" /></div>
              </div>
            )}
            <div className="field"><label>Work email</label><input className="input" type="email" defaultValue="priya.n@bank.example" /></div>
            <div className="field"><label>Password</label><input className="input" type="password" defaultValue="············" /></div>
            {isSignup && (
              <div className="field">
                <label>Role</label>
                <div className="seg" style={{ width: '100%' }}>
                  <label className="seg-opt" style={{ flex: 1, justifyContent: 'center' }}><input type="radio" name="role" defaultChecked />Analyst</label>
                  <label className="seg-opt" style={{ flex: 1, justifyContent: 'center' }}><input type="radio" name="role" />Admin</label>
                  <label className="seg-opt" style={{ flex: 1, justifyContent: 'center' }}><input type="radio" name="role" />Operator</label>
                </div>
              </div>
            )}
            <button type="button" className="btn btn-primary btn-block" onClick={rp.goApp} style={{ padding: 12, fontSize: 15, marginTop: 6 }}>{authCta}</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>
              <span>{authSwapText}</span>
              <button type="button" className="btn btn-ghost" onClick={rp.swapAuth} style={{ fontSize: 13 }}>{authSwapCta}</button>
            </div>
          </div>
          <p style={{ fontSize: 11.5, lineHeight: 1.5, margin: '28px 0 0', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>Token-based (JWT) auth. Sandbox tenants get a seeded transaction graph and the scenario simulator enabled.</p>
        </div>
      </div>
      <div style={{ background: 'var(--color-surface)', padding: '40px max(28px,4vw)', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 26 }}>
        <span style={{ fontSize: 11, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>Tenant status board</span>
        <Blueprint style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 20 }}>
            <div>
              <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>Scored today</span>
              <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 44, lineHeight: 1, fontFeatureSettings: "'tnum' 1" }}>1,84,203</span>
            </div>
            <svg viewBox="0 0 220 56" preserveAspectRatio="none" style={{ flex: 1, height: 56 }}>
              <path d={authSparkArea} fill="var(--color-accent)" opacity="0.16" />
              <path d={authSpark} fill="none" stroke="var(--color-accent)" strokeWidth="1.5" />
            </svg>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', marginTop: 20, borderTop: '1px solid var(--color-divider)' }}>
            {authStats.map((s) => (
              <div key={s.k} style={{ padding: '14px 12px 0' }}>
                <span style={{ display: 'block', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 24, fontFeatureSettings: "'tnum' 1", color: s.c }}>{s.v}</span>
                <span style={{ display: 'block', fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{s.k}</span>
              </div>
            ))}
          </div>
        </Blueprint>
        <Blueprint style={{ padding: 20 }}>
          <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 60%,transparent)', marginBottom: 14 }}>Service health</span>
          {services.map((s) => (
            <div key={s.n} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', fontSize: 13 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.c }} />
              <span style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 12 }}>{s.n}</span>
              <span style={{ flex: 1, height: 1, background: 'var(--color-divider)' }} />
              <span style={{ fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1" }}>{s.v}</span>
            </div>
          ))}
        </Blueprint>
      </div>
    </div>
  );
}
