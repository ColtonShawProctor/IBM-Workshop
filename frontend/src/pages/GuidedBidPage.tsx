import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getBidPeriod, getMe, guidedBuild } from '../lib/api';
import type { GuidedCriteria, GuidedBuildResult } from '../lib/api';
import TripPickerStep from '../components/TripPickerStep';
import BuildBidStep from '../components/BuildBidStep';

const STEP_LABELS = ['Pick Trips', 'Build Bid'] as const;

const DEFAULT_CRITERIA: GuidedCriteria = {
  trip_lengths: [3, 4],
  preferred_cities: [],
  avoided_cities: [],
  report_earliest_minutes: null,    // no hard cutoff — hotel model handles it
  release_latest_minutes: null,     // no hard cutoff — hotel model handles it
  credit_min_minutes: 5100, // 85h
  credit_max_minutes: 5400, // 90h
  days_off: [],
  avoid_redeyes: true,
  schedule_preference: 'best',
};

export default function GuidedBidPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const navigate = useNavigate();

  // Skip criteria step — go straight to trip picker (step 0 = picker, step 1 = build)
  const [step, setStep] = useState(0);
  const [criteria, setCriteria] = useState<GuidedCriteria>(DEFAULT_CRITERIA);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [buildResult, setBuildResult] = useState<GuidedBuildResult | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);

  // Load bid period info
  const { data: bidPeriod } = useQuery({
    queryKey: ['bidPeriod', bidPeriodId],
    queryFn: () => getBidPeriod(bidPeriodId!),
    enabled: !!bidPeriodId,
  });

  // Load user profile to populate criteria from preferences
  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const isCommuter = !!user?.profile?.commute_from;
  const commuteFrom = user?.profile?.commute_from || '';
  const totalDates = bidPeriod?.total_dates || 30;

  // Auto-populate criteria from user preferences (zero-config)
  useEffect(() => {
    if (!user) return;
    const prefs = user.default_preferences;
    if (!prefs) return;
    setCriteria(prev => ({
      ...prev,
      preferred_cities: prefs.preferred_layover_cities || prev.preferred_cities,
      avoided_cities: prefs.avoided_layover_cities || prev.avoided_cities,
      report_earliest_minutes: prefs.report_earliest_minutes ?? null,
      release_latest_minutes: prefs.release_latest_minutes ?? null,
      credit_min_minutes: prefs.tpay_min_minutes || prev.credit_min_minutes,
      credit_max_minutes: prefs.tpay_max_minutes || prev.credit_max_minutes,
      avoid_redeyes: prefs.avoid_redeyes ?? true,
    }));
  }, [user]);

  const handleBuild = useCallback(async (ids: string[]) => {
    setSelectedIds(ids);
    setStep(1);
    setIsBuilding(true);
    setBuildResult(null);
    window.scrollTo(0, 0);

    try {
      const result = await guidedBuild(bidPeriodId!, ids, criteria);
      setBuildResult(result);
    } catch (err) {
      console.error('Build failed:', err);
      setBuildResult(null);
    } finally {
      setIsBuilding(false);
    }
  }, [bidPeriodId, criteria]);

  const handleStartOver = useCallback(() => {
    setSelectedIds([]);
    setBuildResult(null);
    setIsBuilding(false);
    setStep(0);
    window.scrollTo(0, 0);
  }, []);

  const handleBackToTrips = useCallback(() => {
    setStep(0);
    setBuildResult(null);
    setIsBuilding(false);
    window.scrollTo(0, 0);
  }, []);

  if (!bidPeriodId) {
    return <div className="p-8 text-center text-gray-500">No bid period selected.</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Step content */}
      <div className="max-w-4xl mx-auto px-4 py-6">
        {step === 0 && (
          <TripPickerStep
            bidPeriodId={bidPeriodId}
            criteria={criteria}
            onBack={() => navigate('/')}
            onBuild={handleBuild}
            isCommuter={isCommuter}
          />
        )}

        {step === 1 && (
          <BuildBidStep
            bidPeriodId={bidPeriodId}
            selectedIds={selectedIds}
            criteria={criteria}
            buildResult={buildResult}
            isBuilding={isBuilding}
            onBack={handleBackToTrips}
            onStartOver={handleStartOver}
          />
        )}
      </div>
    </div>
  );
}
