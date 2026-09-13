import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getContestProgress, getLeaderboard, setDisplayName } from '../utils/api';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';

function Stat({ value, label, highlight = false }) {
  return (
    <div style={{ textAlign: 'center', padding: '10px 4px' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: highlight ? 'var(--accent-gold-bright)' : 'var(--text-primary)' }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
    </div>
  );
}

function NameEditor({ current }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  const save = async () => {
    setError('');
    try {
      await setDisplayName(value);
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ['contest-me'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not save that name');
    }
  };

  if (!editing) {
    return (
      <button onClick={() => { setValue(current.startsWith('Handicapper ') ? '' : current); setEditing(true); }}
        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer', padding: 0 }}>
        {current} · Edit Name
      </button>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
      <input value={value} maxLength={40} onChange={(e) => setValue(e.target.value)} placeholder="Leaderboard name" style={{ flex: 1, minWidth: 140 }} />
      <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 12px' }} onClick={save}>Save</button>
      <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px' }} onClick={() => setEditing(false)}>Cancel</button>
      {error && <span style={{ width: '100%', fontSize: 12, color: 'var(--accent-red-bright)' }}>{error}</span>}
    </div>
  );
}

export default function ContestPage() {
  const navigate = useNavigate();
  const authToken = useAppStore((s) => s.authToken);
  const [period, setPeriod] = useState('week');

  const { data: board } = useQuery({ queryKey: ['leaderboard', period], queryFn: () => getLeaderboard(period) });
  const { data: me } = useQuery({ queryKey: ['contest-me'], queryFn: getContestProgress, enabled: !!authToken });

  const sec = board?.secretariat;

  return (
    <div>
      <PageHeader title="BEAT SECRETARIAT" subtitle="CALL THE WINNER BEFORE POST · FREE TO PLAY" />

      <div style={{ padding: 16 }}>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
          10 points for the winner, +5 more when Secretariat is wrong. No betting, no money.
        </div>

        <div className="contest-grid">
          {/* ── You ─────────────────────────────────────────── */}
          {authToken && me ? (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
                <NameEditor current={me.display_name} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)' }}>
                <Stat value={me.points} label="Points" highlight />
                <Stat value={me.pick_day_streak} label="Day streak" />
                <Stat value={me.beat_secretariat_streak} label="Beat streak" />
                <Stat value={`${me.wins}/${me.settled}`} label="Winners" />
                <Stat value={me.beat_secretariat} label="Beat Secretariat" />
                <Stat value={me.best_correct_streak} label="Best streak" />
              </div>
            </div>
          ) : (
            <div style={{ padding: 14, background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sign in to make picks and track your streaks.</span>
              {!authToken && (
                <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 12px', flexShrink: 0 }} onClick={() => navigate('/login')}>Sign In</button>
              )}
            </div>
          )}

          {/* ── Leaderboard ─────────────────────────────────── */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)', gap: 10 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>LEADERBOARD</div>
                {sec?.win_rate !== null && sec?.win_rate !== undefined && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    Bar to beat: Secretariat <strong style={{ color: 'var(--accent-gold-bright)' }}>{(sec.win_rate * 100).toFixed(1)}%</strong> winners · {sec.races} races
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                {[['day', 'Today'], ['week', 'This Week']].map(([k, label]) => (
                  <button key={k} onClick={() => setPeriod(k)} style={{
                    fontSize: 12, padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
                    background: period === k ? 'var(--accent-gold-dim)' : 'transparent',
                    color: period === k ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
                    border: '1px solid var(--border-subtle)',
                  }}>{label}</button>
                ))}
              </div>
            </div>

            {!board?.board?.length ? (
              <div style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  No graded picks {period === 'day' ? 'today' : 'this week'} yet.
                </span>
                <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px', flexShrink: 0 }} onClick={() => navigate('/')}>
                  Make A Pick
                </button>
              </div>
            ) : board.board.map((row) => {
              const isMe = me && row.name === me.display_name;
              return (
                <div key={`${row.rank}-${row.name}`} style={{
                  display: 'grid', gridTemplateColumns: '32px 1fr auto auto', gap: 10, alignItems: 'center',
                  padding: '8px 14px', borderBottom: '1px solid var(--border-subtle)',
                  background: isMe ? 'rgba(201,162,39,0.08)' : 'transparent',
                }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: row.rank <= 3 ? 'var(--accent-gold-bright)' : 'var(--text-muted)' }}>
                    {row.rank}
                  </span>
                  <span style={{ fontSize: 14, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.name}{row.beat_secretariat ? <span style={{ fontSize: 11, color: 'var(--accent-gold)', marginLeft: 6 }}>beat S×{row.beat_secretariat}</span> : null}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {row.wins}/{row.picks}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', minWidth: 40, textAlign: 'right' }}>
                    {row.points}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
