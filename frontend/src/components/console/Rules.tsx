import { useEffect, useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { rules as mockRules, builderRows, RED, AMBER, GREEN, tint } from '../../lib/mock';
import { listRules, getRuleStats, createRule, previewRule, type RuleDTO, type RulePreviewDTO } from '../../lib/api';

type DisplayRule = typeof mockRules[number];

const actionColor = (r: RuleDTO) => (r.action === 'override' ? RED : r.forced_tier === 'block' ? RED : AMBER);
const actionLabel = (r: RuleDTO) =>
  r.action === 'override' ? `Force ${r.forced_tier ?? 'review'}` : `${r.score_delta && r.score_delta >= 0 ? '+' : ''}${(r.score_delta ?? 0).toFixed(2)} score`;
const conditionText = (c: Record<string, unknown>): string => {
  if ('all' in c || 'any' in c) {
    const key = 'all' in c ? 'all' : 'any';
    const joiner = key === 'all' ? ' AND ' : ' OR ';
    return (c[key] as Record<string, unknown>[]).map(conditionText).join(joiner);
  }
  return `${c.field} ${c.op} ${c.value}`;
};

async function loadLiveRules(): Promise<DisplayRule[]> {
  const live = await listRules();
  const withStats = await Promise.all(
    live.map(async (r) => {
      const stats = await getRuleStats(r.id).catch(() => null);
      const fireRate = stats ? Math.round(stats.fire_rate * 100) + '%' : '—';
      const precision = stats?.precision_estimate != null ? stats.precision_estimate.toFixed(2) : '—';
      const c = actionColor(r);
      return {
        name: r.name, action: actionLabel(r), c, tint: tint(c), pr: r.priority,
        cond: `IF ${conditionText(r.condition_json)} THEN ${actionLabel(r)}`,
        stats: [
          { k: 'Fired (sampled)', v: String(stats?.fired_count ?? 0), w: fireRate, c: stats && stats.fire_rate > 0.5 ? RED : AMBER },
          { k: 'Precision', v: precision, w: Math.round((stats?.precision_estimate ?? 0) * 100) + '%', c: (stats?.precision_estimate ?? 0) > 0.7 ? GREEN : AMBER },
          { k: 'Feedback coverage', v: String(stats?.feedback_coverage ?? 0), w: '100%', c: 'var(--color-accent)' },
        ],
      };
    }),
  );
  return withStats;
}

const OPS = ['==', '!=', '>', '>=', '<', '<=', 'in', 'not in'];

type BuilderRow = { field: string; op: string; value: string };
type ThenAction = 'augment' | 'review' | 'block';

function parseValue(raw: string): string | number {
  const n = Number(raw);
  return raw.trim() !== '' && !Number.isNaN(n) ? n : raw;
}

function buildConditionJson(rows: BuilderRow[]): Record<string, unknown> {
  const leaves = rows.map((r) => ({ field: r.field, op: r.op, value: parseValue(r.value) }));
  return leaves.length === 1 ? leaves[0] : { all: leaves };
}

export function Rules() {
  const [liveRules, setLiveRules] = useState<DisplayRule[] | null>(null);
  const [deploying, setDeploying] = useState(false);
  const [deployMsg, setDeployMsg] = useState<string | null>(null);

  const [ruleName, setRuleName] = useState('Night-time large transfer to new VPA');
  const [rows, setRows] = useState<BuilderRow[]>(
    builderRows.map((b) => ({ field: b.fields[0], op: b.op, value: b.val })),
  );
  const [thenAction, setThenAction] = useState<ThenAction>('review');
  const [scoreAdj, setScoreAdj] = useState('0.30');
  const [preview, setPreview] = useState<RulePreviewDTO | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewMsg, setPreviewMsg] = useState<string | null>(null);

  const refresh = () => {
    loadLiveRules().then(setLiveRules).catch(() => setLiveRules(null));
  };
  useEffect(refresh, []);

  const displayRules = liveRules ?? mockRules;

  const setRow = (i: number, patch: Partial<BuilderRow>) => {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
    setPreview(null);
  };
  const addRow = () => { setRows((prev) => [...prev, { field: 'amount', op: '>', value: '0' }]); setPreview(null); };

  const runPreview = async () => {
    setPreviewing(true);
    setPreviewMsg(null);
    try {
      const result = await previewRule(buildConditionJson(rows));
      setPreview(result);
    } catch {
      setPreview(null);
      setPreviewMsg('Backend unreachable — preview unavailable.');
    } finally {
      setPreviewing(false);
    }
  };

  const deployRule = async () => {
    setDeploying(true);
    setDeployMsg(null);
    try {
      const delta = parseFloat(scoreAdj) || 0;
      await createRule({
        name: ruleName,
        condition_json: buildConditionJson(rows),
        action: thenAction === 'augment' ? 'augment' : 'override',
        score_delta: thenAction === 'augment' ? delta : null,
        forced_tier: thenAction === 'block' ? 'block' : thenAction === 'review' ? 'step_up' : null,
        priority: 50,
      });
      setDeployMsg('Rule deployed — live immediately.');
      setPreview(null);
      refresh();
    } catch {
      setDeployMsg('Backend unreachable — rule not deployed.');
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 360px', gap: 22, alignItems: 'start' }}>
      <Blueprint style={{ padding: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '11px 18px', borderBottom: '1px solid var(--color-divider)' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 12.5, letterSpacing: '.1em', textTransform: 'uppercase' }}>Active rules</span>
          <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{liveRules ? 'Live from /api/v1/rules' : 'Evaluated alongside the model · no retraining'}</span>
        </div>
        {displayRules.map((r) => (
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
          <div className="field"><label>Rule name</label><input className="input" value={ruleName} onChange={(e) => setRuleName(e.target.value)} /></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>IF</span>
            {rows.map((r, i) => {
              const fields = builderRows[i % builderRows.length].fields;
              const fieldOptions = fields.includes(r.field) ? fields : [r.field, ...fields];
              return (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 62px 84px', gap: 8 }}>
                  <select className="input" style={{ fontSize: 12.5 }} value={r.field} onChange={(e) => setRow(i, { field: e.target.value })}>
                    {fieldOptions.map((f) => <option key={f}>{f}</option>)}
                  </select>
                  <select className="input" style={{ fontSize: 12.5 }} value={r.op} onChange={(e) => setRow(i, { op: e.target.value })}>
                    {OPS.map((op) => <option key={op}>{op}</option>)}
                  </select>
                  <input className="input" style={{ fontSize: 12.5 }} value={r.value} onChange={(e) => setRow(i, { value: e.target.value })} />
                </div>
              );
            })}
            <button type="button" className="btn btn-ghost" style={{ alignSelf: 'flex-start', fontSize: 12.5 }} onClick={addRow}>+ Add condition</button>
          </div>
          <div>
            <span style={{ display: 'block', fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)', marginBottom: 8 }}>THEN</span>
            <div className="seg" style={{ width: '100%' }}>
              <label className="seg-opt" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }}><input type="radio" name="act" checked={thenAction === 'augment'} onChange={() => setThenAction('augment')} />Add to score</label>
              <label className="seg-opt" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }}><input type="radio" name="act" checked={thenAction === 'review'} onChange={() => setThenAction('review')} />Force review</label>
              <label className="seg-opt" style={{ flex: 1, justifyContent: 'center', fontSize: 12 }}><input type="radio" name="act" checked={thenAction === 'block'} onChange={() => setThenAction('block')} />Block</label>
            </div>
          </div>
          {thenAction === 'augment' && (
            <div className="field"><label>Score adjustment</label><input className="input" value={scoreAdj} onChange={(e) => setScoreAdj(e.target.value)} /></div>
          )}
          <div style={{ padding: 12, border: '1px solid var(--color-divider)', background: 'var(--color-surface)' }}>
            <span style={{ display: 'block', fontSize: 10.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginBottom: 6 }}>Condition preview</span>
            <code style={{ display: 'block', fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 80%,transparent)' }}>
              IF {rows.map((r) => `${r.field} ${r.op} ${r.value}`).join(' AND ')} THEN {thenAction === 'augment' ? `score += ${scoreAdj}` : thenAction === 'block' ? 'block' : 'force review'}
            </code>
          </div>
          <button type="button" className="btn btn-secondary btn-block" style={{ padding: 10 }} disabled={previewing} onClick={runPreview}>
            {previewing ? 'Testing against history…' : 'Preview — how many past txns would this catch?'}
          </button>
          {preview && (
            <div style={{ padding: 10, border: '1px solid var(--color-divider)', background: 'var(--color-surface)', fontSize: 12 }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 16 }}>{preview.matched}</span> of {preview.sampled} sampled transactions match ({Math.round(preview.match_rate * 100)}%).
              {!preview.sampled && <span style={{ display: 'block', marginTop: 4, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>No scored history yet — score a few transactions first.</span>}
            </div>
          )}
          {previewMsg && <span style={{ fontSize: 11.5, color: RED }}>{previewMsg}</span>}
          <button type="button" className="btn btn-primary btn-block" style={{ padding: 11 }} disabled={deploying} onClick={deployRule}>
            {deploying ? 'Deploying…' : 'Deploy rule — takes effect immediately'}
          </button>
          {deployMsg && <span style={{ fontSize: 11.5, color: deployMsg.startsWith('Rule') ? GREEN : RED }}>{deployMsg}</span>}
        </div>
      </Blueprint>
    </div>
  );
}
