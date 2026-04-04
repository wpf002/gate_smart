/**
 * PageHeader component tests.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderHeader(props) {
  return render(
    <MemoryRouter>
      <PageHeader {...props} />
    </MemoryRouter>
  );
}

describe('PageHeader', () => {
  it('renders the title', () => {
    renderHeader({ title: 'GATESMART' });
    expect(screen.getByText('GATESMART')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    renderHeader({ title: 'RACES', subtitle: 'Today\'s cards' });
    expect(screen.getByText("Today's cards")).toBeInTheDocument();
  });

  it('does not render subtitle when omitted', () => {
    renderHeader({ title: 'RACES' });
    // No subtitle element
    expect(screen.queryByText(/today/i)).not.toBeInTheDocument();
  });

  it('does not render back button by default', () => {
    renderHeader({ title: 'HOME' });
    expect(screen.queryByText('←')).not.toBeInTheDocument();
  });

  it('renders back button when showBack=true', () => {
    renderHeader({ title: 'RACE', showBack: true });
    expect(screen.getByText('←')).toBeInTheDocument();
  });

  it('calls navigate(-1) when back button is clicked', () => {
    renderHeader({ title: 'RACE', showBack: true });
    fireEvent.click(screen.getByText('←'));
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  it('renders right slot content', () => {
    renderHeader({ title: 'RACE', right: <button>Refresh</button> });
    expect(screen.getByText('Refresh')).toBeInTheDocument();
  });
});
