import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getRaceDetail, getScoreCard } from '../utils/api';
import { HorseRow, HorseRowSkeleton } from '../components/races/HorseRow';
import ScorecardPanel from '../components/races/ScorecardPanel';
import { getDisplayTime, formatDistance, formatPurse } from '../components/races/RaceCard';
import { useAppStore } from '../store';

const MODES = [
  { id: 'safe',       label: '🛡 Safe',       desc: 'Minimize risk'  },
  { id: 'balanced',   label: '⚖️ Balanced',   desc: 'Value + safety' },
  { id: 'aggressive', label: '⚡ Aggressive', desc: 'Max upside'     },
  { id: 'longshot',   label: '🎯 Longshot',   desc: 'Overlay value'  },
];

// ── Inline AnalysisPanel (kept local — no separate file) ──────────────────────
function AnalysisPanel({ analysis, loading }) {
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

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: 16,
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>
          SECRETARIAT ANALYSIS
        </span>
        <span className={`badge badge-${analysis.confidence === 'high' ? 'green' : analysis.confidence === 'low' ? 'red' : 'gold'}`}>
          {analysis.confidence} confidence
        </span>
      </div>

      <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 12 }}>
        {analysis.overall_summary}
      </p>

      {analysis.pace_scenario && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Pace Scenario
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{analysis.pace_scenario}</p>
        </div>
      )}

      {analysis.vulnerable_favorite && (
        <div style={{
          background: 'rgba(192,57,43,0.1)',
          border: '1px solid rgba(192,57,43,0.25)',
          borderRadius: 8,
          padding: '8px 12px',
          marginBottom: 10,
          fontSize: 13,
        }}>
          ⚠️ <strong style={{ color: 'var(--accent-red-bright)' }}>Vulnerable Favorite:</strong>{' '}
          <span style={{ color: 'var(--text-secondary)' }}>{analysis.vulnerable_favorite}</span>
        </div>
      )}

      {analysis.longshot_alert?.horse_name && (
        <div style={{
          background: 'rgba(42,122,75,0.1)',
          border: '1px solid rgba(42,122,75,0.25)',
          borderRadius: 8,
          padding: '8px 12px',
          marginBottom: 10,
          fontSize: 13,
        }}>
          🎯 <strong style={{ color: 'var(--accent-green-bright)' }}>Longshot Alert:</strong>{' '}
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-gold)' }}>{analysis.longshot_alert.odds}</span>{' '}
          <strong>{analysis.longshot_alert.horse_name}</strong>{' '}
          <span style={{ color: 'var(--text-secondary)' }}>— {analysis.longshot_alert.reason}</span>
        </div>
      )}

      {analysis.recommended_bets?.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Recommended Bets
          </div>
          {analysis.recommended_bets.map((bet, i) => (
            <div key={i} style={{
              background: 'var(--bg-card)',
              borderRadius: 8,
              padding: '10px 12px',
              marginBottom: 8,
              border: '1px solid var(--border-subtle)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent-gold)' }}>{bet.bet_type}</span>
                <span className={`badge badge-${bet.risk_level === 'low' ? 'green' : bet.risk_level === 'high' ? 'red' : 'gold'}`}>
                  {bet.risk_level}
                </span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{bet.selection}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{bet.reasoning}</div>
              {bet.suggested_stake && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  Suggested stake: <span style={{ color: 'var(--accent-gold-bright)', fontFamily: 'var(--font-mono)' }}>{bet.suggested_stake}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {analysis.beginner_tip && (
        <div style={{
          marginTop: 12,
          padding: '8px 12px',
          background: 'rgba(26,107,168,0.1)',
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--text-secondary)',
          borderLeft: '2px solid var(--accent-blue)',
        }}>
          💡 <strong style={{ color: 'var(--accent-blue-bright)' }}>Beginner tip:</strong> {analysis.beginner_tip}
        </div>
      )}
    </div>
  );
}

// ── Tab bar ───────────────────────────────────────────────────────────────────
function TabBar({ tabs, active, onChange }) {
  return (
    <div style={{
      display: 'flex',
      borderBottom: '1px solid var(--border-subtle)',
      marginBottom: 12,
    }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            flex: 1,
            padding: '8px 4px',
            background: 'none',
            border: 'none',
            borderBottom: active === t.id ? '2px solid var(--accent-gold)' : '2px solid transparent',
            color: active === t.id ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
            fontFamily: 'var(--font-display)',
            fontSize: 14,
            letterSpacing: '0.04em',
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
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
  const { userProfile } = useAppStore();
  const [analysisMode, setAnalysisMode] = useState('balanced');
  const [analysis, setAnalysis] = useState(null);
  const [analysisStreaming, setAnalysisStreaming] = useState(false);
  const [scorecardData, setScorecardData] = useState(null);
  const [analyzeError, setAnalyzeError] = useState(null);
  const [scoreError, setScoreError] = useState(null);
  const [activeTab, setActiveTab] = useState('analysis');
  const abortRef = useRef(null);

  const { data: race, isLoading } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRaceDetail(raceId),
  });

  const runAnalysis = () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAnalysisStreaming(true);
    setAnalyzeError(null);
    setActiveTab('analysis');

    fetch('/api/advisor/analyze/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ race_id: raceId, mode: analysisMode, bankroll: userProfile.bankroll || null }),
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
            if (msg.result) { setAnalysis(msg.result); }
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

  // shim so the rest of the page can still check isPending
  const analyzeMutation = { isPending: analysisStreaming, mutate: runAnalysis };

  const scoreMutation = useMutation({
    mutationFn: () => getScoreCard(raceId),
    onSuccess: (data) => {
      setScorecardData(data);
      setScoreError(null);
      setActiveTab('scorecard');
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail || err.message || 'Unknown error';
      setScoreError(
        detail.includes('credit')
          ? 'Secretariat needs Anthropic API credits. Add credits at console.anthropic.com.'
          : `Scoring failed: ${detail}`
      );
    },
  });

  // What tabs exist right now
  const hasAnalysisTab = !!(analysis || analyzeMutation.isPending);
  const hasScorecardTab = !!(scorecardData || scoreMutation.isPending);
  const showTabs = hasAnalysisTab || hasScorecardTab;

  // Which action buttons to show
  const showAnalyseBtn = !analysis && !analyzeMutation.isPending;
  const showScoreBtn   = !scorecardData && !scoreMutation.isPending;
  const showActionArea = showAnalyseBtn || showScoreBtn;

  const tabs = [
    ...(hasAnalysisTab  ? [{ id: 'analysis',  label: 'ANALYSIS'   }] : []),
    ...(hasScorecardTab ? [{ id: 'scorecard', label: 'SCORE CARD' }] : []),
  ];

  // Keep activeTab valid whenever tabs change
  const validTab = tabs.find(t => t.id === activeTab) ? activeTab : tabs[0]?.id ?? 'analysis';

  return (
    <div>
      {/* ── Sticky header ─────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '14px 16px',
        borderBottom: '1px solid var(--border-subtle)',
        position: 'sticky',
        top: 0,
        background: 'var(--bg-primary)',
        zIndex: 10,
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}
        >
          ←
        </button>
        {race && (() => {
          const { time: displayTime, label: timeLabel } = getDisplayTime(race);
          return (
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--accent-gold)' }}>
                {displayTime}
                {timeLabel && (
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-body)', color: 'var(--text-muted)', marginLeft: 4 }}>
                    {timeLabel}
                  </span>
                )}
                {' · '}{race.course}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>
                {race.title || race.race_name}
              </div>
            </div>
          );
        })()}
      </div>

      <div style={{ padding: '16px' }}>
        {/* ── Race meta ─────────────────────────────────────────────── */}
        {race && !isLoading && (
          <div style={{
            display: 'flex',
            gap: 12,
            marginBottom: 16,
            flexWrap: 'wrap',
            fontSize: 13,
            color: 'var(--text-secondary)',
          }}>
            {(race.distance || race.distance_f) && <span>📏 {formatDistance(race.distance, race.distance_f)}</span>}
            {race.surface && <span>🌿 {race.surface}</span>}
            {race.going && <span>⛅ Going: {race.going}</span>}
            {formatPurse(race) && <span>💰 {formatPurse(race)}</span>}
            {race.runners?.length && <span>🏇 {race.runners.length} runners</span>}
          </div>
        )}

        {/* ── Action buttons ─────────────────────────────────────────── */}
        {showActionArea && (
          <div style={{ marginBottom: 16 }}>
            {/* Mode selector — only relevant for analysis */}
            {showAnalyseBtn && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  Analysis Mode
                </div>
                <div style={{ display: 'flex', gap: 6, overflowX: 'auto' }}>
                  {MODES.map(m => (
                    <button
                      key={m.id}
                      onClick={() => setAnalysisMode(m.id)}
                      style={{
                        flexShrink: 0,
                        padding: '6px 12px',
                        borderRadius: 20,
                        border: '1px solid',
                        borderColor: analysisMode === m.id ? 'var(--accent-gold)' : 'var(--border-subtle)',
                        background: analysisMode === m.id ? 'rgba(201,162,39,0.12)' : 'transparent',
                        color: analysisMode === m.id ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              {showAnalyseBtn && (
                <button
                  className="btn btn-primary btn-full"
                  onClick={() => analyzeMutation.mutate()}
                  disabled={isLoading}
                >
                  Analyse with Secretariat
                </button>
              )}
              {showScoreBtn && (
                <button
                  className="btn btn-secondary btn-full"
                  onClick={() => scoreMutation.mutate()}
                  disabled={isLoading}
                >
                  Score the Field
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Error banners ──────────────────────────────────────────── */}
        {analyzeError && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(192,57,43,0.08)',
            border: '1px solid rgba(192,57,43,0.25)',
            borderRadius: 'var(--radius-md)',
            fontSize: 13,
            color: 'var(--accent-red-bright)',
            marginBottom: 12,
          }}>
            ⚠️ {analyzeError}
          </div>
        )}
        {scoreError && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(192,57,43,0.08)',
            border: '1px solid rgba(192,57,43,0.25)',
            borderRadius: 'var(--radius-md)',
            fontSize: 13,
            color: 'var(--accent-red-bright)',
            marginBottom: 12,
          }}>
            ⚠️ {scoreError}
          </div>
        )}

        {/* ── Tab panel ─────────────────────────────────────────────── */}
        {showTabs && (
          <div style={{ marginBottom: 16 }}>
            {tabs.length > 1 && (
              <TabBar tabs={tabs} active={validTab} onChange={setActiveTab} />
            )}
            {validTab === 'analysis' && (
              <AnalysisPanel analysis={analysis} loading={analyzeMutation.isPending} />
            )}
            {validTab === 'scorecard' && (
              <ScorecardPanel raceScorecards={scorecardData} loading={scoreMutation.isPending} />
            )}
          </div>
        )}

        {/* ── Runners ───────────────────────────────────────────────── */}
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 18, marginBottom: 10, letterSpacing: '0.04em' }}>
            RUNNERS
          </h3>
          {isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...Array(8)].map((_, i) => <HorseRowSkeleton key={i} />)}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(race?.runners || []).map(horse => (
                <HorseRow
                  key={horse.horse_id}
                  horse={horse}
                  analysis={analysis}
                  raceId={raceId}
                  scorecards={scorecardData?.scorecards || []}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
