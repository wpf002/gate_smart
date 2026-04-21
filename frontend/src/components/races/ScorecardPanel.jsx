import { useState } from 'react';
import ScoreCard from './ScoreCard';


/**
 * Field scorecard panel — renders all horse scorecards sorted by overall score.
 *
 * Props:
 *   raceScorecards  {object}   full API response: { race_id, course, scorecards[] }
 *   loading         {boolean}
 */
export default function ScorecardPanel({ raceScorecards, loading, runners = [] }) {
  const [expandedId, setExpandedId] = useState(null);

  // Build a lookup from horse_id → program number
  const numByHorseId = {};
  const numByName = {};
  runners.forEach(r => {
    const num = r.program_number || r.cloth_number || r.stall_number || '';
    if (r.horse_id && num) numByHorseId[r.horse_id] = num;
    if ((r.horse_name || r.horse) && num) numByName[(r.horse_name || r.horse).toLowerCase()] = num;
  });

  if (loading) {
    return (
      <div style={{
        padding: 16,
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-md)',
        marginBottom: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: 'var(--accent-gold)',
            animation: 'pulse 1s infinite',
          }} />
          <span style={{ fontSize: 13, color: 'var(--accent-gold)' }}>
            Secretariat is scoring the field…
          </span>
        </div>
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="skeleton"
            style={{ height: 52, borderRadius: 8, marginBottom: 6 }}
          />
        ))}
      </div>
    );
  }

  if (!raceScorecards) return null;

  const sorted = [...(raceScorecards.scorecards || [])].sort(
    (a, b) => (b.overall || 0) - (a.overall || 0)
  );

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: 16,
      marginBottom: 16,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--accent-gold)' }}>
          FIELD SCORECARD
        </span>
        <span className="badge badge-gold">{sorted.length} horses</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
        Tap any horse to see the full radar breakdown
      </div>

      {sorted.map((sc, idx) => {
        const num = numByHorseId[sc.horse_id] || numByName[(sc.horse_name || '').toLowerCase()] || '';
        const numPrefix = num ? `#${num} — ` : '';
        const displayCard = { ...sc, horse_name: `${numPrefix}${sc.horse_name}` };
        const rowId = sc.horse_id || idx;
        return (
          <ScoreCard
            key={rowId}
            scorecard={displayCard}
            rank={idx < 3 ? idx + 1 : null}
            expanded={expandedId === rowId}
            onToggle={() => setExpandedId(expandedId === rowId ? null : rowId)}
          />
        );
      })}
    </div>
  );
}
