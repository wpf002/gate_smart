import { useNavigate } from 'react-router-dom';
import { formatPurse as formatPurseUtil } from '../../utils/currency';
import { formatRaceTime, TIMEZONE_OPTIONS } from '../../utils/timezone';
import { useAppStore } from '../../store';

/**
 * For US/CAN races, derive the display time from off_dt using the user's
 * preferred timezone (defaults to Eastern).
 * For all other races, use the time field (local track time from the API).
 * Returns { time: string, label: string|null }
 */
export function getDisplayTime(race, timezone = 'America/New_York') {
  if (['USA', 'CAN'].includes((race.region || '').toUpperCase()) && race.off_dt) {
    const { time, abbr } = formatRaceTime(race.off_dt, timezone);
    const opt = TIMEZONE_OPTIONS.find((o) => o.value === timezone);
    return { time, label: abbr ?? opt?.abbr ?? 'ET' };
  }
  return { time: race.time || race.off_time || '', label: null };
}

/**
 * Display prize/purse with correct currency symbol for the race's region.
 * Delegates to currency.js which handles USA/CAN/GB/IRE/AUS/FRA.
 */
export function formatPurse(race) {
  const raw = race.prize || race.purse;
  if (raw == null || raw === '') return null;
  return formatPurseUtil(raw, race.region) || null;
}

/**
 * Determine whether a race is definitively finished.
 *
 * Rules:
 * 1. Return true only when the API status field explicitly says "result",
 *    "resulted", "finished", "complete", "official", or "void".
 * 2. OR when off_dt (timezone-aware ISO string) is more than 10 minutes in
 *    the past.  The 10-minute buffer allows results to be processed.
 * 3. Never mark a race as finished from the scheduled post_time string alone —
 *    that is local track time with no timezone and will produce wrong results
 *    for NA races compared against the user's clock.
 */
export function isRaceDefinitelyFinished(race) {
  const finishedStatuses = ['result', 'resulted', 'finished', 'complete', 'official', 'void'];
  if (race.status && finishedStatuses.includes(race.status.toLowerCase())) {
    return true;
  }
  if (race.off_dt) {
    const offTime = new Date(race.off_dt);
    if (!isNaN(offTime.getTime())) {
      return (Date.now() - offTime.getTime()) > 10 * 60 * 1000;
    }
  }
  return false;
}

/** Alias kept for any callers that haven't migrated yet. */
export const isRacePast = isRaceDefinitelyFinished;

/**
 * Format distance as decimal miles / remainder furlongs.
 * e.g. distanceF=9  (1m1f) → "1.125m / 1f"
 *      distanceF=11 (1m3f) → "1.375m / 3f"
 *      distanceF=8  (1m)   → "1m"
 *      distanceF=7  (7f)   → "7f"  (sub-mile shown in furlongs only)
 */
export function formatDistance(dist, distanceF, region) {
  // US races: show the raw description (e.g. "5 1/2 Furlongs", "1 1/16 Miles")
  if (['USA', 'CAN'].includes((region || '').toUpperCase())) {
    return dist || (distanceF != null ? `${distanceF}f` : '');
  }

  const totalF = distanceF != null ? parseFloat(distanceF) : null;
  if (!totalF && !dist) return '';
  if (!totalF) return dist || '';

  const wholeMiles = Math.floor(totalF / 8);
  const remainderF = Math.round((totalF - wholeMiles * 8) * 10) / 10;

  if (wholeMiles === 0) return `${remainderF}f`;
  if (remainderF === 0) return `${wholeMiles}m`;
  return `${wholeMiles}m / ${remainderF}f`;
}

export function RaceCardSkeleton() {
  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <div className="skeleton" style={{ height: 16, width: '40%', borderRadius: 4 }} />
        <div className="skeleton" style={{ height: 16, width: '25%', borderRadius: 4 }} />
      </div>
      <div className="skeleton" style={{ height: 13, width: '60%', borderRadius: 4, marginBottom: 10 }} />
      <div style={{ display: 'flex', gap: 8 }}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 24, width: 60, borderRadius: 12 }} />
        ))}
      </div>
    </div>
  );
}

export function RaceCard({ race, isTomorrow = false }) {
  const navigate = useNavigate();
  const timezone = useAppStore((s) => s.userProfile?.timezone);
  const past = !isTomorrow && isRacePast(race);
  const { time: displayTime, label: timeLabel } = getDisplayTime(race, timezone);
  const runnersCount = race.runners?.length ?? race.no_of_runners;

  return (
    <div
      className="card"
      onClick={() => navigate(`/race/${race.race_id}`)}
      style={{
        marginBottom: 10,
        cursor: 'pointer',
        opacity: past ? 0.6 : 1,
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg-card)'; }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 18,
          color: past ? 'var(--text-muted)' : 'var(--accent-gold)',
          letterSpacing: '0.04em',
        }}>
          {displayTime}
          {timeLabel && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-body)', color: 'var(--text-muted)', marginLeft: 4 }}>
              {timeLabel}
            </span>
          )}
          {' · '}{race.course}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {past && (
            <span className="badge badge-muted">Finished</span>
          )}
          {race.going && (
            <span className="badge badge-muted">{race.going}</span>
          )}
        </div>
      </div>

      {/* Race title */}
      <div style={{
        fontSize: 13,
        color: 'var(--text-secondary)',
        marginBottom: 10,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {race.title || race.race_name}
      </div>

      {/* Meta chips */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {(race.distance || race.distance_f) && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            📏 {formatDistance(race.distance, race.distance_f, race.region)}
          </span>
        )}
        {race.surface && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🌿 {race.surface}</span>
        )}
        {runnersCount && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🏇 {runnersCount} runners</span>
        )}
        {formatPurse(race) && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>💰 {formatPurse(race)}</span>
        )}
        {!past && (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--accent-gold-dim)', fontWeight: 600 }}>
            Analyze →
          </span>
        )}
      </div>
    </div>
  );
}
