import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store';
import { trackBetAdded } from '../../utils/analytics';
import { getHorsePastPerformances } from '../../utils/api';
import RadarChart from './RadarChart';

// ── Position badge helper ──────────────────────────────────────────────────────
function PosBadge({ pos, fieldSize }) {
  const n = parseInt(pos);
  const color =
    n === 1 ? '#FFD700' :
    n === 2 ? '#C0C0C0' :
    n === 3 ? '#CD7F32' :
    'var(--text-muted)';
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color, fontSize: 13 }}>
      {pos}{fieldSize ? `/${fieldSize}` : ''}
    </span>
  );
}

// ── UK/IRE form string chips ───────────────────────────────────────────────────
const FORM_CHAR_COLOR = {
  '1': '#FFD700', '2': '#C0C0C0', '3': '#CD7F32',
  'F': 'var(--accent-red-bright)', 'P': 'var(--accent-red-bright)',
  'U': 'var(--accent-red-bright)', 'R': 'var(--accent-red-bright)',
  'B': 'var(--accent-red-bright)', 'S': 'var(--accent-red-bright)',
};

function FormChips({ formString }) {
  // Split on separators, keep each meaningful run character
  const tokens = (formString || '').split('').filter(c => c !== '/' );
  if (tokens.every(c => c === '-')) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
        Recent Form
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
        {tokens.map((c, i) => {
          if (c === '-') {
            return <span key={i} style={{ color: 'var(--border-subtle)', fontSize: 14, lineHeight: 1 }}>·</span>;
          }
          const color = FORM_CHAR_COLOR[c] || (parseInt(c) ? 'var(--text-secondary)' : 'var(--text-muted)');
          return (
            <span key={i} style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 22, height: 22, borderRadius: 4,
              background: 'var(--bg-card)',
              border: `1px solid ${color === '#FFD700' ? 'rgba(201,162,39,0.4)' : 'var(--border-subtle)'}`,
              fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12,
              color,
            }}>
              {c}
            </span>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 6, fontSize: 10, color: 'var(--text-muted)' }}>
        <span>1=Win</span><span>2=2nd</span><span>3=3rd</span>
        <span style={{ color: 'var(--accent-red-bright)' }}>F=Fell · P=PU · U=Unseated</span>
      </div>
    </div>
  );
}

// ── US Equibase past performances ─────────────────────────────────────────────
function EquibasePP({ horse }) {
  const [perf, setPerf] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const fetchedRef = useRef(false);

  if (!fetchedRef.current && !loading && !perf && !error) {
    fetchedRef.current = true;
    setLoading(true);
    getHorsePastPerformances(horse.horse_id, horse.horse_name)
      .then((data) => setPerf(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }

  if (loading) {
    return (
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Recent Form</div>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 11, width: `${80 - i * 15}%`, borderRadius: 3, marginBottom: 5 }} />
        ))}
      </div>
    );
  }

  const runs = perf?.past_performances?.slice(0, 5) ?? [];
  if (error || runs.length === 0) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
        Recent Form
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {runs.map((r, i) => (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: '62px 36px 1fr auto',
            gap: 6,
            alignItems: 'center',
            fontSize: 11,
            padding: '4px 8px',
            borderRadius: 4,
            background: 'var(--bg-card)',
          }}>
            <div>
              <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>{r.pp_race_date?.slice(5)}</div>
              <div style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{r.pp_track_code}</div>
            </div>
            <PosBadge pos={r.official_finish} fieldSize={r.field_size > 0 ? r.field_size : null} />
            <div style={{ minWidth: 0, overflow: 'hidden' }}>
              <span style={{ color: 'var(--text-muted)' }}>
                {[r.pp_distance, r.pp_track_condition].filter(Boolean).join(' · ')}
              </span>
              {r.short_comment && (
                <>
                  <span style={{ color: 'var(--border-medium)', margin: '0 4px' }}>|</span>
                  <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block', maxWidth: 130 }}>
                    {r.short_comment}
                  </span>
                </>
              )}
            </div>
            {r.speed_figure > 0 && (
              <span style={{
                fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12,
                color: r.speed_figure >= 90 ? 'var(--accent-gold-bright)' : r.speed_figure >= 75 ? 'var(--accent-green-bright)' : 'var(--text-muted)',
              }}>
                {r.speed_figure}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Region-aware form display ──────────────────────────────────────────────────
function RecentForm({ horse, region }) {
  const isNA = ['USA', 'CAN'].includes((region || '').toUpperCase());
  if (isNA) return <EquibasePP horse={horse} />;
  if (horse.form) return <FormChips formString={horse.form} />;
  return null;
}

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
export function HorseRow({ horse, analysis, raceId, scorecards = [], course = '', raceName = '', region = '', isCoupled = false }) {
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
        {/* Program number + score ring */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, flexShrink: 0 }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
            color: 'var(--text-muted)', lineHeight: 1,
          }}>
            #{horse.program_number || horse.cloth_number || horse.stall_number || '?'}
          </span>
          {scoreClass ? (
            <div className={`score-ring ${scoreClass}`}>{score}</div>
          ) : (
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: isScratched ? 'var(--bg-elevated)' : 'rgba(201,162,39,0.15)',
              border: `2px solid ${isScratched ? 'var(--border-subtle)' : 'var(--accent-gold-dim)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 700,
              color: isScratched ? 'var(--text-muted)' : 'var(--accent-gold)',
            }}>
              {horse.program_number || horse.cloth_number || horse.stall_number || '?'}
            </div>
          )}
        </div>

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
            {isCoupled && !isScratched && (
              <span className="badge badge-gold" style={{ flexShrink: 0, fontSize: 9 }}>ENTRY</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {[horse.jockey, horse.trainer].filter(Boolean).join(' · ')}
          </div>
          {horse.claiming_price && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              Claim: ${Number(horse.claiming_price).toLocaleString()}
            </div>
          )}
          {analysisData?.recommended_bet && (
            <div style={{ marginTop: 4 }}>
              {(() => {
                const raw = analysisData.recommended_bet;
                const LABELS = {
                  'use-in-exotics': 'Use in Exotics',
                  'each-way': 'Each Way',
                  'avoid': 'Avoid',
                  'win': 'Win',
                  'place': 'Place',
                  'show': 'Show',
                };
                const label = LABELS[raw] || raw;
                const color = raw === 'avoid' ? 'red' : raw === 'win' ? 'green' : 'gold';
                return <span className={`badge badge-${color}`}>{label}</span>;
              })()}
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
                {experienceLevel !== 'beginner' && analysisData.strengths?.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-green-bright)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>
                      Strengths
                    </div>
                    {analysisData.strengths.map((s, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>
                        · {s.charAt(0).toUpperCase() + s.slice(1)}
                      </div>
                    ))}
                  </div>
                )}
                {experienceLevel !== 'beginner' && analysisData.weaknesses?.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-red-bright)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>
                      Concerns
                    </div>
                    {analysisData.weaknesses.map((w, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>
                        · {w.charAt(0).toUpperCase() + w.slice(1)}
                      </div>
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

          <RecentForm horse={horse} region={region} />

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
