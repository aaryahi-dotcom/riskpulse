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
}

interface LaidOutLink {
  x1: number; y1: number; x2: number; y2: number; w: number;
}

function layout(data: SubgraphDTO, width: number, height: number, ticks = 250) {
  const nodes: LaidOutNode[] = data.nodes.map((n) => ({ id: n.id, suspicious: n.suspicious }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges = data.edges.filter((e) => byId.has(e.source) && byId.has(e.target));

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
    return { x1: s.x!, y1: s.y!, x2: t.x!, y2: t.y!, w: Math.min(4, 1 + Math.log2(1 + e.count)) };
  });

  return { nodes, links };
}

export function ForceGraph({
  data, width, height, selectedId, onSelect,
}: {
  data: SubgraphDTO;
  width: number;
  height: number;
  selectedId?: string;
  onSelect?: (id: string) => void;
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
        <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="color-mix(in srgb, currentColor 22%, transparent)" strokeWidth={l.w} />
      ))}
      {nodes.map((n) => {
        const isSelected = n.id === selectedId;
        const color = n.suspicious ? RED : isSelected ? AMBER : 'var(--color-accent)';
        return (
          <g key={n.id} transform={`translate(${n.x},${n.y})`} style={{ cursor: onSelect ? 'pointer' : 'default' }} onClick={() => onSelect?.(n.id)}>
            <circle r={isSelected ? 11 : 8} fill={`color-mix(in srgb, ${color} 24%, transparent)`} stroke={color} strokeWidth={isSelected ? 2.4 : 1.6} />
            <text y={-13} textAnchor="middle" style={{ fontSize: 8.5, fontFamily: 'ui-monospace,Menlo,monospace', fill: 'currentColor', opacity: 0.65 }}>
              {n.id.length > 14 ? n.id.slice(0, 13) + '…' : n.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
