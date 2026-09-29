import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPersonProfile } from '../utils/api';
import PageHeader from '../components/common/PageHeader';
import FollowButton from '../components/common/FollowButton';

/**
 * A trainer or jockey, read from all three archives.
 *
 * The windows are kept apart on purpose. 2023 is the only season where every
 * runner was recorded, so it is the only place a win rate can come from — the
 * 2024-onward archive keeps top-three finishes, meaning its wins are real but
 * its starts were never written down. Dividing one by the other would invent a
 * number, so the page shows the rate for 2023 and counts for everything since,
 * each labelled with where it came from.
 */

const pct = (v) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);
const day = (iso) => {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+m]} ${+d} ${y}`;
};
const titleCase = (s) => (s || '').toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase());

function Card({ title, note, wide = false, children }) {
  return (
    <div className={`person-card${wide ? ' is-wide' : ''}`}>
      <div className="person-card-head">
        <span className="person-card-title">{title}</span>
        {note && <span className="person-card-note">{note}</span>}
      </div>
      {children}
    </div>
  );
}

function Figure({ value, label, highlight = false }) {
  return (
    <div className="person-figure">
      <div className={`person-figure-value${highlight ? ' is-gold' : ''}`}>{value}</div>
      <div className="person-figure-label">{label}</div>
    </div>
  );
}

export default function PersonDetailPage({ type }) {
  const { name } = useParams();
  const navigate = useNavigate();
  const decoded = decodeURIComponent(name || '');

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['person-profile', type, decoded],
    queryFn: () => getPersonProfile(decoded, type),
    enabled: decoded.length >= 2,
    retry: false,
  });

  const notFound = isError && error?.response?.status === 404;

  return (
    <div>
      <PageHeader
        title={decoded}
        subtitle={type}
        showBack
        right={data ? (
          <FollowButton entityType={type} entityLabel={data.name} entityKey={data.entity_key} size={22} />
        ) : null}
      />

      <div className="person-body">
        {isLoading && <div className="person-empty">Reading the archives…</div>}

        {notFound && (
          <div className="person-empty">
            No record for {decoded} in our archives.
            <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px', marginTop: 12 }}
                    onClick={() => navigate('/search')}>
              Back to search
            </button>
          </div>
        )}

        {isError && !notFound && <div className="person-empty">Couldn't load that profile.</div>}

        {data && (
          <>
            {data.rated && (
              <Card title={`${data.rated.season} Season`} note="Every start on file">
                <div className="person-figures">
                  <Figure value={pct(data.rated.win_rate)} label="Win Rate" highlight />
                  <Figure value={pct(data.rated.itm_rate)} label="In The Money" />
                  <Figure value={data.rated.wins.toLocaleString()} label="Wins" />
                  <Figure value={data.rated.starts.toLocaleString()} label="Starts" />
                </div>
              </Card>
            )}

            {/* No rate on this card: the 2024 archive keeps top-three finishes,
                so the wins are real but the losing runs were never recorded.
                The note says so in four words rather than a paragraph. */}
            <Card title="Since 2024" note="Wins only · top-three on file">
              <div className="person-figures">
                <Figure value={data.recent.wins.toLocaleString()} label="Wins" highlight />
                <Figure value={data.recent.itm.toLocaleString()} label="In The Money" />
                <Figure value={data.recent.tracks} label="Tracks" />
                <Figure value={data.recent.horses.toLocaleString()} label="Horses" />
              </div>
            </Card>

            {data.top_tracks.length > 0 && (
              <Card title="Best Tracks" note="Since 2024">
                <div className="person-rows">
                {data.top_tracks.map((t, i) => (
                  <div key={t.track} className="person-row">
                    <span className="person-row-rank">{i + 1}</span>
                    <span className="person-row-name">{titleCase(t.track)}</span>
                    <span className="person-row-stat">{t.wins}<span className="person-row-unit"> wins</span></span>
                  </div>
                ))}
                </div>
              </Card>
            )}

            {data.surfaces.length > 0 && (
              <Card title="Surface" note="Wins since 2024">
                <div className="person-rows">
                {data.surfaces.map((s) => (
                  <div key={s.surface} className="person-row">
                    <span className="person-row-name">{s.surface}</span>
                    <span className="person-row-stat">{s.wins}<span className="person-row-unit"> wins</span></span>
                  </div>
                ))}
                </div>
              </Card>
            )}

            {data.recent_winners.length > 0 && (
              <Card title="Latest Winners" wide
                    note={data.recent.last_run ? `Last one ${day(data.recent.last_run)}` : ''}>
                <div className="person-rows">
                {data.recent_winners.map((w, i) => (
                  <div key={`${w.horse}-${w.date}-${i}`} className="person-row">
                    <span className="person-row-name">{w.horse}</span>
                    <span className="person-row-sub">{titleCase(w.track)} · {day(w.date)}</span>
                    {w.win_payoff ? (
                      <span className="person-row-stat">${w.win_payoff.toFixed(2)}</span>
                    ) : null}
                  </div>
                ))}
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
