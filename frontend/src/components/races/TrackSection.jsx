import { useState } from 'react';
import { RaceCard } from './RaceCard';

/**
 * One track's card, collapsed by default.
 *
 * Shared by both race views so the US and international pages render a track
 * the same way — same header, same RaceCard grid. RaceCard already branches on
 * region for time, currency and distance, so a core-feed race needs nothing
 * special here.
 */
export default function TrackSection({ course, races, isTomorrow, defaultOpen = false }) {
  const [collapsed, setCollapsed] = useState(!defaultOpen);
  return (
    <div className={`track-section${collapsed ? '' : ' is-open'}`}>
      <button
        onClick={() => setCollapsed((c) => !c)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          width: '100%',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '6px 0 10px',
          textAlign: 'left',
        }}
      >
        <span style={{
          fontFamily: 'var(--font-display)',
          fontSize: 20,
          color: 'var(--accent-gold)',
          letterSpacing: '0.06em',
          flex: 1,
        }}>
          {course}
        </span>
        <span style={{
          fontSize: 11,
          color: 'var(--text-muted)',
          fontWeight: 600,
          background: 'var(--bg-elevated)',
          padding: '2px 8px',
          borderRadius: 10,
        }}>
          {races.length} {races.length === 1 ? 'race' : 'races'}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {collapsed ? '›' : '‹'}
        </span>
      </button>

      {!collapsed && (
        <div className="race-grid">
          {races.map((race) => (
            <RaceCard key={race.race_id} race={race} isTomorrow={isTomorrow} />
          ))}
        </div>
      )}
    </div>
  );
}
