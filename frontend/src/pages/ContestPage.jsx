import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getContestProgress, getLeaderboard } from '../utils/api';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import NameEditor from '../components/contest/NameEditor';
import NextToPost from '../components/contest/NextToPost';
import FirstPick, { isDefaultName } from '../components/contest/FirstPick';

function Stat({ value, label, highlight = false }) {
  return (
    <div className="contest-stat">
      <div className="contest-stat-value" style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: highlight ? 'var(--accent-gold-bright)' : 'var(--text-primary)' }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
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

      <div className="contest-body">
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
          10 points for the winner, +5 more when Secretariat is wrong. No betting, no money.
        </div>

        <div className="contest-grid">
          {/* ── You ─────────────────────────────────────────── */}
          {authToken ? (
            <div className="contest-you" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-subtle)', minHeight: 44 }}>
                {me && (isDefaultName(me.display_name) ? (
                  <NameEditor
                    current={me.display_name}
                    renderIdle={(edit) => (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Choose the name other players see</span>
                        <button className="btn btn-ghost" style={{ fontSize: 12, padding: '5px 12px', flexShrink: 0 }} onClick={edit}>
                          Set Your Name
                        </button>
                      </div>
                    )}
                  />
                ) : (
                  <NameEditor current={me.display_name} />
                ))}
              </div>
              {me && !me.total_picks ? <FirstPick /> : (
              <div className="contest-stats">
                <Stat value={me ? me.points : '–'} label="Points" highlight />
                <Stat value={me ? me.pick_day_streak : '–'} label="Day Streak" />
                <Stat value={me ? me.beat_secretariat_streak : '–'} label="Beat Streak" />
                <Stat value={me ? `${me.wins}/${me.settled}` : '–'} label="Winners" />
                <Stat value={me ? me.beat_secretariat : '–'} label="Beat Secretariat" />
                <Stat value={me ? me.best_correct_streak : '–'} label="Best Streak" />
              </div>
              )}
            </div>
          ) : (
            <div style={{ padding: 14, background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sign in to make picks and track your streaks.</span>
              {!authToken && (
                <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 12px', flexShrink: 0 }} onClick={() => navigate('/login')}>Sign In</button>
              )}
            </div>
          )}

          <div className="contest-main">
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

          {/* ── Races still open for a pick ─────────────────── */}
          <NextToPost />
          </div>
        </div>
      </div>
    </div>
  );
}
