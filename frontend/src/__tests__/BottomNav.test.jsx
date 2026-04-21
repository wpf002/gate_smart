/**
 * BottomNav component tests.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BottomNav from '../components/common/BottomNav';

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
});

describe('BottomNav', () => {
  it('renders all 4 nav items', () => {
    renderNav();
    expect(screen.getByText('Races')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('Advisor')).toBeInTheDocument();
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

  it('navigates to /profile when Profile is clicked', () => {
    renderNav();
    fireEvent.click(screen.getByText('Profile'));
    expect(mockNavigate).toHaveBeenCalledWith('/profile');
  });

});
