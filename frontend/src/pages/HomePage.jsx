import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getRacesToday, getRacesByDate, getInternationalRaces } from '../utils/api';
import { RaceCard, RaceCardSkeleton } from '../components/races/RaceCard';
import InternationalCard from '../components/races/InternationalCard';
import PageHeader from '../components/common/PageHeader';
import AccuracyBadge from '../components/common/AccuracyBadge';
import Icon from '../components/common/Icon';

const DATE_TABS = [
  { key: 'today', label: 'Today' },
  { key: 'tomorrow', label: 'Tomorrow' },
];

// Two feeds, not two filters on one. The US view is the North America add-on;
// the international view is the core feed — Britain, Ireland, France and
// whatever group races are carded elsewhere — so they can't be merged.
const VIEW_TABS = [
  { key: 'usa', label: 'United States' },
  { key: 'intl', label: 'International' },
];

function TrackSection({ course, races, isTomorrow }) {
  const [collapsed, setCollapsed] = useState(true);
  return (
    <div className={`track-section${collapsed ? '' : ' is-open'}`}>
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


export default function HomePage() {
  const [selectedDay, setSelectedDay] = useState('today');
  const [view, setView] = useState('usa');
  const [trackSearch, setTrackSearch] = useState('');
  const isIntl = view === 'intl';

  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['races', view, selectedDay],
    queryFn: () =>
      isIntl
        ? getInternationalRaces(selectedDay)
        : selectedDay === 'today'
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
      queryKey: ['races', view, otherDay],
      queryFn: () =>
        isIntl
          ? getInternationalRaces(otherDay)
          : otherDay === 'today'
            ? getRacesToday('usa')
            : getRacesByDate('tomorrow', 'usa'),
    });
  }, [selectedDay, view, isIntl, queryClient]);

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
        right={<AccuracyBadge />}
      />

      {/* Which feed */}
      <div className="view-toggle">
        {VIEW_TABS.map(({ key, label }) => (
          <button
            key={key}
            className={`view-toggle-btn${view === key ? ' is-active' : ''}`}
            onClick={() => setView(key)}
          >
            {label}
          </button>
        ))}
      </div>

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

      {/* Track search — US view only; the international view groups by country
          first, so filtering tracks across all of them reads wrong. */}
      {!isIntl && (
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
      )}

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
        ) : isIntl ? (
          (data?.countries || []).length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}><Icon name="horse" size={48} /></div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 22 }}>No international racing</div>
              <div style={{ fontSize: 13, marginTop: 6 }}>Nothing carded outside the US for this day</div>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
                {data.total} races across {data.countries.length}{' '}
                {data.countries.length === 1 ? 'country' : 'countries'}
              </div>
              <InternationalCard countries={data.countries} />
            </>
          )
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
            <div className="track-grid">
              {tracks.map(course => (
                <TrackSection key={course} course={course} races={byTrack[course]} isTomorrow={selectedDay === 'tomorrow'} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
