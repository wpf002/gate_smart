import { useMemo, useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getWatchlist, getWatchlistToday, removeFromWatchlist } from '../utils/api';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import Icon from '../components/common/Icon';

const TYPE_LABEL = { horse: 'Horses', trainer: 'Trainers', jockey: 'Jockeys' };
const TYPE_ORDER = ['horse', 'trainer', 'jockey'];
const DAY_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'today', label: 'Today' },
  { key: 'tomorrow', label: 'Tomorrow' },
];

function FilterPill({ active, label, count, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '5px 12px',
        borderRadius: 999,
        border: `1px solid ${active ? 'var(--accent-gold)' : 'var(--border-medium)'}`,
        background: active ? 'rgba(201,162,39,0.15)' : 'transparent',
        color: active ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
        fontSize: 12,
        fontWeight: 600,
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {label}{count != null ? ` (${count})` : ''}
    </button>
  );
}

export default function WatchlistPage() {
  const authToken = useAppStore((s) => s.authToken);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [dayFilter, setDayFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [whoFilter, setWhoFilter] = useState('all');
  const [trackFilter, setTrackFilter] = useState('all');

  const { data: wl, isLoading } = useQuery({
    queryKey: ['watchlist'], queryFn: getWatchlist, enabled: !!authToken,
  });
  const { data: today } = useQuery({
    queryKey: ['watchlist-today'], queryFn: getWatchlistToday, enabled: !!authToken,
    refetchInterval: 10 * 60 * 1000,
  });

  const remove = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlist'] });
      qc.invalidateQueries({ queryKey: ['watchlist-today'] });
    },
  });

  if (!authToken) {
    return (
      <div>
        <PageHeader title="WATCHLIST" subtitle="FOLLOW HORSES, TRAINERS & JOCKEYS" />
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}><Icon name="star" size={40} /></div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, marginBottom: 8 }}>Sign in to build your watchlist</div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>Follow your horses, trainers, and jockeys and get alerted when they run.</div>
          <button onClick={() => navigate('/login')} style={{
            padding: '10px 20px', background: 'var(--accent-gold)', color: '#000',
            border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 700, cursor: 'pointer',
          }}>Sign In</button>
        </div>
      </div>
    );
  }

  const items = wl?.items || [];
  const matches = today?.matches || [];
  const grouped = TYPE_ORDER.map((t) => ({ type: t, rows: items.filter((i) => i.entity_type === t) }))
    .filter((g) => g.rows.length);

  // Filter options are derived from the matches themselves, so we never offer a
  // filter that would return nothing (e.g. no "Tomorrow" pill on a today-only list).
  const dayCounts = {
    all: matches.length,
    today: matches.filter((m) => m.day === 'today').length,
    tomorrow: matches.filter((m) => m.day === 'tomorrow').length,
  };
  const typesPresent = TYPE_ORDER.filter((t) => matches.some((m) => m.entity_type === t));
  const whoPresent = [...new Set(matches.map((m) => m.entity_label))].sort((a, b) => a.localeCompare(b));
  const tracksPresent = [...new Set(matches.map((m) => m.course).filter(Boolean))].sort((a, b) => a.localeCompare(b));

  const filtered = matches.filter((m) =>
    (dayFilter === 'all' || m.day === dayFilter) &&
    (typeFilter === 'all' || m.entity_type === typeFilter) &&
    (whoFilter === 'all' || m.entity_label === whoFilter) &&
    (trackFilter === 'all' || m.course === trackFilter)
  );
  const filtersActive = dayFilter !== 'all' || typeFilter !== 'all' || whoFilter !== 'all' || trackFilter !== 'all';
  const clearFilters = () => { setDayFilter('all'); setTypeFilter('all'); setWhoFilter('all'); setTrackFilter('all'); };

  const selectStyle = {
    padding: '5px 8px', fontSize: 12, borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border-medium)', background: 'var(--bg-elevated)',
    color: 'var(--text-primary)', maxWidth: 180,
  };

  return (
    <div>
      <PageHeader title="WATCHLIST" subtitle="FOLLOW HORSES, TRAINERS & JOCKEYS" />

      <div style={{ padding: '12px 20px 24px' }}>
        {/* Racing today */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', letterSpacing: '0.06em', marginBottom: 10 }}>
            RACING SOON ({filtersActive ? `${filtered.length} of ${matches.length}` : matches.length})
          </div>

          {matches.length > 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
              {/* Day */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {DAY_FILTERS.filter((d) => d.key === 'all' || dayCounts[d.key] > 0).map((d) => (
                  <FilterPill key={d.key} label={d.label} count={dayCounts[d.key]}
                    active={dayFilter === d.key} onClick={() => setDayFilter(d.key)} />
                ))}
              </div>
              {/* Type — only when following more than one kind */}
              {typesPresent.length > 1 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <FilterPill label="All types" active={typeFilter === 'all'} onClick={() => setTypeFilter('all')} />
                  {typesPresent.map((t) => (
                    <FilterPill key={t} label={TYPE_LABEL[t]}
                      count={matches.filter((m) => m.entity_type === t).length}
                      active={typeFilter === t} onClick={() => setTypeFilter(t)} />
                  ))}
                </div>
              )}
              {/* Who / track dropdowns + clear */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                {whoPresent.length > 1 && (
                  <select value={whoFilter} onChange={(e) => setWhoFilter(e.target.value)} style={selectStyle} aria-label="Filter by who">
                    <option value="all">Anyone ({whoPresent.length})</option>
                    {whoPresent.map((w) => <option key={w} value={w}>{w}</option>)}
                  </select>
                )}
                {tracksPresent.length > 1 && (
                  <select value={trackFilter} onChange={(e) => setTrackFilter(e.target.value)} style={selectStyle} aria-label="Filter by track">
                    <option value="all">All tracks ({tracksPresent.length})</option>
                    {tracksPresent.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                )}
                {filtersActive && (
                  <button onClick={clearFilters} style={{
                    background: 'none', border: 'none', color: 'var(--text-muted)',
                    fontSize: 12, cursor: 'pointer', textDecoration: 'underline', padding: 4,
                  }}>Clear</button>
                )}
              </div>
            </div>
          )}

          {matches.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              None of your follows are entered in today's or tomorrow's cards yet.
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              No entries match these filters.{' '}
              <button onClick={clearFilters} style={{
                background: 'none', border: 'none', color: 'var(--accent-gold-bright)',
                fontSize: 13, cursor: 'pointer', textDecoration: 'underline', padding: 0,
              }}>Clear filters</button>
            </div>
          ) : (
            filtered.map((m, i) => (
              <div key={i} onClick={() => m.race_id && navigate(`/race/${m.race_id}`)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                  background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)',
                  marginBottom: 8, cursor: 'pointer',
                }}>
                <Icon name="star-filled" size={16} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, color: 'var(--text-primary)', fontWeight: 600 }}>
                    {m.entity_label}{m.entity_type !== 'horse' && m.horse_name ? ` · ${m.horse_name}` : ''}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {m.course} · {m.race_name}{m.post_time_et ? ` · ${m.post_time_et} ET` : ''} · {m.day ? m.day.charAt(0).toUpperCase() + m.day.slice(1) : ''}
                  </div>
                </div>
                <Icon name="chevron-right" size={16} />
              </div>
            ))
          )}
        </div>

        {/* Following */}
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', letterSpacing: '0.06em', marginBottom: 10 }}>
          FOLLOWING ({items.length})
        </div>
        {isLoading ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading…</div>
        ) : items.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Tap the ☆ next to any horse, trainer, or jockey on a race page to follow them.
          </div>
        ) : (
          grouped.map((g) => (
            <div key={g.type} style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6 }}>{TYPE_LABEL[g.type]}</div>
              {g.rows.map((it) => (
                <div key={it.id} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
                  background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', marginBottom: 6,
                }}>
                  <span style={{ flex: 1, fontSize: 14, color: 'var(--text-primary)' }}>{it.entity_label}</span>
                  <button onClick={() => remove.mutate(it.id)} disabled={remove.isPending}
                    aria-label={`Unfollow ${it.entity_label}`}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-gold-bright)', padding: 4, display: 'inline-flex' }}>
                    <Icon name="star-filled" size={16} />
                  </button>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
