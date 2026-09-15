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

// Trimmed /api/races/today racecards. "Now" in these tests is 18:00 UTC.
const NOW = Date.parse('2026-09-13T18:00:00Z');
const card = (race_id, off_dt, extra = {}) => ({
  race_id, off_dt, course: 'Churchill Downs', field_size: 9, is_cancelled: false, has_results: false, ...extra,
});
const TODAY = {
  racecards: [
    card('CD_1789257600000-9', '2026-09-13T22:00:00+00:00'),
    card('CD_1789257600000-2', '2026-09-13T17:00:00+00:00', { has_results: true }),
    card('CD_1789257600000-5', '2026-09-13T18:20:00+00:00'),
    card('CD_1789257600000-6', '2026-09-13T19:00:00+00:00', { is_cancelled: true }),
    card('GP_1789257600000-7', '2026-09-13T18:45:00+00:00', { course: 'Gulfstream Park' }),
  ],
};

const api = {
  getLeaderboard: vi.fn(() => Promise.resolve(BOARD)),
  getContestProgress: vi.fn(() => Promise.resolve(ME)),
  setDisplayName: vi.fn(() => Promise.resolve({ display_name: 'Chalk Eater' })),
  getBetCurve: vi.fn(() => Promise.resolve(CURVE)),
  getRacesToday: vi.fn(() => Promise.resolve({ racecards: [] })),
  getRacesByDate: vi.fn(() => Promise.resolve({ racecards: [] })),
};
vi.mock('../utils/api', () => ({
  getLeaderboard: (...a) => api.getLeaderboard(...a),
  getContestProgress: (...a) => api.getContestProgress(...a),
  setDisplayName: (...a) => api.setDisplayName(...a),
  getBetCurve: (...a) => api.getBetCurve(...a),
  getRacesToday: (...a) => api.getRacesToday(...a),
  getRacesByDate: (...a) => api.getRacesByDate(...a),
}));

import ContestPage from '../pages/ContestPage';
import BetCurve from '../components/accuracy/BetCurve';
import NextToPost from '../components/contest/NextToPost';

function wrap(node) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>
  );
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockClear());
  api.getRacesToday.mockImplementation(() => Promise.resolve({ racecards: [] }));
  api.getRacesByDate.mockImplementation(() => Promise.resolve({ racecards: [] }));
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
    expect(await screen.findByText('4/8')).toBeInTheDocument();
    expect(screen.getByText('Day Streak')).toBeInTheDocument();
    expect(screen.getByText('Beat Streak')).toBeInTheDocument();
  });

  it('shows a first-pick prompt instead of a card of zeros for a new player', async () => {
    useAppStore.setState({ authToken: 'token' });
    api.getContestProgress.mockImplementationOnce(() => Promise.resolve({
      display_name: 'Handicapper 3', pick_day_streak: 0, beat_secretariat_streak: 0,
      best_correct_streak: 0, total_picks: 0, settled: 0, wins: 0, beat_secretariat: 0, points: 0,
    }));
    wrap(<ContestPage />);
    expect(await screen.findByText('NO PICKS YET')).toBeInTheDocument();
    expect(screen.getByText('Make Your First Pick')).toBeInTheDocument();
    expect(screen.getByText('Set Your Name')).toBeInTheDocument();
    expect(screen.queryByText('Day Streak')).not.toBeInTheDocument();
    expect(screen.queryByText('Handicapper 3 · Edit Name')).not.toBeInTheDocument();
  });

  it('switches between today and this week', async () => {
    wrap(<ContestPage />);
    await screen.findByText('Longshot Larry');
    fireEvent.click(screen.getByText('Today'));
    await waitFor(() => expect(api.getLeaderboard).toHaveBeenCalledWith('day'));
  });
});

describe('NextToPost', () => {
  it('lists only races still open for a pick, soonest first', async () => {
    api.getRacesToday.mockImplementation(() => Promise.resolve(TODAY));
    wrap(<NextToPost now={NOW} />);
    expect(await screen.findByText('NEXT TO POST')).toBeInTheDocument();
    // Race 2 already has results and race 6 is cancelled.
    expect(screen.getAllByText(/^Race \d/).map((el) => el.textContent)).toEqual([
      'Race 5 · 9 runners', 'Race 7 · 9 runners', 'Race 9 · 9 runners',
    ]);
    expect(screen.getByText('in 20 min')).toBeInTheDocument();
    expect(api.getRacesByDate).not.toHaveBeenCalled();
  });

  it("falls back to tomorrow's card once today's last race is off", async () => {
    api.getRacesToday.mockImplementation(() => Promise.resolve({ racecards: [card('CD_1789257600000-2', '2026-09-13T17:00:00+00:00')] }));
    api.getRacesByDate.mockImplementation(() => Promise.resolve({ racecards: [card('SA_1789344000000-1', '2026-09-14T20:00:00+00:00', { course: 'Santa Anita' })] }));
    wrap(<NextToPost now={NOW} />);
    expect(await screen.findByText('Santa Anita')).toBeInTheDocument();
    expect(screen.getByText('Tomorrow')).toBeInTheDocument();
    expect(api.getRacesByDate).toHaveBeenCalledWith('tomorrow', 'usa');
  });

  it('renders nothing when no race is open', async () => {
    const { container } = wrap(<NextToPost now={NOW} />);
    await waitFor(() => expect(api.getRacesByDate).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});

describe('BetCurve', () => {
  it('states the running result and return from official payouts', async () => {
    wrap(<BetCurve />);
    expect(await screen.findByText('$2 ON EVERY PICK')).toBeInTheDocument();
    expect(screen.getByText('−$9')).toBeInTheDocument();
    expect(screen.getByText('-1.0% Return')).toBeInTheDocument();
    expect(screen.getByText(/2 Unpriced Excluded/)).toBeInTheDocument();
  });

  it('draws one line with a break-even baseline', async () => {
    const { container } = wrap(<BetCurve />);
    await screen.findByText('$2 ON EVERY PICK');
    expect(container.querySelectorAll('svg path')).toHaveLength(2); // area + line
    expect(screen.getByText('Break Even')).toBeInTheDocument();
  });
});
