import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBetCurve } from '../../utils/api';

// Plot coordinates. The SVG stretches to its box (preserveAspectRatio="none"),
// so anything that must keep its shape — labels, the end dot — is HTML placed
// by percentage, and strokes don't scale.
const W = 600;
const H = 180;
const PAD = { top: 22, right: 6, bottom: 8, left: 6 };
const pct = (v, total) => `${((v / total) * 100).toFixed(2)}%`;

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
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>
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

      <div className="bet-curve-plot">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}
          aria-label={`Running result of $2 win bets on every pick over ${days} days: ${money(data.net)}`}>
          <path d={area} fill={color} opacity="0.1" />
          <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--border-medium)" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
          <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        </svg>
        <span style={{
          position: 'absolute', right: 0, top: pct(y(0), H), transform: 'translateY(-100%)',
          paddingBottom: 3, fontSize: 11, color: 'var(--text-muted)',
        }}>
          break even
        </span>
        <span style={{
          position: 'absolute', left: pct(x(pts.length - 1), W), top: pct(y(last.cumulative), H),
          width: 9, height: 9, borderRadius: '50%', background: color, transform: 'translate(-50%, -50%)',
        }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        <span>{pts[0].date.slice(5)}</span>
        <span>{last.date.slice(5)}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 10 }}>
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
            }}>{d}D</button>
          ))}
        </div>
      </div>
    </div>
  );
}
