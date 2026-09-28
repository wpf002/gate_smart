/**
 * LandingPage — the front door for logged-out visitors.
 *
 * The one thing worth pinning down here is the break-even block. It states the
 * gap between how often the top pick wins and how often it would have to win to
 * return the stake, over 30 days. It must never overstate the picks, and it must
 * not fall over when the numbers aren't in yet.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const ACCURACY = {
  total_predictions: 100, win_rate_percent: 18, place_rate_percent: 42, show_rate_percent: 58,
};

// Real /api/accuracy/bet-curve?days=30 shape, trimmed to the fields used here.
const CURVE = {
  days: 30, points: [], total_bets: 3732, staked: 7464, net: -1653.84, roi: -0.2216,
  unpriced_excluded: 41,
  breakeven: { bets: 3732, cashed: 993, hit_rate: 0.266, avg_payoff: 5.85,
               needed_rate: 0.342, gap: -0.076 },
};

const api = {
  getSecretariatAccuracy: vi.fn(() => Promise.resolve(ACCURACY)),
  getBetCurve: vi.fn(() => Promise.resolve(CURVE)),
};
vi.mock('../utils/api', () => ({
  getSecretariatAccuracy: (...a) => api.getSecretariatAccuracy(...a),
  getBetCurve: (...a) => api.getBetCurve(...a),
}));

import LandingPage from '../pages/LandingPage';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><LandingPage onGetStarted={vi.fn()} /></QueryClientProvider>);
}

beforeEach(() => Object.values(api).forEach((f) => f.mockClear()));

describe('LandingPage break-even block', () => {
  it('states the win rate, the rate needed, and the gap between them', async () => {
    wrap();
    // Each rate appears twice: once in the figure row, once in the sentence
    // under it. Both must be the same number.
    expect(await screen.findAllByText('26.6%')).toHaveLength(2);    // wins
    expect(screen.getAllByText('34.2%')).toHaveLength(2);           // needs
    expect(screen.getByText('−7.6')).toBeInTheDocument();           // gap, in points
    expect(screen.getByText('Wins')).toBeInTheDocument();
    expect(screen.getByText('Needs')).toBeInTheDocument();
    expect(screen.getByText('Gap')).toBeInTheDocument();
  });

  it('says plainly that the picks do not clear the bar yet', async () => {
    wrap();
    expect(await screen.findByText(/doesn't clear the bar yet/)).toBeInTheDocument();
    expect(screen.getByText(/3,732 races/)).toBeInTheDocument();
  });

  it('reads 30 days, not a single day, so one longshot cannot move it', async () => {
    wrap();
    await screen.findByText('Gap');
    expect(api.getBetCurve).toHaveBeenCalledWith(30);
  });

  it('claims a positive gap only when the picks actually cleared the bar', async () => {
    api.getBetCurve.mockImplementationOnce(() => Promise.resolve({
      ...CURVE,
      breakeven: { ...CURVE.breakeven, hit_rate: 0.38, needed_rate: 0.342, gap: 0.038 },
    }));
    wrap();
    expect(await screen.findByText('+3.8')).toBeInTheDocument();
    expect(screen.getByText(/It clears the bar\./)).toBeInTheDocument();
  });

  it('falls back to prose when no race has been priced yet', async () => {
    api.getBetCurve.mockImplementationOnce(() => Promise.resolve({
      days: 30, points: [], total_bets: 0, breakeven: { bets: 0, hit_rate: null, needed_rate: null, gap: null },
    }));
    wrap();
    expect(await screen.findByText(/clear what the chalk costs/)).toBeInTheDocument();
    expect(screen.queryByText('Gap')).not.toBeInTheDocument();
  });
});
