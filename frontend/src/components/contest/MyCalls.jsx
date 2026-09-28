import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getMyContestPicks, getRacesToday, getRacesByDate } from '../../utils/api';
import { formatRaceTime } from '../../utils/timezone';
import { useAppStore } from '../../store';

/**
 * The calls you've already made: today's, plus anything locked in on a later
 * card that hasn't run. Before this the only trace of a pick was on the race
 * page you made it from, so locking one in and then opening the contest page
 * looked like nothing had happened.
 *
 * Track names come from the race cards the page already has in cache. When a
 * card isn't loaded the race_id still carries the track code and race number,
 * so the row degrades to "LAD · Race 7" rather than disappearing.
 */

const money = (n) => `${n >= 0 ? '+' : '−'}$${Math.abs(Number(n || 0)).toFixed(2)}`;

function describeBet(pick) {
  const picks = (pick.selections || []).filter((s) => s && (s.name || s.number));
  if (picks.length > 1) {
    return `${pick.bet_label || 'Exacta'} ${picks.map((s) => s.number || '?').join('-')}`;
  }
  const name = picks[0]?.name || pick.horse_name;
  const type = (pick.bet_type || 'win').toLowerCase();
  return type === 'win' ? name : `${name} to ${type}`;
}

/** Track code and race number, read straight off "LAD_1790553600000-7". */
function fromRaceId(raceId) {
  const [meet, number] = String(raceId || '').split('-');
  return { code: (meet || '').split('_')[0] || '', number: number || '' };
}

export default function MyCalls({ now = Date.now() }) {
  const navigate = useNavigate();
  const authToken = useAppStore((s) => s.authToken);
  const timezone = useAppStore((s) => s.userProfile?.timezone);

  const { data } = useQuery({
    queryKey: ['contest-picks', ''],
    queryFn: () => getMyContestPicks(),
    enabled: !!authToken,
    // A call settles minutes after the race, so keep this fresh while it's open.
    refetchInterval: 60000,
  });

  // Same query keys as the Races page and NextToPost, so this reuses their cache.
  const { data: today } = useQuery({ queryKey: ['races', 'today'], queryFn: () => getRacesToday('usa') });
  const { data: tomorrow } = useQuery({ queryKey: ['races', 'tomorrow'], queryFn: () => getRacesByDate('tomorrow', 'usa') });

  const picks = data?.picks || [];
  if (!authToken || !picks.length) return null;

  const cards = {};
  for (const r of [...(today?.racecards || []), ...(tomorrow?.racecards || [])]) cards[r.race_id] = r;

  const rows = picks.map((p) => {
    const card = cards[p.race_id];
    const { code, number } = fromRaceId(p.race_id);
    const off = card?.off_dt ? new Date(card.off_dt).getTime() : null;
    return {
      ...p,
      course: card?.course || code,
      number: card ? String(card.race_id).split('-').pop() : number,
      off,
      open: off !== null && off > now && !p.settled,
    };
  }).sort((a, b) => (a.off ?? Infinity) - (b.off ?? Infinity));

  const open = rows.filter((r) => r.open).length;

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '12px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>YOUR CALLS</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {open ? `${open} still open · change until the gate` : 'All locked'}
        </span>
      </div>
      {rows.map((r, i) => (
        <button
          key={r.race_id}
          onClick={() => navigate(`/race/${r.race_id}`)}
          style={{
            display: 'grid', gridTemplateColumns: '92px minmax(0, 1fr) auto', gap: 12, alignItems: 'center',
            width: '100%', padding: '10px 14px', background: 'none', border: 'none', cursor: 'pointer',
            textAlign: 'left', borderTop: i ? '1px solid var(--border-subtle)' : 'none',
          }}
        >
          <span>
            <span style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              {r.off ? formatRaceTime(new Date(r.off).toISOString(), timezone).time : '—'}
            </span>
            <span style={{ display: 'block', fontSize: 11, color: r.open ? 'var(--accent-gold-bright)' : 'var(--text-muted)' }}>
              {r.open ? 'Open' : r.settled ? 'Graded' : 'Running'}
            </span>
          </span>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {describeBet(r)}
            </span>
            <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {r.bet_label || 'Win'} · {r.course}{r.number ? ` Race ${r.number}` : ''}
            </span>
          </span>
          <Outcome pick={r} />
        </button>
      ))}
    </div>
  );
}

function Outcome({ pick }) {
  if (!pick.settled) {
    return <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-gold)' }}>{pick.open ? 'Change →' : 'View →'}</span>;
  }
  // correct === null means the chart could never price the bet, so it scored
  // nothing either way — say that rather than showing it as a loss.
  if (pick.correct === null) {
    return <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>No price</span>;
  }
  const tone = pick.correct ? 'var(--accent-green-bright)' : 'var(--text-muted)';
  return (
    <span style={{ textAlign: 'right' }}>
      <span style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: tone }}>
        +{pick.points}
      </span>
      {pick.net !== null && pick.net !== undefined && (
        <span style={{
          display: 'block', fontFamily: 'var(--font-mono)', fontSize: 11,
          color: pick.net >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)',
        }}>
          {money(pick.net)}
        </span>
      )}
    </span>
  );
}
