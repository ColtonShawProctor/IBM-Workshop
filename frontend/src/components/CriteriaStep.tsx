import { useState, useEffect, useCallback, useRef } from 'react';
import { guidedPoolCount } from '../lib/api';
import type { GuidedCriteria, PoolCountResult } from '../lib/api';

interface CriteriaStepProps {
  bidPeriodId: string;
  criteria: GuidedCriteria;
  onCriteriaChange: (criteria: GuidedCriteria) => void;
  onNext: () => void;
  isCommuter: boolean;
  commuteFrom: string;
  totalDates: number;
}

// ── City lists ─────────────────────────────────────────────────────────

const LOVE_CITIES = [
  'SFO', 'DEN', 'BOS', 'SAN', 'SEA', 'LAX', 'AUS', 'PDX', 'MIA', 'SNA', 'HNL', 'SJU',
];

const AVOID_CITIES = [
  'CLT', 'RDU', 'CVG', 'STL', 'CMH', 'IND', 'MCI', 'PHL',
];

// ── Credit hour presets ────────────────────────────────────────────────

const CREDIT_PRESETS = [
  { label: '85-90h', min: 85, max: 90 },
  { label: '80-90h', min: 80, max: 90 },
  { label: '75-90h', min: 75, max: 90 },
  { label: '70-90h', min: 70, max: 90 },
];

// ── Component ──────────────────────────────────────────────────────────

export default function CriteriaStep({
  bidPeriodId,
  criteria,
  onCriteriaChange,
  onNext,
  isCommuter,
  commuteFrom,
  totalDates,
}: CriteriaStepProps) {
  const [poolCount, setPoolCount] = useState<PoolCountResult | null>(null);
  const [poolLoading, setPoolLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Live pool count with 300ms debounce ────────────────────────────

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(async () => {
      setPoolLoading(true);
      try {
        const result = await guidedPoolCount(bidPeriodId, criteria);
        setPoolCount(result);
      } catch {
        setPoolCount(null);
      } finally {
        setPoolLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [bidPeriodId, criteria]);

  // ── Helpers ────────────────────────────────────────────────────────

  const update = useCallback(
    (patch: Partial<GuidedCriteria>) => {
      onCriteriaChange({ ...criteria, ...patch });
    },
    [criteria, onCriteriaChange],
  );

  const toggleInArray = useCallback(
    (arr: number[], value: number): number[] =>
      arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value],
    [],
  );

  const toggleInStringArray = useCallback(
    (arr: string[], value: string): string[] =>
      arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value],
    [],
  );

  // ── Derived values ────────────────────────────────────────────────

  const creditMinHours = Math.round(criteria.credit_min_minutes / 60);
  const creditMaxHours = Math.round(criteria.credit_max_minutes / 60);
  const matchingCount = poolCount?.total_matching ?? 0;
  const isDisabled = poolLoading || matchingCount === 0;

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto space-y-10 pb-8">
      {/* ── 1. TRIP LENGTH ─────────────────────────────────────────── */}
      <section>
        <h3 className="text-sm font-semibold uppercase text-gray-500 mb-3 tracking-wide">
          Trip Length
        </h3>
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5].map((len) => {
            const active = criteria.trip_lengths.includes(len);
            return (
              <button
                key={len}
                type="button"
                onClick={() => update({ trip_lengths: toggleInArray(criteria.trip_lengths, len) })}
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                }`}
              >
                {len}d
              </button>
            );
          })}
        </div>
      </section>

      {/* ── 2. LAYOVER CITIES ──────────────────────────────────────── */}
      <section>
        <h3 className="text-sm font-semibold uppercase text-gray-500 mb-3 tracking-wide">
          Layover Cities
        </h3>

        {/* Love row */}
        <div className="mb-4">
          <p className="text-xs font-medium text-green-700 mb-2">Love</p>
          <div className="flex flex-wrap gap-2">
            {LOVE_CITIES.map((city) => {
              const active = criteria.preferred_cities.includes(city);
              return (
                <button
                  key={city}
                  type="button"
                  onClick={() =>
                    update({ preferred_cities: toggleInStringArray(criteria.preferred_cities, city) })
                  }
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    active
                      ? 'bg-green-600 text-white border-green-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-green-400'
                  }`}
                >
                  {city}
                </button>
              );
            })}
          </div>
        </div>

        {/* Avoid row */}
        <div>
          <p className="text-xs font-medium text-red-700 mb-2">Avoid</p>
          <div className="flex flex-wrap gap-2">
            {AVOID_CITIES.map((city) => {
              const active = criteria.avoided_cities.includes(city);
              return (
                <button
                  key={city}
                  type="button"
                  onClick={() =>
                    update({ avoided_cities: toggleInStringArray(criteria.avoided_cities, city) })
                  }
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    active
                      ? 'bg-red-600 text-white border-red-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-red-400'
                  }`}
                >
                  {city}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── 3. REPORT TIME (commuter-aware) ───────────────────────── */}
      {isCommuter && (
        <section>
          <h3 className="text-sm font-semibold uppercase text-gray-500 mb-1 tracking-wide">
            Report Time
          </h3>
          <p className="text-xs text-gray-400 mb-3">You commute from {commuteFrom}</p>
          <div className="space-y-2">
            {[
              { label: 'After 9:00 AM \u2014 easy commute', value: 540 },
              { label: 'After 8:00 AM \u2014 tight but doable', value: 480 },
              { label: 'After 7:00 AM \u2014 early flight', value: 420 },
              { label: "Don't care", value: null },
            ].map((opt) => (
              <label
                key={opt.label}
                className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors"
              >
                <input
                  type="radio"
                  name="report_time"
                  checked={criteria.report_earliest_minutes === opt.value}
                  onChange={() => update({ report_earliest_minutes: opt.value })}
                  className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">{opt.label}</span>
              </label>
            ))}
          </div>
        </section>
      )}

      {/* ── 4. RELEASE TIME ───────────────────────────────────────── */}
      <section>
        <h3 className="text-sm font-semibold uppercase text-gray-500 mb-3 tracking-wide">
          Release Time
        </h3>
        <div className="space-y-2">
          {[
            { label: 'Before 5:00 PM \u2014 easy commute home', value: 1020 },
            { label: 'Before 7:00 PM \u2014 reasonable', value: 1140 },
            { label: 'Before 9:00 PM \u2014 very tight', value: 1260 },
            { label: "Don't care", value: null },
          ].map((opt) => (
            <label
              key={opt.label}
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors"
            >
              <input
                type="radio"
                name="release_time"
                checked={criteria.release_latest_minutes === opt.value}
                onChange={() => update({ release_latest_minutes: opt.value })}
                className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">{opt.label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* ── 5. CREDIT HOURS ───────────────────────────────────────── */}
      <section>
        <h3 className="text-sm font-semibold uppercase text-gray-500 mb-3 tracking-wide">
          Credit Hours
        </h3>
        <div className="flex flex-wrap gap-2 mb-3">
          {CREDIT_PRESETS.map((preset) => {
            const active =
              creditMinHours === preset.min && creditMaxHours === preset.max;
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() =>
                  update({
                    credit_min_minutes: preset.min * 60,
                    credit_max_minutes: preset.max * 60,
                  })
                }
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">Min</label>
            <input
              type="number"
              min={0}
              max={120}
              value={creditMinHours}
              onChange={(e) =>
                update({ credit_min_minutes: Math.max(0, Number(e.target.value)) * 60 })
              }
              className="w-20 border border-gray-200 rounded px-2 py-1.5 text-sm text-center"
            />
            <span className="text-xs text-gray-400">h</span>
          </div>
          <span className="text-gray-300">&ndash;</span>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">Max</label>
            <input
              type="number"
              min={0}
              max={120}
              value={creditMaxHours}
              onChange={(e) =>
                update({ credit_max_minutes: Math.max(0, Number(e.target.value)) * 60 })
              }
              className="w-20 border border-gray-200 rounded px-2 py-1.5 text-sm text-center"
            />
            <span className="text-xs text-gray-400">h</span>
          </div>
        </div>
      </section>

      {/* ── 6. SCHEDULE PREFERENCE ────────────────────────────────── */}
      <section>
        <h3 className="text-sm font-semibold uppercase text-gray-500 mb-3 tracking-wide">
          Schedule Preference
        </h3>
        <div className="space-y-2">
          {[
            { label: 'First half of month', value: 'first_half' as const },
            { label: 'Second half', value: 'second_half' as const },
            { label: 'Best available trips', value: 'best' as const },
          ].map((opt) => (
            <label
              key={opt.value}
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors"
            >
              <input
                type="radio"
                name="schedule_preference"
                checked={criteria.schedule_preference === opt.value}
                onChange={() => update({ schedule_preference: opt.value })}
                className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">{opt.label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* ── 7. DAYS OFF ───────────────────────────────────────────── */}
      <section>
        <h3 className="text-sm font-semibold uppercase text-gray-500 mb-1 tracking-wide">
          Days Off
        </h3>
        <p className="text-xs text-gray-400 mb-3">
          {criteria.days_off.length > 0
            ? `${criteria.days_off.length} day${criteria.days_off.length === 1 ? '' : 's'} selected`
            : 'Tap dates you want off'}
        </p>
        <div className="grid grid-cols-7 gap-1.5">
          {Array.from({ length: totalDates }, (_, i) => i + 1).map((day) => {
            const active = criteria.days_off.includes(day);
            return (
              <button
                key={day}
                type="button"
                onClick={() => update({ days_off: toggleInArray(criteria.days_off, day) })}
                className={`h-10 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-50 text-gray-700 hover:bg-blue-100'
                }`}
              >
                {day}
              </button>
            );
          })}
        </div>
        {criteria.days_off.length > 0 && (
          <button
            type="button"
            onClick={() => update({ days_off: [] })}
            className="mt-2 text-xs text-gray-400 hover:text-gray-600 underline"
          >
            Clear all
          </button>
        )}
      </section>

      {/* ── 8. LIVE POOL COUNT ────────────────────────────────────── */}
      <section className="sticky bottom-0 bg-white border-t border-gray-100 pt-4 -mx-4 px-4 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            {poolLoading && (
              <svg
                className="animate-spin h-4 w-4 text-blue-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            <span className="text-sm font-medium text-gray-700">
              Matching trips:{' '}
              <span
                className={`font-semibold ${
                  matchingCount > 0 ? 'text-blue-600' : 'text-gray-400'
                }`}
              >
                {poolLoading ? '...' : matchingCount}
              </span>
            </span>
          </div>

          {poolCount && !poolLoading && matchingCount > 0 && poolCount.by_trip_length && (
            <div className="flex gap-2">
              {Object.entries(poolCount.by_trip_length).map(([len, count]) => (
                <span key={len} className="text-xs text-gray-400">
                  {len}d: {count}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* ── 9. FIND MY TRIPS BUTTON ──────────────────────────────── */}
        <button
          type="button"
          disabled={isDisabled}
          onClick={onNext}
          className={`w-full py-3.5 rounded-xl text-base font-semibold transition-colors ${
            isDisabled
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
          }`}
        >
          Find My Trips
        </button>
      </section>
    </div>
  );
}
