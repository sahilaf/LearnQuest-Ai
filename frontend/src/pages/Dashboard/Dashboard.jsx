
/**
 * Dashboard - OWNER: Member 2. See plan.md §7.2, §7.4.
 *
 * Information-dense learner dashboard showing:
 * - Next action hero banner
 * - M4 gamification stats summary (integrated gracefully)
 * - Current enrolled learning tracks with progress bars
 * - Recent learning activity feed (lessons, quizzes, results)
 * - Available tracks to explore
 * - Empty, loading, and error states
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  listCourses,
  myEnrollments,
  myProgress,
  myHistory,
  generateCourse,
} from '../../api/courses';
import { generateAdaptiveQuiz } from '../../api/quizzes';
import { myQuota } from '../../api/jobs';
import { myStats } from '../../api/gamification';
import useGenerationJob from '../../hooks/useGenerationJob';
import { useAuth } from '../../context/AuthContext';
import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  ProgressBar,
  Select,
  Spinner,
} from '../../components/ui';
import { StreakFlame, XPBar, DailyChallenges } from '../../components/game';
import ForYouPanel from '../../components/tutor/ForYouPanel';

const N_LESSONS_OPTIONS = [
  { value: '3', label: '3 Lessons (Quick intro)' },
  { value: '4', label: '4 Lessons (Standard track)' },
  { value: '5', label: '5 Lessons (Comprehensive)' },
  { value: '6', label: '6 Lessons (Deep dive)' },
];

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0 min';
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return remMins > 0 ? `${hours}h ${remMins}m` : `${hours}h`;
}

function formatDate(isoString) {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '';
  }
}

function getDifficultyTone(difficulty) {
  switch (difficulty?.toLowerCase()) {
    case 'beginner':
      return 'easy';
    case 'intermediate':
      return 'warning';
    case 'advanced':
      return 'danger';
    default:
      return 'default';
  }
}

export default function Dashboard() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [progressItems, setProgressItems] = useState([]);
  const [historyItems, setHistoryItems] = useState([]);
  const [availableCourses, setAvailableCourses] = useState([]);
  const [stats, setStats] = useState(null);

  // Generation Quota & Actions (Slot 9D)
  const [quota, setQuota] = useState(null);

  // Adaptive Quiz Generation State
  const [generatingAdaptive, setGeneratingAdaptive] = useState(false);
  const [adaptiveError, setAdaptiveError] = useState(null);

  // Course Generation State (Job Polling)
  const [courseGoal, setCourseGoal] = useState('');
  const [nLessons, setNLessons] = useState(4);
  const [courseGoalError, setCourseGoalError] = useState(null);
  const courseJob = useGenerationJob();

  // Route to the new course on success
  useEffect(() => {
    if (courseJob.status === 'succeeded' && courseJob.result?.slug) {
      navigate(`/courses/${courseJob.result.slug}`);
    }
  }, [courseJob.status, courseJob.result, navigate]);

  const loadDashboardData = useCallback(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    const progressPromise = myProgress().catch(() => ({ items: [] }));
    const historyPromise = myHistory({ page_size: 5 }).catch(() => ({ items: [] }));
    const catalogPromise = listCourses({ page_size: 4 }).catch(() => ({ items: [] }));
    const statsPromise = myStats().catch(() => null);
    const quotaPromise = myQuota().catch(() => null);

    Promise.allSettled([progressPromise, historyPromise, catalogPromise, statsPromise, quotaPromise])
      .then(([progRes, histRes, catRes, statsRes, quotaRes]) => {
        if (!isMounted) return;

        if (progRes.status === 'fulfilled') {
          const val = progRes.value;
          setProgressItems(Array.isArray(val) ? val : val?.items || []);
        }

        if (histRes.status === 'fulfilled') {
          const val = histRes.value;
          setHistoryItems(Array.isArray(val) ? val : val?.items || []);
        }

        if (catRes.status === 'fulfilled') {
          const val = catRes.value;
          setAvailableCourses(Array.isArray(val) ? val : val?.items || []);
        }

        if (statsRes.status === 'fulfilled') {
          setStats(statsRes.value);
        }

        if (quotaRes.status === 'fulfilled' && quotaRes.value) {
          setQuota(quotaRes.value);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err?.detail || 'Unable to load dashboard. Please try again.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handlePracticeWeakSpots = async () => {
    if (generatingAdaptive) return;
    if (quota && quota.remaining <= 0) {
      setAdaptiveError("Today's generation limit has been reached.");
      return;
    }
    setGeneratingAdaptive(true);
    setAdaptiveError(null);
    try {
      const data = await generateAdaptiveQuiz();
      if (data?.id) {
        navigate(`/quiz/${data.id}`);
      } else {
        setAdaptiveError('Adaptive quiz was generated with an unexpected response shape.');
      }
    } catch (err) {
      console.error('Adaptive quiz generation failed:', err);
      if (err?.status === 429 || err?.response?.status === 429) {
        setAdaptiveError("Today's generation limit has been reached.");
      } else {
        const msg =
          err?.detail ||
          err?.response?.data?.detail ||
          'Could not generate adaptive quiz. Try completing some lessons or quizzes first.';
        setAdaptiveError(msg);
      }
    } finally {
      setGeneratingAdaptive(false);
    }
  };

  const handleBuildCourseSubmit = async (e) => {
    if (e) e.preventDefault();
    const trimmed = courseGoal.trim();
    if (trimmed.length < 4) {
      setCourseGoalError('Tell us what you want to learn (at least 4 characters).');
      return;
    }
    if (quota && quota.remaining <= 0) {
      setCourseGoalError("Today's generation limit has been reached.");
      return;
    }
    setCourseGoalError(null);
    await courseJob.start(() => generateCourse(trimmed, Number(nLessons)));
  };

  useEffect(() => {
    const cancel = loadDashboardData();
    return cancel;
  }, [loadDashboardData]);

  // Determine top next action
  const nextAction = useMemo(() => {
    // Look for first active track that is not 100% completed
    const activeTrack = progressItems.find(
      (p) => (p.completion_percentage ?? 0) < 100 && p.next_lesson_id
    );
    if (activeTrack) {
      return {
        type: 'resume',
        track: activeTrack,
        title: activeTrack.next_lesson_title || 'Next Lesson',
        courseTitle: activeTrack.course_title,
        lessonId: activeTrack.next_lesson_id,
        courseSlug: activeTrack.course_slug,
        percentage: activeTrack.completion_percentage,
      };
    }

    if (progressItems.length > 0) {
      // All enrolled are completed
      return {
        type: 'completed',
      };
    }

    // No enrollments
    return {
      type: 'empty',
    };
  }, [progressItems]);

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Spinner size="lg" label="Loading your learning dashboard..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8">
        <PageHeader title="Dashboard" subtitle="Track your learning progress and performance." />
        <Card className="mt-4 border-hard/30 bg-hard-bg/50 p-6 text-center">
          <p className="text-sm font-medium text-hard-fg">{error}</p>
          <Button variant="primary" size="sm" onClick={loadDashboardData} className="mt-4">
            Retry
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Page Header */}
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome back${user?.full_name ? `, ${user.full_name}` : ''}. Pick up right where you left off.`}
      />

      {/* 1. M4 Gamification Stats Ribbon (Integrated gracefully) */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="flex items-center p-3.5">
            <StreakFlame stats={stats} />
          </Card>

          <Card className="flex items-center p-3.5">
            <div className="w-full">
              <XPBar stats={stats} />
            </div>
          </Card>

          <Card className="flex items-center gap-3 p-3.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-easy-bg text-lg">
              ⏱️
            </span>
            <div className="min-w-0">
              <div className="text-xs font-medium text-muted">Time Spent</div>
              <div className="text-lg font-bold text-ink">
                {formatDuration(stats.total_learning_seconds)}
              </div>
            </div>
          </Card>

          <Card className="flex items-center gap-3 p-3.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-info-bg text-lg">
              📚
            </span>
            <div className="min-w-0">
              <div className="text-xs font-medium text-muted">Active Tracks</div>
              <div className="text-lg font-bold text-ink">
                {progressItems.length} {progressItems.length === 1 ? 'track' : 'tracks'}
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 2. Next Action Hero Banner */}
      {nextAction.type === 'resume' && (
        <Card className="border-primary-500/30 bg-gradient-to-r from-primary-500/10 to-surface p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1.5 max-w-xl">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded bg-primary-600 px-2 py-0.5 text-xs font-semibold text-white">
                  NEXT ACTION
                </span>
                <span className="text-xs font-medium text-muted">
                  {nextAction.courseTitle} • {nextAction.percentage}% complete
                </span>
              </div>
              <h2 className="text-xl font-bold tracking-tight text-ink">
                {nextAction.title}
              </h2>
              <p className="text-sm text-body">
                Continue your learning flow. Read the concept notes and test yourself on practice quizzes.
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <Link to={`/courses/${nextAction.courseSlug}`}>
                <Button variant="secondary" size="sm">
                  View Syllabus
                </Button>
              </Link>
              <Link to={`/lessons/${nextAction.lessonId}`}>
                <Button variant="primary" size="md">
                  Resume Lesson →
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      )}

      {nextAction.type === 'completed' && (
        <Card className="border-easy/30 bg-easy-bg/50 p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-bold text-easy-fg">
                🎉 All Enrolled Tracks Completed!
              </h2>
              <p className="text-sm text-easy-fg">
                You have completed all lessons in your active tracks. Expand your skills with another track.
              </p>
            </div>
            <Link to="/courses">
              <Button variant="primary" size="sm">
                Explore Catalog →
              </Button>
            </Link>
          </div>
        </Card>
      )}

      {nextAction.type === 'empty' && (
        <Card className="p-8 text-center">
          <h2 className="text-xl font-bold text-ink">
            Welcome to LearnQuest AI
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-body">
            You are not enrolled in any tracks yet. Choose a learning track to start reading lessons and taking quizzes.
          </p>
          <div className="mt-5">
            <Link to="/courses">
              <Button variant="primary" size="md">
                Browse Learning Tracks →
              </Button>
            </Link>
          </div>
        </Card>
      )}

      {/* 2.25 M1: next roadmap step, today's plan, recommendations (G3) */}
      <ForYouPanel />

      {/* 2.5 Daily Challenges */}
      <DailyChallenges onClaimed={() => myStats().then(setStats).catch(() => {})} />
      {/* AI Generative Learning: Practice Weak Spots & Build Me a Course (Slot 9D) */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-ink">
              AI Practice & Learning
            </h2>
            <p className="text-xs text-muted">
              Personalized practice tailored to your misconceptions and custom courses built to your goals.
            </p>
          </div>
          {quota && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted">Generations today:</span>
              <Badge tone={quota.remaining > 0 ? 'info' : 'medium'}>
                {quota.remaining} of {quota.limit} remaining
              </Badge>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Practice My Weak Spots */}
          <Card className="flex flex-col justify-between p-5">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Badge tone="primary" className="text-xs">Adaptive Practice</Badge>
                {quota && (
                  <span className="font-mono text-xs text-muted">
                    {quota.remaining} gen{quota.remaining === 1 ? '' : 's'} left
                  </span>
                )}
              </div>
              <h3 className="text-base font-bold text-ink">
                Practice my weak spots
              </h3>
              <p className="text-xs leading-relaxed text-body">
                Generates a targeted practice quiz focusing on your weakest topics and actively
                tests against known misconceptions recorded from your previous quiz attempts.
              </p>

              {adaptiveError && (
                <div className="rounded border border-hard/40 bg-hard-bg p-2.5 text-xs text-hard-fg">
                  {adaptiveError}
                </div>
              )}

              {quota && quota.remaining <= 0 && !adaptiveError && (
                <div className="rounded border border-medium/40 bg-medium-bg p-2.5 text-xs text-medium-fg">
                  Today's generation limit has been reached.
                </div>
              )}
            </div>

            <div className="pt-4">
              <Button
                variant="secondary"
                size="md"
                loading={generatingAdaptive}
                disabled={generatingAdaptive || (quota && quota.remaining <= 0)}
                onClick={handlePracticeWeakSpots}
                className="w-full"
              >
                {generatingAdaptive ? 'Generating adaptive quiz (~8s)...' : 'Practice my weak spots 🎯'}
              </Button>
            </div>
          </Card>

          {/* Build Me a Course */}
          <Card className="flex flex-col justify-between p-5">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Badge tone="info" className="text-xs">Generative Course</Badge>
                {courseJob.isRunning && (
                  <span className="font-mono text-xs text-primary-400">
                    {courseJob.progress}%
                  </span>
                )}
              </div>
              <h3 className="text-base font-bold text-ink">
                Build me a course
              </h3>
              <p className="text-xs leading-relaxed text-body">
                Describe a topic or goal you wish to learn. We'll generate an outline, structured lessons, and practice quizzes automatically.
              </p>

              {courseJob.isRunning ? (
                <div className="space-y-2.5 py-2">
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span>Generating course syllabus & lessons (~25s)...</span>
                    <span className="font-mono font-semibold text-ink">{courseJob.progress}%</span>
                  </div>
                  <ProgressBar value={courseJob.progress} tone="default" size="sm" />
                </div>
              ) : (
                <form onSubmit={handleBuildCourseSubmit} className="space-y-3">
                  <Input
                    id="course-goal-input"
                    label="What do you want to learn?"
                    placeholder="e.g. Distributed Consensus, SQL Query Optimization, Redis Caching"
                    value={courseGoal}
                    onChange={(e) => {
                      setCourseGoal(e.target.value);
                      if (courseGoalError) setCourseGoalError(null);
                    }}
                    disabled={courseJob.isRunning || (quota && quota.remaining <= 0)}
                  />

                  <Select
                    id="course-lessons-select"
                    label="Target Number of Lessons"
                    value={String(nLessons)}
                    onChange={(e) => setNLessons(Number(e.target.value))}
                    options={N_LESSONS_OPTIONS}
                    disabled={courseJob.isRunning || (quota && quota.remaining <= 0)}
                  />

                  {courseGoalError && (
                    <div className="rounded border border-hard/40 bg-hard-bg p-2 text-xs text-hard-fg">
                      {courseGoalError}
                    </div>
                  )}

                  {courseJob.status === 'failed' && courseJob.error && (
                    <div className="rounded border border-hard/40 bg-hard-bg p-2.5 text-xs text-hard-fg">
                      {courseJob.error}
                    </div>
                  )}

                  {quota && quota.remaining <= 0 && (
                    <div className="rounded border border-medium/40 bg-medium-bg p-2.5 text-xs text-medium-fg">
                      Today's generation limit has been reached.
                    </div>
                  )}

                  <div className="pt-1">
                    <Button
                      type="submit"
                      variant="primary"
                      size="md"
                      loading={courseJob.isRunning}
                      disabled={courseJob.isRunning || !courseGoal.trim() || (quota && quota.remaining <= 0)}
                      className="w-full"
                    >
                      {courseJob.isRunning ? 'Building course...' : 'Build me a course ✨'}
                    </Button>
                  </div>
                </form>
              )}
            </div>
          </Card>
        </div>
      </div>

  {/* 3. In-Progress Learning Tracks (Course Progress) */ }
  <div className="space-y-4">
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-lg font-bold text-ink">
          Enrolled Tracks & Progress
        </h2>
        <p className="text-xs text-muted">
          Track your module completion rate and continue current tracks.
        </p>
      </div>
      <Link
        to="/courses"
        className="text-xs font-semibold text-primary-600 hover:text-primary-700"
      >
        Browse All Tracks →
      </Link>
    </div>

    {progressItems.length === 0 ? (
      <EmptyState
        title="No enrolled tracks"
        description="Enroll in a track from the course catalog to start tracking your progress here."
        action={
          <Link to="/courses">
            <Button variant="primary" size="sm">
              Find a Track
            </Button>
          </Link>
        }
      />
    ) : (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {progressItems.map((track) => {
          const pct = track.completion_percentage ?? 0;
          const isDone = pct >= 100;
          const nextId = track.next_lesson_id;

          return (
            <Card
              key={track.course_id}
              className="flex flex-col justify-between gap-4 p-5 hover:border-line-strong transition-colors"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge tone="default" className="text-[10px]">
                        {track.subject || 'Track'}
                      </Badge>
                      <Badge tone={getDifficultyTone(track.difficulty)} className="text-[10px]">
                        {track.difficulty || 'beginner'}
                      </Badge>
                      {track.source === 'ai_generated' && (
                        <Badge tone="info" className="text-[10px]">AI Generated</Badge>
                      )}
                    </div>
                    <h3 className="mt-1.5 font-bold text-ink">
                      {track.course_title}
                    </h3>
                  </div>
                  <Badge tone={isDone ? 'easy' : 'default'}>
                    {isDone ? 'Completed' : `${pct}%`}
                  </Badge>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-muted">
                    <span>Progress</span>
                    <span>
                      {track.completed_lessons} of {track.total_lessons} lessons ({pct}%)
                    </span>
                  </div>
                  <ProgressBar value={pct} tone={isDone ? 'easy' : 'default'} size="sm" />
                </div>

                {track.next_lesson_title && !isDone && (
                  <div className="rounded bg-raised p-2 text-xs text-body">
                    <span className="font-semibold text-ink">Up next:</span>{' '}
                    {track.next_lesson_title}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between border-t border-line pt-3">
                <Link
                  to={`/courses/${track.course_slug}`}
                  className="text-xs font-semibold text-muted hover:text-ink"
                >
                  Track Details
                </Link>
                {nextId ? (
                  <Link to={`/lessons/${nextId}`}>
                    <Button variant={isDone ? 'secondary' : 'primary'} size="sm">
                      {isDone ? 'Review' : 'Continue →'}
                    </Button>
                  </Link>
                ) : (
                  <Link to={`/courses/${track.course_slug}`}>
                    <Button variant="secondary" size="sm">
                      View Track
                    </Button>
                  </Link>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    )}
  </div>

  {/* 4. Two Column Layout: Recent Activity & Explore Tracks */ }
  <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
    {/* Left 2 Cols: Recent Activity */}
    <div className="space-y-4 lg:col-span-2">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-ink">
            Recent Learning Activity
          </h2>
          <p className="text-xs text-muted">
            Your latest completed lessons and practice quiz results.
          </p>
        </div>
        <Link
          to="/history"
          className="text-xs font-semibold text-primary-600 hover:text-primary-700"
        >
          Full History →
        </Link>
      </div>

      {historyItems.length === 0 ? (
        <EmptyState
          title="No recent activity"
          description="Start reading a lesson or take a quiz to begin your learning timeline."
          action={
            <Link to="/courses">
              <Button variant="secondary" size="sm">
                Browse Tracks
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-2.5">
          {historyItems.map((item) => {
            const isLesson = item.item_type === 'lesson';
            const isQuiz = item.item_type === 'quiz';

            return (
              <Card
                key={`${item.item_type}-${item.id}`}
                className="flex flex-col gap-3 p-3.5 transition-colors hover:border-line-strong sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${isLesson
                        ? 'bg-info-bg text-info-fg'
                        : 'bg-primary-500/15 text-primary-600'
                      }`}
                  >
                    {isLesson ? '📖' : '⚡'}
                  </span>

                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-ink">
                        {item.title}
                      </span>
                      {isLesson && (
                        <Badge
                          tone={item.status === 'completed' ? 'easy' : 'default'}
                          className="text-[10px]"
                        >
                          {item.status === 'completed' ? 'Completed' : 'In Progress'}
                        </Badge>
                      )}
                      {isQuiz && (
                        <Badge
                          tone={item.passed ? 'easy' : 'danger'}
                          className="text-[10px]"
                        >
                          {item.passed ? `Passed (${item.score}%)` : `Score: ${item.score}%`}
                        </Badge>
                      )}
                    </div>

                    <div className="text-xs text-muted">
                      {item.course_title && <span>{item.course_title} • </span>}
                      {formatDate(item.completed_at)}
                    </div>
                  </div>
                </div>

                <div className="flex shrink-0 items-center justify-end">
                  {isLesson && item.lesson_id && (
                    <Link to={`/lessons/${item.lesson_id}`}>
                      <Button variant="ghost" size="sm" className="text-xs">
                        View Lesson
                      </Button>
                    </Link>
                  )}
                  {isQuiz && item.attempt_id && (
                    <Link to={`/quiz/attempts/${item.attempt_id}`}>
                      <Button variant="ghost" size="sm" className="text-xs">
                        Review Attempt
                      </Button>
                    </Link>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>

    {/* Right Col: Explore Other Tracks */}
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold text-ink">
          Explore Tracks
        </h2>
        <p className="text-xs text-muted">Expand into new computer science subjects.</p>
      </div>

      {availableCourses.length === 0 ? (
        <EmptyState
          title="No courses available"
          description="New tracks will appear here once published."
        />
      ) : (
        <div className="space-y-3">
          {availableCourses.slice(0, 3).map((c) => (
            <Card key={c.id} className="space-y-2 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-bold text-ink">
                  {c.title}
                </h4>
                <div className="flex items-center gap-1.5">
                  {c.source === 'ai_generated' && (
                    <Badge tone="info" className="text-[10px]">AI Generated</Badge>
                  )}
                  <Badge tone={getDifficultyTone(c.difficulty)} className="text-[10px]">
                    {c.difficulty || 'beginner'}
                  </Badge>
                </div>
              </div>
              <p className="line-clamp-2 text-xs text-muted">{c.description}</p>
              <div className="flex justify-end pt-1">
                <Link to={`/courses/${c.slug}`}>
                  <Button variant="secondary" size="sm" className="text-xs">
                    View Track →
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  </div>
    </div >
  );
}

