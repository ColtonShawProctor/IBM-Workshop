import React, { useState, useMemo, useEffect } from 'react';
import type { GuidedCriteria, GuidedBuildResult } from '../lib/api';

interface BuildBidStepProps {
  bidPeriodId: string;
  selectedIds: string[];
  criteria: GuidedCriteria;
  buildResult: GuidedBuildResult | null;
  isBuilding: boolean;
  onBack: () => void;
  onStartOver: () => void;
}

const LAYER_STRATEGIES: Record<number, string> = {
  1: 'Dream Schedule',
  2: 'Your Picks',
  3: 'Generic Properties',
  4: 'Wider Pool',
  5: 'Broader',
  6: 'Broad Domestic',
  7: 'Safety Net',
};

const LAYER_DESCRIPTIONS: Record<number, string> = {
  1: 'Dream schedule from full pool',
  2: 'Your specific pairings',
  3: 'Building from generic pairings...',
  4: 'Waiting...',
  5: 'Waiting...',
  6: 'Waiting...',
  7: 'Waiting...',
};

function holdabilityColor(pct: number): string {
  if (pct >= 80) return 'text-green-600';
  if (pct >= 50) return 'text-yellow-600';
  return 'text-red-600';
}

function holdabilityBg(pct: number): string {
  if (pct >= 80) return 'bg-green-100 text-green-800';
  if (pct >= 50) return 'bg-yellow-100 text-yellow-800';
  return 'bg-red-100 text-red-800';
}

function poolHealthIcon(poolSize: number): React.ReactNode {
  if (poolSize >= 100) {
    return <span className="inline-block w-2 h-2 rounded-full bg-green-500" title="Healthy pool" />;
  }
  if (poolSize >= 30) {
    return <span className="inline-block w-2 h-2 rounded-full bg-yellow-500" title="Moderate pool" />;
  }
  return <span className="inline-block w-2 h-2 rounded-full bg-red-500" title="Small pool" />;
}

function formatCreditHours(hours: number): string {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

// --- Loading State Component ---

function LoadingState({ selectedCount }: { selectedCount: number }) {
  const [activeLayer, setActiveLayer] = useState(1);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveLayer((prev) => (prev >= 7 ? 1 : prev + 1));
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const layerLines = [
    { layer: 1, text: 'Dream schedule from full pool' },
    { layer: 2, text: `Your ${selectedCount} specific pairings` },
    { layer: 3, text: 'Building from generic pairings...' },
    { layer: 4, text: 'Waiting...' },
    { layer: 5, text: 'Waiting...' },
    { layer: 6, text: 'Waiting...' },
    { layer: 7, text: 'Waiting...' },
  ];

  return (
    <div className="max-w-lg mx-auto py-12 text-center">
      <div className="mb-8">
        <h2 className="text-xl font-bold text-gray-900 tracking-wide uppercase">
          Building Your Bid
        </h2>
        <p className="text-sm text-gray-500 mt-2">
          Optimizing 7 layers for maximum holdability
        </p>
      </div>

      {/* Animated progress bar */}
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-8">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-1000 ease-in-out"
          style={{ width: `${(activeLayer / 7) * 100}%` }}
        />
      </div>

      {/* Layer status lines */}
      <div className="space-y-3 text-left">
        {layerLines.map(({ layer, text }) => {
          const isActive = layer === activeLayer;
          const isDone = layer < activeLayer;

          return (
            <div
              key={layer}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
                isActive ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50 border border-transparent'
              }`}
            >
              {/* Status icon */}
              <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                {isDone ? (
                  <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : isActive ? (
                  <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <span className="w-2 h-2 rounded-full bg-gray-300" />
                )}
              </div>

              {/* Layer label */}
              <span
                className={`text-xs font-semibold w-6 ${
                  isActive ? 'text-blue-700' : isDone ? 'text-green-700' : 'text-gray-400'
                }`}
              >
                L{layer}
              </span>

              {/* Description */}
              <span
                className={`text-sm ${
                  isActive ? 'text-blue-800 font-medium' : isDone ? 'text-gray-600' : 'text-gray-400'
                }`}
              >
                {text}
              </span>
            </div>
          );
        })}
      </div>

      <p className="mt-8 text-xs text-gray-400">
        This takes about 30 seconds.
      </p>
    </div>
  );
}

// --- Print View Component ---

function PrintView({
  buildResult,
  criteria,
  selectedIds,
}: {
  buildResult: GuidedBuildResult;
  criteria: GuidedCriteria;
  selectedIds: string[];
}) {
  // Extract sequence numbers from entries for L2 display
  const l2SeqNumbers = buildResult.entries
    .filter((e) => (e as Record<string, unknown>).layer === 2)
    .map((e) => (e as Record<string, unknown>).seq_number)
    .filter(Boolean);

  const formatDaysOff = (days: number[]) =>
    days.length > 0 ? days.map((d) => `Day ${d}`).join(', ') : 'None specified';

  const formatTripLengths = (lengths: number[]) =>
    lengths.length > 0 ? lengths.map((l) => `${l}-day`).join(', ') : 'Any';

  const formatTime = (minutes: number | null) => {
    if (minutes === null) return 'Any';
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    const period = h >= 12 ? 'PM' : 'AM';
    const hour12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${hour12}:${m.toString().padStart(2, '0')} ${period}`;
  };

  return (
    <div className="print-view bg-white rounded-lg border border-gray-200 p-6">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-view, .print-view * { visibility: visible; }
          .print-view {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            border: none !important;
            box-shadow: none !important;
            padding: 20px !important;
          }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="text-center mb-6 pb-4 border-b-2 border-gray-900">
        <h1 className="text-2xl font-bold text-gray-900 tracking-wide uppercase">
          Your PBS Bid
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Bid ID: {buildResult.bid_id} | {buildResult.total_entries} total entries
        </p>
      </div>

      <div className="space-y-5">
        {/* Layer 1 */}
        <div className="border-l-4 border-blue-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 1: Dream Schedule</h3>
          <p className="text-sm text-gray-600 mt-1">
            This layer bids your ideal schedule from the entire pool. At fapbs.aa.com, create a new
            bid group with the following Pairing Tab properties:
          </p>
          <ul className="mt-2 text-sm text-gray-700 space-y-1 list-disc list-inside">
            <li>Trip length: {formatTripLengths(criteria.trip_lengths)}</li>
            {criteria.preferred_cities.length > 0 && (
              <li>Preferred cities: {criteria.preferred_cities.join(', ')}</li>
            )}
            {criteria.avoided_cities.length > 0 && (
              <li>Avoid cities: {criteria.avoided_cities.join(', ')}</li>
            )}
            <li>Report no earlier than: {formatTime(criteria.report_earliest_minutes)}</li>
            <li>Release no later than: {formatTime(criteria.release_latest_minutes)}</li>
            <li>Credit range: {formatCreditHours(criteria.credit_min_minutes / 60)} - {formatCreditHours(criteria.credit_max_minutes / 60)}</li>
            {criteria.days_off.length > 0 && <li>Days off: {formatDaysOff(criteria.days_off)}</li>}
            {criteria.avoid_redeyes && <li>Avoid red-eyes: Yes</li>}
          </ul>
        </div>

        {/* Layer 2 */}
        <div className="border-l-4 border-indigo-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 2: Your Picks</h3>
          <p className="text-sm text-gray-600 mt-1">
            Add these specific pairings by sequence number at fapbs.aa.com:
          </p>
          <p className="mt-2 text-sm font-mono bg-gray-50 rounded px-3 py-2 text-gray-800">
            {l2SeqNumbers.length > 0 ? l2SeqNumbers.join(', ') : `(${selectedIds.length} sequences selected)`}
          </p>
        </div>

        {/* Layer 3 */}
        <div className="border-l-4 border-purple-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 3: Generic Properties</h3>
          <p className="text-sm text-gray-600 mt-1">
            Set these PROPERTIES on the Pairing Tab to match similar pairings:
          </p>
          <ul className="mt-2 text-sm text-gray-700 space-y-1 list-disc list-inside">
            <li>Trip length: {formatTripLengths(criteria.trip_lengths)}</li>
            {criteria.preferred_cities.length > 0 && (
              <li>Cities: {criteria.preferred_cities.join(', ')}</li>
            )}
            <li>Credit range: {formatCreditHours(criteria.credit_min_minutes / 60)} - {formatCreditHours(criteria.credit_max_minutes / 60)}</li>
            {criteria.avoid_redeyes && <li>No red-eyes</li>}
          </ul>
        </div>

        {/* Layer 4 */}
        <div className="border-l-4 border-pink-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 4: Wider Pool</h3>
          <p className="text-sm text-gray-600 mt-1">
            Widen by adding more trip lengths. Remove the report/release time filters if set.
            Keep city preferences and credit range.
          </p>
        </div>

        {/* Layer 5 */}
        <div className="border-l-4 border-orange-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 5: Broader</h3>
          <p className="text-sm text-gray-600 mt-1">
            Widen by adding any trip length. Remove the city preference filter.
            Keep only the credit range and days-off constraints.
          </p>
        </div>

        {/* Layer 6 */}
        <div className="border-l-4 border-amber-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 6: Broad Domestic</h3>
          <p className="text-sm text-gray-600 mt-1">
            Remove the credit range filter. Keep only days-off if specified.
            This layer captures a wide domestic pool.
          </p>
        </div>

        {/* Layer 7 */}
        <div className="border-l-4 border-red-500 pl-4">
          <h3 className="text-sm font-bold text-gray-900">Layer 7: Safety Net</h3>
          <p className="text-sm text-gray-600 mt-1">
            Remove ALL filters. This is your safety net -- it bids on every available pairing so
            you are guaranteed an award rather than being assigned a reserve line.
          </p>
        </div>
      </div>

      <div className="mt-6 pt-4 border-t text-xs text-gray-400 text-center">
        Generated by PBS Optimizer | Enter layers top-to-bottom at fapbs.aa.com
      </div>

      <div className="mt-4 text-center no-print">
        <button
          type="button"
          onClick={() => window.print()}
          className="px-4 py-2 text-sm font-medium text-white bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
        >
          Print This Page
        </button>
      </div>
    </div>
  );
}

// --- Main Component ---

export default function BuildBidStep({
  bidPeriodId,
  selectedIds,
  criteria,
  buildResult,
  isBuilding,
  onBack,
  onStartOver,
}: BuildBidStepProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [showPrint, setShowPrint] = useState(false);

  // Find the most likely award layer: first layer with holdability >= 70%
  const likelyAwardLayer = useMemo(() => {
    if (!buildResult) return null;
    const sorted = [...buildResult.layer_summary].sort((a, b) => a.layer - b.layer);
    return sorted.find((l) => l.holdability_pct >= 70) ?? null;
  }, [buildResult]);

  // --- Loading / Building State ---
  if (isBuilding && !buildResult) {
    return (
      <div>
        <LoadingState selectedCount={selectedIds.length} />
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={onBack}
            className="text-sm text-gray-500 hover:text-gray-700 font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // --- No Result Yet (shouldn't happen normally) ---
  if (!buildResult) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Waiting for build to start...</p>
        <button
          type="button"
          onClick={onBack}
          className="mt-4 text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          Go Back
        </button>
      </div>
    );
  }

  // --- Results State ---
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="inline-flex items-center gap-2 mb-2">
          <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="text-xl font-bold text-gray-900 tracking-wide uppercase">
            Your Bid Is Ready
          </h2>
        </div>
        <p className="text-sm text-gray-500">
          Bid ID: <span className="font-mono text-gray-700">{buildResult.bid_id}</span>
          {' '} | {buildResult.total_entries} total entries across 7 layers
        </p>
      </div>

      {/* Layer Summary Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Layer
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Strategy
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Pool
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Credit
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Holdability
                </th>
              </tr>
            </thead>
            <tbody>
              {buildResult.layer_summary
                .slice()
                .sort((a, b) => a.layer - b.layer)
                .map((layer) => {
                  const isLikelyAward = likelyAwardLayer?.layer === layer.layer;

                  return (
                    <tr
                      key={layer.layer}
                      className={`border-b border-gray-100 ${
                        isLikelyAward ? 'bg-green-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
                            {layer.layer}
                          </span>
                          {isLikelyAward && (
                            <span className="text-xs bg-green-600 text-white px-1.5 py-0.5 rounded-full font-medium">
                              Likely
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-700 font-medium">
                        {LAYER_STRATEGIES[layer.layer] ?? `Layer ${layer.layer}`}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <span className="text-gray-700">{layer.pool_size.toLocaleString()}</span>
                          {poolHealthIcon(layer.pool_size)}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {formatCreditHours(layer.credit_hours)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${holdabilityBg(layer.holdability_pct)}`}
                        >
                          {layer.holdability_pct}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Most Likely Outcome */}
      {likelyAwardLayer && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-green-800">Most likely outcome</p>
              <p className="text-sm text-green-700 mt-0.5">
                You will most likely be awarded from{' '}
                <strong>Layer {likelyAwardLayer.layer} ({LAYER_STRATEGIES[likelyAwardLayer.layer]})</strong>{' '}
                with {likelyAwardLayer.holdability_pct}% holdability and{' '}
                {formatCreditHours(likelyAwardLayer.credit_hours)} credit.
              </p>
            </div>
          </div>
        </div>
      )}

      {!likelyAwardLayer && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-yellow-800">Low holdability across all layers</p>
              <p className="text-sm text-yellow-700 mt-0.5">
                No layer reached 70% holdability. Consider adjusting your criteria for better odds,
                or check your seniority settings.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => { setShowDetails(!showDetails); setShowPrint(false); }}
          className={`px-5 py-2.5 text-sm font-medium rounded-lg border transition-colors ${
            showDetails
              ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          }`}
        >
          {showDetails ? 'Hide Details' : 'View Details'}
        </button>

        <button
          type="button"
          onClick={() => { setShowPrint(!showPrint); setShowDetails(false); }}
          className={`px-5 py-2.5 text-sm font-medium rounded-lg border transition-colors ${
            showPrint
              ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          }`}
        >
          {showPrint ? 'Hide Print Guide' : 'Print Guide'}
        </button>

        <button
          type="button"
          onClick={onStartOver}
          className="px-5 py-2.5 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
        >
          Start Over
        </button>
      </div>

      {/* Detail View */}
      {showDetails && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Layer Details
          </h3>
          {buildResult.layer_summary
            .slice()
            .sort((a, b) => a.layer - b.layer)
            .map((layer) => (
              <div
                key={layer.layer}
                className="bg-white border border-gray-200 rounded-lg p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-7 h-7 rounded bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
                      {layer.layer}
                    </span>
                    <div>
                      <span className="text-sm font-semibold text-gray-900">
                        {LAYER_STRATEGIES[layer.layer] ?? `Layer ${layer.layer}`}
                      </span>
                    </div>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold ${holdabilityBg(layer.holdability_pct)}`}
                  >
                    {layer.holdability_pct}% holdable
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-4 pt-2 border-t border-gray-100">
                  <div>
                    <p className="text-xs text-gray-500">Sequences</p>
                    <p className="text-sm font-semibold text-gray-800">
                      {layer.sequences.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Pool Size</p>
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-semibold text-gray-800">
                        {layer.pool_size.toLocaleString()}
                      </p>
                      {poolHealthIcon(layer.pool_size)}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Credit Hours</p>
                    <p className="text-sm font-semibold text-gray-800">
                      {formatCreditHours(layer.credit_hours)}
                    </p>
                  </div>
                </div>

                {/* Holdability bar */}
                <div className="pt-1">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        layer.holdability_pct >= 80
                          ? 'bg-green-500'
                          : layer.holdability_pct >= 50
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(layer.holdability_pct, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Print View */}
      {showPrint && (
        <PrintView
          buildResult={buildResult}
          criteria={criteria}
          selectedIds={selectedIds}
        />
      )}
    </div>
  );
}
