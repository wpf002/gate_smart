import React from 'react';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';

const RISK_OPTIONS = ['low', 'medium', 'high'];
const EXPERIENCE_OPTIONS = ['beginner', 'intermediate', 'advanced'];

function SegmentControl({ options, value, onChange }) {
  return (
    <div style={{
      display: 'flex',
      background: 'var(--bg-elevated)',
      borderRadius: 'var(--radius-md)',
      padding: 3,
      gap: 2,
    }}>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          style={{
            flex: 1,
            padding: '7px 0',
            borderRadius: 8,
            border: 'none',
            background: value === opt ? 'var(--bg-card)' : 'transparent',
            color: value === opt ? 'var(--text-primary)' : 'var(--text-muted)',
            fontFamily: 'var(--font-body)',
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
            textTransform: 'capitalize',
            transition: 'all 0.15s',
            boxShadow: value === opt ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
          }}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 11,
      fontWeight: 700,
      color: 'var(--text-muted)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 8,
      marginTop: 20,
    }}>
      {children}
    </div>
  );
}

export default function ProfilePage() {
  const { userProfile, setUserProfile } = useAppStore();

  return (
    <div>
      <PageHeader title="PROFILE" subtitle="Your betting preferences" />

      <div style={{ padding: '16px' }}>
        {/* Name */}
        <SectionLabel>Display Name</SectionLabel>
        <input
          value={userProfile.name}
          onChange={(e) => setUserProfile({ name: e.target.value })}
          placeholder="Enter your name…"
          style={{ width: '100%', padding: '10px 14px', fontSize: 14 }}
        />

        {/* Bankroll */}
        <SectionLabel>Betting Bankroll</SectionLabel>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 18, color: 'var(--text-muted)' }}>$</span>
          <input
            type="number"
            min="0"
            value={userProfile.bankroll}
            onChange={(e) => setUserProfile({ bankroll: parseFloat(e.target.value) || 0 })}
            style={{ flex: 1, padding: '10px 14px', fontSize: 16, fontFamily: 'var(--font-mono)' }}
          />
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
          Used by Secretariat to calculate stake recommendations
        </div>

        {/* Risk tolerance */}
        <SectionLabel>Risk Tolerance</SectionLabel>
        <SegmentControl
          options={RISK_OPTIONS}
          value={userProfile.riskTolerance}
          onChange={(v) => setUserProfile({ riskTolerance: v })}
        />

        {/* Experience level */}
        <SectionLabel>Experience Level</SectionLabel>
        <SegmentControl
          options={EXPERIENCE_OPTIONS}
          value={userProfile.experienceLevel}
          onChange={(v) => setUserProfile({ experienceLevel: v })}
        />

        {/* Profile summary */}
        <div style={{
          marginTop: 24,
          padding: 16,
          background: 'rgba(201,162,39,0.08)',
          border: '1px solid var(--border-gold)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--accent-gold)', marginBottom: 10 }}>
            YOUR BETTING PROFILE
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            <div>💰 Bankroll: <strong style={{ color: 'var(--text-primary)' }}>${userProfile.bankroll.toFixed(2)}</strong></div>
            <div>⚡ Risk: <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{userProfile.riskTolerance}</strong></div>
            <div>📚 Level: <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{userProfile.experienceLevel}</strong></div>
          </div>
        </div>

        <div style={{
          marginTop: 16,
          padding: '10px 14px',
          background: 'rgba(26,107,168,0.08)',
          borderRadius: 'var(--radius-md)',
          borderLeft: '2px solid var(--accent-blue)',
          fontSize: 12,
          color: 'var(--text-muted)',
          lineHeight: 1.5,
        }}>
          GateSmart is an educational tool. Always gamble responsibly. Never bet more than you can afford to lose. If gambling is affecting your life, visit <strong>BeGambleAware.org</strong>.
        </div>
      </div>
    </div>
  );
}
