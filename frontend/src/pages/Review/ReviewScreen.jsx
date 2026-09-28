/**
 * ReviewScreen - OWNER: Member 2 (Learning Management).
 * Consumes M1's Spaced-Repetition Review Queue (plan.md §6.12, §7.2).
 *
 * Implements:
 * - One review card at a time with clean, distraction-free layout
 * - Consumes GET /api/review/today and submits to POST /api/review/{id}/answer
 * - Free-response textarea or MCQ/TF options
 * - AI conceptual feedback and misconception diagnosis on submit
 * - Queue completion state
 * - Strict adherence to docs/DESIGN_GUIDELINES.md and 375px mobile responsiveness
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  Calendar,
  CheckCircle2,
  ChevronRight,
  GraduationCap,
  RotateCcw,
  Sparkles,
  Trophy,
  XCircle,
} from 'lucide-react';

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  Spinner,
} from '../../components/ui';
import { getTodayReview, submitReviewAnswer } from '../../api/review';

export default function ReviewScreen() {
  const navigate = useNavigate();

  const [items, setItems] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Result of current question submission
  const [feedback, setFeedback] = useState(null);
  const [reviewedCount, setReviewedCount] = useState(0);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getTodayReview();
      const list = res?.items || (Array.isArray(res) ? res : []);
      setItems(list);
      setCurrentIndex(0);
      setCurrentAnswer('');
      setFeedback(null);
      setReviewedCount(0);
    } catch (err) {
      console.error('Failed to load review queue:', err);
      setError(err?.detail || 'Unable to load your review queue for today. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const currentItem = items[currentIndex];

  const handleSubmitAnswer = async () => {
    if (!currentItem || submitting || !String(currentAnswer).trim()) return;
    setSubmitting(true);
    setError(null);

    try {
      const result = await submitReviewAnswer(currentItem.id, {
        answer: String(currentAnswer).trim(),
      });
      setFeedback(result);
      setReviewedCount((prev) => prev + 1);
    } catch (err) {
      console.error('Failed to submit review answer:', err);
      setError(err?.detail || 'Failed to submit review answer. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleNextItem = () => {
    if (currentIndex + 1 < items.length) {
      setCurrentIndex((prev) => prev + 1);
      setCurrentAnswer('');
      setFeedback(null);
      setError(null);
    } else {
      // Completed all items in queue
      setCurrentIndex(items.length);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-sm text-muted">Retrieving today's due review items...</p>
      </div>
    );
  }

  if (error && items.length === 0) {
    return (
      <div className="space-y-4 max-w-2xl mx-auto py-8">
        <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Dashboard
        </Link>
        <EmptyState
          title="Review Queue Unavailable"
          description={error}
          action={
            <Button variant="secondary" onClick={loadQueue}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  // Queue finished or initially empty
  if (items.length === 0 || currentIndex >= items.length) {
    return (
      <div className="mx-auto max-w-2xl py-12 px-4 text-center space-y-6">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-easy-bg text-3xl">
          🎉
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">
            All Caught Up for Today!
          </h1>
          <p className="text-sm text-muted max-w-md mx-auto leading-relaxed">
            {reviewedCount > 0
              ? `Great session! You completed ${reviewedCount} due review ${
                  reviewedCount === 1 ? 'item' : 'items'
                }. Spaced repetition intervals have been scheduled.`
              : 'You have no items due for spaced-repetition review right now. Check back tomorrow!'}
          </p>
        </div>

        <div className="flex flex-col items-center justify-center gap-3 pt-2">
          <Link to="/dashboard">
            <Button variant="primary" size="lg" className="px-8 font-semibold">
              Continue your course →
            </Button>
          </Link>
          <Link to="/learn" className="text-xs text-muted hover:text-ink transition-colors pt-1">
            Or browse all courses & challenges →
          </Link>
        </div>
      </div>
    );
  }

  const isAnswered = Boolean(feedback);
  const isCorrect = feedback?.is_correct;
  const totalDue = items.length;
  const progressPct = Math.round((currentIndex / totalDue) * 100);

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-16">
      {/* Top Header & Queue Progress Bar */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Exit Review
          </Link>

          <span className="font-mono text-xs font-semibold text-muted">
            Due Item {currentIndex + 1} of {totalDue}
          </span>
        </div>

        <ProgressBar
          value={currentIndex + 1}
          max={totalDue}
          tone="primary"
          size="sm"
        />
      </div>

      {/* Main Single-Card Review Unit */}
      <Card className="p-6 sm:p-8 space-y-6">
        {/* Topic Tag Header */}
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <Badge tone="default" className="text-xs">
              {currentItem.topic_name || currentItem.topic_tag}
            </Badge>
            <span className="text-2xs font-mono uppercase text-muted">
              {currentItem.type === 'short_answer'
                ? 'Free Response'
                : currentItem.type === 'true_false'
                ? 'True / False'
                : 'Multiple Choice'}
            </span>
          </div>
          <span className="text-2xs text-muted flex items-center gap-1">
            <Calendar className="h-3 w-3" /> Due today
          </span>
        </div>

        {/* Prompt */}
        <div className="text-lg font-semibold leading-relaxed text-ink">
          {currentItem.prompt}
        </div>

        {/* Answer Controls */}
        <div className="space-y-4">
          {/* Multiple Choice */}
          {currentItem.type === 'mcq' && (
            <div className="space-y-2">
              {(currentItem.options || []).map((opt, idx) => {
                const selected = currentAnswer === opt;
                return (
                  <button
                    key={idx}
                    type="button"
                    disabled={isAnswered}
                    onClick={() => setCurrentAnswer(opt)}
                    className={`flex w-full items-start gap-3 rounded border p-3.5 text-left text-sm transition-colors ${
                      selected
                        ? 'border-primary-600 bg-primary-500/10 font-medium text-ink ring-1 ring-primary-600'
                        : 'border-line-strong bg-surface hover:border-muted hover:bg-canvas disabled:opacity-60'
                    }`}
                  >
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                        selected
                          ? 'border-primary-600 bg-primary-600 text-white'
                          : 'border-line-strong text-muted'
                      }`}
                    >
                      {String.fromCharCode(65 + idx)}
                    </span>
                    <span className="leading-relaxed">{opt}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* True / False */}
          {currentItem.type === 'true_false' && (
            <div className="grid grid-cols-2 gap-3">
              {['True', 'False'].map((choice) => {
                const selected = currentAnswer.toLowerCase() === choice.toLowerCase();
                return (
                  <button
                    key={choice}
                    type="button"
                    disabled={isAnswered}
                    onClick={() => setCurrentAnswer(choice)}
                    className={`flex items-center justify-center rounded border p-4 text-sm font-semibold transition-colors ${
                      selected
                        ? 'border-primary-600 bg-primary-500/10 text-primary-600 ring-1 ring-primary-600'
                        : 'border-line-strong bg-surface hover:border-muted hover:bg-canvas disabled:opacity-60'
                    }`}
                  >
                    {choice}
                  </button>
                );
              })}
            </div>
          )}

          {/* Free Response / Short Answer Textarea */}
          {currentItem.type === 'short_answer' && (
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                Your Answer / Explanation
              </label>
              <textarea
                rows={4}
                value={currentAnswer}
                disabled={isAnswered}
                onChange={(e) => setCurrentAnswer(e.target.value)}
                placeholder="Type your explanation in plain English..."
                className="field w-full leading-relaxed resize-y font-sans disabled:opacity-60"
              />
            </div>
          )}
        </div>

        {/* AI Feedback & Misconception Panel (Visible Post-Submission) */}
        {feedback && (
          <div className="animate-fade-in space-y-3 rounded-lg border border-line bg-canvas p-4 sm:p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isCorrect ? (
                  <Badge tone="easy" className="text-xs">
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Mastered
                  </Badge>
                ) : (
                  <Badge tone="danger" className="text-xs">
                    <XCircle className="h-3.5 w-3.5 mr-1" /> Needs Revision
                  </Badge>
                )}
                <span className="text-xs text-muted font-mono">
                  Score: {Math.round((feedback.score_0_1 ?? (isCorrect ? 1 : 0)) * 100)}%
                </span>
              </div>

              {feedback.next_due_at && (
                <span className="text-2xs text-muted">
                  Next review in 2 days
                </span>
              )}
            </div>

            {/* Written Explanation */}
            {feedback.feedback && (
              <p className="text-sm leading-relaxed text-body">
                {feedback.feedback}
              </p>
            )}

            {/* Diagnosed Misconception */}
            {feedback.misconception && (
              <div className="rounded border-l-2 border-primary-600 bg-primary-500/10 p-3 text-xs leading-relaxed text-body">
                <span className="font-semibold text-primary-600 block mb-0.5">
                  Identified Misconception
                </span>
                “{feedback.misconception}”
              </div>
            )}
          </div>
        )}

        {/* Action Button Footer */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <div className="text-xs text-muted">
            {!isAnswered ? 'Submit to receive conceptual feedback' : 'Interval updated'}
          </div>

          <div>
            {!isAnswered ? (
              <Button
                variant="primary"
                size="md"
                loading={submitting}
                disabled={submitting || !String(currentAnswer).trim()}
                onClick={handleSubmitAnswer}
              >
                Submit Answer
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                onClick={handleNextItem}
              >
                {currentIndex + 1 < totalDue ? 'Next Due Item →' : 'Complete Queue ✓'}
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
