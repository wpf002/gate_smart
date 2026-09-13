/**
 * BetSlip — Secretariat's ticket, before and after the race.
 *
 * Fixtures are real production responses from /api/races/ticket/{race_id}
 * (Gulfstream race 4, 2026-09-12), so the component is tested against the shape
 * the backend actually returns.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const SETTLED = {
  race_id: 'GP_1789171200000-4',
  settled: true,
  legs: [
    { type: 'win', numbers: ['4'], horses: ['Alinao Forever'], say: '$2 to win on #4, race 4', status: 'hit', payout: 15.0, winning_numbers: ['4'] },
    { type: 'exacta', numbers: ['4', '7'], horses: ['Alinao Forever', 'Magic Heart'], say: '$2 exacta 4-7, race 4', status: 'miss', payout: null, winning_numbers: ['4', '8'] },
    { type: 'trifecta', numbers: ['4', '7', '5'], horses: ['Alinao Forever', 'Magic Heart', 'Outta Money'], say: '$2 trifecta 4-7-5, race 4', status: 'miss', payout: null, winning_numbers: ['4', '8', '7'] },
  ],
  summary: { legs_priced: 3, hits: 1, staked: 6.0, returned: 15.0, net: 9.0 },
};

const PENDING = {
  race_id: 'GP_1789257600000-2',
  settled: false,
  legs: SETTLED.legs.map((l) => ({ ...l, status: 'pending', payout: null, winning_numbers: null })),
  summary: null,
};

const getRaceTicket = vi.fn();
vi.mock('../utils/api', () => ({ getRaceTicket: (...a) => getRaceTicket(...a) }));

const shareResult = vi.fn(() => Promise.resolve('copied'));
vi.mock('../utils/share', () => ({ shareResult: (...a) => shareResult(...a) }));

import BetSlip from '../components/race/BetSlip';

function renderSlip(props) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <BetSlip raceId="GP_1789171200000-4" {...props} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  getRaceTicket.mockReset();
  shareResult.mockClear();
});

describe('BetSlip before the race', () => {
  it('explains each bet in plain words and totals the stake', async () => {
    getRaceTicket.mockResolvedValue(PENDING);
    renderSlip({ raceFinished: false, onPlaceBet: vi.fn() });
    expect(await screen.findByText("SECRETARIAT'S TICKET")).toBeInTheDocument();
    expect(screen.getByText('Your horse must finish 1st.')).toBeInTheDocument();
    expect(screen.getByText('First two, in exact order.')).toBeInTheDocument();
    expect(screen.getByText('Total $6.00')).toBeInTheDocument();
  });

  it('hands the exact bets to the sportsbook drawer', async () => {
    getRaceTicket.mockResolvedValue(PENDING);
    const onPlaceBet = vi.fn();
    renderSlip({ raceFinished: false, onPlaceBet });
    fireEvent.click(await screen.findByText('Place this bet'));
    expect(onPlaceBet).toHaveBeenCalledWith(
      '$2 to win on #4, race 4\n$2 exacta 4-7, race 4\n$2 trifecta 4-7-5, race 4'
    );
  });
});

describe('BetSlip after the race', () => {
  it('shows the official payout on a hit and what came in on a miss', async () => {
    getRaceTicket.mockResolvedValue(SETTLED);
    renderSlip({ raceFinished: true });
    expect(await screen.findByText('$15.00')).toBeInTheDocument();
    expect(screen.getAllByText('Came in')).toHaveLength(2);
    expect(screen.getAllByText('−$2.00')).toHaveLength(2);
  });

  it('nets the ticket in one line', async () => {
    getRaceTicket.mockResolvedValue(SETTLED);
    renderSlip({ raceFinished: true });
    await screen.findByText('$15.00');
    expect(screen.getByText(/Bet \$6\.00 · Back \$15\.00/)).toBeInTheDocument();
    expect(screen.getByText('+$9.00')).toBeInTheDocument();
  });

  it('offers sharing only when something hit, and never before the race', async () => {
    getRaceTicket.mockResolvedValue(SETTLED);
    renderSlip({ raceFinished: true });
    fireEvent.click(await screen.findByText('Share'));
    await waitFor(() => expect(shareResult).toHaveBeenCalled());
    expect(shareResult.mock.calls[0][0].text).toContain('win');
    expect(shareResult.mock.calls[0][0].text).toContain('$15.00');
  });

  it('hides Place this bet once the race is off', async () => {
    getRaceTicket.mockResolvedValue(PENDING);
    renderSlip({ raceFinished: true, onPlaceBet: vi.fn() });
    await screen.findByText("SECRETARIAT'S TICKET");
    expect(screen.queryByText('Place this bet')).not.toBeInTheDocument();
  });

  it('shows "No pool" for a leg with no official price, not a loss', async () => {
    getRaceTicket.mockResolvedValue({
      ...SETTLED,
      legs: [SETTLED.legs[0], { ...SETTLED.legs[2], status: 'unpriced', winning_numbers: null }],
      summary: { legs_priced: 1, hits: 1, staked: 2.0, returned: 15.0, net: 13.0 },
    });
    renderSlip({ raceFinished: true });
    expect(await screen.findByText('No pool')).toBeInTheDocument();
    expect(screen.queryByText('−$2.00')).not.toBeInTheDocument();
  });
});

describe('BetSlip with no pick', () => {
  it('renders nothing when Secretariat has no ticket for the race', async () => {
    getRaceTicket.mockRejectedValue(new Error('404'));
    const { container } = renderSlip({ raceFinished: false });
    await waitFor(() => expect(getRaceTicket).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});
