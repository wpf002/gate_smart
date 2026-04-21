import { useNavigate, useLocation } from 'react-router-dom';
import Icon from './Icon';

const NAV_ITEMS = [
  { path: '/',        icon: 'home',      label: 'Races'   },
  { path: '/search',  icon: 'search',    label: 'Search'  },
  { path: '/advisor', icon: 'simulator', label: 'Advisor' },
  { path: '/profile', icon: 'profile',   label: 'Profile' },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();

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
              minHeight: 44,
              minWidth: 44,
            }}
          >
            <Icon name={icon} size={22} />
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.04em' }}>
              {label}
            </span>
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
