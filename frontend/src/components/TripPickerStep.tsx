import React, { useState, useEffect, useCallback, useMemo } from 'react';
import type { GuidedCriteria, RankedTrip, ConflictPair } from '../lib/api';
import { guidedRankedTrips, guidedCheckConflicts } from '../lib/api';

interface TripPickerStepProps {
  bidPeriodId: string;
  criteria: GuidedCriteria;
  onBack: () => void;
  onBuild: (selectedIds: string[]) => void;
  isCommuter: boolean;
}

const SORT_OPTIONS = [
  { label: 'Best Match', value: 'best_match' },
  { label: 'Highest Credit', value: 'credit' },
  { label: 'Date (earliest)', value: 'date' },
  { label: 'Report Time (latest)', value: 'report_time' },
] as const;

const PAGE_SIZE = 50;

function formatMinutesToTime(minutes: string): string {
  // report_time / release_time come as HH:MM strings from the API
  return minutes;
}

function holdabilityColor(label: string): string {
  switch (label.toUpperCase()) {
    case 'LIKELY':
      return 'bg-green-100 text-green-800 border-green-300';
    case 'COMPETITIVE':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'LONG SHOT':
      return 'bg-red-100 text-red-800 border-red-300';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300';
  }
}

function commuteImpactDot(impact: 'green' | 'yellow' | 'red'): string {
  switch (impact) {
    case 'green':
      return 'bg-green-500';
    case 'yellow':
      return 'bg-yellow-500';
    case 'red':
      return 'bg-red-500';
    default:
      return 'bg-gray-400';
  }
}

export default function TripPickerStep({
  bidPeriodId,
  criteria,
  onBack,
  onBuild,
  isCommuter,
}: TripPickerStepProps) {
  // ── State ──────────────────────────────────────────────────────────────
  const [trips, setTrips] = useState<RankedTrip[]>([]);
  const [totalMatching, setTotalMatching] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [conflicts, setConflicts] = useState<ConflictPair[]>([]);
  const [sortBy, setSortBy] = useState('best_match');
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // ── Fetch trips ────────────────────────────────────────────────────────
  const fetchTrips = useCallback(
    async (currentOffset: number, append: boolean) => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      try {
        const result = await guidedRankedTrips(bidPeriodId, {
          ...criteria,
          sort_by: sortBy,
          limit: PAGE_SIZE,
          offset: currentOffset,
        });
        if (append) {
          setTrips((prev) => [...prev, ...result.trips]);
        } else {
          setTrips(result.trips);
        }
        setTotalMatching(result.total_matching);
      } catch (err) {
        console.error('Failed to fetch ranked trips', err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [bidPeriodId, criteria, sortBy],
  );

  // Initial fetch and re-fetch when sort changes
  useEffect(() => {
    setOffset(0);
    fetchTrips(0, false);
  }, [fetchTrips]);

  // ── Conflict checking ─────────────────────────────────────────────────
  useEffect(() => {
    const ids = Array.from(selectedIds);
    if (ids.length < 2) {
      setConflicts([]);
      return;
    }
    let cancelled = false;
    guidedCheckConflicts(bidPeriodId, ids)
      .then((res) => {
        if (!cancelled) setConflicts(res.conflicts);
      })
      .catch((err) => console.error('Conflict check failed', err));
    return () => {
      cancelled = true;
    };
  }, [bidPeriodId, selectedIds]);

  // ── Selection helpers ─────────────────────────────────────────────────
  const toggleSelect = useCallback((seqId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(seqId)) {
        next.delete(seqId);
      } else {
        next.add(seqId);
      }
      return next;
    });
  }, []);

  const toggleExpand = useCallback((seqId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(seqId)) {
        next.delete(seqId);
      } else {
        next.add(seqId);
      }
      return next;
    });
  }, []);

  // ── Load more ─────────────────────────────────────────────────────────
  const handleLoadMore = useCallback(() => {
    const newOffset = offset + PAGE_SIZE;
    setOffset(newOffset);
    fetchTrips(newOffset, true);
  }, [offset, fetchTrips]);

  // ── Computed values from selection ────────────────────────────────────
  const selectedTrips = useMemo(
    () => trips.filter((t) => selectedIds.has(t.sequence_id)),
    [trips, selectedIds],
  );

  const totalCredit = useMemo(
    () =>
      selectedTrips.reduce((sum, t) => sum + t.tpay_minutes / 60, 0),
    [selectedTrips],
  );

  const workingDates = useMemo(() => {
    const dates = new Set<number>();
    for (const t of selectedTrips) {
      for (const d of t.operating_dates) {
        // Each operating date starts a span of duty_days
        for (let i = 0; i < t.duty_days; i++) {
          dates.add(d + i);
        }
      }
    }
    return dates;
  }, [selectedTrips]);

  const firstDay = useMemo(() => {
    if (workingDates.size === 0) return 0;
    return Math.min(...workingDates);
  }, [workingDates]);

  const lastDay = useMemo(() => {
    if (workingDates.size === 0) return 0;
    return Math.max(...workingDates);
  }, [workingDates]);

  const daysOff = useMemo(() => 30 - workingDates.size, [workingDates]);

  // ── Conflict lookup for a given trip ──────────────────────────────────
  const getConflictsForTrip = useCallback(
    (seqId: string): ConflictPair[] =>
      conflicts.filter(
        (c) => c.seq_a_id === seqId || c.seq_b_id === seqId,
      ),
    [conflicts],
  );

  // ── Mini calendar data (days 1-30) ────────────────────────────────────
  const calendarBoxes = useMemo(() => {
    const boxes: ('working' | 'off')[] = [];
    for (let d = 1; d <= 30; d++) {
      boxes.push(workingDates.has(d) ? 'working' : 'off');
    }
    return boxes;
  }, [workingDates]);

  // ── Sort change handler ───────────────────────────────────────────────
  const handleSortChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSortBy(e.target.value);
    },
    [],
  );

  // ── Build handler ─────────────────────────────────────────────────────
  const handleBuild = useCallback(() => {
    onBuild(Array.from(selectedIds));
  }, [onBuild, selectedIds]);

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col min-h-screen bg-gray-50 pb-40">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-white border-b px-4 py-3">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          <button
            onClick={onBack}
            className="text-sm text-gray-400 hover:text-gray-600 font-medium flex items-center gap-1"
          >
            <span>&larr;</span> Home
          </button>
          <div className="text-center">
            <h2 className="text-lg font-bold text-gray-900 tracking-wide">
              YOUR TOP TRIPS
            </h2>
            <p className="text-xs text-gray-500">
              {totalMatching} trips match your preferences
            </p>
          </div>
          <div className="w-16" /> {/* spacer for centering */}
        </div>
      </div>

      {/* Auto-build CTA */}
      {!loading && trips.length > 0 && (
        <div className="max-w-3xl mx-auto w-full px-4 pt-4 pb-2">
          <button
            onClick={() => {
              // Auto-select top 20 trips and build immediately
              const autoIds = trips.slice(0, Math.min(20, trips.length)).map(t => t.sequence_id);
              onBuild(autoIds);
            }}
            className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white px-6 py-4 shadow-lg transition-all focus:outline-none focus:ring-4 focus:ring-blue-200"
          >
            <div className="text-lg font-bold">Build My Bid</div>
            <div className="text-sm text-blue-200 mt-0.5">
              Auto-selects your best {Math.min(20, trips.length)} trips for all 7 layers
            </div>
          </button>
          <p className="text-center text-xs text-gray-400 mt-2">
            Or star specific trips below, then use the Build button at the bottom
          </p>
        </div>
      )}

      {/* Sort bar */}
      <div className="max-w-3xl mx-auto w-full px-4 pt-3 pb-1">
        <div className="flex items-center gap-2">
          <label htmlFor="sort-select" className="text-sm font-medium text-gray-600">
            Sort by:
          </label>
          <select
            id="sort-select"
            value={sortBy}
            onChange={handleSortChange}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Trip list */}
      <div className="max-w-3xl mx-auto w-full px-4 py-2 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
            <span className="ml-3 text-gray-500 text-sm">Loading trips...</span>
          </div>
        ) : trips.length === 0 ? (
          <div className="text-center py-16 text-gray-400 text-sm">
            No matching trips found. Try adjusting your criteria.
          </div>
        ) : (
          trips.map((trip, index) => {
            const isSelected = selectedIds.has(trip.sequence_id);
            const isExpanded = expandedIds.has(trip.sequence_id);
            const tripConflicts = isSelected
              ? getConflictsForTrip(trip.sequence_id)
              : [];
            const cities = trip.layover_cities.join(', ');
            const dateFirst = trip.operating_dates.length > 0
              ? Math.min(...trip.operating_dates)
              : 0;
            const dateLast = trip.operating_dates.length > 0
              ? Math.max(...trip.operating_dates)
              : 0;

            return (
              <div
                key={trip.sequence_id}
                className={`rounded-lg border shadow-sm hover:shadow-md transition-shadow ${
                  isSelected
                    ? 'bg-yellow-50 border-yellow-300'
                    : 'bg-white border-gray-200'
                }`}
              >
                <div className="flex items-start gap-3 p-4">
                  {/* Star toggle */}
                  <button
                    onClick={() => toggleSelect(trip.sequence_id)}
                    className="mt-0.5 text-2xl leading-none flex-shrink-0 focus:outline-none"
                    aria-label={isSelected ? 'Unstar trip' : 'Star trip'}
                  >
                    {isSelected ? (
                      <span className="text-yellow-500">{'\u2605'}</span>
                    ) : (
                      <span className="text-gray-300 hover:text-yellow-400">{'\u2606'}</span>
                    )}
                  </button>

                  {/* Main content */}
                  <div className="flex-1 min-w-0">
                    {/* Top row */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold text-gray-400">
                        #{index + 1}
                      </span>
                      <span className="text-sm font-semibold text-gray-900 truncate">
                        {cities || 'N/A'} {trip.duty_days}-Day
                      </span>
                      <span className="text-sm text-gray-600">
                        {trip.credit_hours.toFixed(1)}h
                      </span>
                      <span className="text-xs text-gray-400">
                        Seq #{trip.seq_number}
                      </span>
                      {dateFirst > 0 && (
                        <span className="text-xs text-gray-500 ml-auto whitespace-nowrap">
                          Day {dateFirst}&ndash;{dateLast + trip.duty_days - 1}
                        </span>
                      )}
                    </div>

                    {/* Second line */}
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
                      <span>
                        Report {formatMinutesToTime(trip.report_time)}
                      </span>
                      <span>
                        Release {formatMinutesToTime(trip.release_time)}
                      </span>
                      {trip.equipment.length > 0 && (
                        <span className="text-gray-400">
                          {trip.equipment.join(', ')}
                        </span>
                      )}
                      {trip.is_redeye && (
                        <span className="text-red-400 font-medium">Red-eye</span>
                      )}
                    </div>

                    {/* Match reasons */}
                    {trip.match_reasons.length > 0 && (
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        {trip.match_reasons.map((reason, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-50 rounded-full px-2 py-0.5"
                          >
                            <span className="text-green-500">{'\u2713'}</span>
                            {reason}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Badges row */}
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      {/* Holdability badge */}
                      <span
                        className={`text-xs font-medium border rounded-full px-2 py-0.5 ${holdabilityColor(
                          trip.holdability_label,
                        )}`}
                      >
                        {trip.holdability_label} ({trip.holdability_pct}%)
                      </span>

                      {/* Commute impact dot */}
                      {isCommuter && (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                          <span
                            className={`inline-block w-2.5 h-2.5 rounded-full ${commuteImpactDot(
                              trip.commute_impact,
                            )}`}
                          />
                          Commute
                        </span>
                      )}

                      {/* Expand toggle */}
                      <button
                        onClick={() => toggleExpand(trip.sequence_id)}
                        className="ml-auto text-xs text-blue-600 hover:text-blue-800 font-medium focus:outline-none"
                      >
                        {isExpanded ? 'Less' : 'More'}
                      </button>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <p className="text-xs font-medium text-gray-600 mb-1">
                          Operating Dates
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {trip.operating_dates.map((d) => (
                            <span
                              key={d}
                              className="text-xs bg-blue-50 text-blue-700 rounded px-1.5 py-0.5"
                            >
                              Day {d}
                            </span>
                          ))}
                        </div>
                        <div className="mt-2 text-xs text-gray-500 space-y-0.5">
                          <p>Category: {trip.category}</p>
                          <p>Match Score: {trip.match_score.toFixed(1)}</p>
                          {trip.is_odan && <p className="text-orange-600 font-medium">ODAN trip</p>}
                        </div>
                      </div>
                    )}

                    {/* Conflict warnings */}
                    {tripConflicts.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {tripConflicts.map((c, i) => {
                          const otherSeq =
                            c.seq_a_id === trip.sequence_id
                              ? c.seq_b_number
                              : c.seq_a_number;
                          return (
                            <div
                              key={i}
                              className="flex items-start gap-1.5 text-xs bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-md px-2 py-1.5"
                            >
                              <span className="text-yellow-600 flex-shrink-0 mt-px">
                                {'\u26A0'}
                              </span>
                              <span>
                                This trip overlaps with #{otherSeq} on day(s){' '}
                                {c.overlap_dates.join(', ')}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}

        {/* Load more button */}
        {!loading && trips.length < totalMatching && (
          <div className="flex justify-center py-4">
            <button
              onClick={handleLoadMore}
              disabled={loadingMore}
              className="text-sm font-medium text-blue-600 hover:text-blue-800 bg-white border border-blue-300 rounded-lg px-6 py-2 hover:bg-blue-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingMore ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                  Loading...
                </span>
              ) : (
                'Load more trips'
              )}
            </button>
          </div>
        )}
      </div>

      {/* Floating bottom bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-30">
        <div className="max-w-3xl mx-auto px-4 py-3">
          {/* Stats line */}
          <div className="flex items-center justify-between text-sm text-gray-700 mb-2 flex-wrap gap-1">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="font-semibold text-yellow-600">
                {'\u2605'} {selectedIds.size} selected
              </span>
              <span className="text-gray-400">|</span>
              <span>{totalCredit.toFixed(1)}h credit</span>
              {firstDay > 0 && (
                <>
                  <span className="text-gray-400">|</span>
                  <span>
                    Day {firstDay}&ndash;{lastDay}
                  </span>
                </>
              )}
              <span className="text-gray-400">|</span>
              <span>{daysOff} days off</span>
            </div>
          </div>

          {/* Mini calendar bar */}
          <div className="flex items-center gap-px mb-3" aria-label="Monthly calendar overview">
            {calendarBoxes.map((status, i) => (
              <div
                key={i}
                className={`rounded-sm ${
                  status === 'working' ? 'bg-blue-500' : 'bg-gray-200'
                }`}
                style={{ width: '4px', height: '12px' }}
                title={`Day ${i + 1}: ${status === 'working' ? 'Working' : 'Off'}`}
              />
            ))}
            <span className="ml-2 text-[10px] text-gray-400">1&ndash;30</span>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="text-sm text-gray-500 hover:text-gray-700 font-medium px-3 py-2"
            >
              &larr; Back
            </button>
            <button
              onClick={handleBuild}
              disabled={selectedIds.size === 0}
              className={`flex-1 text-sm font-semibold rounded-lg px-4 py-2.5 transition ${
                selectedIds.size > 0
                  ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
            >
              Build with {selectedIds.size} starred trip{selectedIds.size !== 1 ? 's' : ''} &rarr;
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
