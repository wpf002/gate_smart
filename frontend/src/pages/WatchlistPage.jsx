import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getWatchlist, getWatchlistToday, removeFromWatchlist } from '../utils/api';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import Icon from '../components/common/Icon';

const TYPE_LABEL = { horse: 'Horses', trainer: 'Trainers', jockey: 'Jockeys' };
const TYPE_ORDER = ['horse', 'trainer', 'jockey'];

export default function WatchlistPage() {
  const authToken = useAppStore((s) => s.authToken);
  const navigate = useNavigate();
  const qc = useQueryClient();

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

  return (
    <div>
      <PageHeader title="WATCHLIST" subtitle="FOLLOW HORSES, TRAINERS & JOCKEYS" />

      <div style={{ padding: '12px 20px 24px' }}>
        {/* Racing today */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', letterSpacing: '0.06em', marginBottom: 10 }}>
            RACING SOON ({matches.length})
          </div>
          {matches.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              None of your follows are entered in today's or tomorrow's cards yet.
            </div>
          ) : (
            matches.map((m, i) => (
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
