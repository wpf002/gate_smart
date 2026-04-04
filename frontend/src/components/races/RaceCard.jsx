import React from 'react';
import { useNavigate } from 'react-router-dom';

export function RaceCardSkeleton() {
  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <div className="skeleton" style={{ height: 16, width: '40%', borderRadius: 4 }} />
        <div className="skeleton" style={{ height: 16, width: '25%', borderRadius: 4 }} />
      </div>
      <div className="skeleton" style={{ height: 13, width: '60%', borderRadius: 4, marginBottom: 10 }} />
      <div style={{ display: 'flex', gap: 8 }}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 24, width: 60, borderRadius: 12 }} />
        ))}
      </div>
    </div>
  );
}

export function RaceCard({ race }) {
  const navigate = useNavigate();

  const handleClick = () => navigate(`/race/${race.race_id}`);

  const runnersCount = race.runners?.length ?? race.no_of_runners;

  return (
    <div
      className="card"
      onClick={handleClick}
      style={{
        marginBottom: 10,
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-card)')}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 18,
          color: 'var(--accent-gold)',
          letterSpacing: '0.04em',
        }}>
          {race.time} · {race.course}
        </div>
        {race.going && (
          <span className="badge badge-muted">{race.going}</span>
        )}
      </div>

      {/* Race title */}
      <div style={{
        fontSize: 13,
        color: 'var(--text-secondary)',
        marginBottom: 10,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {race.title || race.race_name}
      </div>

      {/* Meta chips */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {race.distance && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>📏 {race.distance}</span>
        )}
        {race.surface && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🌿 {race.surface}</span>
        )}
        {runnersCount && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🏇 {runnersCount} runners</span>
        )}
        {race.prize && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>💰 {race.prize}</span>
        )}
        <span style={{
          marginLeft: 'auto',
          fontSize: 12,
          color: 'var(--accent-gold-dim)',
          fontWeight: 600,
        }}>
          Analyze →
        </span>
      </div>
    </div>
  );
}
