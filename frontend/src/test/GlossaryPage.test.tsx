import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GlossaryPage from '../pages/GlossaryPage';

function renderPage() {
  return render(
    <MemoryRouter>
      <GlossaryPage />
    </MemoryRouter>
  );
}

describe('GlossaryPage', () => {
  it('renders glossary heading', () => {
    renderPage();
    expect(screen.getByText('Glossary')).toBeInTheDocument();
  });

  it('renders glossary terms', () => {
    renderPage();
    expect(screen.getByText('Sequence')).toBeInTheDocument();
    expect(screen.getByText('Total Pay')).toBeInTheDocument();
    expect(screen.getByText('Deadhead')).toBeInTheDocument();
  });

  it('filters terms based on search', () => {
    renderPage();
    const searchInput = screen.getByPlaceholderText('Search terms...');
    fireEvent.change(searchInput, { target: { value: 'deadhead' } });
    expect(screen.getByText('Deadhead')).toBeInTheDocument();
    // "Sequence" should be filtered out
    expect(screen.queryByText('Sequence')).not.toBeInTheDocument();
  });

  it('shows no results message for unmatched search', () => {
    renderPage();
    const searchInput = screen.getByPlaceholderText('Search terms...');
    fireEvent.change(searchInput, { target: { value: 'xyznonexistent' } });
    expect(screen.getByText('No matching terms.')).toBeInTheDocument();
  });
});
