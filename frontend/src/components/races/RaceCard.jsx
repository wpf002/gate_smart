import { useNavigate } from 'react-router-dom';

/**
 * For US races, derive the display time from off_dt in Eastern Time.
 * For all other races, use the time field (local track time from the API).
 * Returns { time: string, label: string|null }
 */
export function getDisplayTime(race) {
  if (race.region === 'USA' && race.off_dt) {
    const t = new Date(race.off_dt).toLocaleTimeString('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
    return { time: t, label: 'ET' };
  }
  return { time: race.time || race.off_time || '', label: null };
}

/**
 * Display prize/purse with correct currency symbol.
 * The API always returns £ — for US/CAN races swap to $.
 */
export function formatPurse(race) {
  const raw = race.prize || race.purse;
  if (!raw) return null;
  const isNorthAmerica = ['USA', 'CAN'].includes((race.region || '').toUpperCase());
  return isNorthAmerica ? raw.replace(/£/g, '$') : raw;
}

/**
 * Use off_dt (ISO 8601 with timezone, e.g. "2026-04-04T14:30:00+01:00") when
 * available — it is timezone-correct regardless of where the race is held.
 * Fallback: compare HH:MM against current UK time (BST/GMT offset applied).
 */
export function isRacePast(race) {
  if (race.off_dt) {
    return Date.now() > new Date(race.off_dt).getTime() + 5 * 60 * 1000;
  }
  // Fallback for races without off_dt
  const timeStr = race.time || race.off_time;
  if (!timeStr) return false;
  const match = timeStr.match(/^(\d{1,2}):(\d{2})/);
  if (!match) return false;
  const now = new Date();
  const ukOffset = now.getUTCMonth() >= 2 && now.getUTCMonth() <= 9 ? 60 : 0;
  const ukNow = now.getUTCHours() * 60 + now.getUTCMinutes() + ukOffset;
  const raceMin = parseInt(match[1]) * 60 + parseInt(match[2]);
  return ukNow > raceMin + 5;
}

/**
 * Format distance as decimal miles / remainder furlongs.
 * e.g. distanceF=9  (1m1f) → "1.125m / 1f"
 *      distanceF=11 (1m3f) → "1.375m / 3f"
 *      distanceF=8  (1m)   → "1m"
 *      distanceF=7  (7f)   → "7f"  (sub-mile shown in furlongs only)
 */
export function formatDistance(dist, distanceF) {
  const totalF = distanceF ? parseFloat(distanceF) : null;
  if (!totalF && !dist) return '';
  if (!totalF) return dist || '';

  const wholeMiles = Math.floor(totalF / 8);
  const remainderF = totalF % 8;

  if (wholeMiles === 0) {
    return `${totalF}f`;
  }

  const decimalMiles = totalF / 8;
  const milesStr = Number.isInteger(decimalMiles) ? `${decimalMiles}m` : `${decimalMiles}m`;

  if (remainderF === 0) return milesStr;

  const remStr = `${Number.isInteger(remainderF) ? remainderF : remainderF}f`;
  return `${milesStr} / ${remStr}`;
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
  const past = !isTomorrow && isRacePast(race);
  const { time: displayTime, label: timeLabel } = getDisplayTime(race);
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
            📏 {formatDistance(race.distance, race.distance_f)}
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
