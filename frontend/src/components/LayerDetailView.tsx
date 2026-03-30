import type { BidProperty, PropertyCategory } from '../types/api';
import { PROPERTY_DEFINITIONS } from '../types/pbs-catalog';
import { NUM_LAYERS } from '../types/api';

interface Props {
  layerNumber: number;
  properties: BidProperty[];
  onClose: () => void;
}

const CATEGORY_LABELS: Record<PropertyCategory, string> = {
  days_off: 'Days Off',
  line: 'Line',
  pairing: 'Pairing',
  reserve: 'Reserve',
};

const CATEGORIES: PropertyCategory[] = ['days_off', 'pairing', 'line', 'reserve'];

function formatValue(value: unknown, valueType: string): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'On' : 'Off';
  if (typeof value === 'number') {
    if (valueType === 'time') {
      const h = Math.floor(value / 60);
      const m = value % 60;
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
    return String(value);
  }
  if (typeof value === 'string') return value;
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if ('start' in obj && 'end' in obj) {
      const fmt = (v: unknown) => {
        if (typeof v === 'number') {
          const h = Math.floor(v / 60);
          const m = v % 60;
          return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
        }
        return String(v);
      };
      return `${fmt(obj.start)} – ${fmt(obj.end)}`;
    }
    if ('min' in obj && 'max' in obj) return `${obj.min} – ${obj.max}`;
    if ('airport' in obj && 'date' in obj) return `${obj.airport} on ${obj.date}`;
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return (value as number[]).map((i) => days[i] || i).join(', ');
  }
  return String(value);
}

export default function LayerDetailView({ layerNumber, properties, onClose }: Props) {
  const layerProps = properties.filter((p) => p.layers.includes(layerNumber) && p.is_enabled);

  // Group by category
  const grouped = CATEGORIES.reduce((acc, cat) => {
    const catProps = layerProps.filter((p) => p.category === cat);
    if (catProps.length > 0) acc[cat] = catProps;
    return acc;
  }, {} as Record<PropertyCategory, BidProperty[]>);

  // Layer assignment overview
  const layerCounts = Array.from({ length: NUM_LAYERS }, (_, i) => {
    const l = i + 1;
    return {
      layer: l,
      count: properties.filter((p) => p.layers.includes(l) && p.is_enabled).length,
    };
  });

  return (
    <div className="border rounded-lg bg-white shadow-sm p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">
          Layer {layerNumber} — {layerProps.length} {layerProps.length === 1 ? 'property' : 'properties'}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          Close
        </button>
      </div>

      {layerProps.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">
          No properties assigned to Layer {layerNumber}. All pairings in the base package are available.
        </p>
      ) : (
        <div className="space-y-4">
          {Object.entries(grouped).map(([cat, props]) => (
            <div key={cat}>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                {CATEGORY_LABELS[cat as PropertyCategory]}
              </p>
              <div className="space-y-1">
                {props.map((prop) => {
                  const defn = PROPERTY_DEFINITIONS.find((d) => d.key === prop.property_key);
                  return (
                    <div key={prop.id} className="flex items-center justify-between px-3 py-1.5 bg-gray-50 rounded text-sm">
                      <span className="text-gray-700">{defn?.label ?? prop.property_key}</span>
                      <span className="text-gray-500 font-mono text-xs">
                        {formatValue(prop.value, defn?.value_type ?? 'text')}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Layer overview */}
      <div className="mt-4 pt-3 border-t">
        <p className="text-xs font-semibold text-gray-500 uppercase mb-2">All Layers</p>
        <div className="flex gap-2">
          {layerCounts.map(({ layer, count }) => (
            <div
              key={layer}
              className={`flex-1 text-center py-1 rounded text-xs ${
                layer === layerNumber
                  ? 'bg-blue-100 text-blue-700 font-semibold'
                  : 'bg-gray-50 text-gray-500'
              }`}
            >
              L{layer}: {count}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
