import { useState, useCallback } from 'react';
import type { BidProperty } from '../types/api';
import { PROPERTY_DEFINITIONS } from '../types/pbs-catalog';

interface Props {
  properties: BidProperty[];
  onUpdate: (propertyId: string, updates: Partial<BidProperty>) => void;
  onAdd: (propertyKey: string, value: unknown) => void;
  /** Which property keys to surface as sliders (template-driven) */
  visibleKeys?: string[];
}

// Default set of controls if no template specifies favorites
const DEFAULT_VISIBLE = [
  'prefer_pairing_length',
  'maximize_credit',
  'report_between',
  'release_between',
  'layover_at_city',
  'prefer_pairing_type',
  'prefer_aircraft',
];

function fmtTime(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function parseTime(str: string): number {
  const [h, m] = str.split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

export default function KeyPreferenceSliders({ properties, onUpdate, onAdd, visibleKeys }: Props) {
  const keys = visibleKeys ?? DEFAULT_VISIBLE;

  // Helper to find a property by key
  const findProp = useCallback((key: string) => properties.find(p => p.property_key === key), [properties]);
  const findDefn = (key: string) => PROPERTY_DEFINITIONS.find(d => d.key === key);

  // Ensure a property exists, or add it
  const ensureAndUpdate = (key: string, value: unknown) => {
    const existing = findProp(key);
    if (existing) {
      onUpdate(existing.id, { value });
    } else {
      onAdd(key, value);
    }
  };

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-gray-700">Key Preferences</h4>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Trip Length */}
        {keys.includes('prefer_pairing_length') && (() => {
          const prop = findProp('prefer_pairing_length');
          const val = (prop?.value as number) || 3;
          return (
            <SliderControl
              label="Trip Length"
              hint="Preferred number of duty days per trip"
              min={1}
              max={5}
              step={1}
              value={val}
              displayValue={`${val}-day trips`}
              onChange={(v) => ensureAndUpdate('prefer_pairing_length', v)}
            />
          );
        })()}

        {/* Report Time */}
        {keys.includes('report_between') && (() => {
          const prop = findProp('report_between');
          const val = prop?.value as { start: number; end: number } | null;
          const start = val?.start ?? 480;
          const end = val?.end ?? 840;
          return (
            <TimeRangeControl
              label="Report Window"
              hint="Earliest to latest report time (first day)"
              startValue={start}
              endValue={end}
              onChange={(s, e) => ensureAndUpdate('report_between', { start: s, end: e })}
            />
          );
        })()}

        {/* Release Time */}
        {keys.includes('release_between') && (() => {
          const prop = findProp('release_between');
          const val = prop?.value as { start: number; end: number } | null;
          const start = val?.start ?? 480;
          const end = val?.end ?? 1200;
          return (
            <TimeRangeControl
              label="Release Window"
              hint="Earliest to latest release time (last day)"
              startValue={start}
              endValue={end}
              onChange={(s, e) => ensureAndUpdate('release_between', { start: s, end: e })}
            />
          );
        })()}

        {/* Maximize Credit toggle */}
        {keys.includes('maximize_credit') && (() => {
          const prop = findProp('maximize_credit');
          const isOn = prop?.value === true;
          return (
            <ToggleControl
              label="Maximize Credit"
              hint="Prioritize high credit hour trips"
              value={isOn}
              onChange={(v) => ensureAndUpdate('maximize_credit', v)}
            />
          );
        })()}

        {/* Layover City */}
        {keys.includes('layover_at_city') && (() => {
          const prop = findProp('layover_at_city');
          const val = (prop?.value as string) || '';
          return (
            <TextControl
              label="Preferred Layover City"
              hint="3-letter airport code (e.g. SAN, NRT, LHR)"
              value={val}
              placeholder="e.g. SAN"
              maxLength={3}
              onChange={(v) => ensureAndUpdate('layover_at_city', v)}
            />
          );
        })()}

        {/* Pairing Type */}
        {keys.includes('prefer_pairing_type') && (() => {
          const prop = findProp('prefer_pairing_type');
          const val = (prop?.value as string) || '';
          return (
            <SelectControl
              label="Pairing Type"
              hint="Type of flying to prefer"
              value={val}
              options={[
                { value: '', label: 'Any' },
                { value: 'regular', label: 'Regular' },
                { value: 'ipd', label: 'IPD (International)' },
                { value: 'nipd', label: 'NIPD' },
                { value: 'premium_transcon', label: 'Premium Transcon' },
              ]}
              onChange={(v) => ensureAndUpdate('prefer_pairing_type', v || null)}
            />
          );
        })()}

        {/* Equipment */}
        {keys.includes('prefer_aircraft') && (() => {
          const prop = findProp('prefer_aircraft');
          const val = (prop?.value as string) || '';
          return (
            <SelectControl
              label="Preferred Aircraft"
              hint="Equipment type preference"
              value={val}
              options={[
                { value: '', label: 'Any' },
                { value: '777', label: '777 (Widebody)' },
                { value: '787', label: '787 (Widebody)' },
                { value: '321', label: 'A321' },
                { value: '737', label: '737' },
                { value: '320', label: 'A320' },
              ]}
              onChange={(v) => ensureAndUpdate('prefer_aircraft', v || null)}
            />
          );
        })()}

        {/* Commutable Work Block */}
        {keys.includes('commutable_work_block') && (() => {
          const prop = findProp('commutable_work_block');
          const isOn = prop?.value === true;
          return (
            <ToggleControl
              label="Commutable Work Blocks"
              hint="Prefer trips that work with your commute"
              value={isOn}
              onChange={(v) => ensureAndUpdate('commutable_work_block', v)}
            />
          );
        })()}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

function SliderControl({ label, hint, min, max, step, value, displayValue, onChange }: {
  label: string; hint: string; min: number; max: number; step: number;
  value: number; displayValue: string; onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-xs font-medium text-blue-600">{displayValue}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
      />
      <p className="text-xs text-gray-400">{hint}</p>
    </div>
  );
}

function TimeRangeControl({ label, hint, startValue, endValue, onChange }: {
  label: string; hint: string; startValue: number; endValue: number;
  onChange: (start: number, end: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="time"
          value={fmtTime(startValue)}
          onChange={(e) => onChange(parseTime(e.target.value), endValue)}
          className="border border-gray-200 rounded px-2 py-1.5 text-sm w-28"
        />
        <span className="text-xs text-gray-400">to</span>
        <input
          type="time"
          value={fmtTime(endValue)}
          onChange={(e) => onChange(startValue, parseTime(e.target.value))}
          className="border border-gray-200 rounded px-2 py-1.5 text-sm w-28"
        />
      </div>
      <p className="text-xs text-gray-400">{hint}</p>
    </div>
  );
}

function ToggleControl({ label, hint, value, onChange }: {
  label: string; hint: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <div>
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <p className="text-xs text-gray-400">{hint}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          value ? 'bg-blue-600' : 'bg-gray-200'
        }`}
      >
        <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
          value ? 'translate-x-6' : 'translate-x-1'
        }`} />
      </button>
    </div>
  );
}

function TextControl({ label, hint, value, placeholder, maxLength, onChange }: {
  label: string; hint: string; value: string; placeholder: string;
  maxLength?: number; onChange: (v: string) => void;
}) {
  // Local state so we don't fire onChange on every keystroke (which would
  // create duplicate properties via onAdd before the API returns).
  const [localValue, setLocalValue] = useState(value);
  // Sync from parent when the prop changes (e.g. template switch)
  const [prevValue, setPrevValue] = useState(value);
  if (value !== prevValue) {
    setPrevValue(value);
    setLocalValue(value);
  }

  const commit = () => {
    const trimmed = localValue.trim();
    if (trimmed !== value) {
      onChange(trimmed);
    }
  };

  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <input
        type="text"
        value={localValue}
        placeholder={placeholder}
        maxLength={maxLength}
        onChange={(e) => setLocalValue(e.target.value.toUpperCase())}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === 'Enter') commit(); }}
        className="border border-gray-200 rounded px-3 py-1.5 text-sm w-full uppercase"
      />
      <p className="text-xs text-gray-400">{hint}</p>
    </div>
  );
}

function SelectControl({ label, hint, value, options, onChange }: {
  label: string; hint: string; value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border border-gray-200 rounded px-3 py-1.5 text-sm w-full bg-white"
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <p className="text-xs text-gray-400">{hint}</p>
    </div>
  );
}
