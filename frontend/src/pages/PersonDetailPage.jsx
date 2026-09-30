import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPersonProfile, getPersonRecord } from '../utils/api';
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
// Our archive records a top-three finish and nothing else from 2024 on, so
// there is no start count to divide by and no true in-the-money rate for these
// windows. What it can say honestly is how many of the board hits were wins.
const winShare = (wins, board) => (board ? pct(wins / board) : '—');
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

/**
 * One season, with a real denominator where the feed has one.
 *
 * `rec` comes from the results endpoint, which returns whole races, so it can
 * count starts as well as wins. When the feed has nothing for that person in
 * that year the card falls back to the archive's counts and says so, rather
 * than showing a rate it can't stand behind.
 */
function SeasonCard({ title, rec, fallback, fallbackNote }) {
  const n = (v) => (v ?? 0).toLocaleString();
  if (rec && rec.starts) {
    return (
      <Card title={title}
            note={`${rec.label ? `${rec.label} · ` : ''}${n(rec.starts)} ${rec.starts === 1 ? 'Start' : 'Starts'} In Stakes Company`}>
        <Figures items={[
          { value: pct(rec.win_rate), label: 'Win Rate', gold: true },
          { value: pct(rec.itm_rate), label: 'In The Money' },
          { value: n(rec.wins), label: 'Wins' },
          { value: n(rec.starts), label: 'Starts' },
        ]} />
      </Card>
    );
  }
  return (
    <Card title={title} note={fallbackNote}>
      <Figures items={[
        { value: n(fallback?.wins), label: 'Wins', gold: true },
        { value: winShare(fallback?.wins, fallback?.itm), label: 'Win Share' },
        { value: n(fallback?.tracks), label: 'Tracks' },
        { value: n(fallback?.horses), label: 'Horses' },
      ]} />
    </Card>
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

  // Six years of real start counts is a dozen upstream calls on a plan that
  // 429s above three at once — ten seconds the rest of the page shouldn't wait
  // for. It loads alongside, and the cards show the archive's counts until it
  // lands.
  const { data: record } = useQuery({
    queryKey: ['person-record', type, decoded],
    queryFn: () => getPersonRecord(decoded, type),
    enabled: decoded.length >= 2,
    retry: false,
    staleTime: 6 * 60 * 60 * 1000,
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
            {/* This year against last, same four measures, both with a real
                start count behind them. The page used to lead with a 2023 win
                rate, because 2023 was the only season our own archive recorded
                losing runs for — a number nobody has a reason to care about. */}
            {/* Earlier years on the left, this year on the right, so the cards
                read left to right in time.

                Both sides use one source or neither does. A claiming yard can
                have 273 wins in our archive and barely a run in the feed's
                stakes-company dataset, which left one card showing a win rate
                over real starts and the other showing raw counts — two cards
                side by side measuring different things. */}
            {(() => {
              const paired = record?.season_prior && record?.season_rec;
              return (
                <div className="person-split">
                  <SeasonCard title={`Before ${data.season}`}
                              rec={paired ? record.season_prior : null}
                              fallback={data.prior} fallbackNote={
                                data.prior.first_run ? `First On File ${day(data.prior.first_run)}` : ''} />
                  <SeasonCard title={String(data.season)}
                              rec={paired ? record.season_rec : null}
                              fallback={data.current} fallbackNote={
                                data.current.last_run ? `Last Winner ${day(data.current.last_run)}` : 'No Winners Yet'} />
                </div>
              );
            })()}

            {data.top_tracks.length > 0 && (
              <Card title="Best Tracks" note="Wins Since 2024">
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

            {/* Three surfaces in a two-column list left a hole in the corner.
                One row of equal tiles fits however many there are. */}
            {data.surfaces.length > 0 && (
              <Card title="Surface" note="Wins Since 2024">
                <div
                  className="person-surfaces"
                  style={{ gridTemplateColumns: `repeat(${data.surfaces.length}, 1fr)` }}
                >
                  {data.surfaces.map((s) => (
                    <div className="person-figure" key={s.surface}>
                      <div className="person-figure-value">{n(s.wins)}</div>
                      <div className="person-figure-label">{s.surface}</div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {data.recent_winners.length > 0 && (
              <Card title="Latest Winners" note="$2 Win Payoff">
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
