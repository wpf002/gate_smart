import { useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import BottomNav from './components/common/BottomNav';
import HomePage from './pages/HomePage';
import RaceDetailPage from './pages/RaceDetailPage';
import HorseDetailPage from './pages/HorseDetailPage';
import SearchPage from './pages/SearchPage';
import AdvisorPage from './pages/AdvisorPage';
import BetSlipPage from './pages/BetSlipPage';
import EducationPage from './pages/EducationPage';
import ProfilePage from './pages/ProfilePage';
import SimulatorPage from './pages/SimulatorPage';
import LoginPage from './pages/LoginPage';
import OnboardingFlow from './components/common/OnboardingFlow';
import { useAppStore } from './store';

const NAV_ITEMS = [
  { path: '/', icon: '🏠', label: 'Races' },
  { path: '/search', icon: '🔍', label: 'Search' },
  { path: '/simulator', icon: '📈', label: 'Simulator' },
  { path: '/advisor', icon: '🤖', label: 'Advisor' },
  { path: '/betslip', icon: '🎫', label: 'Bet Slip' },
  { path: '/education', icon: '📚', label: 'Learn' },
  { path: '/profile', icon: '👤', label: 'Profile' },
];

function SideNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const betSlip = useAppStore((s) => s.betSlip);

  return (
    <nav className="side-nav">
      <div className="side-nav-logo">GATE<br />SMART</div>
      {NAV_ITEMS.map(({ path, icon, label }) => {
        const active = location.pathname === path ||
          (path !== '/' && location.pathname.startsWith(path));
        const isBetSlip = path === '/betslip';
        return (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`side-nav-item${active ? ' active' : ''}`}
          >
            <span className="side-nav-icon">{icon}</span>
            <span>{label}</span>
            {isBetSlip && betSlip.length > 0 && (
              <span style={{
                marginLeft: 'auto',
                background: 'var(--accent-gold)',
                color: '#000',
                borderRadius: '50%',
                width: 18,
                height: 18,
                fontSize: 11,
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {betSlip.length}
              </span>
            )}
          </button>
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
    <div style={{
      position: 'fixed',
      bottom: 80,
      left: '50%',
      transform: 'translateX(-50%)',
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

function AppShell() {
  const onboardingComplete = useAppStore((s) => s.onboardingComplete);
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
      {!onboardingComplete && <OnboardingFlow />}
      <SideNav />
      <BetSlipToast />
      <div className="page-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/race/:raceId" element={<RaceDetailPage />} />
          <Route path="/horse/:horseId" element={<HorseDetailPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/advisor" element={<AdvisorPage />} />
          <Route path="/betslip" element={<BetSlipPage />} />
          <Route path="/education" element={<EducationPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </div>
      <BottomNav />
    </div>
  );
}

export default function App() {
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
    </BrowserRouter>
  );
}
