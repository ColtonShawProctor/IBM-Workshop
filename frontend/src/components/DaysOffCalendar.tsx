import { useState, useCallback, useRef, useEffect } from 'react';

interface Props {
  /** ISO date strings of the bid month range */
  monthStart: string; // e.g. "2026-01-01"
  monthEnd: string;   // e.g. "2026-01-31"
  /** Currently selected day-of-month numbers (1-31) */
  selectedDays: number[];
  /** Called with updated array of selected day-of-month numbers */
  onChange: (days: number[]) => void;
}

function getDaysInMonth(dateStr: string): Date[] {
  const d = new Date(dateStr + 'T00:00:00');
  const year = d.getFullYear();
  const month = d.getMonth();
  const days: Date[] = [];
  const current = new Date(year, month, 1);
  while (current.getMonth() === month) {
    days.push(new Date(current));
    current.setDate(current.getDate() + 1);
  }
  return days;
}

function formatMonthYear(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function DaysOffCalendar({ monthStart, monthEnd, selectedDays, onChange }: Props) {
  const [lastClicked, setLastClicked] = useState<number | null>(null);
  const announcerRef = useRef<HTMLDivElement>(null);

  const days = getDaysInMonth(monthStart);
  const endDate = new Date(monthEnd + 'T00:00:00');
  const validDays = days.filter(d => d <= endDate);
  const firstDayOfWeek = days[0].getDay(); // 0=Sunday

  // Derive all weekend days in range
  const weekendDays = validDays
    .filter(d => d.getDay() === 0 || d.getDay() === 6)
    .map(d => d.getDate());

  const selected = new Set(selectedDays);

  const announce = (msg: string) => {
    if (announcerRef.current) {
      announcerRef.current.textContent = msg;
    }
  };

  const toggleDay = useCallback((dayNum: number, shiftKey: boolean) => {
    if (shiftKey && lastClicked !== null) {
      // Range select
      const start = Math.min(lastClicked, dayNum);
      const end = Math.max(lastClicked, dayNum);
      const rangeDays: number[] = [];
      for (let i = start; i <= end; i++) {
        if (validDays.some(d => d.getDate() === i)) {
          rangeDays.push(i);
        }
      }
      const newSelected = new Set(selectedDays);
      for (const d of rangeDays) newSelected.add(d);
      onChange([...newSelected].sort((a, b) => a - b));
      announce(`Selected days ${start} through ${end}`);
    } else {
      if (selected.has(dayNum)) {
        onChange(selectedDays.filter(d => d !== dayNum));
        announce(`Day ${dayNum} deselected`);
      } else {
        onChange([...selectedDays, dayNum].sort((a, b) => a - b));
        announce(`Day ${dayNum} selected as day off`);
      }
    }
    setLastClicked(dayNum);
  }, [lastClicked, selectedDays, selected, validDays, onChange]);

  // Keyboard navigation
  const [focusDay, setFocusDay] = useState<number>(1);
  const gridRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const maxDay = validDays[validDays.length - 1]?.getDate() ?? 31;
    let next = focusDay;

    switch (e.key) {
      case 'ArrowRight': next = Math.min(focusDay + 1, maxDay); break;
      case 'ArrowLeft': next = Math.max(focusDay - 1, 1); break;
      case 'ArrowDown': next = Math.min(focusDay + 7, maxDay); break;
      case 'ArrowUp': next = Math.max(focusDay - 7, 1); break;
      case ' ':
      case 'Enter':
        e.preventDefault();
        toggleDay(focusDay, e.shiftKey);
        return;
      default: return;
    }
    e.preventDefault();
    setFocusDay(next);
  }, [focusDay, validDays, toggleDay]);

  // Focus the active day cell
  useEffect(() => {
    if (gridRef.current) {
      const cell = gridRef.current.querySelector(`[data-day="${focusDay}"]`) as HTMLElement;
      cell?.focus();
    }
  }, [focusDay]);

  // Summarize selected ranges
  const summary = summarizeRanges(selectedDays);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700">Days Off</h4>
        <span className="text-xs text-gray-500">{formatMonthYear(monthStart)}</span>
      </div>

      {/* Calendar grid */}
      <div
        ref={gridRef}
        role="grid"
        aria-label={`Days off calendar for ${formatMonthYear(monthStart)}`}
        onKeyDown={handleKeyDown}
        className="select-none"
      >
        {/* Day name headers */}
        <div role="row" className="grid grid-cols-7 gap-1 mb-1">
          {DAY_NAMES.map(name => (
            <div key={name} role="columnheader" className="text-center text-xs font-medium text-gray-400 py-1">
              {name}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div role="row" className="grid grid-cols-7 gap-1">
          {/* Empty cells for offset */}
          {Array.from({ length: firstDayOfWeek }).map((_, i) => (
            <div key={`empty-${i}`} role="gridcell" className="h-9" />
          ))}

          {validDays.map(date => {
            const dayNum = date.getDate();
            const isSelected = selected.has(dayNum);
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            const isFocused = focusDay === dayNum;

            // Range visual: check if adjacent days are also selected
            const prevSelected = selected.has(dayNum - 1);
            const nextSelected = selected.has(dayNum + 1);
            const rangeClass = isSelected
              ? prevSelected && nextSelected
                ? 'rounded-none'
                : prevSelected
                  ? 'rounded-l-none rounded-r-lg'
                  : nextSelected
                    ? 'rounded-r-none rounded-l-lg'
                    : 'rounded-lg'
              : 'rounded-lg';

            return (
              <button
                key={dayNum}
                role="gridcell"
                data-day={dayNum}
                aria-selected={isSelected}
                aria-label={`${date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}${isSelected ? ' - day off' : ''}`}
                tabIndex={isFocused ? 0 : -1}
                onClick={(e) => toggleDay(dayNum, e.shiftKey)}
                className={`h-9 text-sm font-medium flex items-center justify-center transition-colors
                  ${isSelected
                    ? `bg-blue-500 text-white hover:bg-blue-600 ${rangeClass}`
                    : isWeekend
                      ? `bg-gray-50 text-gray-600 hover:bg-blue-100 ${rangeClass}`
                      : `bg-white text-gray-800 hover:bg-blue-100 ${rangeClass}`
                  }
                  ${isFocused ? 'ring-2 ring-blue-300 ring-offset-1' : ''}
                `}
              >
                {dayNum}
              </button>
            );
          })}
        </div>
      </div>

      {/* Summary */}
      <div className="text-xs text-gray-500">
        {selectedDays.length > 0
          ? <>Days Off: {summary} ({selectedDays.length} days total)</>
          : 'Click dates to mark as days off. Shift+Click to select a range.'}
      </div>

      {/* Quick actions */}
      <div className="flex gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => onChange(weekendDays.sort((a, b) => a - b))}
          className="text-xs px-2.5 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50"
        >
          Select All Weekends
        </button>
        <button
          type="button"
          onClick={() => onChange([])}
          className="text-xs px-2.5 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50"
        >
          Clear All
        </button>
        <button
          type="button"
          onClick={() => {
            const allDays = validDays.map(d => d.getDate());
            const inverted = allDays.filter(d => !selected.has(d));
            onChange(inverted.sort((a, b) => a - b));
          }}
          className="text-xs px-2.5 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50"
        >
          Invert
        </button>
      </div>

      {/* Screen reader announcements */}
      <div ref={announcerRef} aria-live="polite" className="sr-only" />
    </div>
  );
}

/** Turn [1,2,3,5,6,10] into "Jan 1-3, Jan 5-6, Jan 10" */
function summarizeRanges(days: number[]): string {
  if (days.length === 0) return '';
  const sorted = [...days].sort((a, b) => a - b);
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

  return ranges
    .map(([s, e]) => s === e ? `${s}` : `${s}-${e}`)
    .join(', ');
}
