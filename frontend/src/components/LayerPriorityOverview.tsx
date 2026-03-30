import { useState } from 'react';
import type { BidProperty, LayerSummary } from '../types/api';
import { NUM_LAYERS } from '../types/api';
import { LAYER_LABELS, LAYER_GROUPS } from '../types/templates';
import { PROPERTY_DEFINITIONS } from '../types/pbs-catalog';

interface Props {
  summaries: LayerSummary[];
  properties: BidProperty[];
  loading?: boolean;
  onReorderLayers?: (fromLayer: number, toLayer: number) => void;
}

export default function LayerPriorityOverview({ summaries, properties, loading, onReorderLayers }: Props) {
  const [expandedLayer, setExpandedLayer] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700">Layer Priority</h4>
        {loading && <span className="text-xs text-gray-400 animate-pulse">Updating...</span>}
      </div>

      <div className="space-y-4">
        {LAYER_GROUPS.map(group => {
          const groupLayers = group.layers;
          return (
            <div key={group.name}>
              {/* Group header */}
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm">{group.emoji}</span>
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{group.name}</span>
              </div>

              {/* Layer rows */}
              <div className="space-y-1.5">
                {groupLayers.map(layerNum => {
                  const label = LAYER_LABELS[layerNum];
                  const summary = summaries.find(s => s.layer_number === layerNum);
                  const total = summary?.total_pairings ?? 0;
                  const propCount = summary?.properties_count ?? 0;
                  const isExpanded = expandedLayer === layerNum;
                  const layerProps = properties.filter(p => p.layers.includes(layerNum) && p.is_enabled);

                  return (
                    <div key={layerNum}>
                      <button
                        type="button"
                        onClick={() => setExpandedLayer(isExpanded ? null : layerNum)}
                        className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
                          isExpanded
                            ? `border-gray-300 ${label.lightBg}`
                            : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          {/* Layer badge */}
                          <span className={`w-7 h-7 rounded-md text-white text-xs font-bold flex items-center justify-center flex-shrink-0 ${label.color}`}>
                            {layerNum}
                          </span>

                          {/* Label */}
                          <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-gray-800">
                              L{layerNum} <span className="text-gray-500 font-normal">{label.name}</span>
                            </span>
                          </div>

                          {/* Stats */}
                          <span className="text-xs text-gray-500 flex-shrink-0">
                            {propCount} prop{propCount !== 1 ? 's' : ''}
                          </span>
                          <span className="text-xs font-medium text-gray-700 flex-shrink-0 min-w-[70px] text-right">
                            {total.toLocaleString()} match
                          </span>

                          {/* Reorder buttons */}
                          {onReorderLayers && (
                            <div className="flex flex-col gap-0.5 flex-shrink-0">
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); if (layerNum > 1) onReorderLayers(layerNum, layerNum - 1); }}
                                disabled={layerNum === 1}
                                className="text-gray-300 hover:text-gray-600 disabled:opacity-20"
                                aria-label={`Move layer ${layerNum} up`}
                              >
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" /></svg>
                              </button>
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); if (layerNum < NUM_LAYERS) onReorderLayers(layerNum, layerNum + 1); }}
                                disabled={layerNum === NUM_LAYERS}
                                className="text-gray-300 hover:text-gray-600 disabled:opacity-20"
                                aria-label={`Move layer ${layerNum} down`}
                              >
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                              </button>
                            </div>
                          )}

                          {/* Expand arrow */}
                          <svg className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </button>

                      {/* Expanded detail */}
                      {isExpanded && (
                        <div className="ml-9 mt-1 mb-2 pl-3 border-l-2 border-gray-200 space-y-1">
                          {layerProps.length === 0 ? (
                            <p className="text-xs text-gray-400 py-1">No properties assigned to this layer</p>
                          ) : (
                            layerProps.map(prop => {
                              const defn = PROPERTY_DEFINITIONS.find(d => d.key === prop.property_key);
                              return (
                                <div key={prop.id} className="flex items-center gap-2 text-xs py-0.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-gray-300 flex-shrink-0" />
                                  <span className="text-gray-600">{defn?.label ?? prop.property_key}</span>
                                  <span className="text-gray-400 truncate">
                                    {formatPropValue(prop.value)}
                                  </span>
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatPropValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'On' : 'Off';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') return value;
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if ('start' in obj && 'end' in obj) {
      const s = obj.start as number;
      const e = obj.end as number;
      if (s > 24 || e > 24) {
        // Time in minutes
        return `${fmtTime(s)} - ${fmtTime(e)}`;
      }
      return `${s} - ${e}`;
    }
    if ('min' in obj && 'max' in obj) return `${obj.min} - ${obj.max}`;
  }
  return JSON.stringify(value);
}

function fmtTime(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
