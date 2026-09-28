/**
 * QuizResult.jsx
 *
 * OWNER: Member 2 (Learning Management).
 * Renders the score, summary statistics, and question-by-question review
 * post-submission following docs/DESIGN_GUIDELINES.md.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Award,
  BookOpen,
  CheckCircle2,
  Clock,
  GraduationCap,
  Lightbulb,
  RotateCcw,
  Sparkles,
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
import { getAttempt, getQuiz } from '../../api/quizzes';
import { getLesson } from '../../api/lessons';
import { myMisconceptions } from '../../api/mastery';

export default function QuizResult() {
  const { attemptId } = useParams();
  const navigate = useNavigate();

  const [attempt, setAttempt] = useState(null);
  const [quizDetails, setQuizDetails] = useState(null);
  const [lessonInfo, setLessonInfo] = useState(null);
  const [misconceptions, setMisconceptions] = useState([]);
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
      if (data?.quiz_id) {
        getQuiz(data.quiz_id)
          .then((qRes) => {
            const qData = qRes?.data || qRes;
            setQuizDetails(qData);
            if (qData?.lesson_id) {
              getLesson(qData.lesson_id).then(setLessonInfo).catch(() => {});
            }
          })
          .catch(() => {});
      }
      myMisconceptions(false)
        .then((mRes) => {
          setMisconceptions(mRes?.items || []);
        })
        .catch(() => {});
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

  const wrongAnswers = useMemo(() => {
    return (attempt?.answers || []).filter((a) => !a.is_correct);
  }, [attempt]);

  const primaryMisconception = useMemo(() => {
    if (!wrongAnswers.length) return null;
    const firstWrong = wrongAnswers[0];
    const matched = misconceptions.find(
      (m) => m.topic_tag === firstWrong.topic_tag && m.misconception
    );
    if (matched) {
      return {
        topic: firstWrong.topic_tag,
        text: matched.misconception,
      };
    }
    const cleanExpl = firstWrong.explanation
      ? firstWrong.explanation.replace(/^Explanation:\s*/i, '').trim()
      : null;
    return {
      topic: firstWrong.topic_tag || 'sql',
      text: cleanExpl || `A conceptual misunderstanding regarding ${firstWrong.topic_tag || 'this topic'} was detected.`,
    };
  }, [wrongAnswers, misconceptions]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <Link
            to="/learn"
            className="inline-flex items-center gap-1 text-xs text-muted hover:text-body"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Courses
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-ink">
            {attempt.quiz_title || 'Quiz Results & Review'}
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {attempt.quiz_id && (
            <Link to={`/quiz/${attempt.quiz_id}`}>
              <Button variant="ghost" size="sm">
                <RotateCcw className="h-3.5 w-3.5" />
                Retake Quiz
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Summary Score Card */}
      <Card className="grid grid-cols-1 gap-6 p-6 md:grid-cols-3">
        {/* Score Column */}
        <div className="flex flex-col items-center justify-center border-b border-line pb-6 text-center md:border-b-0 md:border-r md:pb-0 md:pr-6">
          <div className="text-4xl font-bold tracking-tight text-ink">
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
            <div className="rounded border border-line bg-canvas p-3">
              <span className="label">Accuracy</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-xl font-semibold text-ink">
                  {correct} / {total}
                </span>
                <span className="text-xs text-muted">questions</span>
              </div>
            </div>

            <div className="rounded border border-line bg-canvas p-3">
              <span className="label">Time Taken</span>
              <div className="mt-1 flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-muted" />
                <span className="text-xl font-semibold text-ink">
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

      {/* PROMINENT NEXT STEP CARD (Requirement C) */}
      {isPassing ? (
        <Card className="border-easy/40 bg-gradient-to-r from-easy/10 via-surface to-surface p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge tone="easy" className="text-xs font-semibold">
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Quiz Passed
                </Badge>
              </div>
              <h3 className="text-lg font-bold text-ink">
                Concept Mastered! Ready for the next lesson.
              </h3>
              <p className="text-xs text-muted">
                Keep your learning momentum going and proceed directly to your next lesson.
              </p>
            </div>

            <div className="shrink-0">
              {lessonInfo?.next_lesson_id ? (
                <Link to={`/lessons/${lessonInfo.next_lesson_id}`}>
                  <Button variant="primary" size="lg" className="font-semibold px-6">
                    Next Lesson →
                  </Button>
                </Link>
              ) : (
                <Link to="/learn">
                  <Button variant="primary" size="lg" className="font-semibold px-6">
                    Continue Course →
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </Card>
      ) : (
        <Card className="border-warning/50 bg-gradient-to-r from-warning/15 via-surface to-surface p-6 sm:p-7 shadow-sm">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-warning" />
              <span className="text-xs font-bold uppercase tracking-wider text-warning">
                Misconception Detected
              </span>
            </div>

            <div>
              <span className="text-2xs font-semibold text-muted uppercase tracking-wider">
                You seem to believe:
              </span>
              <p className="mt-1 text-base sm:text-lg font-bold text-ink italic leading-snug">
                “{primaryMisconception?.text}”
              </p>
            </div>

            <p className="text-xs text-body leading-relaxed max-w-xl">
              Explaining this concept to someone else is the proven way to rewire your mental model.
              Teach Nova why this belief is wrong — her score is your grade.
            </p>

            <div className="pt-1">
              <Link
                to={
                  primaryMisconception?.topic
                    ? `/tutor?topic=${encodeURIComponent(primaryMisconception.topic)}&mode=teachback`
                    : '/tutor?mode=teachback'
                }
              >
                <Button variant="primary" size="lg" className="font-semibold px-6">
                  <GraduationCap className="h-4 w-4" />
                  Teach Nova to fix it →
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      )}

      {/* Detailed Question Review Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">
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
                  <div className="mb-3 text-sm font-semibold text-ink">
                    {item.prompt}
                  </div>

                  {/* User Answer vs Correct Answer */}
                  <div className="mb-3 grid grid-cols-1 gap-2 rounded border border-line bg-canvas p-3 sm:grid-cols-2">
                    <div>
                      <span className="text-2xs font-semibold uppercase tracking-wider text-muted">
                        Your Answer:
                      </span>
                      <p
                        className={`mt-0.5 text-sm ${
                          isCorrect
                            ? 'font-medium text-easy'
                            : 'font-medium text-hard'
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
                        <p className="mt-0.5 text-sm font-medium text-easy">
                          {item.correct_answer}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Explanation */}
                  {item.explanation && (
                    <div className="rounded border-l-2 border-primary-600 bg-primary-500/10 p-3 text-xs leading-relaxed text-body">
                      <span className="font-semibold text-primary-600">
                        Explanation:{' '}
                      </span>
                      {item.explanation}
                    </div>
                  )}

                  {/* Actions for incorrect answers (Slot 9D) */}
                  {!isCorrect && (
                    <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                      {quizDetails?.lesson_id ? (
                        <Link to={`/lessons/${quizDetails.lesson_id}`}>
                          <Button variant="secondary" size="sm">
                            <BookOpen className="h-3.5 w-3.5 text-muted" />
                            Learn this
                          </Button>
                        </Link>
                      ) : (
                        <Link to="/courses">
                          <Button variant="secondary" size="sm">
                            <BookOpen className="h-3.5 w-3.5 text-muted" />
                            Learn this
                          </Button>
                        </Link>
                      )}

                      <Link
                        to={
                          quizDetails?.lesson_id
                            ? `/tutor?lessonId=${quizDetails.lesson_id}&mode=teachback`
                            : item.topic_tag
                            ? `/tutor?topic=${encodeURIComponent(item.topic_tag)}&mode=teachback`
                            : '/tutor'
                        }
                      >
                        <Button variant="secondary" size="sm">
                          <GraduationCap className="h-3.5 w-3.5 text-primary-500" />
                          Teach Nova
                        </Button>
                      </Link>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Action Footer (Requirement C: Exactly one main next step) */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
        {isPassing ? (
          <>
            <Link to="/learn">
              <Button variant="ghost">
                ← Back to Courses
              </Button>
            </Link>

            <div className="flex items-center gap-3">
              {attempt.quiz_id && (
                <Link to={`/quiz/${attempt.quiz_id}`}>
                  <Button variant="secondary">
                    <RotateCcw className="h-4 w-4" />
                    Retake Quiz
                  </Button>
                </Link>
              )}
              {lessonInfo?.next_lesson_id ? (
                <Link to={`/lessons/${lessonInfo.next_lesson_id}`}>
                  <Button variant="primary">
                    Next Lesson →
                  </Button>
                </Link>
              ) : (
                <Link to="/learn">
                  <Button variant="primary">
                    Continue Learning →
                  </Button>
                </Link>
              )}
            </div>
          </>
        ) : (
          <>
            {attempt.quiz_id ? (
              <Link to={`/quiz/${attempt.quiz_id}`}>
                <Button variant="secondary">
                  <RotateCcw className="h-4 w-4" />
                  Retake This Quiz
                </Button>
              </Link>
            ) : (
              <Link to="/learn">
                <Button variant="secondary">
                  ← Back to Courses
                </Button>
              </Link>
            )}

            <Link
              to={
                primaryMisconception?.topic
                  ? `/tutor?topic=${encodeURIComponent(primaryMisconception.topic)}&mode=teachback`
                  : '/tutor?mode=teachback'
              }
            >
              <Button variant="primary">
                <GraduationCap className="h-4 w-4" />
                Teach Nova to fix it →
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
