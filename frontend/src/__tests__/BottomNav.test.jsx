/**
 * BottomNav component tests.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BottomNav from '../components/common/BottomNav';
import { useAppStore } from '../store';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderNav(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <BottomNav />
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockNavigate.mockClear();
  useAppStore.setState({ betSlip: [] });
});

describe('BottomNav', () => {
  it('renders all 5 nav items', () => {
    renderNav();
    expect(screen.getByText('Races')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('Advisor')).toBeInTheDocument();
    expect(screen.getByText('My Picks')).toBeInTheDocument();
    expect(screen.getByText('Profile')).toBeInTheDocument();
  });

  it('navigates to / when Races is clicked', () => {
    renderNav('/advisor');
    fireEvent.click(screen.getByText('Races'));
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('navigates to /search when Search is clicked', () => {
    renderNav();
    fireEvent.click(screen.getByText('Search'));
    expect(mockNavigate).toHaveBeenCalledWith('/search');
  });

  it('navigates to /advisor when Advisor is clicked', () => {
    renderNav();
    fireEvent.click(screen.getByText('Advisor'));
    expect(mockNavigate).toHaveBeenCalledWith('/advisor');
  });

  it('navigates to /betslip when My Picks is clicked', () => {
    renderNav();
    fireEvent.click(screen.getByText('My Picks'));
    expect(mockNavigate).toHaveBeenCalledWith('/betslip');
  });

  it('navigates to /profile when Profile is clicked', () => {
    renderNav();
    fireEvent.click(screen.getByText('Profile'));
    expect(mockNavigate).toHaveBeenCalledWith('/profile');
  });

  it('does not show badge when bet slip is empty', () => {
    renderNav();
    // No number badge should appear
    expect(screen.queryByText('1')).not.toBeInTheDocument();
  });

  it('shows bet count badge when slip has items', () => {
    useAppStore.setState({
      betSlip: [
        { horse_id: 'h1', bet_type: 'win', stake: 10 },
        { horse_id: 'h2', bet_type: 'win', stake: 10 },
      ],
    });
    renderNav();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('badge count updates when bets are added', () => {
    const { rerender } = renderNav();
    useAppStore.setState({
      betSlip: [{ horse_id: 'h1', bet_type: 'win', stake: 10 }],
    });
    rerender(
      <MemoryRouter initialEntries={['/']}>
        <BottomNav />
      </MemoryRouter>
    );
    expect(screen.getByText('1')).toBeInTheDocument();
  });
});
