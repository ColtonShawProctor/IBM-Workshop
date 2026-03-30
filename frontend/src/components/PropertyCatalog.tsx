import { useState, useMemo } from 'react';
import type { BidProperty } from '../types/api';
import { PROPERTY_DEFINITIONS } from '../types/pbs-catalog';
import { NUM_LAYERS } from '../types/api';
import { INTENT_PROPERTY_GROUPS } from '../types/templates';
import { LAYER_LABELS } from '../types/templates';
import PropertyValueEditor from './PropertyValueEditor';

interface Props {
  properties: BidProperty[];
  onAdd: (propertyKey: string, value: unknown) => void;
  onUpdate: (propertyId: string, updates: Partial<BidProperty>) => void;
  onRemove: (propertyId: string) => void;
  /** Keys set by a template — shown with a badge */
  templateKeys?: Set<string>;
  /** Template-driven favorite keys to show at top */
  favoriteKeys?: string[];
}

export default function PropertyCatalog({ properties, onAdd, onUpdate, onRemove, templateKeys, favoriteKeys }: Props) {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['schedule_shape', 'trip_preferences']));
  const [showAdd, setShowAdd] = useState<string | null>(null); // group id or 'favorites'

  const usedKeys = new Set(properties.map(p => p.property_key));

  // Fuzzy search across all property definitions (including aliases)
  const filteredDefns = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const q = searchQuery.toLowerCase();
    return PROPERTY_DEFINITIONS.filter(d =>
      d.label.toLowerCase().includes(q) ||
      d.key.toLowerCase().includes(q) ||
      d.category.toLowerCase().includes(q) ||
      d.aliases?.some(a => a.toLowerCase().includes(q))
    );
  }, [searchQuery]);

  const toggleGroup = (groupId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  // Template-driven favorites (or default)
  const favKeys = favoriteKeys ?? [
    'report_between', 'release_between', 'prefer_pairing_type',
    'prefer_pairing_length', 'maximize_credit', 'layover_at_city',
  ];
  const favoriteDefns = favKeys
    .map(k => PROPERTY_DEFINITIONS.find(d => d.key === k))
    .filter(Boolean) as typeof PROPERTY_DEFINITIONS;

  const activeFavorites = properties.filter(p => favKeys.includes(p.property_key));
  const availableFavorites = favoriteDefns.filter(d => !usedKeys.has(d.key));

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search properties... (e.g. 'credit', 'layover', 'report')"
          className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-400 outline-none"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        )}
      </div>

      {/* Search results */}
      {filteredDefns && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
          <p className="text-xs text-gray-500">{filteredDefns.length} properties match "{searchQuery}"</p>
          {filteredDefns.length === 0 && (
            <p className="text-sm text-gray-400">No properties found. Try a different search term.</p>
          )}
          {filteredDefns.map(defn => {
            const existing = properties.find(p => p.property_key === defn.key);
            return (
              <div key={defn.key} className="flex items-center gap-2 py-1">
                {existing ? (
                  <PropertyRow
                    property={existing}
                    defn={defn}
                    onUpdate={onUpdate}
                    onRemove={onRemove}
                    isTemplate={templateKeys?.has(defn.key)}
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => onAdd(defn.key, null)}
                    className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 py-1"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                    {defn.label}
                    <span className="text-xs text-gray-400">({defn.category})</span>
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Normal view (when not searching) */}
      {!filteredDefns && (
        <>
          {/* Favorites section */}
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
              <h4 className="text-sm font-semibold text-gray-700">Quick Access</h4>
              <p className="text-xs text-gray-400">Most commonly adjusted properties for your strategy</p>
            </div>
            <div className="p-4 space-y-2">
              {activeFavorites.map(prop => {
                const defn = PROPERTY_DEFINITIONS.find(d => d.key === prop.property_key);
                if (!defn) return null;
                return (
                  <PropertyRow
                    key={prop.id}
                    property={prop}
                    defn={defn}
                    onUpdate={onUpdate}
                    onRemove={onRemove}
                    isTemplate={templateKeys?.has(defn.key)}
                  />
                );
              })}
              {availableFavorites.length > 0 && (
                <div className="pt-2 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={() => setShowAdd(showAdd === 'favorites' ? null : 'favorites')}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {showAdd === 'favorites' ? '- Hide' : '+ Add quick access property'}
                  </button>
                  {showAdd === 'favorites' && (
                    <div className="mt-2 space-y-1">
                      {availableFavorites.map(defn => (
                        <button
                          key={defn.key}
                          type="button"
                          onClick={() => { onAdd(defn.key, null); setShowAdd(null); }}
                          className="block w-full text-left px-3 py-1.5 text-sm rounded hover:bg-blue-50 text-blue-700"
                        >
                          {defn.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Accordion groups */}
          {INTENT_PROPERTY_GROUPS.map(group => {
            const isExpanded = expandedGroups.has(group.id);
            const groupProps = properties.filter(p => group.propertyKeys.includes(p.property_key));
            const availableProps = PROPERTY_DEFINITIONS.filter(
              d => group.propertyKeys.includes(d.key) && !usedKeys.has(d.key)
            );
            const activeCount = groupProps.length;

            return (
              <div key={group.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                {/* Accordion header */}
                <button
                  type="button"
                  onClick={() => toggleGroup(group.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                >
                  <svg className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-semibold text-gray-800">{group.label}</span>
                    <p className="text-xs text-gray-400">{group.description}</p>
                  </div>
                  {activeCount > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700 font-medium">
                      {activeCount}
                    </span>
                  )}
                  <span className="text-xs text-gray-400">{group.propertyKeys.length} available</span>
                </button>

                {/* Accordion content */}
                {isExpanded && (
                  <div className="border-t border-gray-100 p-4 space-y-2">
                    {groupProps.length === 0 && (
                      <p className="text-sm text-gray-400 text-center py-2">No properties configured in this group.</p>
                    )}

                    {groupProps.map(prop => {
                      const defn = PROPERTY_DEFINITIONS.find(d => d.key === prop.property_key);
                      if (!defn) return null;
                      return (
                        <PropertyRow
                          key={prop.id}
                          property={prop}
                          defn={defn}
                          onUpdate={onUpdate}
                          onRemove={onRemove}
                          isTemplate={templateKeys?.has(defn.key)}
                        />
                      );
                    })}

                    {/* Add property for this group */}
                    {availableProps.length > 0 && (
                      <div className="pt-2 border-t border-gray-100">
                        <button
                          type="button"
                          onClick={() => setShowAdd(showAdd === group.id ? null : group.id)}
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                        >
                          {showAdd === group.id ? '- Hide' : '+ Add Property'}
                        </button>
                        {showAdd === group.id && (
                          <div className="mt-2 space-y-1">
                            {availableProps.map(defn => (
                              <button
                                key={defn.key}
                                type="button"
                                onClick={() => { onAdd(defn.key, null); setShowAdd(null); }}
                                className="block w-full text-left px-3 py-1.5 text-sm rounded hover:bg-blue-50 text-blue-700"
                              >
                                {defn.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

// ── PropertyRow ──────────────────────────────────────────────────────

interface PropertyRowProps {
  property: BidProperty;
  defn: { key: string; label: string; value_type: string };
  onUpdate: (propertyId: string, updates: Partial<BidProperty>) => void;
  onRemove: (propertyId: string) => void;
  isTemplate?: boolean;
}

function PropertyRow({ property: prop, defn, onUpdate, onRemove, isTemplate }: PropertyRowProps) {
  return (
    <div className="flex items-center gap-2 p-2.5 bg-gray-50 rounded-lg">
      {/* Enable/disable */}
      <input
        type="checkbox"
        checked={prop.is_enabled}
        onChange={(e) => onUpdate(prop.id, { is_enabled: e.target.checked })}
        className="w-4 h-4 flex-shrink-0"
        aria-label={`Enable ${defn.label}`}
      />

      {/* Label + template badge */}
      <div className="min-w-[140px] flex-shrink-0">
        <span className={`text-sm font-medium ${!prop.is_enabled ? 'text-gray-400' : 'text-gray-800'}`}>
          {defn.label}
        </span>
        {isTemplate && (
          <span className="ml-1.5 text-xs text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded">template</span>
        )}
      </div>

      {/* Value editor */}
      <div className="flex-1 min-w-0">
        <PropertyValueEditor
          valueType={defn.value_type as any}
          value={prop.value}
          onChange={(val) => onUpdate(prop.id, { value: val })}
          disabled={!prop.is_enabled}
        />
      </div>

      {/* Layer toggles with labels */}
      <div className="flex gap-0.5 flex-shrink-0">
        <button
          type="button"
          onClick={() => {
            const allLayers = Array.from({ length: NUM_LAYERS }, (_, i) => i + 1);
            const allSelected = prop.layers.length === NUM_LAYERS;
            onUpdate(prop.id, { layers: allSelected ? [1] : allLayers });
          }}
          className={`w-7 h-7 text-xs rounded border font-medium ${
            prop.layers.length === NUM_LAYERS
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-400 border-gray-200 hover:border-gray-400'
          }`}
          title={prop.layers.length === NUM_LAYERS ? 'Deselect all layers' : 'Select all layers'}
        >
          All
        </button>
        {Array.from({ length: NUM_LAYERS }, (_, i) => i + 1).map(layer => {
          const label = LAYER_LABELS[layer];
          const isSelected = prop.layers.includes(layer);
          return (
            <button
              key={layer}
              type="button"
              onClick={() => {
                const newLayers = isSelected
                  ? prop.layers.filter(l => l !== layer)
                  : [...prop.layers, layer].sort();
                if (newLayers.length > 0) {
                  onUpdate(prop.id, { layers: newLayers });
                }
              }}
              className={`w-7 h-7 text-xs rounded border font-medium ${
                isSelected
                  ? `${label.color} text-white border-transparent`
                  : 'bg-white text-gray-400 border-gray-200 hover:border-gray-400'
              }`}
              title={`L${layer} ${label.name}`}
            >
              {layer}
            </button>
          );
        })}
      </div>

      {/* Remove */}
      <button
        type="button"
        onClick={() => onRemove(prop.id)}
        className="text-red-400 hover:text-red-600 text-sm px-1 flex-shrink-0"
        aria-label={`Remove ${defn.label}`}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
      </button>
    </div>
  );
}
