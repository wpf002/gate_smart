import { Component, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import Icon from './components/common/Icon';
import BottomNav from './components/common/BottomNav';
import HomePage from './pages/HomePage';
import RaceDetailPage from './pages/RaceDetailPage';
import HorseDetailPage from './pages/HorseDetailPage';
import SearchPage from './pages/SearchPage';
import AdvisorPage from './pages/AdvisorPage';
import EducationPage from './pages/EducationPage';
import ProfilePage from './pages/ProfilePage';
import LoginPage from './pages/LoginPage';
import AccuracyPage from './pages/AccuracyPage';
import OnboardingFlow from './components/common/OnboardingFlow';
import { useAppStore } from './store';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: 32,
          textAlign: 'center',
          color: 'var(--text-muted)',
          maxWidth: 400,
          margin: '60px auto',
        }}>
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'center', color: 'var(--accent-red-bright)' }}><Icon name="warning" size={40} /></div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--accent-gold)', marginBottom: 10 }}>
            Something went wrong
          </div>
          <div style={{ fontSize: 13, marginBottom: 20, lineHeight: 1.6 }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button
            className="btn btn-primary"
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.href = '/'; }}
          >
            Go back to races
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const NAV_ITEMS = [
  { path: '/',          icon: 'home',    label: 'Races'   },
  { path: '/search',    icon: 'search',  label: 'Search'  },
  { path: '/advisor',   icon: 'robot',   label: 'Advisor' },
  { path: '/education', icon: 'learn',   label: 'Learn'   },
  { path: '/profile',   icon: 'profile', label: 'Profile' },
];

function SideNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  // Tapping Races or the GateSmart logo always lands on a freshly-refetched
  // Races list. When the user is already on the home route, navigate() is a
  // no-op, so we scroll to top and force a refetch ourselves so the tap gives
  // clear visual feedback that something happened.
  const goToRacesFresh = () => {
    queryClient.invalidateQueries({ queryKey: ['races'] });
    if (location.pathname === '/') {
      const scroller = document.querySelector('.page-content');
      if (scroller) scroller.scrollTo({ top: 0, behavior: 'smooth' });
      queryClient.refetchQueries({ queryKey: ['races'], type: 'active' });
    } else {
      navigate('/');
    }
  };

  const goTo = (path) => {
    if (path === '/') return goToRacesFresh();
    navigate(path);
  };

  return (
    <nav className="side-nav">
      <div className="side-nav-logo" onClick={goToRacesFresh} style={{ cursor: 'pointer' }}>GATE<br />SMART</div>
      {NAV_ITEMS.map(({ path, label }, idx) => {
        const active = location.pathname === path ||
          (path !== '/' && location.pathname.startsWith(path));
        return (
          <div key={path}>
            {idx > 0 && (
              <div style={{
                height: 1,
                margin: '0 16px',
                background: 'linear-gradient(to right, transparent, rgba(201,162,39,0.2), transparent)',
              }} />
            )}
            <button
              onClick={() => goTo(path)}
              className={`side-nav-item${active ? ' active' : ''}`}
            >
              <span style={{
                fontSize: 12,
                fontWeight: active ? 700 : 500,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: active ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
              }}>{label}</span>
            </button>
          </div>
        );
      })}
    </nav>
  );
}

function BetSlipToast() {
  const toast = useAppStore((s) => s.betSlipToast);
  const clearBetSlipToast = useAppStore((s) => s.clearBetSlipToast);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!toast) return;
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => clearBetSlipToast(), 2500);
    return () => clearTimeout(timerRef.current);
  }, [toast?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!toast) return null;
  return (
    <div className="bet-slip-toast" style={{
      background: 'var(--bg-elevated)',
      border: '1px solid var(--accent-gold-dim)',
      borderRadius: 'var(--radius-md)',
      padding: '10px 18px',
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--text-primary)',
      zIndex: 9999,
      pointerEvents: 'none',
      whiteSpace: 'nowrap',
      boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
    }}>
      {toast.message}
    </div>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    const scroller = document.querySelector('.page-content');
    if (scroller) scroller.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [pathname]);
  return null;
}

function AppShell() {
  const onboardingComplete = useAppStore((s) => s.onboardingComplete);
  const authToken = useAppStore((s) => s.authToken);
  const location = useLocation();

  useEffect(() => {
    if (!window.gtag) return;
    const gaId = import.meta.env.VITE_GA_MEASUREMENT_ID;
    if (!gaId) return;
    window.gtag('event', 'page_view', {
      page_path: location.pathname,
      page_title: document.title,
    });
  }, [location.pathname]);

  return (
    <div className="app-shell">
      {(!onboardingComplete || !authToken) && <OnboardingFlow />}
      <SideNav />
      <BetSlipToast />
      <ScrollToTop />
      <div className="page-content">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/race/:raceId" element={<RaceDetailPage />} />
            <Route path="/horse/:horseId" element={<HorseDetailPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/advisor" element={<AdvisorPage />} />
            <Route path="/education" element={<EducationPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/accuracy" element={<AccuracyPage />} />
          </Routes>
        </ErrorBoundary>
      </div>
      <BottomNav />
    </div>
  );
}

function IOSInstallBanner() {
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isInStandaloneMode = window.matchMedia('(display-mode: standalone)').matches;
  const [visible, setVisible] = useState(
    isIOS && !isInStandaloneMode && !localStorage.getItem('gs_install_prompted')
  );

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 10000,
      background: '#C9A84C',
      color: '#0a0a0a',
      padding: '12px 16px',
      fontSize: 13,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 10,
    }}>
      <span>
        Add GateSmart to your home screen — works on any device. Tap Share → Add to Home Screen
      </span>
      <button
        onClick={() => {
          localStorage.setItem('gs_install_prompted', '1');
          setVisible(false);
        }}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 20,
          lineHeight: 1,
          color: '#0a0a0a',
          flexShrink: 0,
          padding: 4,
        }}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

export default function App() {
  // Service Worker registration
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js')
        .catch(err => console.log('SW registration failed:', err));
    }
  }, []);

  // OneSignal
  useEffect(() => {
    const appId = import.meta.env.VITE_ONESIGNAL_APP_ID;
    if (!appId) return;
    window.OneSignalDeferred = window.OneSignalDeferred || [];
    window.OneSignalDeferred.push(async (OneSignal) => {
      await OneSignal.init({
        appId,
        notifyButton: { enable: false },
        allowLocalhostAsSecureOrigin: true,
      });
    });
  }, []);

  // GA4 init
  useEffect(() => {
    const gaId = import.meta.env.VITE_GA_MEASUREMENT_ID;
    if (!gaId) return;

    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${gaId}`;
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    window.gtag = function() { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', gaId, {
      page_path: window.location.pathname,
      cookie_flags: 'SameSite=None;Secure',
    });
  }, []);

  return (
    <BrowserRouter>
      <AppShell />
      <IOSInstallBanner />
    </BrowserRouter>
  );
}
