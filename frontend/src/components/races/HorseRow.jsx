import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store';
import { trackBetAdded } from '../../utils/analytics';
import RadarChart from './RadarChart';

export function HorseRowSkeleton() {
  return (
    <div style={{
      background: 'var(--bg-card)',
      borderRadius: 'var(--radius-md)',
      padding: '12px',
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <div className="skeleton" style={{ width: 40, height: 40, borderRadius: '50%' }} />
        <div style={{ flex: 1 }}>
          <div className="skeleton" style={{ height: 15, width: '50%', borderRadius: 4, marginBottom: 6 }} />
          <div className="skeleton" style={{ height: 12, width: '35%', borderRadius: 4 }} />
        </div>
        <div className="skeleton" style={{ height: 28, width: 56, borderRadius: 6 }} />
      </div>
    </div>
  );
}

/**
 * Single runner row.
 *
 * Props:
 *   horse      {object}   runner data from the race API
 *   analysis   {object}   full Secretariat analysis (optional)
 *   raceId     {string}
 *   scorecards {array}    array of scorecards from /advisor/scorecard (optional)
 */
export function HorseRow({ horse, analysis, raceId, scorecards = [], course = '', raceName = '' }) {
  const navigate = useNavigate();
  const addToBetSlip = useAppStore((s) => s.addToBetSlip);
  const betSlip = useAppStore((s) => s.betSlip);
  const experienceLevel = useAppStore((s) => s.userProfile?.experienceLevel);
  const [expanded, setExpanded] = useState(false);
  const [added, setAdded] = useState(false);

  const isScratched = horse.non_runner || horse.scratched ||
    ['scratched', 'non-runner', 'nr', 'withdrawn'].includes((horse.status || '').toLowerCase());

  // Match analysis runner
  const analysisData = analysis?.runners?.find(
    (r) => r.horse_id === horse.horse_id || r.horse_name === horse.horse_name
  );

  // Match scorecard
  const scorecard = scorecards.find(
    (sc) => sc.horse_id === horse.horse_id || sc.horse_name === horse.horse_name
  );

  const score = analysisData?.contender_score;
  const scoreClass =
    score >= 70 ? 'score-high' : score >= 40 ? 'score-med' : score != null ? 'score-low' : null;

  const isInSlip = betSlip.some((b) => b.horse_id === horse.horse_id);

  const handleAddBet = (e) => {
    e.stopPropagation();
    const betType = analysisData?.recommended_bet || 'win';
    const odds = horse.odds || horse.sp || '?';
    addToBetSlip({
      horse_id: horse.horse_id,
      horse_name: horse.horse_name,
      race_id: raceId,
      bet_type: betType,
      odds,
      stake: 10,
      course,
      race_name: raceName,
      jockey: horse.jockey || '',
      trainer: horse.trainer || '',
      owner: horse.owner || '',
    });
    trackBetAdded(betType, horse.horse_id, odds);
    setAdded(true);
    setTimeout(() => setAdded(false), 1500);
  };

  const summaryText = experienceLevel === 'beginner'
    ? (analysisData?.summary_beginner || analysisData?.summary)
    : analysisData?.summary;
  const hasExpandedContent = !!(summaryText || scorecard);

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
        transition: 'background 0.15s',
        opacity: isScratched ? 0.5 : 1,
      }}
    >
      {/* ── Header row (always visible) ─────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          padding: '12px',
          cursor: hasExpandedContent ? 'pointer' : 'default',
        }}
        onClick={() => { if (hasExpandedContent) setExpanded(e => !e); }}
        onMouseEnter={e => { if (hasExpandedContent) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
      >
        {/* Score ring or program number */}
        {scoreClass ? (
          <div className={`score-ring ${scoreClass}`}>{score}</div>
        ) : (
          <div style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: isScratched ? 'var(--bg-elevated)' : 'rgba(201,162,39,0.15)',
            border: `2px solid ${isScratched ? 'var(--border-subtle)' : 'var(--accent-gold-dim)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'var(--font-display)',
            fontSize: 15,
            fontWeight: 700,
            color: isScratched ? 'var(--text-muted)' : 'var(--accent-gold)',
            flexShrink: 0,
          }}>
            {horse.program_number || horse.cloth_number || horse.stall_number || '?'}
          </div>
        )}

        {/* Horse info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              fontWeight: 700,
              fontSize: 14,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              textDecoration: isScratched ? 'line-through' : 'none',
            }}>
              {horse.horse_name}
            </div>
            {isScratched && (
              <span className="badge badge-muted" style={{ flexShrink: 0, fontSize: 10 }}>Scratched</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {[horse.jockey, horse.trainer].filter(Boolean).join(' · ')}
          </div>
          {analysisData?.recommended_bet && (
            <div style={{ marginTop: 4 }}>
              <span className={`badge badge-${
                analysisData.recommended_bet === 'avoid' ? 'red' :
                analysisData.recommended_bet === 'win'   ? 'green' : 'gold'
              }`}>
                {analysisData.recommended_bet}
              </span>
            </div>
          )}
        </div>

        {/* Odds + actions */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
          {(horse.odds || horse.sp) && (
            <span className="odds-chip">{horse.odds || horse.sp}</span>
          )}
          {analysisData && !isInSlip && (
            <button
              onClick={handleAddBet}
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: '3px 8px',
                borderRadius: 6,
                border: '1px solid var(--accent-gold-dim)',
                background: added ? 'var(--accent-gold)' : 'transparent',
                color: added ? '#000' : 'var(--accent-gold)',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {added ? '✓ Added' : '+ Bet'}
            </button>
          )}
          {isInSlip && (
            <span style={{ fontSize: 11, color: 'var(--accent-green-bright)' }}>✓ In slip</span>
          )}
          {hasExpandedContent && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              {expanded ? '▲' : '▼'}
            </span>
          )}
        </div>
      </div>

      {/* ── Expanded section ─────────────────────────────────────────── */}
      {expanded && (
        <div style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '12px',
          background: 'var(--bg-secondary)',
        }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            {/* Analysis text */}
            {summaryText && (
              <div style={{ flex: 1, minWidth: 0 }}>
                {analysisData.strengths?.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-green-bright)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>
                      Strengths
                    </div>
                    {analysisData.strengths.map((s, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>· {s}</div>
                    ))}
                  </div>
                )}
                {analysisData.weaknesses?.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-red-bright)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>
                      Concerns
                    </div>
                    {analysisData.weaknesses.map((w, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>· {w}</div>
                    ))}
                  </div>
                )}
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {summaryText}
                </p>
              </div>
            )}

            {/* Compact radar fingerprint (visual only — no labels, no overall text) */}
            {scorecard && (
              <div style={{ flexShrink: 0 }}>
                <RadarChart
                  scores={scorecard.scores}
                  overall={scorecard.overall}
                  size={120}
                  animate={false}
                  showLabels={false}
                  showOverall={false}
                />
              </div>
            )}
          </div>

          {/* View horse profile link */}
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/horse/${horse.horse_id}`); }}
            style={{
              marginTop: 10,
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--text-muted)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              textDecoration: 'underline',
            }}
          >
            View horse profile →
          </button>
        </div>
      )}
    </div>
  );
}
