import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listBidPeriods, createBidPeriod, deleteBidPeriod } from '../lib/api';
import type { BidPeriod } from '../types/api';

export default function BidPeriodsPage() {
  const [bidPeriods, setBidPeriods] = useState<BidPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadForm, setUploadForm] = useState({ name: '', file: null as File | null, effective_start: '', effective_end: '' });
  const [error, setError] = useState('');

  const refresh = () => {
    listBidPeriods()
      .then((res) => setBidPeriods(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadForm.file || !uploadForm.name || !uploadForm.effective_start || !uploadForm.effective_end) return;
    setUploading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', uploadForm.file);
      fd.append('name', uploadForm.name);
      fd.append('effective_start', uploadForm.effective_start);
      fd.append('effective_end', uploadForm.effective_end);
      await createBidPeriod(fd);
      setShowUpload(false);
      setUploadForm({ name: '', file: null, effective_start: '', effective_end: '' });
      refresh();
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { detail?: string | Array<{ msg: string }> } } })?.response?.data;
      const detail = data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : 'Upload failed';
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this bid period and all its data?')) return;
    try {
      await deleteBidPeriod(id);
      refresh();
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Bid Periods</h1>
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showUpload ? 'Cancel' : 'New Bid Period'}
        </button>
      </div>

      {showUpload && (
        <form onSubmit={handleUpload} className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          {error && <div className="text-sm text-red-700 bg-red-50 rounded p-2">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-gray-700">Period Name</label>
            <input
              required
              placeholder="January 2026"
              value={uploadForm.name}
              onChange={(e) => setUploadForm((f) => ({ ...f, name: e.target.value }))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">Effective Start</label>
              <input
                type="date"
                required
                value={uploadForm.effective_start}
                onChange={(e) => setUploadForm((f) => ({ ...f, effective_start: e.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Effective End</label>
              <input
                type="date"
                required
                value={uploadForm.effective_end}
                onChange={(e) => setUploadForm((f) => ({ ...f, effective_end: e.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Bid Sheet PDF</label>
            <input
              type="file"
              accept=".pdf"
              required
              onChange={(e) => setUploadForm((f) => ({ ...f, file: e.target.files?.[0] ?? null }))}
              className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
          <button type="submit" disabled={uploading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {uploading ? 'Uploading...' : 'Upload & Parse'}
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : bidPeriods.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
          <p className="text-sm text-gray-500">No bid periods yet. Upload a bid sheet to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {bidPeriods.map((bp) => (
            <div key={bp.id} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
              <Link to={`/bid-periods/${bp.id}`} className="flex-1">
                <p className="font-medium text-gray-900">{bp.name}</p>
                <p className="text-sm text-gray-500">
                  {bp.effective_start} — {bp.effective_end} | {bp.total_sequences} sequences
                </p>
                {bp.categories.length > 0 && (
                  <p className="text-xs text-gray-400 mt-1">{bp.categories.join(', ')}</p>
                )}
              </Link>
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  bp.parse_status === 'completed' ? 'bg-green-100 text-green-700' :
                  bp.parse_status === 'failed' ? 'bg-red-100 text-red-700' :
                  bp.parse_status === 'processing' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {bp.parse_status}
                </span>
                <button onClick={() => handleDelete(bp.id)}
                  className="text-sm text-red-500 hover:text-red-700">
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
