/**
 * RaceCard component tests.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RaceCard, RaceCardSkeleton } from '../components/races/RaceCard';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

const baseRace = {
  race_id: 'r123',
  time: '14:30',
  course: 'Ascot',
  title: 'Queen Anne Stakes',
  distance: '1m',
  surface: 'Turf',
  going: 'Good',
  runners: [{}, {}, {}, {}, {}],
  prize: '£200,000',
};

function renderCard(race = baseRace) {
  return render(
    <MemoryRouter>
      <RaceCard race={race} />
    </MemoryRouter>
  );
}

describe('RaceCard', () => {
  it('renders time and course', () => {
    renderCard();
    expect(screen.getByText(/14:30/)).toBeInTheDocument();
    expect(screen.getByText(/Ascot/)).toBeInTheDocument();
  });

  it('renders race title', () => {
    renderCard();
    expect(screen.getByText('Queen Anne Stakes')).toBeInTheDocument();
  });

  it('renders distance', () => {
    renderCard();
    expect(screen.getByText(/1m/)).toBeInTheDocument();
  });

  it('renders surface', () => {
    renderCard();
    expect(screen.getByText(/Turf/)).toBeInTheDocument();
  });

  it('renders going badge', () => {
    renderCard();
    expect(screen.getByText('Good')).toBeInTheDocument();
  });

  it('renders runner count', () => {
    renderCard();
    expect(screen.getByText(/5 runners/)).toBeInTheDocument();
  });

  it('renders prize money', () => {
    renderCard();
    expect(screen.getByText(/£200,000/)).toBeInTheDocument();
  });

  it('shows Analyze CTA', () => {
    renderCard();
    expect(screen.getByText(/Analyze/)).toBeInTheDocument();
  });

  it('navigates to race detail on click', () => {
    renderCard();
    fireEvent.click(screen.getByText(/14:30/));
    expect(mockNavigate).toHaveBeenCalledWith('/race/r123');
  });

  it('handles missing optional fields gracefully', () => {
    renderCard({ race_id: 'r1', time: '15:00', course: 'Newmarket' });
    expect(screen.getByText(/15:00/)).toBeInTheDocument();
    expect(screen.queryByText(/runners/)).not.toBeInTheDocument();
  });

  it('uses race_name as fallback for title', () => {
    renderCard({ ...baseRace, title: undefined, race_name: 'Fallback Race' });
    expect(screen.getByText('Fallback Race')).toBeInTheDocument();
  });
});

describe('RaceCardSkeleton', () => {
  it('renders without errors', () => {
    const { container } = render(
      <MemoryRouter>
        <RaceCardSkeleton />
      </MemoryRouter>
    );
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders skeleton elements', () => {
    const { container } = render(
      <MemoryRouter>
        <RaceCardSkeleton />
      </MemoryRouter>
    );
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
