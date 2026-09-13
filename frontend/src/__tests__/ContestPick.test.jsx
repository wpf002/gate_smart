/**
 * ContestPick — "Beat Secretariat" on a race page.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from '../store';

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => navigate };
});

const api = {
  getMyContestPicks: vi.fn(() => Promise.resolve({ date: '2026-09-13', picks: [] })),
  makeContestPick: vi.fn(() => Promise.resolve({})),
};
vi.mock('../utils/api', () => ({
  getMyContestPicks: (...a) => api.getMyContestPicks(...a),
  makeContestPick: (...a) => api.makeContestPick(...a),
}));

const shareResult = vi.fn(() => Promise.resolve('copied'));
vi.mock('../utils/share', () => ({ shareResult: (...a) => shareResult(...a) }));

import ContestPick from '../components/race/ContestPick';

const RUNNERS = [
  { horse_name: 'Alinao Forever', number: '4', scratched: false },
  { horse_name: 'Magic Heart', number: '7', scratched: false },
  { horse_name: 'Scratched Sam', number: '9', scratched: true },
];

function renderPick(props = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ContestPick raceId="GP_1-4" raceDate="2026-09-13" runners={RUNNERS} secretariatPick="Magic Heart" {...props} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  navigate.mockClear();
  shareResult.mockClear();
  Object.values(api).forEach((f) => f.mockClear());
  api.getMyContestPicks.mockImplementation(() => Promise.resolve({ date: '2026-09-13', picks: [] }));
  useAppStore.setState({ authToken: 'token' });
});

describe('ContestPick', () => {
  it('sends signed-out visitors to sign in', () => {
    useAppStore.setState({ authToken: null });
    renderPick();
    fireEvent.click(screen.getByText('Sign in to play'));
    expect(navigate).toHaveBeenCalledWith('/login');
  });

  it('never offers a scratched horse', async () => {
    renderPick();
    await waitFor(() => expect(api.getMyContestPicks).toHaveBeenCalled());
    expect(screen.queryByRole('option', { name: /Scratched Sam/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#4 Alinao Forever' })).toBeInTheDocument();
  });

  it('locks in a pick with the horse and its program number', async () => {
    renderPick();
    await waitFor(() => expect(api.getMyContestPicks).toHaveBeenCalled());
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Alinao Forever' } });
    fireEvent.click(screen.getByText('Lock it in'));
    await waitFor(() => expect(api.makeContestPick).toHaveBeenCalledWith('GP_1-4', 'Alinao Forever', '4'));
  });

  it('shows the server reason when a pick is refused', async () => {
    api.makeContestPick.mockRejectedValueOnce({ response: { data: { detail: 'Picks are locked — this race is already off' } } });
    renderPick();
    await waitFor(() => expect(api.getMyContestPicks).toHaveBeenCalled());
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Magic Heart' } });
    fireEvent.click(screen.getByText('Lock it in'));
    expect(await screen.findByText('Picks are locked — this race is already off')).toBeInTheDocument();
  });

  it('celebrates beating Secretariat and offers to share it', async () => {
    api.getMyContestPicks.mockImplementation(() => Promise.resolve({ date: '2026-09-13', picks: [{
      race_id: 'GP_1-4', horse_name: 'Alinao Forever', settled: true, winner_name: 'Alinao Forever',
      correct: true, secretariat_correct: false, beat_secretariat: true, points: 15,
    }] }));
    renderPick({ raceFinished: true });
    expect(await screen.findByText('You beat Secretariat — Alinao Forever won.')).toBeInTheDocument();
    expect(screen.getByText('+15')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Share'));
    await waitFor(() => expect(shareResult).toHaveBeenCalled());
  });

  it('reports a miss plainly, with no share button', async () => {
    api.getMyContestPicks.mockImplementation(() => Promise.resolve({ date: '2026-09-13', picks: [{
      race_id: 'GP_1-4', horse_name: 'Magic Heart', settled: true, winner_name: 'Alinao Forever',
      correct: false, secretariat_correct: false, beat_secretariat: false, points: 0,
    }] }));
    renderPick({ raceFinished: true });
    expect(await screen.findByText('You had Magic Heart. Alinao Forever won.')).toBeInTheDocument();
    expect(screen.queryByText('Share')).not.toBeInTheDocument();
  });

  it('renders nothing on a finished race the player never picked', async () => {
    const { container } = renderPick({ raceFinished: true });
    await waitFor(() => expect(api.getMyContestPicks).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});
