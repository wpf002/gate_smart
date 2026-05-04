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

  it('renders experience level options', () => {
    renderPage();
    expect(screen.getAllByText('beginner').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('advanced')).toBeInTheDocument();
  });

  it('updates experience level when a segment is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('advanced'));
    expect(useAppStore.getState().userProfile.experienceLevel).toBe('advanced');
  });

  it('shows responsible gambling message', () => {
    renderPage();
    expect(screen.getByText(/ncpgambling/)).toBeInTheDocument();
  });
});
