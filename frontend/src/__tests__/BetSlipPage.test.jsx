/**
 * BetSlipPage tests — empty state, bet item rendering, payout calculation,
 * stake editing, and remove.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BetSlipPage from '../pages/BetSlipPage';
import { useAppStore } from '../store';

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

vi.mock('../utils/api', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, simPlaceBet: vi.fn().mockResolvedValue({}) };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <BetSlipPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useAppStore.setState({ betSlip: [] });
});

describe('BetSlipPage — empty state', () => {
  it('shows empty state heading', () => {
    renderPage();
    expect(screen.getByText('No Bets Yet')).toBeInTheDocument();
  });

  it('shows helper text', () => {
    renderPage();
    expect(screen.getByText(/Analyze a race/)).toBeInTheDocument();
  });

  it('does not show Clear all button when empty', () => {
    renderPage();
    expect(screen.queryByText('Clear all')).not.toBeInTheDocument();
  });
});

describe('BetSlipPage — with bets', () => {
  beforeEach(() => {
    useAppStore.setState({
      betSlip: [
        { horse_id: 'h1', horse_name: 'Frankel', bet_type: 'win', odds: '5/2', stake: 10, race_id: 'r1' },
        { horse_id: 'h2', horse_name: 'Enable', bet_type: 'place', odds: '2/1', stake: 20, race_id: 'r1' },
      ],
    });
  });

  it('renders horse names', () => {
    renderPage();
    expect(screen.getByText('Frankel')).toBeInTheDocument();
    expect(screen.getByText('Enable')).toBeInTheDocument();
  });

  it('renders bet types', () => {
    renderPage();
    expect(screen.getByText(/WIN/)).toBeInTheDocument();
    expect(screen.getByText(/PLACE/)).toBeInTheDocument();
  });

  it('renders selection count in subtitle', () => {
    renderPage();
    expect(screen.getByText(/2 selections/)).toBeInTheDocument();
  });

  it('shows Clear all button', () => {
    renderPage();
    expect(screen.getByText('Clear all')).toBeInTheDocument();
  });

  it('clears all bets when Clear all is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('Clear all'));
    expect(useAppStore.getState().betSlip).toHaveLength(0);
  });

  it('removes individual bet when × is clicked', () => {
    renderPage();
    const removeButtons = screen.getAllByText('×');
    fireEvent.click(removeButtons[0]); // Remove first bet
    expect(useAppStore.getState().betSlip).toHaveLength(1);
  });

  it('calculates correct payout for 5/2 at £10 stake', () => {
    // 5/2 decimal = 3.5, payout = 10 * 3.5 = 35.00, profit = 25.00
    renderPage();
    expect(screen.getByText('£35.00')).toBeInTheDocument();
    expect(screen.getByText('+£25.00 profit')).toBeInTheDocument();
  });

  it('calculates correct payout for 2/1 at £20 stake', () => {
    // 2/1 decimal = 3.0, payout = 20 * 3.0 = 60.00, profit = 40.00
    renderPage();
    expect(screen.getByText('£60.00')).toBeInTheDocument();
    expect(screen.getByText('+£40.00 profit')).toBeInTheDocument();
  });

  it('shows correct total stake', () => {
    renderPage();
    // £10 + £20 = £30.00, appears in footer and Place button
    const thirtyElements = screen.getAllByText(/£30\.00/);
    expect(thirtyElements.length).toBeGreaterThan(0);
  });

  it('updates stake input when changed', () => {
    renderPage();
    const inputs = screen.getAllByDisplayValue('10');
    fireEvent.change(inputs[0], { target: { value: '50' } });
    expect(useAppStore.getState().betSlip[0].stake).toBe(50);
  });
});

describe('BetSlipPage — singular selection label', () => {
  it('shows "1 selection" not "1 selections"', () => {
    useAppStore.setState({
      betSlip: [{ horse_id: 'h1', horse_name: 'Frankel', bet_type: 'win', odds: '2/1', stake: 10 }],
    });
    renderPage();
    expect(screen.getByText('1 selection')).toBeInTheDocument();
  });
});

describe('BetSlipPage — unknown odds', () => {
  it('does not show payout when odds are "?"', () => {
    useAppStore.setState({
      betSlip: [{ horse_id: 'h1', horse_name: 'Mystery', bet_type: 'win', odds: '?', stake: 10 }],
    });
    renderPage();
    expect(screen.queryByText(/Returns/)).not.toBeInTheDocument();
  });
});
