import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { autoSetup, createBidPeriod, listBidPeriods } from '../lib/api';
import type { BidPeriod } from '../types/api';

export default function HomePage() {
  const { user, setAuth } = useAuth();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [recentPeriods, setRecentPeriods] = useState<BidPeriod[]>([]);
  const [initializing, setInitializing] = useState(!user);

  // Auto-setup: create/login the default user on first visit
  useEffect(() => {
    if (user) {
      setInitializing(false);
      return;
    }
    autoSetup()
      .then((res) => {
        setAuth(res.access_token, res.refresh_token, res.user);
      })
      .catch(() => setError('Could not connect to the server. Make sure the backend is running.'))
      .finally(() => setInitializing(false));
  }, [user, setAuth]);

  // Load recent bid periods
  useEffect(() => {
    if (!user) return;
    listBidPeriods()
      .then((res) => setRecentPeriods(res.data || []))
      .catch(() => {});
  }, [user]);

  const profile = user?.profile;
  const prefs = user?.default_preferences;
  const seniorityPct = profile?.seniority_number && profile?.total_base_fas
    ? ((profile.seniority_number / profile.total_base_fas) * 100).toFixed(1)
    : null;

  const loveCities = prefs?.preferred_layover_cities?.join(', ') || 'SFO, DEN, BOS, SAN';
  const creditMin = prefs?.tpay_min_minutes ? Math.round(prefs.tpay_min_minutes / 60) : 85;
  const creditMax = prefs?.tpay_max_minutes ? Math.round(prefs.tpay_max_minutes / 60) : 90;
  const reportAfter = prefs?.report_earliest_minutes
    ? `${String(Math.floor(prefs.report_earliest_minutes / 60)).padStart(2, '0')}:${String(prefs.report_earliest_minutes % 60).padStart(2, '0')}`
    : '09:00';
  const releaseBy = prefs?.release_latest_minutes
    ? `${String(Math.floor(prefs.release_latest_minutes / 60)).padStart(2, '0')}:${String(prefs.release_latest_minutes % 60).padStart(2, '0')}`
    : '19:00';

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const bp = await createBidPeriod(formData);
      // Go directly to the guided bid flow
      navigate(`/bid-periods/${bp.id}/guided`);
    } catch (err: any) {
      setError(err?.response?.data?.message || err?.message || 'Upload failed. Check the file and try again.');
      setUploading(false);
    }
  }

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-3 text-sm text-gray-500">Setting up your profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 pt-16 pb-12">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900">
            {recentPeriods.length > 0 ? `Welcome back, ${profile?.display_name?.split(' ')[0] || 'Katya'}!` : `Welcome, ${profile?.display_name?.split(' ')[0] || 'Katya'}!`}
          </h1>
          {recentPeriods.length > 0 && (
            <p className="mt-2 text-gray-500">Your preferences are loaded from last month.</p>
          )}
        </div>

        {/* Profile summary card */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Base</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">{profile?.base_city || 'ORD'}</p>
              {profile?.commute_from && (
                <p className="text-xs text-gray-400">{profile.commute_from} commuter</p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Seniority</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">
                #{profile?.seniority_number || 1170}
              </p>
              {seniorityPct && (
                <p className="text-xs text-gray-400">of {profile?.total_base_fas || 2323}</p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Credit</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">{creditMin}-{creditMax}h</p>
              <p className="text-xs text-gray-400">target range</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-sm text-gray-500 text-center">
              3-4 day trips &middot; {loveCities} &middot; Report after {reportAfter} &middot; Release by {releaseBy}
            </p>
          </div>
        </div>

        {/* Upload area */}
        <div className="text-center mb-6">
          <p className="text-gray-600 mb-4">
            {recentPeriods.length > 0
              ? "Upload this month's pairing sheet to see your trips."
              : "Upload your pairing sheet to get started."}
          </p>

          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            className="hidden"
          />

          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-4 text-lg font-semibold text-white shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {uploading ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Parsing pairing sheet...
              </>
            ) : (
              <>
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Upload Pairing Sheet
              </>
            )}
          </button>

          {error && (
            <p className="mt-3 text-sm text-red-600">{error}</p>
          )}
        </div>

        {/* Settings link — small and secondary */}
        <div className="text-center mb-10">
          <button
            onClick={() => navigate('/settings')}
            className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
          >
            Change settings
          </button>
        </div>

        {/* Recent bid periods */}
        {recentPeriods.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Recent Months</h2>
            <div className="space-y-2">
              {recentPeriods.slice(0, 5).map((bp) => (
                <button
                  key={bp.id}
                  onClick={() => navigate(`/bid-periods/${bp.id}/guided`)}
                  className="w-full text-left rounded-lg border border-gray-200 bg-white p-4 hover:border-blue-300 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{bp.name}</p>
                      <p className="text-sm text-gray-500">{bp.effective_start} to {bp.effective_end}</p>
                    </div>
                    <div className="text-right">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        bp.parse_status === 'completed' ? 'bg-green-100 text-green-700' :
                        bp.parse_status === 'failed' ? 'bg-red-100 text-red-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {bp.parse_status === 'completed' ? `${bp.total_sequences} trips` : bp.parse_status}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
