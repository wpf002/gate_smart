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
  });
});

describe('ProfilePage', () => {
  it('renders PROFILE heading', () => {
    renderPage();
    expect(screen.getByText('PROFILE')).toBeInTheDocument();
  });

  it('updates name in store when name input changes', () => {
    renderPage();
    const nameInput = screen.getByPlaceholderText(/Enter your name/);
    fireEvent.change(nameInput, { target: { value: 'Will' } });
    expect(useAppStore.getState().userProfile.name).toBe('Will');
  });

  it('renders risk tolerance options', () => {
    renderPage();
    expect(screen.getByText('low')).toBeInTheDocument();
    // 'medium' appears in both the segment button and the profile summary
    expect(screen.getAllByText('medium').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('high')).toBeInTheDocument();
  });

  it('updates risk tolerance when a segment is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('high'));
    expect(useAppStore.getState().userProfile.riskTolerance).toBe('high');
  });

  it('updates risk tolerance to low when low is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('low'));
    expect(useAppStore.getState().userProfile.riskTolerance).toBe('low');
  });

  it('renders experience level options', () => {
    renderPage();
    // 'beginner' appears in both the segment button and the profile summary.
    // The page only offers two levels now (beginner and advanced); the prior
    // 'intermediate' option was retired.
    expect(screen.getAllByText('beginner').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('advanced')).toBeInTheDocument();
  });

  it('updates experience level when a segment is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('advanced'));
    expect(useAppStore.getState().userProfile.experienceLevel).toBe('advanced');
  });

  it('shows profile summary with current values', () => {
    renderPage();
    const mediumEls = screen.getAllByText(/medium/i);
    expect(mediumEls.length).toBeGreaterThan(0);
  });

  it('shows responsible gambling message', () => {
    renderPage();
    expect(screen.getByText(/ncpgambling/)).toBeInTheDocument();
  });
});
