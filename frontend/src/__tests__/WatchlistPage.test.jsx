/**
 * WatchlistPage — "Racing Soon" filtering.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from '../store';

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

const MATCHES = [
  { race_id: 'r1', course: 'Saratoga',     race_name: 'Race 2', day: 'today',    entity_type: 'jockey',  entity_label: 'Kendrick Carmouche', horse_name: 'All About Soul' },
  { race_id: 'r2', course: 'Belterra Park', race_name: 'Race 4', day: 'today',    entity_type: 'trainer', entity_label: 'Kenneth McPeek',     horse_name: 'No More Cents' },
  { race_id: 'r3', course: 'Ellis Park',    race_name: 'Race 2', day: 'tomorrow', entity_type: 'jockey',  entity_label: 'Brian Hernandez, Jr.', horse_name: 'Bagg O Time' },
];

vi.mock('../utils/api', () => ({
  getWatchlist: vi.fn(() => Promise.resolve({
    items: [
      { id: 1, entity_type: 'jockey',  entity_key: 'kendrick carmouche', entity_label: 'Kendrick Carmouche' },
      { id: 2, entity_type: 'trainer', entity_key: 'kenneth mcpeek',     entity_label: 'Kenneth McPeek' },
    ],
    total: 2,
  })),
  getWatchlistToday: vi.fn(() => Promise.resolve({ matches: MATCHES, total: MATCHES.length })),
  removeFromWatchlist: vi.fn(() => Promise.resolve({ deleted: 1 })),
}));

import WatchlistPage from '../pages/WatchlistPage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><WatchlistPage /></MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useAppStore.setState({ authToken: 'test-token', authUser: { id: 1 } });
});

describe('WatchlistPage racing-soon filters', () => {
  it('lists every match before filtering', async () => {
    renderPage();
    expect(await screen.findByText(/All About Soul/)).toBeInTheDocument();
    expect(screen.getByText(/No More Cents/)).toBeInTheDocument();
    expect(screen.getByText(/Bagg O Time/)).toBeInTheDocument();
  });

  it('filters to a single day', async () => {
    renderPage();
    await screen.findByText(/All About Soul/);
    fireEvent.click(screen.getByRole('button', { name: /^Tomorrow/ }));
    // Only the tomorrow entry survives.
    expect(screen.getByText(/Bagg O Time/)).toBeInTheDocument();
    expect(screen.queryByText(/All About Soul/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No More Cents/)).not.toBeInTheDocument();
  });

  it('filters by entity type', async () => {
    renderPage();
    await screen.findByText(/All About Soul/);
    fireEvent.click(screen.getByRole('button', { name: /^Trainers/ }));
    expect(screen.getByText(/No More Cents/)).toBeInTheDocument();
    expect(screen.queryByText(/All About Soul/)).not.toBeInTheDocument();
  });

  it('filters by track', async () => {
    renderPage();
    await screen.findByText(/All About Soul/);
    fireEvent.change(screen.getByLabelText('Filter by track'), { target: { value: 'Ellis Park' } });
    expect(screen.getByText(/Bagg O Time/)).toBeInTheDocument();
    expect(screen.queryByText(/All About Soul/)).not.toBeInTheDocument();
  });

  it('clears filters back to the full list', async () => {
    renderPage();
    await screen.findByText(/All About Soul/);
    fireEvent.click(screen.getByRole('button', { name: /^Tomorrow/ }));
    expect(screen.queryByText(/All About Soul/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Clear$/ }));
    expect(screen.getByText(/All About Soul/)).toBeInTheDocument();
    expect(screen.getByText(/Bagg O Time/)).toBeInTheDocument();
  });

  it('shows a message when filters exclude everything', async () => {
    renderPage();
    await screen.findByText(/All About Soul/);
    // Tomorrow + Trainers = no rows (the only tomorrow row is a jockey).
    fireEvent.click(screen.getByRole('button', { name: /^Tomorrow/ }));
    fireEvent.click(screen.getByRole('button', { name: /^Trainers/ }));
    expect(screen.getByText(/No entries match these filters/)).toBeInTheDocument();
  });
});
