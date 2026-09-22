/**
 * Public marketing landing page - the app's front door at "/".
 *
 * Unauthenticated visitors land here; signed-in users go straight to their
 * dashboard so the marketing page never sits between them and the app.
 *
 * Connected to the backend: the "Live catalogue" strip reads real published
 * courses from GET /api/courses (public, no token). It degrades quietly when
 * the API is unreachable so the page still renders standalone.
 *
 * Styling follows docs/DESIGN_GUIDELINES.md.
 */
import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import {
  Sparkles,
  MessageSquare,
  BookOpen,
  Trophy,
  BarChart3,
  ArrowRight,
  Check,
  Flame,
  Zap,
} from 'lucide-react';

import { listCourses } from '../../api/courses';
import { useAuth } from '../../context/AuthContext';
import AvatarStage from '../../components/avatar/AvatarStage';
import Button from '../../components/ui/Button';
import Badge from '../../components/ui/Badge';
import Spinner from '../../components/ui/Spinner';

const FEATURES = [
  {
    icon: MessageSquare,
    color: 'bg-info-bg text-info-fg',
    title: 'A tutor that talks back',
    body: 'Ask anything and get a Socratic answer from an animated avatar with real-time lipsync.',
  },
  {
    icon: BookOpen,
    color: 'bg-easy-bg text-easy-fg',
    title: 'Courses that adapt',
    body: 'Lessons adjust to what you already know, and your weak topics carry across sessions.',
  },
  {
    icon: Flame,
    color: 'bg-medium-bg text-medium-fg',
    title: 'Streaks that stick',
    body: 'XP, streaks and quests turn steady practice into something you want to keep up.',
  },
  {
    icon: BarChart3,
    color: 'bg-medium-bg text-medium-fg',
    title: 'See what stuck',
    body: 'Mastery tracking surfaces the things you are about to forget, before you forget them.',
  },
];

const STEPS = [
  { n: 1, title: 'Pick a course', body: 'Browse the catalogue and enrol in whatever you want to learn.' },
  { n: 2, title: 'Learn with your tutor', body: 'Work through lessons and ask the avatar anything, any time.' },
  { n: 3, title: 'Prove it', body: 'Take quizzes, build streaks, and watch your mastery map fill in.' },
];

const DIFFICULTY_TONE = { beginner: 'easy', intermediate: 'info', advanced: 'danger' };

function FeaturedCourses() {
  const [state, setState] = useState({ status: 'loading', courses: [], total: 0 });

  useEffect(() => {
    let cancelled = false;

    listCourses({ page: 1, page_size: 3 })
      .then((res) => {
        if (cancelled) return;
        const items = res?.items ?? (Array.isArray(res) ? res : []);
        setState({ status: 'ready', courses: items, total: res?.total ?? items.length });
      })
      .catch(() => {
        // The landing page must render with or without a backend.
        if (!cancelled) setState({ status: 'error', courses: [], total: 0 });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === 'loading') {
    return (
      <div className="flex min-h-[240px] items-center justify-center">
        <Spinner size="lg" label="Loading courses" />
      </div>
    );
  }

  // Empty catalogue or no backend - skip rather than advertise an empty shelf.
  if (state.courses.length === 0) return null;

  return (
    <section className="border-t-2 border-line bg-surface py-20">
      <div className="mx-auto max-w-6xl px-4">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="label">Live catalogue</span>
            <h2 className="display mt-2 text-3xl sm:text-4xl">
              Start with one of these
            </h2>
            <p className="mt-2 font-semibold text-muted">
              {state.total} {state.total === 1 ? 'course' : 'courses'} published and ready to learn.
            </p>
          </div>
          <Link to="/courses">
            <Button variant="secondary">
              All courses
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {state.courses.map((course) => (
            <Link
              key={course.id ?? course.slug}
              to={`/courses/${course.slug}`}
              className="card row-interactive flex flex-col p-6"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary-100 text-primary-900">
                <BookOpen className="h-6 w-6" />
              </div>
              <div className="mb-2.5 flex flex-wrap items-center gap-2">
                {course.subject && <Badge tone="neutral">{course.subject}</Badge>}
                {course.difficulty && (
                  <Badge tone={DIFFICULTY_TONE[String(course.difficulty).toLowerCase()] ?? 'neutral'}>
                    {course.difficulty}
                  </Badge>
                )}
              </div>
              <h3 className="text-lg font-semibold leading-snug">{course.title}</h3>
              {course.description && (
                <p className="mt-2 line-clamp-3 text-sm font-semibold leading-relaxed text-muted">
                  {course.description}
                </p>
              )}
              <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary-700">
                View course
                <ArrowRight className="h-4 w-4" />
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  const { isAuthenticated, loading } = useAuth();

  // Wait for the session check so we never flash marketing at a signed-in user.
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-full bg-canvas">
      {/* ---------- Nav ---------- */}
      <header className="sticky top-0 z-30 border-b-2 border-line bg-surface">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white">
              <Sparkles className="h-5 w-5" />
            </span>
            <span className="text-xl font-semibold tracking-tight text-primary-600">LearnQuest</span>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/login">
              <Button variant="ghost" size="sm">Sign in</Button>
            </Link>
            <Link to="/register" className="hidden sm:block">
              <Button size="sm">Get started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* ---------- Hero ---------- */}
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 lg:grid-cols-2 lg:py-24">
        <div>
          <span className="label">Free · AI avatar tutor</span>
          <h1 className="display mt-4 text-4xl leading-[1.05] sm:text-5xl lg:text-6xl">
            The free, fun way to
            <span className="text-primary-600"> actually learn it</span>
          </h1>

          <p className="mt-6 max-w-xl text-lg font-semibold leading-relaxed text-muted">
            Bite-sized lessons, a talking AI tutor that explains things your way, and streaks that
            keep you coming back. Learning that feels like a game, because it is one.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link to="/register" className="sm:w-auto">
              <Button size="lg" className="w-full sm:w-auto">
                Get started
              </Button>
            </Link>
            <Link to="/login" className="sm:w-auto">
              <Button size="lg" variant="secondary" className="w-full sm:w-auto">
                I already have an account
              </Button>
            </Link>
          </div>

          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2">
            {['Always free', 'No card needed', 'Unlimited questions'].map((item) => (
              <li
                key={item}
                className="flex items-center gap-2 text-sm font-medium text-muted"
              >
                <Check className="h-4 w-4 shrink-0 text-easy" strokeWidth={3} />
                {item}
              </li>
            ))}
          </ul>
        </div>

        {/* The real tutor component, idle - the product demoing itself. */}
        <div className="relative mx-auto w-full max-w-md">
          <div className="card p-5">
            <div className="mb-4 flex items-center gap-2 border-b-2 border-line pb-3">
              <span className="h-2.5 w-2.5 rounded-full bg-primary-600" />
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                Nova · your tutor
              </span>
            </div>
            <div className="mx-auto w-full max-w-[280px] animate-bob">
              <AvatarStage preview />
            </div>
            <div className="mt-5 space-y-2.5">
              <div className="ml-auto w-fit max-w-[85%] rounded-lg rounded-br-md bg-primary-600 px-4 py-2.5 text-sm text-white">
                Why does recursion need a base case?
              </div>
              <div className="w-fit max-w-[90%] rounded-lg rounded-bl-md border border-line bg-surface px-4 py-2.5 text-sm text-body">
                Good question — what do you think happens without one?
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section className="border-t-2 border-line bg-surface py-20">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="display text-3xl sm:text-4xl">
              Everything you need to actually finish
            </h2>
            <p className="mt-3 font-semibold text-muted">
              Most courses are a video and a hope. This one watches how you are doing and adjusts.
            </p>
          </div>

          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon: Icon, color, title, body }) => (
              <div key={title} className="card p-6">
                <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg ${color}`}>
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm font-semibold leading-relaxed text-muted">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Live catalogue from the API ---------- */}
      <FeaturedCourses />

      {/* ---------- How it works ---------- */}
      <section className="py-20">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="display text-3xl sm:text-4xl">How it works</h2>
            <p className="mt-3 font-semibold text-muted">
              Three steps, then you are learning.
            </p>
          </div>

          <div className="mt-14 grid gap-5 md:grid-cols-3">
            {STEPS.map(({ n, title, body }) => (
              <div key={n} className="card p-6 text-center">
                <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-2xl font-semibold text-white">
                  {n}
                </span>
                <h3 className="text-lg font-semibold">{title}</h3>
                <p className="mt-2 text-sm font-semibold leading-relaxed text-muted">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Final CTA ---------- */}
      <section className="px-4 pb-20">
        <div className="mx-auto max-w-4xl rounded-xl border border-primary-500/40 bg-primary-600 px-6 py-14 text-center">
          <Zap className="mx-auto h-12 w-12 text-white" strokeWidth={2.5} />
          <h2 className="display mt-4 text-3xl text-white sm:text-4xl">
            Your tutor is waiting
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-lg text-primary-100">
            Create an account and ask your first question in under a minute.
          </p>
          <div className="mt-8 flex justify-center">
            <Link to="/register">
              <Button size="lg" variant="secondary">
                Create free account
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer className="border-t-2 border-line py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-primary-600 text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="font-semibold text-body">LearnQuest AI</span>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-xs font-semibold uppercase tracking-wide text-muted">
            <Link to="/courses" className="transition-colors hover:text-primary-600">Courses</Link>
            <Link to="/login" className="transition-colors hover:text-primary-600">Sign in</Link>
            <Link to="/register" className="transition-colors hover:text-primary-600">Get started</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
