import { useState } from 'react';
import { useAppStore } from '../../store';

const TOTAL_STEPS = 4;

const EXPERIENCE_OPTIONS = [
  { value: 'beginner',     icon: '🐎', label: 'Complete Beginner',    desc: "I'm new to horse racing" },
  { value: 'intermediate', icon: '📊', label: 'Casual Bettor',        desc: 'I bet occasionally' },
  { value: 'advanced',     icon: '🏆', label: 'Experienced Bettor',   desc: "I know what I'm doing" },
];

const RISK_OPTIONS = [
  { value: 'low',    icon: '🛡',  label: 'Play It Safe',    desc: 'Favourites and low-risk bets' },
  { value: 'medium', icon: '⚖️', label: 'Balanced',         desc: 'Mix of value and safety' },
  { value: 'high',   icon: '⚡',  label: 'Go For Value',    desc: 'Overlays and longshots' },
];

const REGION_OPTIONS = [
  { value: 'usa', icon: '🇺🇸', label: 'USA' },
  { value: 'gb',  icon: '🇬🇧', label: 'UK & Ireland' },
  { value: 'aus', icon: '🇦🇺', label: 'Australia' },
  { value: 'int', icon: '🌍', label: 'International' },
];

const BANKROLL_CHIPS = [50, 100, 200, 500, 1000];

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

function OptionCard({ icon, label, desc, selected, onClick, multiSelect }) {
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
      <span style={{ fontSize: 26, flexShrink: 0 }}>{icon}</span>
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
    <div style={{
      animation: 'slideIn 0.3s ease',
      ...style,
    }}>
      {children}
    </div>
  );
}

export default function OnboardingFlow() {
  const { setUserProfile, completeOnboarding } = useAppStore();

  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState('beginner');
  const [bankroll, setBankroll] = useState(500);
  const [risk, setRisk] = useState('medium');
  const [regions, setRegions] = useState(['usa']);

  const advance = () => setStep((s) => s + 1);

  const save = () => {
    const primaryRegion = regions[0] || 'usa';
    setUserProfile({ bankroll, riskTolerance: risk, experienceLevel: experience, region: primaryRegion });
    completeOnboarding();
  };

  const skip = () => {
    completeOnboarding();
  };

  const selectExperience = (val) => {
    setExperience(val);
    setTimeout(advance, 400);
  };

  const selectRisk = (val) => {
    setRisk(val);
    setTimeout(advance, 400);
  };

  const toggleRegion = (val) => {
    setRegions((prev) =>
      prev.includes(val) ? prev.filter((r) => r !== val) : [...prev, val]
    );
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

        {/* ── Step 0: Experience ─────────────────────────────────────── */}
        {step === 0 && (
          <StepWrapper>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--accent-gold)', marginBottom: 6 }}>
              Welcome to GateSmart
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 24 }}>
              Let's personalise your experience.
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 14 }}>
              How familiar are you with horse racing betting?
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

        {/* ── Step 1: Bankroll ───────────────────────────────────────── */}
        {step === 1 && (
          <StepWrapper>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--accent-gold)', marginBottom: 6 }}>
              Set Your Paper Trading Bank
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>
              This is simulated money — nothing real. You can change it anytime.
            </div>

            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 48, color: 'var(--accent-gold-bright)', lineHeight: 1 }}>
                ${bankroll}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 20 }}>
              {BANKROLL_CHIPS.map((amt) => (
                <button
                  key={amt}
                  onClick={() => setBankroll(amt)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 20,
                    border: `1px solid ${bankroll === amt ? 'var(--accent-gold)' : 'var(--border-subtle)'}`,
                    background: bankroll === amt ? 'rgba(201,162,39,0.12)' : 'transparent',
                    color: bankroll === amt ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  £{amt}
                </button>
              ))}
            </div>

            <input
              type="range"
              min={50}
              max={2000}
              step={50}
              value={bankroll}
              onChange={(e) => setBankroll(Number(e.target.value))}
              style={{ width: '100%', marginBottom: 24, accentColor: 'var(--accent-gold)' }}
            />

            <button className="btn btn-primary btn-full" onClick={advance}>Next</button>
          </StepWrapper>
        )}

        {/* ── Step 2: Risk ───────────────────────────────────────────── */}
        {step === 2 && (
          <StepWrapper>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--accent-gold)', marginBottom: 6 }}>
              How do you like to bet?
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>
              This shapes how Secretariat tailors recommendations to you.
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

        {/* ── Step 3: Region ─────────────────────────────────────────── */}
        {step === 3 && (
          <StepWrapper>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--accent-gold)', marginBottom: 6 }}>
              Where do you follow racing?
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>
              Select all that apply.
            </div>
            {REGION_OPTIONS.map((opt) => (
              <OptionCard
                key={opt.value}
                icon={opt.icon}
                label={opt.label}
                selected={regions.includes(opt.value)}
                onClick={() => toggleRegion(opt.value)}
                multiSelect
              />
            ))}
            <button
              className="btn btn-primary btn-full"
              style={{ marginTop: 8 }}
              onClick={save}
            >
              Let's Go
            </button>
          </StepWrapper>
        )}

        {/* Skip */}
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
      </div>
    </div>
  );
}
