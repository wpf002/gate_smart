// Throwaway harness. Not shipped.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './styles/globals.css';
import AccuracyBadge from './components/common/AccuracyBadge';
import LandingPage from './pages/LandingPage';

const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchOnMount: false } } });
const ACC = { total_predictions: 3338, correct_predictions: 888, win_rate_percent: 26.6,
  place_rate_percent: 47.8, show_rate_percent: 62.0, days: 30, since: '2026-08-30' };
qc.setQueryData(['secretariat-accuracy'], ACC);
qc.setQueryData(['landing-breakeven'], { days: 30, points: [], total_bets: 3569,
  breakeven: { bets: 3569, cashed: 951, hit_rate: 0.2665, avg_payoff: 5.8, needed_rate: 0.3448, gap: -0.0783 } });

createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={qc}><MemoryRouter>
    <div style={{ background: 'var(--bg-primary)', padding: 16 }}>
      <div style={{ maxWidth: 520, marginBottom: 24 }}><AccuracyBadge /></div>
      <LandingPage onGetStarted={() => {}} />
    </div>
  </MemoryRouter></QueryClientProvider>);
