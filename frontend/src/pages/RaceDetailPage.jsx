import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { trackRaceAnalysis, trackScoreCardViewed, trackDebriefViewed } from '../utils/analytics';
import { useQuery } from '@tanstack/react-query';
import { getRaceDetail, getScoreCard, getRaceDebrief, clearRaceAnalysis, getRaceResults } from '../utils/api';
import { HorseRow, HorseRowSkeleton } from '../components/races/HorseRow';
import ScorecardPanel from '../components/races/ScorecardPanel';
import DebriefPanel from '../components/races/DebriefPanel';
import { getDisplayTime, formatDistance, formatPurse, isRaceDefinitelyFinished } from '../components/races/RaceCard';
import { useAppStore } from '../store';
import AffiliateDrawer from '../components/common/AffiliateDrawer';

const MODES = [
  { id: 'safe',       label: '🛡 Safe',       desc: 'Minimize risk'  },
  { id: 'balanced',   label: '⚖️ Balanced',   desc: 'Value + safety' },
  { id: 'aggressive', label: '⚡ Aggressive', desc: 'Max upside'     },
  { id: 'longshot',   label: '🎯 Longshot',   desc: 'Overlay value'  },
];

const FINISH_MEDALS = { first: '🥇', second: '🥈', third: '🥉', fourth: '4️⃣' };

// ── AnalysisPanel ─────────────────────────────────────────────────────────────
function AnalysisPanel({ analysis, loading, mode, runners = [], userRegion = 'usa' }) {
  const [viewMode, setViewMode] = useState('beginner'); // 'technical' | 'beginner'
  const [copied, setCopied] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerHorse, setDrawerHorse] = useState('');
  const [drawerBetType, setDrawerBetType] = useState('');
  const [tellerBet, setTellerBet] = useState(null); // { selection, script }

  // Normalise a name for fuzzy matching (lowercase, strip punctuation/numbers)
  const normName = (s) => (s || '').toLowerCase().replace(/[^a-z\s]/g, '').trim();

  // Find runner by horse name (Secretariat may include number prefix like "4 Best Horse")
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

  const openBetAtCounter = (selection, betTypeKey) => {
    const script = analysis?.teller_script?.[betTypeKey]
      || (selection ? `"$10 ${(betTypeKey || 'win').toUpperCase()} on ${selection}"` : '');
    setTellerBet({ selection, script });
  };

  // Two-button pattern for each recommended bet
  const BetButtons = ({ selection, betTypeKey = 'win', betTypeLabel = '' }) => {
    if (!selection) return null;
    const label = betTypeLabel || betTypeKey;
    return (
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <button
          onClick={(e) => { e.stopPropagation(); openBetOnline(selection, label); }}
          style={{
            fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
            border: '1px solid var(--accent-gold-dim)',
            background: 'rgba(201,162,39,0.1)',
            color: 'var(--accent-gold)', cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          🏦 Bet Online
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); openBetAtCounter(selection, betTypeKey); }}
          style={{
            fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
            border: '1px solid var(--border-subtle)',
            background: 'transparent',
            color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          🎯 Counter
        </button>
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent-gold)',
            animation: 'pulse 1s infinite',
            flexShrink: 0,
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
  const summaryText = viewMode === 'beginner'
    ? (analysis.overall_summary_beginner || analysis.overall_summary)
    : analysis.overall_summary;

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: 16,
      marginBottom: 16,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>
            SECRETARIAT — {modeLabel.replace(/^[^ ]+ /, '').toUpperCase()}
          </span>
          <span className={`badge badge-${analysis.confidence === 'high' ? 'green' : analysis.confidence === 'low' ? 'red' : 'gold'}`}>
            {analysis.confidence} confidence
          </span>
        </div>
        {/* Technical / Beginner toggle */}
        <div style={{ display: 'flex', background: 'var(--bg-elevated)', borderRadius: 16, padding: 2, gap: 2 }}>
          {['beginner', 'technical'].map(v => (
            <button key={v} onClick={() => setViewMode(v)} style={{
              padding: '4px 10px', borderRadius: 14, border: 'none', fontSize: 11, fontWeight: 600,
              background: viewMode === v ? 'var(--accent-gold)' : 'transparent',
              color: viewMode === v ? '#000' : 'var(--text-muted)',
              cursor: 'pointer', textTransform: 'capitalize',
            }}>
              {v === 'beginner' ? '📖 Plain' : '🔬 Technical'}
            </button>
          ))}
        </div>
      </div>

      <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 12 }}>
        {summaryText}
      </p>

      {analysis.pace_scenario && viewMode === 'technical' && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Pace Scenario
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{analysis.pace_scenario}</p>
        </div>
      )}

      {analysis.vulnerable_favorite && (
        <div style={{ background: 'rgba(192,57,43,0.1)', border: '1px solid rgba(192,57,43,0.25)', borderRadius: 8, padding: '8px 12px', marginBottom: 10, fontSize: 13 }}>
          ⚠️ <strong style={{ color: 'var(--accent-red-bright)' }}>
            {viewMode === 'beginner' ? 'The favorite looks beatable:' : 'Vulnerable Favorite:'}
          </strong>{' '}
          <span style={{ color: 'var(--text-secondary)' }}>{analysis.vulnerable_favorite}</span>
          {viewMode === 'beginner' && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              The horse most people are betting on may not win today — consider looking at other runners.
            </div>
          )}
        </div>
      )}

      {analysis.longshot_alert?.horse_name && (
        <div style={{ background: 'rgba(42,122,75,0.1)', border: '1px solid rgba(42,122,75,0.25)', borderRadius: 8, padding: '8px 12px', marginBottom: 10, fontSize: 13 }}>
          🎯 <strong style={{ color: 'var(--accent-green-bright)' }}>
            {viewMode === 'beginner' ? 'Surprise Pick:' : 'Longshot Alert:'}
          </strong>{' '}
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-gold)' }}>{analysis.longshot_alert.odds}</span>{' '}
          <strong>{analysis.longshot_alert.number ? `${analysis.longshot_alert.number} ` : ''}{analysis.longshot_alert.horse_name}</strong>{' '}
          <span style={{ color: 'var(--text-secondary)' }}>— {analysis.longshot_alert.reason}</span>
          {viewMode === 'beginner' && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              A "longshot" is a horse with high odds — not many people are betting on it, but if it wins, the payout is much bigger than the favorite.
            </div>
          )}
        </div>
      )}

      {/* ── Predicted Finish Order ───────────────────────────────── */}
      {analysis.predicted_finish && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Predicted Finish Order
          </div>
          {['first', 'second', 'third', 'fourth'].map(pos => {
            const p = analysis.predicted_finish[pos];
            if (!p?.horse_name) return null;
            const betTypeKey = pos === 'first' ? 'win' : pos === 'second' ? 'place' : 'show';
            const selection = `${p.number ? p.number + ' ' : ''}${p.horse_name}`;
            return (
              <div key={pos} style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 20, lineHeight: 1, flexShrink: 0 }}>{FINISH_MEDALS[pos]}</span>
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
                  {p.reasoning && viewMode === 'technical' && (
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 6 }}>— {p.reasoning}</span>
                  )}
                </div>
                {pos === 'first' && <BetButtons selection={selection} betTypeKey={betTypeKey} betTypeLabel={`${betTypeKey.charAt(0).toUpperCase() + betTypeKey.slice(1)}`} />}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Bet Recommendations ──────────────────────────────────── */}
      {analysis.bet_recommendations && (() => {
        const BET_LABELS = {
          win:        'Win — pick the winner',
          place:      'Place — finish in the top 2',
          show:       'Show — finish in the top 3',
          exacta:     'Exacta',
          trifecta:   'Trifecta',
          superfecta: 'Superfecta',
        };
        const SIMPLE_BETS = ['win', 'place', 'show'];
        const entries = Object.entries(analysis.bet_recommendations)
          .filter(([type, rec]) => rec?.selection && (viewMode === 'technical' || SIMPLE_BETS.includes(type)));
        if (entries.length === 0) return null;
        return (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Bet Recommendations
            </div>
            {entries.map(([type, rec]) => (
              <div key={type} style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '10px 12px', marginBottom: 8, border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4, gap: 8, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent-gold)', marginBottom: 2 }}>
                      {viewMode === 'beginner' ? (BET_LABELS[type] || type) : type.charAt(0).toUpperCase() + type.slice(1)}
                      {rec.stake_suggestion && (
                        <span style={{ fontSize: 11, color: 'var(--accent-gold-bright)', fontFamily: 'var(--font-mono)', marginLeft: 8 }}>{rec.stake_suggestion}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{rec.selection}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{rec.reasoning}</div>
                    {rec.box_option && viewMode === 'technical' && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>📦 {rec.box_option}</div>
                    )}
                  </div>
                  <BetButtons
                    selection={rec.selection}
                    betTypeKey={type}
                    betTypeLabel={BET_LABELS[type] || type}
                  />
                </div>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Legacy recommended_bets (backwards compat with cached responses) */}
      {!analysis.bet_recommendations && analysis.recommended_bets?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Recommended Bets
          </div>
          {analysis.recommended_bets.map((bet, i) => (
            <div key={i} style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '10px 12px', marginBottom: 8, border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4, gap: 8, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent-gold)', marginBottom: 2 }}>
                    {bet.bet_type}
                    <span className={`badge badge-${bet.risk_level === 'low' ? 'green' : bet.risk_level === 'high' ? 'red' : 'gold'}`} style={{ marginLeft: 6 }}>{bet.risk_level}</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{bet.selection}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{bet.reasoning}</div>
                  {bet.suggested_stake && (
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                      Suggested: <span style={{ color: 'var(--accent-gold-bright)', fontFamily: 'var(--font-mono)' }}>{bet.suggested_stake}</span>
                    </div>
                  )}
                </div>
                <BetButtons
                  selection={bet.selection}
                  betTypeKey={(bet.bet_type || 'win').toLowerCase()}
                  betTypeLabel={bet.bet_type || 'Win'}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Pick 3 / 4 / 5 / 6 ─────────────────────────────────── */}
      {analysis.top_contenders?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Multi-Race Bets — Pick 3 / 4 / 5 / 6
          </div>
          <div style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--border-subtle)' }}>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>
              {viewMode === 'beginner'
                ? 'Pick 3/4/5/6 bets require picking the winner of several consecutive races in a row. Use your top selection from this race as one "leg" of your ticket — then pick winners from the next 2–5 races on the card.'
                : 'Sequence bets — use the primary leg single or wheel to the backup for coverage. Stack with other legs from adjacent races.'}
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 80, flexShrink: 0 }}>Primary leg</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-gold-bright)' }}>{analysis.top_contenders[0]}</span>
            </div>
            {analysis.top_contenders[1] && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 80, flexShrink: 0 }}>Backup leg</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{analysis.top_contenders[1]}</span>
              </div>
            )}
            {viewMode === 'beginner' && (
              <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(26,107,168,0.1)', borderRadius: 6, fontSize: 11, color: 'var(--accent-blue-bright)', lineHeight: 1.5 }}>
                💡 At the window: <em>"$2 Pick 3, [horse #] in this race, [pick for next race], [pick for race after], Race [N]"</em>
              </div>
            )}
          </div>
        </div>
      )}

      {analysis.beginner_tip && (
        <div style={{ marginTop: 4, padding: '8px 12px', background: 'rgba(26,107,168,0.1)', borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)', borderLeft: '2px solid var(--accent-blue)' }}>
          💡 <strong style={{ color: 'var(--accent-blue-bright)' }}>Beginner tip:</strong> {analysis.beginner_tip}
        </div>
      )}

      {/* ── Single-bet teller modal ───────────────────────────────── */}
      {tellerBet && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9000, padding: '24px 16px' }}
          onClick={() => setTellerBet(null)}>
          <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-lg)', padding: 24, width: '100%', maxWidth: 440, boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, marginBottom: 8 }}>Bet at Counter</div>
            {drawerHorse && (
              <div style={{ fontSize: 13, color: 'var(--accent-gold-bright)', marginBottom: 12 }}>
                Secretariat recommends: <strong>{tellerBet.selection}</strong>
              </div>
            )}
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>Read this aloud at the teller window:</p>
            <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', padding: 14, fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 1.8, marginBottom: 14, border: '1px solid var(--border-subtle)', whiteSpace: 'pre-wrap' }}>
              {tellerBet.script}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => { navigator.clipboard?.writeText(tellerBet.script).catch(() => {}); setCopied('teller'); setTimeout(() => setCopied(null), 1500); }}>
                {copied === 'teller' ? '✓ Copied' : 'Copy'}
              </button>
              <button className="btn" style={{ flex: 1, border: '1px solid var(--border-subtle)' }} onClick={() => setTellerBet(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Affiliate drawer (Bet Online) ─────────────────────────── */}
      <AffiliateDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        region={userRegion}
        recommendedHorse={drawerHorse}
        recommendedBet={drawerBetType}
      />
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
  const { userProfile, raceAnalysisCache, setRaceAnalysisCache, clearRaceAnalysisCache } = useAppStore();

  // Restore analysis state from in-memory cache (survives navigating to horse profile and back)
  const cached = raceAnalysisCache[raceId];
  const CACHE_TTL = 5 * 60 * 1000; // 5 minutes — matches server cache
  const validCache = cached && (Date.now() - cached.cachedAt) < CACHE_TTL ? cached : null;

  const [analysisMode, setAnalysisMode] = useState(validCache?.mode || 'balanced');
  const [analysis, setAnalysis] = useState(validCache?.analysis || null);
  const [analysisStreaming, setAnalysisStreaming] = useState(false);
  const [scorecardData, setScorecardData] = useState(validCache?.scorecardData || null);
  const [analyzeError, setAnalyzeError] = useState(null);
  const [activeTab, setActiveTab] = useState(validCache ? 'analysis' : 'analysis');
  const [debrief, setDebrief] = useState(null);
  const [debriefLoading, setDebriefLoading] = useState(false);
  const [debriefError, setDebriefError] = useState(null);
  const [debriefPending, setDebriefPending] = useState(false);
  const [raceResults, setRaceResults] = useState(null);
  // Mode-switch confirmation
  const [pendingMode, setPendingMode] = useState(null);
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
    // Poll every 45 s within the 30-min window before post time; stop once finished
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || isRaceDefinitelyFinished(data) || !data.off_dt) return false;
      const minsToPost = (new Date(data.off_dt) - Date.now()) / 60000;
      return minsToPost <= 30 && minsToPost > -5 ? 45000 : false;
    },
  });

  // Auto-load official results when a finished race is loaded (onSuccess removed in RQ v5)
  useEffect(() => {
    if (race && isRaceDefinitelyFinished(race) && !raceResults) {
      getRaceResults(raceId).then(setRaceResults).catch(() => {});
    }
  }, [race, raceId]); // eslint-disable-line react-hooks/exhaustive-deps

  // B1: Fire analysis + scorecard concurrently
  const runAnalysisAndScore = (mode = analysisMode) => {
    // Check 5-min cache before firing API — same race + same mode = serve cached result
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

    // Fire scorecard in parallel (non-blocking)
    getScoreCard(raceId)
      .then(data => {
        setScorecardData(data);
        setRaceAnalysisCache(raceId, {
          ...(raceAnalysisCache[raceId] || {}),
          scorecardData: data,
          cachedAt: Date.now(),
        });
        trackScoreCardViewed(raceId);
      })
      .catch(() => {});

    const apiBase = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : '/api';
    fetch(`${apiBase}/advisor/analyze/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ race_id: raceId, mode, bankroll: userProfile.bankroll || null }),
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
      const detail = err.message || 'Unknown error';
      setAnalyzeError(
        detail.includes('credit')
          ? 'Secretariat needs Anthropic API credits. Add credits at console.anthropic.com.'
          : `Analysis failed: ${detail}`
      );
    }).finally(() => {
      setAnalysisStreaming(false);
    });
  };

  // B2: Mode switch — if analysis already exists, confirm re-run
  const handleModeChange = (newMode) => {
    if (analysis && newMode !== analysisMode) {
      setPendingMode(newMode);
    } else {
      setAnalysisMode(newMode);
    }
  };

  const confirmModeSwitch = () => {
    const mode = pendingMode;
    setPendingMode(null);
    setAnalysisMode(mode);
    setAnalysis(null);
    setScorecardData(null);
    runAnalysisAndScore(mode);
  };

  // C6: Reset analysis
  const handleResetAnalysis = async () => {
    try { await clearRaceAnalysis(raceId); } catch { /* ignore */ }
    clearRaceAnalysisCache(raceId);
    setAnalysis(null);
    setScorecardData(null);
    setAnalyzeError(null);
    setActiveTab('analysis');
  };

  const analyzeMutation = { isPending: analysisStreaming, mutate: () => runAnalysisAndScore() };

  const hasAnalysisTab = !!(analysis || analysisStreaming);
  const hasScorecardTab = !!(scorecardData);
  const hasDebriefTab = !!(debrief || debriefLoading);
  const showTabs = hasAnalysisTab || hasScorecardTab || hasDebriefTab;

  const showAnalyseBtn = !analysis && !analysisStreaming;
  const showDebriefBtn = !debrief && !debriefLoading && !!race && isRaceDefinitelyFinished(race);
  const raceFinished = !!race && isRaceDefinitelyFinished(race);

  const tabs = [
    ...(hasAnalysisTab  ? [{ id: 'analysis',  label: 'ANALYSIS'   }] : []),
    ...(hasScorecardTab ? [{ id: 'scorecard', label: 'SCORE CARD' }] : []),
    ...(hasDebriefTab   ? [{ id: 'debrief',   label: 'DEBRIEF'    }] : []),
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
      </div>

      <div style={{ padding: '16px' }}>
        {/* ── Race meta ─────────────────────────────────────────────── */}
        {race && !isLoading && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', fontSize: 13, color: 'var(--text-secondary)' }}>
            {(race.distance || race.distance_f) && <span>📏 {formatDistance(race.distance, race.distance_f, race.region)}</span>}
            {race.surface && <span>🌿 {race.surface}</span>}
            {race.going && <span>🏁 Track: {race.going}</span>}
            {race.race_class && (() => {
              const m = race.race_class.match(/^(.+?)\s+(CLAIMING\(\$[\d,]+\))$/i);
              return m ? (
                <span>🏷 {m[1]} <span style={{ color: 'var(--border-medium)', margin: '0 2px' }}>|</span> {m[2]}</span>
              ) : (
                <span>🏷 {race.race_class}</span>
              );
            })()}
            {formatPurse(race) && <span>💰 {formatPurse(race)}</span>}
            {race.runners?.length && <span>🏇 {race.runners.length} runners</span>}
            {raceFinished && <span style={{ color: 'var(--accent-gold-bright)', fontWeight: 600 }}>✓ Finished</span>}
          </div>
        )}

        {/* ── Finished race results ──────────────────────────────────── */}
        {raceFinished && raceResults && <ResultsPanel results={raceResults} />}

        {/* ── Mode selector (always visible) ────────────────────────── */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Analysis Mode</div>
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
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {showAnalyseBtn && (
            <button className="btn btn-primary btn-full" onClick={() => analyzeMutation.mutate()} disabled={isLoading}>
              Analyse with Secretariat
            </button>
          )}
          {analysis && !analysisStreaming && (
            <button className="btn btn-ghost" onClick={handleResetAnalysis} style={{ fontSize: 12, padding: '6px 12px' }}>
              Reset
            </button>
          )}
          {showDebriefBtn && (
            <button className="btn btn-secondary btn-full" onClick={runDebrief} disabled={isLoading}>
              📋 Post-Race Debrief
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
          // Check if race is within 90 minutes of post
          const postMs = race?.off_dt ? new Date(race.off_dt).getTime() : null;
          const minsToPost = postMs ? Math.floor((postMs - Date.now()) / 60000) : null;
          if (minsToPost !== null && (minsToPost > 90 || minsToPost < 0)) return null;
          return (
            <div style={{
              padding: '10px 14px', marginBottom: 12,
              background: 'rgba(201,162,39,0.08)',
              border: '1px solid var(--border-gold)',
              borderRadius: 'var(--radius-md)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
            }}>
              <span style={{ fontSize: 12, color: 'var(--accent-gold-bright)' }}>
                ⚠️ Analysis is {ageMin} min old — odds may have shifted. Re-run for fresh picks.
              </span>
              <button
                className="btn btn-ghost"
                style={{ fontSize: 11, padding: '4px 10px', flexShrink: 0 }}
                onClick={handleResetAnalysis}
              >
                Re-run
              </button>
            </div>
          );
        })()}

        {/* ── Error banners ──────────────────────────────────────────── */}
        {analyzeError && (
          <div style={{ padding: '10px 14px', background: 'rgba(192,57,43,0.08)', border: '1px solid rgba(192,57,43,0.25)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--accent-red-bright)', marginBottom: 12 }}>
            ⚠️ {analyzeError}
          </div>
        )}
        {debriefPending && (
          <div style={{ padding: '10px 14px', background: 'rgba(201,162,39,0.08)', border: '1px solid var(--border-gold)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--accent-gold-bright)', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
            <span>⏳ Results processing — try again in a few minutes</span>
            <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px', flexShrink: 0 }} onClick={runDebrief}>Try Again</button>
          </div>
        )}
        {debriefError && (
          <div style={{ padding: '10px 14px', background: 'rgba(192,57,43,0.08)', border: '1px solid rgba(192,57,43,0.25)', borderRadius: 'var(--radius-md)', fontSize: 13, color: 'var(--accent-red-bright)', marginBottom: 12 }}>
            ⚠️ {debriefError}
          </div>
        )}

        {/* ── Tab panel ─────────────────────────────────────────────── */}
        {showTabs && (
          <div style={{ marginBottom: 16 }}>
            {tabs.length > 1 && <TabBar tabs={tabs} active={validTab} onChange={setActiveTab} />}
            {validTab === 'analysis' && <AnalysisPanel analysis={analysis} loading={analysisStreaming} mode={analysisMode} runners={race?.runners || []} userRegion={userProfile?.region || 'usa'} />}
            {validTab === 'scorecard' && <ScorecardPanel raceScorecards={scorecardData} loading={false} runners={race?.runners || []} />}
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
            // Sort by program number (handles "1", "1A", "2", "10" correctly)
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

            // Detect coupled entries (same base number, e.g. "1" and "1A")
            const baseGroups = {};
            sortedRunners.forEach(r => {
              const base = String(r.program_number || r.cloth_number || '').match(/^(\d+)/)?.[1];
              if (base) { if (!baseGroups[base]) baseGroups[base] = []; baseGroups[base].push(r.horse_id); }
            });
            const coupledIds = new Set();
            Object.values(baseGroups).forEach(ids => { if (ids.length > 1) ids.forEach(id => coupledIds.add(id)); });

            // Race connections summary (trainers + jockeys + owners)
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
            const jockeys  = Object.entries(jockeyMap).sort((a, b)  => b[1].nums.length - a[1].nums.length);
            const owners   = Object.entries(ownerMap).sort((a, b)   => b[1].nums.length - a[1].nums.length);

            return (
              <>
                {/* Trainer / Jockey connections */}
                {(trainers.length > 0 || jockeys.length > 0 || owners.length > 0) && (
                  <div style={{ marginBottom: 12, borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
                    {/* Header */}
                    <div style={{
                      padding: '8px 14px',
                      background: 'linear-gradient(90deg, rgba(201,162,39,0.12) 0%, rgba(201,162,39,0.04) 100%)',
                      borderBottom: '1px solid var(--border-subtle)',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-gold)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {race?.course}
                      </span>
                      <span style={{ width: 1, height: 12, background: 'var(--border-subtle)', flexShrink: 0 }} />
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Trainers & Jockeys</span>
                    </div>

                    {/* Trainers | Jockeys */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
                      {trainers.length > 0 && (
                        <div style={{ padding: '10px 14px', borderRight: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                            Trainers
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {trainers.map(([name, info]) => (
                              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{
                                  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                                  color: 'var(--accent-gold-bright)',
                                  background: 'rgba(201,162,39,0.1)',
                                  border: '1px solid rgba(201,162,39,0.2)',
                                  borderRadius: 4, padding: '1px 5px', flexShrink: 0,
                                }}>
                                  #{info.nums.join(',')}
                                </span>
                                <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {name}
                                </span>
                                {info.winPct != null && (
                                  <span style={{ fontSize: 10, color: 'var(--accent-green-bright)', fontFamily: 'var(--font-mono)', flexShrink: 0, marginLeft: 'auto' }}>
                                    {info.winPct}%
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {jockeys.length > 0 && (
                        <div style={{ padding: '10px 14px' }}>
                          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                            Jockeys
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {jockeys.map(([name, info]) => (
                              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{
                                  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                                  color: 'var(--accent-gold-bright)',
                                  background: 'rgba(201,162,39,0.1)',
                                  border: '1px solid rgba(201,162,39,0.2)',
                                  borderRadius: 4, padding: '1px 5px', flexShrink: 0,
                                }}>
                                  #{info.nums.join(',')}
                                </span>
                                <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {name}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Owners — full width below */}
                    {owners.length > 0 && (
                      <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border-subtle)' }}>
                        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                          Owners
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
                          {owners.map(([name, info]) => (
                            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{
                                fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                                color: 'var(--accent-gold-bright)',
                                background: 'rgba(201,162,39,0.1)',
                                border: '1px solid rgba(201,162,39,0.2)',
                                borderRadius: 4, padding: '1px 5px', flexShrink: 0,
                              }}>
                                #{info.nums.join(',')}
                              </span>
                              <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {name}
                              </span>
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
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
