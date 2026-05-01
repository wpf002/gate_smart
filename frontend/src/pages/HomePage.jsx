import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getRacesToday, getRacesByDate, getDailyAccuracy } from '../utils/api';
import { RaceCard, RaceCardSkeleton } from '../components/races/RaceCard';
import PageHeader from '../components/common/PageHeader';
import Icon from '../components/common/Icon';

const DATE_TABS = [
  { key: 'today', label: 'Today' },
  { key: 'tomorrow', label: 'Tomorrow' },
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
          {collapsed ? '›' : '‹'}
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

function SecretariatReportCard() {
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: ['accuracy-daily'],
    queryFn: () => getDailyAccuracy(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  if (!data || data.status === 'pending') return null;

  const wr = ((data.win_rate || 0) * 100).toFixed(0);
  const wrColor = Number(wr) >= 50 ? 'var(--accent-green-bright)' : Number(wr) >= 35 ? 'var(--accent-gold-bright)' : 'var(--accent-red-bright)';

  return (
    <div style={{
      margin: '12px 16px 0',
      padding: '12px 14px',
      background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-elevated) 100%)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--accent-gold)' }}>
          SECRETARIAT TODAY
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: wrColor }}>
          {wr}% win rate
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>
        Races called: <strong>{data.races_analyzed}</strong>
        {data.best_call && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}> · <Icon name="target" size={12} /> {data.best_call}</span>}
      </div>
      <button
        onClick={() => navigate('/accuracy')}
        style={{ marginTop: 6, background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, color: 'var(--accent-gold-dim)', fontWeight: 600 }}
      >
        View Full Report →
      </button>
    </div>
  );
}

export default function HomePage() {
  const [selectedDay, setSelectedDay] = useState('today');
  const [trackSearch, setTrackSearch] = useState('');

  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['races', selectedDay],
    queryFn: () =>
      selectedDay === 'today'
        ? getRacesToday('usa')
        : getRacesByDate('tomorrow', 'usa'),
    // Keep last-good data visible while refetching or during a transient
    // failure, so a brief Railway redeploy or network blip doesn't blank
    // the screen with a scary error.
    placeholderData: keepPreviousData,
  });

  // Warm the cache for the other day so toggling tabs feels instant.
  useEffect(() => {
    const otherDay = selectedDay === 'today' ? 'tomorrow' : 'today';
    queryClient.prefetchQuery({
      queryKey: ['races', otherDay],
      queryFn: () =>
        otherDay === 'today'
          ? getRacesToday('usa')
          : getRacesByDate('tomorrow', 'usa'),
    });
  }, [selectedDay, queryClient]);

  const races = data?.racecards ?? [];

  // Group/sort/filter the race list. Memoised on (races, trackSearch) so
  // unrelated re-renders (e.g. tab highlight updates, refetch toggles) don't
  // re-run the whole pipeline over 100+ races.
  const { byTrack, tracks, allTracks } = useMemo(() => {
    const normalizeCourse = (c) =>
      (c || 'Unknown')
        .replace(/\s+(turf\s+)?pick\s+\d+$/i, '')
        .replace(/\s+(super|grand)\s+pick\s+\d+$/i, '')
        .trim() || 'Unknown';

    const grouped = races.reduce((acc, race) => {
      const course = normalizeCourse(race.course);
      if (!acc[course]) acc[course] = [];
      acc[course].push(race);
      return acc;
    }, {});

    const allTracks = Object.keys(grouped).sort((a, b) => a.localeCompare(b));
    const filtered = trackSearch.trim()
      ? allTracks.filter(t => t.toLowerCase().includes(trackSearch.trim().toLowerCase()))
      : allTracks;

    filtered.forEach(t => {
      grouped[t].sort((a, b) => {
        if (a.off_dt && b.off_dt) return new Date(a.off_dt) - new Date(b.off_dt);
        return (a.time || '').localeCompare(b.time || '');
      });
    });

    return { byTrack: grouped, tracks: filtered, allTracks };
  }, [races, trackSearch]);

  return (
    <div>
      <PageHeader
        title="GATESMART"
        subtitle="AI-POWERED RACING INTELLIGENCE"
      />

      <SecretariatReportCard />

      {/* Date tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-subtle)', marginTop: 12 }}>
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

      {/* Track search */}
      <div style={{ padding: '10px 16px 0' }}>
        <div style={{ position: 'relative' }}>
          <span style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            pointerEvents: 'none', color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
          }}><Icon name="search" size={14} /></span>
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
            {races.length > 0
              ? "Couldn't refresh — showing last update. Tap refresh to try again."
              : 'Failed to load races. Check your connection and try again.'}
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
            <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}><Icon name="horse" size={48} /></div>
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
