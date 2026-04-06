import React, { useState, useMemo, useEffect } from 'react';
import type { GuidedCriteria, GuidedBuildResult, BuildEntry, BuildEntryDP } from '../lib/api';

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
  1: 'Best Domestic',
  2: 'Your Picks',
  3: 'Generic Match',
  4: 'Wider Pool',
  5: 'Broader',
  6: 'Broad Domestic',
  7: 'Safety Net',
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
  shiftLayers,
}: {
  buildResult: GuidedBuildResult;
  shiftLayers: boolean;
}) {
  const LAYER_COLORS = ['blue', 'indigo', 'purple', 'pink', 'orange', 'amber', 'red'];

  // Group entries by optimizer layer and extract seq numbers
  const seqsByLayer: Record<number, number[]> = {};
  for (const e of buildResult.entries) {
    const l = e.layer || 0;
    if (!seqsByLayer[l]) seqsByLayer[l] = [];
    if (e.seq_number && !seqsByLayer[l].includes(e.seq_number)) {
      seqsByLayer[l].push(e.seq_number);
    }
  }

  // Build the PBS layer list
  const pbsLayers: { pbsNum: number; optLayer: number | null; name: string; seqs: number[]; description: string }[] = [];

  if (shiftLayers) {
    pbsLayers.push({
      pbsNum: 1, optLayer: null,
      name: 'Your International Lottery',
      seqs: [],
      description: 'Enter your London/NRT/international trips manually at fapbs.aa.com.',
    });
    for (let i = 1; i <= 6; i++) {
      pbsLayers.push({
        pbsNum: i + 1, optLayer: i,
        name: LAYER_STRATEGIES[i] || `Layer ${i}`,
        seqs: seqsByLayer[i] || [],
        description: `Optimizer Layer ${i} sequences.`,
      });
    }
  } else {
    for (let i = 1; i <= 7; i++) {
      pbsLayers.push({
        pbsNum: i, optLayer: i,
        name: LAYER_STRATEGIES[i] || `Layer ${i}`,
        seqs: seqsByLayer[i] || [],
        description: `Optimizer Layer ${i} sequences.`,
      });
    }
  }

  return (
    <div className="print-view bg-white rounded-lg border border-gray-200 p-6">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-view, .print-view * { visibility: visible; }
          .print-view {
            position: absolute; left: 0; top: 0; width: 100%;
            border: none !important; box-shadow: none !important; padding: 20px !important;
          }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="text-center mb-6 pb-4 border-b-2 border-gray-900">
        <h1 className="text-2xl font-bold text-gray-900 tracking-wide uppercase">
          PBS Bid Instructions
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Enter these layers top-to-bottom at fapbs.aa.com
        </p>
        {shiftLayers && (
          <p className="text-xs text-purple-600 mt-1 font-medium">
            Layer 1 = your international lottery (entered manually) | Layers 2-7 = optimizer output
          </p>
        )}
      </div>

      <div className="space-y-4">
        {pbsLayers.map((pl, idx) => {
          const color = LAYER_COLORS[idx] || 'gray';
          const isManual = pl.optLayer === null;

          return (
            <div key={pl.pbsNum} className={`border-l-4 border-${color}-500 pl-4`} style={{ borderLeftColor: isManual ? '#9333ea' : undefined }}>
              <h3 className="text-sm font-bold text-gray-900">
                PBS Layer {pl.pbsNum}: {pl.name}
                {pl.optLayer && <span className="text-xs text-gray-400 font-normal ml-2">(optimizer L{pl.optLayer})</span>}
              </h3>
              {isManual ? (
                <p className="text-sm text-purple-700 mt-1 italic">{pl.description}</p>
              ) : pl.seqs.length > 0 ? (
                <div className="mt-1">
                  <p className="text-xs text-gray-500 mb-1">Add these sequences at fapbs.aa.com:</p>
                  <p className="text-sm font-mono bg-gray-50 rounded px-3 py-2 text-gray-800">
                    {pl.seqs.join(', ')}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-gray-500 mt-1">{pl.description}</p>
              )}
            </div>
          );
        })}
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

// --- Helper: format minutes to HH:MM ---

function fmtTime(hhmm: string | undefined): string {
  if (!hhmm) return '—';
  return hhmm;
}

function fmtMin(minutes: number): string {
  if (!minutes) return '0:00';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

// --- Trip Card Component ---

function TripCard({ entry }: { entry: BuildEntry }) {
  const [expanded, setExpanded] = useState(false);
  const t = entry.totals || {};
  const dps = entry.duty_periods || [];
  const cities = entry.layover_cities || [];
  const dd = t.duty_days || dps.length || 1;
  const tpay = t.tpay_minutes || 0;
  const block = t.block_minutes || 0;
  const tafb = t.tafb_minutes || 0;
  const cpd = dd > 0 ? tpay / dd : 0;
  const rpt = dps[0]?.report_base || '';
  const rls = dps[dps.length - 1]?.release_base || '';
  const chosenStart = entry.chosen_dates?.[0] || entry.operating_dates?.[0] || 0;
  const chosenEnd = chosenStart + dd - 1;

  return (
    <div className="border border-gray-100 rounded-lg bg-white">
      {/* Collapsed row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
      >
        <span className="text-xs text-gray-400 w-4 flex-shrink-0">{expanded ? '▾' : '▸'}</span>
        <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap text-sm">
          <span className="font-semibold text-gray-900">
            {cities.length > 0 ? cities.join('+') : 'Turn'} {dd}-Day
          </span>
          <span className="text-gray-600 font-medium">{fmtMin(tpay)}</span>
          <span className="text-xs text-gray-400">SEQ {entry.seq_number}</span>
          <span className="text-xs text-gray-500 ml-auto whitespace-nowrap">
            RPT {fmtTime(rpt)} &middot; RLS {fmtTime(rls)} &middot; Day {chosenStart}–{chosenEnd}
          </span>
        </div>
        <span className={`text-xs font-medium rounded-full px-2 py-0.5 flex-shrink-0 ${holdabilityBg(entry.holdability_pct)}`}>
          {entry.holdability_pct}%
        </span>
      </button>

      {/* Expanded duty-by-duty detail */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-gray-100">
          <div className="space-y-3">
            {dps.map((dp, i) => {
              const dpBlock = dp.legs.reduce((s, l) => s + (l.block_minutes || 0), 0);
              const legCount = dp.legs.length;
              const eqSet = [...new Set(dp.legs.map(l => l.equipment).filter(Boolean))];
              const dest = dp.legs[dp.legs.length - 1]?.destination || '';
              const origin = dp.legs[0]?.origin || '';
              const dayNum = chosenStart + i;

              return (
                <div key={i} className="text-sm">
                  <div className="flex items-center gap-2 font-medium text-gray-800">
                    <span className="text-xs bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">
                      Day {dayNum}
                    </span>
                    <span>{origin} → {dest}</span>
                  </div>
                  <div className="ml-6 mt-1 text-xs text-gray-500 space-y-0.5">
                    <p>
                      Report {fmtTime(dp.report_base)} &middot;{' '}
                      {legCount} leg{legCount !== 1 ? 's' : ''}
                      {legCount > 1 && ` (${dp.legs.map(l => `${l.origin}→${l.destination}`).join(', ')})`}
                      {eqSet.length > 0 && ` · ${eqSet.join(', ')}`}
                    </p>
                    <p>
                      Block: {fmtMin(dpBlock)} &middot; Duty: {fmtMin(dp.duty_minutes)}
                      {dp.release_base && ` · Release ${fmtTime(dp.release_base)}`}
                    </p>
                    {dp.layover && (
                      <p className="text-gray-600">
                        Layover: <span className="font-medium">{dp.layover.city}</span> — {fmtMin(dp.layover.rest_minutes)}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-2 border-t border-gray-100 text-xs text-gray-500 flex gap-4">
            <span>TAFB: {fmtMin(tafb)}</span>
            <span>Block: {fmtMin(block)}</span>
            <span>CPD: {fmtMin(Math.round(cpd))}/day</span>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Layer Detail View with expandable trips ---

function LayerDetailView({ buildResult }: { buildResult: GuidedBuildResult }) {
  const [expandedLayers, setExpandedLayers] = useState<Set<number>>(new Set([1, 2]));

  const toggleLayer = (n: number) => {
    setExpandedLayers(prev => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n); else next.add(n);
      return next;
    });
  };

  const entriesByLayer = useMemo(() => {
    const map = new Map<number, BuildEntry[]>();
    for (const e of buildResult.entries) {
      const layer = e.layer || 0;
      if (!map.has(layer)) map.set(layer, []);
      map.get(layer)!.push(e);
    }
    return map;
  }, [buildResult.entries]);

  return (
    <div className="space-y-3">
      {buildResult.layer_summary
        .slice()
        .sort((a, b) => a.layer - b.layer)
        .map((layer) => {
          const isOpen = expandedLayers.has(layer.layer);
          const layerEntries = entriesByLayer.get(layer.layer) || [];

          // Compute working days from chosen_dates
          const workDays = new Set<number>();
          for (const e of layerEntries) {
            const dd = e.totals?.duty_days || 1;
            const start = e.chosen_dates?.[0] || e.operating_dates?.[0] || 0;
            for (let d = start; d < start + dd; d++) workDays.add(d);
          }

          return (
            <div key={layer.layer} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {/* Layer header — clickable */}
              <button
                onClick={() => toggleLayer(layer.layer)}
                className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
              >
                <span className="w-7 h-7 rounded bg-blue-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {layer.layer}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-semibold text-gray-900">
                    {LAYER_STRATEGIES[layer.layer] ?? `Layer ${layer.layer}`}
                  </span>
                  <span className="text-xs text-gray-500 ml-2">
                    {layerEntries.length} trips &middot; {formatCreditHours(layer.credit_hours)} &middot;{' '}
                    {30 - workDays.size} days off
                  </span>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold flex-shrink-0 ${holdabilityBg(layer.holdability_pct)}`}>
                  {layer.holdability_pct}%
                </span>
                <span className="text-gray-400 text-xs flex-shrink-0">{isOpen ? '▾' : '▸'}</span>
              </button>

              {/* Expanded: mini calendar + trip cards */}
              {isOpen && (
                <div className="px-4 pb-4 border-t border-gray-100">
                  {/* Mini calendar */}
                  <div className="flex items-center gap-px py-3" aria-label="Calendar">
                    {Array.from({ length: 30 }, (_, i) => i + 1).map(d => (
                      <div
                        key={d}
                        className={`rounded-sm ${workDays.has(d) ? 'bg-blue-500' : 'bg-gray-200'}`}
                        style={{ width: '4px', height: '14px' }}
                        title={`Day ${d}: ${workDays.has(d) ? 'Working' : 'Off'}`}
                      />
                    ))}
                    <span className="ml-2 text-[10px] text-gray-400">{workDays.size} work / {30 - workDays.size} off</span>
                  </div>

                  {/* Trip cards */}
                  <div className="space-y-1">
                    {layerEntries
                      .sort((a, b) => a.rank - b.rank)
                      .map(entry => (
                        <TripCard key={entry.sequence_id + '-' + entry.layer} entry={entry} />
                      ))
                    }
                  </div>
                </div>
              )}
            </div>
          );
        })}
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
  const [shiftLayers, setShiftLayers] = useState(false); // true = "I'll enter my own L1"

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

      {/* PBS Layer Mapping Toggle */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-sm font-medium text-gray-700 mb-3">
          How are you using Layer 1 at fapbs.aa.com?
        </p>
        <div className="space-y-2">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="layerMapping"
              checked={!shiftLayers}
              onChange={() => setShiftLayers(false)}
              className="mt-0.5 text-blue-600"
            />
            <div>
              <span className="text-sm text-gray-800 font-medium">Use optimizer output as my PBS Layer 1</span>
              <span className="text-xs text-gray-500 block">Direct mapping — optimizer L1 = PBS L1</span>
            </div>
          </label>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="layerMapping"
              checked={shiftLayers}
              onChange={() => setShiftLayers(true)}
              className="mt-0.5 text-blue-600"
            />
            <div>
              <span className="text-sm text-gray-800 font-medium">I'll enter my own L1 (London/international)</span>
              <span className="text-xs text-gray-500 block">Shift optimizer layers to PBS L2–L7</span>
            </div>
          </label>
        </div>
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
              {/* If shifted, show the manual L1 row first */}
              {shiftLayers && (
                <tr className="border-b border-gray-100 bg-purple-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded bg-purple-600 text-white text-xs font-bold flex items-center justify-center">
                        1
                      </span>
                      <span className="text-xs text-purple-600 font-medium">PBS</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-purple-700 font-medium italic">
                    Your London/NRT trips (enter manually)
                  </td>
                  <td className="px-4 py-3 text-right text-purple-400">—</td>
                  <td className="px-4 py-3 text-right text-purple-400">—</td>
                  <td className="px-4 py-3 text-right text-purple-400">—</td>
                </tr>
              )}
              {buildResult.layer_summary
                .slice()
                .sort((a, b) => a.layer - b.layer)
                .filter((layer) => !shiftLayers || layer.layer <= 6) // drop L7 when shifted
                .map((layer) => {
                  const pbsLayer = shiftLayers ? layer.layer + 1 : layer.layer;
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
                            {pbsLayer}
                          </span>
                          {isLikelyAward && (
                            <span className="text-xs bg-green-600 text-white px-1.5 py-0.5 rounded-full font-medium">
                              Likely
                            </span>
                          )}
                          {shiftLayers && (
                            <span className="text-[10px] text-gray-400">opt L{layer.layer}</span>
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

      {/* Detail View — expandable layers with trip cards */}
      {showDetails && (
        <LayerDetailView buildResult={buildResult} />
      )}

      {/* Print View */}
      {showPrint && (
        <PrintView
          buildResult={buildResult}
          shiftLayers={shiftLayers}
        />
      )}
    </div>
  );
}
