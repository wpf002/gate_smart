import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getMyContestPicks, getRacesToday, getRacesByDate } from '../../utils/api';
import { formatRaceTime } from '../../utils/timezone';
import { useAppStore } from '../../store';

/**
 * Today's calls, on the contest page. Before this the only trace of a pick was
 * on the race page you made it from, so locking one in and then opening the
 * contest page looked like nothing had happened.
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
  const { data: today } = useQuery({ queryKey: ['races', 'usa', 'today'], queryFn: () => getRacesToday('usa') });
  const { data: tomorrow } = useQuery({ queryKey: ['races', 'usa', 'tomorrow'], queryFn: () => getRacesByDate('tomorrow', 'usa') });

  // Today only. The endpoint also returns ungraded calls on later cards so
  // NextToPost can still exclude a race you've already called, but this list is
  // the day's scoreboard and shouldn't carry tomorrow's picks into it.
  const dayKey = data?.date;
  const picks = (data?.picks || []).filter((p) => !dayKey || !p.race_date || p.race_date === dayKey);
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
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>TODAY'S CALLS</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {open ? `${open} still open · change until the gate` : 'All locked'}
        </span>
      </div>
      {rows.map((r, i) => {
        // The finish is only worth a line when the bet missed — on a winner
        // "Won: #1 Apicturesworth" just repeats the selection above it. When it
        // is shown it replaces the track line, which by then adds nothing but
        // the bet type already in the title.
        const showResult = r.settled && r.correct === false && r.finish?.length > 0;
        return (
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
            {r.off && (
              <span style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                {formatRaceTime(new Date(r.off).toISOString(), timezone).time}
              </span>
            )}
            <span style={{ display: 'block', fontSize: 11, color: r.open ? 'var(--accent-gold-bright)' : 'var(--text-muted)' }}>
              {r.open ? 'Open' : r.settled ? 'Graded' : 'Running'}
            </span>
          </span>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {describeBet(r)}
            </span>
            {!showResult && (
              <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {r.bet_label || 'Win'} · {r.course}{r.number ? ` Race ${r.number}` : ''}
              </span>
            )}
            {showResult && (
              <span style={{ display: 'block', fontSize: 11, marginTop: 3, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span style={{ color: 'var(--accent-gold-bright)' }}>
                  Won: {r.finish[0].number ? `#${r.finish[0].number} ` : ''}{r.finish[0].name}
                </span>
                {r.finish.length > 1 && (
                  <span> · then {r.finish.slice(1, 3).map((f) => (f.number ? `#${f.number}` : f.name)).join(', ')}</span>
                )}
                {r.result_note && <span> — {r.result_note}</span>}
              </span>
            )}
          </span>
          <Outcome pick={r} />
        </button>
        );
      })}
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
