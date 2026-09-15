import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import Icon from '../components/common/Icon';
import NameEditor from '../components/contest/NameEditor';
import FirstPick, { isDefaultName } from '../components/contest/FirstPick';
import { authUpdateProfile, authLogout, getContestProgress } from '../utils/api';
import { TIMEZONE_OPTIONS } from '../utils/timezone';

const EXPERIENCE_OPTIONS = ['beginner', 'advanced'];

const EXPERIENCE_LABELS = { beginner: 'Beginner', advanced: 'Advanced' };

const EXPERIENCE_NOTES = {
  beginner: 'Plain English, top pick highlighted, details hidden until you tap.',
  advanced: 'Full technical view — pace, all bet types, Beyer figures, nothing simplified.',
};

const SHORTCUTS = [
  { label: 'Leaderboard', path: '/contest', note: 'Beat Secretariat standings', icon: 'trophy' },
  { label: 'Report Card', path: '/accuracy', note: 'How the picks actually did', icon: 'chart' },
  { label: 'Watchlist', path: '/watchlist', note: 'Horses, trainers and jockeys you follow', icon: 'star' },
];

const card = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-md)',
};

function CardTitle({ children }) {
  return (
    <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', letterSpacing: '0.04em' }}>
      {children}
    </div>
  );
}

function FieldLabel({ children, first = false }) {
  return (
    <div style={{
      fontSize: 11,
      fontWeight: 700,
      color: 'var(--text-muted)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginTop: first ? 16 : 22,
      marginBottom: 8,
    }}>
      {children}
    </div>
  );
}

function Hint({ children }) {
  return <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.5 }}>{children}</div>;
}

function ExperienceOptions({ value, onChange }) {
  return (
    <div className="profile-experience">
      {EXPERIENCE_OPTIONS.map((opt) => {
        const selected = value === opt;
        return (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            aria-pressed={selected}
            style={{
              display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
              padding: '12px 14px', borderRadius: 'var(--radius-md)',
              background: selected ? 'rgba(201,162,39,0.10)' : 'var(--bg-elevated)',
              border: `1px solid ${selected ? 'var(--accent-gold)' : 'var(--border-subtle)'}`,
              transition: 'all 0.15s',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
                border: `2px solid ${selected ? 'var(--accent-gold-bright)' : 'var(--text-muted)'}`,
                background: selected ? 'radial-gradient(var(--accent-gold-bright) 40%, transparent 45%)' : 'transparent',
              }} />
              <span style={{ fontSize: 14, fontWeight: 600, color: selected ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                {EXPERIENCE_LABELS[opt]}
              </span>
            </span>
            <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
              {EXPERIENCE_NOTES[opt]}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function Avatar({ letter }) {
  return (
    <div className="profile-avatar" style={{
      borderRadius: '50%',
      flexShrink: 0,
      display: 'grid',
      placeItems: 'center',
      background: 'rgba(201,162,39,0.12)',
      border: '1px solid var(--border-gold)',
      color: 'var(--accent-gold-bright)',
      fontFamily: 'var(--font-display)',
    }}>
      {letter || <Icon name="profile" size={24} />}
    </div>
  );
}

export default function ProfilePage() {
  const { userProfile, setUserProfile, authUser, authToken, setAuth, clearAuth } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();

  const isLoggedIn = !!(authToken && authUser);

  const { data: me } = useQuery({
    queryKey: ['contest-me'],
    queryFn: getContestProgress,
    enabled: isLoggedIn,
  });

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

  const name = me?.display_name;
  // "Handicapper <id>" is the leaderboard's stand-in until a name is chosen;
  // showing it as the account's name made the card read as placeholder data.
  const customName = name && !isDefaultName(name) ? name : '';
  const initial = (customName || authUser?.email || '').trim().charAt(0).toUpperCase();

  return (
    <div>
      <PageHeader
        title="PROFILE"
        subtitle="Account, progress & settings"
        right={isLoggedIn ? (
          <button
            className="btn btn-secondary"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            style={{ fontSize: 12, padding: '7px 14px' }}
          >
            {logoutMutation.isPending ? 'Signing Out…' : 'Sign Out'}
          </button>
        ) : (
          <button
            className="btn btn-primary"
            onClick={() => navigate('/login', { state: { from: location.pathname } })}
            style={{ fontSize: 12, padding: '7px 14px' }}
          >
            Sign In
          </button>
        )}
      />

      <div className="profile-layout">
        {/* ── Account + progress ─────────────────────────────── */}
        <section className="profile-identity" style={{ ...card, borderColor: isLoggedIn ? 'var(--border-gold)' : 'var(--border-subtle)' }}>
          <div className="profile-account">
            <Avatar letter={isLoggedIn ? initial : ''} />
            <div className="profile-account-text">
              {isLoggedIn ? (
                <>
                  {customName ? (
                    <NameEditor
                      current={customName}
                      renderIdle={(edit) => (
                        <div className="profile-name-row" style={{ display: 'flex', alignItems: 'baseline', gap: 10, minWidth: 0 }}>
                          <span style={{
                            fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--text-primary)',
                            letterSpacing: '0.02em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {customName}
                          </span>
                          <button onClick={edit} style={{
                            background: 'none', border: 'none', padding: 0, cursor: 'pointer', flexShrink: 0,
                            fontSize: 12, fontWeight: 600, color: 'var(--accent-gold)',
                          }}>
                            Edit Name
                          </button>
                        </div>
                      )}
                    />
                  ) : (
                    <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {authUser.email}
                    </div>
                  )}
                  {customName ? (
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {authUser.email}
                    </div>
                  ) : name ? (
                    <NameEditor
                      current={name}
                      renderIdle={(edit) => (
                        <button className="btn btn-ghost" onClick={edit} style={{ fontSize: 12, padding: '5px 12px', marginTop: 8 }}>
                          Set Your Name
                        </button>
                      )}
                    />
                  ) : null}
                </>
              ) : (
                <>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
                    Guest
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>
                    Sign in to save settings and track your points
                  </div>
                </>
              )}
            </div>
          </div>

          {isLoggedIn && me && !me.total_picks && <FirstPick divider />}
          {isLoggedIn && !(me && !me.total_picks) && (
            <div className="profile-stats">
              {[
                // Dashes until progress loads, so the card keeps its shape.
                [me ? me.points : '–', 'Points'],
                [me ? me.pick_day_streak : '–', 'Day Streak'],
                [me ? `${me.wins}/${me.settled}` : '–', 'Winners'],
                [me ? me.beat_secretariat : '–', 'Beat Secretariat'],
              ].map(([value, label], i) => (
                <div key={label} className="profile-stat">
                  <div className="profile-stat-value" style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: i === 0 ? 'var(--accent-gold-bright)' : 'var(--text-primary)' }}>
                    {value}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="profile-main">
          {/* ── Settings ─────────────────────────────────────── */}
          <section className="profile-card-body" style={card}>
            <CardTitle>SETTINGS</CardTitle>

            <FieldLabel first>Race Time Display</FieldLabel>
            <select
              value={userProfile.timezone || 'America/New_York'}
              onChange={(e) => setUserProfile({ timezone: e.target.value })}
              className="form-select"
              // backgroundColor (not the `background` shorthand) — the shorthand
              // resets background-image and would wipe the chevron from globals.css,
              // leaving the select with no dropdown indicator at all.
              style={{ width: '100%', backgroundColor: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}
            >
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz.value} value={tz.value}>{tz.label}</option>
              ))}
            </select>
            <Hint>US race times are shown in this timezone on race cards</Hint>

            <FieldLabel>Experience Level</FieldLabel>
            <ExperienceOptions
              value={userProfile.experienceLevel}
              onChange={(v) => handleProfileChange({ experienceLevel: v })}
            />
          </section>

          {/* ── Shortcuts ────────────────────────────────────── */}
          <section style={{ ...card, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="profile-card-body" style={{ paddingBottom: 6 }}>
              <CardTitle>SHORTCUTS</CardTitle>
            </div>
            {SHORTCUTS.map(({ label, path, note, icon }, i) => (
              <button key={path} onClick={() => navigate(path)} style={{
                flex: 1, display: 'flex', alignItems: 'center', gap: 14, width: '100%', minHeight: 64,
                padding: '12px 20px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
                borderTop: i ? '1px solid var(--border-subtle)' : 'none',
              }}>
                <span style={{
                  width: 36, height: 36, borderRadius: 'var(--radius-sm)', flexShrink: 0,
                  display: 'grid', placeItems: 'center', background: 'var(--bg-elevated)', color: 'var(--accent-gold)',
                }}>
                  <Icon name={icon} size={18} />
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
                  <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{note}</span>
                </span>
                <span style={{ color: 'var(--text-muted)', fontSize: 18 }}>›</span>
              </button>
            ))}
          </section>
        </div>

        <div className="profile-footer" style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, textAlign: 'center', padding: '0 8px' }}>
          GateSmart is an AI-powered analysis tool for serious horseplayers, tracks, and ADWs. For responsible gambling support, visit <strong style={{ color: 'var(--text-secondary)' }}>ncpgambling.org</strong>.
        </div>
      </div>
    </div>
  );
}
