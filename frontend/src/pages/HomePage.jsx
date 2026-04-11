import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRacesToday, getRacesByDate } from '../utils/api';
import { RaceCard, RaceCardSkeleton } from '../components/races/RaceCard';
import PageHeader from '../components/common/PageHeader';

const DATE_TABS = [
  { key: 'today', label: 'Today' },
  { key: 'tomorrow', label: 'Tomorrow' },
];

const REGION_TABS = [
  { key: 'USA,CAN', label: '🇺🇸 USA' },
  { key: 'GB,IRE', label: '🇬🇧 UK & IRE' },
  { key: null, label: 'All' },
];

function TrackSection({ course, races, isTomorrow }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div style={{ marginBottom: 24 }}>
      <button
        onClick={() => setCollapsed(c => !c)}
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
          {collapsed ? '▶' : '▼'}
        </span>
      </button>

      {!collapsed && (
        <div className="race-grid">
          {races.map(race => (
            <RaceCard key={race.race_id} race={race} isTomorrow={isTomorrow} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function HomePage() {
  const [selectedDay, setSelectedDay] = useState('today');
  const [selectedRegion, setSelectedRegion] = useState('USA,CAN');
  const [trackSearch, setTrackSearch] = useState('');

  const isAll = selectedRegion === null;

  // Standard (UK/IRE/etc.) fetch — always runs
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['races', selectedDay, selectedRegion],
    queryFn: () =>
      selectedDay === 'today'
        ? getRacesToday(isAll ? null : selectedRegion)
        : getRacesByDate('tomorrow', isAll ? null : selectedRegion),
  });

  // NA fetch — only runs when "All" is selected
  const { data: naData, refetch: naRefetch } = useQuery({
    queryKey: ['races', selectedDay, 'USA,CAN'],
    queryFn: () =>
      selectedDay === 'today'
        ? getRacesToday('USA,CAN')
        : getRacesByDate('tomorrow', 'USA,CAN'),
    enabled: isAll,
  });

  const handleRefetch = () => { refetch(); if (isAll) naRefetch(); };

  const races = isAll
    ? [...(data?.racecards ?? []), ...(naData?.racecards ?? [])]
    : (data?.racecards ?? []);

  // Normalize course names — strip exotic wager suffixes the NA API appends
  // e.g. "Keeneland Turf Pick 3" → "Keeneland"
  const normalizeCourse = (c) =>
    (c || 'Unknown')
      .replace(/\s+(turf\s+)?pick\s+\d+$/i, '')
      .replace(/\s+(super|grand)\s+pick\s+\d+$/i, '')
      .trim() || 'Unknown';

  // Group by course, sort courses alphabetically
  const byTrack = races.reduce((acc, race) => {
    const course = normalizeCourse(race.course);
    if (!acc[course]) acc[course] = [];
    acc[course].push(race);
    return acc;
  }, {});

  const allTracks = Object.keys(byTrack).sort((a, b) => a.localeCompare(b));
  const tracks = trackSearch.trim()
    ? allTracks.filter(t => t.toLowerCase().includes(trackSearch.trim().toLowerCase()))
    : allTracks;

  // Sort races within each track by off_dt (accurate) then time string fallback
  tracks.forEach(t => {
    byTrack[t].sort((a, b) => {
      if (a.off_dt && b.off_dt) return new Date(a.off_dt) - new Date(b.off_dt);
      return (a.time || '').localeCompare(b.time || '');
    });
  });

  return (
    <div>
      <PageHeader
        title="GATESMART"
        subtitle="AI-powered racing intelligence"
        right={
          <button
            onClick={handleRefetch}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}
          >
            ↻
          </button>
        }
      />

      {/* Date tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-subtle)' }}>
        {DATE_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSelectedDay(key)}
            style={{
              flex: 1,
              padding: '10px 0',
              background: 'none',
              border: 'none',
              borderBottom: selectedDay === key ? '2px solid var(--accent-gold)' : '2px solid transparent',
              color: selectedDay === key ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
              fontFamily: 'var(--font-body)',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Region tabs */}
      <div style={{ display: 'flex', gap: 6, padding: '10px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        {REGION_TABS.map(({ key, label }) => (
          <button
            key={String(key)}
            onClick={() => setSelectedRegion(key)}
            style={{
              padding: '5px 14px',
              borderRadius: 20,
              border: '1px solid',
              borderColor: selectedRegion === key ? 'var(--accent-gold)' : 'var(--border-subtle)',
              background: selectedRegion === key ? 'rgba(201,162,39,0.12)' : 'transparent',
              color: selectedRegion === key ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Track search */}
      <div style={{ padding: '10px 16px 0' }}>
        <div style={{ position: 'relative' }}>
          <span style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 14, pointerEvents: 'none', color: 'var(--text-muted)',
          }}>🔍</span>
          <input
            type="search"
            placeholder="Filter tracks…"
            value={trackSearch}
            onChange={(e) => setTrackSearch(e.target.value)}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '9px 12px 9px 32px',
              fontSize: 14,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-medium)',
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {isError && (
          <div style={{
            padding: 16,
            background: 'rgba(192,57,43,0.1)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--accent-red-bright)',
            fontSize: 13,
            marginBottom: 16,
          }}>
            Failed to load races. Check your connection and try again.
          </div>
        )}

        {isLoading ? (
          <div>
            {[...Array(3)].map((_, t) => (
              <div key={t} style={{ marginBottom: 24 }}>
                <div className="skeleton" style={{ height: 24, width: 200, borderRadius: 6, marginBottom: 12 }} />
                <div className="race-grid">
                  {[...Array(2)].map((_, i) => <RaceCardSkeleton key={i} />)}
                </div>
              </div>
            ))}
          </div>
        ) : tracks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🏇</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 22 }}>No races scheduled</div>
            <div style={{ fontSize: 13, marginTop: 6 }}>Check back later or try another day</div>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              {trackSearch.trim()
                ? `${tracks.length} of ${allTracks.length} tracks match "${trackSearch.trim()}"`
                : `${races.length} races across ${tracks.length} tracks`}
            </div>
            {tracks.map(course => (
              <TrackSection key={course} course={course} races={byTrack[course]} isTomorrow={selectedDay === 'tomorrow'} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
