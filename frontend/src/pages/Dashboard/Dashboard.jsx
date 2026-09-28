/**
 * Dashboard (Home) - Single loop, clear next step.
 * Shows ONE big "Continue" card driven by the daily plan:
 * Due reviews first -> Next lesson -> Quiz.
 * Underneath: Today's short list, Slim streak/XP strip, and Misconception summary.
 * Plus 3-step first-run onboarding for new learners.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Compass,
  Flame,
  GraduationCap,
  HelpCircle,
  Lightbulb,
  Map,
  RotateCcw,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { dailyPlan } from '../../api/recommendations';
import { getTodayReview } from '../../api/review';
import { myProgress, listCourses } from '../../api/courses';
import { myRoadmap, generateRoadmap } from '../../api/roadmap';
import { myMisconceptions } from '../../api/mastery';
import { myStats } from '../../api/gamification';

import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  ProgressBar,
  Spinner,
} from '../../components/ui';
import { StreakFlame, XPBar } from '../../components/game';

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0m';
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return remMins > 0 ? `${hours}h ${remMins}m` : `${hours}h`;
}

const KIND_LABEL = {
  revision: 'Review',
  lesson: 'Lesson',
  quiz: 'Quiz',
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [plan, setPlan] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [progressItems, setProgressItems] = useState([]);
  const [roadmap, setRoadmap] = useState(null);
  const [misconceptions, setMisconceptions] = useState([]);
  const [stats, setStats] = useState(null);

  // First-run onboarding state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(1);
  const [popularCourses, setPopularCourses] = useState([]);
  const [roadmapGoal, setRoadmapGoal] = useState('Get confident with databases and SQL');
  const [dailyMinutes, setDailyMinutes] = useState(30);
  const [onboardingBusy, setOnboardingBusy] = useState(false);

  const loadData = useCallback(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.allSettled([
      dailyPlan().catch(() => null),
      getTodayReview().catch(() => null),
      myProgress().catch(() => []),
      myRoadmap().catch(() => null),
      myMisconceptions(false).catch(() => ({ items: [] })), // active only
      myStats().catch(() => null),
      listCourses({ page_size: 4 }).catch(() => ({ items: [] })),
    ])
      .then(([planRes, reviewRes, progRes, roadmapRes, miscRes, statsRes, coursesRes]) => {
        if (!isMounted) return;

        if (planRes.status === 'fulfilled') setPlan(planRes.value);
        if (reviewRes.status === 'fulfilled') setReviewData(reviewRes.value);

        let prog = [];
        if (progRes.status === 'fulfilled') {
          const val = progRes.value;
          prog = Array.isArray(val) ? val : val?.items || [];
          setProgressItems(prog);
        }

        let rdmp = null;
        if (roadmapRes.status === 'fulfilled') {
          rdmp = roadmapRes.value?.roadmap ?? null;
          setRoadmap(rdmp);
        }

        if (miscRes.status === 'fulfilled') {
          const items = miscRes.value?.items || [];
          setMisconceptions(items.filter((m) => m.status === 'active' || m.status === 'fading'));
        }

        if (statsRes.status === 'fulfilled') setStats(statsRes.value);

        if (coursesRes.status === 'fulfilled') {
          const items = coursesRes.value?.items || (Array.isArray(coursesRes.value) ? coursesRes.value : []);
          setPopularCourses(items);
        }

        // Check if first-run: 0 active progress, no roadmap, 0 stats completed
        const hasDismissedOnboarding = localStorage.getItem('learnquest_onboarding_done');
        if (!hasDismissedOnboarding && prog.length === 0 && !rdmp && (!statsRes.value || statsRes.value.total_learning_seconds === 0)) {
          setShowOnboarding(true);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err?.detail || 'Failed to load your learning plan.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // First-run finish handler
  const handleCompleteOnboarding = async (chosenCourseId = null) => {
    setOnboardingBusy(true);
    try {
      localStorage.setItem('learnquest_onboarding_done', 'true');
      localStorage.setItem('learnquest_daily_minutes', String(dailyMinutes));

      if (chosenCourseId) {
        // Find course slug
        const course = popularCourses.find((c) => c.id === chosenCourseId);
        if (course?.slug) {
          navigate(`/courses/${course.slug}`);
          return;
        }
      } else if (roadmapGoal.trim()) {
        try {
          await generateRoadmap(roadmapGoal.trim());
        } catch {
          // Non-fatal
        }
      }
      setShowOnboarding(false);
      loadData();
    } finally {
      setOnboardingBusy(false);
    }
  };

  // Determine THE ONE primary "Continue" card
  const continueAction = useMemo(() => {
    const dueCount = reviewData?.total_due ?? (Array.isArray(reviewData?.items) ? reviewData.items.length : 0);

    // 1. Due Review First (The core loop requirement)
    if (dueCount > 0) {
      return {
        type: 'review',
        badge: 'DUE TODAY • SPACED REPETITION',
        badgeTone: 'warning',
        title: `Review ${dueCount} due topic${dueCount === 1 ? '' : 's'}`,
        description:
          'Spaced review prevents forgetting and makes learning stick. Complete your due items first before starting new lessons.',
        buttonLabel: `Start Review (${dueCount * 3}m) →`,
        link: '/review',
      };
    }

    // 2. Next Lesson from Enrolled Progress or Roadmap
    const activeTrack = progressItems.find(
      (p) => (p.completion_percentage ?? 0) < 100 && p.next_lesson_id
    );
    if (activeTrack) {
      return {
        type: 'lesson',
        badge: `NEXT LESSON • ${activeTrack.course_title}`,
        badgeTone: 'primary',
        title: activeTrack.next_lesson_title || 'Continue Lesson',
        description: `Pick up where you left off (${activeTrack.completion_percentage ?? 0}% completed). Read concept notes and take the quiz.`,
        buttonLabel: 'Resume Lesson →',
        link: `/lessons/${activeTrack.next_lesson_id}`,
      };
    }

    // 3. Next step from Roadmap
    const nextRoadmapNode = roadmap?.nodes?.find(
      (n) => n.node_key === roadmap?.progress?.next_node_key
    );
    if (nextRoadmapNode) {
      return {
        type: 'roadmap',
        badge: `AI ROADMAP • +${nextRoadmapNode.xp_reward ?? 50} XP`,
        badgeTone: 'info',
        title: nextRoadmapNode.title,
        description: nextRoadmapNode.summary || 'Your next recommended quest on your AI roadmap.',
        buttonLabel: 'Start Quest →',
        link: nextRoadmapNode.lesson_id ? `/lessons/${nextRoadmapNode.lesson_id}` : '/learn?tab=roadmap',
      };
    }

    // 4. Daily Plan First Item (if any)
    const planFirstItem = plan?.items?.[0];
    if (planFirstItem) {
      return {
        type: planFirstItem.kind,
        badge: `TODAY'S PLAN • ${KIND_LABEL[planFirstItem.kind] || 'NEXT'}`,
        badgeTone: 'primary',
        title: planFirstItem.title,
        description: planFirstItem.reason || 'Recommended by your personalized daily learning plan.',
        buttonLabel: 'Continue →',
        link: planFirstItem.link || '/learn',
      };
    }

    // 5. If everything completed or no enrollments
    if (progressItems.length > 0) {
      return {
        type: 'explore',
        badge: 'ALL ACTIVE TRACKS COMPLETED 🎉',
        badgeTone: 'easy',
        title: 'Ready for your next skill?',
        description: 'You have finished all active tracks. Explore the catalogue or set a new roadmap goal.',
        buttonLabel: 'Browse Courses →',
        link: '/learn?tab=browse',
      };
    }

    return {
      type: 'empty',
      badge: 'GET STARTED',
      badgeTone: 'primary',
      title: 'Start your learning journey',
      description: 'Choose a computer science track, build a roadmap, or upload your lecture notes.',
      buttonLabel: 'Explore Catalog →',
      link: '/learn',
    };
  }, [reviewData, progressItems, roadmap, plan]);

  if (loading) {
    return (
      <div className="flex min-h-[450px] items-center justify-center">
        <Spinner size="lg" label="Loading your personalized learning loop..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 space-y-4">
        <PageHeader title="Home" subtitle="Pick up right where you left off." />
        <Card className="border-hard/30 bg-hard-bg/50 p-6 text-center">
          <p className="text-sm font-medium text-hard-fg">{error}</p>
          <Button variant="primary" size="sm" onClick={loadData} className="mt-4">
            Retry
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* Page Header */}
      <PageHeader
        title="Home"
        subtitle={`Welcome back${user?.full_name ? `, ${user.full_name}` : ''}. One clear step at a time.`}
      />

      {/* 3-Step First-Run Onboarding Modal / Banner */}
      {showOnboarding && (
        <Card className="border-primary-500/40 bg-gradient-to-r from-primary-500/15 via-surface to-surface p-6 sm:p-8">
          <div className="max-w-2xl space-y-5">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-pill bg-primary-600 text-xs font-bold text-white">
                Step {onboardingStep} of 2
              </span>
              <span className="text-xs font-semibold uppercase tracking-wider text-primary-400">
                Quick Setup
              </span>
            </div>

            {onboardingStep === 1 && (
              <div className="space-y-4">
                <h2 className="text-2xl font-bold tracking-tight text-ink">
                  What do you want to learn?
                </h2>
                <p className="text-sm text-body leading-relaxed">
                  LearnQuest guides you through one continuous loop: learn a lesson, quiz your understanding, diagnose mistakes, and teach Nova to make concepts stick.
                </p>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 pt-2">
                  {popularCourses.slice(0, 2).map((course) => (
                    <button
                      key={course.id}
                      type="button"
                      onClick={() => handleCompleteOnboarding(course.id)}
                      className="group flex flex-col justify-between rounded-lg border border-line bg-surface p-4 text-left transition-colors hover:border-primary-500 hover:bg-raised"
                    >
                      <div>
                        <Badge tone="default" className="text-[10px]">Course</Badge>
                        <h4 className="mt-2 text-sm font-bold text-ink group-hover:text-primary-400">
                          {course.title}
                        </h4>
                        <p className="mt-1 line-clamp-2 text-xs text-muted">
                          {course.description || 'Master core principles through guided lessons and quizzes.'}
                        </p>
                      </div>
                      <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary-400">
                        Start this track <ArrowRight className="h-3.5 w-3.5" />
                      </span>
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                  <Link to="/upload" onClick={() => setShowOnboarding(false)} className="text-xs font-semibold text-muted hover:text-ink">
                    📄 Or upload notes & slides
                  </Link>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setOnboardingStep(2)}
                  >
                    Custom Goal →
                  </Button>
                </div>
              </div>
            )}

            {onboardingStep === 2 && (
              <div className="space-y-4">
                <h2 className="text-2xl font-bold tracking-tight text-ink">
                  How many minutes a day?
                </h2>
                <p className="text-sm text-body leading-relaxed">
                  A small daily session beats weekend cramming every time. Spaced reviews schedule automatically based on your budget.
                </p>

                <div className="grid grid-cols-3 gap-3 pt-2">
                  {[15, 30, 45].map((mins) => (
                    <button
                      key={mins}
                      type="button"
                      onClick={() => setDailyMinutes(mins)}
                      className={`flex flex-col items-center justify-center rounded-lg border p-4 text-center transition-colors ${
                        dailyMinutes === mins
                          ? 'border-primary-500 bg-primary-500/10 text-ink'
                          : 'border-line bg-surface text-muted hover:text-ink'
                      }`}
                    >
                      <span className="text-xl font-bold text-ink">{mins}m</span>
                      <span className="text-xs text-muted">
                        {mins === 15 ? 'Casual' : mins === 30 ? 'Recommended' : 'Deep focus'}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Nova Introduction */}
                <div className="rounded-lg border border-primary-500/30 bg-primary-500/5 p-3.5 text-xs text-body flex items-start gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-primary-600 text-white">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div>
                    <span className="font-semibold text-ink">Meet Nova:</span> Your personal AI tutor who explains tough concepts, captures false beliefs behind wrong answers, and lets you teach her to achieve true mastery.
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOnboardingStep(1)}
                  >
                    ← Back
                  </Button>
                  <Button
                    variant="primary"
                    size="md"
                    loading={onboardingBusy}
                    onClick={() => handleCompleteOnboarding(null)}
                  >
                    Let's Go →
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ============================================================ */}
      {/* B. THE ONE BIG "CONTINUE" CARD                                */}
      {/* ============================================================ */}
      <Card className="border-primary-500/40 bg-gradient-to-r from-primary-500/15 via-raised to-surface p-7 sm:p-9 shadow-md transition-all hover:border-primary-500">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3 max-w-2xl">
            <div className="flex items-center gap-2">
              <Badge tone={continueAction.badgeTone || 'primary'} className="text-xs font-bold tracking-wide">
                {continueAction.badge}
              </Badge>
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-ink">
              {continueAction.title}
            </h2>

            <p className="text-sm sm:text-base leading-relaxed text-body">
              {continueAction.description}
            </p>
          </div>

          <div className="shrink-0 flex items-center">
            <Link to={continueAction.link} className="w-full sm:w-auto">
              <Button variant="primary" size="lg" className="w-full sm:w-auto px-8 py-3.5 text-base font-semibold shadow-lg">
                {continueAction.buttonLabel}
              </Button>
            </Link>
          </div>
        </div>
      </Card>

      {/* ============================================================ */}
      {/* SLIM STREAK / XP STRIP                                       */}
      {/* ============================================================ */}
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
              <div className="text-xs font-medium text-muted">Study Time</div>
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

      {/* ============================================================ */}
      {/* TWO COLUMNS: TODAY'S SHORT LIST & MISCONCEPTION SUMMARY       */}
      {/* ============================================================ */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Today's Short List */}
        <Card className="p-5 flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-primary-400" />
                <h3 className="text-base font-bold text-ink">Today's Plan</h3>
              </div>
              {plan && (
                <span className="font-mono text-xs text-muted">
                  {plan.planned_minutes} of {plan.minutes || 30} mins
                </span>
              )}
            </div>

            {(!plan?.items || plan.items.length === 0) ? (
              <p className="text-xs text-muted py-4 text-center">
                Nothing is queued right now. Complete a lesson or take a quiz to let the app plan your daily loop.
              </p>
            ) : (
              <ol className="space-y-2">
                {plan.items.slice(0, 3).map((item, index) => (
                  <li key={`${item.kind}-${index}`}>
                    <Link
                      to={item.link || '/dashboard'}
                      className="row-interactive flex items-start gap-3 rounded-lg border border-line p-3 transition-colors hover:border-primary-500"
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-pill bg-raised font-mono text-xs text-muted">
                        {index + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-ink">{item.title}</span>
                          <Badge tone="default" className="text-[10px]">
                            {KIND_LABEL[item.kind] || item.kind}
                          </Badge>
                        </span>
                        <span className="mt-0.5 block text-xs text-muted line-clamp-1">
                          {item.reason}
                        </span>
                      </span>
                      <span className="shrink-0 font-mono text-xs text-faint">
                        {item.minutes}m
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="border-t border-line pt-3 flex items-center justify-between">
            <span className="text-xs text-muted">Review comes first to protect memory.</span>
            <Link to="/learn" className="text-xs font-semibold text-primary-400 hover:text-primary-300">
              View all tracks →
            </Link>
          </div>
        </Card>

        {/* Misconception Summary */}
        <Card className="p-5 flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-warning" />
                <h3 className="text-base font-bold text-ink">Active Misconceptions</h3>
              </div>
              <Badge tone={misconceptions.length > 0 ? 'warning' : 'easy'} className="text-[10px]">
                {misconceptions.length} recorded
              </Badge>
            </div>

            {misconceptions.length === 0 ? (
              <div className="py-6 text-center space-y-2">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-pill bg-easy-bg text-lg">
                  ✓
                </div>
                <h4 className="text-sm font-semibold text-ink">Mental Models are Clear</h4>
                <p className="mx-auto max-w-sm text-xs text-muted leading-relaxed">
                  You have no active false beliefs. When a quiz reveals a misconception, Nova captures the exact belief here so you can teach her out of it.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {misconceptions.slice(0, 2).map((item) => (
                  <div
                    key={item.topic_tag}
                    className="rounded-lg border border-line bg-surface p-3.5 space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-2xs font-semibold uppercase tracking-wider text-muted">
                        You seem to believe:
                      </span>
                      <Badge tone={item.status === 'active' ? 'hard' : 'medium'} className="text-[10px]">
                        {item.status}
                      </Badge>
                    </div>

                    <p className="text-xs italic font-medium text-ink">
                      “{item.misconception}”
                    </p>

                    <div className="flex items-center justify-between border-t border-line/60 pt-2">
                      <span className="font-mono text-[10px] text-muted">{item.topic_tag}</span>
                      <Link
                        to={`/tutor?topic=${encodeURIComponent(item.topic_tag)}&mode=teachback`}
                      >
                        <Button variant="secondary" size="sm" className="text-xs">
                          <GraduationCap className="h-3.5 w-3.5 text-primary-400" />
                          Teach Nova to fix it →
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-line pt-3 flex items-center justify-between">
            <span className="text-xs text-muted">Explaining fixes misunderstandings.</span>
            <Link to="/progress?tab=stats" className="text-xs font-semibold text-primary-400 hover:text-primary-300">
              Misconception map →
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
