import { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { compareSequences } from '../lib/api';
import type { Sequence } from '../types/api';

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

interface ComparisonResult {
  sequences: Sequence[];
  differences: { attribute: string; values: Record<string, unknown> }[];
}

export default function SequenceComparisonPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const [searchParams] = useSearchParams();
  const ids = searchParams.get('ids')?.split(',').filter(Boolean) || [];

  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!bidPeriodId || ids.length < 2) {
      setError('Select at least 2 sequences to compare.');
      setLoading(false);
      return;
    }
    setLoading(true);
    compareSequences(bidPeriodId, ids)
      .then((res) => setResult(res))
      .catch((err) => setError(err.response?.data?.message || 'Failed to load comparison'))
      .finally(() => setLoading(false));
  }, [bidPeriodId, searchParams.get('ids')]);

  if (loading) return <p className="text-sm text-gray-500">Loading comparison...</p>;
  if (error) return (
    <div className="space-y-4">
      <Link to={`/bid-periods/${bidPeriodId}/sequences`} className="text-sm text-blue-600 hover:underline">&larr; Back to Sequences</Link>
      <p className="text-sm text-red-600">{error}</p>
    </div>
  );
  if (!result) return null;

  const { sequences, differences } = result;
  const diffSet = new Set(differences.map((d) => d.attribute));

  const rows: { label: string; key: string; render: (seq: Sequence) => string }[] = [
    { label: 'SEQ Number', key: 'seq_number', render: (s) => String(s.seq_number) },
    { label: 'Category', key: 'category', render: (s) => s.category || '—' },
    { label: 'OPS', key: 'ops_count', render: (s) => String(s.ops_count) },
    { label: 'Position', key: 'position', render: (s) => `${s.position_min}–${s.position_max}` },
    { label: 'Language', key: 'language', render: (s) => s.language ? `${s.language} (${s.language_count})` : '—' },
    { label: 'TPAY', key: 'totals.tpay_minutes', render: (s) => fmt(s.totals.tpay_minutes) },
    { label: 'Block', key: 'totals.block_minutes', render: (s) => fmt(s.totals.block_minutes) },
    { label: 'SYNTH', key: 'totals.synth_minutes', render: (s) => fmt(s.totals.synth_minutes) },
    { label: 'TAFB', key: 'totals.tafb_minutes', render: (s) => fmt(s.totals.tafb_minutes) },
    { label: 'Duty Days', key: 'totals.duty_days', render: (s) => String(s.totals.duty_days) },
    { label: 'Legs', key: 'totals.leg_count', render: (s) => String(s.totals.leg_count) },
    { label: 'Deadheads', key: 'totals.deadhead_count', render: (s) => String(s.totals.deadhead_count) },
    { label: 'Turn?', key: 'is_turn', render: (s) => s.is_turn ? 'Yes' : 'No' },
    { label: 'Red-eye?', key: 'is_redeye', render: (s) => s.is_redeye ? 'Yes' : 'No' },
    { label: 'Has Deadhead?', key: 'has_deadhead', render: (s) => s.has_deadhead ? 'Yes' : 'No' },
    { label: 'Layover Cities', key: 'layover_cities', render: (s) => s.layover_cities.join(', ') || '—' },
    { label: 'Operating Dates', key: 'operating_dates', render: (s) => s.operating_dates.join(', ') },
    {
      label: 'Report Time',
      key: 'report_time',
      render: (s) => s.duty_periods[0] ? `${s.duty_periods[0].report_local} / ${s.duty_periods[0].report_base}` : '—',
    },
    {
      label: 'Release Time',
      key: 'release_time',
      render: (s) => {
        const last = s.duty_periods[s.duty_periods.length - 1];
        return last ? `${last.release_local} / ${last.release_base}` : '—';
      },
    },
    {
      label: 'Equipment',
      key: 'equipment',
      render: (s) => {
        const eqs = new Set<string>();
        for (const dp of s.duty_periods) for (const leg of dp.legs) eqs.add(leg.equipment);
        return [...eqs].join(', ') || '—';
      },
    },
    {
      label: 'Hotels',
      key: 'hotels',
      render: (s) => s.duty_periods
        .filter((dp) => dp.layover?.hotel_name)
        .map((dp) => `${dp.layover!.city}: ${dp.layover!.hotel_name}`)
        .join('; ') || '—',
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <Link to={`/bid-periods/${bidPeriodId}/sequences`} className="text-sm text-blue-600 hover:underline">&larr; Back to Sequences</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Compare Sequences</h1>
        <p className="text-sm text-gray-500">{sequences.length} sequences selected</p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 bg-white text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-medium text-gray-600 sticky left-0 bg-gray-50 min-w-[100px] sm:min-w-[140px]">Attribute</th>
              {sequences.map((seq) => (
                <th key={seq.id} scope="col" className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-medium text-gray-900 min-w-[120px] sm:min-w-[160px]">
                  <Link to={`/bid-periods/${bidPeriodId}/sequences/${seq.id}`} className="text-blue-600 hover:underline">
                    SEQ {seq.seq_number}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => {
              const isDiff = diffSet.has(row.key);
              return (
                <tr key={row.key} className={isDiff ? 'bg-yellow-50' : ''}>
                  <th scope="row" className={`px-2 sm:px-4 py-2 text-xs sm:text-sm font-medium sticky left-0 ${isDiff ? 'bg-yellow-50 text-yellow-800' : 'bg-white text-gray-600'}`}>
                    {row.label}
                    {isDiff && <span className="ml-1 text-xs text-yellow-600">*</span>}
                  </th>
                  {sequences.map((seq) => (
                    <td key={seq.id} className="px-2 sm:px-4 py-2 text-xs sm:text-sm text-gray-900">
                      {row.render(seq)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {differences.length > 0 && (
        <p className="text-xs text-gray-500">
          * Highlighted rows indicate attributes that differ between the selected sequences.
        </p>
      )}
    </div>
  );
}
