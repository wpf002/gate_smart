import TrackSection from './TrackSection';

/**
 * The non-US card: country, then the same track sections the US view uses.
 *
 * The only thing this adds over the US view is the country heading. Everything
 * below it is TrackSection and RaceCard, so a Chantilly race reads exactly like
 * a Saratoga one.
 */
export default function InternationalCard({ countries, isTomorrow }) {
  return (
    <div className="intl-countries">
      {countries.map((c) => (
        <section className="intl-country" key={c.region_code}>
          <header className="intl-country-head">
            <h2 className="intl-country-name">{c.region}</h2>
            <span className="intl-country-count">
              {c.race_count} races · {c.track_count}{' '}
              {c.track_count === 1 ? 'track' : 'tracks'}
            </span>
          </header>
          <div className="track-grid">
            {c.tracks.map((t) => (
              <TrackSection
                key={t.course_id || t.course}
                course={t.course}
                races={t.races}
                isTomorrow={isTomorrow}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
