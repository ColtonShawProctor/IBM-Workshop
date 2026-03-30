import { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { listBids, createBid, updateBid, optimizeBid, listSequences } from '../lib/api';
import type { Bid, BidEntry, Sequence } from '../types/api';

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

function groupColor(group: string): string {
  return `hsl(${parseInt(group, 36) % 360}, 60%, 60%)`;
}

function AttainabilityBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    high: 'bg-green-100 text-green-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-red-100 text-red-700',
    unknown: 'bg-gray-100 text-gray-600',
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors[level] || colors.unknown}`}>
      {level}
    </span>
  );
}

function PrefScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-16 rounded-full bg-gray-200">
        <div className="h-2 rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  );
}

function RationaleTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      <button
        className="text-gray-400 hover:text-gray-600 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400 rounded-full"
        aria-label="Show reasoning for this rank"
        aria-expanded={show}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
      >?</button>
      {show && (
        <span role="tooltip" className="absolute bottom-full right-0 mb-2 w-64 rounded-md bg-gray-900 px-3 py-2 text-xs text-white shadow-lg z-50">
          {text}
          <span className="absolute top-full right-4 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  );
}

export default function BidsPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const navigate = useNavigate();
  const [bids, setBids] = useState<Bid[]>([]);
  const [activeBid, setActiveBid] = useState<Bid | null>(null);
  const [sequences, setSequences] = useState<Map<string, Sequence>>(new Map());
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [newBidName, setNewBidName] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);

  const refreshBids = useCallback(async () => {
    if (!bidPeriodId) return;
    const res = await listBids(bidPeriodId);
    setBids(res.data);
    if (res.data.length > 0 && !activeBid) {
      setActiveBid(res.data[0]);
    }
  }, [bidPeriodId, activeBid]);

  useEffect(() => { refreshBids().finally(() => setLoading(false)); }, [refreshBids]);

  useEffect(() => {
    if (!bidPeriodId || !activeBid) return;
    const ids = activeBid.entries.map((e) => e.sequence_id).filter((id) => !sequences.has(id));
    if (ids.length === 0) return;
    listSequences(bidPeriodId, { limit: 200 }).then((res) => {
      const map = new Map(sequences);
      for (const s of res.data) map.set(s.id, s);
      setSequences(map);
    });
  }, [bidPeriodId, activeBid, sequences]);

  const handleCreateBid = async () => {
    if (!bidPeriodId || !newBidName) return;
    const bid = await createBid(bidPeriodId, newBidName);
    setBids((prev) => [bid, ...prev]);
    setActiveBid(bid);
    setShowCreate(false);
    setNewBidName('');
  };

  const handleOptimize = async () => {
    if (!bidPeriodId || !activeBid) return;
    setOptimizing(true);
    try {
      const updated = await optimizeBid(bidPeriodId, activeBid.id);
      setActiveBid(updated);
      setBids((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    } catch { /* ignore */ } finally { setOptimizing(false); }
  };

  const sendUpdate = async (entries: BidEntry[]) => {
    if (!bidPeriodId || !activeBid) return;
    const updated = await updateBid(bidPeriodId, activeBid.id, {
      entries: entries.map((e) => ({
        sequence_id: e.sequence_id, rank: e.rank, is_pinned: e.is_pinned, is_excluded: e.is_excluded,
      })),
    } as Partial<Bid>);
    setActiveBid(updated);
  };

  const handleTogglePin = (entry: BidEntry) => {
    if (!activeBid) return;
    const newEntries = activeBid.entries.map((e) =>
      e.sequence_id === entry.sequence_id ? { ...e, is_pinned: !e.is_pinned } : e
    );
    sendUpdate(newEntries);
  };

  const handleToggleExclude = (entry: BidEntry) => {
    if (!activeBid) return;
    const newEntries = activeBid.entries.map((e) =>
      e.sequence_id === entry.sequence_id ? { ...e, is_excluded: !e.is_excluded } : e
    );
    sendUpdate(newEntries);
  };

  const handleDragStart = (idx: number) => setDragIdx(idx);
  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); };
  const handleDrop = async (idx: number) => {
    if (dragIdx === null || !activeBid || !bidPeriodId) return;
    const entries = [...activeBid.entries];
    const [moved] = entries.splice(dragIdx, 1);
    entries.splice(idx, 0, moved);
    const reranked = entries.map((e, i) => ({ ...e, rank: i + 1 }));
    setActiveBid({ ...activeBid, entries: reranked });
    setDragIdx(null);
    sendUpdate(reranked);
  };

  const activeEntries = activeBid?.entries.filter((e) => !e.is_excluded) || [];
  const excludedEntries = activeBid?.entries.filter((e) => e.is_excluded) || [];
  const coverage = activeBid?.summary?.date_coverage;

  // Determine primary/fallback within conflict groups
  const conflictGroupFirstRank: Record<string, number> = {};
  for (const entry of activeEntries) {
    if (entry.date_conflict_group) {
      if (!(entry.date_conflict_group in conflictGroupFirstRank)) {
        conflictGroupFirstRank[entry.date_conflict_group] = entry.rank;
      }
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Loading...</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <Link to={`/bid-periods/${bidPeriodId}`} className="text-sm text-blue-600 hover:underline">&larr; Back</Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">Bid Builder</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {activeBid && (
            <>
              <button onClick={handleOptimize} disabled={optimizing}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                {optimizing ? 'Optimizing...' : 'Optimize'}
              </button>
              <button onClick={() => navigate(`/bid-periods/${bidPeriodId}/export?bidId=${activeBid.id}`)}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
                Export
              </button>
            </>
          )}
          <button onClick={() => setShowCreate(!showCreate)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
            + New Bid
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg p-3">
          <input placeholder="Bid name (e.g. My January Bid)" value={newBidName}
            onChange={(e) => setNewBidName(e.target.value)}
            className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
          <button onClick={handleCreateBid}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
            Create
          </button>
        </div>
      )}

      {bids.length > 1 && (
        <div className="flex gap-2" role="tablist" aria-label="Bid versions">
          {bids.map((b) => (
            <button key={b.id} onClick={() => setActiveBid(b)}
              role="tab"
              aria-selected={activeBid?.id === b.id}
              className={`rounded-md px-3 py-1 text-sm ${
                activeBid?.id === b.id ? 'bg-blue-100 text-blue-700 font-medium' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>{b.name}</button>
          ))}
        </div>
      )}

      {!activeBid ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
          <p className="text-sm text-gray-500">No bids yet. Create one to start building your rank-ordered bid.</p>
        </div>
      ) : (
        <>
          {/* Date coverage meter */}
          {coverage && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Date Coverage</span>
                <span className="text-sm text-gray-500">{Math.round(coverage.coverage_rate * 100)}%</span>
              </div>
              <div className="h-3 rounded-full bg-gray-200">
                <div className={`h-3 rounded-full transition-all ${
                  coverage.coverage_rate >= 0.9 ? 'bg-green-500' :
                  coverage.coverage_rate >= 0.7 ? 'bg-yellow-500' : 'bg-red-500'
                }`} style={{ width: `${Math.round(coverage.coverage_rate * 100)}%` }} />
              </div>
              {coverage.uncovered_dates.length > 0 && (
                <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3">
                  <p className="text-sm font-medium text-red-800">Coverage Warning</p>
                  <p className="text-xs text-red-700 mt-1">
                    Your bid does not cover dates: <span className="font-medium">{coverage.uncovered_dates.join(', ')}</span>.
                    You may be assigned reserve on those days. Consider adding sequences that operate on those dates.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Summary stats */}
          {activeBid.summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500 uppercase">Entries</p>
                <p className="text-lg font-semibold">{activeBid.summary.total_entries}</p>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500 uppercase">Total TPAY</p>
                <p className="text-lg font-semibold">{fmt(activeBid.summary.total_tpay_minutes)}</p>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500 uppercase">Days Off</p>
                <p className="text-lg font-semibold">{activeBid.summary.total_days_off}</p>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500 uppercase">Conflict Groups</p>
                <p className="text-lg font-semibold">{activeBid.summary.conflict_groups}</p>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500 uppercase">Status</p>
                <p className="text-lg font-semibold capitalize">{activeBid.status}</p>
              </div>
            </div>
          )}

          {/* Ranked entries */}
          <div>
            <h2 className="text-sm font-medium text-gray-700 mb-2">
              Ranked Sequences ({activeEntries.length})
            </h2>
            {activeEntries.length === 0 ? (
              <p className="text-sm text-gray-400">
                No entries yet. Run Optimize to auto-rank sequences based on your preferences.
              </p>
            ) : (
              <div className="space-y-1" role="list" aria-label="Ranked bid entries">
                {activeEntries.map((entry, idx) => {
                  const seq = sequences.get(entry.sequence_id);
                  const isPrimary = entry.date_conflict_group &&
                    conflictGroupFirstRank[entry.date_conflict_group] === entry.rank;
                  const isFallback = entry.date_conflict_group && !isPrimary;

                  return (
                    <div
                      key={entry.sequence_id}
                      role="listitem"
                      draggable
                      aria-label={`Rank ${entry.rank}, Sequence ${entry.seq_number}${entry.is_pinned ? ', pinned' : ''}${isPrimary ? ', primary pick' : ''}${isFallback ? ', fallback' : ''}`}
                      onDragStart={() => handleDragStart(idx)}
                      onDragOver={handleDragOver}
                      onDrop={() => handleDrop(idx)}
                      className={`flex items-center gap-3 rounded-lg border bg-white p-3 cursor-grab active:cursor-grabbing transition-colors ${
                        entry.is_pinned ? 'border-blue-300 bg-blue-50' : 'border-gray-200'
                      } ${entry.date_conflict_group ? 'border-l-4' : ''}`}
                      style={entry.date_conflict_group ? { borderLeftColor: groupColor(entry.date_conflict_group) } : undefined}
                    >
                      <span className="text-sm font-medium text-gray-400 w-8 text-right shrink-0">#{entry.rank}</span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-gray-900">SEQ {entry.seq_number}</span>
                          {isPrimary && (
                            <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">primary</span>
                          )}
                          {isFallback && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">fallback</span>
                          )}
                        </div>
                        {seq && (
                          <span className="text-xs text-gray-500">
                            {fmt(seq.totals.tpay_minutes)} TPAY | {seq.layover_cities.join(', ') || 'Turn'} | {seq.operating_dates.length}d
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <PrefScoreBar score={entry.preference_score} />
                        <AttainabilityBadge level={entry.attainability} />
                        {entry.rationale && <RationaleTooltip text={entry.rationale} />}
                        <button onClick={() => handleTogglePin(entry)}
                          title={entry.is_pinned ? 'Unpin' : 'Pin'}
                          aria-label={entry.is_pinned ? `Unpin sequence ${entry.seq_number}` : `Pin sequence ${entry.seq_number}`}
                          className={`text-sm ${entry.is_pinned ? 'text-blue-600' : 'text-gray-400 hover:text-blue-600'}`}>
                          {entry.is_pinned ? '\uD83D\uDCCC' : '\uD83D\uDCCD'}
                        </button>
                        <button onClick={() => handleToggleExclude(entry)}
                          title="Exclude"
                          aria-label={`Exclude sequence ${entry.seq_number} from bid`}
                          className="text-sm text-gray-400 hover:text-red-600">
                          \u2715
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Excluded entries */}
          {excludedEntries.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-gray-500 mb-2">Excluded ({excludedEntries.length})</h2>
              <div className="space-y-1 opacity-60">
                {excludedEntries.map((entry) => (
                  <div key={entry.sequence_id}
                    className="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 p-2">
                    <span className="text-sm text-gray-400 w-16">SEQ {entry.seq_number}</span>
                    <button onClick={() => handleToggleExclude(entry)}
                      className="text-xs text-blue-600 hover:underline ml-auto">Restore</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
