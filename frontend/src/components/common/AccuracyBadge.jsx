import { useQuery } from '@tanstack/react-query';
import { getSecretariatAccuracy } from '../../utils/api';

export default function AccuracyBadge() {
  const { data } = useQuery({
    queryKey: ['secretariat-accuracy'],
    queryFn: getSecretariatAccuracy,
    refetchInterval: 10 * 60 * 1000, // 10 minutes
    staleTime: 5 * 60 * 1000,
  });

  // Only show after meaningful sample size
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
      {/* S avatar */}
      <div style={{
        width: 28,
        height: 28,
        borderRadius: '50%',
        background: 'var(--accent-gold)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--font-display)',
        fontSize: 16,
        color: '#000',
        flexShrink: 0,
      }}>
        S
      </div>

      {/* Stats */}
      <div style={{ flex: 1 }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 11,
          color: 'var(--accent-gold)',
          letterSpacing: '0.06em',
          display: 'block',
          lineHeight: 1.2,
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

      {/* Trend indicator */}
      <div style={{
        fontSize: 20,
        color: trend.color,
        fontWeight: 700,
        lineHeight: 1,
        flexShrink: 0,
      }}>
        {trend.icon}
      </div>
    </div>
  );
}
