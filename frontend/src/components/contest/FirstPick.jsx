import { useNavigate } from 'react-router-dom';
import Icon from '../common/Icon';
import { useOpenRaces } from './NextToPost';

// The leaderboard gives every account "Handicapper <id>" until a name is set.
export const isDefaultName = (name) => /^Handicapper \d+$/.test(name || '');

/**
 * Shown in place of a player's stats until they have made a pick. A card of six
 * zeros is accurate, but it reads as placeholder data.
 */
export default function FirstPick({ divider = false }) {
  const navigate = useNavigate();
  const { races } = useOpenRaces();
  const next = races[0];

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      textAlign: 'center', gap: 10, padding: '28px 20px',
      borderTop: divider ? '1px solid var(--border-subtle)' : 'none',
    }}>
      <Icon name="trophy" size={28} color="var(--accent-gold)" />
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--text-primary)', letterSpacing: '0.04em' }}>
        NO PICKS YET
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 260, lineHeight: 1.5 }}>
        Call the winner of any race before it starts. Your points and streaks start with your first pick.
      </div>
      <button
        className="btn btn-primary"
        style={{ fontSize: 13, padding: '8px 16px', marginTop: 4 }}
        onClick={() => navigate(next ? `/race/${next.race_id}` : '/')}
      >
        Make Your First Pick
      </button>
    </div>
  );
}
