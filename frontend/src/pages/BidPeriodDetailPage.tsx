import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getBidPeriod, listBids, createBid, optimizeBid, exportBid,
  addBidProperty, updateBidProperty, deleteBidProperty, getLayerSummaries, getBid,
  updateTargetCredit, getProjectedSchedule,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import type { BidPeriod, Bid, BidEntry, BidProperty, LayerSummary, ProjectedScheduleResponse, ProjectedScheduleLayer } from '../types/api';
import { NUM_LAYERS } from '../types/api';
import PropertyCatalog from '../components/PropertyCatalog';
import LayerSummaryPanel from '../components/LayerSummaryPanel';
import LayerDetailView from '../components/LayerDetailView';
import StrategySelection from '../components/StrategySelection';
import PersonalizeYourBid from '../components/PersonalizeYourBid';
import type { BidTemplate } from '../types/templates';
import { LAYER_LABELS } from '../types/templates';

function fmt(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

// Group entries by their backend-assigned layer (supports both 7 and 9)
function buildLayers(entries: BidEntry[], maxLayers: number): BidEntry[][] {
  const layers: BidEntry[][] = Array.from({ length: maxLayers }, () => []);
  for (const entry of entries) {
    if (entry.is_excluded) continue;
    const idx = (entry.layer || 1) - 1;
    if (idx >= 0 && idx < maxLayers) {
      layers[idx].push(entry);
    }
  }
  return layers;
}

const STEP_LABELS = ['Configure Properties', 'Generate Bid', 'Review Results'];

export default function BidPeriodDetailPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  useAuth(); // ensure authenticated

  const [bp, setBp] = useState<BidPeriod | null>(null);
  const [bids, setBids] = useState<Bid[]>([]);
  const [activeBid, setActiveBid] = useState<Bid | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(0); // 0=configure, 1=generate, 2=results
  const [expandedLayer, setExpandedLayer] = useState<number | null>(0);

  // PBS Properties state
  const [properties, setProperties] = useState<BidProperty[]>([]);
  const [layerSummaries, setLayerSummaries] = useState<LayerSummary[]>([]);
  const [selectedLayer, setSelectedLayer] = useState<number | null>(null);
  const [layersLoading, setLayersLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Projected schedule state
  const [projectedSchedule, setProjectedSchedule] = useState<ProjectedScheduleResponse | null>(null);
  const [projectedLayer, setProjectedLayer] = useState(1);
  const [projectedLoading, setProjectedLoading] = useState(false);

  // Browse pairings state
  const [browsingLayer, setBrowsingLayer] = useState<number | null>(null);

  // Step 1 sub-tab state: 0=Strategy, 1=Personalize, 2=Fine-Tune
  const [subStep, setSubStep] = useState(0);
  const [activeTemplate, setActiveTemplate] = useState<BidTemplate | null>(null);
  const [templateKeys, setTemplateKeys] = useState<Set<string>>(new Set());

  // Confirmation dialog state (replaces window.confirm which can be suppressed)
  const [confirmDialog, setConfirmDialog] = useState<{
    message: string;
    onConfirm: () => void;
  } | null>(null);

  const refresh = useCallback(async () => {
    if (!bidPeriodId) return;
    try {
      const [bpData, bidsData] = await Promise.all([
        getBidPeriod(bidPeriodId),
        listBids(bidPeriodId).catch(() => ({ data: [] as Bid[] })),
      ]);
      setBp(bpData);
      setBids(bidsData.data);
      if (bidsData.data.length > 0) {
        const optimized = bidsData.data.find(b => b.status === 'optimized');
        const active = optimized || bidsData.data[0];
        setActiveBid(active);
        setProperties(active.properties || []);
        if (active.status === 'optimized') setStep(2);
      }
    } catch {
      setError('Failed to load bid period');
    } finally {
      setLoading(false);
    }
  }, [bidPeriodId]);

  useEffect(() => { refresh(); }, [refresh]);

  // Debounced layer summary refresh
  const refreshLayerSummaries = useCallback(async () => {
    if (!bidPeriodId || !activeBid) return;
    setLayersLoading(true);
    try {
      const summaries = await getLayerSummaries(bidPeriodId, activeBid.id);
      setLayerSummaries(summaries);
    } catch { /* ignore */ }
    finally { setLayersLoading(false); }
  }, [bidPeriodId, activeBid]);

  const triggerLayerRefresh = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(refreshLayerSummaries, 500);
  }, [refreshLayerSummaries]);

  useEffect(() => {
    if (activeBid && step === 0) refreshLayerSummaries();
  }, [activeBid, step, refreshLayerSummaries]);

  // Fetch projected schedule when results are shown
  useEffect(() => {
    if (step === 2 && activeBid && bidPeriodId && activeBid.status === 'optimized') {
      setProjectedLoading(true);
      getProjectedSchedule(bidPeriodId, activeBid.id)
        .then(setProjectedSchedule)
        .catch(() => setProjectedSchedule(null))
        .finally(() => setProjectedLoading(false));
    }
  }, [step, activeBid, bidPeriodId]);

  // Ensure a bid exists for property CRUD
  const ensureBid = async (): Promise<string> => {
    if (activeBid) return activeBid.id;
    if (!bidPeriodId) throw new Error('No bid period');
    const bidName = `Bid ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`;
    const newBid = await createBid(bidPeriodId, bidName);
    setActiveBid(newBid);
    setBids(prev => [newBid, ...prev]);
    return newBid.id;
  };

  const handleAddProperty = async (propertyKey: string, value: unknown) => {
    try {
      const bidId = await ensureBid();
      const prop = await addBidProperty(bidPeriodId!, bidId, {
        property_key: propertyKey, value, layers: [1], is_enabled: true,
      });
      setProperties(prev => [...prev, prop]);
      triggerLayerRefresh();
    } catch { setError('Failed to add property'); }
  };

  const handleUpdateProperty = async (propertyId: string, updates: Partial<BidProperty>) => {
    if (!bidPeriodId || !activeBid) return;
    const current = properties.find(p => p.id === propertyId);
    if (!current) return;
    try {
      const updated = await updateBidProperty(bidPeriodId, activeBid.id, propertyId, {
        property_key: current.property_key,
        value: updates.value !== undefined ? updates.value : current.value,
        layers: updates.layers || current.layers,
        is_enabled: updates.is_enabled !== undefined ? updates.is_enabled : current.is_enabled,
      });
      setProperties(prev => prev.map(p => p.id === propertyId ? updated : p));
      triggerLayerRefresh();
    } catch { setError('Failed to update property'); }
  };

  const handleRemoveProperty = async (propertyId: string) => {
    if (!bidPeriodId || !activeBid) return;
    try {
      await deleteBidProperty(bidPeriodId, activeBid.id, propertyId);
      setProperties(prev => prev.filter(p => p.id !== propertyId));
      triggerLayerRefresh();
    } catch { setError('Failed to remove property'); }
  };

  const handleGenerate = async () => {
    if (!bidPeriodId) return;
    setGenerating(true);
    setError('');
    try {
      const bidId = await ensureBid();
      const optimized = await optimizeBid(bidPeriodId, bidId);
      setActiveBid(optimized);
      setBids(prev => prev.map(b => b.id === optimized.id ? optimized : b));
      setStep(2);
      setExpandedLayer(0);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to generate bid');
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async (format: 'txt' | 'csv') => {
    if (!bidPeriodId || !activeBid) return;
    try {
      const blob = await exportBid(bidPeriodId, activeBid.id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bid-export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { setError('Export failed'); }
  };

  // Clear all existing properties from the active bid
  const clearAllProperties = async () => {
    if (!bidPeriodId || !activeBid) return;
    const toRemove = [...properties];
    for (const prop of toRemove) {
      try {
        await deleteBidProperty(bidPeriodId, activeBid.id, prop.id);
      } catch { /* ignore */ }
    }
    setProperties([]);
  };

  const applyTemplate = async (template: BidTemplate) => {
    setActiveTemplate(template);
    const keys = new Set(template.propertyDefaults.map(d => d.property_key));
    setTemplateKeys(keys);

    // Clear existing properties first
    await clearAllProperties();

    // Apply template defaults as properties
    const bidId = await ensureBid();
    for (const def of template.propertyDefaults) {
      try {
        await addBidProperty(bidPeriodId!, bidId, {
          property_key: def.property_key,
          value: def.value,
          layers: def.layers,
          is_enabled: true,
        });
      } catch { /* ignore */ }
    }

    // Refresh properties from server
    try {
      const freshBid = await getBid(bidPeriodId!, bidId);
      setProperties(freshBid.properties || []);
    } catch { /* ignore */ }

    triggerLayerRefresh();
    setSubStep(1); // Auto-advance to Personalize
  };

  const handleSelectTemplate = (template: BidTemplate) => {
    if (properties.length > 0) {
      setConfirmDialog({
        message: `Switching to "${template.name}" will replace your current ${properties.length} properties. Continue?`,
        onConfirm: () => {
          setConfirmDialog(null);
          applyTemplate(template);
        },
      });
      return;
    }
    applyTemplate(template);
  };

  const handleStartFromScratch = () => {
    const doScratch = async () => {
      await clearAllProperties();
      setActiveTemplate(null);
      setTemplateKeys(new Set());
      triggerLayerRefresh();
      setSubStep(2); // Go directly to Fine-Tune
    };

    if (properties.length > 0) {
      setConfirmDialog({
        message: `This will clear all ${properties.length} configured properties. Continue?`,
        onConfirm: () => {
          setConfirmDialog(null);
          doScratch();
        },
      });
      return;
    }
    doScratch();
  };

  const handleCopyLayer = (layerEntries: BidEntry[]) => {
    const text = layerEntries.map(e => `SEQ ${e.seq_number}`).join('\n');
    navigator.clipboard.writeText(text);
  };

  if (loading) return <p className="text-sm text-gray-500 p-4">Loading...</p>;
  if (!bp) return <p className="text-sm text-red-600 p-4">Bid period not found.</p>;

  const isCompleted = bp.parse_status === 'completed';
  const maxLayer = activeBid ? Math.max(...activeBid.entries.map(e => e.layer || 1), NUM_LAYERS) : NUM_LAYERS;
  const numLayers = maxLayer <= NUM_LAYERS ? NUM_LAYERS : 9;
  const layers = activeBid ? buildLayers(activeBid.entries, numLayers) : [];
  const coverage = activeBid?.summary?.date_coverage;

  const attColors: Record<string, string> = {
    high: 'text-green-600', medium: 'text-yellow-600', low: 'text-red-500', unknown: 'text-gray-400',
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Confirmation Dialog */}
      {confirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl max-w-sm w-full mx-4 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-gray-900">Confirm</h3>
            <p className="text-sm text-gray-600">{confirmDialog.message}</p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDialog(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDialog.onConfirm}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div>
        <Link to="/bid-periods" className="text-sm text-blue-600 hover:underline">&larr; All Bid Periods</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">{bp.name}</h1>
        <p className="text-sm text-gray-500">
          {bp.effective_start} to {bp.effective_end} &middot; {bp.base_city} &middot; {bp.total_sequences} sequences
        </p>
      </div>

      {bp.parse_status === 'processing' && (
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-4 text-sm text-yellow-700">Parsing bid sheet... Refresh to check status.</div>
      )}
      {bp.parse_status === 'failed' && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">Parse failed: {bp.parse_error}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          {error} <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {isCompleted && (
        <>
          {/* Quick nav */}
          <div className="flex gap-3 text-sm">
            <Link to={`/bid-periods/${bp.id}/sequences`}
              className="rounded-md border border-gray-200 bg-white px-4 py-2 hover:border-blue-300 transition-colors">
              Browse {bp.total_sequences} Sequences
            </Link>
            <Link to={`/bid-periods/${bp.id}/calendar`}
              className="rounded-md border border-gray-200 bg-white px-4 py-2 hover:border-blue-300 transition-colors">
              Calendar ({bp.total_dates} days)
            </Link>
            {activeBid && (
              <Link to={`/bid-periods/${bp.id}/bids`}
                className="rounded-md border border-gray-200 bg-white px-4 py-2 hover:border-blue-300 transition-colors">
                Advanced Editor
              </Link>
            )}
          </div>

          {/* Step indicator */}
          <div className="flex items-center gap-2">
            {STEP_LABELS.map((label, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  step === i
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                  step === i ? 'bg-white text-blue-600' : 'bg-gray-300 text-white'
                }`}>{i + 1}</span>
                {label}
              </button>
            ))}
          </div>

          {/* ── STEP 1: CONFIGURE PROPERTIES ── */}
          {step === 0 && (
            <div className="space-y-4">
              {/* Target Credit Range — from the bid package */}
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">Target Credit Range</h3>
                    <p className="text-xs text-gray-500">From the bid package — the airline's min/max credit hours for this month</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={Math.floor((bp.target_credit_min_minutes || 4200) / 60)}
                      onChange={async (e) => {
                        const hours = parseInt(e.target.value) || 70;
                        const newMin = hours * 60;
                        try {
                          const updated = await updateTargetCredit(bp.id, newMin, bp.target_credit_max_minutes || 5400);
                          setBp(updated);
                        } catch { /* ignore */ }
                      }}
                      className="border rounded px-2 py-1 w-20 text-sm text-center"
                      min={30} max={120}
                    />
                    <span className="text-sm text-gray-500">to</span>
                    <input
                      type="number"
                      value={Math.floor((bp.target_credit_max_minutes || 5400) / 60)}
                      onChange={async (e) => {
                        const hours = parseInt(e.target.value) || 90;
                        const newMax = hours * 60;
                        try {
                          const updated = await updateTargetCredit(bp.id, bp.target_credit_min_minutes || 4200, newMax);
                          setBp(updated);
                        } catch { /* ignore */ }
                      }}
                      className="border rounded px-2 py-1 w-20 text-sm text-center"
                      min={30} max={120}
                    />
                    <span className="text-sm text-gray-500">hours</span>
                  </div>
                </div>
              </div>

              {/* Sub-step tabs within Step 1 */}
              <div className="flex items-center gap-1 border-b border-gray-200">
                {[
                  { id: 0, label: 'Strategy', icon: '🎯' },
                  { id: 1, label: 'Personalize', icon: '🔧' },
                  { id: 2, label: 'Fine-Tune', icon: '⚙️' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setSubStep(tab.id)}
                    className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                      subStep === tab.id
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <span className="text-base">{tab.icon}</span>
                    {tab.label}
                    {tab.id === 2 && properties.length > 0 && (
                      <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
                        {properties.filter(p => p.is_enabled).length}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Sub-step 1a: Strategy Selection */}
              {subStep === 0 && (
                <StrategySelection
                  onSelectTemplate={handleSelectTemplate}
                  onStartFromScratch={handleStartFromScratch}
                />
              )}

              {/* Sub-step 1b: Personalize Your Bid */}
              {subStep === 1 && (
                <PersonalizeYourBid
                  bidPeriod={bp}
                  properties={properties}
                  layerSummaries={layerSummaries}
                  layersLoading={layersLoading}
                  onAddProperty={handleAddProperty}
                  onUpdateProperty={handleUpdateProperty}
                  onRemoveProperty={handleRemoveProperty}
                  favoritePropertyKeys={activeTemplate?.favoriteProperties}
                />
              )}

              {/* Sub-step 1c: Fine-Tune */}
              {subStep === 2 && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-2">
                    <PropertyCatalog
                      properties={properties}
                      onAdd={handleAddProperty}
                      onUpdate={handleUpdateProperty}
                      onRemove={handleRemoveProperty}
                      templateKeys={templateKeys}
                      favoriteKeys={activeTemplate?.favoriteProperties}
                    />
                  </div>
                  <div className="space-y-4">
                    <LayerSummaryPanel
                      summaries={layerSummaries}
                      totalSequences={bp.total_sequences}
                      selectedLayer={selectedLayer}
                      onSelectLayer={setSelectedLayer}
                      onBrowsePairings={(layer) => setBrowsingLayer(browsingLayer === layer ? null : layer)}
                      loading={layersLoading}
                    />
                    {browsingLayer && (() => {
                      const summary = layerSummaries.find(s => s.layer_number === browsingLayer);
                      const lbl = LAYER_LABELS[browsingLayer];
                      const layerProps = properties.filter(p => p.layers.includes(browsingLayer) && p.is_enabled && p.category === 'pairing');
                      return (
                        <div className="border rounded-lg bg-white shadow-sm p-4">
                          <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-semibold text-gray-700">
                              L{browsingLayer} {lbl?.name} Pairings
                            </h3>
                            <button onClick={() => setBrowsingLayer(null)} className="text-gray-400 hover:text-gray-600 text-sm">Close</button>
                          </div>
                          <div className="space-y-2 text-sm">
                            <p className="text-gray-700">
                              <span className="font-medium">{summary?.total_pairings ?? 0}</span> sequences match this layer
                              {summary?.pairings_by_layer ? ` (${summary.pairings_by_layer} unique to layer ${browsingLayer})` : ''}
                            </p>
                            {layerProps.length > 0 ? (
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Active pairing filters:</p>
                                <ul className="text-xs text-gray-600 space-y-0.5">
                                  {layerProps.map(p => (
                                    <li key={p.id} className="flex items-center gap-1">
                                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
                                      {p.property_key.replace(/_/g, ' ')}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            ) : (
                              <p className="text-xs text-gray-400">No pairing filters -- all {bp.total_sequences} sequences available.</p>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                    {selectedLayer && (
                      <LayerDetailView
                        layerNumber={selectedLayer}
                        properties={properties}
                        onClose={() => setSelectedLayer(null)}
                      />
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── STEP 2: GENERATE BID ── */}
          {step === 1 && (
            <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">Generate {numLayers}-Layer Bid</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-gray-900">{properties.filter(p => p.is_enabled).length}</p>
                  <p className="text-xs text-gray-500">Active Properties</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-gray-900">{properties.filter(p => p.category === 'pairing').length}</p>
                  <p className="text-xs text-gray-500">Pairing Filters</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-gray-900">{properties.filter(p => p.category === 'days_off').length}</p>
                  <p className="text-xs text-gray-500">Days Off Rules</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-gray-900">{properties.filter(p => p.category === 'line').length}</p>
                  <p className="text-xs text-gray-500">Line Rules</p>
                </div>
              </div>

              {properties.length === 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-700">
                  No properties configured. The optimizer will use default scoring. Go back to Step 1 to add PBS properties for better results.
                </div>
              )}

              <div className="flex items-center gap-3">
                <button onClick={handleGenerate} disabled={generating}
                  className="rounded-md bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 shadow-sm">
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                      Analyzing {bp.total_sequences} sequences...
                    </span>
                  ) : 'Generate Optimized Layers'}
                </button>
                <button onClick={() => handleExport('txt')} disabled={!activeBid}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-30">
                  Export TXT
                </button>
                <button onClick={() => handleExport('csv')} disabled={!activeBid}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-30">
                  Export CSV
                </button>
              </div>

              {bids.length > 1 && (
                <div className="flex items-center gap-2 flex-wrap pt-3 border-t border-gray-100">
                  <span className="text-xs text-gray-500">Previous bids:</span>
                  {bids.map(b => (
                    <button key={b.id} onClick={async () => {
                      const full = await getBid(bidPeriodId!, b.id);
                      setActiveBid(full);
                      setProperties(full.properties || []);
                      if (full.status === 'optimized') setStep(2);
                    }}
                      className={`rounded-full px-3 py-0.5 text-xs transition-colors ${
                        activeBid?.id === b.id ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}>
                      {b.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── STEP 3: RESULTS ── */}
          {step === 2 && activeBid && activeBid.entries.filter(e => !e.is_excluded).length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-gray-900">Your {numLayers}-Layer Bid</h2>

              {/* Summary bar */}
              {activeBid.summary && (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{activeBid.summary.total_entries}</p>
                      <p className="text-xs text-gray-500">Sequences Ranked</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{fmt(activeBid.summary.total_tpay_minutes)}</p>
                      <p className="text-xs text-gray-500">Total TPAY</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{activeBid.summary.total_days_off}</p>
                      <p className="text-xs text-gray-500">Days Off</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{activeBid.summary.conflict_groups}</p>
                      <p className="text-xs text-gray-500">Conflict Groups</p>
                    </div>
                    <div>
                      <p className={`text-2xl font-bold ${
                        (coverage?.coverage_rate || 0) >= 0.9 ? 'text-green-600' :
                        (coverage?.coverage_rate || 0) >= 0.7 ? 'text-yellow-600' : 'text-red-600'
                      }`}>{Math.round((coverage?.coverage_rate || 0) * 100)}%</p>
                      <p className="text-xs text-gray-500">Date Coverage</p>
                    </div>
                  </div>
                  {activeBid.summary.commute_warnings && activeBid.summary.commute_warnings.length > 0 && (
                    <div className="mt-3 border-t border-gray-100 pt-3">
                      <p className="text-xs font-medium text-amber-700 mb-1">Commute Warnings</p>
                      <ul className="space-y-0.5">
                        {activeBid.summary.commute_warnings.map((w, i) => (
                          <li key={i} className="text-xs text-amber-600 flex items-start gap-1">
                            <span className="mt-0.5 inline-block w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                            {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Projected Schedule */}
              {projectedLoading && (
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm text-gray-500 animate-pulse">Loading projected schedule...</div>
              )}
              {projectedSchedule && projectedSchedule.layers.length > 0 && (() => {
                const pl: ProjectedScheduleLayer | undefined = projectedSchedule.layers.find(l => l.layer_number === projectedLayer);
                return (
                  <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-700">Projected Schedule</h3>
                      <div className="flex gap-1">
                        {projectedSchedule.layers.map(l => (
                          <button
                            key={l.layer_number}
                            onClick={() => setProjectedLayer(l.layer_number)}
                            className={`w-8 h-8 text-xs rounded font-medium transition-colors ${
                              projectedLayer === l.layer_number
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                          >
                            L{l.layer_number}
                          </button>
                        ))}
                      </div>
                    </div>
                    {pl && (
                      <>
                        <div className="flex items-center gap-4 text-sm">
                          <span className={`font-medium ${pl.within_credit_range ? 'text-green-600' : 'text-amber-600'}`}>
                            {pl.sequences.length} trips, {pl.total_credit_hours.toFixed(1)} credit hours, {pl.total_days_off} days off
                          </span>
                          {!pl.within_credit_range && (
                            <span className="text-xs text-amber-500">Outside credit range</span>
                          )}
                          {pl.schedule_shape && (
                            <span className="text-xs text-gray-400">{pl.schedule_shape}</span>
                          )}
                        </div>
                        {/* Mini calendar: working vs off days */}
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Working / Off Days</p>
                          <div className="flex flex-wrap gap-1">
                            {[...pl.working_dates, ...pl.off_dates].sort((a, b) => a - b).map(d => {
                              const isWorking = pl.working_dates.includes(d);
                              return (
                                <span
                                  key={d}
                                  className={`inline-flex items-center justify-center w-7 h-7 text-xs rounded ${
                                    isWorking ? 'bg-blue-100 text-blue-700 font-medium' : 'bg-gray-50 text-gray-400'
                                  }`}
                                  title={isWorking ? `Day ${d} - Working` : `Day ${d} - Off`}
                                >
                                  {d}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                        {/* Credit hour indicator */}
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Credit Hours: {pl.total_credit_hours.toFixed(1)}h</p>
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${pl.within_credit_range ? 'bg-green-500' : 'bg-amber-500'}`}
                              style={{ width: `${Math.min(100, (pl.total_credit_hours / 100) * 100)}%` }}
                            />
                          </div>
                        </div>
                        {/* Projected sequences */}
                        {pl.sequences.length > 0 && (
                          <div>
                            <p className="text-xs text-gray-500 mb-1">Projected Sequences</p>
                            <div className="space-y-1">
                              {pl.sequences.map(s => (
                                <div key={s.seq_number} className="flex items-center gap-3 px-2 py-1 bg-gray-50 rounded text-sm">
                                  <span className="font-semibold text-gray-900">SEQ {s.seq_number}</span>
                                  <span className="text-xs text-gray-500">{s.category}</span>
                                  <span className="text-xs text-gray-500">{fmt(s.tpay_minutes)} TPAY</span>
                                  <span className="text-xs text-gray-400">{s.duty_days}d</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                );
              })()}

              {/* Layer cards */}
              <div className="space-y-2">
                {layers.map((layerEntries, i) => {
                  const isExpanded = expandedLayer === i;
                  const hasEntries = layerEntries.length > 0;
                  const avgScore = hasEntries
                    ? Math.round((layerEntries.reduce((s, e) => s + e.preference_score, 0) / layerEntries.length) * 100)
                    : 0;

                  // Build layer description from properties
                  const layerProps = properties.filter(p => p.layers.includes(i + 1) && p.is_enabled && p.category === 'pairing');
                  const layerDesc = layerProps.length > 0
                    ? layerProps.slice(0, 3).map(p => p.property_key.replace(/_/g, ' ')).join(', ')
                    : 'All pairings';

                  return (
                    <div key={i} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                      <button onClick={() => setExpandedLayer(isExpanded ? null : i)} disabled={!hasEntries}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${hasEntries ? 'hover:bg-gray-50' : 'opacity-40'}`}>
                        <span className={`flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold text-white ${
                          LAYER_LABELS[i + 1]?.color ?? 'bg-gray-400'
                        }`}>L{i + 1}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-gray-900">
                              Layer {i + 1} <span className="text-gray-400 font-normal">{LAYER_LABELS[i + 1]?.name}</span>
                            </span>
                            <span className="text-xs text-gray-400">{layerEntries.length} sequences</span>
                          </div>
                          <p className="text-xs text-gray-500 truncate">{layerDesc}</p>
                        </div>
                        {hasEntries && <span className="text-xs text-gray-500">Avg: {avgScore}%</span>}
                        {hasEntries && (
                          <svg className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        )}
                      </button>

                      {isExpanded && hasEntries && (
                        <div className="border-t border-gray-100">
                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                            <span className="text-xs text-gray-500">Enter in Layer {i + 1} of fapbs.aa.com</span>
                            <button onClick={() => handleCopyLayer(layerEntries)} className="text-xs text-blue-600 hover:text-blue-800 font-medium">Copy to clipboard</button>
                          </div>
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                                <th className="px-4 py-2 text-left font-medium w-16">#</th>
                                <th className="px-4 py-2 text-left font-medium">Sequence</th>
                                <th className="px-4 py-2 text-left font-medium">TPAY</th>
                                <th className="px-4 py-2 text-left font-medium hidden sm:table-cell">Layovers</th>
                                <th className="px-4 py-2 text-left font-medium">Match</th>
                                <th className="px-4 py-2 text-left font-medium">Chances</th>
                              </tr>
                            </thead>
                            <tbody>
                              {layerEntries.map((entry) => {
                                const pct = Math.round(entry.preference_score * 100);
                                const tpayMatch = entry.rationale?.match(/TPAY\s([\d:]+)/);
                                const layoverMatch = entry.rationale?.match(/layover[s]?:?\s*([^;]+)/i);
                                return (
                                  <tr key={entry.sequence_id} className="border-b border-gray-50 hover:bg-blue-50/30">
                                    <td className="px-4 py-2 text-gray-400 font-medium">{entry.rank}</td>
                                    <td className="px-4 py-2">
                                      <span className="font-semibold text-gray-900">SEQ {entry.seq_number}</span>
                                      {entry.commute_impact && (
                                        <span
                                          className={`inline-block w-2 h-2 rounded-full ml-1.5 align-middle ${
                                            entry.commute_impact.impact_level === 'green' ? 'bg-green-500' :
                                            entry.commute_impact.impact_level === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'
                                          }`}
                                          title={[entry.commute_impact.first_day_note, entry.commute_impact.last_day_note].filter(Boolean).join(' | ')}
                                        />
                                      )}
                                    </td>
                                    <td className="px-4 py-2 text-gray-600">{tpayMatch ? tpayMatch[1] : '—'}</td>
                                    <td className="px-4 py-2 text-gray-600 hidden sm:table-cell truncate max-w-[200px]">{layoverMatch ? layoverMatch[1].trim() : '—'}</td>
                                    <td className="px-4 py-2">
                                      <div className="flex items-center gap-1.5">
                                        <div className="h-1.5 w-10 rounded-full bg-gray-200">
                                          <div className={`h-1.5 rounded-full ${pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-400'}`} style={{ width: `${pct}%` }} />
                                        </div>
                                        <span className="text-xs text-gray-500 w-8">{pct}%</span>
                                      </div>
                                    </td>
                                    <td className={`px-4 py-2 text-xs font-medium capitalize ${attColors[entry.attainability] || 'text-gray-400'}`}>{entry.attainability}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Portal instructions */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-medium text-blue-900">How to submit at fapbs.aa.com</p>
                <ol className="text-sm text-blue-800 mt-2 space-y-1 list-decimal ml-4">
                  <li>Open each layer above and click "Copy to clipboard"</li>
                  <li>Go to fapbs.aa.com and navigate to the Pairing tab</li>
                  <li>Paste the sequence numbers into the corresponding layer (1-{numLayers})</li>
                  <li>Review the Layer tab to verify pairing counts</li>
                  <li>Submit your bid before the deadline</li>
                </ol>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
