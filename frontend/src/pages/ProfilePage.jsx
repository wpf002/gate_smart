import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import Icon from '../components/common/Icon';
import { authUpdateProfile, authLogout, getContestProgress } from '../utils/api';
import { TIMEZONE_OPTIONS } from '../utils/timezone';

const EXPERIENCE_OPTIONS = ['beginner', 'advanced'];

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

      <div style={{ padding: '16px' }} className="profile-grid">
        <div>

        {/* Auth status banner */}
        {isLoggedIn ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            background: 'rgba(201,162,39,0.08)',
            border: '1px solid var(--border-gold)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 4,
          }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-gold)' }}>
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
              {logoutMutation.isPending ? 'Signing Out…' : 'Sign Out'}
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
              Sign In
            </button>
          </div>
        )}

        {/* Timezone */}
        <SectionLabel>Race Time Display</SectionLabel>
        <select
          value={userProfile.timezone || 'America/New_York'}
          onChange={(e) => setUserProfile({ timezone: e.target.value })}
          // backgroundColor (not the `background` shorthand) — the shorthand
          // resets background-image and would wipe the chevron from globals.css,
          // leaving the select with no dropdown indicator at all.
          style={{ width: '100%', padding: '10px 30px 10px 14px', fontSize: 14, backgroundColor: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}
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
            beginner: 'Plain English, top pick highlighted, details hidden until you tap.',
            advanced: 'Full technical view — pace, all bet types, Beyer figures, nothing simplified.',
          }[userProfile.experienceLevel]}
        </div>

        <div style={{
          marginTop: 16,
          padding: '10px 14px',
          background: 'rgba(201,162,39,0.06)',
          border: '1px solid var(--border-gold)',
          borderRadius: 'var(--radius-md)',
          fontSize: 12,
          color: 'var(--text-muted)',
          lineHeight: 1.5,
        }}>
          GateSmart is an AI-powered analysis tool for serious horseplayers, tracks, and ADWs. For responsible gambling support, visit <strong>ncpgambling.org</strong>.
        </div>
        </div>

        <ProgressPanel isLoggedIn={isLoggedIn} navigate={navigate} />
      </div>
    </div>
  );
}

function ProgressPanel({ isLoggedIn, navigate }) {
  const { data: me } = useQuery({
    queryKey: ['contest-me'],
    queryFn: getContestProgress,
    enabled: isLoggedIn,
  });

  const links = [
    { label: 'Leaderboard', path: '/contest', note: 'Beat Secretariat standings' },
    { label: 'Report Card', path: '/accuracy', note: 'How the picks actually did' },
    { label: 'Watchlist', path: '/watchlist', note: 'Horses, trainers and jockeys you follow' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {isLoggedIn && me && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)', fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>
            YOUR PROGRESS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)' }}>
            {[
              [me.points, 'Points'],
              [me.pick_day_streak, 'Day streak'],
              [`${me.wins}/${me.settled}`, 'Winners'],
            ].map(([value, label], i) => (
              <div key={label} style={{ textAlign: 'center', padding: '10px 4px' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: i === 0 ? 'var(--accent-gold-bright)' : 'var(--text-primary)' }}>
                  {value}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        {links.map(({ label, path, note }, i) => (
          <button key={path} onClick={() => navigate(path)} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%',
            padding: '12px 14px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
            borderTop: i ? '1px solid var(--border-subtle)' : 'none',
          }}>
            <span>
              <span style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
              <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{note}</span>
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: 16 }}>›</span>
          </button>
        ))}
      </div>
    </div>
  );
}
