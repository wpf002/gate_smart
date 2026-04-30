/**
 * HorseRow component tests.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HorseRow, HorseRowSkeleton } from '../components/races/HorseRow';
import { useAppStore } from '../store';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

const baseHorse = {
  horse_id: 'h1',
  horse_name: 'Frankel',
  jockey: 'T. Queally',
  trainer: 'H. Cecil',
  odds: '2/1',
};

function renderRow(horse = baseHorse, analysis = null, raceId = 'r1') {
  return render(
    <MemoryRouter>
      <HorseRow horse={horse} analysis={analysis} raceId={raceId} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockNavigate.mockClear();
  useAppStore.setState({ betSlip: [] });
});

describe('HorseRow', () => {
  it('renders horse name', () => {
    renderRow();
    expect(screen.getByText('Frankel')).toBeInTheDocument();
  });

  it('renders jockey and trainer', () => {
    renderRow();
    expect(screen.getByText(/T. Queally/)).toBeInTheDocument();
    expect(screen.getByText(/H. Cecil/)).toBeInTheDocument();
  });

  it('renders odds chip', () => {
    renderRow();
    expect(screen.getByText('2/1')).toBeInTheDocument();
  });

  it('shows stall number when no analysis score', () => {
    renderRow({ ...baseHorse, cloth_number: '3' });
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('navigates to horse detail via profile button in expanded row', () => {
    const analysis = {
      runners: [{ horse_id: 'h1', contender_score: 70, summary: 'Strong form.' }],
    };
    renderRow(baseHorse, analysis);
    // Click the row to expand it
    fireEvent.click(screen.getByText('Frankel'));
    // Then click the profile link inside the expanded section
    fireEvent.click(screen.getByText('View Horse Profile →'));
    expect(mockNavigate).toHaveBeenCalledWith('/horse/h1');
  });

  it('shows score ring when analysis contains horse', () => {
    const analysis = {
      runners: [{ horse_id: 'h1', horse_name: 'Frankel', contender_score: 80, summary: null }],
    };
    renderRow(baseHorse, analysis);
    expect(screen.getByText('80')).toBeInTheDocument();
  });

  it('score ring uses score-high class for score >= 70', () => {
    const analysis = {
      runners: [{ horse_id: 'h1', contender_score: 75, summary: null }],
    };
    const { container } = renderRow(baseHorse, analysis);
    expect(container.querySelector('.score-high')).toBeInTheDocument();
  });

  it('score ring uses score-med class for score 40–69', () => {
    const analysis = {
      runners: [{ horse_id: 'h1', contender_score: 55, summary: null }],
    };
    const { container } = renderRow(baseHorse, analysis);
    expect(container.querySelector('.score-med')).toBeInTheDocument();
  });

  it('score ring uses score-low class for score < 40', () => {
    const analysis = {
      runners: [{ horse_id: 'h1', contender_score: 20, summary: null }],
    };
    const { container } = renderRow(baseHorse, analysis);
    expect(container.querySelector('.score-low')).toBeInTheDocument();
  });

  it('shows recommended_bet badge when present', () => {
    const analysis = {
      runners: [{ horse_id: 'h1', recommended_bet: 'win', contender_score: 80, summary: null }],
    };
    renderRow(baseHorse, analysis);
    expect(screen.getByText('Win')).toBeInTheDocument();
  });


  it('shows analysis summary when present after expanding row', () => {
    const analysis = {
      runners: [{
        horse_id: 'h1',
        contender_score: 70,
        summary: 'Consistent front-runner at this trip.',
      }],
    };
    renderRow(baseHorse, analysis);
    // Summary is in the collapsed section — click to expand
    fireEvent.click(screen.getByText('Frankel'));
    expect(screen.getByText('Consistent front-runner at this trip.')).toBeInTheDocument();
  });
});

describe('HorseRowSkeleton', () => {
  it('renders without errors', () => {
    const { container } = render(<HorseRowSkeleton />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('contains skeleton elements', () => {
    const { container } = render(<HorseRowSkeleton />);
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
