import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { register, updatePreferences } from '../lib/api';

const STEPS = ['Account', 'Profile', 'Preferences'];

export default function RegisterPage() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    email: '',
    password: '',
    display_name: '',
    base_city: 'ORD',
    commute_from: '',
    seniority_percentage: '',
    position_min: '1',
    position_max: '4',
    language_qualifications: '',
  });
  const [prefs, setPrefs] = useState({
    preferred_days_off: '',
    preferred_layover_cities: '',
    avoided_layover_cities: '',
    tpay_min_minutes: '',
    tpay_max_minutes: '',
    preferred_equipment: '',
    avoid_redeyes: false,
    prefer_turns: '',
    cluster_trips: false,
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuth();
  const navigate = useNavigate();

  const update = (field: string, value: string) => setForm((f) => ({ ...f, [field]: value }));
  const updatePref = (field: string, value: string | boolean) => setPrefs((p) => ({ ...p, [field]: value }));

  const handleCreateAccount = async () => {
    setError('');
    setLoading(true);
    try {
      const langs = form.language_qualifications
        .split(',')
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      const res = await register({
        email: form.email,
        password: form.password,
        profile: {
          display_name: form.display_name,
          base_city: form.base_city,
          commute_from: form.commute_from || undefined,
          seniority_percentage: form.seniority_percentage ? Number(form.seniority_percentage) : undefined,
          position_min: Number(form.position_min),
          position_max: Number(form.position_max),
          language_qualifications: langs,
        },
      });
      setAuth(res.access_token, res.refresh_token, res.user);
      setStep(2); // Skip to preferences since profile was in registration
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { detail?: string | Array<{ msg: string }> } } })?.response?.data;
      const detail = data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : 'Registration failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSavePreferences = async () => {
    setError('');
    setLoading(true);
    try {
      const daysOff = prefs.preferred_days_off.split(',').map((s) => parseInt(s.trim())).filter((n) => !isNaN(n));
      const prefCities = prefs.preferred_layover_cities.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
      const avoidCities = prefs.avoided_layover_cities.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
      const equipment = prefs.preferred_equipment.split(',').map((s) => s.trim()).filter(Boolean);

      await updatePreferences({
        preferred_days_off: daysOff,
        preferred_layover_cities: prefCities,
        avoided_layover_cities: avoidCities,
        tpay_min_minutes: prefs.tpay_min_minutes ? Number(prefs.tpay_min_minutes) : undefined,
        tpay_max_minutes: prefs.tpay_max_minutes ? Number(prefs.tpay_max_minutes) : undefined,
        preferred_equipment: equipment,
        avoid_redeyes: prefs.avoid_redeyes,
        prefer_turns: prefs.prefer_turns === '' ? undefined : prefs.prefer_turns === 'true',
        cluster_trips: prefs.cluster_trips,
      });
      navigate('/');
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { detail?: string | Array<{ msg: string }> } } })?.response?.data;
      const detail = data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : 'Failed to save preferences';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 py-8">
      <div className="w-full max-w-lg px-4 sm:px-0 space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900">BidPilot</h1>
          <p className="mt-1 text-sm text-gray-500">Set up your account</p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium ${
                i <= step ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                {i + 1}
              </div>
              <span className={`hidden sm:inline text-sm ${i <= step ? 'text-gray-900' : 'text-gray-400'}`}>{s}</span>
              {i < STEPS.length - 1 && <div className="w-8 h-px bg-gray-300 mx-1" />}
            </div>
          ))}
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 space-y-4">
          {error && <div className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</div>}

          {/* Step 0: Account */}
          {step === 0 && (
            <>
              <h2 className="text-lg font-medium text-gray-900">Create Account</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700">Display Name</label>
                <input required value={form.display_name} onChange={(e) => update('display_name', e.target.value)} className={inputClass} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Email</label>
                <input type="email" required value={form.email} onChange={(e) => update('email', e.target.value)} className={inputClass} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Password</label>
                <input type="password" required minLength={8} value={form.password} onChange={(e) => update('password', e.target.value)} className={inputClass} />
              </div>
              <button onClick={() => setStep(1)} disabled={!form.email || !form.password || !form.display_name}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                Next: Profile Setup
              </button>
            </>
          )}

          {/* Step 1: Profile */}
          {step === 1 && (
            <>
              <h2 className="text-lg font-medium text-gray-900">Your Profile</h2>
              <p className="text-sm text-gray-500">Tell us about your scheduling situation.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Base City (IATA)</label>
                  <input required value={form.base_city} onChange={(e) => update('base_city', e.target.value)} placeholder="ORD" className={inputClass} />
                  <p className="text-xs text-gray-400 mt-0.5">Your assigned crew base</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Commute From (IATA)</label>
                  <input value={form.commute_from} onChange={(e) => update('commute_from', e.target.value.toUpperCase())} placeholder="DEN" maxLength={3} className={inputClass} />
                  <p className="text-xs text-gray-400 mt-0.5">Leave blank if you live in base</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Seniority %</label>
                  <input type="number" step="0.1" min="0" max="100" value={form.seniority_percentage} onChange={(e) => update('seniority_percentage', e.target.value)} placeholder="e.g. 30.0" className={inputClass} />
                  <p className="text-xs text-gray-400 mt-0.5">From your PBS portal dashboard</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Language Quals</label>
                  <input value={form.language_qualifications} onChange={(e) => update('language_qualifications', e.target.value)} placeholder="JP, SP" className={inputClass} />
                  <p className="text-xs text-gray-400 mt-0.5">Comma-separated, if any</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Position Min</label>
                  <input type="number" required value={form.position_min} onChange={(e) => update('position_min', e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Position Max</label>
                  <input type="number" required value={form.position_max} onChange={(e) => update('position_max', e.target.value)} className={inputClass} />
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setStep(0)} className="flex-1 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                  Back
                </button>
                <button onClick={handleCreateAccount} disabled={loading}
                  className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                  {loading ? 'Creating...' : 'Next: Preferences'}
                </button>
              </div>
            </>
          )}

          {/* Step 2: Preferences */}
          {step === 2 && (
            <>
              <h2 className="text-lg font-medium text-gray-900">Default Preferences</h2>
              <p className="text-sm text-gray-500">These drive the optimizer. You can change them per bid period later.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700">Preferred Days Off</label>
                  <input value={prefs.preferred_days_off} onChange={(e) => updatePref('preferred_days_off', e.target.value)}
                    placeholder="1, 15, 20" className={inputClass} />
                  <p className="text-xs text-gray-400 mt-0.5">Comma-separated day-of-month numbers</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Preferred Layover Cities</label>
                  <input value={prefs.preferred_layover_cities} onChange={(e) => updatePref('preferred_layover_cities', e.target.value)}
                    placeholder="NRT, LHR" className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Avoided Layover Cities</label>
                  <input value={prefs.avoided_layover_cities} onChange={(e) => updatePref('avoided_layover_cities', e.target.value)}
                    placeholder="PEK" className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">TPAY Min (minutes)</label>
                  <input type="number" value={prefs.tpay_min_minutes} onChange={(e) => updatePref('tpay_min_minutes', e.target.value)}
                    className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">TPAY Max (minutes)</label>
                  <input type="number" value={prefs.tpay_max_minutes} onChange={(e) => updatePref('tpay_max_minutes', e.target.value)}
                    className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Preferred Equipment</label>
                  <input value={prefs.preferred_equipment} onChange={(e) => updatePref('preferred_equipment', e.target.value)}
                    placeholder="777, 787" className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Trip Preference</label>
                  <select value={prefs.prefer_turns} onChange={(e) => updatePref('prefer_turns', e.target.value)}
                    className={inputClass}>
                    <option value="">No preference</option>
                    <option value="true">Prefer turns/day trips</option>
                    <option value="false">Prefer multi-day trips</option>
                  </select>
                </div>
                <div className="sm:col-span-2 flex flex-wrap gap-4 sm:gap-6">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={prefs.avoid_redeyes}
                      onChange={(e) => updatePref('avoid_redeyes', e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    <span className="text-sm text-gray-700">Avoid red-eyes</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={prefs.cluster_trips}
                      onChange={(e) => updatePref('cluster_trips', e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    <span className="text-sm text-gray-700">Cluster trips together</span>
                  </label>
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => navigate('/')}
                  className="flex-1 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                  Skip for now
                </button>
                <button onClick={handleSavePreferences} disabled={loading}
                  className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                  {loading ? 'Saving...' : 'Save & Go to Dashboard'}
                </button>
              </div>
            </>
          )}
        </div>

        {step === 0 && (
          <p className="text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-600 hover:underline">Sign in</Link>
          </p>
        )}
      </div>
    </div>
  );
}
