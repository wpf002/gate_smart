import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getRaceDetail, analyzeRace } from '../utils/api';
import { HorseRow, HorseRowSkeleton } from '../components/races/HorseRow';
import { useAppStore } from '../store';

const MODES = [
  { id: 'safe', label: '🛡 Safe', desc: 'Minimize risk' },
  { id: 'balanced', label: '⚖️ Balanced', desc: 'Value + safety' },
  { id: 'aggressive', label: '⚡ Aggressive', desc: 'Max upside' },
  { id: 'longshot', label: '🎯 Longshot', desc: 'Overlay value' },
];

function AnalysisPanel({ analysis, loading }) {
  if (loading) {
    return (
      <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent-gold)',
            animation: 'pulse 1s infinite',
          }} />
          <span style={{ fontSize: 13, color: 'var(--accent-gold)' }}>Secretariat is analyzing this race…</span>
        </div>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 14, width: `${80 - i * 15}%`, borderRadius: 4, marginBottom: 8 }} />
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

export default function RaceDetailPage() {
  const { raceId } = useParams();
  const navigate = useNavigate();
  const { userProfile } = useAppStore();
  const [analysisMode, setAnalysisMode] = useState('balanced');
  const [analysis, setAnalysis] = useState(null);

  const { data: race, isLoading } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRaceDetail(raceId),
  });

  const [analyzeError, setAnalyzeError] = useState(null);

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeRace(raceId, analysisMode, userProfile.bankroll),
    onSuccess: (data) => { setAnalysis(data); setAnalyzeError(null); },
    onError: (err) => {
      const detail = err?.response?.data?.detail || err.message || 'Unknown error';
      setAnalyzeError(
        detail.includes('credit')
          ? 'Secretariat needs Anthropic API credits. Add credits at console.anthropic.com.'
          : `Analysis failed: ${detail}`
      );
    },
  });

  return (
    <div>
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
        {race && (
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--accent-gold)' }}>
              {race.time} · {race.course}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>
              {race.title || race.race_name}
            </div>
          </div>
        )}
      </div>

      <div style={{ padding: '16px' }}>
        {race && !isLoading && (
          <div style={{
            display: 'flex',
            gap: 12,
            marginBottom: 16,
            flexWrap: 'wrap',
            fontSize: 13,
            color: 'var(--text-secondary)',
          }}>
            {race.distance && <span>📏 {race.distance}</span>}
            {race.surface && <span>🌿 {race.surface}</span>}
            {race.going && <span>⛅ Going: {race.going}</span>}
            {race.purse && <span>💰 {race.purse}</span>}
            {race.runners?.length && <span>🏇 {race.runners.length} runners</span>}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          {!analysis && !analyzeMutation.isPending && (
            <div>
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
              <button
                className="btn btn-primary btn-full"
                onClick={() => analyzeMutation.mutate()}
                disabled={isLoading}
              >
                🤖 Analyze with Secretariat
              </button>
            </div>
          )}

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
          <AnalysisPanel analysis={analysis} loading={analyzeMutation.isPending} />
        </div>

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
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
