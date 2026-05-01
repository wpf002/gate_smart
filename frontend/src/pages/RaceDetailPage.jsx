import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { trackRaceAnalysis, trackScoreCardViewed, trackDebriefViewed, trackEvent } from '../utils/analytics';
import { useQuery } from '@tanstack/react-query';
import { getRaceDetail, getScoreCard, getRaceDebrief, clearRaceAnalysis, getRaceResults } from '../utils/api';
import { HorseRow, HorseRowSkeleton } from '../components/races/HorseRow';
import ScorecardPanel from '../components/races/ScorecardPanel';
import DebriefPanel from '../components/races/DebriefPanel';
import { getDisplayTime, formatDistance, formatPurse, isRaceDefinitelyFinished } from '../components/races/RaceCard';
import { useAppStore } from '../store';
import AffiliateDrawer from '../components/common/AffiliateDrawer';
import { PARTNERS } from '../utils/affiliates';
import Icon from '../components/common/Icon';
import AccuracyBadge from '../components/common/AccuracyBadge';
import NotificationBell from '../components/common/NotificationBell';

const MODES = [
  { id: 'low',    label: 'Low',    desc: 'Favorites and safe bets'    },
  { id: 'medium', label: 'Medium', desc: 'Balanced value and safety'  },
  { id: 'high',   label: 'High',   desc: 'Overlays and longshots'     },
];

const FINISH_POSITION = {
  first:  { label: '1', color: 'var(--accent-gold-bright)',   bg: 'rgba(201,162,39,0.2)',  border: 'rgba(201,162,39,0.5)'  },
  second: { label: '2', color: 'var(--text-secondary)',        bg: 'rgba(160,160,160,0.15)', border: 'rgba(160,160,160,0.35)' },
  third:  { label: '3', color: 'var(--accent-gold)',           bg: 'rgba(140,90,30,0.15)',  border: 'rgba(140,90,30,0.35)'  },
  fourth: { label: '4', color: 'var(--text-muted)',            bg: 'rgba(80,80,80,0.1)',    border: 'rgba(80,80,80,0.25)'   },
};

const CONFIDENCE_PLAIN = {
  high:   'Secretariat is very confident in this pick — the data strongly favors one horse.',
  medium: 'Secretariat sees a clear leader but there is some competition.',
  low:    'This race is genuinely wide open — any horse could win.',
};

// ── AnalysisPanel ─────────────────────────────────────────────────────────────
function AnalysisPanel({ analysis, loading, mode, runners = [], userRegion = 'usa', raceId = '', course = '', raceType = '' }) {
  const [techExpanded, setTechExpanded] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerHorse, setDrawerHorse] = useState('');
  const [drawerBetType, setDrawerBetType] = useState('');
  const [tgDismissed, setTgDismissed] = useState(!!sessionStorage.getItem('gs_tg_dismissed'));
  const [wpDismissed, setWpDismissed] = useState(!!sessionStorage.getItem('gs_wp_dismissed'));
  const [tellerOpenMap, setTellerOpenMap] = useState({});
  const toggleTeller = (type) => setTellerOpenMap(m => ({ ...m, [type]: !m[type] }));
  const { addToBetSlip } = useAppStore();
  const experienceLevel = useAppStore(s => s.userProfile?.experienceLevel || 'beginner');

  // Beginners always see Plain content with no toggle. Advanced users get the
  // Plain/Technical toggle as a per-race view override that does NOT touch
  // their stored experience level — switching to Plain here is "show me the
  // plain summary for this race", not "demote my account to beginner".
  const [advancedViewMode, setAdvancedViewMode] = useState('technical');
  const effectiveViewMode = experienceLevel === 'advanced' ? advancedViewMode : 'beginner';

  const normName = (s) => (s || '').toLowerCase().replace(/[^a-z\s]/g, '').trim();

  const findRunner = (nameOrSelection) => {
    const raw = (nameOrSelection || '').replace(/^#?\d+\s+[-–]?\s*/, '').trim();
    const norm = normName(raw);
    return runners.find(r => normName(r.horse_name) === norm || normName(r.horse_name).includes(norm) || norm.includes(normName(r.horse_name)));
  };

  const openBetOnline = (selection, betTypeLabel) => {
    setDrawerHorse(selection || '');
    setDrawerBetType(betTypeLabel || '');
    setDrawerOpen(true);
  };

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent-gold)', animation: 'pulse 1s infinite', flexShrink: 0,
          }} />
          <span style={{ fontSize: 13, color: 'var(--accent-gold)' }}>Secretariat is analyzing…</span>
        </div>
        {[65, 50, 35].map((w, i) => (
          <div key={i} className="skeleton" style={{ height: 12, width: `${w}%`, borderRadius: 4, marginBottom: 8 }} />
        ))}
      </div>
    );
  }

  if (!analysis) return null;

  const modeLabel = MODES.find(m => m.id === mode)?.label || mode;
  const winTellerScript = analysis.teller_script?.win;

  // ── Shared section builders ───────────────────────────────────────────────

  // Panel header (always shown, toggle changes based on experience level).
  // Both children use lineHeight: 1 so flex `center` aligns their visual
  // centers — without it, the display-font SECRETARIAT label has more leading
  // than the badge and they read as misaligned.
  const PanelHeader = () => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, lineHeight: 1, color: 'var(--accent-gold)' }}>
          SECRETARIAT
        </span>
        <span
          className={`badge badge-${analysis.confidence === 'high' ? 'green' : analysis.confidence === 'low' ? 'red' : 'gold'}`}
          style={{ lineHeight: 1, display: 'inline-flex', alignItems: 'center' }}
        >
          {analysis.confidence} confidence
        </span>
      </div>
      {experienceLevel === 'advanced' && (
        <div style={{ display: 'flex', background: 'var(--bg-elevated)', borderRadius: 16, padding: 2, gap: 2 }}>
          {['beginner', 'technical'].map(v => (
            <button key={v} onClick={() => setAdvancedViewMode(v)} style={{
              padding: '4px 10px', borderRadius: 14, border: 'none', fontSize: 11, fontWeight: 600,
              background: effectiveViewMode === v ? 'var(--accent-gold)' : 'transparent',
              color: effectiveViewMode === v ? '#000' : 'var(--text-muted)',
              cursor: 'pointer',
            }}>
              {v === 'beginner' ? 'Plain' : 'Technical'}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  // Top pick hero (used prominently in BEGINNER layout)
  const topPick = analysis.predicted_finish?.first;
  const TopPickHero = () => topPick && (
    <div style={{
      background: 'rgba(201,162,39,0.12)',
      border: '2px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: '14px 16px',
      marginBottom: 12,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-gold)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
        Secretariat's Top Pick
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--accent-gold-bright)', marginBottom: 2 }}>
        {topPick.number ? `${topPick.number} ` : ''}{topPick.horse_name}
      </div>
      {(() => {
        const r = findRunner(topPick.horse_name);
        const odds = r?.odds || r?.sp;
        return odds ? <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--text-secondary)' }}>{odds}</div> : null;
      })()}
    </div>
  );

  // Summary text section
  const SummarySection = ({ forceMode } = {}) => {
    const m = forceMode || effectiveViewMode;
    const text = m === 'beginner'
      ? (analysis.overall_summary_beginner || analysis.overall_summary)
      : analysis.overall_summary;
    return text ? (
      <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 12 }}>{text}</p>
    ) : null;
  };

  // Confidence plain-English explanation
  const ConfidenceSection = () => (
    <div style={{ marginBottom: 10, padding: '8px 12px', background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>
        Confidence: {(analysis.confidence || '').charAt(0).toUpperCase() + (analysis.confidence || '').slice(1)}
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
        {CONFIDENCE_PLAIN[analysis.confidence] || ''}
      </p>
    </div>
  );

  // Teller script section — "Bet at Counter" toggle button for top pick (used in BEGINNER)
  const TellerScriptSection = () => {
    if (!winTellerScript && !topPick) return null;
    const scriptText = winTellerScript?.replace(/^Say to teller:\s*/i, '').trim()
      || (topPick ? `$2 to win on ${topPick.horse_name}` : null);
    if (!scriptText) return null;
    const isOpen = !!tellerOpenMap['win-main'];
    return (
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => toggleTeller('win-main')}
            style={{
              fontSize: 12, fontWeight: 700, padding: '7px 14px', borderRadius: 6,
              border: '1px solid var(--accent-gold)',
              background: 'rgba(201,162,39,0.12)', color: 'var(--accent-gold)',
              cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {isOpen ? 'Hide Script ▲' : 'Bet at Counter ▼'}
          </button>
          {topPick && (
            <button
              onClick={() => openBetOnline(topPick.horse_name, 'Win')}
              style={{
                fontSize: 12, fontWeight: 700, padding: '7px 14px', borderRadius: 6,
                border: '1px solid var(--accent-gold)',
                background: 'rgba(201,162,39,0.12)', color: 'var(--accent-gold)',
                cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              Bet Online →
            </button>
          )}
        </div>
        {isOpen && (
          <div style={{
            marginTop: 8,
            background: 'rgba(201,168,76,0.1)', border: '1px solid #C9A84C',
            borderRadius: 8, padding: '10px 14px',
            fontFamily: 'var(--font-mono)', fontSize: 14,
            color: 'var(--text-primary)', lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
          }}>
            {scriptText}
          </div>
        )}
      </div>
    );
  };

  // Pace scenario
  const PaceSection = () => analysis.pace_scenario ? (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
        Pace Scenario
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-primary)' }}>{analysis.pace_scenario}</p>
    </div>
  ) : null;

  // Predicted finish order
  const PredictedFinishSection = () => analysis.predicted_finish ? (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
        Predicted Finish Order
      </div>
      {['first', 'second', 'third', 'fourth'].map(pos => {
        const p = analysis.predicted_finish[pos];
        if (!p?.horse_name) return null;
        return (
          <div key={pos} style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
            <div style={{
              width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: FINISH_POSITION[pos].bg,
              border: `1px solid ${FINISH_POSITION[pos].border}`,
              color: FINISH_POSITION[pos].color,
              fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 700,
            }}>{FINISH_POSITION[pos].label}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent-gold-bright)' }}>
                {p.number ? `${p.number} ` : ''}{p.horse_name}
              </span>
              {(() => {
                const r = findRunner(p.horse_name);
                const odds = r?.odds || r?.sp;
                return odds ? (
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-gold)', marginLeft: 6 }}>{odds}</span>
                ) : null;
              })()}
              {p.reasoning && effectiveViewMode === 'technical' && (
                <span style={{ fontSize: 12, color: 'var(--text-primary)', marginLeft: 6 }}>— {p.reasoning}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  ) : null;

  const BET_LABELS = {
    win:        'Win — pick the winner',
    place:      'Place — finish in the top 2',
    show:       'Show — finish in the top 3',
    exacta:     'Exacta',
    quinella:   'Quinella',
    trifecta:   'Trifecta',
    superfecta: 'Superfecta',
  };
  const SIMPLE_BETS = ['win', 'place', 'show'];

  const getFallbackScript = (type, selection) => {
    switch (type) {
      case 'win':   return `$2 to win on ${selection}`;
      case 'place': return `$2 to place on ${selection}`;
      case 'show':  return `$2 to show on ${selection}`;
      default:      return `$2 ${type} — ${selection}`;
    }
  };

  const BetRecsSection = () => {
    if (!analysis.bet_recommendations) return null;
    const entries = Object.entries(analysis.bet_recommendations)
      .filter(([type, rec]) => rec?.selection && (effectiveViewMode === 'technical' || SIMPLE_BETS.includes(type)));
    if (entries.length === 0) return null;
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
          Bet Recommendations
        </div>
        {entries.map(([type, rec]) => {
          const raw = analysis.teller_script?.[type];
          const scriptText = raw?.replace(/^Say to teller:\s*/i, '').trim() || getFallbackScript(type, rec.selection);
          const isOpen = !!tellerOpenMap[`bet-${type}`];
          return (
            <div key={type} style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '10px 12px', marginBottom: 8, border: '1px solid var(--border-subtle)' }}>
              {/* Two-column: content left, buttons right */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                {/* Left: bet info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent-gold)', marginBottom: 2 }}>
                    {effectiveViewMode === 'beginner' ? (BET_LABELS[type] || type) : type.charAt(0).toUpperCase() + type.slice(1)}
                    {rec.stake_suggestion && (
                      <span style={{ fontSize: 11, color: 'var(--accent-gold-bright)', fontFamily: 'var(--font-mono)', marginLeft: 8 }}>{rec.stake_suggestion}</span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{rec.selection}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>{rec.reasoning}</div>
                  {rec.box_option && effectiveViewMode === 'technical' && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Box: {rec.box_option}</div>
                  )}
                </div>
                {/* Right: action buttons side by side */}
                <div style={{ display: 'flex', flexDirection: 'row', gap: 5, flexShrink: 0 }}>
                  <button
                    onClick={() => toggleTeller(`bet-${type}`)}
                    style={{
                      fontSize: 11, fontWeight: 700, padding: '6px 10px', borderRadius: 6,
                      border: '1px solid var(--accent-gold)',
                      background: 'rgba(201,162,39,0.12)', color: 'var(--accent-gold)',
                      cursor: 'pointer', whiteSpace: 'nowrap',
                    }}
                  >
                    {isOpen ? 'Hide ▲' : 'Bet at Counter ▼'}
                  </button>
                  <button
                    onClick={() => openBetOnline(rec.selection, BET_LABELS[type] || type)}
                    style={{
                      fontSize: 11, fontWeight: 700, padding: '6px 10px', borderRadius: 6,
                      border: '1px solid var(--accent-gold)',
                      background: 'rgba(201,162,39,0.12)', color: 'var(--accent-gold)',
                      cursor: 'pointer', whiteSpace: 'nowrap',
                    }}
                  >
                    Bet Online →
                  </button>
                </div>
              </div>
              {isOpen && (
                <div style={{
                  marginTop: 8,
                  background: 'rgba(201,168,76,0.1)', border: '1px solid #C9A84C',
                  borderRadius: 6, padding: '8px 12px',
                  fontFamily: 'var(--font-mono)', fontSize: 13,
                  color: 'var(--text-primary)', lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                }}>
                  {scriptText}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  // Legacy recommended_bets (backwards compat)
  const LegacyBetRecsSection = () => {
    if (analysis.bet_recommendations || !analysis.recommended_bets?.length) return null;
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
          Recommended Bets
        </div>
        {analysis.recommended_bets.map((bet, i) => (
          <div key={i} style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '10px 12px', marginBottom: 8, border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent-gold)', marginBottom: 2 }}>
              {bet.bet_type}
              <span className={`badge badge-${bet.risk_level === 'low' ? 'green' : bet.risk_level === 'high' ? 'red' : 'gold'}`} style={{ marginLeft: 6 }}>{bet.risk_level}</span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{bet.selection}</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{bet.reasoning}</div>
          </div>
        ))}
      </div>
    );
  };

  // Pick 3/4/5/6
  const MultiRaceSection = () => analysis.top_contenders?.length > 0 ? (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
        Multi-Race Bets — Pick 3 / 4 / 5 / 6
      </div>
      <div style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--border-subtle)' }}>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>
          {effectiveViewMode === 'beginner'
            ? 'Pick 3/4/5/6 bets require picking the winner of several consecutive races in a row. Use your top selection from this race as one "leg" of your ticket — then pick winners from the next 2–5 races on the card.'
            : 'Sequence bets — use the primary leg single or wheel to the backup for coverage. Stack with other legs from adjacent races.'}
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 80, flexShrink: 0 }}>Top selection</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-gold-bright)' }}>{analysis.top_contenders[0]}</span>
        </div>
        {analysis.top_contenders[1] && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 80, flexShrink: 0 }}>Second pick</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{analysis.top_contenders[1]}</span>
          </div>
        )}
      </div>
    </div>
  ) : null;

  // Beginner tip
  const BeginnerTipSection = () => analysis.beginner_tip ? (
    <div style={{ marginTop: 4, padding: '8px 12px', background: 'rgba(201,162,39,0.08)', borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)', borderLeft: '2px solid var(--accent-gold)', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <Icon name="lightbulb" size={15} color="var(--accent-gold)" style={{ flexShrink: 0, marginTop: 1 }} />
      <span><strong style={{ color: 'var(--accent-gold)' }}>Tip:</strong> {analysis.beginner_tip}</span>
    </div>
  ) : null;

  // Partner cards
  const PartnerCards = () => (
    <>
      {!tgDismissed && ['usa', 'can'].includes((userRegion || '').toLowerCase()) && (
        <div style={{ background: '#1a1a1a', border: '1px solid #C9A84C', borderRadius: 8, padding: 14, marginTop: 12, marginBottom: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Icon name="chart" size={15} /> Want deeper speed figures?
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 10 }}>
                {PARTNERS.thorograph.description}
              </div>
              <button
                onClick={() => { trackEvent('partner_click', { partner: 'thorograph' }); window.open(PARTNERS.thorograph.url, '_blank', 'noopener,noreferrer'); }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#C9A84C', fontSize: 13, fontWeight: 600, padding: 0, textDecoration: 'underline' }}
              >
                {PARTNERS.thorograph.cta} →
              </button>
            </div>
            <button
              onClick={() => { sessionStorage.setItem('gs_tg_dismissed', '1'); setTgDismissed(true); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 18, lineHeight: 1, padding: 4, flexShrink: 0 }}
              aria-label="Dismiss"
            >×</button>
          </div>
        </div>
      )}
      {!wpDismissed && (raceType?.toLowerCase().includes('maiden') || analysis?.overall_summary?.toLowerCase().includes('maiden') || analysis?.overall_summary_beginner?.toLowerCase().includes('maiden')) && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'rgba(201,168,76,0.7)', lineHeight: 1.6, display: 'flex', alignItems: 'flex-start', gap: 6 }}>
          <span>Interested in horses like these?{' '}
            <button
              onClick={() => { trackEvent('partner_click', { partner: 'westpoint' }); window.open(PARTNERS.westpoint.url, '_blank', 'noopener,noreferrer'); sessionStorage.setItem('gs_wp_dismissed', '1'); setWpDismissed(true); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(201,168,76,0.85)', fontSize: 12, padding: 0, textDecoration: 'underline' }}
            >
              West Point Thoroughbreds offers fractional ownership in top-level thoroughbreds. Learn more →
            </button>
          </span>
          <button
            onClick={() => { sessionStorage.setItem('gs_wp_dismissed', '1'); setWpDismissed(true); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 14, padding: '0 0 0 4px', lineHeight: 1 }}
            aria-label="Dismiss"
          >×</button>
        </div>
      )}
    </>
  );

  // Panel wrapper style
  const panelStyle = {
    background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
    border: '1px solid var(--border-gold)',
    borderRadius: 'var(--radius-md)',
    padding: 16,
    marginBottom: 16,
  };

  // ── BEGINNER LAYOUT ────────────────────────────────────────────────────────
  if (experienceLevel === 'beginner') {
    return (
      <div style={panelStyle}>
        <PanelHeader />
        <TopPickHero />
        <SummarySection forceMode="beginner" />
        <ConfidenceSection />
        <TellerScriptSection />

        {/* "Want to understand why?" expandable */}
        <div style={{ marginBottom: 12 }}>
          <button
            onClick={() => setTechExpanded(e => !e)}
            style={{
              background: 'none', border: '1px solid var(--border-subtle)',
              borderRadius: 8, padding: '8px 14px',
              color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600,
              cursor: 'pointer', width: '100%', textAlign: 'left',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}
          >
            <span>Want to understand why?</span>
            <span style={{ fontSize: 10 }}>{techExpanded ? '▲' : '▼'}</span>
          </button>
          {techExpanded && (
            <div style={{ marginTop: 8, padding: '12px', background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
              <PaceSection />
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                {analysis.overall_summary}
              </p>
            </div>
          )}
        </div>

        <PredictedFinishSection />
        <BeginnerTipSection />
        <PartnerCards />
        <AffiliateDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} region={userRegion} recommendedHorse={drawerHorse} recommendedBet={drawerBetType} />
      </div>
    );
  }

  // ── ADVANCED LAYOUT ────────────────────────────────────────────────────────
  return (
    <div style={panelStyle}>
      <PanelHeader />
      <PaceSection />
      <PredictedFinishSection />
      <BetRecsSection />
      <LegacyBetRecsSection />
      <MultiRaceSection />

<BeginnerTipSection />
      <PartnerCards />
      <AffiliateDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} region={userRegion} recommendedHorse={drawerHorse} recommendedBet={drawerBetType} />
    </div>
  );
}

// ── Finished race results panel ───────────────────────────────────────────────
function ResultsPanel({ results }) {
  if (!results?.runners?.length) return null;
  const sorted = [...results.runners]
    .filter(r => r.position && !isNaN(parseInt(r.position)))
    .sort((a, b) => parseInt(a.position) - parseInt(b.position));
  const posStyle = (pos) => {
    const n = parseInt(pos);
    if (n === 1) return { color: '#FFD700', fontWeight: 800 };
    if (n === 2) return { color: '#C0C0C0', fontWeight: 700 };
    if (n === 3) return { color: '#CD7F32', fontWeight: 700 };
    return { color: 'var(--text-muted)', fontWeight: 600 };
  };
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)', padding: 14, marginBottom: 16 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--accent-gold)', marginBottom: 10 }}>OFFICIAL RESULT</div>
      {sorted.map((r, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
          <span style={{ width: 24, fontSize: 14, ...posStyle(r.position) }}>{r.position}</span>
          <span style={{ flex: 1, fontSize: 13, fontWeight: 600 }}>{r.number ? `#${r.number} ` : ''}{r.horse_name || r.horse}</span>
          {(r.sp || r.odds) && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{r.sp || r.odds}</span>}
        </div>
      ))}
    </div>
  );
}

// ── Tab bar ───────────────────────────────────────────────────────────────────
function TabBar({ tabs, active, onChange }) {
  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', marginBottom: 12 }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)} style={{
          flex: 1, padding: '8px 4px', background: 'none', border: 'none',
          borderBottom: active === t.id ? '2px solid var(--accent-gold)' : '2px solid transparent',
          color: active === t.id ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
          fontFamily: 'var(--font-display)', fontSize: 14, letterSpacing: '0.04em',
          cursor: 'pointer', transition: 'all 0.15s',
        }}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function RaceDetailPage() {
  const { raceId } = useParams();
  const navigate = useNavigate();
  const { userProfile, setUserProfile, raceAnalysisCache, setRaceAnalysisCache, clearRaceAnalysisCache, setLastRaceId } = useAppStore();

  useEffect(() => {
    if (raceId) setLastRaceId(raceId);
  }, [raceId, setLastRaceId]);

  const cached = raceAnalysisCache[raceId];
  const CACHE_TTL = 5 * 60 * 1000;
  const validCache = cached && (Date.now() - cached.cachedAt) < CACHE_TTL ? cached : null;

  const [analysisMode, setAnalysisMode] = useState(validCache?.mode || userProfile.riskTolerance || 'medium');

  // Reactive sync: if the user changes Risk Tolerance elsewhere (Profile page,
  // another tab, deep link), reflect it on this page. Cached analysis is kept
  // — the user can re-run when they want analysis at the new mode.
  useEffect(() => {
    if (userProfile.riskTolerance && userProfile.riskTolerance !== analysisMode) {
      setAnalysisMode(userProfile.riskTolerance);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userProfile.riskTolerance]);
  const [analysis, setAnalysis] = useState(validCache?.analysis || null);
  const [analysisStreaming, setAnalysisStreaming] = useState(false);
  const [scorecardData, setScorecardData] = useState(validCache?.scorecardData || null);
  const [analyzeError, setAnalyzeError] = useState(null);
  const [activeTab, setActiveTab] = useState('analysis');
  const [debrief, setDebrief] = useState(null);
  const [debriefLoading, setDebriefLoading] = useState(false);
  const [debriefError, setDebriefError] = useState(null);
  const [debriefPending, setDebriefPending] = useState(false);
  const [raceResults, setRaceResults] = useState(null);
  const [pendingMode, setPendingMode] = useState(null);
  const [bellSubscribed, setBellSubscribed] = useState(() => typeof localStorage !== 'undefined' && localStorage.getItem(`sub:${raceId}`) === 'true');
  const [scorecardOpen, setScorecardOpen] = useState(false);
  const abortRef = useRef(null);

  const runDebrief = async () => {
    setDebriefLoading(true);
    setDebriefError(null);
    setDebriefPending(false);
    try {
      const result = await getRaceDebrief(raceId);
      if (result?.status === 'pending') {
        setDebriefPending(true);
      } else {
        setDebrief(result);
        setActiveTab('debrief');
        trackDebriefViewed(raceId);
      }
    } catch (err) {
      const status = err?.response?.status;
      if (status === 202) {
        setDebriefPending(true);
      } else {
        const detail = err?.response?.data?.detail || err.message || 'Unknown error';
        setDebriefError(detail.includes('not yet available')
          ? 'Results not yet available — check back after the race.'
          : `Debrief failed: ${detail}`);
      }
    } finally {
      setDebriefLoading(false);
    }
  };

  const { data: race, isLoading } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRaceDetail(raceId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || isRaceDefinitelyFinished(data) || !data.off_dt) return false;
      const minsToPost = (new Date(data.off_dt) - Date.now()) / 60000;
      return minsToPost <= 30 && minsToPost > -5 ? 45000 : false;
    },
  });

  useEffect(() => {
    if (race && isRaceDefinitelyFinished(race) && !raceResults) {
      getRaceResults(raceId).then(setRaceResults).catch(() => {});
    }
  }, [race, raceId]); // eslint-disable-line react-hooks/exhaustive-deps

  const runAnalysisAndScore = (mode = analysisMode) => {
    const cached = raceAnalysisCache[raceId];
    if (cached && cached.mode === mode && (Date.now() - cached.cachedAt) < CACHE_TTL) {
      setAnalysis(cached.analysis);
      if (cached.scorecardData) setScorecardData(cached.scorecardData);
      setActiveTab('analysis');
      return;
    }

    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAnalysisStreaming(true);
    setAnalyzeError(null);
    setActiveTab('analysis');

    getScoreCard(raceId)
      .then(data => {
        setScorecardData(data);
        setRaceAnalysisCache(raceId, { ...(raceAnalysisCache[raceId] || {}), scorecardData: data, cachedAt: Date.now() });
        trackScoreCardViewed(raceId);
      })
      .catch(() => {});

    const apiBase = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : '/api';
    fetch(`${apiBase}/advisor/analyze/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        race_id: raceId,
        mode,
        bankroll: userProfile.bankroll || null,
        experience_level: userProfile.experienceLevel || 'beginner',
      }),
      signal: controller.signal,
    }).then(async (res) => {
      if (!res.ok) { throw new Error(`HTTP ${res.status}`); }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') { setAnalysisStreaming(false); return; }
          try {
            const msg = JSON.parse(payload);
            if (msg.result) {
              setAnalysis(msg.result);
              setRaceAnalysisCache(raceId, { analysis: msg.result, mode, scorecardData: null, cachedAt: Date.now() });
              trackRaceAnalysis(raceId, mode);
            }
            if (msg.error) throw new Error(msg.error);
          } catch (e) { if (e.message !== 'JSON parse error') throw e; }
        }
      }
    }).catch((err) => {
      if (err.name === 'AbortError') return;
      const detail = err.message || '';
      const status = err?.response?.status || err?.status;
      setAnalyzeError(
        detail.includes('credit') || status === 402
          ? 'Secretariat needs Anthropic API credits. Add credits at console.anthropic.com.'
          : status === 503 || status === 502
          ? 'Secretariat is temporarily unavailable — try again in a moment.'
          : 'Analysis failed — tap Reset and try again.'
      );
    }).finally(() => {
      setAnalysisStreaming(false);
    });
  };

  const handleModeChange = (newMode) => {
    if (analysis && newMode !== analysisMode) {
      setPendingMode(newMode);
    } else {
      setAnalysisMode(newMode);
      setUserProfile({ riskTolerance: newMode });
    }
  };

  const confirmModeSwitch = () => {
    const mode = pendingMode;
    setPendingMode(null);
    setAnalysisMode(mode);
    setUserProfile({ riskTolerance: mode });
    setAnalysis(null);
    setScorecardData(null);
    runAnalysisAndScore(mode);
  };

  const handleResetAnalysis = async () => {
    try { await clearRaceAnalysis(raceId); } catch { /* ignore */ }
    clearRaceAnalysisCache(raceId);
    setAnalysis(null);
    setScorecardData(null);
    setAnalyzeError(null);
    setActiveTab('analysis');
    runAnalysisAndScore();
  };

  const analyzeMutation = { isPending: analysisStreaming, mutate: () => runAnalysisAndScore() };

  const hasAnalysisTab = !!(analysis || analysisStreaming);
  const hasDebriefTab = !!(debrief || debriefLoading);
  const showTabs = hasAnalysisTab || hasDebriefTab;
  const showAnalyseBtn = !analysis && !analysisStreaming;
  const showDebriefBtn = !debrief && !debriefLoading && !!race && isRaceDefinitelyFinished(race);
  const raceFinished = !!race && isRaceDefinitelyFinished(race);

  const tabs = [
    ...(hasAnalysisTab ? [{ id: 'analysis', label: 'ANALYSIS' }] : []),
    ...(hasDebriefTab  ? [{ id: 'debrief',  label: 'DEBRIEF'  }] : []),
  ];
  const validTab = tabs.find(t => t.id === activeTab) ? activeTab : tabs[0]?.id ?? 'analysis';

  return (
    <div>
      {/* ── Mode-switch confirm modal ─────────────────────────────── */}
      {pendingMode && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
          <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 24, maxWidth: 340, width: '100%', border: '1px solid var(--border-gold)' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', marginBottom: 12 }}>
              Re-run analysis in {MODES.find(m => m.id === pendingMode)?.label} mode?
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
              This will clear the current analysis and scorecard.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setPendingMode(null)}>Cancel</button>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={confirmModeSwitch}>Re-run</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Sticky header ─────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px',
        borderBottom: '1px solid var(--border-subtle)', position: 'sticky',
        top: 0, background: 'var(--bg-primary)', zIndex: 10,
      }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>←</button>
        {race && (() => {
          const { time: displayTime, label: timeLabel } = getDisplayTime(race, userProfile?.timezone);
          return (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--accent-gold)' }}>
                {displayTime}
                {timeLabel && <span style={{ fontSize: 11, fontFamily: 'var(--font-body)', color: 'var(--text-muted)', marginLeft: 4 }}>{timeLabel}</span>}
                {' · '}{race.course}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>{race.title || race.race_name}</div>
            </div>
          );
        })()}
        {/* NotificationBell — top-right of header */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
          <NotificationBell raceId={raceId} raceName={race?.title || race?.race_name || ''} onSubscribe={setBellSubscribed} />
          {race && (
            <span style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: -2, whiteSpace: 'nowrap', display: 'block' }}>
              Alerts
            </span>
          )}
        </div>
      </div>

      <div style={{ padding: '16px' }}>
        {/* ── Race meta ─────────────────────────────────────────────── */}
        {race && !isLoading && (() => {
          const fmtClass = (cls) => {
            if (!cls) return null;
            return cls
              .replace(/\b\w+/g, w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
              .replace(/\(\$?([\d,]+)\)/g, (_, n) => ` ($${parseInt(n.replace(/,/g, ''), 10).toLocaleString()})`);
          };
          const items = [
            (race.distance || race.distance_f) ? formatDistance(race.distance, race.distance_f, race.region) : null,
            race.surface || null,
            race.going ? `Track: ${race.going}` : null,
            fmtClass(race.race_class) || null,
            formatPurse(race) || null,
            race.runners?.length ? `${race.runners.length} runners` : null,
          ].filter(Boolean);
          return (
            <div style={{ display: 'flex', gap: 0, marginBottom: 12, flexWrap: 'nowrap', overflowX: 'auto', alignItems: 'center', whiteSpace: 'nowrap' }}>
              {items.map((item, i) => (
                <span key={i} style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {i > 0 && <span style={{ color: 'var(--accent-gold-dim)', margin: '0 6px' }}>·</span>}
                  {item}
                </span>
              ))}
              {raceFinished && (
                <>
                  <span style={{ color: 'var(--accent-gold-dim)', margin: '0 6px' }}>·</span>
                  <span style={{ fontSize: 13, color: 'var(--accent-gold-bright)', fontWeight: 600 }}>Finished</span>
                </>
              )}
            </div>
          );
        })()}

        {/* ── AccuracyBadge — Secretariat's track record (PART 1C) ── */}
        {race && !raceFinished && (
          <AccuracyBadge
            trackCode={race.track_code || race.course_id || race.course}
            trackName={race.course || race.track}
            compact={false}
          />
        )}

        {/* ── Notification subscription note ────────────────────────── */}
        {race && !raceFinished && bellSubscribed && (
          <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--accent-gold)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🔔</span> You'll be notified 30 min before post
          </div>
        )}

        {/* ── Finished race results ──────────────────────────────────── */}
        {raceFinished && raceResults && <ResultsPanel results={raceResults} />}

        {/* ── Mode selector ──────────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', flexShrink: 0 }}>
            Risk Tolerance
          </span>
          <div style={{ display: 'flex', gap: 6, overflowX: 'auto' }}>
            {MODES.map(m => (
              <button key={m.id} onClick={() => handleModeChange(m.id)} style={{
                flexShrink: 0, padding: '6px 12px', borderRadius: 20, border: '1px solid',
                borderColor: analysisMode === m.id ? 'var(--accent-gold)' : 'var(--border-subtle)',
                background: analysisMode === m.id ? 'rgba(201,162,39,0.12)' : 'transparent',
                color: analysisMode === m.id ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
              }}>
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Action buttons ─────────────────────────────────────────── */}
        <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {showAnalyseBtn && (
            <button className="btn btn-primary btn-full" onClick={() => analyzeMutation.mutate()} disabled={isLoading}>
              Analyze with Secretariat
            </button>
          )}
          {analysis && !analysisStreaming && (
            <button className="btn btn-primary" onClick={handleResetAnalysis} disabled={isLoading} style={{ fontSize: 12, padding: '6px 12px' }}>
              Reset
            </button>
          )}
          {showDebriefBtn && (
            <button className="btn btn-secondary btn-full" onClick={runDebrief} disabled={isLoading} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <Icon name="clipboard" size={15} /> Post-Race Debrief
            </button>
          )}
        </div>

        {/* ── Staleness warning ─────────────────────────────────────── */}
        {analysis && !analysisStreaming && (() => {
          const cached = raceAnalysisCache[raceId];
          if (!cached?.cachedAt) return null;
          const ageMs = Date.now() - cached.cachedAt;
          const ageMin = Math.floor(ageMs / 60000);
          if (ageMin < 30) return null;
          const postMs = race?.off_dt ? new Date(race.off_dt).getTime() : null;
          const minsToPost = postMs ? Math.floor((postMs - Date.now()) / 60000) : null;
          if (minsToPost !== null && (minsToPost > 90 || minsToPost < 0)) return null;
          return (
            <div style={{ padding: '10px 14px', marginBottom: 12, background: 'rgba(201,162,39,0.08)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <span style={{ fontSize: 12, color: 'var(--accent-gold-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Icon name="warning" size={14} /> Analysis is {ageMin} min old — odds may have shifted. Re-run for fresh picks.
              </span>
              <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px', flexShrink: 0 }} onClick={handleResetAnalysis}>Re-run</button>
            </div>
          );
        })()}

        {/* ── Error banners ──────────────────────────────────────────── */}
        {analyzeError && (
          <div style={{ padding: '10px 14px', background: 'rgba(192,57,43,0.08)', border: '1px solid rgba(192,57,43,0.25)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--accent-red-bright)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="warning" size={15} color="var(--accent-red-bright)" /> {analyzeError}
          </div>
        )}
        {debriefPending && (
          <div style={{ padding: '10px 14px', background: 'rgba(201,162,39,0.08)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--accent-gold-bright)', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon name="clock" size={15} /> Results processing — try again in a few minutes</span>
            <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px', flexShrink: 0 }} onClick={runDebrief}>Try Again</button>
          </div>
        )}
        {debriefError && (
          <div style={{ padding: '10px 14px', background: 'rgba(192,57,43,0.08)', border: '1px solid rgba(192,57,43,0.25)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--accent-red-bright)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="warning" size={15} color="var(--accent-red-bright)" /> {debriefError}
          </div>
        )}

        {/* ── Tab panel ─────────────────────────────────────────────── */}
        {showTabs && (
          <div style={{ marginBottom: 16 }}>
            {tabs.length > 1 && <TabBar tabs={tabs} active={validTab} onChange={setActiveTab} />}
            {validTab === 'analysis' && <AnalysisPanel analysis={analysis} loading={analysisStreaming} mode={analysisMode} runners={race?.runners || []} userRegion={userProfile?.region || 'usa'} raceId={raceId} course={race?.course || race?.venue || ''} raceType={race?.race_type || race?.race_class || ''} />}
            {validTab === 'debrief' && <DebriefPanel debrief={debrief} loading={debriefLoading} />}
          </div>
        )}

        {/* ── Runners ───────────────────────────────────────────────── */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 18, letterSpacing: '0.04em' }}>RUNNERS</h3>
            {analysis && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Colored circle = AI contender score (0–100, higher is stronger)
              </span>
            )}
          </div>
          {isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...Array(8)].map((_, i) => <HorseRowSkeleton key={i} />)}
            </div>
          ) : (() => {
            const sortedRunners = [...(race?.runners || [])].sort((a, b) => {
              const parse = r => {
                const raw = String(r.program_number || r.cloth_number || r.stall_number || '99');
                const m = raw.match(/^(\d+)([A-Za-z]*)$/);
                return m ? [parseInt(m[1], 10), m[2].toUpperCase()] : [99, raw];
              };
              const [an, as] = parse(a);
              const [bn, bs] = parse(b);
              return an !== bn ? an - bn : as.localeCompare(bs);
            });

            const baseGroups = {};
            sortedRunners.forEach(r => {
              const base = String(r.program_number || r.cloth_number || '').match(/^(\d+)/)?.[1];
              if (base) { if (!baseGroups[base]) baseGroups[base] = []; baseGroups[base].push(r.horse_id); }
            });
            const coupledIds = new Set();
            Object.values(baseGroups).forEach(ids => { if (ids.length > 1) ids.forEach(id => coupledIds.add(id)); });

            const trainerMap = {};
            const jockeyMap = {};
            const ownerMap = {};
            sortedRunners.forEach(r => {
              const num = r.program_number || r.cloth_number || '?';
              if (r.trainer) {
                if (!trainerMap[r.trainer]) trainerMap[r.trainer] = { nums: [], winPct: r.trainer_14_day_percent };
                trainerMap[r.trainer].nums.push(num);
              }
              if (r.jockey) {
                if (!jockeyMap[r.jockey]) jockeyMap[r.jockey] = { nums: [] };
                jockeyMap[r.jockey].nums.push(num);
              }
              if (r.owner) {
                if (!ownerMap[r.owner]) ownerMap[r.owner] = { nums: [] };
                ownerMap[r.owner].nums.push(num);
              }
            });
            const trainers = Object.entries(trainerMap).sort((a, b) => b[1].nums.length - a[1].nums.length);
            const jockeys  = Object.entries(jockeyMap).sort((a, b) => b[1].nums.length - a[1].nums.length);
            const owners   = Object.entries(ownerMap).sort((a, b) => b[1].nums.length - a[1].nums.length);

            return (
              <>
                {(trainers.length > 0 || jockeys.length > 0 || owners.length > 0) && (
                  <div style={{ marginBottom: 12, borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
                    <div style={{ padding: '8px 14px', background: 'linear-gradient(90deg, rgba(201,162,39,0.12) 0%, rgba(201,162,39,0.04) 100%)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-gold)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{race?.course}</span>
                      <span style={{ width: 1, height: 12, background: 'var(--border-subtle)', flexShrink: 0 }} />
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Trainers & Jockeys</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
                      {trainers.length > 0 && (
                        <div style={{ padding: '10px 14px', borderRight: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Trainers</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {trainers.map(([name, info]) => (
                              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: 'var(--accent-gold-bright)', background: 'rgba(201,162,39,0.1)', border: '1px solid rgba(201,162,39,0.2)', borderRadius: 4, padding: '1px 5px', flexShrink: 0 }}>#{info.nums.join(',')}</span>
                                <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                                {info.winPct != null && <span style={{ fontSize: 10, color: 'var(--accent-green-bright)', fontFamily: 'var(--font-mono)', flexShrink: 0, marginLeft: 'auto' }}>{info.winPct}%</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {jockeys.length > 0 && (
                        <div style={{ padding: '10px 14px' }}>
                          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Jockeys</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {jockeys.map(([name, info]) => (
                              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: 'var(--accent-gold-bright)', background: 'rgba(201,162,39,0.1)', border: '1px solid rgba(201,162,39,0.2)', borderRadius: 4, padding: '1px 5px', flexShrink: 0 }}>#{info.nums.join(',')}</span>
                                <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    {owners.length > 0 && (
                      <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border-subtle)' }}>
                        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Owners</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
                          {owners.map(([name, info]) => (
                            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: 'var(--accent-gold-bright)', background: 'rgba(201,162,39,0.1)', border: '1px solid rgba(201,162,39,0.2)', borderRadius: 4, padding: '1px 5px', flexShrink: 0 }}>#{info.nums.join(',')}</span>
                              <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {sortedRunners.map(horse => (
                    <HorseRow
                      key={horse.horse_id}
                      horse={horse}
                      analysis={analysis}
                      raceId={raceId}
                      scorecards={scorecardData?.scorecards || []}
                      course={race?.course || ''}
                      raceName={race?.title || race?.race_name || ''}
                      region={race?.region || ''}
                      isCoupled={coupledIds.has(horse.horse_id)}
                    />
                  ))}
                </div>

                {scorecardData && (
                  <div style={{ marginTop: 16 }}>
                    <button
                      onClick={() => setScorecardOpen(o => !o)}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 14px', background: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)',
                        color: 'var(--text-primary)', fontSize: 13, fontWeight: 700,
                        cursor: 'pointer', fontFamily: 'var(--font-display)', letterSpacing: '0.04em',
                        marginBottom: scorecardOpen ? 8 : 0,
                      }}
                    >
                      <span>FIELD SCORECARD</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{scorecardOpen ? '▲' : '▼'}</span>
                    </button>
                    {scorecardOpen && <ScorecardPanel raceScorecards={scorecardData} loading={false} runners={race?.runners || []} />}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
