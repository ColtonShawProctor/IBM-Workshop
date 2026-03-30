import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listBidPeriods } from '../lib/api';
import type { BidPeriod } from '../types/api';

export default function BidHistoryPage() {
  const [bidPeriods, setBidPeriods] = useState<BidPeriod[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listBidPeriods()
      .then((res) => setBidPeriods(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bid History</h1>
        <p className="text-sm text-gray-500 mt-1">All past and current bid periods</p>
      </div>

      {bidPeriods.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
          <p className="text-sm text-gray-500">No bid periods yet.</p>
          <Link to="/bid-periods" className="text-sm text-blue-600 hover:underline mt-1 inline-block">
            Upload your first bid sheet
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {bidPeriods.map((bp) => (
            <div key={bp.id} className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <div>
                  <Link to={`/bid-periods/${bp.id}`} className="font-medium text-gray-900 hover:text-blue-600">
                    {bp.name}
                  </Link>
                  <p className="text-sm text-gray-500 mt-0.5">
                    {bp.effective_start} to {bp.effective_end}
                    {bp.base_city && <span className="ml-2">({bp.base_city})</span>}
                  </p>
                  {bp.categories.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {bp.categories.map((cat) => (
                        <span key={cat} className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">{cat}</span>
                      ))}
                    </div>
                  )}
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
                  <p className="text-sm text-gray-500 mt-1">{bp.total_sequences} sequences</p>
                  <p className="text-xs text-gray-400">{bp.total_dates} days</p>
                </div>
              </div>
              <div className="flex gap-3 mt-3 pt-3 border-t border-gray-100">
                <Link to={`/bid-periods/${bp.id}/sequences`}
                  className="text-sm text-blue-600 hover:underline">Sequences</Link>
                <Link to={`/bid-periods/${bp.id}/bids`}
                  className="text-sm text-blue-600 hover:underline">Bids</Link>
                <Link to={`/bid-periods/${bp.id}/calendar`}
                  className="text-sm text-blue-600 hover:underline">Calendar</Link>
                <Link to={`/bid-periods/${bp.id}/awarded`}
                  className="text-sm text-blue-600 hover:underline">Award Analysis</Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
