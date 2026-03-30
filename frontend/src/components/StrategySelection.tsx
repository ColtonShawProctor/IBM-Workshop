import { useState } from 'react';
import { BID_TEMPLATES } from '../types/templates';
import type { BidTemplate, TemplatePropertyDefault } from '../types/templates';

interface Props {
  seniorityPercentage?: number;
  onSelectTemplate: (template: BidTemplate) => void;
  onStartFromScratch: () => void;
}

// Quiz questions
const QUIZ_QUESTIONS = [
  {
    id: 'commute',
    question: 'Do you commute to your base?',
    options: [
      { label: 'Yes', value: 'yes' },
      { label: 'No', value: 'no' },
    ],
  },
  {
    id: 'priority',
    question: 'What matters most to you?',
    options: [
      { label: 'Maximum time off', value: 'time_off' },
      { label: 'Maximum pay', value: 'pay' },
      { label: 'Best trip quality', value: 'quality' },
      { label: 'Avoiding bad schedules', value: 'safe' },
    ],
  },
  {
    id: 'trip_length',
    question: 'Preferred trip length?',
    options: [
      { label: 'Day turns', value: '1' },
      { label: '2-day', value: '2' },
      { label: '3-day', value: '3' },
      { label: '4+ day', value: '4' },
      { label: 'No preference', value: 'any' },
    ],
  },
  {
    id: 'international',
    question: 'International interest?',
    options: [
      { label: "It's the dream", value: 'dream' },
      { label: 'Nice to have', value: 'nice' },
      { label: "Don't care", value: 'none' },
      { label: 'Avoid it', value: 'avoid' },
    ],
  },
];

type QuizAnswers = Record<string, string>;

function scoreTemplate(template: BidTemplate, answers: QuizAnswers): number {
  let score = 0;

  if (answers.commute === 'yes' && template.id === 'commuter_max_time_off') score += 3;
  if (answers.priority === 'time_off' && (template.id === 'commuter_max_time_off' || template.id === 'weekend_warrior')) score += 2;
  if (answers.priority === 'pay' && template.id === 'high_credit_domestic') score += 3;
  if (answers.priority === 'quality' && template.id === 'international_explorer') score += 3;
  if (answers.priority === 'safe' && template.id === 'new_fa_safe_bid') score += 3;
  if (answers.international === 'dream' && template.id === 'international_explorer') score += 3;
  if (answers.international === 'avoid' && template.id === 'high_credit_domestic') score += 1;
  if (answers.trip_length === '3' && (template.id === 'commuter_max_time_off' || template.id === 'weekend_warrior')) score += 1;
  if (answers.trip_length === '4' && template.id === 'international_explorer') score += 1;

  return score;
}

export default function StrategySelection({ seniorityPercentage, onSelectTemplate, onStartFromScratch }: Props) {
  const [showQuiz, setShowQuiz] = useState(false);
  const [quizStep, setQuizStep] = useState(0);
  const [answers, setAnswers] = useState<QuizAnswers>({});
  const [recommendedId, setRecommendedId] = useState<string | null>(null);

  const handleQuizAnswer = (questionId: string, value: string) => {
    const newAnswers = { ...answers, [questionId]: value };
    setAnswers(newAnswers);

    if (quizStep < QUIZ_QUESTIONS.length - 1) {
      setQuizStep(quizStep + 1);
    } else {
      // Score all templates
      let bestId = BID_TEMPLATES[0].id;
      let bestScore = -1;
      for (const t of BID_TEMPLATES) {
        const s = scoreTemplate(t, newAnswers);
        if (s > bestScore) {
          bestScore = s;
          bestId = t.id;
        }
      }
      setRecommendedId(bestId);
      setShowQuiz(false);
    }
  };

  const resetQuiz = () => {
    setQuizStep(0);
    setAnswers({});
    setRecommendedId(null);
    setShowQuiz(true);
  };

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Choose a Strategy</h3>
        <p className="text-sm text-gray-500 mt-1">
          Pick a starting point that matches how you like to fly. You'll customize everything in the next step.
        </p>
      </div>

      {/* Help Me Choose */}
      {!showQuiz && (
        <button
          type="button"
          onClick={resetQuiz}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          {recommendedId ? 'Retake quiz' : 'Not sure? Help me choose →'}
        </button>
      )}

      {/* Quiz Modal/Inline */}
      {showQuiz && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-blue-900">
              Question {quizStep + 1} of {QUIZ_QUESTIONS.length}
            </h4>
            <button
              type="button"
              onClick={() => setShowQuiz(false)}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              Skip
            </button>
          </div>
          <p className="text-sm font-medium text-gray-900">{QUIZ_QUESTIONS[quizStep].question}</p>
          <div className="flex flex-wrap gap-2">
            {QUIZ_QUESTIONS[quizStep].options.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleQuizAnswer(QUIZ_QUESTIONS[quizStep].id, opt.value)}
                className="px-4 py-2 rounded-lg border border-blue-200 text-sm font-medium text-blue-800 hover:bg-blue-100 transition-colors"
              >
                {opt.label}
              </button>
            ))}
          </div>
          {/* Progress dots */}
          <div className="flex gap-1.5">
            {QUIZ_QUESTIONS.map((_, i) => (
              <div
                key={i}
                className={`h-1.5 flex-1 rounded-full ${i <= quizStep ? 'bg-blue-400' : 'bg-blue-200'}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Template grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {BID_TEMPLATES.map(template => {
          const isRecommended = recommendedId === template.id;
          const senMatch = seniorityPercentage !== undefined
            && seniorityPercentage >= template.seniorityRange[0]
            && seniorityPercentage <= template.seniorityRange[1];

          return (
            <button
              key={template.id}
              type="button"
              onClick={() => onSelectTemplate(template)}
              className={`relative text-left p-4 rounded-lg border-2 transition-all hover:shadow-md ${
                isRecommended
                  ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                  : 'border-gray-200 bg-white hover:border-blue-300'
              }`}
            >
              {isRecommended && (
                <span className="absolute -top-2.5 left-3 px-2 py-0.5 text-xs font-semibold bg-blue-600 text-white rounded-full">
                  Recommended
                </span>
              )}

              <div className="flex items-start gap-3">
                <span className="text-2xl">{template.icon}</span>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-semibold text-gray-900">{template.name}</h4>
                  <p className="text-xs text-gray-500 mt-0.5">{template.description}</p>

                  <div className="mt-3 space-y-1">
                    <div className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                      {template.stats.targetTripLength}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                      {template.stats.daysOffPattern}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                      {template.stats.creditRange}
                    </div>
                  </div>

                  {senMatch && (
                    <span className="inline-block mt-2 text-xs text-green-700 bg-green-50 px-2 py-0.5 rounded-full">
                      Good for {template.seniorityRange[0]}-{template.seniorityRange[1]}% seniority
                    </span>
                  )}
                </div>
              </div>
            </button>
          );
        })}

        {/* Start from Scratch */}
        <button
          type="button"
          onClick={onStartFromScratch}
          className="text-left p-4 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-white transition-all"
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl">⚙️</span>
            <div>
              <h4 className="text-sm font-semibold text-gray-700">Start from Scratch</h4>
              <p className="text-xs text-gray-500 mt-0.5">Build your bid property by property. For experienced FAs who know exactly what they want.</p>
            </div>
          </div>
        </button>
      </div>
    </div>
  );
}
