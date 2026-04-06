import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { updateMe, updatePreferences } from '../lib/api';

const CITY_OPTIONS = [
  'SFO', 'DEN', 'BOS', 'SAN', 'PDX', 'SEA', 'AUS', 'SNA', 'LAX',
  'HNL', 'MIA', 'TPA', 'LHR', 'NRT', 'CDG', 'FCO', 'SJU',
  'PHX', 'LAS', 'MCO', 'ATL', 'DFW', 'CLT', 'RDU', 'EWR', 'IAH',
];

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const profile = user?.profile;
  const prefs = user?.default_preferences;

  const [seniorityNumber, setSeniorityNumber] = useState(profile?.seniority_number || 1170);
  const [totalFas, setTotalFas] = useState(profile?.total_base_fas || 2323);
  const [commuteFrom, setCommuteFrom] = useState(profile?.commute_from || 'LGA');
  const [loveCities, setLoveCities] = useState<string[]>(prefs?.preferred_layover_cities || ['SFO', 'DEN', 'BOS', 'SAN']);
  const [avoidCities, setAvoidCities] = useState<string[]>(prefs?.avoided_layover_cities || ['CLT', 'RDU']);
  const [reportEarliest, setReportEarliest] = useState(prefs?.report_earliest_minutes ?? 540);
  const [releaseLatest, setReleaseLatest] = useState(prefs?.release_latest_minutes ?? 1140);
  const [creditMin, setCreditMin] = useState(prefs?.tpay_min_minutes ? Math.round(prefs.tpay_min_minutes / 60) : 85);
  const [creditMax, setCreditMax] = useState(prefs?.tpay_max_minutes ? Math.round(prefs.tpay_max_minutes / 60) : 90);
  const [avoidRedeyes, setAvoidRedeyes] = useState(prefs?.avoid_redeyes ?? true);
  const [clusterTrips, setClusterTrips] = useState(prefs?.cluster_trips ?? true);

  const [showAdvanced, setShowAdvanced] = useState(false);

  function toggleCity(city: string, list: string[], setList: (v: string[]) => void) {
    if (list.includes(city)) {
      setList(list.filter(c => c !== city));
    } else {
      setList([...list, city]);
    }
  }

  function minutesToTime(mins: number) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await updateMe({
        profile: {
          ...profile,
          seniority_number: seniorityNumber,
          total_base_fas: totalFas,
          commute_from: commuteFrom,
        } as any,
      });
      await updatePreferences({
        preferred_layover_cities: loveCities,
        avoided_layover_cities: avoidCities,
        report_earliest_minutes: reportEarliest,
        release_latest_minutes: releaseLatest,
        tpay_min_minutes: creditMin * 60,
        tpay_max_minutes: creditMax * 60,
        avoid_redeyes: avoidRedeyes,
        cluster_trips: clusterTrips,
      });
      await refreshUser();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-xl mx-auto px-4 pt-10 pb-16">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <button onClick={() => navigate('/')} className="text-sm text-gray-400 hover:text-gray-600">
            Back to home
          </button>
        </div>

        <p className="text-sm text-gray-500 mb-6">
          All settings are optional — defaults work great for your profile.
        </p>

        <div className="space-y-6">
          {/* Seniority */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Seniority</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Your line number</label>
                <input
                  type="number"
                  value={seniorityNumber}
                  onChange={(e) => setSeniorityNumber(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Total FAs at base</label>
                <input
                  type="number"
                  value={totalFas}
                  onChange={(e) => setTotalFas(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
          </section>

          {/* Commute */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Commute</h2>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Commute from (IATA code)</label>
              <input
                type="text"
                value={commuteFrom}
                onChange={(e) => setCommuteFrom(e.target.value.toUpperCase())}
                maxLength={3}
                className="w-24 rounded-lg border border-gray-300 px-3 py-2 text-sm uppercase"
              />
            </div>
          </section>

          {/* Love cities */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Love Cities</h2>
            <div className="flex flex-wrap gap-2">
              {CITY_OPTIONS.filter(c => !avoidCities.includes(c)).map(city => (
                <button
                  key={city}
                  onClick={() => toggleCity(city, loveCities, setLoveCities)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    loveCities.includes(city)
                      ? 'bg-blue-100 text-blue-700 border border-blue-300'
                      : 'bg-gray-100 text-gray-500 border border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {city}
                </button>
              ))}
            </div>
          </section>

          {/* Avoid cities */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Avoid Cities</h2>
            <div className="flex flex-wrap gap-2">
              {CITY_OPTIONS.filter(c => !loveCities.includes(c)).map(city => (
                <button
                  key={city}
                  onClick={() => toggleCity(city, avoidCities, setAvoidCities)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    avoidCities.includes(city)
                      ? 'bg-red-100 text-red-700 border border-red-300'
                      : 'bg-gray-100 text-gray-500 border border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {city}
                </button>
              ))}
            </div>
          </section>

          {/* Time preferences */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Time Preferences</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Report after</label>
                <select
                  value={reportEarliest}
                  onChange={(e) => setReportEarliest(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  {[360, 420, 480, 540, 600, 660, 720].map(m => (
                    <option key={m} value={m}>{minutesToTime(m)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Release by</label>
                <select
                  value={releaseLatest}
                  onChange={(e) => setReleaseLatest(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  {[1020, 1080, 1140, 1200, 1260, 1320].map(m => (
                    <option key={m} value={m}>{minutesToTime(m)}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {/* Credit target */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Credit Target</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Minimum hours</label>
                <input
                  type="number"
                  value={creditMin}
                  onChange={(e) => setCreditMin(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Maximum hours</label>
                <input
                  type="number"
                  value={creditMax}
                  onChange={(e) => setCreditMax(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
          </section>

          {/* Toggles */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Preferences</h2>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={clusterTrips}
                  onChange={(e) => setClusterTrips(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600"
                />
                <span className="text-sm text-gray-700">Compact schedule (cluster trips together)</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={avoidRedeyes}
                  onChange={(e) => setAvoidRedeyes(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600"
                />
                <span className="text-sm text-gray-700">Avoid red-eyes</span>
              </label>
            </div>
          </section>

          {/* Advanced */}
          <div>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              {showAdvanced ? 'Hide' : 'Show'} advanced settings
            </button>
            {showAdvanced && (
              <div className="mt-3 bg-gray-50 rounded-xl border border-gray-200 p-5 text-xs text-gray-500 space-y-2">
                <p>These are automatically configured for your profile. Only change them if you know what you're doing.</p>
                <ul className="space-y-1 ml-4 list-disc">
                  <li>Scoring weights: Commuter-optimized (report/release weighted high)</li>
                  <li>Strategy: Progressive relaxation across 7 layers</li>
                  <li>Layer 1 mode: Lottery ticket (enter manually)</li>
                  <li>Min trip length L1-L3: 3 days</li>
                  <li>Min trip length L4-L7: 2 days</li>
                  <li>Rest waivers: Waived to FAR minimums</li>
                  <li>Block hour limit: 30h / 7 days (standard)</li>
                  <li>Avoid red-eyes and ODANs: Always on</li>
                </ul>
              </div>
            )}
          </div>

          {/* Save */}
          <div className="flex items-center gap-4 pt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            {saved && <span className="text-sm text-green-600">Saved!</span>}
            <button
              onClick={() => navigate('/')}
              className="text-sm text-gray-400 hover:text-gray-600"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
