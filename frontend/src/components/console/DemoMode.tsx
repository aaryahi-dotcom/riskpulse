import { useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { scoreTransaction } from '../../lib/api';

const DEMO_SCENARIOS = [
  {
    name: 'Digital Arrest - Transfer 1',
    payload: {
      amount: 50000,
      sender_id: `demo-victim-${Date.now()}@okhdfc`,
      receiver_id: 'demo-mule-1@ybl',
      timestamp: new Date().toISOString(),
      channel: 'UPI',
      vpa: 'demo-mule-1@ybl',
    },
  },
  {
    name: 'Digital Arrest - Transfer 2',
    payload: {
      amount: 75000,
      sender_id: `demo-victim-${Date.now()}@okhdfc`,
      receiver_id: 'demo-mule-2@ybl',
      timestamp: new Date(Date.now() + 120000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-mule-2@ybl',
    },
  },
  {
    name: 'Digital Arrest - Transfer 3',
    payload: {
      amount: 100000,
      sender_id: `demo-victim-${Date.now()}@okhdfc`,
      receiver_id: 'demo-mule-3@ybl',
      timestamp: new Date(Date.now() + 240000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-mule-3@ybl',
    },
  },
  {
    name: 'Genuine Large Payment',
    payload: {
      amount: 150000,
      sender_id: `demo-legit-user-${Date.now()}@oksbi`,
      receiver_id: 'demo-payee-legit@paytm',
      timestamp: new Date(Date.now() + 3600000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-payee-legit@paytm',
    },
  },
  {
    name: 'Fake KYC - Transfer 1',
    payload: {
      amount: 25000,
      sender_id: `demo-kyc-victim-${Date.now()}@apl`,
      receiver_id: 'demo-kyc-fraud@ybl',
      timestamp: new Date().toISOString(),
      channel: 'UPI',
      vpa: 'demo-kyc-fraud@ybl',
    },
  },
  {
    name: 'Fake KYC - Transfer 2',
    payload: {
      amount: 50000,
      sender_id: `demo-kyc-victim-${Date.now()}@apl`,
      receiver_id: 'demo-kyc-fraud@ybl',
      timestamp: new Date(Date.now() + 60000).toISOString(),
      channel: 'UPI',
      vpa: 'demo-kyc-fraud@ybl',
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

      // Demo header
      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'pending');
      addLog('Scenario 1: Digital Arrest Scam', 'warning');
      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'pending');
      await new Promise((r) => setTimeout(r, 400));

      // Run digital arrest scenarios
      for (let i = 0; i < 3; i++) {
        const scenario = DEMO_SCENARIOS[i];
        try {
          addLog(`Injecting ${scenario.name}...`, 'pending');
          const resp = await scoreTransaction(scenario.payload);
          const msg = `Score: ${resp.risk_score.toFixed(2)} | Decision: ${resp.decision.toUpperCase()} | Puppet: ${resp.puppet_score.toFixed(2)}`;
          addLog(msg, resp.decision === 'block' ? 'error' : resp.decision === 'step_up' ? 'warning' : 'success');
          setProgress((i + 1) / DEMO_SCENARIOS.length);
          await new Promise((r) => setTimeout(r, 600));
        } catch (e) {
          addLog(`Error on ${scenario.name}`, 'error');
        }
      }

      // Genuine payment
      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'pending');
      addLog('Scenario 2: Legitimate Large Payment', 'pending');
      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'pending');
      await new Promise((r) => setTimeout(r, 400));

      const legitimateScenario = DEMO_SCENARIOS[3];
      try {
        addLog(`Injecting ${legitimateScenario.name}...`, 'pending');
        const resp = await scoreTransaction(legitimateScenario.payload);
        const msg = `Score: ${resp.risk_score.toFixed(2)} | Decision: ${resp.decision.toUpperCase()} | Puppet: ${resp.puppet_score.toFixed(2)}`;
        addLog(msg, resp.decision === 'block' ? 'error' : resp.decision === 'step_up' ? 'warning' : 'success');
        setProgress(0.67);
        await new Promise((r) => setTimeout(r, 600));
      } catch (e) {
        addLog(`Error on ${legitimateScenario.name}`, 'error');
      }

      // Fake KYC
      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'pending');
      addLog('Scenario 3: Fake KYC + Remote Access', 'warning');
      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'pending');
      await new Promise((r) => setTimeout(r, 400));

      for (let i = 4; i < 6; i++) {
        const scenario = DEMO_SCENARIOS[i];
        try {
          addLog(`Injecting ${scenario.name}...`, 'pending');
          const resp = await scoreTransaction(scenario.payload);
          const msg = `Score: ${resp.risk_score.toFixed(2)} | Decision: ${resp.decision.toUpperCase()} | Puppet: ${resp.puppet_score.toFixed(2)}`;
          addLog(msg, resp.decision === 'block' ? 'error' : resp.decision === 'step_up' ? 'warning' : 'success');
          setProgress(0.67 + ((i - 3) / 3) * 0.33);
          await new Promise((r) => setTimeout(r, 600));
        } catch (e) {
          addLog(`Error on ${scenario.name}`, 'error');
        }
      }

      addLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'success');
      addLog('✓ Demo complete! Check the live feed and brain panel →', 'success');
      addLog('Notice how the agent pipeline detects coercion in the arrest scenario', 'success');
      addLog('and approves the legitimate large payment.', 'success');
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
