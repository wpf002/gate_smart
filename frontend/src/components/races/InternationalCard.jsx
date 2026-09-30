import { useState } from 'react';

/**
 * The non-US card, grouped country then track.
 *
 * It doesn't reuse RaceCard. RaceCard links into the race detail page, which
 * reads the North America feed and can't resolve a core-feed race_id, so a
 * link there would be a dead end. These rows carry their own detail instead —
 * time, name, distance, going, class and field — which is what you'd open the
 * race to see anyway.
 *
 * One track open per country, and the open one sits below the grid rather than
 * inside it. Inside, spanning every column stopped auto-fit collapsing the
 * empty ones, so a country with three tracks left the right third of the row
 * blank. Out here the grid holds nothing but uniform headers and fills.
 */

function Race({ race }) {
  const tags = [race.distance, race.going, race.race_class].filter(Boolean);
  return (
    <div className={`intl-race${race.is_abandoned ? ' is-off' : ''}`}>
      <span className="intl-race-time">{race.off_time || '—'}</span>
      <span className="intl-race-body">
        <span className="intl-race-name">
          {race.race_name}
          {race.big_race && <span className="intl-race-flag">Group</span>}
        </span>
        {tags.length > 0 && <span className="intl-race-tags">{tags.join(' · ')}</span>}
      </span>
      <span className="intl-race-field">
        {race.is_abandoned ? 'Abandoned' : `${race.field_size || '?'} run`}
      </span>
    </div>
  );
}

function Country({ country }) {
  const [openCourse, setOpenCourse] = useState(null);
  const open = country.tracks.find((t) => t.course === openCourse) || null;

  return (
    <section className="intl-country">
      <header className="intl-country-head">
        <h2 className="intl-country-name">{country.region}</h2>
        <span className="intl-country-count">
          {country.race_count} races · {country.track_count}{' '}
          {country.track_count === 1 ? 'track' : 'tracks'}
        </span>
      </header>

      <div className="intl-tracks">
        {country.tracks.map((t) => (
          <button
            key={t.course_id || t.course}
            className={`intl-track-head${t.course === openCourse ? ' is-active' : ''}`}
            onClick={() => setOpenCourse(t.course === openCourse ? null : t.course)}
          >
            <span className="intl-track-name">{t.course}</span>
            <span className="intl-track-count">
              {t.race_count} {t.race_count === 1 ? 'race' : 'races'}
            </span>
            <span className="intl-track-chevron">{t.course === openCourse ? '‹' : '›'}</span>
          </button>
        ))}
      </div>

      {open && (
        <div className="intl-open">
          <div className="intl-races">
            {open.races.map((r) => <Race key={r.race_id} race={r} />)}
          </div>
        </div>
      )}
    </section>
  );
}

export default function InternationalCard({ countries }) {
  return (
    <div className="intl-countries">
      {countries.map((c) => <Country key={c.region_code} country={c} />)}
    </div>
  );
}
