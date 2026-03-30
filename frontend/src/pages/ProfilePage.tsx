import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { updateMe } from '../lib/api';

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const profile = user?.profile;

  const [form, setForm] = useState({
    display_name: profile?.display_name || '',
    base_city: profile?.base_city || '',
    commute_from: profile?.commute_from || '',
    seniority_number: String(profile?.seniority_number || ''),
    total_base_fas: String(profile?.total_base_fas || ''),
    position_min: String(profile?.position_min || '1'),
    position_max: String(profile?.position_max || '4'),
    language_qualifications: (profile?.language_qualifications || []).join(', '),
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const update = (field: string, value: string) => setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      const langs = form.language_qualifications.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
      await updateMe({
        profile: {
          display_name: form.display_name,
          base_city: form.base_city,
          commute_from: form.commute_from || undefined,
          seniority_number: Number(form.seniority_number),
          total_base_fas: Number(form.total_base_fas),
          position_min: Number(form.position_min),
          position_max: Number(form.position_max),
          language_qualifications: langs,
        },
      });
      await refreshUser();
      setMessage('Profile updated');
    } catch {
      setMessage('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Profile</h1>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white p-6 rounded-lg border border-gray-200">
        {message && (
          <div className={`rounded p-3 text-sm ${message.includes('Failed') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
            {message}
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700">Display Name</label>
          <input value={form.display_name} onChange={(e) => update('display_name', e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Base City</label>
            <input value={form.base_city} onChange={(e) => update('base_city', e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Commute From</label>
            <input value={form.commute_from} onChange={(e) => update('commute_from', e.target.value.toUpperCase())}
              placeholder="e.g. DEN"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Seniority #</label>
            <input type="number" value={form.seniority_number} onChange={(e) => update('seniority_number', e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Total FAs at Base</label>
            <input type="number" value={form.total_base_fas} onChange={(e) => update('total_base_fas', e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Languages</label>
            <input value={form.language_qualifications} onChange={(e) => update('language_qualifications', e.target.value)}
              placeholder="JP, SP"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Position Min</label>
            <input type="number" value={form.position_min} onChange={(e) => update('position_min', e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Position Max</label>
            <input type="number" value={form.position_max} onChange={(e) => update('position_max', e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none" />
          </div>
        </div>
        <button type="submit" disabled={saving}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </form>
    </div>
  );
}
