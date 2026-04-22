import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store';
import { getHorsePastPerformances } from '../../utils/api';
import RadarChart from './RadarChart';
import Icon from '../common/Icon';

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

// Converts Equibase short_comment abbreviations into readable English sentences.
// e.g. "3-4-wide turn, wknd" → "3 to 4 wide on the turn, then weakened"
function readableComment(raw) {
  if (!raw) return '';

  const LOC = {
    '1/4': 'at the quarter pole', '1/2': 'at the half', '3/8': 'at the three-eighths',
    'str': 'in the stretch', 'turn': 'on the turn', 'gate': 'at the start',
  };

  const ACT = {
    'wknd': 'weakened', 'bmpd': 'bumped', 'bmp': 'bumped', 'stdy': 'steadied',
    'falt': 'faltered', 'svrd': 'swerved', 'drvg': 'driving', 'drvn': 'driven out',
    'drv': 'driven', 'chsd': 'chased the leader', 'prssd': 'pressed the pace',
    'trkd': 'tracked the leader', 'bid': 'bid for the lead', 'btw': 'between rivals',
    'clrd': 'cleared rivals', 'lugi': 'drifted in', 'lugo': 'drifted out', 'lug': 'drifted',
    'ins': 'inside', 'outs': 'outside', 'out': 'outside', 'rail': 'on the rail',
    'slw': 'slow start', 'brkslw': 'broke slowly', 'brk': 'broke well',
    'str': 'in the stretch', 'turn': 'on the turn',
    'hung': 'hung', 'borei': 'bore in', 'boreo': 'bore out',
    'evenly': 'ran evenly', 'clear': 'drew clear', 'game': 'ran gamely',
    'rallied': 'rallied', 'tired': 'tired', 'tiring': 'tiring late',
    'handily': 'won handily', 'ridden': 'ridden out', 'eased': 'eased',
    'fell': 'fell', 'refused': 'refused', 'unseated': 'unseated rider',
  };

  const decodePart = (part) => {
    part = part.trim();
    if (!part) return null;

    // "3-4-wide turn" → "3 to 4 wide on the turn"
    let m = part.match(/^(\d+)-(\d+)-?wides?\s*(turn|str|stretch|1\/4|1\/2|3\/8|gate)?/i);
    if (m) {
      const where = m[3] ? (' ' + (LOC[m[3].toLowerCase()] || 'on the ' + m[3].toLowerCase())) : '';
      return `${m[1]} to ${m[2]} wide${where}`;
    }

    // "4-wide str" or "4w str" or "4p str" → "4 wide in the stretch"
    m = part.match(/^(\d+)-?(?:wide|[pw])\s*(turn|str|stretch|1\/4|1\/2|3\/8|gate)?/i);
    if (m) {
      const where = m[2] ? (' ' + (LOC[m[2].toLowerCase()] || 'on the ' + m[2].toLowerCase())) : '';
      return `${m[1]} wide${where}`;
    }

    // "3p1/2" or "3p str" → "3 wide at the half"
    m = part.match(/^(\d+)[pw](1\/4|1\/2|3\/8|str|turn|gate)/i);
    if (m) return `${m[1]} wide ${LOC[m[2].toLowerCase()] || m[2]}`;

    // Just "3p" or "4w"
    m = part.match(/^(\d+)[pw]$/i);
    if (m) return `${m[1]} wide`;

    const key = part.toLowerCase().replace(/\s+/g, '').replace(/[.-]/g, '');
    if (ACT[key]) return ACT[key];
    const key2 = part.toLowerCase().trim();
    if (ACT[key2]) return ACT[key2];

    // Unknown: capitalize and return as-is
    return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
  };

  const parts = raw.split(/,\s*/);
  const decoded = parts.map(decodePart).filter(Boolean);
  if (decoded.length === 0) return '';

  const sentence = decoded.join(', then ');
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

// ── UK/IRE form string chips ───────────────────────────────────────────────────
const FORM_CHAR_COLOR = {
  '1': '#FFD700', '2': '#C0C0C0', '3': '#CD7F32',
  'F': 'var(--accent-red-bright)', 'P': 'var(--accent-red-bright)',
  'U': 'var(--accent-red-bright)', 'R': 'var(--accent-red-bright)',
  'B': 'var(--accent-red-bright)', 'S': 'var(--accent-red-bright)',
};

function FormChips({ formString }) {
  const tokens = (formString || '').split('').filter(c => c !== '/');
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
function EquibasePP({ horse, maxRuns = 5 }) {
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

  const runs = perf?.past_performances?.slice(0, maxRuns) ?? [];
  if (error || runs.length === 0) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
        Recent Form
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {runs.map((r, i) => {
          const comment = readableComment(r.short_comment);
          return (
            <div key={i} style={{
              padding: '5px 8px',
              borderRadius: 4,
              background: 'var(--bg-card)',
              fontSize: 11,
            }}>
              {/* Top row: date · track · finish · distance · speed fig */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'nowrap', marginBottom: comment ? 3 : 0 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 10, flexShrink: 0 }}>{r.pp_race_date?.slice(5)}</span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 600, flexShrink: 0 }}>{r.pp_track_code}</span>
                <PosBadge pos={r.official_finish} fieldSize={r.field_size > 0 ? r.field_size : null} />
                <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {[r.pp_distance, r.pp_track_condition].filter(Boolean).join(' · ')}
                </span>
                {r.speed_figure > 0 && (
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12, flexShrink: 0, marginLeft: 'auto',
                    color: r.speed_figure >= 90 ? 'var(--accent-gold-bright)' : r.speed_figure >= 75 ? 'var(--accent-green-bright)' : 'var(--text-muted)',
                  }}>
                    {r.speed_figure}
                  </span>
                )}
              </div>
              {/* Comment — full width, wrapping, plain English */}
              {comment && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.45 }}>
                  {comment}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Region-aware form display ──────────────────────────────────────────────────
function RecentForm({ horse, region, maxRuns }) {
  const isNA = ['USA', 'CAN'].includes((region || '').toUpperCase());
  if (isNA) return <EquibasePP horse={horse} maxRuns={maxRuns} />;
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
  const experienceLevel = useAppStore((s) => s.userProfile?.experienceLevel);
  const [expanded, setExpanded] = useState(false);
  const isBeginner = experienceLevel === 'beginner';
  const isAdvanced = experienceLevel === 'advanced';

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

  // Top pick for beginner gold star indicator
  const isTopPick = analysis?.runners?.length > 0 &&
    score != null &&
    score === Math.max(...analysis.runners.map(r => r.contender_score || 0));

  const summaryText = isBeginner
    ? (analysisData?.summary_beginner || analysisData?.summary)
    : analysisData?.summary;

  // Beginner rows are always expandable to reveal hidden details
  const hasExpandedContent = isBeginner ? true : !!(summaryText || scorecard);

  const LABELS = {
    'use-in-exotics': 'Use in Exotics',
    'each-way': 'Each Way',
    'avoid': 'Avoid',
    'win': 'Win',
    'place': 'Place',
    'show': 'Show',
  };

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
              maxWidth: 180,
              textDecoration: isScratched ? 'line-through' : 'none',
            }}>
              {horse.horse_name}
            </div>
            {/* Beginner: gold star for top pick */}
            {isBeginner && isTopPick && !isScratched && (
              <span style={{ fontSize: 14, flexShrink: 0 }} title="Secretariat's top pick">⭐</span>
            )}
            {/* Horse profile link — always visible */}
            <button
              onClick={(e) => { e.stopPropagation(); navigate(`/horse/${horse.horse_id}`); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 2px', lineHeight: 1, flexShrink: 0, display: 'flex', alignItems: 'center' }}
              title="View horse profile"
            >
              <Icon name="search" size={13} color="var(--text-muted)" />
            </button>
            {isScratched && (
              <span className="badge badge-muted" style={{ flexShrink: 0, fontSize: 10 }}>Scratched</span>
            )}
            {isCoupled && !isScratched && (
              <span className="badge badge-gold" style={{ flexShrink: 0, fontSize: 9 }}>ENTRY</span>
            )}
          </div>

          {/* Beginner hides trainer/jockey (revealed on expand) */}
          {!isBeginner && (
            <div style={{
              fontSize: 11,
              color: 'var(--text-secondary)',
              marginTop: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {[horse.jockey, horse.trainer].filter(Boolean).join(' · ')}
            </div>
          )}

          {/* Advanced shows weight + days since last run if available */}
          {isAdvanced && (horse.weight || horse.lbs || horse.days_since_last_run) && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>
              {[
                (horse.weight || horse.lbs) ? `${horse.weight || horse.lbs}lbs` : null,
                horse.days_since_last_run ? `${horse.days_since_last_run}d since last run` : null,
              ].filter(Boolean).join(' · ')}
            </div>
          )}

          {horse.claiming_price && !isBeginner && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              Claim: ${Number(horse.claiming_price).toLocaleString()}
            </div>
          )}

          {/* Beginner hides recommended_bet (revealed on expand) */}
          {!isBeginner && analysisData?.recommended_bet && (
            <div style={{ marginTop: 4 }}>
              {(() => {
                const raw = analysisData.recommended_bet;
                const label = LABELS[raw] || raw;
                const color = raw === 'avoid' ? 'red' : raw === 'win' ? 'green' : 'gold';
                return <span className={`badge badge-${color}`}>{label}</span>;
              })()}
            </div>
          )}
        </div>

        {/* Odds + expand indicator */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
          {(horse.odds || horse.sp) && (
            <span className="odds-chip">{horse.odds || horse.sp}</span>
          )}
          {hasExpandedContent && (
            isBeginner ? (
              <span style={{ fontSize: 10, color: 'var(--accent-gold)', fontWeight: 600 }}>
                {expanded ? 'Hide ▲' : 'Details ▼'}
              </span>
            ) : (
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {expanded ? '▲' : '▼'}
              </span>
            )
          )}
        </div>
      </div>

      {/* ── Expanded section ─────────────────────────────────────────── */}
      {expanded && (
        <div style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '12px',
          background: 'var(--bg-secondary)',
          maxWidth: '100%',
          overflow: 'hidden',
        }}>
          {/* Beginner: reveal hidden header details */}
          {isBeginner && (horse.jockey || horse.trainer || analysisData?.recommended_bet) && (
            <div style={{ marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--border-subtle)' }}>
              {(horse.jockey || horse.trainer) && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  {[horse.jockey, horse.trainer].filter(Boolean).join(' · ')}
                </div>
              )}
              {horse.claiming_price && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                  Claim: ${Number(horse.claiming_price).toLocaleString()}
                </div>
              )}
              {analysisData?.recommended_bet && (() => {
                const raw = analysisData.recommended_bet;
                const label = LABELS[raw] || raw;
                const color = raw === 'avoid' ? 'red' : raw === 'win' ? 'green' : 'gold';
                return <span className={`badge badge-${color}`}>{label}</span>;
              })()}
            </div>
          )}

          {/* Analysis text + radar: side-by-side on wider screens */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            {summaryText && (
              <div style={{ flex: 1, minWidth: 0 }}>
                {!isBeginner && analysisData?.strengths?.length > 0 && (
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
                {!isBeginner && analysisData?.weaknesses?.length > 0 && (
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

            {/* Compact radar fingerprint */}
            {scorecard && (
              <div className="horse-radar-desktop">
                <RadarChart
                  scores={scorecard.scores}
                  overall={scorecard.overall}
                  size={130}
                  animate={false}
                  showLabels={false}
                  showOverall={false}
                />
              </div>
            )}
          </div>

          <RecentForm horse={horse} region={region} maxRuns={isAdvanced ? 3 : 5} />

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
