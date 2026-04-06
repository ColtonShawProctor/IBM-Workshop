import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getBidPeriod, getMe, guidedBuild } from '../lib/api';
import type { GuidedCriteria, GuidedBuildResult } from '../lib/api';
import CriteriaStep from '../components/CriteriaStep';
import TripPickerStep from '../components/TripPickerStep';
import BuildBidStep from '../components/BuildBidStep';

const STEP_LABELS = ['Set Criteria', 'Pick Trips', 'Build Bid'] as const;

const DEFAULT_CRITERIA: GuidedCriteria = {
  trip_lengths: [3, 4],
  preferred_cities: [],
  avoided_cities: [],
  report_earliest_minutes: null,
  release_latest_minutes: null,
  credit_min_minutes: 5100, // 85h
  credit_max_minutes: 5400, // 90h
  days_off: [],
  avoid_redeyes: true,
  schedule_preference: 'best',
};

export default function GuidedBidPage() {
  const { bidPeriodId } = useParams<{ bidPeriodId: string }>();
  const navigate = useNavigate();

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

  // Load user profile for commuter detection
  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const isCommuter = !!user?.profile?.commute_from;
  const commuteFrom = user?.profile?.commute_from || '';
  const totalDates = bidPeriod?.total_dates || 30;

  // Pre-populate report time for commuters
  useEffect(() => {
    if (isCommuter && criteria.report_earliest_minutes === null) {
      setCriteria(prev => ({ ...prev, report_earliest_minutes: 540 })); // 9 AM default
    }
  }, [isCommuter]);

  const handleCriteriaChange = useCallback((newCriteria: GuidedCriteria) => {
    setCriteria(newCriteria);
  }, []);

  const handleGoToStep2 = useCallback(() => {
    setStep(1);
    window.scrollTo(0, 0);
  }, []);

  const handleBackToStep1 = useCallback(() => {
    setStep(0);
    window.scrollTo(0, 0);
  }, []);

  const handleBuild = useCallback(async (ids: string[]) => {
    setSelectedIds(ids);
    setStep(2);
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
    setCriteria(DEFAULT_CRITERIA);
    setSelectedIds([]);
    setBuildResult(null);
    setIsBuilding(false);
    setStep(0);
    window.scrollTo(0, 0);
  }, []);

  const handleBackToStep2 = useCallback(() => {
    setStep(1);
    setBuildResult(null);
    setIsBuilding(false);
    window.scrollTo(0, 0);
  }, []);

  if (!bidPeriodId) {
    return <div className="p-8 text-center text-gray-500">No bid period selected.</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <button
                onClick={() => navigate(`/bid-periods/${bidPeriodId}`)}
                className="text-sm text-blue-600 hover:text-blue-800 mb-1"
              >
                &larr; Back to {bidPeriod?.name || 'Bid Period'}
              </button>
              <h1 className="text-lg font-bold text-gray-900">Build Your Bid</h1>
            </div>

            {/* Step indicator */}
            <div className="flex items-center gap-2">
              {STEP_LABELS.map((label, i) => (
                <div key={label} className="flex items-center gap-2">
                  {i > 0 && (
                    <div className={`w-8 h-0.5 ${i <= step ? 'bg-blue-500' : 'bg-gray-200'}`} />
                  )}
                  <div className="flex items-center gap-1.5">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        i < step
                          ? 'bg-blue-600 text-white'
                          : i === step
                            ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-500'
                            : 'bg-gray-100 text-gray-400'
                      }`}
                    >
                      {i < step ? '✓' : i + 1}
                    </div>
                    <span
                      className={`text-xs font-medium hidden sm:inline ${
                        i === step ? 'text-blue-700' : 'text-gray-400'
                      }`}
                    >
                      {label}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Step content */}
      <div className="max-w-4xl mx-auto px-4 py-6">
        {step === 0 && (
          <CriteriaStep
            bidPeriodId={bidPeriodId}
            criteria={criteria}
            onCriteriaChange={handleCriteriaChange}
            onNext={handleGoToStep2}
            isCommuter={isCommuter}
            commuteFrom={commuteFrom}
            totalDates={totalDates}
          />
        )}

        {step === 1 && (
          <TripPickerStep
            bidPeriodId={bidPeriodId}
            criteria={criteria}
            onBack={handleBackToStep1}
            onBuild={handleBuild}
            isCommuter={isCommuter}
          />
        )}

        {step === 2 && (
          <BuildBidStep
            bidPeriodId={bidPeriodId}
            selectedIds={selectedIds}
            criteria={criteria}
            buildResult={buildResult}
            isBuilding={isBuilding}
            onBack={handleBackToStep2}
            onStartOver={handleStartOver}
          />
        )}
      </div>
    </div>
  );
}
