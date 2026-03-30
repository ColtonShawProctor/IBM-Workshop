import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GlossaryTerm } from '../components/GlossaryTooltip';

describe('GlossaryTerm', () => {
  it('renders the term text', () => {
    render(<GlossaryTerm term="SEQ" />);
    expect(screen.getByText('SEQ')).toBeInTheDocument();
  });

  it('renders children when provided', () => {
    render(<GlossaryTerm term="TPAY">Custom Label</GlossaryTerm>);
    expect(screen.getByText('Custom Label')).toBeInTheDocument();
  });

  it('returns plain text for unknown terms', () => {
    render(<GlossaryTerm term="UNKNOWN_TERM" />);
    expect(screen.getByText('UNKNOWN_TERM')).toBeInTheDocument();
  });

  it('shows tooltip on hover', () => {
    render(<GlossaryTerm term="TPAY" />);
    const term = screen.getByText('TPAY');
    fireEvent.mouseEnter(term);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('hides tooltip on mouse leave', () => {
    render(<GlossaryTerm term="TPAY" />);
    const term = screen.getByText('TPAY');
    fireEvent.mouseEnter(term);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.mouseLeave(term);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('shows tooltip on focus for keyboard users', () => {
    render(<GlossaryTerm term="SEQ" />);
    const term = screen.getByText('SEQ');
    fireEvent.focus(term);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('hides tooltip on Escape key', () => {
    render(<GlossaryTerm term="SEQ" />);
    const term = screen.getByText('SEQ');
    fireEvent.focus(term);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.keyDown(term, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('has tabIndex for keyboard accessibility', () => {
    render(<GlossaryTerm term="TAFB" />);
    const term = screen.getByText('TAFB');
    expect(term).toHaveAttribute('tabindex', '0');
  });

  it('sets aria-describedby when tooltip is visible', () => {
    render(<GlossaryTerm term="SEQ" />);
    const term = screen.getByText('SEQ');
    expect(term).not.toHaveAttribute('aria-describedby');
    fireEvent.mouseEnter(term);
    expect(term).toHaveAttribute('aria-describedby', 'glossary-seq');
  });
});
