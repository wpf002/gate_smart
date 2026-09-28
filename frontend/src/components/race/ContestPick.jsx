import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getMyContestPicks, makeContestPick } from '../../utils/api';
import { shareResult } from '../../utils/share';
import { useAppStore as useStore } from '../../store';

/**
 * "Beat Secretariat" — call a race before post. No wagering, no money, no
 * prizes: points, a leaderboard, and a running $2 scoreline so you can see what
 * the calls would have been worth. Points are scaled to how often each bet type
 * actually lands, so a show bet can't out-earn a trifecta.
 */

const BET_TYPES = [
  { key: 'win', label: 'Win', picks: 1, points: 10, how: 'Your horse must finish 1st.' },
  { key: 'place', label: 'Place', picks: 1, points: 7, how: 'Your horse must finish 1st or 2nd.' },
  { key: 'show', label: 'Show', picks: 1, points: 5, how: 'Your horse must finish in the top 3.' },
  { key: 'exacta', label: 'Exacta', picks: 2, points: 25, how: 'First two, in exact order.' },
  { key: 'trifecta', label: 'Trifecta', picks: 3, points: 50, how: 'First three, in exact order.' },
];
const ORDINAL = ['1st', '2nd', '3rd'];
const spec = (key) => BET_TYPES.find((b) => b.key === key) || BET_TYPES[0];

/** How a settled call reads back: a straight bet names the horse, an exotic
 *  names the program numbers, because "3-7" is how you'd have said it aloud. */
function describeBet(pick) {
  const picks = (pick.selections || []).filter((s) => s && (s.name || s.number));
  if (picks.length > 1) {
    return `${pick.bet_label || 'Exacta'} ${picks.map((s) => s.number || '?').join('-')}`;
  }
  const name = picks[0]?.name || pick.horse_name;
  const type = (pick.bet_type || 'win').toLowerCase();
  return type === 'win' ? name : `${name} to ${type}`;
}
const money = (n) => `${n >= 0 ? '+' : '−'}$${Math.abs(Number(n || 0)).toFixed(2)}`;

export default function ContestPick({ raceId, raceDate, runners = [], raceFinished = false, secretariatPick = '' }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const authToken = useStore((s) => s.authToken);
  const [betType, setBetType] = useState('win');
  const [choices, setChoices] = useState(['', '', '']);
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

  // Settled: show the call, how it went, and what $2 on it returned.
  if (mine?.settled) {
    const voided = mine.correct === null;
    const tone = mine.beat_secretariat
      ? 'var(--accent-gold-bright)'
      : mine.correct ? 'var(--accent-green-bright)' : 'var(--text-muted)';
    const called = describeBet(mine);
    const isWin = (mine.bet_type || 'win') === 'win';
    // A win bet reads best as "the horse won"; anything else has to say which
    // bet landed, because finishing 3rd is a winning show bet and a losing win.
    const landed = isWin ? `${mine.horse_name} won.` : `Your ${(mine.bet_label || 'Win').toLowerCase()} landed.`;
    const line = voided
      ? `${called} — no official price, so this one doesn't count.`
      : mine.beat_secretariat
        ? `You beat Secretariat — ${landed}`
        : mine.correct
          ? `${landed}${mine.secretariat_correct ? ' Secretariat got it too.' : ''}`
          : `You had ${called}. ${mine.winner_name} won.`;
    const onShare = async () => {
      const r = await shareResult({
        title: 'GateSmart',
        text: `I beat Secretariat — called the ${(mine.bet_label || 'win').toLowerCase()} on ${mine.horse_name}.`,
      });
      setShareState(r === 'copied' ? 'Copied' : r === 'shared' ? 'Shared' : '');
    };
    return (
      <Shell>
        <span style={{ fontSize: 13, color: tone }}>{line}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {mine.net !== null && mine.net !== undefined && (
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 13,
              color: mine.net >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)',
            }}>
              {money(mine.net)} <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>on $2</span>
            </span>
          )}
          {!voided && <strong style={{ fontFamily: 'var(--font-mono)', color: tone }}>+{mine.points}</strong>}
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
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Your call: <strong>{describeBet(mine)}</strong>
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Grades when the official chart posts
        </span>
      </Shell>
    );
  }

  const needed = spec(betType).picks;
  const picked = choices.slice(0, needed);
  const ready = picked.length === needed && picked.every(Boolean) && new Set(picked).size === needed;

  const setChoice = (i, value) => {
    setChoices((prev) => {
      const next = [...prev];
      next[i] = value;
      return next;
    });
    setError('');
  };

  const changeBetType = (key) => {
    setBetType(key);
    // Keep the horses already chosen — going Win → Exacta shouldn't wipe them.
    setChoices((prev) => prev.map((c, i) => (i < spec(key).picks ? c : '')));
    setError('');
  };

  const submit = async () => {
    if (!ready) return;
    setSaving(true);
    setError('');
    try {
      await makeContestPick(raceId, picked, betType);
      // Prefix match: refreshes this race's day and the contest page's list.
      await queryClient.invalidateQueries({ queryKey: ['contest-picks'] });
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not save your pick');
    } finally {
      setSaving(false);
    }
  };

  const lockedLabel = mine ? describeBet(mine) : '';

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
          {spec(betType).how} {spec(betType).points} points if it lands, +5 if Secretariat is wrong.
          {secretariatPick ? ` Secretariat has ${secretariatPick}.` : ''}
        </div>
      </div>

      <div className="contest-pick-form">
        <div className="bet-type-row" role="group" aria-label="Bet type">
          {BET_TYPES.map((b) => (
            <button
              key={b.key}
              type="button"
              className={`bet-type-btn${b.key === betType ? ' is-active' : ''}`}
              aria-pressed={b.key === betType}
              onClick={() => changeBetType(b.key)}
            >
              {b.label}
            </button>
          ))}
        </div>

        <div className="contest-pick-selects">
          {Array.from({ length: needed }, (_, i) => (
            <select
              key={i}
              value={choices[i] || ''}
              onChange={(e) => setChoice(i, e.target.value)}
              className="form-select"
              aria-label={needed > 1 ? `${ORDINAL[i]} place` : 'Your horse'}
              style={{ flex: 1, minWidth: 0 }}
            >
              <option value="" disabled>
                {needed > 1 ? ORDINAL[i] : 'Choose a horse'}
              </option>
              {active.map((r) => (
                <option key={r.horse_name} value={r.horse_name}>#{r.number} {r.horse_name}</option>
              ))}
            </select>
          ))}
          <button
            className="btn btn-primary"
            style={{ fontSize: 12, padding: '6px 14px', flexShrink: 0 }}
            disabled={saving || !ready}
            onClick={submit}
          >
            {mine ? 'Change' : 'Lock It In'}
          </button>
        </div>
      </div>

      {mine && (
        <span className="contest-pick-note" style={{ fontSize: 12, color: 'var(--accent-green-bright)' }}>
          Locked in: {lockedLabel}
        </span>
      )}
      {picked.length === needed && picked.every(Boolean) && new Set(picked).size !== needed && (
        <span className="contest-pick-note" style={{ fontSize: 12, color: 'var(--accent-red-bright)' }}>
          Each horse can only be used once.
        </span>
      )}
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
