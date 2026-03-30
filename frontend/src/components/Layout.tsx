import { useState } from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import OnlineStatus from './OnlineStatus';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [quickFindOpen, setQuickFindOpen] = useState(false);
  const [quickFindValue, setQuickFindValue] = useState('');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navLinks = [
    { to: '/', label: 'Dashboard' },
    { to: '/bid-periods', label: 'Bid Periods' },
    { to: '/history', label: 'History' },
    { to: '/glossary', label: 'Glossary' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:rounded-md focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-sm focus:text-white">
        Skip to content
      </a>
      <nav className="bg-white border-b border-gray-200" aria-label="Main navigation">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <div className="flex items-center gap-6">
              <Link to="/" className="text-lg font-semibold text-gray-900">
                BidPilot
              </Link>
              <div className="hidden sm:flex items-center gap-4">
                {navLinks.map(({ to, label }) => (
                  <Link key={to} to={to} className="text-sm text-gray-600 hover:text-gray-900">{label}</Link>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* Quick-find search icon */}
              <div className="relative">
                <button
                  onClick={() => { setQuickFindOpen(!quickFindOpen); setQuickFindValue(''); }}
                  className="p-1.5 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                  aria-label="Quick find sequence"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </button>
                {quickFindOpen && (
                  <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 z-50 w-64">
                    <input
                      type="number"
                      autoFocus
                      value={quickFindValue}
                      onChange={(e) => setQuickFindValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && quickFindValue.trim()) {
                          setQuickFindOpen(false);
                          navigate(`/bid-periods?seq=${quickFindValue.trim()}`);
                        }
                        if (e.key === 'Escape') setQuickFindOpen(false);
                      }}
                      placeholder="Sequence # (e.g. 1234)"
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                    <p className="text-xs text-gray-400 mt-1 px-1">Press Enter to search</p>
                  </div>
                )}
              </div>
              <OnlineStatus />
              {user && (
                <>
                  <Link to="/profile" className="hidden sm:inline text-sm text-gray-600 hover:text-gray-900">
                    {user.profile.display_name || user.email}
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="hidden sm:inline text-sm text-gray-500 hover:text-gray-700"
                  >
                    Sign out
                  </button>
                </>
              )}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="sm:hidden p-1.5 rounded-md text-gray-600 hover:bg-gray-100"
                aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={mobileMenuOpen}
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  {mobileMenuOpen ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  )}
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="sm:hidden border-t border-gray-100 bg-white px-4 py-3 space-y-2">
            {navLinks.map(({ to, label }) => (
              <Link key={to} to={to} onClick={() => setMobileMenuOpen(false)}
                className="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
                {label}
              </Link>
            ))}
            {user && (
              <div className="border-t border-gray-100 pt-2 mt-2 space-y-2">
                <Link to="/profile" onClick={() => setMobileMenuOpen(false)}
                  className="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
                  {user.profile.display_name || user.email}
                </Link>
                <button onClick={() => { handleLogout(); setMobileMenuOpen(false); }}
                  className="block w-full text-left rounded-md px-3 py-2 text-sm text-gray-500 hover:bg-gray-100">
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </nav>
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
