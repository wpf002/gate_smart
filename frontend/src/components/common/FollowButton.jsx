import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../../utils/api';
import { useAppStore } from '../../store';
import Icon from './Icon';

// Must mirror backend normalize_entity so followed-state checks line up.
export function normalizeEntity(name) {
  return (name || '')
    .toLowerCase()
    .trim()
    .replace(/'/g, '')
    .replace(/-/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Star toggle to follow/unfollow a horse, trainer, or jockey.
 * The auth gate lives in the wrapper so the query-using inner component only
 * mounts for signed-in users — logged-out (and tests without a QueryClient)
 * render nothing and never touch react-query.
 */
export default function FollowButton({ entityType, entityLabel, entityKey = null, size = 16 }) {
  const authToken = useAppStore((s) => s.authToken);
  if (!authToken || !entityLabel) return null;
  return (
    <FollowButtonInner entityType={entityType} entityLabel={entityLabel} entityKey={entityKey} size={size} />
  );
}

function FollowButtonInner({ entityType, entityLabel, entityKey, size }) {
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    staleTime: 60 * 1000,
  });

  const key = normalizeEntity(entityKey || entityLabel);
  const existing = (data?.items || []).find(
    (i) => i.entity_type === entityType && i.entity_key === key
  );
  const followed = !!existing;

  const mutation = useMutation({
    mutationFn: () =>
      followed
        ? removeFromWatchlist(existing.id)
        : addToWatchlist(entityType, entityLabel, entityKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlist'] });
      qc.invalidateQueries({ queryKey: ['watchlist-today'] });
    },
  });

  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); mutation.mutate(); }}
      disabled={mutation.isPending}
      aria-label={followed ? `Unfollow ${entityLabel}` : `Follow ${entityLabel}`}
      title={followed ? `Unfollow ${entityLabel}` : `Follow ${entityLabel}`}
      style={{
        background: 'none', border: 'none', cursor: 'pointer', padding: 4,
        display: 'inline-flex', alignItems: 'center',
        color: followed ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
        opacity: mutation.isPending ? 0.5 : 1,
      }}
    >
      <Icon name={followed ? 'star-filled' : 'star'} size={size} />
    </button>
  );
}
