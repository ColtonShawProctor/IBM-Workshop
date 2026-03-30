import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../lib/api';

interface AwardedSequenceEntry {
  seq_number: number;
  sequence_id?: string;
  operating_dates: number[];
  tpay_minutes: number;
  block_minutes: number;
  tafb_minutes: number;
}

interface AwardedSchedule {
  id: string;
  bid_period_id: string;
  bid_id?: string;
  source_filename?: string;
  imported_at?: string;
  awarded_sequences: AwardedSequenceEntry[];
}

interface AwardAnalysis {
  bid_id: string;
  awarded_schedule_id: string;
  match_count: number;
  match_rate: number;
  top_10_match_count: number;
  top_10_match_rate: number;
  matched_entries: { seq_number: number; bid_rank: number; was_awarded: boolean; attainability: string }[];
  unmatched_awards: number[];
  attainability_accuracy: { high_awarded: number; high_total: number; low_awarded: number; low_total: number };
  insights: string[];
}

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

export default function AwardedSchedulePage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const [schedule, setSchedule] = useState<AwardedSchedule | null>(null);
  const [analysis, setAnalysis] = useState<AwardAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');

  const fetchData = async () => {
    if (!bidPeriodId) return;
    try {
      const res = await api.get(`/bid-periods/${bidPeriodId}/awarded-schedule`);
      setSchedule(res.data);
      try {
        const analysisRes = await api.get(`/bid-periods/${bidPeriodId}/award-analysis`);
        setAnalysis(analysisRes.data);
      } catch {
        // No analysis available
      }
    } catch {
      // No awarded schedule yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [bidPeriodId]);

  const handleUpload = async () => {
    if (!bidPeriodId || !file) return;
    setUploading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post(`/bid-periods/${bidPeriodId}/awarded-schedule`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setFile(null);
      await fetchData();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/bid-periods/${bidPeriodId}`} className="text-sm text-blue-600 hover:underline">&larr; Back</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Awarded Schedule</h1>
      </div>

      {!schedule ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center">
            <p className="text-sm text-gray-500 mb-3">
              No awarded schedule imported yet. Upload your award file to see how your bid performed.
            </p>
            {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
            <div className="flex items-center justify-center gap-2">
              <input
                type="file"
                accept=".csv,.txt"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-sm text-gray-500 file:mr-2 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-blue-700"
              />
              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {uploading ? 'Importing...' : 'Import'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Awarded sequences table */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              Awarded Sequences ({schedule.awarded_sequences.length})
            </h2>
            <p className="text-xs text-gray-400 mb-3">
              Source: {schedule.source_filename} | Imported: {schedule.imported_at ? new Date(schedule.imported_at).toLocaleDateString() : '—'}
            </p>
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200 bg-white text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">SEQ</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">TPAY</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Block</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">TAFB</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Dates</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {schedule.awarded_sequences.map((as) => (
                    <tr key={as.seq_number} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{as.seq_number}</td>
                      <td className="px-3 py-2">{fmt(as.tpay_minutes)}</td>
                      <td className="px-3 py-2">{fmt(as.block_minutes)}</td>
                      <td className="px-3 py-2">{fmt(as.tafb_minutes)}</td>
                      <td className="px-3 py-2 text-gray-400 text-xs">
                        {as.operating_dates.join(', ') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Analysis */}
          {analysis && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">Bid vs. Award Analysis</h2>

              <div className="grid gap-3 sm:grid-cols-4">
                <div className="rounded-lg border border-gray-200 bg-white p-3">
                  <p className="text-xs text-gray-500 uppercase">Match Rate</p>
                  <p className="text-2xl font-semibold text-gray-900">{Math.round(analysis.match_rate * 100)}%</p>
                  <p className="text-xs text-gray-400">{analysis.match_count} matched</p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-3">
                  <p className="text-xs text-gray-500 uppercase">Top 10 Hit Rate</p>
                  <p className="text-2xl font-semibold text-gray-900">{Math.round(analysis.top_10_match_rate * 100)}%</p>
                  <p className="text-xs text-gray-400">{analysis.top_10_match_count} of top 10</p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-3">
                  <p className="text-xs text-gray-500 uppercase">High Accuracy</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {analysis.attainability_accuracy.high_total > 0
                      ? Math.round((analysis.attainability_accuracy.high_awarded / analysis.attainability_accuracy.high_total) * 100)
                      : 0}%
                  </p>
                  <p className="text-xs text-gray-400">
                    {analysis.attainability_accuracy.high_awarded}/{analysis.attainability_accuracy.high_total} high
                  </p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-3">
                  <p className="text-xs text-gray-500 uppercase">Unmatched Awards</p>
                  <p className="text-2xl font-semibold text-gray-900">{analysis.unmatched_awards.length}</p>
                  {analysis.unmatched_awards.length > 0 && (
                    <p className="text-xs text-gray-400">SEQ {analysis.unmatched_awards.join(', ')}</p>
                  )}
                </div>
              </div>

              {/* Attainability accuracy detail */}
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Attainability Accuracy</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">
                      <span className="font-medium text-green-700">{analysis.attainability_accuracy.high_awarded}</span>
                      {' '}of{' '}
                      <span className="font-medium">{analysis.attainability_accuracy.high_total}</span>
                      {' '}sequences marked &ldquo;high&rdquo; attainability were awarded
                    </p>
                    {analysis.attainability_accuracy.high_total > 0 && (
                      <div className="h-2 rounded-full bg-gray-200 mt-2">
                        <div className="h-2 rounded-full bg-green-500" style={{
                          width: `${Math.round((analysis.attainability_accuracy.high_awarded / analysis.attainability_accuracy.high_total) * 100)}%`
                        }} />
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">
                      <span className="font-medium text-red-700">{analysis.attainability_accuracy.low_awarded}</span>
                      {' '}of{' '}
                      <span className="font-medium">{analysis.attainability_accuracy.low_total}</span>
                      {' '}sequences marked &ldquo;low&rdquo; were awarded (surprises)
                    </p>
                    {analysis.attainability_accuracy.low_total > 0 && (
                      <div className="h-2 rounded-full bg-gray-200 mt-2">
                        <div className="h-2 rounded-full bg-red-400" style={{
                          width: `${Math.round((analysis.attainability_accuracy.low_awarded / analysis.attainability_accuracy.low_total) * 100)}%`
                        }} />
                      </div>
                    )}
                  </div>
                </div>
                {analysis.attainability_accuracy.low_awarded > 0 && (
                  <p className="text-xs text-amber-700 mt-3">
                    Sequences marked &ldquo;low&rdquo; that were awarded suggest the seniority model may need recalibration for next month.
                  </p>
                )}
              </div>

              {/* Surprises: matched entries where attainability didn't predict correctly */}
              {analysis.matched_entries && analysis.matched_entries.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Bid Entry Results</h3>
                  <div className="overflow-x-auto max-h-64 overflow-y-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-1.5 text-left text-xs font-medium text-gray-500">SEQ</th>
                          <th className="px-3 py-1.5 text-left text-xs font-medium text-gray-500">Bid Rank</th>
                          <th className="px-3 py-1.5 text-left text-xs font-medium text-gray-500">Attainability</th>
                          <th className="px-3 py-1.5 text-left text-xs font-medium text-gray-500">Awarded?</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {analysis.matched_entries.map((me) => {
                          const surprise = (me.attainability === 'low' && me.was_awarded) ||
                                          (me.attainability === 'high' && !me.was_awarded);
                          return (
                            <tr key={me.seq_number} className={surprise ? 'bg-amber-50' : ''}>
                              <td className="px-3 py-1.5 font-medium">SEQ {me.seq_number}</td>
                              <td className="px-3 py-1.5">#{me.bid_rank}</td>
                              <td className="px-3 py-1.5">
                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                  me.attainability === 'high' ? 'bg-green-100 text-green-700' :
                                  me.attainability === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                  me.attainability === 'low' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
                                }`}>{me.attainability}</span>
                              </td>
                              <td className="px-3 py-1.5">
                                {me.was_awarded
                                  ? <span className="text-green-600 font-medium">Yes</span>
                                  : <span className="text-gray-400">No</span>}
                                {surprise && <span className="ml-1 text-amber-600 text-xs">(surprise)</span>}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Insights */}
              {analysis.insights.length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-blue-900 mb-2">Insights</h3>
                  <ul className="space-y-1">
                    {analysis.insights.map((insight, i) => (
                      <li key={i} className="text-sm text-blue-800">&bull; {insight}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
