import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store';

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

export function HorseRow({ horse, analysis, raceId }) {
  const navigate = useNavigate();
  const addToBetSlip = useAppStore((s) => s.addToBetSlip);
  const betSlip = useAppStore((s) => s.betSlip);
  const [added, setAdded] = useState(false);

  // Find this horse in analysis runners if available
  const analysisData = analysis?.runners?.find(
    (r) => r.horse_id === horse.horse_id || r.horse_name === horse.horse_name
  );

  const score = analysisData?.contender_score;
  const scoreClass =
    score >= 70 ? 'score-high' : score >= 40 ? 'score-med' : score != null ? 'score-low' : null;

  const isInSlip = betSlip.some(
    (b) => b.horse_id === horse.horse_id
  );

  const handleAddBet = (e) => {
    e.stopPropagation();
    addToBetSlip({
      horse_id: horse.horse_id,
      horse_name: horse.horse_name,
      race_id: raceId,
      bet_type: analysisData?.recommended_bet || 'win',
      odds: horse.odds || horse.sp || '?',
      stake: 10,
    });
    setAdded(true);
    setTimeout(() => setAdded(false), 1500);
  };

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-md)',
        padding: '12px',
        border: '1px solid var(--border-subtle)',
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
      onClick={() => navigate(`/horse/${horse.horse_id}`)}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-card)')}
    >
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        {/* Score ring */}
        {scoreClass ? (
          <div className={`score-ring ${scoreClass}`}>{score}</div>
        ) : (
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            background: 'var(--bg-elevated)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-display)', fontSize: 16,
            color: 'var(--text-muted)',
            flexShrink: 0,
          }}>
            {horse.cloth_number || horse.stall_number || '?'}
          </div>
        )}

        {/* Horse info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontWeight: 700,
            fontSize: 14,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {horse.horse_name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {[horse.jockey, horse.trainer].filter(Boolean).join(' · ')}
          </div>
          {analysisData?.recommended_bet && (
            <div style={{ marginTop: 4 }}>
              <span className={`badge badge-${
                analysisData.recommended_bet === 'avoid' ? 'red' :
                analysisData.recommended_bet === 'win' ? 'green' : 'gold'
              }`}>
                {analysisData.recommended_bet}
              </span>
            </div>
          )}
        </div>

        {/* Odds + add button */}
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
        </div>
      </div>

      {/* Analysis summary if available */}
      {analysisData?.summary && (
        <p style={{
          marginTop: 10,
          paddingTop: 10,
          borderTop: '1px solid var(--border-subtle)',
          fontSize: 12,
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
        }}>
          {analysisData.summary}
        </p>
      )}
    </div>
  );
}
