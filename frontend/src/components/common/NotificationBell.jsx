import { useState } from 'react';
import { subscribeToRaceAlerts, unsubscribeFromRaceAlerts } from '../../utils/api';

function getSessionId() {
  try {
    const stored = JSON.parse(localStorage.getItem('gatesmart-v2') || '{}');
    return stored?.state?.sessionId || 'anon';
  } catch {
    return 'anon';
  }
}

function getPlayerId() {
  return new Promise((resolve) => {
    if (!window.OneSignalDeferred) return resolve(null);
    window.OneSignalDeferred.push(async (OneSignal) => {
      resolve(OneSignal?.User?.PushSubscription?.id ?? null);
    });
  });
}

export default function NotificationBell({ raceId, raceName, onSubscribe }) {
  const [subscribed, setSubscribed] = useState(
    () => localStorage.getItem(`sub:${raceId}`) === 'true'
  );
  const [loading, setLoading] = useState(false);

  if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {
    return null;
  }

  const handleClick = async () => {
    setLoading(true);
    try {
      if (!subscribed) {
        if (typeof Notification !== 'undefined' && Notification.permission !== 'granted') {
          await Notification.requestPermission();
        }
        const playerId = await getPlayerId();
        const sessionId = getSessionId();
        await subscribeToRaceAlerts(raceId, sessionId, playerId || sessionId);
        localStorage.setItem(`sub:${raceId}`, 'true');
        setSubscribed(true);
        onSubscribe?.(true);
      } else {
        await unsubscribeFromRaceAlerts(raceId);
        localStorage.removeItem(`sub:${raceId}`);
        setSubscribed(false);
        onSubscribe?.(false);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      title={subscribed ? 'Unsubscribe from value alerts' : 'Subscribe to value alerts'}
      style={{
        background: 'none',
        border: 'none',
        cursor: loading ? 'wait' : 'pointer',
        padding: 6,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill={subscribed ? 'var(--accent-gold)' : 'none'}
        stroke={subscribed ? 'var(--accent-gold)' : 'var(--text-muted)'}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {subscribed && (
        <span style={{
          position: 'absolute',
          top: 4,
          right: 4,
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: 'var(--accent-gold)',
        }} />
      )}
    </button>
  );
}
