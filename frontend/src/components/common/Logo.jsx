/**
 * GateSmart logo — black "GS" monogram inside a gold rounded square.
 * Both colors come from the app's existing palette (--accent-gold,
 * --bg-primary).
 *
 *   <GateSmartMark size={48} />     — just the icon (square)
 *   <GateSmartLogo size={40} />     — icon + GATESMART wordmark, horizontal
 */

const GOLD = 'var(--accent-gold)';
const BLACK = 'var(--bg-primary)';

export function GateSmartMark({ size = 48 }) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      xmlns="http://www.w3.org/2000/svg"
      style={{ display: 'block' }}
      aria-label="GateSmart"
    >
      <rect x="0" y="0" width="64" height="64" rx="10" ry="10" fill={GOLD} />
      <text
        x="32"
        y="44"
        textAnchor="middle"
        fontFamily="var(--font-display, sans-serif)"
        fontSize="32"
        fontWeight="700"
        fill={BLACK}
        letterSpacing="-1"
      >
        GS
      </text>
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
