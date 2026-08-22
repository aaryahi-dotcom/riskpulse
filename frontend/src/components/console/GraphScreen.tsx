import { useEffect, useMemo, useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { ForceGraph } from './ForceGraph';
import { exposed, nodeMetrics as mockNodeMetrics, RED, AMBER } from '../../lib/mock';
import { getGraphNode, getSubgraph, getExposedAccounts, type GraphNodeDTO, type SubgraphDTO, type ExposedAccountDTO } from '../../lib/api';
import type { RiskPulse, GraphMode } from '../../state/useRiskPulse';

function toExposedRows(accounts: ExposedAccountDTO[]) {
  return accounts.slice(0, 6).map((a) => {
    const c = a.exposure_score >= 0.5 ? RED : a.exposure_score >= 0.3 ? AMBER : 'var(--color-accent)';
    const n = a.exposure_score >= 0.5 ? 'pre-flagged' : a.exposure_score >= 0.3 ? 'step-up' : 'monitor';
    return { a: a.user_id, h: a.approx_hop != null ? String(a.approx_hop) : '—', v: a.exposure_score.toFixed(2), w: Math.round(a.exposure_score * 100) + '%', c, n };
  });
}

// hop-1..4 exposure averages, live data blended into the same
// decay-shaped visual texture the mock used (no per-hour exposure
// telemetry is persisted, so the hour axis stays illustrative shading —
// only the per-hop row intensity is real).
function liveHeatCells(accounts: ExposedAccountDTO[]) {
  const byHop = new Map<number, number[]>();
  accounts.forEach((a) => {
    if (a.approx_hop == null) return;
    const arr = byHop.get(a.approx_hop) ?? [];
    arr.push(a.exposure_score);
    byHop.set(a.approx_hop, arr);
  });
  const avg = (hop: number) => {
    const arr = byHop.get(hop);
    return arr && arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : Math.max(0, 0.92 * Math.pow(0.52, hop));
  };
  const cells: { bg: string }[] = [];
  for (let r = 1; r <= 4; r++) {
    for (let h = 0; h < 14; h++) {
      const v = avg(r) * (0.35 + 0.65 * (h / 13)) * (r === 1 ? 1 : 0.9);
      cells.push({ bg: `color-mix(in srgb, ${RED} ${(v * 100).toFixed(0)}%, color-mix(in srgb, var(--color-accent) 8%, transparent))` });
    }
  }
  return cells;
}

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
  const [subgraph, setSubgraph] = useState<SubgraphDTO | null>(null);
  const [exposedAccounts, setExposedAccounts] = useState<ExposedAccountDTO[] | null>(null);
  const [replayHop, setReplayHop] = useState<number | null>(null);

  const lookup = (id: string) => {
    if (!id) return;
    getGraphNode(id).then((n) => { setNode(n); setLookedUp(id); }).catch(() => { setNode(null); setLookedUp(id); });
    getSubgraph(id, 2).then(setSubgraph).catch(() => setSubgraph(null));
  };

  useEffect(() => { lookup(rp.sel.to); }, [rp.sel.to]);
  useEffect(() => {
    getExposedAccounts(0.01, 50).then((r) => setExposedAccounts(r.accounts)).catch(() => setExposedAccounts(null));
  }, []);

  const displayMetrics = node?.present ? toDisplayMetrics(node) : mockNodeMetrics;
  const displayId = node?.present ? (lookedUp ?? rp.sel.to) : (lookedUp ?? 'x8k2m@ybl');
  const hasLiveExposure = !!exposedAccounts && exposedAccounts.length > 0;
  const displayExposed = hasLiveExposure ? toExposedRows(exposedAccounts!) : exposed;
  const displayHeat = hasLiveExposure ? liveHeatCells(exposedAccounts!) : rp.heat;
  const exposureById = useMemo(
    () => new Map((exposedAccounts ?? []).map((a) => [a.user_id, a.exposure_score])),
    [exposedAccounts],
  );

  // checklist 4.9: "watch fraud spread" — replays the real, already-computed
  // per-hop exposure outward from hop 1 to hop 4, on demand (there's no
  // persisted per-event timeline to animate against automatically on
  // confirm-fraud, so this is a manual replay of real hop data rather than
  // a live-triggered animation).
  const replaySpread = () => {
    [1, 2, 3, 4].forEach((h, i) => window.setTimeout(() => setReplayHop(h), i * 550));
    window.setTimeout(() => setReplayHop(null), 4 * 550 + 900);
  };

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
            {subgraph ? (
              <ForceGraph data={subgraph} width={760} height={420} selectedId={displayId} onSelect={lookup} mode={rp.gmode === 'contagion' ? 'contagion' : 'risk'} exposureById={exposureById} />
            ) : (
              <>
                <svg viewBox="0 0 760 420" style={{ width: '100%', display: 'block' }}>
                  {rp.links.map((l, i) => <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke={l.c} strokeWidth={l.w} />)}
                  {rp.nodes.map((n, i) => <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.f} stroke={n.c} strokeWidth="1.6" />)}
                </svg>
                {rp.nodeLabels.map((n) => (
                  <span key={n.t} style={{ position: 'absolute', left: n.l, top: n.t2, transform: 'translate(-50%,-50%)', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 10, opacity: 0.7, whiteSpace: 'nowrap' }}>{n.t}</span>
                ))}
              </>
            )}
          </div>
          <p style={{ margin: 0, padding: '11px 16px', borderTop: '1px solid var(--color-divider)', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>
            {subgraph
              ? `Live ego-network around ${displayId} · ${subgraph.nodes.length} nodes, ${subgraph.edges.length} edges · force-directed layout from /api/v1/graph/subgraph.${rp.gmode === 'contagion' ? ' Node color = live exposure_score.' : ' Dashed red ring = detected cycle; amber ring = high fan-in (possible mule).'}`
              : rp.graphNote}
          </p>
        </Blueprint>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 22 }}>
          <Blueprint style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <span style={{ fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Contagion heatmap · exposure by hop × hour{hasLiveExposure ? ' · live' : ''}</span>
              <button type="button" className="btn btn-ghost" style={{ marginLeft: 'auto', fontSize: 10.5, padding: '3px 8px' }} disabled={replayHop !== null} onClick={replaySpread}>
                {replayHop !== null ? `Spreading · hop ${replayHop}` : 'Watch fraud spread ▶'}
              </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(14,1fr)', gap: 2 }}>
              {displayHeat.map((c, i) => {
                const rowHop = Math.floor(i / 14) + 1;
                const reached = replayHop === null || rowHop <= replayHop;
                const isFront = replayHop !== null && rowHop === replayHop;
                return <span key={i} style={{ aspectRatio: '1', background: c.bg, opacity: reached ? 1 : 0.12, transition: 'opacity .3s', outline: isFront ? `1px solid ${RED}` : 'none' }} />;
              })}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
              <span>low</span>
              <span style={{ flex: 1, height: 6, background: 'linear-gradient(90deg,color-mix(in srgb,var(--color-accent) 8%,transparent),#b0533f)' }} />
              <span>high</span>
            </div>
            {hasLiveExposure && <p style={{ margin: '8px 0 0', fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>Row intensity from live exposure_score per hop · hourly shading is illustrative, no per-hour telemetry is persisted.</p>}
          </Blueprint>
          <Blueprint style={{ padding: 0 }}>
            <span style={{ display: 'block', padding: '14px 16px 10px', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>Most exposed accounts{hasLiveExposure ? ' · live' : ''}</span>
            <table className="table" style={{ fontSize: 12.5 }}>
              <thead><tr><th style={{ paddingLeft: 16 }}>Account</th><th>Hops</th><th>Exposure</th><th style={{ paddingRight: 16 }}>Next txn</th></tr></thead>
              <tbody>
                {displayExposed.map((e) => {
                  const hopNum = Number(e.h);
                  const reached = replayHop === null || !Number.isFinite(hopNum) || hopNum <= replayHop;
                  return (
                  <tr key={e.a} style={{ opacity: reached ? 1 : 0.2, transition: 'opacity .3s' }}>
                    <td style={{ paddingLeft: 16, fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11 }}>{e.a}</td>
                    <td style={{ fontFeatureSettings: "'tnum' 1" }}>{e.h}</td>
                    <td><span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 52, height: 6, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)' }}><span style={{ display: 'block', height: 6, width: e.w, background: e.c }} /></span><span style={{ fontFeatureSettings: "'tnum' 1" }}>{e.v}</span></span></td>
                    <td style={{ paddingRight: 16, fontSize: 11, color: e.c }}>{e.n}</td>
                  </tr>
                  );
                })}
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
