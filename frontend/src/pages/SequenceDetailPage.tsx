import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getSequence } from '../lib/api';
import type { Sequence } from '../types/api';

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

export default function SequenceDetailPage() {
  const { bidPeriodId, sequenceId } = useParams<{ bidPeriodId: string; sequenceId: string }>();
  const [seq, setSeq] = useState<Sequence | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!bidPeriodId || !sequenceId) return;
    getSequence(bidPeriodId, sequenceId)
      .then(setSeq)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [bidPeriodId, sequenceId]);

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;
  if (!seq) return <p className="text-sm text-red-600">Sequence not found.</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/bid-periods/${bidPeriodId}/sequences`} className="text-sm text-blue-600 hover:underline">&larr; Sequences</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">SEQ {seq.seq_number}</h1>
        <div className="flex flex-wrap gap-2 mt-2">
          {seq.category && <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">{seq.category}</span>}
          {seq.language && <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-700">LANG {seq.language} {seq.language_count}</span>}
          {seq.is_turn && <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">Turn</span>}
          {seq.has_deadhead && <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">Deadhead</span>}
          {seq.is_redeye && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">Red-eye</span>}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { label: 'TPAY', value: fmt(seq.totals.tpay_minutes) },
          { label: 'Block', value: fmt(seq.totals.block_minutes) },
          { label: 'TAFB', value: fmt(seq.totals.tafb_minutes) },
          { label: 'OPS', value: String(seq.ops_count) },
          { label: 'Duty Days', value: String(seq.totals.duty_days) },
          { label: 'Legs', value: String(seq.totals.leg_count) },
          { label: 'SYNTH', value: fmt(seq.totals.synth_minutes) },
          { label: 'Position', value: `${seq.position_min}–${seq.position_max}` },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg border border-gray-200 bg-white p-3">
            <p className="text-xs font-medium text-gray-500 uppercase">{label}</p>
            <p className="text-lg font-semibold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="text-sm font-medium text-gray-700 mb-2">Operating Dates</h2>
        <div className="flex flex-wrap gap-1">
          {seq.operating_dates.map((d) => (
            <span key={d} className="inline-block rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">{d}</span>
          ))}
        </div>
      </div>

      {seq.commute_impact && (
        <div className={`rounded-lg border p-4 ${
          seq.commute_impact.impact_level === 'green' ? 'border-green-200 bg-green-50' :
          seq.commute_impact.impact_level === 'yellow' ? 'border-yellow-200 bg-yellow-50' :
          'border-red-200 bg-red-50'
        }`}>
          <h2 className={`text-sm font-semibold mb-2 ${
            seq.commute_impact.impact_level === 'green' ? 'text-green-800' :
            seq.commute_impact.impact_level === 'yellow' ? 'text-yellow-800' :
            'text-red-800'
          }`}>
            Commute Impact — {seq.commute_impact.impact_level.charAt(0).toUpperCase() + seq.commute_impact.impact_level.slice(1)}
          </h2>
          <div className="space-y-1 text-sm">
            {seq.commute_impact.first_day_note && (
              <p className={seq.commute_impact.first_day_feasible ? 'text-gray-700' : 'text-red-700 font-medium'}>
                First day: {seq.commute_impact.first_day_note}
              </p>
            )}
            {seq.commute_impact.last_day_note && (
              <p className={seq.commute_impact.last_day_feasible ? 'text-gray-700' : 'text-red-700 font-medium'}>
                Last day: {seq.commute_impact.last_day_note}
              </p>
            )}
            {seq.commute_impact.hotel_nights_needed > 0 && (
              <p className="text-gray-700">Hotel nights needed: {seq.commute_impact.hotel_nights_needed}</p>
            )}
          </div>
        </div>
      )}

      {seq.layover_cities.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-700 mb-2">Layover Cities</h2>
          <p className="text-sm text-gray-600">{seq.layover_cities.join(' → ')}</p>
        </div>
      )}

      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Itinerary</h2>
        {seq.duty_periods.map((dp) => (
          <div key={dp.dp_number} className="rounded-lg border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-4 py-2 bg-gray-50 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                Duty Period {dp.dp_number}
                {dp.day_of_seq && dp.day_of_seq_total && (
                  <span className="text-gray-400 ml-2">Day {dp.day_of_seq}/{dp.day_of_seq_total}</span>
                )}
              </span>
              <span className="text-xs text-gray-500">
                RPT {dp.report_base} — RLS {dp.release_base}
              </span>
            </div>
            <div className="divide-y divide-gray-50">
              {dp.legs.map((leg) => (
                <div key={leg.leg_index} className={`px-4 py-2 flex items-center gap-4 text-sm ${leg.is_deadhead ? 'bg-yellow-50' : ''}`}>
                  <span className={`font-mono w-16 ${leg.is_deadhead ? 'text-yellow-700' : 'text-gray-700'}`}>
                    {leg.flight_number}
                  </span>
                  <span className="text-gray-500 w-8">{leg.equipment}</span>
                  <span className="font-medium">{leg.departure_station}</span>
                  <span className="text-gray-400">{leg.departure_base}</span>
                  <span className="text-gray-300">→</span>
                  <span className="font-medium">{leg.arrival_station}</span>
                  <span className="text-gray-400">{leg.arrival_base}</span>
                  <span className="text-gray-500 ml-auto">{fmt(leg.block_minutes)}</span>
                </div>
              ))}
            </div>
            {dp.layover && dp.layover.city && (
              <div className="border-t border-gray-100 px-4 py-2 bg-gray-50 text-xs text-gray-500">
                Layover: {dp.layover.city}
                {dp.layover.hotel_name && ` — ${dp.layover.hotel_name}`}
                {dp.layover.rest_minutes && ` (${fmt(dp.layover.rest_minutes)} rest)`}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
