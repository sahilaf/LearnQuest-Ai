/**
 * QuizPlayer.jsx
 *
 * OWNER: Member 2 (Learning Management).
 * Implements the interactive quiz consumption experience adhering to
 * HackerRank information density and docs/DESIGN_GUIDELINES.md.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, ChevronLeft, ChevronRight, HelpCircle, Send } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Input,
  Modal,
  ProgressBar,
  Spinner,
} from '../../components/ui';
import { getQuiz, startAttempt, submitAttempt } from '../../api/quizzes';

export default function QuizPlayer() {
  const { quizId } = useParams();
  const navigate = useNavigate();

  // State
  const [quiz, setQuiz] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({}); // { [questionId]: answerString }
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // 1. Fetch Quiz and Initialize Attempt
  const loadQuizAndStart = useCallback(async () => {
    if (!quizId) return;
    setLoading(true);
    setError(null);

    try {
      // Step A: Load sanitized quiz questions (without answers)
      const quizRes = await getQuiz(quizId);
      const quizData = quizRes?.data || quizRes;
      setQuiz(quizData);

      if (!quizData?.questions || quizData.questions.length === 0) {
        setLoading(false);
        return;
      }

      // Step B: Start or resume attempt
      const attemptRes = await startAttempt(quizId);
      const attemptData = attemptRes?.data || attemptRes;
      setAttemptId(attemptData?.attempt_id);
    } catch (err) {
      console.error('Failed to initialize quiz player:', err);
      const detail = err?.response?.data?.detail || err?.detail || 'Could not load the quiz. Please try again.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [quizId]);

  useEffect(() => {
    loadQuizAndStart();
  }, [loadQuizAndStart]);

  // Answer handler
  const handleSelectAnswer = (questionId, value) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  // Submission handler
  const handleSubmit = async () => {
    if (!attemptId || submitting) return;
    setSubmitting(true);
    setError(null);

    try {
      const payloadAnswers = Object.entries(answers).map(([qid, val]) => ({
        question_id: qid,
        user_answer: String(val).trim(),
      }));

      const res = await submitAttempt(attemptId, payloadAnswers);
      const data = res?.data || res;
      const targetAttemptId = data?.attempt_id || attemptId;

      // Navigate to results
      navigate(`/quiz/attempts/${targetAttemptId}`);
    } catch (err) {
      console.error('Quiz submission failed:', err);
      const detail = err?.response?.data?.detail || err?.detail || 'Failed to submit quiz attempt.';
      setError(detail);
      setSubmitting(false);
      setShowConfirmModal(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-sm text-muted">Preparing your quiz session...</p>
      </div>
    );
  }

  // Error state
  if (error && !quiz) {
    return (
      <div>
        <PageHeader title="Quiz Unavailable" subtitle="There was a problem loading this quiz." />
        <EmptyState
          title="Unable to load quiz"
          description={error}
          action={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={loadQuizAndStart}>
                Try Again
              </Button>
              <Link to="/courses">
                <Button variant="ghost">Return to Courses</Button>
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  // Empty questions
  if (!quiz || !quiz.questions || quiz.questions.length === 0) {
    return (
      <div>
        <PageHeader title={quiz?.title || 'Quiz'} subtitle="Practice and assessment." />
        <EmptyState
          title="No questions in this quiz"
          description="This quiz does not currently have any practice questions."
          action={
            <Link to="/courses">
              <Button variant="secondary">Browse Available Courses</Button>
            </Link>
          }
        />
      </div>
    );
  }

  const questions = quiz.questions;
  const currentQuestion = questions[currentIndex];
  const totalQuestions = questions.length;
  const answeredCount = Object.values(answers).filter((v) => String(v).trim().length > 0).length;
  const isAnswered = String(answers[currentQuestion?.id] || '').trim().length > 0;
  const isLastQuestion = currentIndex === totalQuestions - 1;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Link
              to={quiz.lesson_id ? `/lessons/${quiz.lesson_id}` : '/courses'}
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-body"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              {quiz.lesson_id ? 'Back to Lesson' : 'Back to Courses'}
            </Link>
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-ink">
            {quiz.title || 'Practice Quiz'}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <Badge tone={quiz.difficulty || 'primary'}>
            {quiz.difficulty ? quiz.difficulty.toUpperCase() : 'PRACTICE'}
          </Badge>
          <span className="text-xs text-muted">
            Question <span className="font-semibold text-body">{currentIndex + 1}</span> of {totalQuestions}
          </span>
        </div>
      </div>

      {/* Progress meter */}
      <div className="space-y-1.5">
        <ProgressBar
          value={answeredCount}
          max={totalQuestions}
          label="Answered Progress"
          tone="primary"
          showValue
        />
      </div>

      {/* Question Selector Palette (Dense HackerRank Style) */}
      <div className="flex flex-wrap items-center gap-1.5 rounded border border-line bg-surface p-2.5">
        <span className="mr-2 text-2xs font-semibold uppercase tracking-wider text-muted">
          Questions:
        </span>
        {questions.map((q, idx) => {
          const hasAnswer = String(answers[q.id] || '').trim().length > 0;
          const isCurrent = idx === currentIndex;
          return (
            <button
              key={q.id}
              type="button"
              onClick={() => setCurrentIndex(idx)}
              className={`flex h-7 w-7 items-center justify-center rounded text-xs font-semibold transition-colors ${
                isCurrent
                  ? 'bg-primary-600 text-white ring-2 ring-primary-500/50'
                  : hasAnswer
                  ? 'border border-easy bg-easy-bg text-easy-fg'
                  : 'border border-line bg-canvas text-muted hover:border-line-strong hover:text-body'
              }`}
            >
              {idx + 1}
            </button>
          );
        })}
      </div>

      {/* Main Question Card */}
      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between gap-4 border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <span className="label">
              Question {currentIndex + 1}
            </span>
            <Badge tone="neutral" className="text-2xs">
              {currentQuestion.type === 'mcq'
                ? 'Multiple Choice'
                : currentQuestion.type === 'true_false'
                ? 'True / False'
                : currentQuestion.type === 'fill_blank'
                ? 'Fill in Blank'
                : 'Free Response'}
            </Badge>
          </div>
          {currentQuestion.topic_tag && (
            <span className="font-mono text-2xs text-muted">
              {currentQuestion.topic_tag}
            </span>
          )}
        </div>

        {/* Prompt */}
        <div className="mb-6 text-base font-medium leading-relaxed text-ink">
          {currentQuestion.prompt}
        </div>

        {/* Interactive Answer Input Area */}
        <div className="space-y-3">
          {/* MCQ Options */}
          {currentQuestion.type === 'mcq' && (
            <div className="space-y-2">
              {(currentQuestion.options || []).map((option, optIdx) => {
                const selected = answers[currentQuestion.id] === option;
                return (
                  <button
                    key={optIdx}
                    type="button"
                    onClick={() => handleSelectAnswer(currentQuestion.id, option)}
                    className={`flex w-full items-start gap-3 rounded border p-3.5 text-left text-sm transition-colors ${
                      selected
                        ? 'border-primary-600 bg-primary-50 font-medium text-primary-900 ring-1 ring-primary-600'
                        : 'border-line-strong bg-surface hover:border-muted hover:bg-canvas'
                    }`}
                  >
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                        selected
                          ? 'border-primary-600 bg-primary-600 text-white'
                          : 'border-line-strong text-muted'
                      }`}
                    >
                      {String.fromCharCode(65 + optIdx)}
                    </span>
                    <span className="leading-relaxed">{option}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* True / False Options */}
          {currentQuestion.type === 'true_false' && (
            <div className="grid grid-cols-2 gap-3">
              {['True', 'False'].map((choice) => {
                const selected =
                  String(answers[currentQuestion.id] || '').toLowerCase() ===
                  choice.toLowerCase();
                return (
                  <button
                    key={choice}
                    type="button"
                    onClick={() => handleSelectAnswer(currentQuestion.id, choice)}
                    className={`flex items-center justify-center rounded border p-4 text-sm font-semibold transition-colors ${
                      selected
                        ? 'border-primary-600 bg-primary-50 text-primary-700 ring-1 ring-primary-600'
                        : 'border-line-strong bg-surface hover:border-muted hover:bg-canvas'
                    }`}
                  >
                    {choice}
                  </button>
                );
              })}
            </div>
          )}

          {/* Fill-in-the-blank */}
          {currentQuestion.type === 'fill_blank' && (
            <div className="max-w-md">
              <Input
                label="Your Answer"
                placeholder="Type your exact answer here..."
                value={answers[currentQuestion.id] || ''}
                onChange={(e) => handleSelectAnswer(currentQuestion.id, e.target.value)}
              />
            </div>
          )}

          {/* Short / Free Response */}
          {currentQuestion.type === 'short_answer' && (
            <div className="space-y-1.5">
              <label className="mb-1 block text-sm font-medium text-body">
                Your Explanation / Free Response
              </label>
              <textarea
                rows={4}
                value={answers[currentQuestion.id] || ''}
                onChange={(e) => handleSelectAnswer(currentQuestion.id, e.target.value)}
                placeholder="Explain the concept concisely in your own words..."
                className="field w-full resize-y font-sans leading-relaxed"
              />
              <p className="text-2xs text-muted">
                Tip: Concise plain English answers receive the most accurate conceptual feedback.
              </p>
            </div>
          )}
        </div>

        {/* Navigation Actions within Card */}
        <div className="mt-8 flex items-center justify-between border-t border-line pt-4">
          <Button
            variant="secondary"
            size="md"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>

          <div className="flex items-center gap-2">
            {!isLastQuestion ? (
              <Button
                variant="secondary"
                size="md"
                onClick={() => setCurrentIndex((prev) => Math.min(totalQuestions - 1, prev + 1))}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                onClick={() => setShowConfirmModal(true)}
              >
                <Send className="h-4 w-4" />
                Finish & Submit
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Bottom Floating Bar */}
      <div className="flex items-center justify-between rounded-lg border border-line bg-surface px-4 py-3">
        <div className="flex items-center gap-2 text-xs text-muted">
          <HelpCircle className="h-4 w-4 text-primary-600" />
          <span>
            {answeredCount === totalQuestions
              ? 'All questions answered! Ready to submit.'
              : `${totalQuestions - answeredCount} question(s) remaining`}
          </span>
        </div>

        <Button
          variant="primary"
          size="md"
          loading={submitting}
          onClick={() => setShowConfirmModal(true)}
        >
          Submit Quiz Attempt
        </Button>
      </div>

      {/* Confirmation Modal */}
      <Modal
        open={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="Submit Quiz Attempt?"
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              onClick={() => setShowConfirmModal(false)}
              disabled={submitting}
            >
              Review Answers
            </Button>
            <Button
              variant="primary"
              size="md"
              loading={submitting}
              onClick={handleSubmit}
            >
              Confirm Submission
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p>
            You have answered <span className="font-semibold">{answeredCount}</span> of{' '}
            <span className="font-semibold">{totalQuestions}</span> questions.
          </p>
          {answeredCount < totalQuestions && (
            <p className="text-xs text-medium">
              Note: Unanswered questions will be scored as 0 points.
            </p>
          )}
          {error && <p className="text-xs text-hard">{error}</p>}
        </div>
      </Modal>
    </div>
  );
}
