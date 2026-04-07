import { useId } from 'react';

const AXES = [
  { key: 'speed',          label: 'Speed' },
  { key: 'class',          label: 'Class' },
  { key: 'form',           label: 'Form'  },
  { key: 'pace_fit',       label: 'Pace'  },
  { key: 'value',          label: 'Value' },
  { key: 'trainer_jockey', label: 'T/J'   },
];

function toRad(deg) {
  return (deg * Math.PI) / 180;
}

function axisAngle(i) {
  return toRad(-90 + i * 60);
}

function pointAt(cx, cy, r, i) {
  const a = axisAngle(i);
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function polygonPath(points) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ') + ' Z';
}

function scoreColors(overall) {
  if (overall >= 70) return { fill: 'rgba(42,122,75,0.2)',  stroke: '#3aad6a' };
  if (overall >= 50) return { fill: 'rgba(201,162,39,0.15)', stroke: '#c9a227' };
  return               { fill: 'rgba(192,57,43,0.1)',   stroke: '#c0392b' };
}

/**
 * Pure SVG radar chart — no external libraries.
 *
 * Props:
 *   scores      {object}  keys: speed, class, form, pace_fit, value, trainer_jockey (0-100)
 *   overall     {number}  used for color mapping; if omitted, averages scores
 *   size        {number}  svg width & height (default 160)
 *   animate     {boolean} stroke-dasharray draw-in on mount (default true)
 *   showLabels  {boolean} axis labels (default true)
 *   showOverall {boolean} center overall number + "OVERALL" label (default true)
 */
export default function RadarChart({
  scores = {},
  overall = null,
  size = 160,
  animate = true,
  showLabels = true,
  showOverall = true,
}) {
  const uid = useId().replace(/:/g, '');
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - (showLabels ? 20 : 8);

  // Compute overall for colour if not supplied
  const vals = AXES.map(ax => Math.max(0, Math.min(100, scores[ax.key] || 0)));
  const computedOverall = overall ?? Math.round(vals.reduce((s, v) => s + v, 0) / vals.length);
  const { fill, stroke } = scoreColors(computedOverall);

  // Background ring radii
  const rings = [0.33, 0.66, 1.0].map(f => outerR * f);

  // Data polygon vertices
  const dataPoints = AXES.map((ax, i) => {
    const r = (Math.max(0, Math.min(100, scores[ax.key] || 0)) / 100) * outerR;
    return pointAt(cx, cy, r, i);
  });

  const animKeyframes = `
    @keyframes radarDraw_${uid} {
      from { stroke-dashoffset: 900; }
      to   { stroke-dashoffset: 0;   }
    }
  `;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ overflow: 'visible', display: 'block' }}
      aria-hidden="true"
    >
      {animate && <style>{animKeyframes}</style>}

      {/* Background rings */}
      {rings.map((r, i) => (
        <path
          key={i}
          d={polygonPath(AXES.map((_, ai) => pointAt(cx, cy, r, ai)))}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={1}
        />
      ))}

      {/* Axis spokes */}
      {AXES.map((_, i) => {
        const outer = pointAt(cx, cy, outerR, i);
        return (
          <line
            key={i}
            x1={cx.toFixed(2)} y1={cy.toFixed(2)}
            x2={outer.x.toFixed(2)} y2={outer.y.toFixed(2)}
            stroke="rgba(255,255,255,0.12)"
            strokeWidth={1}
          />
        );
      })}

      {/* Data polygon — fill first so stroke sits on top */}
      <path
        d={polygonPath(dataPoints)}
        fill={fill}
        stroke="none"
      />
      <path
        d={polygonPath(dataPoints)}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinejoin="round"
        style={animate ? {
          strokeDasharray: 900,
          strokeDashoffset: 0,
          animation: `radarDraw_${uid} 0.6s ease-out both`,
        } : undefined}
      />

      {/* Vertex dots */}
      {dataPoints.map((p, i) => (
        <circle
          key={i}
          cx={p.x.toFixed(2)}
          cy={p.y.toFixed(2)}
          r={4}
          fill={stroke}
        />
      ))}

      {/* Axis labels */}
      {showLabels && AXES.map((ax, i) => {
        const lp = pointAt(cx, cy, outerR + 14, i);
        return (
          <text
            key={i}
            x={lp.x.toFixed(2)}
            y={lp.y.toFixed(2)}
            textAnchor="middle"
            dominantBaseline="middle"
            fontFamily="var(--font-mono)"
            fontSize={9}
            fill="var(--text-secondary)"
          >
            {ax.label}
          </text>
        );
      })}

      {/* Overall score in centre */}
      {showOverall && (
        <>
          <text
            x={cx}
            y={cy - 7}
            textAnchor="middle"
            dominantBaseline="middle"
            fontFamily="var(--font-display)"
            fontSize={22}
            fill={stroke}
          >
            {computedOverall}
          </text>
          <text
            x={cx}
            y={cy + 11}
            textAnchor="middle"
            dominantBaseline="middle"
            fontFamily="var(--font-mono)"
            fontSize={8}
            fill="var(--text-muted)"
          >
            OVERALL
          </text>
        </>
      )}
    </svg>
  );
}
