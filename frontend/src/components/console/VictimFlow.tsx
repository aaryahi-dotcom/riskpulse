import { useState, useEffect } from 'react';

type Stage = 'payment' | 'checking' | 'friction' | 'hold' | 'safe' | 'ended';
type Language = 'en' | 'hi';

const QNS_EN = [
  { id: 'call', q: 'Is someone on a call asking you to make this payment?', type: 'yes-no' as const },
  { id: 'refnum', q: 'Did the officer give you a reference number?', type: 'text' as const, prefill: 'CBI/2026/44817' },
  { id: 'family', q: 'Were you told not to tell your family?', type: 'yes-no' as const },
];

const QNS_HI = [
  { id: 'call', q: 'क्या कोई आपको इस भुगतान के लिए कॉल पर कह रहा है?', type: 'yes-no' as const },
  { id: 'refnum', q: 'क्या अधिकारी ने आपको संदर्भ संख्या दी?', type: 'text' as const, prefill: 'CBI/2026/44817' },
  { id: 'family', q: 'क्या आपको अपने परिवार को न बताने के लिए कहा गया था?', type: 'yes-no' as const },
];

const CAPTIONS_EN = {
  payment: 'Attacker shares screen, victim enters payment details',
  checking: 'RiskPulse detects coercion signals, initiates agent pipeline',
  friction: 'Friction questions trigger contradictions in victim responses',
  hold: 'Family is alerted while payment is held in fraud suspense account',
  ended: 'Call drops, scammer sees connection lost',
  safe: 'Victim is protected and informed. The money never reached the scammer.',
};

const CAPTIONS_HI = {
  payment: 'हमलावर स्क्रीन साझा करता है, पीड़ित भुगतान विवरण दर्ज करता है',
  checking: 'RiskPulse जबरदस्ती संकेत detect करता है, एजेंट पाइपलाइन शुरू करता है',
  friction: 'घर्षण प्रश्न पीड़ित की प्रतिक्रिया में विरोधाभास को ट्रिगर करते हैं',
  hold: 'परिवार को सतर्क किया जाता है, भुगतान धोखाधड़ी निलंबन खाते में रखा जाता है',
  ended: 'कॉल बंद हो जाती है, हमलावर को कनेक्शन खो दिखता है',
  safe: 'पीड़ित की रक्षा की जाती है और सूचित किया जाता है। पैसा घोटालेबाज़ तक नहीं पहुंचा।',
};

export function VictimFlow() {
  const [stage, setStage] = useState<Stage>('payment');
  const [lang, setLang] = useState<Language>('en');
  const [qIndex, setQIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [autoPlay, setAutoPlay] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [presentation, setPresentation] = useState(false);
  const [callTime, setCallTime] = useState(0);
  const [logs, setLogs] = useState<{ time: string; tag: string; msg: string; color: string }[]>([]);

  const questions = lang === 'en' ? QNS_EN : QNS_HI;
  const captions = lang === 'en' ? CAPTIONS_EN : CAPTIONS_HI;

  const addLog = (tag: string, msg: string, color: string) => {
    const clockSeconds = 34660 + callTime;
    const h = Math.floor(clockSeconds / 3600) % 24;
    const m = Math.floor((clockSeconds % 3600) / 60);
    const s = clockSeconds % 60;
    const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    setLogs((prev) => [...prev, { time, tag, msg, color }].slice(-20));
  };

  useEffect(() => {
    setLogs([
      { time: '09:37:40', tag: 'SDK', msg: 'RiskPulse session initialized', color: '#3b82f6' },
      { time: '09:37:41', tag: 'ENGINE', msg: 'Fraud detection engine online', color: '#10b981' },
    ]);
  }, []);

  useEffect(() => {
    if (stage !== 'ended' && stage !== 'safe') {
      const timer = setInterval(() => setCallTime((t) => t + 1), 1000);
      return () => clearInterval(timer);
    }
  }, [stage]);

  useEffect(() => {
    if (!autoPlay) return;
    const timings: Record<Stage, number> = { payment: 2000, checking: 2500, friction: 3000, hold: 4500, ended: 2000, safe: 0 };
    const timer = setTimeout(() => {
      if (stage === 'payment') {
        addLog('SDK', 'active_call = true', '#3b82f6');
        addLog('SDK', 'screen_capture = true (AnyDesk)', '#3b82f6');
        addLog('SDK', 'payee VPA pasted from clipboard', '#3b82f6');
        setStage('checking');
      } else if (stage === 'checking') {
        setStage('friction');
        addLog('ENGINE', 'VPA age: 2 days · amount 14× user median', '#10b981');
        addLog('ENGINE', 'risk 0.62 → GREY ZONE', '#f59e0b');
        addLog('AGENT', 'Signal: active call, screen-share, pasted VPA, new payee, amount 14× median', '#8b5cf6');
        addLog('AGENT', 'Scam-Pattern: DIGITAL ARREST 0.92', '#8b5cf6');
        addLog('SDK', 'friction screen secure (hidden from screen-share)', '#3b82f6');
      } else if (stage === 'friction' && qIndex === 0) {
        setAnswers((prev) => ({ ...prev, call: 'No' }));
        setQIndex(1);
      } else if (stage === 'friction' && qIndex === 1) {
        setAnswers((prev) => ({ ...prev, refnum: 'CBI/2026/44817' }));
        setQIndex(2);
      } else if (stage === 'friction' && qIndex === 2) {
        setAnswers((prev) => ({ ...prev, family: 'Yes' }));
        setStage('hold');
        addLog('RULE', 'CONTRADICTION: user says "no call", device active call → COACHED_RESPONSE', '#ef4444');
        addLog('AGENT', 'Friction: reference number supplied → coercion 0.97', '#8b5cf6');
        addLog('VERDICT', 'PROCESSING_HOLD: funds in fraud suspense, not sent', '#ef4444');
        addLog('ENGINE', 'protected mode 24h', '#10b981');
      } else if (stage === 'hold') {
        setStage('ended');
        addLog('SDK', 'active_call = false', '#3b82f6');
        addLog('GUARDIAN', 'family alert sent to Neha (+91 98•••• ••210)', '#06b6d4');
        addLog('GUARDIAN', 'evidence packet ready for 1930', '#06b6d4');
      } else if (stage === 'ended') {
        setStage('safe');
      }
    }, timings[stage]);
    return () => clearTimeout(timer);
  }, [autoPlay, stage, qIndex]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') advanceWithAutoAnswer();
      if (e.key === 'ArrowLeft') back();
      if (e.key === 'r' || e.key === 'R') reset();
      if (e.key === 'h' || e.key === 'H') setShowControls(!showControls);
      if (e.key === 'f' || e.key === 'F') setPresentation(!presentation);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [stage, qIndex, showControls, presentation, answers]);

  const advanceWithAutoAnswer = () => {
    if (stage === 'payment') {
      addLog('SDK', 'active_call = true', '#3b82f6');
      addLog('SDK', 'screen_capture = true (AnyDesk)', '#3b82f6');
      addLog('SDK', 'payee VPA pasted from clipboard', '#3b82f6');
      setStage('checking');
    }
    else if (stage === 'checking') {
      setStage('friction');
      setTimeout(() => {
        addLog('ENGINE', 'VPA age: 2 days · amount 14× user median', '#10b981');
        addLog('ENGINE', 'risk 0.62 → GREY ZONE', '#f59e0b');
        addLog('AGENT', 'Signal: active call, screen-share, pasted VPA, new payee, amount 14× median', '#8b5cf6');
        addLog('AGENT', 'Scam-Pattern: DIGITAL ARREST 0.92', '#8b5cf6');
        addLog('SDK', 'friction screen secure (hidden from screen-share)', '#3b82f6');
      }, 100);
    } else if (stage === 'friction' && qIndex === 0) {
      setAnswers((prev) => ({ ...prev, call: 'No' }));
      setQIndex(1);
    } else if (stage === 'friction' && qIndex === 1) {
      setAnswers((prev) => ({ ...prev, refnum: 'CBI/2026/44817' }));
      setQIndex(2);
    } else if (stage === 'friction' && qIndex === 2) {
      setAnswers((prev) => ({ ...prev, family: 'Yes' }));
      setStage('hold');
      setTimeout(() => {
        addLog('RULE', 'CONTRADICTION: user says "no call", device active call → COACHED_RESPONSE', '#ef4444');
        addLog('AGENT', 'Friction: reference number supplied → coercion 0.97', '#8b5cf6');
        addLog('VERDICT', 'PROCESSING_HOLD: funds in fraud suspense, not sent', '#ef4444');
        addLog('ENGINE', 'protected mode 24h', '#10b981');
      }, 100);
    } else if (stage === 'hold') {
      setStage('ended');
      setTimeout(() => {
        addLog('SDK', 'active_call = false', '#3b82f6');
        addLog('GUARDIAN', 'family alert sent to Neha (+91 98•••• ••210)', '#06b6d4');
        addLog('GUARDIAN', 'evidence packet ready for 1930', '#06b6d4');
      }, 100);
    } else if (stage === 'ended') {
      setStage('safe');
    }
  };

  const back = () => {
    if (stage === 'safe') setStage('ended');
    else if (stage === 'ended') setStage('hold');
    else if (stage === 'hold') setStage('friction');
    else if (stage === 'friction' && qIndex > 0) setQIndex(qIndex - 1);
    else if (stage === 'friction' && qIndex === 0) setStage('checking');
    else if (stage === 'checking') setStage('payment');
  };

  const reset = () => {
    setStage('payment');
    setQIndex(0);
    setAnswers({});
    setAutoPlay(false);
    setCallTime(0);
    setLogs([
      { time: '09:37:40', tag: 'SDK', msg: 'RiskPulse session initialized', color: '#3b82f6' },
      { time: '09:37:41', tag: 'ENGINE', msg: 'Fraud detection engine online', color: '#10b981' },
    ]);
  };

  const hasContradiction = answers['call'] === 'No' && (stage === 'hold' || stage === 'ended' || stage === 'safe');
  const riskScore = stage === 'payment' ? 0.15 : stage === 'checking' ? 0.62 : stage === 'friction' ? 0.84 : 0.97;

  if (presentation) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '22% 36% 42%', gap: 32, padding: 32, background: '#111', height: '100vh', overflow: 'hidden', fontFamily: 'var(--font-body)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888' }}>Scammer's View</div>
          <PhoneScreen stage={stage} qIndex={qIndex} questions={questions} answers={answers} setAnswers={() => {}} onNext={() => {}} callTime={callTime} mirror zoom={0.65} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888' }}>Victim's Phone</div>
          <PhoneScreen stage={stage} qIndex={qIndex} questions={questions} answers={answers} setAnswers={setAnswers} onNext={advanceWithAutoAnswer} callTime={callTime} lang={lang} />
        </div>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888', marginBottom: 12 }}>RiskPulse Brain</div>
          <BrainPanel logs={logs} hasContradiction={hasContradiction} riskScore={riskScore} />
        </div>
        <div style={{ gridColumn: '1 / -1', position: 'fixed', bottom: 0, left: 0, right: 0, background: 'rgba(0,0,0,0.8)', padding: 16, textAlign: 'center', borderTop: '1px solid #333' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', letterSpacing: '.01em' }}>{captions[stage]}</div>
          {lang === 'hi' && <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>{CAPTIONS_HI[stage]}</div>}
        </div>
        {showControls && (
          <div style={{ gridColumn: '1 / -1', position: 'fixed', top: 16, right: 32, display: 'flex', gap: 8, zIndex: 999 }}>
            <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')} style={{ padding: '6px 10px', background: '#333', color: '#fff', border: 'none', borderRadius: 4, fontSize: 10, fontWeight: 600, cursor: 'pointer' }}>EN</button>
            <button onClick={() => setAutoPlay(!autoPlay)} style={{ padding: '6px 10px', background: autoPlay ? '#10b981' : '#333', color: '#fff', border: 'none', borderRadius: 4, fontSize: 10, fontWeight: 600, cursor: 'pointer' }}>▶</button>
            <button onClick={reset} style={{ padding: '6px 10px', background: '#333', color: '#fff', border: 'none', borderRadius: 4, fontSize: 10, fontWeight: 600, cursor: 'pointer' }}>↻</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: 32, paddingBottom: 120, background: '#111', height: '100%', overflow: 'hidden', fontFamily: 'var(--font-body)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '22% 1fr 42%', gap: 32, flex: 1, minHeight: 0 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888', marginBottom: 12 }}>Scammer's View · Screen-share</div>
            <PhoneScreen stage={stage} qIndex={qIndex} questions={questions} answers={answers} setAnswers={() => {}} onNext={() => {}} callTime={callTime} mirror zoom={0.65} />
          </div>
          {(stage === 'hold' || stage === 'ended' || stage === 'safe') && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888', marginBottom: 12 }}>Neha's Alert</div>
              <NehaPhone stage={stage} lang={lang} zoom={0.65} />
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888', width: '100%', textAlign: 'center' }}>Victim's Phone</div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <PhoneScreen stage={stage} qIndex={qIndex} questions={questions} answers={answers} setAnswers={setAnswers} onNext={advanceWithAutoAnswer} callTime={callTime} lang={lang} />
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: '#888', marginBottom: 12 }}>RiskPulse Brain</div>
          <BrainPanel logs={logs} hasContradiction={hasContradiction} riskScore={riskScore} />
        </div>
      </div>

      <div style={{ background: 'rgba(255,255,255,0.05)', padding: 16, borderRadius: 8, textAlign: 'center', marginTop: 'auto' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', letterSpacing: '.01em' }}>{captions[stage]}</div>
        {lang === 'hi' && <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>{CAPTIONS_HI[stage]}</div>}
      </div>

      {showControls && (
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', paddingTop: 16, position: 'fixed', bottom: 24, left: 0, right: 0 }}>
          <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')} style={{ padding: '8px 12px', background: '#333', color: '#fff', border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
            {lang === 'en' ? 'EN' : 'हिंदी'}
          </button>
          <button onClick={() => setAutoPlay(!autoPlay)} style={{ padding: '8px 12px', background: autoPlay ? '#10b981' : '#333', color: '#fff', border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
            {autoPlay ? '▶ Playing' : '⏸ Manual'}
          </button>
          <button onClick={reset} style={{ padding: '8px 12px', background: '#333', color: '#fff', border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
            ↻ Reset
          </button>
          <button onClick={() => setPresentation(!presentation)} style={{ padding: '8px 12px', background: '#555', color: '#fff', border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
            🖥 Present (F)
          </button>
          <span style={{ fontSize: 10, color: '#666', padding: '8px 12px', whiteSpace: 'nowrap' }}>
            → Next | ← Back | R Reset | H Hide | F Present
          </span>
        </div>
      )}
    </div>
  );
}

function PhoneScreen({ stage, qIndex, questions, answers, setAnswers, onNext, callTime, mirror, zoom = 1, lang }: any) {
  const baseTime = 12 * 60 + 47;
  const callDurationTime = baseTime + callTime;

  const formatClockTime = () => {
    const clockSeconds = 34660 + callTime;
    const h = Math.floor(clockSeconds / 3600) % 24;
    const m = Math.floor((clockSeconds % 3600) / 60);
    const s = clockSeconds % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const formatCallDuration = () => {
    const m = Math.floor(callDurationTime / 60);
    const s = callDurationTime % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const phoneHeight = 'calc(100vh - 280px)';
  const showCallPill = stage !== 'ended' && stage !== 'safe' && stage !== 'friction';

  return (
    <div
      style={{
        position: 'relative',
        height: phoneHeight,
        width: 'auto',
        aspectRatio: '9 / 19.5',
        margin: mirror ? '0 auto' : undefined,
        transform: mirror ? `scale(${zoom})` : undefined,
        transformOrigin: 'top center',
      }}
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          background: '#fff',
          border: mirror ? '6px solid #333' : '10px solid #222',
          borderRadius: 40,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: mirror ? undefined : '0 20px 60px rgba(0,0,0,0.3)',
        }}
      >
        <StatusBar time={formatClockTime()} />

        {showCallPill && (
          <div style={{ padding: '12px 16px', background: '#f5f5f5', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'center' }}>
            <div style={{ background: '#10b981', color: '#fff', padding: '6px 12px', borderRadius: 16, fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              ● On call · {formatCallDuration()}
            </div>
          </div>
        )}

        <div style={{ flex: 1, padding: 20, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 16, overflow: 'auto' }}>
          {mirror && stage === 'friction' ? (
            <>
              <div style={{ fontSize: 32 }}>🔒</div>
              <div style={{ color: '#666', fontSize: 10, textAlign: 'center' }}>Secure screen</div>
              <div style={{ color: '#666', fontSize: 10, textAlign: 'center' }}>content hidden</div>
            </>
          ) : mirror && (stage === 'ended' || stage === 'safe') ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', background: '#1a1a1a', fontSize: 14, color: '#fff', fontWeight: 500 }}>Screen-share ended</div>
          ) : stage === 'payment' ? (
            <>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 28, fontWeight: 600, marginBottom: 20 }}>PayNow</div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                  <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 24, fontWeight: 600 }}>
                    S
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>Safe Custody A/C</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#333' }}>safe.custody09@ybl</span>
                    <span style={{ background: '#e0e0e0', padding: '2px 6px', borderRadius: 4, fontSize: 9, whiteSpace: 'nowrap' }}>pasted</span>
                  </div>
                </div>
              </div>
              <div style={{ textAlign: 'center', borderTop: '1px solid #eee', paddingTop: 12 }}>
                <div style={{ fontSize: 32, fontWeight: 600 }}>₹2,00,000</div>
                <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>bail bond</div>
              </div>
              <div style={{ background: '#f9f9f9', padding: 12, borderRadius: 8, fontSize: 11 }}>
                <div style={{ color: '#666' }}>From: Savings ••4821</div>
              </div>
              {!mirror && <TapButton label="Pay" onClick={onNext} />}
            </>
          ) : stage === 'checking' ? (
            <>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>PayNow</div>
                <div style={{ fontSize: 14, color: '#888', marginBottom: 20 }}>Verifying payment…</div>
                <div style={{ width: 40, height: 40, border: '3px solid #e0e0e0', borderTop: '3px solid #3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto' }} />
                <div style={{ fontSize: 11, fontWeight: 600, marginTop: 20, color: '#333' }}>₹2,00,000</div>
                <div style={{ fontSize: 10, color: '#888', marginTop: 4 }}>to safe.custody09@ybl</div>
              </div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </>
          ) : stage === 'friction' ? (
            <>
              <div style={{ fontSize: 16, fontWeight: 600, textAlign: 'center', marginBottom: 12 }}>
                {questions[qIndex].q}
              </div>
              {questions[qIndex].type === 'yes-no' ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <TapButton label="Yes" onClick={() => { setAnswers({ ...answers, [questions[qIndex].id]: 'Yes' }); onNext?.(); }} style={{ flex: 1, background: '#10b981' }} />
                  <TapButton label="No" onClick={() => { setAnswers({ ...answers, [questions[qIndex].id]: 'No' }); onNext?.(); }} style={{ flex: 1, background: '#ef4444' }} />
                </div>
              ) : (
                <input
                  type="text"
                  defaultValue={questions[qIndex].prefill}
                  onChange={(e) => setAnswers({ ...answers, [questions[qIndex].id]: e.target.value })}
                  style={{ padding: 12, border: '1px solid #ddd', borderRadius: 8, fontSize: 12 }}
                  onKeyPress={(e) => e.key === 'Enter' && onNext?.()}
                />
              )}
            </>
          ) : stage === 'hold' ? (
            <>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, fontWeight: 600, color: '#10b981', marginBottom: 8 }}>✓</div>
                <div style={{ fontSize: 12, color: '#666', lineHeight: 1.5 }}>Payment processing, your bank will confirm within 24 hours</div>
              </div>
              {!mirror && <TapButton label="End call" onClick={onNext} style={{ background: '#3b82f6' }} />}
            </>
          ) : stage === 'ended' ? (
            <div style={{ textAlign: 'center', fontSize: 12, color: '#888' }}>Screen-share ended</div>
          ) : (
            <>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, fontWeight: 600, color: '#10b981', marginBottom: 8 }}>✓</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#10b981', marginBottom: 12, lineHeight: 1.4 }}>
                  {lang === 'en' ? 'Your money is safe. ₹2,00,000 was NOT sent.' : 'आपका पैसा सुरक्षित है। ₹2,00,000 नहीं भेजा गया।'}
                </div>
                <div style={{ fontSize: 11, color: '#666', lineHeight: 1.5, marginBottom: 12 }}>
                  {lang === 'en' ? 'No police agency conducts "digital arrest". This was a scam.' : 'कोई भी पुलिस एजेंसी "डिजिटल गिरफ्तारी" नहीं करती। यह एक घोटाला था।'}
                </div>
                <div style={{ fontSize: 11, color: '#666', marginBottom: 12 }}>
                  {lang === 'en' ? 'Your family has been informed.' : 'आपके परिवार को सूचित किया गया है।'}
                </div>
              </div>
              {!mirror && <TapButton label={lang === 'en' ? 'Call 1930' : '1930 पर कॉल करें'} onClick={() => {}} style={{ background: '#06b6d4' }} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function NehaPhone({ lang, zoom = 0.65 }: any) {
  void lang;
  const phoneHeight = `calc(100vh - 280px)`;

  return (
    <div style={{ height: phoneHeight, width: 'auto', aspectRatio: '9 / 19.5', margin: '0 auto', transform: `scale(${zoom})`, transformOrigin: 'top center' }}>
      <div
        style={{
          width: '100%',
          height: '100%',
          background: '#fff',
          border: '4px solid #222',
          borderRadius: 20,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
        }}
      >
        <div style={{ background: '#000', color: '#fff', padding: '6px 12px', fontSize: 11, fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}>
          <span>09:37</span>
          <span>●●●</span>
        </div>
        <div style={{ flex: 1, padding: 12, display: 'flex', flexDirection: 'column', justifyContent: 'center', background: '#f0f9ff', borderLeft: '3px solid #06b6d4', overflow: 'hidden' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#333', lineHeight: 1.4 }}>
            RiskPulse alert: Your father may be on a scam call. ₹2,00,000 is on hold and has NOT reached the caller. Please call him now.
          </div>
          <div style={{ fontSize: 11, color: '#0ea5e9', marginTop: 6, fontWeight: 600 }}>Report at 1930</div>
        </div>
      </div>
    </div>
  );
}

function BrainPanel({ logs, hasContradiction, riskScore }: any) {
  const phoneHeight = 'calc(100vh - 280px)';

  return (
    <div
      style={{
        height: phoneHeight,
        width: '100%',
        background: '#1a1a1a',
        border: '1px solid #333',
        borderRadius: 8,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        color: '#fff',
        fontSize: 11,
        overflow: 'hidden',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #333' }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#888', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '.05em' }}>Risk Score</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
          <div style={{ height: 8, flex: 1, background: '#333', borderRadius: 4, overflow: 'hidden', minWidth: 0 }}>
            <div style={{ height: '100%', width: `${Math.min(riskScore * 100, 100)}%`, background: riskScore > 0.85 ? '#ef4444' : riskScore > 0.6 ? '#f59e0b' : '#10b981', transition: 'all 0.3s' }} />
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, minWidth: 50, textAlign: 'right', whiteSpace: 'nowrap', flexShrink: 0 }}>{riskScore.toFixed(2)}</div>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto', fontSize: 9 }}>
        {logs.map((log: any, i: number) => (
          <div key={i} style={{ display: 'flex', gap: 8, fontFamily: 'var(--font-mono, monospace)', whiteSpace: 'nowrap' }}>
            <span style={{ color: '#666', minWidth: 50, flexShrink: 0 }}>{log.time}</span>
            <span style={{ background: log.color, color: '#000', padding: '1px 4px', borderRadius: 2, fontWeight: 600, minWidth: 50, textAlign: 'center', flexShrink: 0 }}>
              {log.tag}
            </span>
            <span style={{ color: '#aaa', flex: 1, wordBreak: 'break-word', minWidth: 0 }}>{log.msg}</span>
          </div>
        ))}
      </div>

      {hasContradiction && (
        <div style={{ marginTop: 12, padding: 8, background: '#7f1d1d', border: '1px solid #ef4444', borderRadius: 4, fontSize: 9 }}>
          <div style={{ color: '#ef4444', fontWeight: 600, marginBottom: 2 }}>⚠ COACHED_RESPONSE</div>
          <div style={{ color: '#fca5a5' }}>Answer contradicts device signals</div>
        </div>
      )}
    </div>
  );
}

function StatusBar({ time }: any) {
  return (
    <div style={{ background: '#000', color: '#fff', padding: '6px 12px', fontSize: 9, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 600 }}>
      <span>{time}</span>
      <span>●●●●●</span>
    </div>
  );
}

function TapButton({ label, onClick, style }: any) {
  const [ripple, setRipple] = useState<{ x: number; y: number } | null>(null);
  const handleClick = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setRipple({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setTimeout(() => setRipple(null), 600);
    onClick?.();
  };

  return (
    <button
      onClick={handleClick}
      style={{
        padding: 12,
        background: style?.background || '#3b82f6',
        color: '#fff',
        border: 'none',
        borderRadius: 8,
        fontWeight: 600,
        fontSize: 13,
        cursor: 'pointer',
        position: 'relative',
        overflow: 'hidden',
        transition: 'opacity 0.2s',
        ...style,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
      onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
    >
      {label}
      {ripple && (
        <div
          style={{
            position: 'absolute',
            left: ripple.x,
            top: ripple.y,
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.5)',
            transform: 'translate(-50%, -50%)',
            animation: 'ripple 0.6s ease-out',
            pointerEvents: 'none',
          }}
        />
      )}
      <style>{`@keyframes ripple { to { width: 300px; height: 300px; opacity: 0; } }`}</style>
    </button>
  );
}
