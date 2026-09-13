/**
 * ContestPage and BetCurve — leaderboard, streaks, and the $2-on-every-pick line.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from '../store';

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

const BOARD = {
  period: 'week',
  since: '2026-09-07',
  scoring: { correct_winner: 10, beat_secretariat_bonus: 5 },
  secretariat: { races: 1098, win_rate: 0.281 },
  board: [
    { rank: 1, name: 'Longshot Larry', points: 45, picks: 6, wins: 3, win_rate: 0.5, beat_secretariat: 3 },
    { rank: 2, name: 'Handicapper 7', points: 20, picks: 5, wins: 2, win_rate: 0.4, beat_secretariat: 0 },
  ],
};

const ME = {
  display_name: 'Handicapper 7', pick_day_streak: 4, beat_secretariat_streak: 2,
  best_correct_streak: 3, total_picks: 9, settled: 8, wins: 4, beat_secretariat: 2, points: 50,
};

// Real /api/accuracy/bet-curve?days=7 response, trimmed to three days.
const CURVE = {
  days: 7,
  points: [
    { date: '2026-09-06', bets: 193, net: -27.44, cumulative: -27.44 },
    { date: '2026-09-07', bets: 197, net: 33.08, cumulative: 5.64 },
    { date: '2026-09-08', bets: 68, net: -14.82, cumulative: -9.18 },
  ],
  total_bets: 458, staked: 916.0, net: -9.18, roi: -0.01, unpriced_excluded: 2,
};

const api = {
  getLeaderboard: vi.fn(() => Promise.resolve(BOARD)),
  getContestProgress: vi.fn(() => Promise.resolve(ME)),
  setDisplayName: vi.fn(() => Promise.resolve({ display_name: 'Chalk Eater' })),
  getBetCurve: vi.fn(() => Promise.resolve(CURVE)),
};
vi.mock('../utils/api', () => ({
  getLeaderboard: (...a) => api.getLeaderboard(...a),
  getContestProgress: (...a) => api.getContestProgress(...a),
  setDisplayName: (...a) => api.setDisplayName(...a),
  getBetCurve: (...a) => api.getBetCurve(...a),
}));

import ContestPage from '../pages/ContestPage';
import BetCurve from '../components/accuracy/BetCurve';

function wrap(node) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>
  );
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockClear());
  useAppStore.setState({ authToken: null });
});

describe('ContestPage', () => {
  it('ranks players and shows Secretariat as a win rate to beat', async () => {
    wrap(<ContestPage />);
    expect(await screen.findByText('Longshot Larry')).toBeInTheDocument();
    expect(screen.getByText('28.1%')).toBeInTheDocument();
    expect(screen.getByText('beat S×3')).toBeInTheDocument();
  });

  it('never shows an email address on the board', async () => {
    wrap(<ContestPage />);
    await screen.findByText('Longshot Larry');
    expect(document.body.textContent).not.toMatch(/@/);
  });

  it('asks signed-out visitors to sign in instead of showing streaks', async () => {
    wrap(<ContestPage />);
    expect(await screen.findByText('Sign in to make picks and track your streaks.')).toBeInTheDocument();
    expect(api.getContestProgress).not.toHaveBeenCalled();
  });

  it('shows streaks and totals for a signed-in player', async () => {
    useAppStore.setState({ authToken: 'token' });
    wrap(<ContestPage />);
    expect(await screen.findByText('Day streak')).toBeInTheDocument();
    expect(screen.getByText('Beat streak')).toBeInTheDocument();
    expect(screen.getByText('4/8')).toBeInTheDocument();
  });

  it('switches between today and this week', async () => {
    wrap(<ContestPage />);
    await screen.findByText('Longshot Larry');
    fireEvent.click(screen.getByText('Today'));
    await waitFor(() => expect(api.getLeaderboard).toHaveBeenCalledWith('day'));
  });
});

describe('BetCurve', () => {
  it('states the running result and return from official payouts', async () => {
    wrap(<BetCurve />);
    expect(await screen.findByText('$2 ON EVERY PICK')).toBeInTheDocument();
    expect(screen.getByText('−$9')).toBeInTheDocument();
    expect(screen.getByText('-1.0% return')).toBeInTheDocument();
    expect(screen.getByText(/2 unpriced races left out/)).toBeInTheDocument();
  });

  it('draws one line with a break-even baseline', async () => {
    const { container } = wrap(<BetCurve />);
    await screen.findByText('$2 ON EVERY PICK');
    expect(container.querySelectorAll('svg path')).toHaveLength(2); // area + line
    expect(screen.getByText('break even')).toBeInTheDocument();
  });
});
