import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import OnlineStatus from '../components/OnlineStatus';

vi.mock('../lib/offline', () => ({
  isOnline: vi.fn(() => true),
  onStatusChange: vi.fn(() => () => {}),
  getQueueLength: vi.fn(() => 0),
}));

describe('OnlineStatus', () => {
  it('returns null when online with no queue', () => {
    const { container } = render(<OnlineStatus />);
    expect(container.firstChild).toBeNull();
  });

  it('shows offline when not online', async () => {
    const offline = await import('../lib/offline');
    vi.mocked(offline.isOnline).mockReturnValue(false);

    render(<OnlineStatus />);
    expect(screen.getByText('Offline')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');

    vi.mocked(offline.isOnline).mockReturnValue(true);
  });

  it('shows pending count when queue has items', async () => {
    const offline = await import('../lib/offline');
    vi.mocked(offline.isOnline).mockReturnValue(true);
    vi.mocked(offline.getQueueLength).mockReturnValue(3);

    render(<OnlineStatus />);
    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(screen.getByText('(3 pending)')).toBeInTheDocument();

    vi.mocked(offline.getQueueLength).mockReturnValue(0);
  });
});
