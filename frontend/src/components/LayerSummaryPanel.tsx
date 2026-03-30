import type { LayerSummary } from '../types/api';
import { NUM_LAYERS } from '../types/api';
import { LAYER_LABELS, LAYER_GROUPS } from '../types/templates';

interface Props {
  summaries: LayerSummary[];
  totalSequences: number;
  selectedLayer: number | null;
  onSelectLayer: (layer: number) => void;
  onBrowsePairings?: (layer: number) => void;
  loading?: boolean;
}

export default function LayerSummaryPanel({
  summaries,
  totalSequences,
  selectedLayer,
  onSelectLayer,
  onBrowsePairings,
  loading,
}: Props) {
  const maxPairings = Math.max(totalSequences, ...summaries.map((s) => s.total_pairings), 1);

  return (
    <div className="border rounded-lg bg-white shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Layer Summary</h3>
        {loading && <span className="text-xs text-gray-400 animate-pulse">Updating...</span>}
      </div>

      <div className="space-y-4">
        {LAYER_GROUPS.map(group => (
          <div key={group.name}>
            {/* Group header */}
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-xs">{group.emoji}</span>
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{group.name}</span>
            </div>

            {/* Layer rows in this group */}
            <div className="space-y-1.5">
              {group.layers.map(layerNum => {
                const label = LAYER_LABELS[layerNum];
                const summary = summaries.find((s) => s.layer_number === layerNum);
                const total = summary?.total_pairings ?? 0;
                const byLayer = summary?.pairings_by_layer ?? 0;
                const propCount = summary?.properties_count ?? 0;
                const pct = maxPairings > 0 ? (total / maxPairings) * 100 : 0;
                const isSelected = selectedLayer === layerNum;

                return (
                  <button
                    key={layerNum}
                    type="button"
                    onClick={() => onSelectLayer(layerNum)}
                    className={`w-full text-left p-2 rounded-lg border transition-colors ${
                      isSelected
                        ? `border-gray-300 ${label.lightBg}`
                        : 'border-gray-100 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`w-6 h-6 rounded text-white text-xs font-bold flex items-center justify-center ${label.color}`}>
                        {layerNum}
                      </span>
                      <span className="text-xs text-gray-500 truncate">
                        {label.name} · {propCount} prop{propCount !== 1 ? 's' : ''}
                      </span>
                      <span className="ml-auto text-xs font-medium text-gray-700">
                        {total.toLocaleString()}
                      </span>
                      {byLayer > 0 && (
                        <span className="text-xs text-gray-400">
                          (+{byLayer.toLocaleString()})
                        </span>
                      )}
                    </div>
                    {/* Progress bar */}
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${label.color}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    {onBrowsePairings && (
                      <div className="mt-1 flex justify-end">
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onBrowsePairings(layerNum); }}
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                        >
                          Browse Pairings
                        </button>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 pt-3 border-t text-xs text-gray-400">
        <p><strong>Total</strong> = cumulative pairings through this layer</p>
        <p><strong>(+N)</strong> = new pairings unique to this layer</p>
        <p>Full package: {totalSequences.toLocaleString()} positions</p>
      </div>
    </div>
  );
}
