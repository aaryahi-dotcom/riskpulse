import { useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { scoreTransaction } from '../../lib/api';

const DEMO_SCENARIOS = [
  {
    name: 'Safe Transfer (APPROVE)',
    payload: {
      amount: 5000,
      sender_id: `demo-safe-${Date.now()}@okhdfc`,
      receiver_id: 'demo-trusted@ybl',
      timestamp: new Date().toISOString(),
      channel: 'UPI',
      vpa: 'demo-trusted@ybl',
    },
  },
  {
    name: 'Moderate Risk - Unverified (COOL_OFF)',
    payload: {
      amount: 75000,
      sender_id: `demo-moderate-${Date.now()}@okhdfc`,
      receiver_id: 'demo-new-payee@ybl',
      timestamp: new Date(Date.now() + 60000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-new-payee@ybl',
    },
  },
  {
    name: 'High Risk - Rapid Suspicious Pattern (BLOCK)',
    payload: {
      amount: 500000,
      sender_id: `demo-suspicious-${Date.now()}@okhdfc`,
      receiver_id: 'demo-mule-1@ybl',
      timestamp: new Date(Date.now() + 120000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-mule-1@ybl',
    },
  },
  {
    name: 'Another Safe Payment (APPROVE)',
    payload: {
      amount: 25000,
      sender_id: `demo-legit-${Date.now()}@oksbi`,
      receiver_id: 'demo-vendor@paytm',
      timestamp: new Date(Date.now() + 180000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-vendor@paytm',
    },
  },
  {
    name: 'Borderline Risk - First-time Large (COOL_OFF)',
    payload: {
      amount: 150000,
      sender_id: `demo-newuser-${Date.now()}@apl`,
      receiver_id: 'demo-unknown@ybl',
      timestamp: new Date(Date.now() + 240000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-unknown@ybl',
    },
  },
  {
    name: 'Critical Risk - Multiple Red Flags (BLOCK)',
    payload: {
      amount: 750000,
      sender_id: `demo-victim-coercion-${Date.now()}@okhdfc`,
      receiver_id: 'demo-offshore@ybl',
      timestamp: new Date(Date.now() + 300000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-offshore@ybl',
    },
  },
];

type LogEntry = {
  msg: string;
  color: string;
  status: 'pending' | 'success' | 'warning' | 'error';
};

export function DemoMode() {
  const [running, setRunning] = useState(false);
  const [demoComplete, setDemoComplete] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState(0);

  const runFullDemo = async () => {
    setRunning(true);
    setDemoComplete(false);
    setLogs([]);
    setProgress(0);

    const addLog = (msg: string, status: LogEntry['status'] = 'pending') => {
      const colors = {
        pending: '#9ca3af',
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
      };
      setLogs((prev) => [...prev, { msg, color: colors[status], status }]);
    };

    try {
      addLog('🎬 Starting RiskPulse hackathon demo...', 'pending');
      await new Promise((r) => setTimeout(r, 500));

      addLog('✓ Demo initialized', 'success');
      await new Promise((r) => setTimeout(r, 300));

      // Inject all 6 scenarios in sequence
      for (let i = 0; i < DEMO_SCENARIOS.length; i++) {
        const scenario = DEMO_SCENARIOS[i];
        try {
          addLog(`${i + 1}. ${scenario.name}...`, 'pending');
          const resp = await scoreTransaction(scenario.payload);

          // Determine status color based on decision
          let statusColor: LogEntry['status'] = 'success';
          if (resp.decision === 'block') statusColor = 'error';
          else if (resp.decision === 'step_up') statusColor = 'warning';

          const verdict = resp.agent_decision?.verdict || 'N/A';
          const msg = `Score: ${resp.risk_score.toFixed(2)} → Agent Verdict: ${verdict}`;
          addLog(msg, statusColor);

          setProgress((i + 1) / DEMO_SCENARIOS.length);
          await new Promise((r) => setTimeout(r, 700));
        } catch (e) {
          addLog(`Error on ${scenario.name}`, 'error');
        }
      }

      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'success');
      addLog('✓ Demo complete! All 6 transactions scored', 'success');
      addLog('See mix of APPROVE (green), COOL_OFF (yellow), BLOCK (red)', 'success');
      addLog('Click any transaction in live feed to see agent reasoning', 'success');
      setProgress(1);
      setDemoComplete(true);
    } catch (e) {
      addLog(`Fatal error: ${String(e).slice(0, 60)}`, 'error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <Blueprint
      style={{
        padding: 16,
        background: demoComplete ? 'color-mix(in srgb, #22c55e 8%, transparent)' : 'color-mix(in srgb, #f59e0b 6%, transparent)',
        border: demoComplete
          ? '1px solid #22c55e'
          : running
            ? '1px solid #3b82f6'
            : '1px solid #f59e0b',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 13, letterSpacing: '.1em', textTransform: 'uppercase', fontWeight: 600, flex: 1 }}>
          Hackathon Demo Mode
        </span>
        <button
          type="button"
          onClick={runFullDemo}
          disabled={running}
          style={{
            padding: '8px 14px',
            background: running ? '#9ca3af' : demoComplete ? '#22c55e' : '#f59e0b',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            cursor: running ? 'not-allowed' : 'pointer',
            fontWeight: 500,
            fontSize: 12,
            opacity: running ? 0.7 : 1,
          }}
        >
          {running ? 'Running...' : demoComplete ? 'Demo Complete ✓' : 'Run Full Demo'}
        </button>
      </div>

      {/* Progress bar */}
      {(running || demoComplete) && (
        <div style={{ height: 4, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              background: demoComplete ? '#22c55e' : '#3b82f6',
              width: `${progress * 100}%`,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      )}

      {/* Log output */}
      {logs.length > 0 && (
        <div
          style={{
            maxHeight: 240,
            overflow: 'auto',
            background: 'color-mix(in srgb, var(--color-text) 2%, transparent)',
            border: '1px solid color-mix(in srgb, var(--color-text) 10%, transparent)',
            borderRadius: 4,
            padding: 10,
            fontFamily: 'ui-monospace,Menlo,monospace',
            fontSize: 10.5,
            lineHeight: 1.5,
          }}
        >
          {logs.map((log, i) => (
            <div key={i} style={{ color: log.color, marginBottom: 2 }}>
              {log.msg}
            </div>
          ))}
        </div>
      )}

      {!running && !demoComplete && (
        <span style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)', lineHeight: 1.4 }}>
          Watch the demo inject 6 transactions across 3 fraud scenarios. Watch the live feed update in real-time, then check
          the brain panel for agent reasoning and verdicts.
        </span>
      )}

      {demoComplete && (
        <span style={{ fontSize: 11, color: '#22c55e', lineHeight: 1.4 }}>
          Demo data injected! See transactions in live feed. Click one to see the brain panel breakdown of how the agent scored it.
        </span>
      )}
    </Blueprint>
  );
}
