/**
 * QuizResult.jsx
 *
 * OWNER: Member 2 (Learning Management).
 * Renders the score, summary statistics, and question-by-question review
 * post-submission following docs/DESIGN_GUIDELINES.md.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Award,
  CheckCircle2,
  Clock,
  RotateCcw,
  XCircle,
} from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ProgressBar,
  Spinner,
} from '../../components/ui';
import { getAttempt } from '../../api/quizzes';

export default function QuizResult() {
  const { attemptId } = useParams();
  const navigate = useNavigate();

  const [attempt, setAttempt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAttempt = useCallback(async () => {
    if (!attemptId) return;
    setLoading(true);
    setError(null);

    try {
      const res = await getAttempt(attemptId);
      const data = res?.data || res;
      setAttempt(data);
    } catch (err) {
      console.error('Failed to load quiz attempt result:', err);
      const detail = err?.response?.data?.detail || err?.detail || 'Could not load quiz results.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    loadAttempt();
  }, [loadAttempt]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-sm text-muted">Calculating and loading your results...</p>
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div>
        <PageHeader title="Result Unavailable" subtitle="Could not locate this attempt record." />
        <EmptyState
          title="Attempt Not Found"
          description={error || 'No attempt data found.'}
          action={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={loadAttempt}>
                Retry Loading
              </Button>
              <Link to="/courses">
                <Button variant="ghost">Browse Courses</Button>
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  const score = Math.round(attempt.score ?? 0);
  const isPassing = score >= 70;
  const total = attempt.total_questions || (attempt.answers || []).length || 0;
  const correct = attempt.correct_count ?? 0;
  const durationMinutes = Math.floor((attempt.duration_seconds || 0) / 60);
  const durationSeconds = (attempt.duration_seconds || 0) % 60;
  const formattedDuration = `${durationMinutes}m ${durationSeconds < 10 ? '0' : ''}${durationSeconds}s`;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4 dark:border-[#242B35]">
        <div>
          <Link
            to="/courses"
            className="inline-flex items-center gap-1 text-xs text-muted hover:text-body dark:hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Course Catalog
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-ink dark:text-white">
            {attempt.quiz_title || 'Quiz Results & Review'}
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {attempt.quiz_id && (
            <Link to={`/quiz/${attempt.quiz_id}`}>
              <Button variant="secondary" size="md">
                <RotateCcw className="h-4 w-4" />
                Retake Quiz
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Summary Score Card */}
      <Card className="grid grid-cols-1 gap-6 p-6 md:grid-cols-3">
        {/* Score Column */}
        <div className="flex flex-col items-center justify-center border-b border-line pb-6 text-center md:border-b-0 md:border-r md:pb-0 md:pr-6 dark:border-[#242B35]">
          <div className="text-4xl font-bold tracking-tight text-ink dark:text-white">
            {score}%
          </div>
          <div className="mt-2">
            <Badge tone={isPassing ? 'success' : 'medium'}>
              {isPassing ? 'PASSED' : 'NEEDS PRACTICE'}
            </Badge>
          </div>
          <p className="mt-2 text-xs text-muted">
            {isPassing
              ? 'Great work! You demonstrated solid mastery of these concepts.'
              : 'Keep practicing! Review the explanations below to strengthen your understanding.'}
          </p>
        </div>

        {/* Stats Column */}
        <div className="space-y-4 md:col-span-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded border border-line bg-canvas p-3 dark:border-[#2D3643] dark:bg-[#1C222B]">
              <span className="label">Accuracy</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-xl font-semibold text-ink dark:text-white">
                  {correct} / {total}
                </span>
                <span className="text-xs text-muted">questions</span>
              </div>
            </div>

            <div className="rounded border border-line bg-canvas p-3 dark:border-[#2D3643] dark:bg-[#1C222B]">
              <span className="label">Time Taken</span>
              <div className="mt-1 flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-muted" />
                <span className="text-xl font-semibold text-ink dark:text-white">
                  {formattedDuration}
                </span>
              </div>
            </div>
          </div>

          <div>
            <ProgressBar
              value={correct}
              max={total}
              tone={isPassing ? 'easy' : 'medium'}
              label="Correct Answers Ratio"
              showValue={false}
            />
          </div>
        </div>
      </Card>

      {/* Detailed Question Review Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink dark:text-white">
            Question Review ({total})
          </h2>
          <span className="text-xs text-muted">
            Correct answers and explanations are highlighted below.
          </span>
        </div>

        {(!attempt.answers || attempt.answers.length === 0) ? (
          <EmptyState
            title="No questions recorded"
            description="There are no answered questions recorded for this attempt."
          />
        ) : (
          <div className="space-y-3">
            {attempt.answers.map((item, idx) => {
              const isCorrect = item.is_correct;
              return (
                <Card key={idx} className="p-5">
                  {/* Question header */}
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <span className="label">Q{idx + 1}</span>
                      <Badge tone={isCorrect ? 'success' : 'hard'}>
                        {isCorrect ? (
                          <span className="inline-flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3" /> Correct
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1">
                            <XCircle className="h-3 w-3" /> Incorrect
                          </span>
                        )}
                      </Badge>
                    </div>

                    {item.topic_tag && (
                      <span className="font-mono text-2xs text-muted">
                        {item.topic_tag}
                      </span>
                    )}
                  </div>

                  {/* Prompt */}
                  <div className="mb-3 text-sm font-semibold text-ink dark:text-white">
                    {item.prompt}
                  </div>

                  {/* User Answer vs Correct Answer */}
                  <div className="mb-3 grid grid-cols-1 gap-2 rounded border border-line bg-canvas p-3 sm:grid-cols-2 dark:border-[#2D3643] dark:bg-[#1C222B]">
                    <div>
                      <span className="text-2xs font-semibold uppercase tracking-wider text-muted">
                        Your Answer:
                      </span>
                      <p
                        className={`mt-0.5 text-sm ${
                          isCorrect
                            ? 'font-medium text-easy dark:text-easy'
                            : 'font-medium text-hard dark:text-hard'
                        }`}
                      >
                        {item.user_answer ? item.user_answer : <span className="italic text-muted">(No answer provided)</span>}
                      </p>
                    </div>

                    {!isCorrect && (
                      <div>
                        <span className="text-2xs font-semibold uppercase tracking-wider text-muted">
                          Correct Answer:
                        </span>
                        <p className="mt-0.5 text-sm font-medium text-easy dark:text-easy">
                          {item.correct_answer}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Explanation */}
                  {item.explanation && (
                    <div className="rounded border-l-2 border-primary-600 bg-primary-50/50 p-3 text-xs leading-relaxed text-body dark:bg-primary-950/20 dark:text-[#C6CDD6]">
                      <span className="font-semibold text-primary-700 dark:text-primary-300">
                        Explanation:{' '}
                      </span>
                      {item.explanation}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Action Footer */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6 dark:border-[#242B35]">
        <Link to="/courses">
          <Button variant="secondary">
            ← Back to Courses
          </Button>
        </Link>

        {attempt.quiz_id && (
          <Link to={`/quiz/${attempt.quiz_id}`}>
            <Button variant="primary">
              <RotateCcw className="h-4 w-4" />
              Retake This Quiz
            </Button>
          </Link>
        )}
      </div>
    </div>
  );
}
