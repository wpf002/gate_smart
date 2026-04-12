import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../../store';

const NAV_ITEMS = [
  { path: '/', icon: '🏠', label: 'Races' },
  { path: '/search', icon: '🔍', label: 'Search' },
  { path: '/betslip', icon: '🏇', label: 'My Picks' },
  { path: '/advisor', icon: '🤖', label: 'Advisor' },
  { path: '/profile', icon: '👤', label: 'Profile' },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const betSlip = useAppStore((s) => s.betSlip);

  return (
    <nav className="bottom-nav" style={{
      height: 'var(--bottom-nav-height)',
      borderTop: '1px solid var(--border-subtle)',
      background: 'var(--bg-secondary)',
      display: 'flex',
      alignItems: 'stretch',
      flexShrink: 0,
    }}>
      {NAV_ITEMS.map(({ path, icon, label }) => {
        const active = location.pathname === path ||
          (path !== '/' && location.pathname.startsWith(path));
        return (
          <button
            key={path}
            onClick={() => navigate(path)}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 3,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              position: 'relative',
              color: active ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              transition: 'color 0.15s',
            }}
          >
            <span style={{ fontSize: 20, lineHeight: 1 }}>{icon}</span>
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.04em' }}>
              {label}
            </span>
            {path === '/betslip' && betSlip.length > 0 && (
              <span style={{
                position: 'absolute',
                top: 6,
                right: '20%',
                background: 'var(--accent-gold)',
                color: '#000',
                borderRadius: '50%',
                width: 16,
                height: 16,
                fontSize: 10,
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {betSlip.length}
              </span>
            )}
            {active && (
              <span style={{
                position: 'absolute',
                bottom: 0,
                left: '20%',
                right: '20%',
                height: 2,
                background: 'var(--accent-gold)',
                borderRadius: 2,
              }} />
            )}
          </button>
        );
      })}
    </nav>
  );
}
