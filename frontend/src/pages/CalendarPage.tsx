import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getBidPeriod, listBids, getBid, listSequences } from '../lib/api';
import type { BidPeriod, Bid, Sequence } from '../types/api';

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  '777 INTL': { bg: 'bg-blue-200', text: 'text-blue-800', dot: 'bg-blue-400' },
  '787 INTL': { bg: 'bg-indigo-200', text: 'text-indigo-800', dot: 'bg-indigo-400' },
  'NBI INTL': { bg: 'bg-teal-200', text: 'text-teal-800', dot: 'bg-teal-400' },
  'NBD DOM': { bg: 'bg-green-200', text: 'text-green-800', dot: 'bg-green-400' },
};

const DEFAULT_COLOR = { bg: 'bg-gray-200', text: 'text-gray-700', dot: 'bg-gray-400' };

export default function CalendarPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const navigate = useNavigate();
  const [bp, setBp] = useState<BidPeriod | null>(null);
  const [bid, setBid] = useState<Bid | null>(null);
  const [seqMap, setSeqMap] = useState<Map<string, Sequence>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!bidPeriodId) return;
    Promise.all([
      getBidPeriod(bidPeriodId),
      listBids(bidPeriodId),
      listSequences(bidPeriodId, { limit: 200 }),
    ]).then(([bpData, bidsData, seqData]) => {
      setBp(bpData);
      if (bidsData.data.length > 0) {
        getBid(bidPeriodId, bidsData.data[0].id).then(setBid);
      }
      const map = new Map<string, Sequence>();
      for (const s of seqData.data) map.set(s.id, s);
      setSeqMap(map);
    }).finally(() => setLoading(false));
  }, [bidPeriodId]);

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;
  if (!bp) return <p className="text-sm text-red-600">Bid period not found.</p>;

  const totalDays = bp.total_dates || 30;
  const days = Array.from({ length: totalDays }, (_, i) => i + 1);

  const daySequences = new Map<number, { seq: Sequence; rank: number }[]>();
  const coveredDays = new Set<number>();

  if (bid) {
    for (const entry of bid.entries) {
      if (entry.is_excluded) continue;
      const seq = seqMap.get(entry.sequence_id);
      if (!seq) continue;
      for (const d of seq.operating_dates) {
        coveredDays.add(d);
        if (!daySequences.has(d)) daySequences.set(d, []);
        daySequences.get(d)!.push({ seq, rank: entry.rank });
      }
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <Link to={`/bid-periods/${bidPeriodId}`} className="text-sm text-blue-600 hover:underline">&larr; Back</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Calendar View</h1>
        <p className="text-sm text-gray-500">{bp.name} — {bp.effective_start} to {bp.effective_end}</p>
      </div>

      {!bid ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
          <p className="text-sm text-gray-500">No bid found. Create a bid first to see sequences on the calendar.</p>
          <Link to={`/bid-periods/${bidPeriodId}/bids`} className="text-sm text-blue-600 hover:underline mt-1 inline-block">
            Go to Bid Builder
          </Link>
        </div>
      ) : (
        <>
          {/* Calendar grid */}
          <div className="grid grid-cols-4 sm:grid-cols-7 gap-1" role="grid" aria-label="Bid period calendar">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
              <div key={d} role="columnheader" className="hidden sm:block text-center text-xs font-medium text-gray-500 py-1">{d}</div>
            ))}
            {days.map((day) => {
              const seqs = daySequences.get(day) || [];
              const isCovered = coveredDays.has(day);
              const hasConflict = seqs.length > 1;

              return (
                <div
                  key={day}
                  role="gridcell"
                  aria-label={`Day ${day}${!isCovered ? ', uncovered' : ''}${hasConflict ? `, ${seqs.length} conflicting sequences` : ''}`}
                  className={`min-h-[70px] sm:min-h-[90px] rounded border p-1 sm:p-1.5 text-xs relative ${
                    !isCovered
                      ? 'border-red-300'
                      : hasConflict
                      ? 'bg-yellow-50 border-yellow-200'
                      : 'bg-white border-gray-200'
                  }`}
                >
                  {/* Red diagonal hatch for uncovered dates */}
                  {!isCovered && (
                    <div className="absolute inset-0 rounded pointer-events-none"
                      style={{
                        background: 'repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(239,68,68,0.1) 4px, rgba(239,68,68,0.1) 8px)',
                      }} />
                  )}
                  <div className={`font-medium mb-1 relative z-10 flex items-center justify-between ${!isCovered ? 'text-red-600' : 'text-gray-700'}`}>
                    <span>{day}</span>
                    {hasConflict && (
                      <span className="text-yellow-600" role="img" aria-label={`${seqs.length} sequences conflict on day ${day}`} title={`${seqs.length} sequences conflict on this date`}>
                        &#x26A0;
                      </span>
                    )}
                  </div>
                  <div className="relative z-10 space-y-0.5">
                    {seqs.slice(0, 3).map(({ seq, rank }) => {
                      const colors = CATEGORY_COLORS[seq.category || ''] || DEFAULT_COLOR;
                      const isFirstDay = seq.operating_dates.length > 0 && seq.operating_dates[0] === day;
                      const isLastDay = seq.operating_dates.length > 0 && seq.operating_dates[seq.operating_dates.length - 1] === day;
                      const ci = seq.commute_impact;
                      const showCommuteDot = ci && ((isFirstDay && ci.first_day_note) || (isLastDay && ci.last_day_note));
                      return (
                        <button
                          key={seq.id}
                          onClick={() => navigate(`/bid-periods/${bidPeriodId}/sequences/${seq.id}`)}
                          className={`w-full rounded px-1 py-0.5 truncate text-left ${colors.bg} ${colors.text} hover:opacity-80 relative`}
                          title={`#${rank} SEQ ${seq.seq_number} — ${fmt(seq.totals.tpay_minutes)} TPAY | ${seq.layover_cities.join(', ') || 'Turn'}`}
                          aria-label={`Rank ${rank}, Sequence ${seq.seq_number}, ${fmt(seq.totals.tpay_minutes)} TPAY`}
                        >
                          #{rank} S{seq.seq_number}
                          {showCommuteDot && (
                            <span
                              className={`absolute top-0 right-0 w-2 h-2 rounded-full -mt-0.5 -mr-0.5 ${
                                ci.impact_level === 'green' ? 'bg-green-500' :
                                ci.impact_level === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'
                              }`}
                              title={isFirstDay ? ci.first_day_note : ci.last_day_note}
                            />
                          )}
                        </button>
                      );
                    })}
                    {seqs.length > 3 && (
                      <div className="text-gray-400">+{seqs.length - 3} more</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-4 rounded border border-red-300"
                style={{ background: 'repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(239,68,68,0.15) 2px, rgba(239,68,68,0.15) 4px)' }} />
              <span className="text-gray-600">Uncovered (reserve risk)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-4 rounded bg-yellow-50 border border-yellow-200 flex items-center justify-center text-yellow-600 text-[8px]">&#x26A0;</div>
              <span className="text-gray-600">Date conflict</span>
            </div>
            {Object.entries(CATEGORY_COLORS).map(([cat, colors]) => (
              <div key={cat} className="flex items-center gap-1.5">
                <div className={`w-4 h-4 rounded ${colors.bg}`} />
                <span className="text-gray-600">{cat}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
