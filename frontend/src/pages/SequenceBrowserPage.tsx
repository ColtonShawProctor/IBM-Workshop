import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { listSequences, listFilterPresets, createFilterPreset, deleteFilterPreset, listBookmarks, createBookmark, deleteBookmark } from '../lib/api';
import type { Sequence, FilterPreset, FilterSet, Bookmark } from '../types/api';

function formatMinutes(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

const EMPTY_FILTERS: FilterSet = {
  categories: [],
  equipment_types: [],
  layover_cities: [],
  operating_dates: [],
};

function filtersToParams(f: FilterSet): Record<string, string | number | boolean> {
  const p: Record<string, string | number | boolean> = {};
  if (f.categories.length === 1) p.category = f.categories[0];
  if (f.language) p.language = f.language;
  if (f.is_turn !== undefined && f.is_turn !== null) p.is_turn = f.is_turn;
  if (f.tpay_min_minutes != null) p.tpay_min = f.tpay_min_minutes;
  if (f.tpay_max_minutes != null) p.tpay_max = f.tpay_max_minutes;
  if (f.tafb_min_minutes != null) p.tafb_min = f.tafb_min_minutes;
  if (f.tafb_max_minutes != null) p.tafb_max = f.tafb_max_minutes;
  if (f.include_deadheads != null) p.has_deadhead = f.include_deadheads;
  if (f.layover_cities.length > 0) p.layover_city = f.layover_cities[0];
  if (f.duty_days_min != null) p.duty_days_min = f.duty_days_min;
  if (f.duty_days_max != null) p.duty_days_max = f.duty_days_max;
  return p;
}

export default function SequenceBrowserPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const navigate = useNavigate();
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [sortBy, setSortBy] = useState('seq_number');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [filters, setFilters] = useState<FilterSet>({ ...EMPTY_FILTERS });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [presets, setPresets] = useState<FilterPreset[]>([]);
  const [presetName, setPresetName] = useState('');
  const [bookmarks, setBookmarks] = useState<Map<string, Bookmark>>(new Map()); // seqId -> bookmark
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [commutableOnly, setCommutableOnly] = useState(false);
  const [seqSearch, setSeqSearch] = useState('');
  const [seqSearchError, setSeqSearchError] = useState('');
  const [seqSearching, setSeqSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Load filter presets + bookmarks
  useEffect(() => {
    if (!bidPeriodId) return;
    listFilterPresets(bidPeriodId).then((r) => setPresets(r.data)).catch(() => {});
    listBookmarks(bidPeriodId).then((r) => {
      const map = new Map<string, Bookmark>();
      for (const b of r.data) map.set(b.sequence_id, b);
      setBookmarks(map);
    }).catch(() => {});
  }, [bidPeriodId]);

  const fetchSequences = useCallback(() => {
    if (!bidPeriodId) return;
    setLoading(true);
    const params: Record<string, string | number | boolean> = {
      sort_by: sortBy,
      sort_order: sortOrder,
      limit: 50,
      ...filtersToParams(filters),
    };
    if (commutableOnly) params.commutable_only = true;
    listSequences(bidPeriodId, params)
      .then((res) => {
        setSequences(res.data);
        setTotalCount(res.total_count ?? res.data.length);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [bidPeriodId, sortBy, sortOrder, filters, commutableOnly]);

  // Debounced fetch on filter/sort change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchSequences, 200);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [fetchSequences]);

  const toggleSort = (field: string) => {
    if (sortBy === field) setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    else { setSortBy(field); setSortOrder('asc'); }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 5) next.add(id);
      return next;
    });
  };

  const handleCompare = () => {
    if (selected.size < 2) return;
    navigate(`/bid-periods/${bidPeriodId}/sequences/compare?ids=${[...selected].join(',')}`);
  };

  const handleSavePreset = async () => {
    if (!bidPeriodId || !presetName.trim()) return;
    const preset = await createFilterPreset(bidPeriodId, presetName.trim(), filters);
    setPresets((prev) => [preset, ...prev]);
    setPresetName('');
  };

  const handleLoadPreset = (preset: FilterPreset) => {
    setFilters({ ...EMPTY_FILTERS, ...preset.filters });
  };

  const handleDeletePreset = async (presetId: string) => {
    if (!bidPeriodId) return;
    await deleteFilterPreset(bidPeriodId, presetId);
    setPresets((prev) => prev.filter((p) => p.id !== presetId));
  };

  const handleClearFilters = () => setFilters({ ...EMPTY_FILTERS });

  const handleSeqSearch = async () => {
    if (!bidPeriodId || !seqSearch.trim()) return;
    setSeqSearchError('');
    setSeqSearching(true);
    try {
      const res = await listSequences(bidPeriodId, { seq_number: Number(seqSearch.trim()), limit: 1 });
      if (res.data.length > 0) {
        navigate(`/bid-periods/${bidPeriodId}/sequences/${res.data[0].id}`);
      } else {
        setSeqSearchError(`Sequence #${seqSearch.trim()} not found`);
      }
    } catch {
      setSeqSearchError('Search failed');
    } finally {
      setSeqSearching(false);
    }
  };

  const handleToggleBookmark = async (seq: Sequence) => {
    if (!bidPeriodId) return;
    const existing = bookmarks.get(seq.id);
    if (existing) {
      await deleteBookmark(bidPeriodId, existing.id);
      setBookmarks((prev) => { const m = new Map(prev); m.delete(seq.id); return m; });
    } else {
      const bm = await createBookmark(bidPeriodId, seq.id);
      setBookmarks((prev) => new Map(prev).set(seq.id, bm));
    }
  };

  const displayedSequences = showFavoritesOnly
    ? sequences.filter((s) => bookmarks.has(s.id))
    : sequences;

  const updateFilter = <K extends keyof FilterSet>(key: K, value: FilterSet[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const hasActiveFilters = filters.categories.length > 0 || !!filters.language ||
    filters.tpay_min_minutes != null || filters.tpay_max_minutes != null ||
    filters.is_turn != null || filters.layover_cities.length > 0 ||
    filters.include_deadheads != null || filters.duty_days_min != null || filters.duty_days_max != null;

  const SortIcon = ({ field }: { field: string }) => (
    <span className="text-gray-400 ml-1">
      {sortBy === field ? (sortOrder === 'asc' ? '▲' : '▼') : ''}
    </span>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <Link to={`/bid-periods/${bidPeriodId}`} className="text-sm text-blue-600 hover:underline">&larr; Back</Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">Sequences</h1>
          <p className="text-sm text-gray-500">{totalCount} total{hasActiveFilters ? ' (filtered)' : ''}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {selected.size >= 2 && (
            <button onClick={handleCompare}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
              Compare ({selected.size})
            </button>
          )}
          {selected.size > 0 && selected.size < 2 && (
            <span className="text-xs text-gray-400">Select at least 2 to compare</span>
          )}
          <button onClick={() => setCommutableOnly(!commutableOnly)}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
              commutableOnly ? 'border-green-300 bg-green-50 text-green-700' : 'border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}>
            {commutableOnly ? 'Commutable Only' : 'Commutable'}
          </button>
          <button onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
              showFavoritesOnly ? 'border-yellow-300 bg-yellow-50 text-yellow-700' : 'border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}>
            {showFavoritesOnly ? 'Showing Favorites' : 'Favorites'} ({bookmarks.size})
          </button>
          <button onClick={() => setShowFilters(!showFilters)}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
              showFilters ? 'border-blue-300 bg-blue-50 text-blue-700' :
              hasActiveFilters ? 'border-blue-300 text-blue-700' : 'border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}>
            Filters{hasActiveFilters ? ' *' : ''}
          </button>
        </div>
      </div>

      {/* Sequence number search */}
      <div className="bg-white border border-gray-200 rounded-lg p-3 flex items-center gap-2">
        <label htmlFor="seq-search" className="text-sm font-medium text-gray-700 whitespace-nowrap">Find Sequence #</label>
        <input
          id="seq-search"
          type="number"
          value={seqSearch}
          onChange={(e) => { setSeqSearch(e.target.value); setSeqSearchError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSeqSearch(); }}
          placeholder="e.g. 1234"
          className="flex-1 max-w-[200px] rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        />
        <button
          onClick={handleSeqSearch}
          disabled={seqSearching || !seqSearch.trim()}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {seqSearching ? 'Searching...' : 'Go'}
        </button>
        {seqSearchError && <span className="text-sm text-red-500">{seqSearchError}</span>}
      </div>

      {/* Filter sidebar */}
      {showFilters && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-700">Filters</h3>
            {hasActiveFilters && (
              <button onClick={handleClearFilters} className="text-xs text-blue-600 hover:underline">Clear all</button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Category</label>
              <select value={filters.categories[0] || ''} onChange={(e) => updateFilter('categories', e.target.value ? [e.target.value] : [])}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none">
                <option value="">All</option>
                <option value="777 INTL">777 INTL</option>
                <option value="787 INTL">787 INTL</option>
                <option value="NBI INTL">NBI INTL</option>
                <option value="NBD DOM">NBD DOM</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Language</label>
              <select value={filters.language || ''} onChange={(e) => updateFilter('language', e.target.value || undefined)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none">
                <option value="">Any</option>
                <option value="JP">JP</option>
                <option value="SP">SP</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Trip Type</label>
              <select
                value={filters.is_turn == null ? '' : filters.is_turn ? 'turn' : 'multi'}
                onChange={(e) => updateFilter('is_turn', e.target.value === '' ? undefined : e.target.value === 'turn')}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none">
                <option value="">Any</option>
                <option value="turn">Turns only</option>
                <option value="multi">Multi-day only</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Layover City</label>
              <input value={filters.layover_cities[0] || ''}
                onChange={(e) => updateFilter('layover_cities', e.target.value ? [e.target.value.toUpperCase()] : [])}
                placeholder="e.g. NRT"
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">TPAY Min (min)</label>
              <input type="number" value={filters.tpay_min_minutes ?? ''}
                onChange={(e) => updateFilter('tpay_min_minutes', e.target.value ? Number(e.target.value) : undefined)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">TPAY Max (min)</label>
              <input type="number" value={filters.tpay_max_minutes ?? ''}
                onChange={(e) => updateFilter('tpay_max_minutes', e.target.value ? Number(e.target.value) : undefined)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Duty Days Min</label>
              <input type="number" value={filters.duty_days_min ?? ''}
                onChange={(e) => updateFilter('duty_days_min', e.target.value ? Number(e.target.value) : undefined)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Duty Days Max</label>
              <input type="number" value={filters.duty_days_max ?? ''}
                onChange={(e) => updateFilter('duty_days_max', e.target.value ? Number(e.target.value) : undefined)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
            </div>
          </div>

          {/* Presets */}
          <div className="border-t border-gray-100 pt-3">
            <div className="flex items-center gap-2 mb-2">
              <input value={presetName} onChange={(e) => setPresetName(e.target.value)}
                placeholder="Preset name"
                className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none" />
              <button onClick={handleSavePreset} disabled={!presetName.trim()}
                className="rounded-md bg-gray-100 px-3 py-1 text-sm text-gray-700 hover:bg-gray-200 disabled:opacity-50">
                Save Preset
              </button>
            </div>
            {presets.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {presets.map((p) => (
                  <div key={p.id} className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-sm">
                    <button onClick={() => handleLoadPreset(p)} className="text-gray-700 hover:text-blue-600">
                      {p.name}
                    </button>
                    <button onClick={() => handleDeletePreset(p.id)} className="text-gray-400 hover:text-red-500 ml-1"
                      aria-label={`Delete preset ${p.name}`}>
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 bg-white text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 w-8"><span className="sr-only">Select</span></th>
                {[
                  { field: 'seq_number', label: 'SEQ' },
                  { field: 'category', label: 'Category' },
                  { field: 'ops_count', label: 'OPS' },
                  { field: 'totals.duty_days', label: 'Days' },
                  { field: 'totals.tpay_minutes', label: 'TPAY' },
                  { field: 'totals.block_minutes', label: 'Block' },
                  { field: 'totals.tafb_minutes', label: 'TAFB' },
                ].map(({ field, label }) => (
                  <th key={field} scope="col"
                    className="px-3 py-2 text-left font-medium text-gray-600 cursor-pointer hover:text-gray-900"
                    role="columnheader"
                    tabIndex={0}
                    aria-sort={sortBy === field ? (sortOrder === 'asc' ? 'ascending' : 'descending') : undefined}
                    onClick={() => toggleSort(field)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSort(field); } }}>
                    {label}<SortIcon field={field} />
                  </th>
                ))}
                <th scope="col" className="px-3 py-2 text-left font-medium text-gray-600">Layovers</th>
                <th scope="col" className="px-3 py-2 text-left font-medium text-gray-600">Dates</th>
                <th className="px-3 py-2 w-8"><span className="sr-only">Bookmark</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {displayedSequences.map((seq) => (
                <tr key={seq.id} className={`hover:bg-gray-50 ${selected.has(seq.id) ? 'bg-blue-50' : ''}`}>
                  <td className="px-3 py-2">
                    <input type="checkbox" checked={selected.has(seq.id)}
                      onChange={() => toggleSelect(seq.id)}
                      disabled={!selected.has(seq.id) && selected.size >= 5}
                      aria-label={`Select sequence ${seq.seq_number} for comparison`}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                  </td>
                  <td className="px-3 py-2 font-medium">
                    <div className="flex items-center gap-1.5">
                      <Link to={`/bid-periods/${bidPeriodId}/sequences/${seq.id}`} className="text-blue-600 hover:underline">
                        {seq.seq_number}
                      </Link>
                      {seq.eligibility === 'eligible' && (
                        <span className="text-green-500 text-xs" title="Eligible" aria-label="Eligible" role="img">&#x2713;</span>
                      )}
                      {seq.eligibility === 'eligible_no_lang_advantage' && (
                        <span className="text-yellow-500 text-xs" title="Eligible (no language advantage)" aria-label="Eligible, no language advantage" role="img">&#x26A0;</span>
                      )}
                      {seq.eligibility === 'ineligible' && (
                        <span className="text-red-500 text-xs" title="Ineligible" aria-label="Ineligible" role="img">&#x2717;</span>
                      )}
                      {seq.commute_impact && (
                        <span
                          className={`inline-block w-2.5 h-2.5 rounded-full ${
                            seq.commute_impact.impact_level === 'green' ? 'bg-green-500' :
                            seq.commute_impact.impact_level === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          title={[seq.commute_impact.first_day_note, seq.commute_impact.last_day_note].filter(Boolean).join(' | ')}
                          aria-label={`Commute impact: ${seq.commute_impact.impact_level}`}
                          role="img"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-gray-500">{seq.category || '—'}</td>
                  <td className="px-3 py-2">{seq.ops_count}</td>
                  <td className="px-3 py-2">{seq.totals.duty_days}</td>
                  <td className="px-3 py-2">{formatMinutes(seq.totals.tpay_minutes)}</td>
                  <td className="px-3 py-2">{formatMinutes(seq.totals.block_minutes)}</td>
                  <td className="px-3 py-2">{formatMinutes(seq.totals.tafb_minutes)}</td>
                  <td className="px-3 py-2 text-gray-500">{seq.layover_cities.join(', ') || '—'}</td>
                  <td className="px-3 py-2 text-gray-400 text-xs">
                    {seq.operating_dates.slice(0, 5).join(', ')}
                    {seq.operating_dates.length > 5 ? '...' : ''}
                  </td>
                  <td className="px-3 py-2">
                    <button onClick={() => handleToggleBookmark(seq)}
                      className={`text-lg leading-none ${bookmarks.has(seq.id) ? 'text-yellow-500' : 'text-gray-300 hover:text-yellow-400'}`}
                      title={bookmarks.has(seq.id) ? 'Remove bookmark' : 'Bookmark'}
                      aria-label={bookmarks.has(seq.id) ? `Remove bookmark for sequence ${seq.seq_number}` : `Bookmark sequence ${seq.seq_number}`}>
                      {bookmarks.has(seq.id) ? '\u2605' : '\u2606'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
