import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { listBidPeriods } from '../lib/api';
import type { BidPeriod } from '../types/api';

export default function DashboardPage() {
  const { user } = useAuth();
  const [bidPeriods, setBidPeriods] = useState<BidPeriod[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listBidPeriods()
      .then((res) => setBidPeriods(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const profile = user?.profile;
  const seniorityPct = profile?.seniority_number && profile?.total_base_fas
    ? ((profile.seniority_number / profile.total_base_fas) * 100).toFixed(1)
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          Welcome back, {profile?.display_name || user?.email}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Base City</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900">{profile?.base_city || '—'}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Seniority</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900">
            #{profile?.seniority_number || '—'}
            {seniorityPct && <span className="text-sm text-gray-400 ml-1">({seniorityPct}%)</span>}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Position Range</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900">
            {profile?.position_min}–{profile?.position_max}
          </p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">Bid Periods</h2>
          <Link
            to="/bid-periods"
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            Manage Bid Periods
          </Link>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : bidPeriods.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
            <p className="text-sm text-gray-500">No bid periods yet.</p>
            <Link to="/bid-periods" className="text-sm text-blue-600 hover:underline mt-1 inline-block">
              Upload your first bid sheet
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {bidPeriods.map((bp) => (
              <Link
                key={bp.id}
                to={`/bid-periods/${bp.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-4 hover:border-blue-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{bp.name}</p>
                    <p className="text-sm text-gray-500">
                      {bp.effective_start} to {bp.effective_end}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      bp.parse_status === 'completed' ? 'bg-green-100 text-green-700' :
                      bp.parse_status === 'failed' ? 'bg-red-100 text-red-700' :
                      bp.parse_status === 'processing' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {bp.parse_status}
                    </span>
                    {bp.total_sequences > 0 && (
                      <p className="text-sm text-gray-500 mt-1">{bp.total_sequences} sequences</p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
