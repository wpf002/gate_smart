import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import BottomNav from './components/common/BottomNav';
import HomePage from './pages/HomePage';
import RaceDetailPage from './pages/RaceDetailPage';
import HorseDetailPage from './pages/HorseDetailPage';
import SearchPage from './pages/SearchPage';
import AdvisorPage from './pages/AdvisorPage';
import BetSlipPage from './pages/BetSlipPage';
import EducationPage from './pages/EducationPage';
import ProfilePage from './pages/ProfilePage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <div className="page-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/race/:raceId" element={<RaceDetailPage />} />
            <Route path="/horse/:horseId" element={<HorseDetailPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/advisor" element={<AdvisorPage />} />
            <Route path="/betslip" element={<BetSlipPage />} />
            <Route path="/education" element={<EducationPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </div>
        <BottomNav />
      </div>
    </BrowserRouter>
  );
}
