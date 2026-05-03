/**
 * GateSmart logo — a stylized starting gate (4 stalls, top crossbar,
 * post-position numbers, stall #1's door raised to suggest "the break").
 *
 * Two exports:
 *   <GateSmartMark size={48} />     — just the gate icon (square)
 *   <GateSmartLogo size={40} />     — icon + GATESMART wordmark, horizontal
 */

const GOLD = 'var(--accent-gold)';
const GOLD_BRIGHT = 'var(--accent-gold-bright)';

export function GateSmartMark({ size = 48, color = GOLD, accent = GOLD_BRIGHT }) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      xmlns="http://www.w3.org/2000/svg"
      style={{ display: 'block' }}
      aria-label="GateSmart"
    >
      {/* Post-position numbers above the crossbar (1 is the "open" stall) */}
      <text
        x="14" y="10"
        fontSize="8" fontWeight="700"
        fill={accent}
        fontFamily="var(--font-display, sans-serif)"
        textAnchor="middle"
      >
        1
      </text>
      <text
        x="27" y="10"
        fontSize="8" fontWeight="700"
        fill={color}
        fontFamily="var(--font-display, sans-serif)"
        textAnchor="middle"
        opacity="0.55"
      >
        2
      </text>
      <text
        x="40" y="10"
        fontSize="8" fontWeight="700"
        fill={color}
        fontFamily="var(--font-display, sans-serif)"
        textAnchor="middle"
        opacity="0.55"
      >
        3
      </text>
      <text
        x="53" y="10"
        fontSize="8" fontWeight="700"
        fill={color}
        fontFamily="var(--font-display, sans-serif)"
        textAnchor="middle"
        opacity="0.55"
      >
        4
      </text>

      {/* Top crossbar */}
      <rect x="5" y="14" width="54" height="5" rx="1" fill={color} />

      {/* Stall doors — 4 vertical bars. Stall 1's door is shorter (raised). */}
      <rect x="11" y="26" width="6" height="28" fill={accent} />
      <rect x="24" y="20" width="6" height="34" fill={color} />
      <rect x="37" y="20" width="6" height="34" fill={color} />
      <rect x="50" y="20" width="6" height="34" fill={color} />

      {/* Bottom rail */}
      <rect x="5" y="54" width="54" height="4" rx="1" fill={color} />
    </svg>
  );
}

export function GateSmartLogo({ size = 40 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <GateSmartMark size={size} />
      <div
        style={{
          fontFamily: 'var(--font-display, sans-serif)',
          fontSize: size * 0.34,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: GOLD,
          lineHeight: 1.05,
        }}
      >
        GATE<br />SMART
      </div>
    </div>
  );
}

export default GateSmartLogo;
