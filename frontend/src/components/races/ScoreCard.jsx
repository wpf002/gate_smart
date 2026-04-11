import { useState } from 'react';
import RadarChart from './RadarChart';
import { useAppStore } from '../../store';

const DIMENSIONS = [
  { key: 'speed',          label: 'SPEED',        plainLabel: 'Speed',       plainDesc: 'How fast this horse has run compared to today\'s field' },
  { key: 'class',          label: 'CLASS',        plainLabel: 'Competition', plainDesc: 'Quality of races it has competed in — higher is tougher' },
  { key: 'form',           label: 'FORM',         plainLabel: 'Recent Runs', plainDesc: 'How it has finished in its most recent races' },
  { key: 'pace_fit',       label: 'PACE',         plainLabel: 'Race Style',  plainDesc: 'Does its running style suit the way this race is likely to unfold' },
  { key: 'value',          label: 'VALUE',        plainLabel: 'Bet Value',   plainDesc: 'Is the odds price better than what Secretariat thinks it should be' },
  { key: 'trainer_jockey', label: 'T/J',          plainLabel: 'Connections', plainDesc: 'Trainer and jockey win rates and their history together' },
];

function scoreTextColor(score) {
  if (score >= 70) return 'var(--accent-green-bright)';
  if (score >= 50) return 'var(--accent-gold-bright)';
  return 'var(--accent-red-bright)';
}

function scoreBarColor(score) {
  if (score >= 70) return 'var(--accent-green)';
  if (score >= 50) return 'var(--accent-gold)';
  return 'var(--accent-red)';
}

function overallBadgeStyle(score) {
  if (score >= 70) return {
    background: 'rgba(42,122,75,0.2)',
    color: 'var(--accent-green-bright)',
    border: '1px solid rgba(42,122,75,0.4)',
  };
  if (score >= 50) return {
    background: 'rgba(201,162,39,0.15)',
    color: 'var(--accent-gold-bright)',
    border: '1px solid rgba(201,162,39,0.3)',
  };
  return {
    background: 'rgba(192,57,43,0.1)',
    color: 'var(--accent-red-bright)',
    border: '1px solid rgba(192,57,43,0.3)',
  };
}

/**
 * Single-horse scorecard.
 *
 * Props:
 *   scorecard  {object}  horse scorecard from /advisor/scorecard API
 *   expanded   {boolean}
 *   onToggle   {fn}      called when the header is clicked
 */
export default function ScoreCard({ scorecard, expanded, onToggle }) {
  const [activeDim, setActiveDim] = useState(null);
  const experienceLevel = useAppStore((s) => s.userProfile?.experienceLevel);
  const isPlain = experienceLevel === 'beginner';

  const {
    horse_name = '',
    scores = {},
    score_notes = {},
    overall = 0,
    verdict = '',
  } = scorecard;

  return (
    <div style={{
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
      marginBottom: 6,
    }}>
      {/* ── Collapsed header strip ─────────────────────────────────────── */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 12px',
          cursor: 'pointer',
          background: expanded ? 'var(--bg-elevated)' : 'var(--bg-card)',
          transition: 'background 0.15s',
        }}
        onMouseEnter={e => { if (!expanded) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
        onMouseLeave={e => { if (!expanded) e.currentTarget.style.background = 'var(--bg-card)'; }}
      >
        {/* Overall badge */}
        <div style={{
          ...overallBadgeStyle(overall),
          width: 36,
          height: 36,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'var(--font-display)',
          fontSize: 14,
          flexShrink: 0,
        }}>
          {overall}
        </div>

        {/* Name + verdict */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>{horse_name}</div>
          <div style={{
            fontSize: 12,
            color: 'var(--text-muted)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {verdict}
          </div>
        </div>

        <div style={{ color: 'var(--text-muted)', fontSize: 11, flexShrink: 0 }}>
          {expanded ? '▲' : '▼'}
        </div>
      </div>

      {/* ── Expanded body ─────────────────────────────────────────────── */}
      {expanded && (
        <div style={{
          padding: 12,
          background: 'var(--bg-secondary)',
          borderTop: '1px solid var(--border-subtle)',
        }}>
          {/* Radar chart centred */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
            <RadarChart
              scores={scores}
              overall={overall}
              size={180}
              animate
              showLabels
              showOverall
            />
          </div>

          {/* Score legend */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, fontSize: 10, marginBottom: 10 }}>
            <span style={{ color: 'var(--accent-red-bright)' }}>0–49 weak</span>
            <span style={{ color: 'var(--accent-gold-bright)' }}>50–69 average</span>
            <span style={{ color: 'var(--accent-green-bright)' }}>70+ strong</span>
          </div>

          {/* Score bars — tap/click to reveal note */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 12 }}>
            {DIMENSIONS.map(({ key, label, plainLabel, plainDesc }) => {
              const score = scores[key] ?? 0;
              const noteVisible = activeDim === key;
              const dimLabel = isPlain ? plainLabel : label;
              return (
                <div
                  key={key}
                  onClick={() => setActiveDim(noteVisible ? null : key)}
                  style={{ cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 3, paddingBottom: 3 }}>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11,
                      textTransform: isPlain ? 'none' : 'uppercase',
                      color: 'var(--text-muted)',
                      width: 90,
                      flexShrink: 0,
                    }}>
                      {dimLabel}
                    </span>
                    <div style={{
                      flex: 1,
                      height: 4,
                      background: 'var(--border-subtle)',
                      borderRadius: 2,
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${score}%`,
                        background: scoreBarColor(score),
                        borderRadius: 2,
                      }} />
                    </div>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                      color: scoreTextColor(score),
                      width: 28,
                      textAlign: 'right',
                      flexShrink: 0,
                    }}>
                      {score}
                    </span>
                  </div>
                  {noteVisible && (
                    <div style={{
                      fontSize: 11,
                      fontStyle: 'italic',
                      color: 'var(--text-muted)',
                      paddingLeft: 98,
                      paddingBottom: 4,
                      lineHeight: 1.4,
                    }}>
                      {isPlain ? plainDesc : (score_notes[key] || plainDesc)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Verdict */}
          {verdict && (
            <div style={{
              fontSize: 13,
              fontStyle: 'italic',
              color: 'var(--accent-gold)',
              lineHeight: 1.5,
            }}>
              "{verdict}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}
