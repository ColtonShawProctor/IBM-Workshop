import { type ValueType } from '../types/api';
import { EQUIPMENT_CODES, PAIRING_TYPES } from '../types/api';

interface Props {
  valueType: ValueType;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
}

export default function PropertyValueEditor({ valueType, value, onChange, disabled }: Props) {
  switch (valueType) {
    case 'toggle':
      return (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            className="w-4 h-4"
          />
          <span className="text-sm">{value ? 'On' : 'Off'}</span>
        </label>
      );

    case 'integer':
      return (
        <input
          type="number"
          value={typeof value === 'number' ? value : ''}
          onChange={(e) => onChange(e.target.value ? parseInt(e.target.value, 10) : null)}
          disabled={disabled}
          className="border rounded px-2 py-1 w-24 text-sm"
          step={1}
        />
      );

    case 'decimal':
      return (
        <input
          type="number"
          value={typeof value === 'number' ? value : ''}
          onChange={(e) => onChange(e.target.value ? parseFloat(e.target.value) : null)}
          disabled={disabled}
          className="border rounded px-2 py-1 w-24 text-sm"
          step={0.1}
        />
      );

    case 'time': {
      const minutes = typeof value === 'number' ? value : 0;
      const hh = String(Math.floor(minutes / 60)).padStart(2, '0');
      const mm = String(minutes % 60).padStart(2, '0');
      return (
        <input
          type="time"
          value={`${hh}:${mm}`}
          onChange={(e) => {
            const [h, m] = e.target.value.split(':').map(Number);
            onChange(h * 60 + m);
          }}
          disabled={disabled}
          className="border rounded px-2 py-1 text-sm"
        />
      );
    }

    case 'time_range': {
      const range = (typeof value === 'object' && value !== null ? value : { start: 0, end: 0 }) as { start: number; end: number };
      const fmt = (min: number) => {
        const h = String(Math.floor(min / 60)).padStart(2, '0');
        const m = String(min % 60).padStart(2, '0');
        return `${h}:${m}`;
      };
      const parse = (s: string) => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };
      return (
        <div className="flex items-center gap-1">
          <input type="time" value={fmt(range.start)} onChange={(e) => onChange({ ...range, start: parse(e.target.value) })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
          <span className="text-xs text-gray-500">to</span>
          <input type="time" value={fmt(range.end)} onChange={(e) => onChange({ ...range, end: parse(e.target.value) })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
        </div>
      );
    }

    case 'int_range': {
      const ir = (typeof value === 'object' && value !== null ? value : { min: 1, max: 9 }) as { min: number; max: number };
      return (
        <div className="flex items-center gap-1">
          <input type="number" value={ir.min} onChange={(e) => onChange({ ...ir, min: parseInt(e.target.value, 10) })} disabled={disabled} className="border rounded px-2 py-1 w-16 text-sm" />
          <span className="text-xs text-gray-500">to</span>
          <input type="number" value={ir.max} onChange={(e) => onChange({ ...ir, max: parseInt(e.target.value, 10) })} disabled={disabled} className="border rounded px-2 py-1 w-16 text-sm" />
        </div>
      );
    }

    case 'date':
      return (
        <input
          type="date"
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="border rounded px-2 py-1 text-sm"
        />
      );

    case 'date_range': {
      const dr = (typeof value === 'object' && value !== null ? value : { start: '', end: '' }) as { start: string; end: string };
      return (
        <div className="flex items-center gap-1">
          <input type="date" value={dr.start} onChange={(e) => onChange({ ...dr, start: e.target.value })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
          <span className="text-xs text-gray-500">to</span>
          <input type="date" value={dr.end} onChange={(e) => onChange({ ...dr, end: e.target.value })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
        </div>
      );
    }

    case 'pairing_type':
      return (
        <select
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="border rounded px-2 py-1 text-sm"
        >
          <option value="">Select...</option>
          {PAIRING_TYPES.map((pt) => (
            <option key={pt.value} value={pt.value}>{pt.label}</option>
          ))}
        </select>
      );

    case 'equipment':
      return (
        <select
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="border rounded px-2 py-1 text-sm"
        >
          <option value="">Select...</option>
          {EQUIPMENT_CODES.map((code) => (
            <option key={code} value={code}>{code}</option>
          ))}
        </select>
      );

    case 'airport':
    case 'text':
    case 'selection':
    case 'position_list':
      return (
        <input
          type="text"
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          disabled={disabled}
          placeholder={valueType === 'airport' ? 'e.g. ORD' : valueType === 'position_list' ? 'e.g. 03,04,01' : ''}
          className="border rounded px-2 py-1 w-32 text-sm uppercase"
          maxLength={valueType === 'airport' ? 3 : undefined}
        />
      );

    case 'airport_date': {
      const ad = (typeof value === 'object' && value !== null ? value : { airport: '', date: '' }) as { airport: string; date: string };
      return (
        <div className="flex items-center gap-1">
          <input type="text" value={ad.airport} onChange={(e) => onChange({ ...ad, airport: e.target.value.toUpperCase() })} disabled={disabled} placeholder="ORD" className="border rounded px-2 py-1 w-16 text-sm uppercase" maxLength={3} />
          <input type="date" value={ad.date} onChange={(e) => onChange({ ...ad, date: e.target.value })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
        </div>
      );
    }

    case 'days_of_week': {
      const days = Array.isArray(value) ? (value as number[]) : [];
      const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      return (
        <div className="flex gap-1">
          {labels.map((label, i) => (
            <button
              key={i}
              type="button"
              disabled={disabled}
              onClick={() => {
                const newDays = days.includes(i) ? days.filter((d) => d !== i) : [...days, i];
                onChange(newDays.sort());
              }}
              className={`px-2 py-1 text-xs rounded border ${days.includes(i) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'}`}
            >
              {label}
            </button>
          ))}
        </div>
      );
    }

    case 'time_range_date': {
      const trd = (typeof value === 'object' && value !== null ? value : { start: 0, end: 0, date: '' }) as { start: number; end: number; date: string };
      const fmt = (min: number) => { const h = String(Math.floor(min / 60)).padStart(2, '0'); const m = String(min % 60).padStart(2, '0'); return `${h}:${m}`; };
      const parse = (s: string) => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };
      return (
        <div className="flex items-center gap-1 flex-wrap">
          <input type="time" value={fmt(trd.start)} onChange={(e) => onChange({ ...trd, start: parse(e.target.value) })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
          <span className="text-xs text-gray-500">to</span>
          <input type="time" value={fmt(trd.end)} onChange={(e) => onChange({ ...trd, end: parse(e.target.value) })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
          <input type="date" value={trd.date} onChange={(e) => onChange({ ...trd, date: e.target.value })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
        </div>
      );
    }

    case 'int_date': {
      const id = (typeof value === 'object' && value !== null ? value : { value: 1, date: '' }) as { value: number; date: string };
      return (
        <div className="flex items-center gap-1">
          <input type="number" value={id.value} onChange={(e) => onChange({ ...id, value: parseInt(e.target.value, 10) })} disabled={disabled} className="border rounded px-2 py-1 w-16 text-sm" />
          <input type="date" value={id.date} onChange={(e) => onChange({ ...id, date: e.target.value })} disabled={disabled} className="border rounded px-2 py-1 text-sm" />
        </div>
      );
    }

    default:
      return <span className="text-sm text-gray-400">Unsupported: {valueType}</span>;
  }
}
