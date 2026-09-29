import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getRacesToday, getRacesByDate, getMyContestPicks } from '../../utils/api';
import { formatRaceTime } from '../../utils/timezone';
import { useAppStore } from '../../store';

const LIMIT = 10;

const openRaces = (cards, now) => (cards || [])
  .filter((r) => !r.is_cancelled && !r.has_results && r.off_dt && new Date(r.off_dt).getTime() > now)
  .sort((a, b) => new Date(a.off_dt) - new Date(b.off_dt));

/**
 * Races still open for a Beat Secretariat pick, soonest first.
 *
 * Today's card first, then tomorrow's to fill out the list. Late in the evening
 * only a handful of races are left, and the page used to just end there with
 * half a screen of nothing under it — tomorrow's card is both the honest filler
 * and the thing you'd want next anyway, since picks lock at the gate.
 * The hook is unfiltered; the component below drops the ones already called.
 */
export function useOpenRaces(now = Date.now()) {
  // Same query keys as the Races page, so this reuses its cache.
  const { data: today } = useQuery({ queryKey: ['races', 'today'], queryFn: () => getRacesToday('usa') });
  const todayOpen = openRaces(today?.racecards, now);
  const { data: tomorrow } = useQuery({
    queryKey: ['races', 'tomorrow'],
    queryFn: () => getRacesByDate('tomorrow', 'usa'),
    enabled: !!today && todayOpen.length < LIMIT,
  });
  const tomorrowOpen = todayOpen.length < LIMIT ? openRaces(tomorrow?.racecards, now) : [];
  return {
    races: [
      ...todayOpen.map((r) => ({ ...r, tomorrow: false })),
      ...tomorrowOpen.map((r) => ({ ...r, tomorrow: true })),
    ],
    showingTomorrow: todayOpen.length === 0 && tomorrowOpen.length > 0,
  };
}

export default function NextToPost({ now = Date.now() }) {
  const navigate = useNavigate();
  const timezone = useAppStore((s) => s.userProfile?.timezone);
  const authToken = useAppStore((s) => s.authToken);
  const { races: open } = useOpenRaces(now);

  // Races already called live in "Your calls" above, where they can still be
  // changed. Listing them here too made the two lists read as contradictions.
  const { data: mine } = useQuery({
    queryKey: ['contest-picks', ''],
    queryFn: () => getMyContestPicks(),
    enabled: !!authToken,
  });
  const called = new Set((mine?.picks || []).map((p) => p.race_id));

  const races = open.filter((r) => !called.has(r.race_id)).slice(0, LIMIT);
  if (!races.length) return null;

  return (
    <div className="next-to-post" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '12px 14px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>NEXT TO POST</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Pick before the gate opens</span>
      </div>
      <div className="next-to-post-list">
      {races.map((race, i) => {
        const { time, abbr } = formatRaceTime(race.off_dt, timezone);
        const minutes = Math.round((new Date(race.off_dt).getTime() - now) / 60000);
        const raceNumber = String(race.race_id).split('-').pop();
        return (
          <button key={race.race_id} onClick={() => navigate(`/race/${race.race_id}`)} style={{
            display: 'grid', gridTemplateColumns: '92px minmax(0, 1fr) auto', gap: 12, alignItems: 'center',
            width: '100%', padding: '10px 14px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
            borderTop: i ? '1px solid var(--border-subtle)' : 'none',
          }}>
            <span>
              <span style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                {time}{abbr && <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4 }}>{abbr}</span>}
              </span>
              {race.tomorrow ? (
                <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)' }}>Tomorrow</span>
              ) : minutes < 60 && (
                <span style={{ display: 'block', fontSize: 11, color: 'var(--accent-gold-bright)' }}>in {Math.max(minutes, 1)} min</span>
              )}
            </span>
            <span style={{ minWidth: 0 }}>
              <span style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {race.course}
              </span>
              <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)' }}>
                Race {raceNumber}{race.field_size ? ` · ${race.field_size} runners` : ''}
              </span>
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-gold)' }}>Pick →</span>
          </button>
        );
      })}
      </div>
    </div>
  );
}
