import { useQuery } from '@tanstack/react-query';
import { getSecretariatAccuracy, getTrackStats, getMorningLine } from '../../utils/api';

// ── Track-specific badge ──────────────────────────────────────────────────────
function TrackAccuracyBadge({ trackCode, trackName, compact }) {
  const { data, isLoading } = useQuery({
    queryKey: ['track-stats', trackCode],
    queryFn: () => getTrackStats(trackCode),
    staleTime: 5 * 60 * 1000,
    retry: false,
    enabled: !!trackCode,
  });

  if (isLoading) return null;

  const noData = !data || data.itm_rate == null;
  const displayName = trackName || data?.track_code || trackCode;

  if (compact) {
    if (noData) return null;
    const itm = Math.round((data.itm_rate || 0) * 100);
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '3px 8px', borderRadius: 12,
        background: 'rgba(201,162,39,0.1)',
        border: '1px solid rgba(201,162,39,0.3)',
        fontSize: 11, color: 'var(--accent-gold)',
      }}>
        📊 {itm}% ITM at {displayName}
      </span>
    );
  }

  if (noData) {
    return (
      <div className="accuracy-no-data" style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
        <span className="accuracy-no-data-title" style={{ fontFamily: 'var(--font-display)', fontSize: 10, color: 'var(--accent-gold)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          SECRETARIAT AT {(displayName || '').toUpperCase()}
        </span>
        <span className="accuracy-no-data-body" style={{ fontSize: 11, color: 'var(--text-muted)' }}>No predictions recorded here yet — stats appear after races are analyzed and results posted</span>
      </div>
    );
  }

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: '12px 14px',
      marginBottom: 12,
    }}>
      <div style={{
        fontFamily: 'var(--font-display)', fontSize: 11,
        color: 'var(--accent-gold)', letterSpacing: '0.08em',
        marginBottom: 4,
      }}>
        SECRETARIAT AT {(displayName || '').toUpperCase()}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, color: 'var(--accent-gold)' }}>
          {Math.round((data.itm_rate || 0) * 100)}% ITM
        </span>
        <span style={{ fontSize: 14, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
          · {Math.round((data.win_rate || 0) * 100)}% Win
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          · {data.total_predictions} races
        </span>
      </div>
    </div>
  );
}

// ── Morning Line badge — pre-race top-4 picks (N-N-N-N) ───────────────────────
export function MorningLineBadge({ raceId }) {
  const { data, isLoading } = useQuery({
    queryKey: ['morning-line', raceId],
    queryFn: () => getMorningLine(raceId),
    staleTime: 5 * 60 * 1000,
    retry: false,
    enabled: !!raceId,
  });

  if (isLoading || !data || !data.available || !data.picks) return null;

  const formatted = data.picks.map((p) => p ?? '?').join('-');

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: '12px 14px',
      marginBottom: 12,
    }}>
      <div style={{
        fontFamily: 'var(--font-display)', fontSize: 11,
        color: 'var(--accent-gold)', letterSpacing: '0.08em',
        marginBottom: 4,
      }}>
        SECRETARIAT'S MORNING LINE
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700,
        color: 'var(--accent-gold)', letterSpacing: '0.04em',
      }}>
        {formatted}
      </div>
    </div>
  );
}

// ── Global accuracy strip — 4 stats horizontally (Win / Place / Show / ITM) ──
function GlobalAccuracyBadge() {
  const { data } = useQuery({
    queryKey: ['secretariat-accuracy'],
    queryFn: getSecretariatAccuracy,
    refetchInterval: 10 * 60 * 1000,
    staleTime: 5 * 60 * 1000,
  });

  if (!data || data.total_predictions < 10 || data.win_rate_percent == null) {
    return null;
  }

  const stats = [
    { label: 'W',   value: data.win_rate_percent },
    { label: 'P',   value: data.place_rate_percent },
    { label: 'S',   value: data.show_rate_percent },
    { label: 'ITM', value: data.itm_rate_percent },
  ];

  const Stat = ({ label, value }) => (
    <div style={{ display: 'inline-flex', alignItems: 'baseline', gap: 3 }}>
      <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
        {value == null ? '—' : `${value}%`}
      </span>
    </div>
  );

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 10px',
      background: 'var(--bg-card)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
    }}>
      <div style={{
        width: 24, height: 24, borderRadius: '50%',
        background: 'var(--accent-gold)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-display)', fontSize: 14, color: '#000', flexShrink: 0,
      }}>
        S
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 9,
          color: 'var(--accent-gold)', letterSpacing: '0.06em',
          lineHeight: 1.2,
        }}>
          SECRETARIAT · LAST {data.total_predictions}
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.3, display: 'flex', gap: 10 }}>
          {stats.map(s => <Stat key={s.label} {...s} />)}
        </div>
      </div>
    </div>
  );
}

// ── Default export: routes to the right badge based on props ─────────────────
export default function AccuracyBadge({ trackCode, trackName, compact = false } = {}) {
  if (trackCode) {
    return <TrackAccuracyBadge trackCode={trackCode} trackName={trackName} compact={compact} />;
  }
  return <GlobalAccuracyBadge />;
}
