import { useState, useEffect, useRef } from 'react';
import type { BidProperty, BidPeriod, LayerSummary } from '../types/api';
import DaysOffCalendar from './DaysOffCalendar';
import KeyPreferenceSliders from './KeyPreferenceSliders';
import LayerPriorityOverview from './LayerPriorityOverview';

interface Props {
  bidPeriod: BidPeriod;
  properties: BidProperty[];
  layerSummaries: LayerSummary[];
  layersLoading: boolean;
  onAddProperty: (propertyKey: string, value: unknown) => void;
  onUpdateProperty: (propertyId: string, updates: Partial<BidProperty>) => void;
  onRemoveProperty: (propertyId: string) => void;
  /** Which property keys to surface as sliders (from template) */
  favoritePropertyKeys?: string[];
}

export default function PersonalizeYourBid({
  bidPeriod,
  properties,
  layerSummaries,
  layersLoading,
  onAddProperty,
  onUpdateProperty,
  onRemoveProperty,
  favoritePropertyKeys,
}: Props) {
  // Local calendar state — decoupled from PBS properties to support
  // non-contiguous selections, individual day toggles, and weekends.
  const [localDays, setLocalDays] = useState<number[]>(() =>
    parseDaysFromProperties(properties, bidPeriod)
  );

  // Guard: suppress props→local sync while a user-initiated change is being
  // debounced/synced to PBS (prevents Clear All needing two clicks when
  // multiple properties are removed sequentially).
  const suppressSyncRef = useRef(false);

  // Sync from properties → local state when properties change externally
  const prevPropsRef = useRef(properties);
  useEffect(() => {
    if (prevPropsRef.current !== properties) {
      prevPropsRef.current = properties;
      if (suppressSyncRef.current) return; // user-initiated change in progress
      const fromProps = parseDaysFromProperties(properties, bidPeriod);
      // Only sync if the property-derived days actually differ from local
      // (avoids overwriting non-contiguous local selections)
      if (fromProps.length > 0 && localDays.length === 0) {
        setLocalDays(fromProps);
      }
    }
  }, [properties, bidPeriod]);

  // Debounced sync from local state → PBS properties
  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleDaysChange = (days: number[]) => {
    setLocalDays(days);
    suppressSyncRef.current = true;

    // Debounce the PBS property sync
    if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);
    syncTimeoutRef.current = setTimeout(() => {
      syncDaysToPBS(days, properties, bidPeriod, onAddProperty, onUpdateProperty, onRemoveProperty);
      // Release the guard after sync operations have been dispatched
      setTimeout(() => { suppressSyncRef.current = false; }, 500);
    }, 600);
  };

  // Derive mapping hint for the user
  const mappingHint = getMappingHint(localDays, bidPeriod);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Personalize Your Bid</h3>
        <p className="text-sm text-gray-500 mt-1">
          Adjust the calendar, preferences, and layer priorities to match your ideal month.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Calendar + Sliders */}
        <div className="lg:col-span-2 space-y-6">
          {/* Days Off Calendar */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <DaysOffCalendar
              monthStart={bidPeriod.effective_start}
              monthEnd={bidPeriod.effective_end}
              selectedDays={localDays}
              onChange={handleDaysChange}
            />
            {mappingHint && (
              <p className="mt-2 text-xs text-amber-600 bg-amber-50 rounded px-3 py-1.5">
                {mappingHint}
              </p>
            )}
          </div>

          {/* Key Preference Sliders */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <KeyPreferenceSliders
              properties={properties}
              onUpdate={onUpdateProperty}
              onAdd={onAddProperty}
              visibleKeys={favoritePropertyKeys}
            />
          </div>
        </div>

        {/* Right column: Layer Priority Overview */}
        <div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 sticky top-4">
            <LayerPriorityOverview
              summaries={layerSummaries}
              properties={properties}
              loading={layersLoading}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

/** Parse days-off from PBS properties into day-of-month array */
function parseDaysFromProperties(properties: BidProperty[], bidPeriod: BidPeriod): number[] {
  const days = new Set<number>();

  const startProp = properties.find(p => p.property_key === 'string_days_off_starting');
  if (startProp?.value && typeof startProp.value === 'string') {
    const startDate = new Date(startProp.value + 'T00:00:00');
    const endDate = new Date(bidPeriod.effective_end + 'T00:00:00');
    const current = new Date(startDate);
    while (current <= endDate) {
      days.add(current.getDate());
      current.setDate(current.getDate() + 1);
    }
  }

  const endProp = properties.find(p => p.property_key === 'string_days_off_ending');
  if (endProp?.value && typeof endProp.value === 'string') {
    const bpStart = new Date(bidPeriod.effective_start + 'T00:00:00');
    const endDate = new Date(endProp.value + 'T00:00:00');
    const current = new Date(bpStart);
    while (current <= endDate) {
      days.add(current.getDate());
      current.setDate(current.getDate() + 1);
    }
  }

  return [...days].sort((a, b) => a - b);
}

/** Sync local day selections to the best combination of PBS properties */
function syncDaysToPBS(
  days: number[],
  properties: BidProperty[],
  bidPeriod: BidPeriod,
  onAdd: (key: string, value: unknown) => void,
  onUpdate: (id: string, updates: Partial<BidProperty>) => void,
  onRemove: (id: string) => void,
) {
  const startProp = properties.find(p => p.property_key === 'string_days_off_starting');
  const endProp = properties.find(p => p.property_key === 'string_days_off_ending');
  const weekendProp = properties.find(p => p.property_key === 'maximize_weekend_days_off');

  const bpStart = new Date(bidPeriod.effective_start + 'T00:00:00');
  const bpEnd = new Date(bidPeriod.effective_end + 'T00:00:00');
  const year = bpStart.getFullYear();
  const month = bpStart.getMonth();
  const lastDayOfMonth = bpEnd.getDate();

  if (days.length === 0) {
    // Clear all days-off properties
    if (startProp) onRemove(startProp.id);
    if (endProp) onRemove(endProp.id);
    if (weekendProp) onUpdate(weekendProp.id, { value: false });
    return;
  }

  const sorted = [...days].sort((a, b) => a - b);

  // Detect patterns and set the best PBS properties:

  // Check if it's all weekends
  const allDaysInMonth: Date[] = [];
  const current = new Date(bpStart);
  while (current <= bpEnd) {
    allDaysInMonth.push(new Date(current));
    current.setDate(current.getDate() + 1);
  }
  const weekendDays = allDaysInMonth
    .filter(d => d.getDay() === 0 || d.getDay() === 6)
    .map(d => d.getDate())
    .sort((a, b) => a - b);

  const isWeekendSelection = sorted.length === weekendDays.length &&
    sorted.every((d, i) => d === weekendDays[i]);

  if (isWeekendSelection) {
    if (weekendProp) {
      onUpdate(weekendProp.id, { value: true });
    } else {
      onAdd('maximize_weekend_days_off', true);
    }
    // Clear block properties
    if (startProp) onRemove(startProp.id);
    if (endProp) onRemove(endProp.id);
    return;
  }

  // Find contiguous ranges
  const ranges = findRanges(sorted);

  // Check: contiguous block ending at end of month → string_days_off_starting
  const trailingRange = ranges.find(r => r[1] === lastDayOfMonth);
  // Check: contiguous block starting at day 1 → string_days_off_ending
  const leadingRange = ranges.find(r => r[0] === 1);

  if (trailingRange) {
    const startISO = new Date(year, month, trailingRange[0]).toISOString().split('T')[0];
    if (startProp) {
      onUpdate(startProp.id, { value: startISO });
    } else {
      onAdd('string_days_off_starting', startISO);
    }
  } else {
    if (startProp) onRemove(startProp.id);
  }

  if (leadingRange && (!trailingRange || leadingRange !== trailingRange)) {
    const endISO = new Date(year, month, leadingRange[1]).toISOString().split('T')[0];
    if (endProp) {
      onUpdate(endProp.id, { value: endISO });
    } else {
      onAdd('string_days_off_ending', endISO);
    }
  } else if (!leadingRange) {
    if (endProp) onRemove(endProp.id);
  }

  // If no trailing or leading range was found, use the largest contiguous block
  if (!trailingRange && !leadingRange && ranges.length > 0) {
    const largest = ranges.reduce((best, r) => (r[1] - r[0]) > (best[1] - best[0]) ? r : best);
    const startISO = new Date(year, month, largest[0]).toISOString().split('T')[0];
    if (startProp) {
      onUpdate(startProp.id, { value: startISO });
    } else {
      onAdd('string_days_off_starting', startISO);
    }
  }

  // Clear weekend prop if not a weekend selection
  if (weekendProp && !isWeekendSelection) {
    onUpdate(weekendProp.id, { value: false });
  }
}

/** Find contiguous ranges in sorted day numbers */
function findRanges(sorted: number[]): [number, number][] {
  if (sorted.length === 0) return [];
  const ranges: [number, number][] = [];
  let start = sorted[0];
  let end = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === end + 1) {
      end = sorted[i];
    } else {
      ranges.push([start, end]);
      start = sorted[i];
      end = sorted[i];
    }
  }
  ranges.push([start, end]);
  return ranges;
}

/** Generate a user-facing hint about how the selection maps to PBS */
function getMappingHint(days: number[], bidPeriod: BidPeriod): string | null {
  if (days.length === 0) return null;

  const sorted = [...days].sort((a, b) => a - b);
  const ranges = findRanges(sorted);

  if (ranges.length <= 1) return null; // Single block — maps perfectly

  // Check for weekends
  const bpStart = new Date(bidPeriod.effective_start + 'T00:00:00');
  const bpEnd = new Date(bidPeriod.effective_end + 'T00:00:00');
  const allDays: Date[] = [];
  const current = new Date(bpStart);
  while (current <= bpEnd) {
    allDays.push(new Date(current));
    current.setDate(current.getDate() + 1);
  }
  const weekendDays = allDays
    .filter(d => d.getDay() === 0 || d.getDay() === 6)
    .map(d => d.getDate())
    .sort((a, b) => a - b);

  const isWeekends = sorted.length === weekendDays.length &&
    sorted.every((d, i) => d === weekendDays[i]);

  if (isWeekends) return null; // Weekend selection maps to maximize_weekend_days_off

  return `PBS supports one contiguous block of days off. Your ${ranges.length} separate blocks will be mapped to the best available PBS properties. Use Fine-Tune for precise control.`;
}
