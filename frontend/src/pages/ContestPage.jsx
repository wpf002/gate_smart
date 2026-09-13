import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getContestProgress, getLeaderboard, setDisplayName } from '../utils/api';
import { useAppStore } from '../store';

function Stat({ value, label, highlight = false }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '12px 6px' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 700, color: highlight ? 'var(--accent-gold-bright)' : 'var(--text-primary)' }}>
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
        {current} · edit name
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
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '16px 16px 40px' }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--accent-gold)', margin: '0 0 4px' }}>BEAT SECRETARIAT</h1>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 16px' }}>
        Call the winner before post. 10 points if you're right, +5 more if Secretariat is wrong. Free to play — no betting, no money.
      </p>

      {authToken && me ? (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)', marginBottom: 16 }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
            <NameEditor current={me.display_name} />
          </div>
          <div style={{ display: 'flex' }}>
            <Stat value={me.points} label="Points" highlight />
            <Stat value={me.pick_day_streak} label="Day streak" />
            <Stat value={me.beat_secretariat_streak} label="Beat-Secretariat streak" />
          </div>
          <div style={{ display: 'flex', borderTop: '1px solid var(--border-subtle)' }}>
            <Stat value={me.wins} label={`Winners of ${me.settled}`} />
            <Stat value={me.beat_secretariat} label="Times beat Secretariat" />
            <Stat value={me.best_correct_streak} label="Best winner streak" />
          </div>
        </div>
      ) : !authToken ? (
        <div style={{ padding: 14, background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sign in to make picks and track your streaks.</span>
          <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 12px' }} onClick={() => navigate('/login')}>Sign in</button>
        </div>
      ) : null}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0' }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 14, letterSpacing: '0.06em', color: 'var(--text-primary)' }}>LEADERBOARD</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {[['day', 'Today'], ['week', 'This week']].map(([k, label]) => (
            <button key={k} onClick={() => setPeriod(k)} style={{
              fontSize: 12, padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
              background: period === k ? 'var(--accent-gold-dim)' : 'transparent',
              color: period === k ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              border: '1px solid var(--border-subtle)',
            }}>{label}</button>
          ))}
        </div>
      </div>

      {sec?.win_rate !== null && sec?.win_rate !== undefined && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Bar to beat: Secretariat picked <strong style={{ color: 'var(--accent-gold-bright)' }}>{(sec.win_rate * 100).toFixed(1)}%</strong> winners across {sec.races} races.
        </div>
      )}

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        {!board?.board?.length ? (
          <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
            No graded picks yet {period === 'day' ? 'today' : 'this week'}. Open any race to make one.
          </div>
        ) : board.board.map((row) => {
          const isMe = me && row.name === me.display_name;
          return (
            <div key={`${row.rank}-${row.name}`} style={{
              display: 'grid', gridTemplateColumns: '36px 1fr auto auto', gap: 10, alignItems: 'center',
              padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)',
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
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', minWidth: 44, textAlign: 'right' }}>
                {row.points}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
