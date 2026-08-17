import { Blueprint } from '../ui/Blueprint';
import { rules, builderRows } from '../../lib/mock';

export function Rules() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 360px', gap: 22, alignItems: 'start' }}>
      <Blueprint style={{ padding: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '11px 18px', borderBottom: '1px solid var(--color-divider)' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.1em', textTransform: 'uppercase' }}>Active rules</span>
          <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>Evaluated alongside the model · no retraining</span>
        </div>
        {rules.map((r) => (
          <div key={r.name} style={{ padding: '16px 18px', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 8%,transparent)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 16, textTransform: 'uppercase' }}>{r.name}</span>
              <span className="tag" style={{ background: r.tint, color: r.c, fontSize: 10 }}>{r.action}</span>
              <span style={{ marginLeft: 'auto', fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>Priority {r.pr}</span>
            </div>
            <code style={{ display: 'block', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, lineHeight: 1.6, marginTop: 8, padding: '9px 12px', background: 'var(--color-surface)', color: 'color-mix(in srgb,var(--color-text) 82%,transparent)' }}>{r.cond}</code>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18, marginTop: 12 }}>
              {r.stats.map((s) => (
                <div key={s.k}>
                  <span style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}><span>{s.k}</span><span style={{ fontFamily: 'var(--font-heading)', fontSize: 13, color: 'var(--color-text)', fontFeatureSettings: "'tnum' 1" }}>{s.v}</span></span>
                  <span style={{ display: 'block', height: 5, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 5, width: s.w, background: s.c }} /></span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Blueprint>
      <Blueprint style={{ padding: 18 }}>
        <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>New rule</span>
        <hr style={{ height: 1, border: 0, background: 'var(--color-divider)', margin: '12px 0 16px' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="field"><label>Rule name</label><input className="input" defaultValue="Night-time large transfer to new VPA" /></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>IF</span>
            {builderRows.map((b, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 62px 84px', gap: 8 }}>
                <select className="input" style={{ fontSize: 12.5 }}>
                  {b.fields.map((f) => <option key={f}>{f}</option>)}
                </select>
                <select className="input" style={{ fontSize: 12.5 }}><option>{b.op}</option></select>
                <input className="input" style={{ fontSize: 12.5 }} defaultValue={b.val} />
              </div>
            ))}
            <button type="button" className="btn btn-ghost" style={{ alignSelf: 'flex-start', fontSize: 12.5 }}>+ Add condition</button>
          </div>
          <div>
            <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)', marginBottom: 8 }}>THEN</span>
            <div className="seg" style={{ width: '100%' }}>
              <label className="seg-opt" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }}><input type="radio" name="act" />Add to score</label>
              <label className="seg-opt" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }}><input type="radio" name="act" defaultChecked />Force review</label>
              <label className="seg-opt" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }}><input type="radio" name="act" />Block</label>
            </div>
          </div>
          <div className="field"><label>Score adjustment</label><input className="input" defaultValue="+0.30" /></div>
          <div style={{ padding: 12, border: '1px solid var(--color-divider)', background: 'var(--color-surface)' }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 6 }}>Backtest · last 7 days</span>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}><span style={{ fontFamily: 'var(--font-heading)', fontSize: 24, fontFeatureSettings: "'tnum' 1" }}>64</span><span style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>transactions would match · 9 known fraud · est. FPR 2.1%</span></span>
          </div>
          <button type="button" className="btn btn-primary btn-block" style={{ padding: 11 }}>Deploy rule — takes effect immediately</button>
        </div>
      </Blueprint>
    </div>
  );
}
