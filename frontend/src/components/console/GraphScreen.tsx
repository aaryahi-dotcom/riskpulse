import { useEffect, useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { exposed, nodeMetrics as mockNodeMetrics, RED } from '../../lib/mock';
import { getGraphNode, type GraphNodeDTO } from '../../lib/api';
import type { RiskPulse, GraphMode } from '../../state/useRiskPulse';

function toDisplayMetrics(m: GraphNodeDTO) {
  return [
    { k: 'PageRank', v: m.pagerank.toFixed(4), c: m.pagerank > 0.03 ? RED : 'inherit' },
    { k: 'Δ 24 h', v: (m.pagerank_delta_24h >= 0 ? '+' : '') + m.pagerank_delta_24h.toFixed(4), c: m.pagerank_delta_24h > 0 ? RED : 'inherit' },
    { k: 'Clustering', v: m.clustering_coefficient.toFixed(2), c: 'inherit' },
    { k: 'Δ clustering 7d', v: (m.clustering_delta_7d >= 0 ? '+' : '') + m.clustering_delta_7d.toFixed(2), c: 'inherit' },
    { k: 'Degree', v: String(m.degree), c: 'inherit' },
    { k: 'Δ degree 1h', v: (m.degree_delta_1h >= 0 ? '+' : '') + m.degree_delta_1h.toFixed(1), c: 'inherit' },
  ];
}

export function GraphScreen({ rp }: { rp: RiskPulse }) {
  const [query, setQuery] = useState('');
  const [node, setNode] = useState<GraphNodeDTO | null>(null);
  const [lookedUp, setLookedUp] = useState<string | null>(null);

  const lookup = (id: string) => {
    if (!id) return;
    getGraphNode(id).then((n) => { setNode(n); setLookedUp(id); }).catch(() => { setNode(null); setLookedUp(id); });
  };

  useEffect(() => { lookup(rp.sel.to); }, [rp.sel.to]);

  const displayMetrics = node?.present ? toDisplayMetrics(node) : mockNodeMetrics;
  const displayId = node?.present ? (lookedUp ?? rp.sel.to) : (lookedUp ?? 'x8k2m@ybl');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 300px', gap: 22, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        <Blueprint style={{ padding: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '11px 16px', borderBottom: '1px solid var(--color-divider)' }}>
            <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.1em', textTransform: 'uppercase' }}>Transaction network</span>
            <div className="seg">
              {rp.graphModes.map((g) => (
                <button key={g.key} type="button" onClick={() => rp.setGmode(g.key as GraphMode)} style={{ padding: '6px 13px', fontSize: 12, border: 0, borderLeft: '1px solid var(--color-divider)', background: g.bg, color: g.fg, cursor: 'pointer', whiteSpace: 'nowrap', fontFamily: 'var(--font-heading)', letterSpacing: '.06em', textTransform: 'uppercase' }}>{g.t}</button>
              ))}
            </div>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 14, fontSize: 11 }}>
              {rp.graphLegend.map((l) => (
                <span key={l.k} style={{ display: 'flex', alignItems: 'center', gap: 5 }}><span style={{ width: 9, height: 9, borderRadius: '50%', background: l.c }} />{l.k}</span>
              ))}
            </span>
          </div>
          <div style={{ position: 'relative' }}>
            <svg viewBox="0 0 760 420" style={{ width: '100%', display: 'block' }}>
              {rp.links.map((l, i) => <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke={l.c} strokeWidth={l.w} />)}
              {rp.nodes.map((n, i) => <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.f} stroke={n.c} strokeWidth="1.6" />)}
            </svg>
            {rp.nodeLabels.map((n) => (
              <span key={n.t} style={{ position: 'absolute', left: n.l, top: n.t2, transform: 'translate(-50%,-50%)', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 10, opacity: 0.7, whiteSpace: 'nowrap' }}>{n.t}</span>
            ))}
          </div>
          <p style={{ margin: 0, padding: '11px 16px', borderTop: '1px solid var(--color-divider)', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{rp.graphNote}</p>
        </Blueprint>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 22 }}>
          <Blueprint style={{ padding: 16 }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 12 }}>Contagion heatmap · exposure by hop × hour</span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(14,1fr)', gap: 2 }}>
              {rp.heat.map((c, i) => <span key={i} style={{ aspectRatio: '1', background: c.bg }} />)}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
              <span>low</span>
              <span style={{ flex: 1, height: 6, background: 'linear-gradient(90deg,color-mix(in srgb,var(--color-accent) 8%,transparent),#b0533f)' }} />
              <span>high</span>
            </div>
          </Blueprint>
          <Blueprint style={{ padding: 0 }}>
            <span style={{ display: 'block', padding: '14px 16px 10px', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Most exposed accounts</span>
            <table className="table" style={{ fontSize: 12.5 }}>
              <thead><tr><th style={{ paddingLeft: 16 }}>Account</th><th>Hops</th><th>Exposure</th><th style={{ paddingRight: 16 }}>Next txn</th></tr></thead>
              <tbody>
                {exposed.map((e) => (
                  <tr key={e.a}>
                    <td style={{ paddingLeft: 16, fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11 }}>{e.a}</td>
                    <td style={{ fontFeatureSettings: "'tnum' 1" }}>{e.h}</td>
                    <td><span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 52, height: 6, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 6, width: e.w, background: e.c }} /></span><span style={{ fontFeatureSettings: "'tnum' 1" }}>{e.v}</span></span></td>
                    <td style={{ paddingRight: 16, fontSize: 11, color: e.c }}>{e.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Blueprint>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        <Blueprint style={{ padding: 16 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Node inspector</span>
          <span style={{ display: 'block', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 13, margin: '8px 0 4px', color: RED }}>{displayId}</span>
          {node && !node.present && <span style={{ display: 'block', fontSize: 10.5, marginBottom: 8, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>not yet in the transaction graph — showing demo data</span>}
          <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
            <input className="input" placeholder="account / VPA" value={query} onChange={(e) => setQuery(e.target.value)} style={{ fontSize: 11.5, flex: 1 }} />
            <button type="button" className="btn btn-secondary" style={{ fontSize: 11.5, padding: '6px 10px' }} onClick={() => lookup(query)}>Look up</button>
          </div>
          {displayMetrics.map((m) => (
            <div key={m.k} style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '6px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 8%,transparent)', fontSize: 12 }}>
              <span style={{ color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{m.k}</span>
              <span style={{ flex: 1, borderBottom: '1px dotted color-mix(in srgb,var(--color-text) 25%,transparent)' }} />
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 15, fontFeatureSettings: "'tnum' 1", color: m.c }}>{m.v}</span>
            </div>
          ))}
          <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 14 }}>Open case →</button>
        </Blueprint>
        <Blueprint style={{ padding: 16 }}>
          <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 10 }}>Centrality drift · 7d</span>
          <svg viewBox="0 0 240 90" preserveAspectRatio="none" style={{ width: '100%', height: 90 }}>
            <path d={rp.prArea} fill={RED} opacity="0.14" />
            <path d={rp.prLine} fill="none" stroke={RED} strokeWidth="1.8" />
          </svg>
          <p style={{ margin: '8px 0 0', fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>PageRank 0.001 → 0.049 in 24 h. Sudden centrality on a 3-month dormant account — mule activation signature.</p>
        </Blueprint>
      </div>
    </div>
  );
}
