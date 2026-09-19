import { useState } from 'react';
import { Blueprint } from '../ui/Blueprint';
import { scoreTransaction } from '../../lib/api';

export function QuickScenarioLauncher() {
  const [running, setRunning] = useState(false);

  const runQuickScenario = async (type: 'arrest' | 'legit' | 'kyc') => {
    setRunning(true);
    const now = new Date();

    try {
      if (type === 'arrest') {
        // Digital arrest: 3 rapid transfers to new beneficiaries
        const sender = `victim-${Date.now()}@okhdfc`;
        for (const [amt, idx] of [[50000, 0], [75000, 1], [100000, 2]]) {
          await scoreTransaction({
            amount: amt as number,
            sender_id: sender,
            receiver_id: `mule-${idx}@ybl`,
            timestamp: new Date(now.getTime() + (idx as number) * 120000).toISOString(),
            channel: 'UPI',
            vpa: `mule-${idx}@ybl`,
          });
          await new Promise((r) => setTimeout(r, 300));
        }
      } else if (type === 'legit') {
        // Genuine: single large transfer
        await scoreTransaction({
          amount: 150000,
          sender_id: `user-${Date.now()}@oksbi`,
          receiver_id: `payee-legit@paytm`,
          timestamp: new Date(now.getTime() + 3600000).toISOString(),
          channel: 'UPI',
          vpa: `payee-legit@paytm`,
        });
      } else {
        // Fake KYC: 2 transfers with urgency
        const sender = `victim-kyc-${Date.now()}@apl`;
        for (const amt of [25000, 50000]) {
          await scoreTransaction({
            amount: amt,
            sender_id: sender,
            receiver_id: `kyc-fraud@ybl`,
            timestamp: new Date(now.getTime() + Math.random() * 60000).toISOString(),
            channel: 'UPI',
            vpa: `kyc-fraud@ybl`,
          });
          await new Promise((r) => setTimeout(r, 300));
        }
      }
    } catch (e) {
      console.error('Scenario failed:', e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <Blueprint
      style={{
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        background: 'color-mix(in srgb, var(--color-accent) 4%, transparent)',
      }}
    >
      <span style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>
        Quick Test
      </span>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
        <button
          type="button"
          onClick={() => runQuickScenario('arrest')}
          disabled={running}
          style={{
            padding: '8px 10px',
            fontSize: 10,
            background: 'color-mix(in srgb, #ef4444 12%, transparent)',
            border: '1px solid #ef4444',
            color: '#ef4444',
            borderRadius: 3,
            cursor: running ? 'not-allowed' : 'pointer',
            opacity: running ? 0.6 : 1,
            fontWeight: 500,
          }}
        >
          Arrest
        </button>
        <button
          type="button"
          onClick={() => runQuickScenario('legit')}
          disabled={running}
          style={{
            padding: '8px 10px',
            fontSize: 10,
            background: 'color-mix(in srgb, #22c55e 12%, transparent)',
            border: '1px solid #22c55e',
            color: '#22c55e',
            borderRadius: 3,
            cursor: running ? 'not-allowed' : 'pointer',
            opacity: running ? 0.6 : 1,
            fontWeight: 500,
          }}
        >
          Legit
        </button>
        <button
          type="button"
          onClick={() => runQuickScenario('kyc')}
          disabled={running}
          style={{
            padding: '8px 10px',
            fontSize: 10,
            background: 'color-mix(in srgb, #f59e0b 12%, transparent)',
            border: '1px solid #f59e0b',
            color: '#f59e0b',
            borderRadius: 3,
            cursor: running ? 'not-allowed' : 'pointer',
            opacity: running ? 0.6 : 1,
            fontWeight: 500,
          }}
        >
          KYC
        </button>
      </div>
      <span style={{ fontSize: 9, color: 'color-mix(in srgb,var(--color-text) 45%,transparent)', lineHeight: 1.3 }}>
        {running ? 'Injecting...' : 'Click to inject scenarios and watch live feed'}
      </span>
    </Blueprint>
  );
}
