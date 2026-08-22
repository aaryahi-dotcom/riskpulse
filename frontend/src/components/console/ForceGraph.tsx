// checklist 4.5: a real force-directed layout (d3-force) over the live
// /api/v1/graph/subgraph/{user_id} data, replacing the fixed hand-placed
// SVG diagram. Physics runs once (synchronously, a fixed number of
// ticks) rather than animating every frame — this is a small
// ego-neighborhood, not a live simulation, so a static settled layout is
// enough and keeps rendering as cheap as the rest of the console's SVG.
import { useMemo } from 'react';
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type SimulationNodeDatum } from 'd3-force';
import { RED, AMBER } from '../../lib/mock';
import type { SubgraphDTO } from '../../lib/api';

interface LaidOutNode extends SimulationNodeDatum {
  id: string;
  suspicious: boolean;
  inCycle: boolean;
  fanIn: number;
}

interface LaidOutLink {
  x1: number; y1: number; x2: number; y2: number; w: number; inCycle: boolean;
}

// Tarjan's SCC over the real subgraph edges: any strongly-connected
// component with >1 node means a directed path leads back to itself —
// i.e. a real layering/round-tripping cycle in this account's actual
// transaction history, not a simulated one (that's graph_flags'
// CYCLE_DETECTED, computed only for a proposed not-yet-scored txn).
function findCycleNodes(nodeIds: string[], edges: { source: string; target: string }[]): Set<string> {
  const adj = new Map<string, string[]>();
  nodeIds.forEach((id) => adj.set(id, []));
  edges.forEach((e) => adj.get(e.source)?.push(e.target));

  let index = 0;
  const indices = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  const cycleNodes = new Set<string>();

  function strongconnect(v: string) {
    indices.set(v, index);
    lowlink.set(v, index);
    index++;
    stack.push(v);
    onStack.add(v);

    for (const w of adj.get(v) ?? []) {
      if (!indices.has(w)) {
        strongconnect(w);
        lowlink.set(v, Math.min(lowlink.get(v)!, lowlink.get(w)!));
      } else if (onStack.has(w)) {
        lowlink.set(v, Math.min(lowlink.get(v)!, indices.get(w)!));
      }
    }

    if (lowlink.get(v) === indices.get(v)) {
      const component: string[] = [];
      let w: string;
      do {
        w = stack.pop()!;
        onStack.delete(w);
        component.push(w);
      } while (w !== v);
      const selfLoop = component.length === 1 && (adj.get(v) ?? []).includes(v);
      if (component.length > 1 || selfLoop) component.forEach((n) => cycleNodes.add(n));
    }
  }

  nodeIds.forEach((id) => { if (!indices.has(id)) strongconnect(id); });
  return cycleNodes;
}

const MULE_FAN_IN_THRESHOLD = 3;

function layout(data: SubgraphDTO, width: number, height: number, ticks = 250) {
  const edges = data.edges.filter((e) => data.nodes.some((n) => n.id === e.source) && data.nodes.some((n) => n.id === e.target));
  const nodeIds = data.nodes.map((n) => n.id);
  const cycleNodes = findCycleNodes(nodeIds, edges);
  const fanIn = new Map<string, number>();
  edges.forEach((e) => fanIn.set(e.target, (fanIn.get(e.target) ?? 0) + 1));

  const nodes: LaidOutNode[] = data.nodes.map((n) => ({
    id: n.id, suspicious: n.suspicious, inCycle: cycleNodes.has(n.id), fanIn: fanIn.get(n.id) ?? 0,
  }));
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const sim = forceSimulation(nodes)
    .force('link', forceLink(edges as unknown as { source: string; target: string }[]).id((d) => (d as LaidOutNode).id).distance(72).strength(0.5))
    .force('charge', forceManyBody().strength(-150))
    .force('center', forceCenter(width / 2, height / 2))
    .force('collide', forceCollide().radius(16))
    .stop();
  for (let i = 0; i < ticks; i++) sim.tick();

  const clamp = (v: number | undefined, lo: number, hi: number) => Math.max(lo, Math.min(hi, v ?? (lo + hi) / 2));
  nodes.forEach((n) => {
    n.x = clamp(n.x, 24, width - 24);
    n.y = clamp(n.y, 24, height - 24);
  });

  const links: LaidOutLink[] = edges.map((e) => {
    const s = byId.get(e.source)!;
    const t = byId.get(e.target)!;
    return { x1: s.x!, y1: s.y!, x2: t.x!, y2: t.y!, w: Math.min(4, 1 + Math.log2(1 + e.count)), inCycle: s.inCycle && t.inCycle };
  });

  return { nodes, links };
}

export function ForceGraph({
  data, width, height, selectedId, onSelect, mode = 'risk', exposureById,
}: {
  data: SubgraphDTO;
  width: number;
  height: number;
  selectedId?: string;
  onSelect?: (id: string) => void;
  mode?: 'risk' | 'contagion';
  exposureById?: Map<string, number>;
}) {
  const { nodes, links } = useMemo(() => layout(data, width, height), [data, width, height]);

  if (!nodes.length) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height, fontSize: 12, textAlign: 'center', padding: '0 20px', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>
        No graph data yet for this node — score a few transactions in the console to build the network.
      </div>
    );
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', display: 'block' }}>
      {links.map((l, i) => (
        <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
          stroke={l.inCycle ? RED : 'color-mix(in srgb, currentColor 22%, transparent)'}
          strokeWidth={l.inCycle ? l.w + 1 : l.w}
          strokeDasharray={l.inCycle ? '4 2' : undefined} />
      ))}
      {nodes.map((n) => {
        const isSelected = n.id === selectedId;
        const exposure = exposureById?.get(n.id);
        const color = mode === 'contagion' && exposure != null
          ? `color-mix(in srgb, ${RED} ${Math.round(exposure * 100)}%, var(--color-accent))`
          : n.suspicious ? RED : isSelected ? AMBER : 'var(--color-accent)';
        const isMule = n.fanIn >= MULE_FAN_IN_THRESHOLD;
        return (
          <g key={n.id} transform={`translate(${n.x},${n.y})`} style={{ cursor: onSelect ? 'pointer' : 'default' }} onClick={() => onSelect?.(n.id)}>
            {(n.inCycle || isMule) && (
              <circle r={isSelected ? 16 : 13} fill="none" stroke={n.inCycle ? RED : AMBER} strokeWidth={1.4} strokeDasharray="2 2" opacity={0.8} />
            )}
            <circle r={isSelected ? 11 : 8} fill={`color-mix(in srgb, ${color} 24%, transparent)`} stroke={color} strokeWidth={isSelected ? 2.4 : 1.6} />
            <text y={-13} textAnchor="middle" style={{ fontSize: 8.5, fontFamily: 'ui-monospace,Menlo,monospace', fill: 'currentColor', opacity: 0.65 }}>
              {n.id.length > 14 ? n.id.slice(0, 13) + '…' : n.id}
            </text>
            {isMule && !n.inCycle && (
              <text y={22} textAnchor="middle" style={{ fontSize: 7.5, fontFamily: 'ui-monospace,Menlo,monospace', fill: AMBER, opacity: 0.85 }}>fan-in {n.fanIn}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
