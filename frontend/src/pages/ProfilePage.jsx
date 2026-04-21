import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import AccuracyBadge from '../components/common/AccuracyBadge';
import { authUpdateProfile, authLogout } from '../utils/api';
import { TIMEZONE_OPTIONS } from '../utils/timezone';

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
  const { userProfile, setUserProfile, authUser, authToken, setAuth, clearAuth } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();

  const isLoggedIn = !!(authToken && authUser);

  // Sync server profile changes
  const updateServerMutation = useMutation({
    mutationFn: authUpdateProfile,
    onSuccess: (updatedUser) => {
      setAuth(authToken, updatedUser);
    },
  });

  const handleProfileChange = (updates) => {
    setUserProfile(updates);
    if (isLoggedIn) {
      // Map local keys to server keys
      const serverUpdates = {};
      if (updates.riskTolerance !== undefined) serverUpdates.risk_tolerance = updates.riskTolerance;
      if (updates.experienceLevel !== undefined) serverUpdates.experience_level = updates.experienceLevel;
      if (updates.bankroll !== undefined) serverUpdates.bankroll = updates.bankroll;
      if (updates.region !== undefined) serverUpdates.region = updates.region;
      if (Object.keys(serverUpdates).length > 0) {
        updateServerMutation.mutate(serverUpdates);
      }
    }
  };

  const logoutMutation = useMutation({
    mutationFn: authLogout,
    onSettled: () => {
      clearAuth();
      qc.clear();
    },
  });

  return (
    <div>
      <PageHeader title="PROFILE" subtitle="Your betting preferences" />

      <div style={{ padding: '16px' }}>

        {/* Auth status banner */}
        {isLoggedIn ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            background: 'rgba(34,197,94,0.08)',
            border: '1px solid rgba(34,197,94,0.25)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 4,
          }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-green-bright)' }}>
                Signed in
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                {authUser.email}
              </div>
            </div>
            <button
              className="btn btn-secondary"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
              style={{ fontSize: 12, padding: '6px 14px' }}
            >
              {logoutMutation.isPending ? 'Signing out…' : 'Sign out'}
            </button>
          </div>
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            background: 'rgba(26,107,168,0.08)',
            border: '1px solid rgba(26,107,168,0.25)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 4,
          }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-blue)' }}>
                Guest mode
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                Sign in to save bets &amp; profile across devices
              </div>
            </div>
            <button
              className="btn btn-primary"
              onClick={() => navigate('/login', { state: { from: location.pathname } })}
              style={{ fontSize: 12, padding: '6px 14px', whiteSpace: 'nowrap' }}
            >
              Sign in
            </button>
          </div>
        )}

        {/* Name */}
        <SectionLabel>Display Name</SectionLabel>
        <input
          value={userProfile.name}
          onChange={(e) => setUserProfile({ name: e.target.value })}
          placeholder="Enter your name…"
          style={{ width: '100%', padding: '10px 14px', fontSize: 14 }}
        />

        {/* Risk tolerance */}
        <SectionLabel>Risk Tolerance</SectionLabel>
        <SegmentControl
          options={RISK_OPTIONS}
          value={userProfile.riskTolerance}
          onChange={(v) => handleProfileChange({ riskTolerance: v })}
        />
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
          {{
            low:    'Secretariat will favour short-priced favourites and each-way bets. Stake sizes will be conservative (1–2% of bankroll).',
            medium: 'Secretariat will balance value and safety. Stakes will be moderate (2–4% of bankroll).',
            high:   'Secretariat will target overlays and longer shots. Stakes can be aggressive (3–6% of bankroll).',
          }[userProfile.riskTolerance]}
        </div>

        {/* Timezone */}
        <SectionLabel>Race Time Display</SectionLabel>
        <select
          value={userProfile.timezone || 'America/New_York'}
          onChange={(e) => setUserProfile({ timezone: e.target.value })}
          style={{ width: '100%', padding: '10px 14px', fontSize: 14, background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}
        >
          {TIMEZONE_OPTIONS.map((tz) => (
            <option key={tz.value} value={tz.value}>{tz.label}</option>
          ))}
        </select>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
          US race times are shown in this timezone on race cards
        </div>

        {/* Experience level */}
        <SectionLabel>Experience Level</SectionLabel>
        <SegmentControl
          options={EXPERIENCE_OPTIONS}
          value={userProfile.experienceLevel}
          onChange={(v) => handleProfileChange({ experienceLevel: v })}
        />
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
          {{
            beginner:     'Secretariat will use plain-English explanations, avoid jargon, and highlight the Beginner Tip first.',
            intermediate: 'Secretariat will balance plain-English and technical handicapping factors.',
            advanced:     'Secretariat will lead with technical analysis — Beyer figures, class drops, pace scenarios, and form cycles.',
          }[userProfile.experienceLevel]}
        </div>

        {/* Secretariat accuracy stats */}
        <SectionLabel>Secretariat Performance</SectionLabel>
        <AccuracyBadge />

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
          GateSmart is an AI-powered analysis tool for serious horseplayers, tracks, and ADWs. For responsible gambling support, visit <strong>ncpgambling.org</strong>.
        </div>
      </div>
    </div>
  );
}
