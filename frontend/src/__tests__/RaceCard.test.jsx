/**
 * RaceCard component tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RaceCard, RaceCardSkeleton, formatDistance } from '../components/races/RaceCard';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

// Pinned to 2026-04-04T08:00:00Z (= 09:00 UK BST).
// Races with off_dt after this moment are upcoming; before are past.
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-04-04T08:00:00Z'));
});
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

// off_dt for a 14:30 BST race = 13:30 UTC → future at 08:00 UTC
// off_dt for a 08:00 BST race =  07:00 UTC → past  at 08:00 UTC
const baseRace = {
  race_id: 'r123',
  time: '14:30',
  off_dt: '2026-04-04T14:30:00+01:00',
  course: 'Ascot',
  title: 'Queen Anne Stakes',
  distance: '1m',
  distance_f: '8.0',
  surface: 'Turf',
  going: 'Good',
  runners: [{}, {}, {}, {}, {}],
  prize: '£200,000',
  region: 'GB',
};

const pastRace = {
  ...baseRace,
  time: '08:00',
  off_dt: '2026-04-04T08:00:00+01:00', // 07:00 UTC → past at 08:00 UTC
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

  it('renders distance as decimal miles', () => {
    renderCard();
    // 1m (distanceF=8) → "1m" (pure mile, no remainder)
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

  it('shows Analyze CTA for upcoming race', () => {
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

  it('shows Finished badge and hides Analyze CTA for past race (off_dt)', () => {
    renderCard(pastRace);
    expect(screen.getByText('Finished')).toBeInTheDocument();
    expect(screen.queryByText(/Analyze/)).not.toBeInTheDocument();
  });

  it('navigates when clicking a past race', () => {
    renderCard(pastRace);
    fireEvent.click(screen.getByText(/08:00/));
    expect(mockNavigate).toHaveBeenCalledWith('/race/r123');
  });

  it('does NOT show Finished for a future race even if time string looks past', () => {
    // off_dt is in the future — should override time-string comparison
    renderCard({ ...baseRace, time: '07:00', off_dt: '2026-04-04T14:30:00+01:00' });
    expect(screen.queryByText('Finished')).not.toBeInTheDocument();
  });

  it('tomorrow races are never marked Finished', () => {
    render(
      <MemoryRouter>
        <RaceCard race={pastRace} isTomorrow={true} />
      </MemoryRouter>
    );
    expect(screen.queryByText('Finished')).not.toBeInTheDocument();
  });
});

describe('formatDistance', () => {
  it('shows decimal miles only for a pure 1m race', () => {
    expect(formatDistance('1m', '8.0')).toBe('1m');
  });

  it('shows whole miles / remainder furlongs for 1m1f', () => {
    expect(formatDistance('1m1f', '9.0')).toBe('1m / 1f');
  });

  it('shows whole miles / remainder furlongs for 1m3f', () => {
    expect(formatDistance('1m3f', '11.0')).toBe('1m / 3f');
  });

  it('shows whole miles only for pure 2m', () => {
    expect(formatDistance('2m', '16.0')).toBe('2m');
  });

  it('shows whole miles / remainder furlongs for 2m4f', () => {
    expect(formatDistance('2m4f', '20.0')).toBe('2m / 4f');
  });

  it('shows furlongs only for sprint distances under 1m', () => {
    expect(formatDistance('5f', '5.0')).toBe('5f');
    expect(formatDistance('6f', '6.0')).toBe('6f');
    expect(formatDistance('7f', '7.0')).toBe('7f');
  });

  it('returns empty string when no data', () => {
    expect(formatDistance(undefined, undefined)).toBe('');
    expect(formatDistance('', '')).toBe('');
  });

  it('derives format from distance_f alone when dist string missing', () => {
    expect(formatDistance(undefined, '9.0')).toBe('1m / 1f');
    expect(formatDistance(undefined, '8.0')).toBe('1m');
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
