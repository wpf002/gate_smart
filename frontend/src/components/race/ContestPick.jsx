import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getMyContestPicks, makeContestPick } from '../../utils/api';
import { shareResult } from '../../utils/share';
import { useAppStore as useStore } from '../../store';

/**
 * "Beat Secretariat" — call the winner before post. No wagering, no money, no
 * prizes: points and a leaderboard only.
 */
export default function ContestPick({ raceId, raceDate, runners = [], raceFinished = false, secretariatPick = '' }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const authToken = useStore((s) => s.authToken);
  const [choice, setChoice] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [shareState, setShareState] = useState('');

  const { data } = useQuery({
    queryKey: ['contest-picks', raceDate],
    queryFn: () => getMyContestPicks(raceDate),
    enabled: !!authToken && !!raceDate,
    refetchInterval: raceFinished ? 60000 : false,
  });
  const mine = data?.picks?.find((p) => p.race_id === raceId);

  const active = runners.filter((r) => !r.scratched);

  if (!authToken) {
    if (raceFinished) return null;
    return (
      <Shell>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Think you can beat Secretariat?</span>
        <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px' }} onClick={() => navigate('/login')}>
          Sign In To Play
        </button>
      </Shell>
    );
  }

  // Settled: show the call and how it went.
  if (mine?.settled) {
    const tone = mine.beat_secretariat ? 'var(--accent-gold-bright)' : mine.correct ? 'var(--accent-green-bright)' : 'var(--text-muted)';
    const line = mine.beat_secretariat
      ? `You beat Secretariat — ${mine.horse_name} won.`
      : mine.correct
        ? `${mine.horse_name} won. Secretariat got it too.`
        : `You had ${mine.horse_name}. ${mine.winner_name} won.`;
    const onShare = async () => {
      const r = await shareResult({ title: 'GateSmart', text: `I beat Secretariat — called ${mine.horse_name} to win.` });
      setShareState(r === 'copied' ? 'Copied' : r === 'shared' ? 'Shared' : '');
    };
    return (
      <Shell>
        <span style={{ fontSize: 13, color: tone }}>{line}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <strong style={{ fontFamily: 'var(--font-mono)', color: tone }}>+{mine.points}</strong>
          {mine.beat_secretariat && (
            <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={onShare}>
              {shareState || 'Share'}
            </button>
          )}
        </span>
      </Shell>
    );
  }

  // Race is off but not graded yet.
  if (raceFinished) {
    if (!mine) return null;
    return (
      <Shell>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Your call: <strong>{mine.horse_name}</strong></span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Waiting on the result</span>
      </Shell>
    );
  }

  const submit = async () => {
    const runner = active.find((r) => r.horse_name === choice);
    if (!runner) return;
    setSaving(true);
    setError('');
    try {
      await makeContestPick(raceId, runner.horse_name, runner.number || '');
      await queryClient.invalidateQueries({ queryKey: ['contest-picks', raceDate] });
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not save your pick');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="contest-pick" style={{
      marginBottom: 16, padding: '12px 14px', background: 'var(--bg-card)',
      border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)',
    }}>
      <div className="contest-pick-intro">
        <div className="contest-pick-title">
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>
            BEAT SECRETARIAT
          </span>
          <button onClick={() => navigate('/contest')} style={{ background: 'none', border: 'none', padding: 0, color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer' }}>
            Leaderboard →
          </button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          Pick the winner. 10 points if you're right, +5 if Secretariat is wrong.
          {secretariatPick ? ` Secretariat has ${secretariatPick}.` : ''}
        </div>
      </div>
      <div className="contest-pick-form">
        <select
          value={choice || mine?.horse_name || ''}
          onChange={(e) => setChoice(e.target.value)}
          className="form-select"
          style={{ flex: 1, minWidth: 0 }}
        >
          <option value="" disabled>Choose a horse</option>
          {active.map((r) => (
            <option key={r.horse_name} value={r.horse_name}>#{r.number} {r.horse_name}</option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          style={{ fontSize: 12, padding: '6px 14px', flexShrink: 0 }}
          disabled={saving || !choice || choice === mine?.horse_name}
          onClick={submit}
        >
          {mine ? 'Change' : 'Lock It In'}
        </button>
      </div>
      {mine && !choice && <span className="contest-pick-note" style={{ fontSize: 12, color: 'var(--accent-green-bright)' }}>Locked in: {mine.horse_name}</span>}
      {error && <span className="contest-pick-note" style={{ fontSize: 12, color: 'var(--accent-red-bright)' }}>{error}</span>}
    </div>
  );
}

function Shell({ children }) {
  return (
    <div style={{
      marginBottom: 16, padding: '12px 14px', background: 'var(--bg-card)',
      border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)',
      display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center',
    }}>
      {children}
    </div>
  );
}
