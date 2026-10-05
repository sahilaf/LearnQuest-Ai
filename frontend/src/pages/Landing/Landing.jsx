/**
 * Public landing page - the app's front door at "/".
 *
 * Unauthenticated visitors land here; signed-in users go straight to their
 * dashboard so the marketing page never sits between them and the app.
 *
 * It sells what is actually different about LearnQuest, in the order a
 * student meets it: a wrong answer is traced to the belief behind it, and you
 * fix that belief with Redwan - a tutor with a real face and voice.
 * Every claim on this page is something the product does today.
 *
 * The "courses" strip reads real published courses from GET /api/courses
 * (public, no token) and disappears quietly when the API is unreachable.
 *
 * Styling follows docs/DESIGN_GUIDELINES.md: tokens only, depth from borders
 * not shadows, violet only for the primary action and the tutor.
 */
import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  Check,
  Code2,
  FileUp,
  GraduationCap,
  Lightbulb,
  LineChart,
  MessageSquare,
  Mic,
  PenLine,
  Repeat,
  Sparkles,
} from 'lucide-react';

import { listCourses } from '../../api/courses';
import { useAuth } from '../../context/AuthContext';
import { Badge, Spinner, buttonClasses } from '../../components/ui';

const LOOP = [
  {
    icon: BookOpen,
    title: 'Learn',
    body: 'Short lessons, with a tutor you can ask about any line.',
  },
  {
    icon: PenLine,
    title: 'Quiz',
    body: 'Answer in your own words, not only multiple choice.',
  },
  {
    icon: Lightbulb,
    title: 'Diagnose',
    body: 'A wrong answer is traced to the exact belief behind it.',
  },
  {
    icon: GraduationCap,
    title: 'Fix it',
    body: 'Talk it through with Redwan. Getting that topic right in later quizzes clears the belief.',
  },
];

const MODES = [
  {
    icon: Mic,
    title: 'Live conversation',
    body: 'Talk out loud, like a call. Redwan answers in a second or two, with the transcript on screen.',
  },
  {
    icon: MessageSquare,
    title: 'Chat',
    body: 'Type a question any time. He remembers your lessons and what you have already discussed.',
  },
];

const FEATURES = [
  {
    icon: Repeat,
    title: 'Review at the right time',
    body: 'Topics come back a day after you study them, then at growing intervals.',
  },
  {
    icon: Code2,
    title: 'SQL practice, really graded',
    body: 'Your query runs against hidden test cases - no guessing, no partial credit for looking right.',
  },
  {
    icon: LineChart,
    title: 'Progress you can see',
    body: 'Mastery per topic, a map of the beliefs you have fixed, streaks, badges and a leaderboard.',
  },
  {
    icon: FileUp,
    title: 'Courses from your notes',
    body: 'Upload your slides or notes and get a course built from them.',
  },
];

const DIFFICULTY_TONE = { beginner: 'easy', intermediate: 'medium', advanced: 'hard' };

function SectionIntro({ label, title, body, center = false }) {
  return (
    <div className={center ? 'mx-auto max-w-2xl text-center' : 'max-w-2xl'}>
      {label && <span className="label">{label}</span>}
      <h2 className="display mt-2 text-3xl sm:text-4xl">{title}</h2>
      {body && <p className="mt-3 text-lg leading-relaxed text-muted">{body}</p>}
    </div>
  );
}

/** The product, as it looks: Redwan in a live call, mid-answer. */
function HeroPreview() {
  return (
    <div className="panel w-full">
      <div className="panel-head">
        <span className="label">Redwan · Live conversation</span>
        <span className="flex items-center gap-2 text-2xs font-medium text-primary-200">
          <span className="h-1.5 w-1.5 rounded-full bg-primary-400" />
          Speaking
        </span>
      </div>
      <div className="relative aspect-square w-full bg-canvas">
        <picture>
          <source srcSet="/landing/redwan.webp" type="image/webp" />
          <img
            src="/landing/redwan.jpg"
            alt="Redwan, the LearnQuest tutor, on a live call"
            width="720"
            height="720"
            className="h-full w-full object-cover"
          />
        </picture>
        <div className="absolute bottom-3 left-3 inline-flex items-center gap-2 rounded-pill border border-primary-400/40 bg-canvas/80 px-3 py-1.5 backdrop-blur">
          <span className="flex h-3.5 items-end gap-0.5" aria-hidden>
            {[6, 11, 14, 9, 5].map((h) => (
              <span key={h} className="w-0.5 rounded-sm bg-primary-300" style={{ height: `${h}px` }} />
            ))}
          </span>
          <span className="text-sm font-semibold text-primary-200">Redwan is speaking</span>
        </div>
      </div>
      <div className="space-y-3 border-t border-line p-4">
        <div className="flex flex-col items-end">
          <span className="mb-1 text-2xs text-faint">You</span>
          <p className="max-w-[85%] rounded-lg rounded-tr-sm bg-primary-600 px-3.5 py-2 text-sm text-white">
            Doesn&apos;t a LEFT JOIN drop the rows that don&apos;t match?
          </p>
        </div>
        <div className="flex flex-col items-start">
          <span className="mb-1 text-2xs text-faint">Redwan</span>
          <p className="max-w-[90%] rounded-lg rounded-tl-sm border border-line bg-raised px-3.5 py-2 text-sm text-body">
            That&apos;s the belief to fix. A LEFT JOIN keeps every row from the left table - so what
            fills the columns that had no match?
          </p>
        </div>
      </div>
    </div>
  );
}

/** What "diagnose" produces, drawn the way the quiz result shows it. */
function DiagnosisCard() {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <span className="label">Misconception detected</span>
        <Badge tone="medium">Active</Badge>
      </div>
      <p className="mt-3 text-lg font-medium leading-snug text-ink">
        &ldquo;You believe a LEFT JOIN drops the rows that have no match.&rdquo;
      </p>
      <p className="mt-2 text-sm text-muted">
        From your answer to question 2 of the SQL Joins quiz.
      </p>
      <div className="mt-4 flex items-center gap-2 rounded border border-line bg-raised px-3 py-2.5 text-sm text-body">
        <GraduationCap className="h-4 w-4 shrink-0 text-primary-300" />
        Ask Redwan where this belief goes wrong.
      </div>
    </div>
  );
}

function Courses() {
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
      <div className="flex min-h-[200px] items-center justify-center">
        <Spinner size="lg" label="Loading courses" />
      </div>
    );
  }
  // Empty catalogue or no backend - skip rather than advertise an empty shelf.
  if (state.courses.length === 0) return null;

  return (
    <section id="courses" className="scroll-mt-20 border-t border-line bg-surface py-20">
      <div className="mx-auto max-w-6xl px-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <SectionIntro
            label="Courses"
            title="Start with one of these"
            body={`${state.total} ${state.total === 1 ? 'course' : 'courses'} ready now, each with quizzes and practice.`}
          />
          <Link to="/register" className={buttonClasses('secondary', 'md')}>
            See all courses
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {state.courses.map((course) => (
            <Link
              key={course.id ?? course.slug}
              to={`/courses/${course.slug}`}
              className="card group flex flex-col p-6 transition-colors hover:border-line-strong hover:bg-raised"
            >
              <div className="flex flex-wrap items-center gap-2">
                {course.subject && <Badge tone="neutral">{course.subject}</Badge>}
                {course.difficulty && (
                  <Badge tone={DIFFICULTY_TONE[String(course.difficulty).toLowerCase()] ?? 'neutral'}>
                    {course.difficulty}
                  </Badge>
                )}
              </div>
              <h3 className="mt-4 text-lg font-semibold leading-snug text-ink">{course.title}</h3>
              {course.description && (
                <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-muted">{course.description}</p>
              )}
              <span className="mt-auto inline-flex items-center gap-1.5 pt-5 text-sm font-medium text-primary-300">
                View course
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
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
  // Set when the backend refused the session and AuthContext sent us here.
  const sessionEnded = Boolean(useLocation().state?.sessionEnded);

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
      {sessionEnded && (
        <div role="status" className="border-b border-line bg-medium/10 px-4 py-2 text-center text-sm text-body">
          Your session ended. <Link to="/login" className="font-medium text-primary-300 hover:underline">Sign in again</Link> to continue.
        </div>
      )}

      {/* ---------- Nav ---------- */}
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="text-lg font-semibold tracking-tight text-ink">LearnQuest</span>
          </Link>
          <nav className="hidden items-center gap-5 text-sm text-muted md:flex">
            <a href="#how" className="transition-colors hover:text-ink">How it works</a>
            <a href="#tutor" className="transition-colors hover:text-ink">The tutor</a>
            <a href="#courses" className="transition-colors hover:text-ink">Courses</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/login" className={buttonClasses('ghost', 'sm')}>Sign in</Link>
            <Link to="/register" className={buttonClasses('secondary', 'sm', 'hidden sm:inline-flex')}>
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_75%_35%,rgb(var(--primary-600)/0.14),transparent_55%)]"
          aria-hidden
        />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 lg:grid-cols-[1.1fr_1fr] lg:py-24">
          <div>
            <Badge tone="primary">AI tutor with a real face and voice</Badge>
            <h1 className="display mt-5 text-4xl leading-[1.08] sm:text-5xl lg:text-[3.5rem]">
              A tutor that knows <span className="text-primary-300">why</span> you got it wrong.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
              LearnQuest traces every wrong answer to the belief behind it. Then Redwan, your tutor,
              helps you see where it breaks. Talk to him out loud, or type.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/register" className={buttonClasses('primary', 'lg', 'w-full sm:w-auto')}>
                Start learning
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link to="/login" className={buttonClasses('secondary', 'lg', 'w-full sm:w-auto')}>
                Sign in
              </Link>
            </div>

            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
              {['Free for students', 'Talk out loud or type', 'Lessons, quizzes and SQL practice'].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <Check className="h-4 w-4 shrink-0 text-easy" strokeWidth={2.5} />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="mx-auto w-full max-w-md lg:max-w-none">
            <HeroPreview />
          </div>
        </div>
      </section>

      {/* ---------- The loop ---------- */}
      <section id="how" className="scroll-mt-20 border-t border-line bg-surface py-20">
        <div className="mx-auto max-w-6xl px-4">
          <SectionIntro
            label="How it works"
            title="Every mistake becomes something you fix"
            body="Most apps tell you an answer was wrong. LearnQuest finds out what you were thinking, and makes fixing it the lesson."
          />

          <div className="mt-12 grid items-start gap-10 lg:grid-cols-[1.25fr_1fr]">
            <ol className="grid gap-4 sm:grid-cols-2">
              {LOOP.map(({ icon: Icon, title, body }, i) => (
                <li key={title} className="card flex gap-4 p-5">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-line-strong bg-raised text-ink">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-2xs font-medium text-faint">Step {i + 1}</p>
                    <h3 className="text-base font-semibold text-ink">{title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <DiagnosisCard />
          </div>
        </div>
      </section>

      {/* ---------- Two ways to learn with the tutor ---------- */}
      <section id="tutor" className="scroll-mt-20 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <SectionIntro
            label="The tutor"
            title="Two ways to learn with Redwan"
            body="One tutor who remembers you, whichever way you choose to work."
            center
          />
          <div className="mt-12 grid gap-5 md:grid-cols-2">
            {MODES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="card p-6">
                <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-primary-500/30 bg-primary-500/10 text-primary-300">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold text-ink">{title}</h3>
                <p className="mt-2 leading-relaxed text-muted">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- What keeps it learned ---------- */}
      <section className="border-t border-line bg-surface py-20">
        <div className="mx-auto max-w-6xl px-4">
          <SectionIntro
            label="Built to stick"
            title="Everything after the lesson, too"
            body="Understanding something once is the start. These keep it."
          />
          <div className="mt-12 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div key={title}>
                <Icon className="h-6 w-6 text-muted" />
                <h3 className="mt-3 text-base font-semibold text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Live catalogue from the API ---------- */}
      <Courses />

      {/* ---------- Final call to action ---------- */}
      <section className="px-4 py-20">
        <div className="relative mx-auto max-w-4xl overflow-hidden rounded-xl border border-primary-500/30 bg-surface px-6 py-14 text-center">
          <div
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgb(var(--primary-600)/0.18),transparent_60%)]"
            aria-hidden
          />
          <div className="relative">
            <h2 className="display text-3xl sm:text-4xl">Your first lesson takes five minutes</h2>
            <p className="mx-auto mt-3 max-w-xl text-lg text-muted">
              Create an account, pick a course, and ask Redwan your first question.
            </p>
            <Link to="/register" className={buttonClasses('primary', 'lg', 'mt-8')}>
              Create your free account
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-600 text-white">
                <Sparkles className="h-4 w-4" />
              </span>
              <span className="font-semibold text-ink">LearnQuest</span>
            </div>
            <p className="mt-2 text-sm text-muted">A tutor that models your mind, not your score.</p>
          </div>
          <nav className="flex flex-wrap items-center gap-5 text-sm text-muted">
            <a href="#how" className="transition-colors hover:text-ink">How it works</a>
            <a href="#tutor" className="transition-colors hover:text-ink">The tutor</a>
            <Link to="/login" className="transition-colors hover:text-ink">Sign in</Link>
            <Link to="/register" className="transition-colors hover:text-ink">Get started</Link>
          </nav>
        </div>
        <div className="border-t border-line py-4 text-center text-xs text-faint">
          © 2026 LearnQuest
        </div>
      </footer>
    </div>
  );
}
