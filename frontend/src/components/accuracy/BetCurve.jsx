import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBetCurve } from '../../utils/api';

const W = 600;
const H = 180;
const PAD = { top: 16, right: 12, bottom: 22, left: 12 };

const money = (n) => `${n < 0 ? '−' : '+'}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/**
 * "$2 on every pick" — the running result of betting Secretariat's top pick to
 * win, from official payouts only. One line and a zero baseline; nothing else.
 */
export default function BetCurve() {
  const [days, setDays] = useState(30);
  const { data } = useQuery({
    queryKey: ['bet-curve', days],
    queryFn: () => getBetCurve(days),
  });

  if (!data || !data.points?.length) return null;

  const pts = data.points;
  const values = [0, ...pts.map((p) => p.cumulative)];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const x = (i) => PAD.left + (i / Math.max(pts.length - 1, 1)) * (W - PAD.left - PAD.right);
  const y = (v) => PAD.top + (1 - (v - lo) / span) * (H - PAD.top - PAD.bottom);

  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.cumulative).toFixed(1)}`).join(' ');
  const area = `${path} L${x(pts.length - 1).toFixed(1)},${y(0).toFixed(1)} L${x(0).toFixed(1)},${y(0).toFixed(1)} Z`;
  const up = data.net >= 0;
  const color = up ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)';
  const last = pts[pts.length - 1];

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 13, letterSpacing: '0.08em', color: 'var(--accent-gold)' }}>
            $2 ON EVERY PICK
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {data.total_bets.toLocaleString()} bets · ${data.staked.toLocaleString()} wagered
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color }}>{money(data.net)}</div>
          {data.roi !== null && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {(data.roi * 100).toFixed(1)}% return
            </div>
          )}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block', marginTop: 12 }} role="img"
        aria-label={`Running result of $2 win bets on every pick over ${days} days: ${money(data.net)}`}>
        <path d={area} fill={color} opacity="0.1" />
        <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--border-medium)" strokeDasharray="4 4" />
        <text x={W - PAD.right} y={y(0) - 4} textAnchor="end" fontSize="10" fill="var(--text-muted)">break even</text>
        <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(pts.length - 1)} cy={y(last.cumulative)} r="4" fill={color} />
        <text x={PAD.left} y={H - 6} fontSize="10" fill="var(--text-muted)">{pts[0].date.slice(5)}</text>
        <text x={W - PAD.right} y={H - 6} textAnchor="end" fontSize="10" fill="var(--text-muted)">{last.date.slice(5)}</text>
      </svg>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Official payouts only{data.unpriced_excluded ? ` · ${data.unpriced_excluded} unpriced races left out` : ''}
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)} style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 4, cursor: 'pointer',
              background: days === d ? 'var(--accent-gold-dim)' : 'transparent',
              color: days === d ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              border: '1px solid var(--border-subtle)',
            }}>{d}d</button>
          ))}
        </div>
      </div>
    </div>
  );
}
