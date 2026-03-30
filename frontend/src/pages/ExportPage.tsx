import { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { getBid, exportBid } from '../lib/api';
import type { Bid } from '../types/api';

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

export default function ExportPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const [searchParams] = useSearchParams();
  const bidId = searchParams.get('bidId') || '';

  const [bid, setBid] = useState<Bid | null>(null);
  const [loading, setLoading] = useState(true);
  const [format, setFormat] = useState<'txt' | 'csv'>('txt');
  const [exported, setExported] = useState(false);

  useEffect(() => {
    if (!bidPeriodId || !bidId) { setLoading(false); return; }
    getBid(bidPeriodId, bidId)
      .then(setBid)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [bidPeriodId, bidId]);

  const handleExport = async () => {
    if (!bidPeriodId || !bidId) return;
    const blob = await exportBid(bidPeriodId, bidId, format);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bid_${bid?.name || 'export'}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
    setExported(true);
  };

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;
  if (!bid) return (
    <div className="space-y-4">
      <Link to={`/bid-periods/${bidPeriodId}/bids`} className="text-sm text-blue-600 hover:underline">&larr; Back to Bid Builder</Link>
      <p className="text-sm text-red-600">Bid not found.</p>
    </div>
  );

  const activeEntries = bid.entries.filter((e) => !e.is_excluded);

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/bid-periods/${bidPeriodId}/bids`} className="text-sm text-blue-600 hover:underline">&larr; Back to Bid Builder</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Export Bid</h1>
        <p className="text-sm text-gray-500">{bid.name} &middot; {activeEntries.length} ranked sequences</p>
      </div>

      {/* Summary */}
      {bid.summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase">Entries</p>
            <p className="text-lg font-semibold">{bid.summary.total_entries}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase">Total TPAY</p>
            <p className="text-lg font-semibold">{fmt(bid.summary.total_tpay_minutes)}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase">Coverage</p>
            <p className="text-lg font-semibold">{Math.round(bid.summary.date_coverage.coverage_rate * 100)}%</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase">Status</p>
            <p className="text-lg font-semibold capitalize">{bid.status}</p>
          </div>
        </div>
      )}

      {/* Preview: ranked list */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
          <h2 className="text-sm font-medium text-gray-700">Ranked Sequence List (Preview)</h2>
        </div>
        <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
          {activeEntries.map((entry) => (
            <div key={entry.sequence_id} className="flex items-center gap-4 px-4 py-2 text-sm">
              <span className="text-gray-400 w-8 text-right font-mono">#{entry.rank}</span>
              <span className="font-semibold text-gray-900">SEQ {entry.seq_number}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                entry.attainability === 'high' ? 'bg-green-100 text-green-700' :
                entry.attainability === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                entry.attainability === 'low' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
              }`}>{entry.attainability}</span>
              <span className="text-gray-400 text-xs">{Math.round(entry.preference_score * 100)}% match</span>
              {entry.is_pinned && <span className="text-blue-500 text-xs">pinned</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Warnings */}
      {bid.summary?.date_coverage.uncovered_dates.length > 0 && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <p className="text-sm font-medium text-yellow-800">Coverage Warning</p>
          <p className="text-sm text-yellow-700 mt-1">
            Your bid does not cover dates: {bid.summary.date_coverage.uncovered_dates.join(', ')}.
            You may be assigned reserve on those days.
          </p>
        </div>
      )}

      {/* Format selection + confirm */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
        <h2 className="text-sm font-medium text-gray-700">Export Format</h2>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="format" value="txt" checked={format === 'txt'}
              onChange={() => setFormat('txt')}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500" />
            <span className="text-sm text-gray-700">Plain Text (.txt)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="format" value="csv" checked={format === 'csv'}
              onChange={() => setFormat('csv')}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500" />
            <span className="text-sm text-gray-700">CSV (.csv)</span>
          </label>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={handleExport}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Confirm &amp; Download
          </button>
          {exported && (
            <span className="text-sm text-green-600">Downloaded successfully.</span>
          )}
        </div>
      </div>
    </div>
  );
}
