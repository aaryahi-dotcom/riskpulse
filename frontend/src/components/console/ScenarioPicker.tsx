import { useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { scoreTransaction, type ScorePayload } from '../../lib/api';

type Scenario = {
  key: string;
  label: string;
  description: string;
  expectedOutcome: string;
};

const SCENARIOS: Scenario[] = [
  {
    key: 'digital_arrest',
    label: '🚨 Digital Arrest Victim',
    description: 'Fake police officer on call, pressuring transfer. Multiple red flags.',
    expectedOutcome: 'Should → BLOCK (coercion detected)',
  },
  {
    key: 'large_new_payee',
    label: '✅ Genuine Large Payment',
    description: 'Large amount to new payee, no call, normal hours. Legitimate.',
    expectedOutcome: 'Should → COOL_OFF (brief friction, then ALLOW)',
  },
  {
    key: 'fake_kyc_remote',
    label: '⚠️ Fake KYC + Remote Access',
    description: 'AnyDesk open, urgent SMS about account verification. Sophisticated fraud.',
    expectedOutcome: 'Should → BLOCK (remote access + urgency)',
  },
];

export function ScenarioPicker({ onScenarioRun }: { onScenarioRun?: () => void }) {
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<Array<{ msg: string; color: string }>>([]);

  const runScenario = async (scenarioKey: string) => {
    setRunning(true);
    setLog([]);

    const now = new Date();
    const payloads: ScorePayload[] = [];

    if (scenarioKey === 'digital_arrest') {
      const sender = `victim-arrest-${Date.now()}@okhdfc`;
      payloads.push(
        {
          amount: 50000,
          sender_id: sender,
          receiver_id: `mule-arrest-1@ybl`,
          timestamp: new Date(now.getTime()).toISOString(),
          channel: 'UPI',
          vpa: `mule-arrest-1@ybl`,
        },
        {
          amount: 75000,
          sender_id: sender,
          receiver_id: `mule-arrest-2@ybl`,
          timestamp: new Date(now.getTime() + 120000).toISOString(),
          channel: 'UPI',
          vpa: `mule-arrest-2@ybl`,
        },
        {
          amount: 100000,
          sender_id: sender,
          receiver_id: `mule-arrest-3@ybl`,
          timestamp: new Date(now.getTime() + 240000).toISOString(),
          channel: 'UPI',
          vpa: `mule-arrest-3@ybl`,
        },
      );
    } else if (scenarioKey === 'large_new_payee') {
      payloads.push({
        amount: 150000,
        sender_id: `legitimate-user-${Date.now()}@oksbi`,
        receiver_id: `new-payee-legit@paytm`,
        timestamp: new Date(now.getTime() + 3600000).toISOString(),
        channel: 'UPI',
        vpa: `new-payee-legit@paytm`,
      });
    } else if (scenarioKey === 'fake_kyc_remote') {
      const sender = `victim-kyc-${Date.now()}@apl`;
      payloads.push(
        {
          amount: 25000,
          sender_id: sender,
          receiver_id: `kyc-fraud@ybl`,
          timestamp: new Date(now.getTime()).toISOString(),
          channel: 'UPI',
          vpa: `kyc-fraud@ybl`,
        },
        {
          amount: 50000,
          sender_id: sender,
          receiver_id: `kyc-fraud@ybl`,
          timestamp: new Date(now.getTime() + 60000).toISOString(),
          channel: 'UPI',
          vpa: `kyc-fraud@ybl`,
        },
      );
    }

    let successCount = 0;
    let blockCount = 0;

    for (const payload of payloads) {
      try {
        const resp = await scoreTransaction(payload);
        const statusColor =
          resp.decision === 'block'
            ? '#ef4444'
            : resp.decision === 'step_up'
              ? '#f59e0b'
              : '#22c55e';
        const msg = `Scored ₹${payload.amount.toLocaleString('en-IN')} → ${resp.risk_score.toFixed(2)} (${resp.decision.toUpperCase()})`;
        setLog((prev) => [...prev, { msg, color: statusColor }]);

        if (resp.decision === 'block') blockCount++;
        successCount++;
      } catch (e) {
        setLog((prev) => [...prev, { msg: `Error: ${String(e).slice(0, 60)}`, color: '#ef4444' }]);
      }

      await new Promise((r) => setTimeout(r, 400));
    }

    const scenario = SCENARIOS.find((s) => s.key === scenarioKey);
    setLog((prev) => [
      ...prev,
      {
        msg: `✓ Scenario complete: ${successCount}/${payloads.length} scored, ${blockCount} blocked.`,
        color: '#4ade80',
      },
      { msg: `Expected: ${scenario?.expectedOutcome}`, color: '#60a5fa' },
    ]);

    setRunning(false);
    onScenarioRun?.();
  };

  return (
    <Blueprint style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', display: 'block', marginBottom: 12 }}>
          Demo Scenarios
        </span>
        <span style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 68%,transparent)', lineHeight: 1.5 }}>
          Click a scenario to inject transactions and watch the agent pipeline in action. See real risk scores, verdicts, and brain panel reasoning.
        </span>
      </div>

      {/* Scenario Buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {SCENARIOS.map((scenario) => (
          <button
            key={scenario.key}
            type="button"
            onClick={() => runScenario(scenario.key)}
            disabled={running}
            style={{
              padding: '12px 14px',
              background: 'color-mix(in srgb, var(--color-text) 4%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-text) 12%, transparent)',
              borderRadius: 4,
              cursor: running ? 'not-allowed' : 'pointer',
              opacity: running ? 0.6 : 1,
              textAlign: 'left',
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              if (!running) (e.currentTarget as HTMLButtonElement).style.background = 'color-mix(in srgb, var(--color-text) 8%, transparent)';
            }}
            onMouseOut={(e) => {
              if (!running) (e.currentTarget as HTMLButtonElement).style.background = 'color-mix(in srgb, var(--color-text) 4%, transparent)';
            }}
          >
            <div style={{ fontWeight: 500, fontSize: 12, marginBottom: 3 }}>{scenario.label}</div>
            <div style={{ fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{scenario.description}</div>
          </button>
        ))}
      </div>

      {/* Log Output */}
      {log.length > 0 && (
        <div
          style={{
            background: 'color-mix(in srgb, var(--color-text) 3%, transparent)',
            border: '1px solid color-mix(in srgb, var(--color-text) 10%, transparent)',
            borderRadius: 4,
            padding: 10,
            maxHeight: 180,
            overflow: 'auto',
            fontFamily: 'ui-monospace,Menlo,monospace',
            fontSize: 10.5,
          }}
        >
          {log.map((line, i) => (
            <div key={i} style={{ color: line.color, marginBottom: 3, lineHeight: 1.3 }}>
              {line.msg}
            </div>
          ))}
        </div>
      )}
    </Blueprint>
  );
}
