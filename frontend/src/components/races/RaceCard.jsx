import { useNavigate } from 'react-router-dom';
import { formatPurse as formatPurseUtil } from '../../utils/currency';
import { formatRaceTime, TIMEZONE_OPTIONS } from '../../utils/timezone';
import { useAppStore } from '../../store';

/**
 * For US/CAN races: convert off_dt to the user's preferred timezone.
 * For all other races: show local track time, and if off_dt is available
 * also compute the US equivalent so the user knows when to watch.
 * Returns { time, label, usTime, usLabel }
 */
export function getDisplayTime(race, timezone = 'local') {
  const useLocal = !timezone || timezone === 'local';
  const lookupTz = useLocal
    ? (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { return null; } })()
    : timezone;
  const opt = TIMEZONE_OPTIONS.find((o) => o.value === lookupTz);
  const usLabel = opt?.abbr ?? 'ET';

  if (['USA', 'CAN'].includes((race.region || '').toUpperCase()) && race.off_dt) {
    const { time, abbr } = formatRaceTime(race.off_dt, timezone);
    return { time, label: abbr ?? usLabel, usTime: null, usLabel: null };
  }

  const localTime = race.time || race.off_time || '';
  if (race.off_dt) {
    const { time: usTime } = formatRaceTime(race.off_dt, timezone);
    return { time: localTime, label: null, usTime, usLabel };
  }
  return { time: localTime, label: null, usTime: null, usLabel: null };
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
 * 2. OR when off_dt (timezone-aware ISO string) is more than 5 minutes in
 *    the past.  The buffer gives upstream a head start before we begin
 *    polling for results; backend already 404s gracefully if results
 *    aren't ready.
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
      return (Date.now() - offTime.getTime()) > 5 * 60 * 1000;
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
  const experienceLevel = useAppStore((s) => s.userProfile?.experienceLevel);
  const past = !isTomorrow && isRacePast(race);
  const { time: displayTime, label: timeLabel, usTime, usLabel } = getDisplayTime(race, timezone);
  const runnersCount = race.runners?.length ?? race.no_of_runners;
  const isBeginner = experienceLevel === 'beginner';
  const isAdvanced = !isBeginner;

  return (
    <div
      className="card"
      onClick={() => navigate(`/race/${race.race_id}`)}
      style={{
        marginBottom: 10,
        cursor: 'pointer',
        opacity: past ? 0.6 : 1,
        transition: 'background 0.15s',
        minHeight: 60,
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-card-hover)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,0,0,0.35)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg-card)'; e.currentTarget.style.boxShadow = 'none'; }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 18,
          color: past ? 'var(--text-muted)' : 'var(--accent-gold)',
          letterSpacing: '0.04em',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          minWidth: 0,
          flex: 1,
          marginRight: 8,
        }}>
          {displayTime}
          {timeLabel && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-body)', color: 'var(--text-muted)', marginLeft: 4 }}>
              {timeLabel}
            </span>
          )}
          {usTime && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-body)', color: 'var(--text-muted)', marginLeft: 4 }}>
              ({usTime} {usLabel})
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
        marginBottom: isBeginner ? 0 : 10,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {race.title || race.race_name}
      </div>

      {/* Meta row — hidden for beginner; standard for intermediate; extended for advanced */}
      {!isBeginner && (() => {
        const sep = <span aria-hidden="true" style={{ color: 'var(--accent-gold-dim)', fontWeight: 300, fontSize: 13, userSelect: 'none' }}>|</span>;
        const items = [
          (race.distance || race.distance_f) ? formatDistance(race.distance, race.distance_f, race.region) : null,
          race.surface || null,
          runnersCount ? `${runnersCount} runners` : null,
          formatPurse(race) || null,
        ].filter(Boolean);

        // Advanced: append race class/type details
        const fmtClass = (cls) => {
          if (!cls) return null;
          // Title-case all words, then fix parenthetical amounts
          return cls
            .replace(/\b\w+/g, w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
            .replace(/\(\$?([\d,]+)\)/g, (_, n) => ` ($${parseInt(n.replace(/,/g, ''), 10).toLocaleString()})`);
        };
        const advancedItems = isAdvanced ? [
          fmtClass(race.race_class || race.race_type || race.type) || null,
          race.claiming_price ? `Clm $${Number(race.claiming_price).toLocaleString()}` : null,
        ].filter(Boolean) : [];

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              {items.map((item, i) => (
                <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {i > 0 && sep}
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item}</span>
                </span>
              ))}
              {!past && (
                <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--accent-gold-bright)', fontWeight: 600 }}>
                  Analyze →
                </span>
              )}
            </div>
            {isAdvanced && advancedItems.length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                {advancedItems.map((item, i) => (
                  <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {i > 0 && sep}
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item}</span>
                  </span>
                ))}
                {race.conditions && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
                    {race.conditions}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })()}

      {/* Beginner CTA */}
      {isBeginner && !past && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--accent-gold-bright)', fontWeight: 600 }}>
          Tap to analyze →
        </div>
      )}
    </div>
  );
}
