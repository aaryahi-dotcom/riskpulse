import { useRiskPulse } from './state/useRiskPulse';
import { Landing } from './components/Landing';
import { Auth } from './components/Auth';
import { Console } from './components/console/Console';

export default function App() {
  const rp = useRiskPulse();

  return (
    <div
      data-theme={rp.theme}
      data-frame={rp.frame}
      style={{ minHeight: '100vh', background: 'var(--color-bg)', color: 'var(--color-text)', fontFamily: 'var(--font-body)', fontSize: 15 }}
    >
      {rp.view === 'landing' && <Landing rp={rp} />}
      {rp.view === 'auth' && <Auth rp={rp} />}
      {rp.view === 'app' && <Console rp={rp} />}
    </div>
  );
}
