import { useState } from 'react';
import { useAppStore } from '../../store';
import { authLogin, authRegister } from '../../utils/api';

const TOTAL_STEPS = 3;

const EXPERIENCE_OPTIONS = [
  { value: 'beginner', label: 'Beginner', desc: "New to horse racing — plain English explanations, key pick highlighted" },
  { value: 'advanced', label: 'Advanced', desc: "Experienced bettor — full technical data, all bet types, pace analysis" },
];

const RISK_OPTIONS = [
  { value: 'low',    label: 'Play It Safe',    desc: 'Favorites and low-risk bets' },
  { value: 'medium', label: 'Balanced',         desc: 'Mix of value and safety' },
  { value: 'high',   label: 'Go For Value',    desc: 'Overlays and longshots' },
];

function ProgressDots({ step }) {
  return (
    <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 32 }}>
      {Array.from({ length: TOTAL_STEPS }, (_, i) => (
        <div
          key={i}
          style={{
            width: i === step ? 24 : 8,
            height: 8,
            borderRadius: 4,
            background: i === step ? 'var(--accent-gold)' : i < step ? 'var(--accent-gold-dim)' : 'var(--border-medium)',
            transition: 'all 0.3s ease',
          }}
        />
      ))}
    </div>
  );
}

function OptionCard({ label, desc, selected, onClick, multiSelect }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        width: '100%',
        padding: '14px 16px',
        background: selected ? 'rgba(201,162,39,0.1)' : 'var(--bg-card)',
        border: `2px solid ${selected ? 'var(--accent-gold)' : 'var(--border-subtle)'}`,
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all 0.15s',
        marginBottom: 10,
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 15, color: selected ? 'var(--accent-gold-bright)' : 'var(--text-primary)' }}>
          {label}
        </div>
        {desc && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{desc}</div>
        )}
      </div>
      {multiSelect && selected && (
        <span style={{ color: 'var(--accent-gold)', fontSize: 18 }}>✓</span>
      )}
    </button>
  );
}

function StepWrapper({ children, style }) {
  return (
    <div style={{ animation: 'slideIn 0.3s ease', ...style }}>
      {children}
    </div>
  );
}

function AuthStep({ onSuccess }) {
  const [mode, setMode] = useState(null); // null | 'register' | 'login'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { setAuth, resetOnboarding } = useAppStore();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      let result;
      if (mode === 'register') {
        result = await authRegister(email.trim().toLowerCase(), password);
        resetOnboarding(); // ensure overlay stays mounted when authToken is set
        setAuth(result.token, result.user);
      } else {
        result = await authLogin(email.trim().toLowerCase(), password);
        setAuth(result.token, result.user);
      }
      onSuccess(result.user, mode);
    } catch (err) {
      setError(err?.response?.data?.detail || (mode === 'register' ? 'Registration failed' : 'Sign in failed'));
    } finally {
      setLoading(false);
    }
  };

  if (mode === null) {
    return (
      <StepWrapper>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 36, color: 'var(--accent-gold)', letterSpacing: '0.04em', marginBottom: 8 }}>
            GATESMART
          </div>
          <div style={{ fontSize: 15, color: 'var(--text-primary)', fontWeight: 600, marginBottom: 4 }}>
            AI-powered horse racing intelligence
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Built for tracks, ADWs, and serious horseplayers
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          <button
            className="btn btn-primary"
            style={{ flex: 1, padding: '12px 0', fontSize: 14 }}
            onClick={() => setMode('register')}
          >
            Create Account
          </button>
          <button
            className="btn btn-secondary"
            style={{ flex: 1, padding: '12px 0', fontSize: 14 }}
            onClick={() => setMode('login')}
          >
            Sign In
          </button>
        </div>

      </StepWrapper>
    );
  }

  return (
    <StepWrapper>
      <button
        onClick={() => { setMode(null); setError(''); }}
        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer', padding: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: 4 }}
      >
        ← Back
      </button>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--accent-gold)', marginBottom: 20 }}>
        {mode === 'register' ? 'Create Account' : 'Sign In'}
      </div>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            autoComplete="email"
            style={{ width: '100%', padding: '11px 14px', fontSize: 14, boxSizing: 'border-box' }}
          />
        </div>
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
            Password {mode === 'register' && <span style={{ fontWeight: 400 }}>(min 8 characters)</span>}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === 'register' ? 'Minimum 8 characters' : 'Your password'}
            required
            minLength={mode === 'register' ? 8 : undefined}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            style={{ width: '100%', padding: '11px 14px', fontSize: 14, boxSizing: 'border-box' }}
          />
        </div>
        {error && (
          <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.1)', borderRadius: 'var(--radius-md)', borderLeft: '2px solid var(--accent-red-bright)', fontSize: 13, color: 'var(--accent-red-bright)', marginBottom: 14 }}>
            {error}
          </div>
        )}
        <button
          type="submit"
          className="btn btn-primary btn-full"
          disabled={loading}
          style={{ padding: '12px 0', fontSize: 14, fontWeight: 700 }}
        >
          {loading
            ? (mode === 'register' ? 'Creating account…' : 'Signing in…')
            : (mode === 'register' ? 'Create Account' : 'Sign In')}
        </button>
      </form>
    </StepWrapper>
  );
}

export default function OnboardingFlow() {
  const { setUserProfile, completeOnboarding, setAuth } = useAppStore();

  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState('beginner');
  const [risk, setRisk] = useState('medium');

  const advance = () => setStep((s) => s + 1);
  const back = () => setStep((s) => s - 1);

  const save = () => {
    setUserProfile({ bankroll: 500, riskTolerance: risk, experienceLevel: experience, region: 'usa' });
    completeOnboarding();
  };

  const skip = () => completeOnboarding();

  const handleAuthSuccess = (user, mode) => {
    if (mode === 'login' && user?.experience_level && user.experience_level !== 'beginner') {
      setUserProfile({
        bankroll: user.bankroll || 500,
        riskTolerance: user.risk_tolerance || 'medium',
        experienceLevel: user.experience_level || 'beginner',
        region: 'usa',
      });
      completeOnboarding();
    } else {
      advance();
    }
  };

  const selectExperience = (val) => {
    setExperience(val);
    setTimeout(advance, 400);
  };

  const selectRisk = (val) => {
    setRisk(val);
    setTimeout(save, 400);
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 1000,
      background: 'rgba(0,0,0,0.92)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px 16px',
    }}>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(24px); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>

      <div style={{
        width: '100%',
        maxWidth: 380,
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-medium)',
        borderRadius: 'var(--radius-lg)',
        padding: '28px 24px',
        maxHeight: '90vh',
        overflowY: 'auto',
      }}>
        <ProgressDots step={step} />

        {/* ── Step 0: Auth ─────────────────────────────────────────── */}
        {step === 0 && (
          <AuthStep onSuccess={handleAuthSuccess} />
        )}

        {/* ── Step 1: Experience ─────────────────────────────────────── */}
        {step === 1 && (
          <StepWrapper>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--accent-gold)', marginBottom: 6 }}>
              Your experience level
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>
              How familiar are you with horse racing?
            </div>
            {EXPERIENCE_OPTIONS.map((opt) => (
              <OptionCard
                key={opt.value}
                {...opt}
                selected={experience === opt.value}
                onClick={() => selectExperience(opt.value)}
              />
            ))}
          </StepWrapper>
        )}

        {/* ── Step 2: Risk ───────────────────────────────────────────── */}
        {step === 2 && (
          <StepWrapper>
            <button onClick={back} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer', padding: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: 4 }}>← Back</button>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--accent-gold)', marginBottom: 6 }}>
              How do you like to bet?
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>
              This shapes how GateSmart tailors recommendations to you.
            </div>
            {RISK_OPTIONS.map((opt) => (
              <OptionCard
                key={opt.value}
                {...opt}
                selected={risk === opt.value}
                onClick={() => selectRisk(opt.value)}
              />
            ))}
          </StepWrapper>
        )}

        {/* Skip (not shown on auth step) */}
        {step > 0 && (
          <button
            onClick={skip}
            style={{
              display: 'block',
              width: '100%',
              marginTop: 16,
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              fontSize: 12,
              cursor: 'pointer',
              textAlign: 'center',
            }}
          >
            Skip setup →
          </button>
        )}
      </div>
    </div>
  );
}
