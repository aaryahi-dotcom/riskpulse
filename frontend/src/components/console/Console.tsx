import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { Dashboard } from './dashboard/Dashboard';
import { Workbench } from './Workbench';
import { GraphScreen } from './GraphScreen';
import { Alerts } from './Alerts';
import { Thresholds } from './Thresholds';
import { Rules } from './Rules';
import { Health } from './Health';
import { Simulator } from './Simulator';
import type { RiskPulse } from '../../state/useRiskPulse';

export function Console({ rp }: { rp: RiskPulse }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '210px minmax(0,1fr)', minHeight: '100vh' }}>
      <Sidebar rp={rp} />
      <main style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Header rp={rp} />
        <div style={{ padding: '22px 24px 40px', display: 'flex', flexDirection: 'column', gap: 22 }}>
          {rp.screen === 'dashboard' && <Dashboard rp={rp} />}
          {rp.screen === 'workbench' && <Workbench rp={rp} />}
          {rp.screen === 'graph' && <GraphScreen rp={rp} />}
          {rp.screen === 'alerts' && <Alerts />}
          {rp.screen === 'thresholds' && <Thresholds rp={rp} />}
          {rp.screen === 'rules' && <Rules />}
          {rp.screen === 'health' && <Health rp={rp} />}
          {rp.screen === 'simulator' && <Simulator rp={rp} />}
        </div>
      </main>
    </div>
  );
}
