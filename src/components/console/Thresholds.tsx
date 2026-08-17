import { Blueprint } from '../ui/Blueprint';
import { GREEN, AMBER, RED } from '../../lib/mock';
import type { RiskPulse } from '../../state/useRiskPulse';

export function Thresholds({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 340px', gap: 22, alignItems: 'start' }}>
      <Blueprint style={{ padding: 0 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid var(--color-divider)', fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.09em', textTransform: 'uppercase' }}>
          <span style={{ flex: 1, minWidth: '16ch', padding: '11px 20px' }}>Risk appetite · decision bands</span>
          <span style={{ padding: '11px 20px', borderLeft: '1px solid var(--color-divider)', color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>Replay window 1,000 txn</span>
        </div>
        <div style={{ padding: '22px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 170 }}>
            {rp.hist.map((h, i) => <span key={i} style={{ flex: 1, height: h.h, background: h.c, opacity: 0.85 }} />)}
          </div>
          <div style={{ display: 'flex', height: 26, marginTop: 4, fontSize: 10.5, fontFamily: 'var(--font-heading)', letterSpacing: '.06em', textTransform: 'uppercase' }}>
            <span style={{ width: rp.bandApprove, background: `color-mix(in srgb,${GREEN} 22%,transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Approve</span>
            <span style={{ width: rp.bandStep, background: `color-mix(in srgb,${AMBER} 22%,transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Step-up</span>
            <span style={{ width: rp.bandBlock, background: `color-mix(in srgb,${RED} 22%,transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Block</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, marginTop: 5, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}><span>0.0</span><span>0.25</span><span>0.5</span><span>0.75</span><span>1.0</span></div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26, marginTop: 28 }}>
            <div>
              <span style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', fontSize: 12, marginBottom: 8 }}><span style={{ letterSpacing: '.08em', textTransform: 'uppercase' }}>Auto-approve below</span><span style={{ fontFamily: 'var(--font-heading)', fontSize: 22, fontFeatureSettings: "'tnum' 1", color: GREEN }}>{rp.apprLabel}</span></span>
              <input type="range" min="0.05" max="0.6" step="0.01" value={rp.appr} onChange={(e) => rp.setAppr(parseFloat(e.target.value))} style={{ width: '100%', accentColor: GREEN }} />
            </div>
            <div>
              <span style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', fontSize: 12, marginBottom: 8 }}><span style={{ letterSpacing: '.08em', textTransform: 'uppercase' }}>Block at or above</span><span style={{ fontFamily: 'var(--font-heading)', fontSize: 22, fontFeatureSettings: "'tnum' 1", color: RED }}>{rp.blkLabel}</span></span>
              <input type="range" min="0.4" max="0.95" step="0.01" value={rp.blk} onChange={(e) => rp.setBlk(parseFloat(e.target.value))} style={{ width: '100%', accentColor: RED }} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 24, paddingTop: 18, borderTop: '1px solid var(--color-divider)' }}>
            <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Presets</span>
            {rp.presets.map((p) => (
              <button key={p.t} type="button" className="btn btn-secondary" onClick={() => rp.setPreset(p.a, p.b)} style={{ fontSize: 12 }}>{p.t}</button>
            ))}
            <button type="button" className="btn btn-primary" style={{ marginLeft: 'auto' }}>Publish thresholds</button>
          </div>
        </div>
      </Blueprint>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 14 }}>Live replay · last week</span>
          <div style={{ position: 'relative', width: 150, height: 150, margin: '0 auto' }}>
            <svg viewBox="0 0 140 140" style={{ width: 150, height: 150, display: 'block' }}>
              {rp.donut.map((d, i) => <circle key={i} cx="70" cy="70" r="52" fill="none" stroke={d.c} strokeWidth="22" strokeDasharray={d.dash} strokeDashoffset={d.off} transform="rotate(-90 70 70)" />)}
            </svg>
            <span style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 26, lineHeight: 1, fontFeatureSettings: "'tnum' 1", whiteSpace: 'nowrap' }}>{rp.fprLabel}</span>
              <span style={{ fontSize: 10, opacity: 0.6 }}>est. FPR</span>
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 14 }}>
            {rp.previewRows.map((p) => (
              <span key={p.k} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}><span style={{ width: 10, height: 10, background: p.c }} />{p.k}<span style={{ marginLeft: 'auto', fontFamily: 'var(--font-heading)', fontSize: 16, fontFeatureSettings: "'tnum' 1" }}>{p.v}</span></span>
            ))}
          </div>
        </Blueprint>
        <Blueprint style={{ padding: 18 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Trade-off curve</span>
          <svg viewBox="0 0 260 130" style={{ width: '100%' }}>
            <path d={rp.rocPath} fill="none" stroke="var(--color-accent)" strokeWidth="1.8" />
            <line x1="10" y1="120" x2="250" y2="10" stroke="color-mix(in srgb, currentColor 18%, transparent)" strokeDasharray="3 3" />
            <circle cx={rp.rocX} cy={rp.rocY} r="5" fill={RED} />
          </svg>
          <p style={{ margin: '8px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>Moving the block threshold down catches {rp.catchDelta} more fraud and costs {rp.fprDelta} more false positives.</p>
        </Blueprint>
      </div>
    </div>
  );
}
