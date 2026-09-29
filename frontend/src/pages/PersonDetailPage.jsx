import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPersonProfile } from '../utils/api';
import PageHeader from '../components/common/PageHeader';
import FollowButton from '../components/common/FollowButton';

/**
 * A trainer or jockey.
 *
 * Two windows, the same four measures on each, so the cards read against each
 * other: everything before this year, and this year. Only the 2023 charts
 * recorded losing runs, so that season's win rate is the one figure that can be
 * quoted, and it gets its own strip rather than sitting in a card as though it
 * covered the same span. Everything else is counts.
 *
 * Only the two summary cards sit side by side — four tiles each, so they are
 * the same height by construction. Lists run full width: pairing an eight-row
 * card with a four-row one is what put a hole in the corner.
 */

const pct = (v) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);
const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const day = (iso) => {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${MONTHS[+m]} ${+d} ${y}`;
};
const titleCase = (s) => (s || '').toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase());

function Card({ title, note, children }) {
  return (
    <div className="person-card">
      <div className="person-card-head">
        <span className="person-card-title">{title}</span>
        {note && <span className="person-card-note">{note}</span>}
      </div>
      {children}
    </div>
  );
}

function Figures({ items }) {
  return (
    <div className="person-figures">
      {items.map(({ value, label, gold }) => (
        <div className="person-figure" key={label}>
          <div className={`person-figure-value${gold ? ' is-gold' : ''}`}>{value}</div>
          <div className="person-figure-label">{label}</div>
        </div>
      ))}
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
  const n = (v) => (v ?? 0).toLocaleString();

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
            <div className="person-split">
              {/* "First on file" is where our records start, not where the
                  career did — the feed's person endpoints aren't on our plan,
                  so there's no birth date and no true career start to show. */}
              <Card
                title={`Before ${data.season}`}
                note={data.prior.first_run ? `First on file ${day(data.prior.first_run)}` : ''}
              >
                <Figures items={[
                  { value: n(data.prior.wins), label: 'Wins', gold: true },
                  { value: n(data.prior.itm), label: 'In The Money' },
                  { value: n(data.prior.tracks), label: 'Tracks' },
                  { value: n(data.prior.horses), label: 'Horses' },
                ]} />
              </Card>

              <Card
                title={String(data.season)}
                note={data.current.last_run ? `Last winner ${day(data.current.last_run)}` : 'No winners yet'}
              >
                <Figures items={[
                  { value: n(data.current.wins), label: 'Wins', gold: true },
                  { value: n(data.current.itm), label: 'In The Money' },
                  { value: n(data.current.tracks), label: 'Tracks' },
                  { value: n(data.current.horses), label: 'Horses' },
                ]} />
              </Card>
            </div>

            {/* The one season with every runner on file, so the one place a
                rate has a denominator. Its own strip, clearly dated. */}
            {data.prior.rated_season && (
              <div className="person-rate">
                <span className="person-rate-value">{pct(data.prior.rated_win_rate)}</span>
                <span className="person-rate-label">
                  win rate in {data.prior.rated_season} — {n(data.prior.rated_wins)} from{' '}
                  {n(data.prior.rated_starts)} starts, the one season with every run on file
                </span>
              </div>
            )}

            {data.top_tracks.length > 0 && (
              <Card title="Best Tracks" note="Wins since 2024">
                <div className="person-rows is-split">
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
                <div className="person-rows is-split">
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
              <Card title="Latest Winners" note="$2 win payoff">
                <div className="person-rows is-split">
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
