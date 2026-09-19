import { Blueprint } from '../ui/Blueprint';

type AgentTraceEntry = {
  agent: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  reasoning: string;
};

type AgentDecision = {
  verdict: 'ALLOW' | 'COOL_OFF' | 'ALERT_TRUSTED_CONTACT' | 'BLOCK';
  explanation_en: string;
  explanation_hi: string;
  factors: Array<{
    name: string;
    weight: number;
    direction: 'positive' | 'negative';
  }>;
  confidence: number;
  reasoning: string;
};

type AgentTrace = {
  base_score: number;
  grey_zone_active: boolean;
  agents_run: AgentTraceEntry[];
  final_verdict: AgentDecision | null;
};

const statusColor = (status: string): string => {
  if (status === 'success') return 'color-mix(in srgb, #4ade80 100%, transparent)';
  if (status === 'failed') return 'color-mix(in srgb, #ef4444 100%, transparent)';
  if (status === 'running') return 'color-mix(in srgb, #f59e0b 100%, transparent)';
  return 'color-mix(in srgb, var(--color-text) 35%, transparent)';
};

const verdictColor = (verdict: string): { bg: string; fg: string } => {
  if (verdict === 'ALLOW') return { bg: 'color-mix(in srgb, #4ade80 12%, transparent)', fg: '#22c55e' };
  if (verdict === 'COOL_OFF') return { bg: 'color-mix(in srgb, #f59e0b 12%, transparent)', fg: '#f59e0b' };
  if (verdict === 'ALERT_TRUSTED_CONTACT') return { bg: 'color-mix(in srgb, #f59e0b 12%, transparent)', fg: '#f59e0b' };
  return { bg: 'color-mix(in srgb, #ef4444 12%, transparent)', fg: '#ef4444' };
};

export function BrainPanel({
  trace,
  language = 'en',
}: {
  trace: AgentTrace | null;
  language?: 'en' | 'hi';
}) {
  if (!trace) {
    return (
      <Blueprint style={{ padding: 18, textAlign: 'center', color: 'color-mix(in srgb,var(--color-text) 45%,transparent)' }}>
        <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', display: 'block', marginBottom: 12 }}>
          RiskPulse Brain
        </span>
        <span style={{ fontSize: 12 }}>Score outside grey zone — fast path, no agents.</span>
      </Blueprint>
    );
  }

  const verdict = trace.final_verdict;
  const verdictStyle = verdict ? verdictColor(verdict.verdict) : null;

  return (
    <Blueprint style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div>
        <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', display: 'block', marginBottom: 8 }}>
          RiskPulse Brain
        </span>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 28, fontFeatureSettings: "'tnum' 1" }}>
            {(trace.base_score * 100).toFixed(0)}
          </span>
          <span style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>
            grey zone: {trace.grey_zone_active ? 'yes' : 'no'}
          </span>
        </div>
      </div>

      {/* Agent Trace */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {trace.agents_run.map((agent, i) => (
          <div
            key={`${agent.agent}-${i}`}
            style={{
              padding: '10px 12px',
              background: 'color-mix(in srgb, var(--color-text) 3%, transparent)',
              border: `1px solid ${statusColor(agent.status)}`,
              borderRadius: 4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span
                style={{
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 500,
                  fontSize: 11,
                  color: statusColor(agent.status),
                  textTransform: 'uppercase',
                  letterSpacing: '.05em',
                  flex: 1,
                }}
              >
                {agent.agent.replace('_', ' ')}
              </span>
              <span
                style={{
                  fontSize: 9,
                  color: statusColor(agent.status),
                  textTransform: 'uppercase',
                  letterSpacing: '.05em',
                }}
              >
                {agent.status}
              </span>
            </div>
            {agent.reasoning && (
              <span style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 68%,transparent)', lineHeight: 1.4 }}>
                {agent.reasoning}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Verdict Card */}
      {verdict && verdictStyle && (
        <div style={{ background: verdictStyle.bg, border: `1px solid ${verdictStyle.fg}`, borderRadius: 6, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span
              style={{
                fontFamily: 'var(--font-heading)',
                fontWeight: 600,
                fontSize: 14,
                color: verdictStyle.fg,
                textTransform: 'uppercase',
                letterSpacing: '.05em',
              }}
            >
              {verdict.verdict}
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 10, color: 'color-mix(in srgb,var(--color-text) 50%,transparent)' }}>
              Confidence: {(verdict.confidence * 100).toFixed(0)}%
            </span>
          </div>

          <p
            style={{
              fontSize: 11,
              lineHeight: 1.5,
              margin: '0 0 10px 0',
              color: 'color-mix(in srgb,var(--color-text) 75%,transparent)',
            }}
          >
            {language === 'hi' ? verdict.explanation_hi : verdict.explanation_en}
          </p>

          {/* Factor Bars */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {verdict.factors.slice(0, 4).map((factor, i) => (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5, marginBottom: 2 }}>
                  <span style={{ color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{factor.name}</span>
                  <span style={{ fontFamily: 'var(--font-heading)', fontFeatureSettings: "'tnum' 1", fontWeight: 500 }}>
                    {(factor.weight * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ height: 4, background: 'color-mix(in srgb,var(--color-text) 8%,transparent)', borderRadius: 1 }}>
                  <div
                    style={{
                      height: 4,
                      width: `${factor.weight * 100}%`,
                      background:
                        factor.direction === 'positive' ? 'color-mix(in srgb, #4ade80 100%, transparent)' : 'color-mix(in srgb, #ef4444 100%, transparent)',
                      borderRadius: 1,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          {verdict.reasoning && (
            <div style={{ marginTop: 10, fontSize: 9.5, color: 'color-mix(in srgb,var(--color-text) 50%,transparent)', fontStyle: 'italic' }}>
              {verdict.reasoning}
            </div>
          )}
        </div>
      )}
    </Blueprint>
  );
}
