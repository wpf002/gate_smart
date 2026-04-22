import { useQuery } from '@tanstack/react-query';
import { getSecretariatAccuracy, getTrackStats } from '../../utils/api';

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
  if (noData) return null;

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
      {data?.sample_size_note && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
          {data.sample_size_note}
        </div>
      )}
    </div>
  );
}

// ── Global accuracy badge (no trackCode — used on ProfilePage) ────────────────
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

  const { win_rate_percent, total_predictions } = data;

  const trend =
    win_rate_percent >= 35
      ? { icon: '↑', color: 'var(--accent-green-bright)' }
      : win_rate_percent >= 25
      ? { icon: '→', color: 'var(--accent-gold-bright)' }
      : { icon: '↓', color: 'var(--accent-red-bright)' };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '8px 14px',
      background: 'var(--bg-card)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      marginBottom: 16,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        background: 'var(--accent-gold)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-display)', fontSize: 16, color: '#000', flexShrink: 0,
      }}>
        S
      </div>
      <div style={{ flex: 1 }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 11,
          color: 'var(--accent-gold)', letterSpacing: '0.06em',
          display: 'block', lineHeight: 1.2,
        }}>
          SECRETARIAT
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.3 }}>
          {win_rate_percent}% top pick win rate
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {total_predictions} races called
        </div>
      </div>
      <div style={{ fontSize: 20, color: trend.color, fontWeight: 700, lineHeight: 1, flexShrink: 0 }}>
        {trend.icon}
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
