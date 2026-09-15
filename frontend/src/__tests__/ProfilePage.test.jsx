/**
 * ProfilePage tests — form field interactions and store updates.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProfilePage from '../pages/ProfilePage';
import { useAppStore } from '../store';

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

// Real /api/contest/me shape.
const ME = {
  display_name: 'Chalk Eater', pick_day_streak: 4, beat_secretariat_streak: 2,
  best_correct_streak: 3, total_picks: 9, settled: 8, wins: 4, beat_secretariat: 2, points: 50,
};
const getContestProgress = vi.fn(() => Promise.resolve(ME));
vi.mock('../utils/api', () => ({
  getContestProgress: (...a) => getContestProgress(...a),
  authUpdateProfile: vi.fn(() => Promise.resolve({})),
  authLogout: vi.fn(() => Promise.resolve({})),
  getRacesToday: vi.fn(() => Promise.resolve({ racecards: [] })),
  getRacesByDate: vi.fn(() => Promise.resolve({ racecards: [] })),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useAppStore.setState({
    userProfile: {
      bankroll: 500,
      riskTolerance: 'medium',
      experienceLevel: 'beginner',
      name: '',
    },
    betSlip: [],
    advisorMessages: [],
    authToken: null,
    authUser: null,
  });
  getContestProgress.mockClear();
});

describe('ProfilePage', () => {
  it('renders PROFILE heading', () => {
    renderPage();
    expect(screen.getByText('PROFILE')).toBeInTheDocument();
  });

  it('shows both experience levels with what each one means', () => {
    renderPage();
    expect(screen.getByText('Beginner')).toBeInTheDocument();
    expect(screen.getByText('Advanced')).toBeInTheDocument();
    expect(screen.getByText(/Plain English/)).toBeInTheDocument();
    expect(screen.getByText(/Full technical view/)).toBeInTheDocument();
  });

  it('updates experience level when an option is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('Advanced'));
    expect(useAppStore.getState().userProfile.experienceLevel).toBe('advanced');
  });

  it('shows the player name, progress and Sign Out when signed in', async () => {
    useAppStore.setState({ authToken: 'token', authUser: { email: 'player@example.com' } });
    renderPage();
    expect(await screen.findByText('Chalk Eater')).toBeInTheDocument();
    expect(screen.getByText('4/8')).toBeInTheDocument();
    expect(screen.getByText('Beat Secretariat')).toBeInTheDocument();
    expect(screen.getByText('Sign Out')).toBeInTheDocument();
  });

  it('shows no zeros and no stand-in name before the first pick', async () => {
    useAppStore.setState({ authToken: 'token', authUser: { email: 'player@example.com' } });
    getContestProgress.mockImplementationOnce(() => Promise.resolve({
      display_name: 'Handicapper 3', pick_day_streak: 0, beat_secretariat_streak: 0,
      best_correct_streak: 0, total_picks: 0, settled: 0, wins: 0, beat_secretariat: 0, points: 0,
    }));
    renderPage();
    expect(await screen.findByText('NO PICKS YET')).toBeInTheDocument();
    expect(screen.getByText('Set Your Name')).toBeInTheDocument();
    expect(screen.getByText('player@example.com')).toBeInTheDocument();
    expect(screen.queryByText('Handicapper 3')).not.toBeInTheDocument();
    expect(screen.queryByText('0/0')).not.toBeInTheDocument();
  });

  it('asks guests to sign in and never fetches progress', () => {
    renderPage();
    expect(screen.getByText('Guest')).toBeInTheDocument();
    expect(screen.getByText('Sign In')).toBeInTheDocument();
    expect(getContestProgress).not.toHaveBeenCalled();
  });

  it('shows responsible gambling message', () => {
    renderPage();
    expect(screen.getByText(/ncpgambling/)).toBeInTheDocument();
  });
});
