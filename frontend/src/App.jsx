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

function AppShell() {
  return (
    <div className="app-shell">
      <SideNav />
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
        </Routes>
      </div>
      <BottomNav />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
