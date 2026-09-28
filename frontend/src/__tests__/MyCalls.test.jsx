/**
 * MyCalls — the calls you've already locked in, on the contest page.
 *
 * Two things matter here. A pick must never vanish: not when its race card
 * isn't in cache, and not when it's on tomorrow's card. And a settled call must
 * report what actually happened, including the case where the chart carried no
 * price and the bet scored nothing either way.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from '../store';

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => navigate };
});

const NOW = new Date('2026-09-28T22:00:00Z').getTime();

const CARDS = {
  racecards: [
    { race_id: 'LAD_1790553600000-7', course: 'Louisiana Downs', off_dt: '2026-09-28T23:23:00+00:00' },
    { race_id: 'ALB_1790553600000-9', course: 'Albuquerque', off_dt: '2026-09-28T21:30:00+00:00' },
  ],
};

const PICKS = {
  date: '2026-09-28',
  stake: 2,
  picks: [
    { race_id: 'LAD_1790553600000-7', race_date: '2026-09-28', horse_name: 'Apicturesworth',
      bet_type: 'win', bet_label: 'Win', selections: [{ name: 'Apicturesworth', number: '1' }],
      settled: false, points: 0, payoff: null, net: null },
    { race_id: 'ALB_1790553600000-9', race_date: '2026-09-28', horse_name: 'Lady of Lords',
      bet_type: 'exacta', bet_label: 'Exacta',
      selections: [{ name: 'Lady of Lords', number: '2' }, { name: 'Gate Crasher', number: '5' }],
      settled: true, correct: true, points: 25, payoff: 41.2, net: 39.2 },
  ],
};

const api = {
  getMyContestPicks: vi.fn(() => Promise.resolve(PICKS)),
  getRacesToday: vi.fn(() => Promise.resolve(CARDS)),
  getRacesByDate: vi.fn(() => Promise.resolve({ racecards: [] })),
};
vi.mock('../utils/api', () => ({
  getMyContestPicks: (...a) => api.getMyContestPicks(...a),
  getRacesToday: (...a) => api.getRacesToday(...a),
  getRacesByDate: (...a) => api.getRacesByDate(...a),
}));

import MyCalls from '../components/contest/MyCalls';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><MemoryRouter><MyCalls now={NOW} /></MemoryRouter></QueryClientProvider>
  );
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockClear());
  navigate.mockClear();
  useAppStore.setState({ authToken: 'token', userProfile: { timezone: 'America/Chicago' } });
});

describe('MyCalls', () => {
  it('lists each call with its bet, track and race', async () => {
    wrap();
    expect(await screen.findByText('Apicturesworth')).toBeInTheDocument();
    expect(screen.getByText('Win · Louisiana Downs Race 7')).toBeInTheDocument();
    expect(screen.getByText('Exacta 2-5')).toBeInTheDocument();
    expect(screen.getByText('Exacta · Albuquerque Race 9')).toBeInTheDocument();
  });

  it('marks a call still open, and says it can be changed', async () => {
    wrap();
    expect(await screen.findByText('Open')).toBeInTheDocument();
    expect(screen.getByText('Change →')).toBeInTheDocument();
    expect(screen.getByText('1 still open · change until the gate')).toBeInTheDocument();
  });

  it('shows the points and what $2 returned once a call is graded', async () => {
    wrap();
    expect(await screen.findByText('+25')).toBeInTheDocument();
    expect(screen.getByText('+$39.20')).toBeInTheDocument();
    expect(screen.getByText('Graded')).toBeInTheDocument();
  });

  it('calls a voided bet "no price" rather than showing it as a loss', async () => {
    api.getMyContestPicks.mockImplementationOnce(() => Promise.resolve({
      ...PICKS,
      picks: [{ ...PICKS.picks[1], correct: null, points: 0, payoff: null, net: null }],
    }));
    wrap();
    expect(await screen.findByText('No price')).toBeInTheDocument();
    expect(screen.queryByText('+0')).not.toBeInTheDocument();
  });

  it('keeps a call visible when its race card is not in cache', async () => {
    api.getRacesToday.mockImplementationOnce(() => Promise.resolve({ racecards: [] }));
    wrap();
    // Falls back to the track code and race number carried by the race_id.
    expect(await screen.findByText('Win · LAD Race 7')).toBeInTheDocument();
  });

  it('opens the race when a call is clicked', async () => {
    wrap();
    (await screen.findByText('Apicturesworth')).closest('button').click();
    expect(navigate).toHaveBeenCalledWith('/race/LAD_1790553600000-7');
  });

  it('renders nothing when no call has been made', async () => {
    api.getMyContestPicks.mockImplementationOnce(() => Promise.resolve({ picks: [] }));
    const { container } = wrap();
    await waitFor(() => expect(api.getMyContestPicks).toHaveBeenCalled());
    expect(container.querySelector('button')).toBeNull();
  });

  it('asks for no picks at all when signed out', () => {
    useAppStore.setState({ authToken: null });
    wrap();
    expect(api.getMyContestPicks).not.toHaveBeenCalled();
  });
});
