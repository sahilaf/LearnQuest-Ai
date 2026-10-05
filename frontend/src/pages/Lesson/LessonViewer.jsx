/**
 * LessonViewer - OWNER: Member 2. See plan.md §7.2.
 *
 * Full lesson viewer with Markdown rendering, video embeds, sticky outline,
 * auto-completion on 90% scroll, 30s heartbeat progress updates,
 * previous/next navigation, and "Ask the tutor about this" integration.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, ListTree, Sparkles } from 'lucide-react';
import remarkGfm from 'remark-gfm';
import { getLesson, updateProgress } from '../../api/lessons';
import { createConversation, explain } from '../../api/tutor';
import { generateQuiz } from '../../api/quizzes';
import { myQuota } from '../../api/jobs';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Modal,
  Skeleton,
  Spinner,
} from '../../components/ui';
import useLiveConversation from '../Tutor/useLiveConversation';
import useTutorVoice from '../Tutor/useTutorVoice';
import LessonNarrator from './LessonNarrator';
import useLessonNarration from './useLessonNarration';

function slugify(text) {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * Markdown renderers, defined once. Inline in render they were new component
 * types every render, so React remounted every paragraph each second (the
 * time counter re-renders the page) - which also detached the word ranges
 * lesson narration highlights.
 */
const MARKDOWN_COMPONENTS = {
  h1: ({ children, ...props }) => {
    const hId = slugify(children);
    return (
      <h1
        id={hId}
        className="mt-8 mb-4 scroll-mt-4 text-2xl font-bold text-ink"
        {...props}
      >
        {children}
      </h1>
    );
  },
  h2: ({ children, ...props }) => {
    const hId = slugify(children);
    return (
      <h2
        id={hId}
        className="mt-7 mb-3 scroll-mt-4 text-xl font-bold text-ink border-b border-line pb-2"
        {...props}
      >
        {children}
      </h2>
    );
  },
  h3: ({ children, ...props }) => {
    const hId = slugify(children);
    return (
      <h3
        id={hId}
        className="mt-6 mb-2 scroll-mt-4 text-lg font-semibold text-ink"
        {...props}
      >
        {children}
      </h3>
    );
  },
  p: ({ children, ...props }) => (
    <p
      className="my-3 leading-relaxed text-body"
      {...props}
    >
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul
      className="my-3 list-disc list-inside space-y-1 text-body"
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol
      className="my-3 list-decimal list-inside space-y-1 text-body"
      {...props}
    >
      {children}
    </ol>
  ),
  // react-markdown 9 no longer passes `inline`, so every inline `code` word
  // used to render as a whole code block inside its paragraph (<pre> in <p>).
  // A code block is the one wrapped in <pre>; that wrapper gets the styling.
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto rounded-xl bg-canvas p-4 font-mono text-xs text-ink">
      {children}
    </pre>
  ),
  code: ({ className, children }) => {
    const block = /language-/.test(className || '') || String(children).includes('\n');
    return block ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="rounded bg-raised px-1.5 py-0.5 font-mono text-xs text-ink">{children}</code>
    );
  },
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-4 border-l-4 border-primary-500 bg-primary-500/10 py-2 pl-4 italic text-body"
      {...props}
    >
      {children}
    </blockquote>
  ),
};

export default function LessonViewer() {
  const { lessonId, id } = useParams();
  const currentLessonId = lessonId || id;
  const navigate = useNavigate();

  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Progress state
  const [isCompleted, setIsCompleted] = useState(false);
  const [, setSecondsSpent] = useState(0);
  const [scrollProgress, setScrollProgress] = useState(0);

  const secondsSpentRef = useRef(0);
  const isCompletedRef = useRef(false);
  const scrollRestoredRef = useRef(false);
  // Read on leaving, when the lesson pane is already gone.
  const lastScrollTopRef = useRef(0);

  // Tutor modal state
  const [tutorModalOpen, setTutorModalOpen] = useState(false);
  const [selectedText, setSelectedText] = useState('');
  const [tutorQuery, setTutorQuery] = useState('');
  const [tutorLoading, setTutorLoading] = useState(false);
  const [tutorResponse, setTutorResponse] = useState(null);
  const [tutorError, setTutorError] = useState(null);

  // Redwan reading the lesson aloud (see useLessonNarration). The avatar is
  // opt-in, as on the tutor page; without it he reads voice only.
  const contentRef = useRef(null);
  // The lesson text scrolls in its own pane, beside Redwan; everything that
  // used to read window.scrollY (progress, resume, follow-along) reads this.
  const scrollRef = useRef(null);
  const shellRef = useRef(null);
  const [shellHeight, setShellHeight] = useState(null);
  const [contentsOpen, setContentsOpen] = useState(false);
  const avatarRef = useRef(null);
  const [avatarConnected, setAvatarConnected] = useState(false);
  const [avatarLive, setAvatarLive] = useState(false);
  const [muted, setMuted] = useState(false);
  const voice = useTutorVoice({ avatarRef, useAvatar: avatarLive, muted });
  const live = useLiveConversation({ voice });
  const narration = useLessonNarration({
    containerRef: contentRef,
    scrollRef,
    voice,
    contentKey: `${currentLessonId}:${lesson?.content_md?.length ?? 0}`,
  });
  // Questions asked while listening go into one conversation per visit,
  // attached to this lesson, so Chat has them afterwards.
  const askConversationRef = useRef(null);

  // AI Quiz Generation State & Quota (Slot 9D)
  const [generatingQuiz, setGeneratingQuiz] = useState(false);
  const [quizGenError, setQuizGenError] = useState(null);
  const [quota, setQuota] = useState(null);

  useEffect(() => {
    let isMounted = true;
    myQuota()
      .then((data) => {
        if (isMounted) setQuota(data);
      })
      .catch(() => {
        // Non-fatal if quota cannot be fetched
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handlePracticeThisLesson = async () => {
    if (!currentLessonId || generatingQuiz) return;
    if (quota && quota.remaining <= 0) {
      setQuizGenError("Today's generation limit has been reached.");
      return;
    }
    setGeneratingQuiz(true);
    setQuizGenError(null);
    try {
      const data = await generateQuiz(currentLessonId);
      if (data?.id) {
        navigate(`/quiz/${data.id}`);
      } else {
        setQuizGenError('Quiz was generated with an unexpected response shape. Please try again.');
      }
    } catch (err) {
      console.error('Quiz generation failed:', err);
      if (err?.status === 429 || err?.response?.status === 429) {
        setQuizGenError("Today's generation limit has been reached.");
      } else {
        const msg = err?.detail || err?.response?.data?.detail || 'Failed to generate quiz for this lesson. Please try again.';
        setQuizGenError(msg);
      }
    } finally {
      setGeneratingQuiz(false);
    }
  };

  const handleStartQuiz = () => {
    if (lesson?.quiz_id) {
      navigate(`/quiz/${lesson.quiz_id}`);
    } else {
      handlePracticeThisLesson();
    }
  };

  // The voice path changes when video connects or drops: pause rather than
  // carry on with the clock of the old path.
  const narrationRef = useRef(narration);
  narrationRef.current = narration;
  useEffect(() => { narrationRef.current.pause(); }, [avatarLive]);

  const renderedLesson = useMemo(() => (lesson?.content_md ? (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
      {lesson.content_md}
    </ReactMarkdown>
  ) : null), [lesson?.content_md]);

  /** Stop reading and ask Redwan out loud about where we are. */
  const askWhileListening = async () => {
    narration.pause();
    avatarRef.current?.resume?.();
    let ref = askConversationRef.current;
    if (!ref) {
      try {
        const conv = await createConversation({ title: `Lesson: ${lesson?.title || 'questions'}`, lesson_id: currentLessonId });
        ref = conv.number;
        askConversationRef.current = ref;
      } catch {
        ref = null; // the call still works; it just is not saved
      }
    }
    live.start(ref, { reading: narration.passage() });
  };

  /** Done asking: hang up and carry on reading. */
  const continueListening = () => {
    live.stop();
    narration.play();
  };

  const avatar = {
    ref: avatarRef,
    connected: avatarConnected,
    connect: () => setAvatarConnected(true),
    disconnect: () => { avatarRef.current?.stopNow(); setAvatarConnected(false); setAvatarLive(false); },
    setLive: setAvatarLive,
    muted,
    toggleMute: () => setMuted((m) => !m),
  };

  // 1. Fetch lesson data
  const fetchLessonData = useCallback(() => {
    if (!currentLessonId) return;
    let isMounted = true;
    setLoading(true);
    setError(null);
    scrollRestoredRef.current = false;
    isCompletedRef.current = false;
    setIsCompleted(false);
    secondsSpentRef.current = 0;
    setSecondsSpent(0);

    getLesson(currentLessonId)
      .then((data) => {
        if (!isMounted) return;
        setLesson(data);

        // Check if previously completed
        if (data.status === 'completed' || data.progress?.status === 'completed') {
          setIsCompleted(true);
          isCompletedRef.current = true;
        }

        // Restore scroll position
        const savedPos = data.last_position ?? data.progress?.last_position;
        if (savedPos && savedPos > 50 && !scrollRestoredRef.current) {
          scrollRestoredRef.current = true;
          setTimeout(() => {
            scrollRef.current?.scrollTo({ top: savedPos, behavior: 'smooth' });
          }, 250);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.warn('Failed to load lesson:', err);
        setError(err?.detail || 'Lesson could not be loaded. Please try again.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [currentLessonId]);

  useEffect(() => {
    const cancel = fetchLessonData();
    return cancel;
  }, [fetchLessonData]);

  // 2. Active time counter & 30-second heartbeat
  useEffect(() => {
    if (!currentLessonId) return undefined;

    const timer = setInterval(() => {
      secondsSpentRef.current += 1;
      setSecondsSpent((s) => s + 1);
    }, 1000);

    const heartbeat = setInterval(() => {
      updateProgress(currentLessonId, {
        status: isCompletedRef.current ? 'completed' : 'in_progress',
        seconds_spent: secondsSpentRef.current,
        last_position: Math.round(lastScrollTopRef.current),
      }).catch(() => {});
    }, 30000);

    return () => {
      clearInterval(timer);
      clearInterval(heartbeat);

      // Best effort flush on leave
      updateProgress(currentLessonId, {
        status: isCompletedRef.current ? 'completed' : 'in_progress',
        seconds_spent: secondsSpentRef.current,
        last_position: Math.round(lastScrollTopRef.current),
      }).catch(() => {});
    };
  }, [currentLessonId]);

  // 3. Reading progress & auto-completion at ~90%, from the lesson pane.
  useEffect(() => {
    const pane = scrollRef.current;
    if (!pane) return undefined;
    const handleScroll = () => {
      const scrollTop = pane.scrollTop;
      lastScrollTopRef.current = scrollTop;
      const totalScrollable = pane.scrollHeight - pane.clientHeight;
      if (totalScrollable <= 0) return;

      const pct = Math.min(100, Math.max(0, (scrollTop / totalScrollable) * 100));
      setScrollProgress(Math.round(pct));

      if (pct >= 88 && !isCompletedRef.current) {
        isCompletedRef.current = true;
        setIsCompleted(true);
        updateProgress(currentLessonId, {
          status: 'completed',
          seconds_spent: secondsSpentRef.current,
          last_position: Math.round(scrollTop),
        }).catch((err) => {
          console.warn('Auto-completion update failed:', err);
        });
      }
    };

    pane.addEventListener('scroll', handleScroll, { passive: true });
    return () => pane.removeEventListener('scroll', handleScroll);
  }, [currentLessonId, lesson]);

  // The two halves fill the screen below the app's header, and only the
  // lesson pane scrolls: Redwan stays in view the whole time.
  useLayoutEffect(() => {
    const el = shellRef.current;
    if (!el) return undefined;
    const fit = () => {
      const top = el.getBoundingClientRect().top + window.scrollY;
      const wide = window.matchMedia('(min-width: 1024px)').matches;
      // Whatever the layout puts below us (padding; on phones it covers the
      // fixed tab bar) is measured, not guessed, so the page itself never
      // scrolls - only the lesson pane does.
      const below = document.documentElement.scrollHeight - (top + el.offsetHeight);
      const reserve = Math.max(below, 16);
      setShellHeight(Math.max(wide ? 520 : 420, Math.floor(window.innerHeight - top - reserve)));
      window.scrollTo(0, 0);
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [lesson]);

  // 4. Extract Headings for Table of Contents / Outline
  const outline = useMemo(() => {
    if (!lesson?.content_md) return [];
    const lines = lesson.content_md.split('\n');
    const items = [];
    for (const line of lines) {
      const match = line.match(/^(#{1,3})\s+(.+)$/);
      if (match) {
        const level = match[1].length;
        const text = match[2].trim();
        items.push({
          level,
          text,
          id: slugify(text),
        });
      }
    }
    return items;
  }, [lesson?.content_md]);

  const scrollToHeading = (idToScroll) => {
    setContentsOpen(false);
    document.getElementById(idToScroll)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // 5. "Ask the tutor about this" handler
  const handleOpenTutor = () => {
    const sel = window.getSelection()?.toString()?.trim() || '';
    setSelectedText(sel);
    // The question box starts empty when there is a highlight: the excerpt is
    // already the subject, so pre-filling it with "Explain this concept: ..."
    // only gave the student something to delete.
    setTutorQuery(sel ? '' : `Explain the main idea of ${lesson?.title || 'this lesson'}`);
    setTutorResponse(null);
    setTutorError(null);
    setTutorModalOpen(true);
  };

  const handleAskTutorSubmit = async (e) => {
    e?.preventDefault();

    const question = tutorQuery.trim();
    // With a highlight the excerpt alone is a valid request, so only demand a
    // typed question when there is nothing highlighted.
    if (!question && !selectedText) return;

    setTutorLoading(true);
    setTutorError(null);
    setTutorResponse(null);

    try {
      // `selection` is the excerpt the student highlighted - the backend prompt
      // says "a student highlighted the following". Sending the typed question
      // here told the model they had highlighted their own question.
      const res = await explain(currentLessonId, selectedText || question, question);
      const explanation = res?.explanation ?? res?.reply;

      if (typeof explanation === 'string' && explanation.trim()) {
        setTutorResponse(explanation.trim());
      } else {
        // Previously this fell back to a cheerful placeholder, so an empty or
        // unexpected payload looked exactly like a real answer.
        setTutorError('The tutor returned an empty response. Please try again.');
      }
    } catch (err) {
      // This used to swallow every failure and show a fake answer, which made
      // auth, network and server errors indistinguishable from easy.
      // api/client.js normalises rejections to { status, detail, code }.
      const { status, detail, code } = err || {};
      if (status === 401 || status === 403) {
        setTutorError('Your session has expired. Sign in again to ask the tutor.');
      } else if (status === 0 || code === 'NETWORK_ERROR') {
        setTutorError('Could not reach the tutor. Check that the server is running, then try again.');
      } else {
        setTutorError(detail || `The tutor request failed (${status ?? 'unknown error'}).`);
      }
    } finally {
      setTutorLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 pb-20">
        <div className="flex items-center gap-2 text-xs text-muted mb-2">
          <Spinner size="sm" label="Loading lesson" />
          <span>Loading lesson content...</span>
        </div>
        <div className="flex items-center justify-between border-b border-line pb-4">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-8 w-36 rounded-lg" />
        </div>
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          <div className="lg:col-span-8 space-y-6">
            <div className="space-y-3">
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-9 w-3/4" />
              <div className="flex gap-2">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
              </div>
            </div>
            <div className="space-y-3 pt-4">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-28 w-full rounded-xl" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-9/12" />
            </div>
          </div>
          <div className="lg:col-span-4 space-y-4">
            <Card className="p-5 space-y-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-3 w-4/6" />
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (error || !lesson) {
    return (
      <div className="py-8 space-y-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/courses')}>
          ← Return to Courses
        </Button>
        <EmptyState
          title="Lesson Not Found"
          description={error || 'Unable to display this lesson.'}
          action={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => navigate('/courses')}>
                Return to Courses
              </Button>
              <Button variant="primary" onClick={fetchLessonData}>
                Try Again
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  const course = lesson.course;
  const courseSlug = course?.slug || course?.id;
  const prevLesson = lesson.prev_lesson;
  const nextLesson = lesson.next_lesson;
  const topicTags = Array.isArray(lesson.topic_tags) ? lesson.topic_tags : [];

  const percentRead = isCompleted ? 100 : scrollProgress;
  const siblings = course?.lessons || [];
  const TOOL = 'inline-flex items-center gap-1.5 rounded border border-line px-2.5 py-1.5 text-xs font-medium text-body transition-colors hover:border-muted hover:text-ink';

  return (
    <>
      <div
        ref={shellRef}
        style={shellHeight ? { height: shellHeight } : undefined}
        className="-mb-6 flex flex-col gap-4 lg:-mb-12 lg:grid lg:grid-cols-2 lg:gap-6"
      >
        {/* ---- Left half: Redwan ---- */}
        <section aria-label="Redwan, your tutor" className="shrink-0 lg:min-h-0">
          <LessonNarrator
            narration={narration}
            live={live}
            voice={voice}
            avatar={avatar}
            onAsk={askWhileListening}
            onContinue={continueListening}
            canRead={Boolean(lesson.content_md)}
          />
        </section>

        {/* ---- Right half: the lesson, scrolling on its own ---- */}
        <section aria-label="Lesson" className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-line bg-surface">
          <header className="shrink-0 border-b border-line px-4 py-3 sm:px-6">
            <div className="flex items-center gap-2">
              <nav aria-label="Breadcrumb" className="flex min-w-0 flex-1 items-center gap-1.5 text-xs text-muted">
                <Link to="/courses" className="shrink-0 hover:text-ink">Courses</Link>
                {course && (
                  <>
                    <ChevronRight className="h-3 w-3 shrink-0" />
                    <Link to={`/courses/${courseSlug}`} className="truncate hover:text-ink">{course.title}</Link>
                  </>
                )}
                <ChevronRight className="h-3 w-3 shrink-0" />
                <span className="shrink-0 font-medium text-ink">Lesson {lesson.order_index ?? 1}</span>
              </nav>

              <div className="relative flex shrink-0 items-center gap-1.5">
                {(outline.length > 0 || siblings.length > 0) && (
                  <button
                    type="button"
                    onClick={() => setContentsOpen((open) => !open)}
                    aria-expanded={contentsOpen}
                    aria-label="Contents"
                    className={TOOL}
                  >
                    <ListTree className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Contents</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleOpenTutor}
                  aria-label="Explain a selection"
                  className={TOOL}
                  title="Highlight text in the lesson first, then press this"
                >
                  <Sparkles className="h-3.5 w-3.5 text-primary-300" />
                  <span className="hidden sm:inline">Explain a selection</span>
                </button>

                {contentsOpen && (
                  <>
                    <button
                      type="button"
                      aria-label="Close contents"
                      className="fixed inset-0 z-20 cursor-default"
                      onClick={() => setContentsOpen(false)}
                    />
                    <div className="card absolute right-0 top-full z-30 mt-2 max-h-[60vh] w-72 overflow-y-auto p-3">
                      {outline.length > 0 && (
                        <>
                          <p className="label px-2 pb-1.5">In this lesson</p>
                          {outline.map((item, i) => (
                            <button
                              key={`${item.id}-${i}`}
                              type="button"
                              onClick={() => scrollToHeading(item.id)}
                              className={`block w-full rounded px-2 py-1.5 text-left text-sm transition-colors hover:bg-raised hover:text-ink ${
                                item.level === 1 ? 'font-medium text-ink' : item.level === 2 ? 'pl-4 text-body' : 'pl-6 text-xs text-muted'
                              }`}
                            >
                              {item.text}
                            </button>
                          ))}
                        </>
                      )}
                      {siblings.length > 0 && (
                        <>
                          <p className="label px-2 pb-1.5 pt-3">Lessons in this course</p>
                          {siblings.map((sibling) => {
                            const isCurrent = String(sibling.id) === String(lesson.id);
                            return (
                              <Link
                                key={sibling.id}
                                to={`/lessons/${sibling.id}`}
                                onClick={() => setContentsOpen(false)}
                                className={`flex items-center justify-between gap-2 rounded px-2 py-1.5 text-sm transition-colors ${
                                  isCurrent ? 'bg-primary-500/15 font-medium text-ink' : 'text-body hover:bg-raised'
                                }`}
                              >
                                <span className="truncate">{sibling.order_index}. {sibling.title}</span>
                                {isCurrent && <span className="shrink-0 text-2xs text-primary-300">Here</span>}
                              </Link>
                            );
                          })}
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="mt-2.5 flex items-center gap-3">
              <div className="h-1 flex-1 overflow-hidden rounded-pill bg-line">
                <div className="h-full bg-easy transition-[width] duration-300" style={{ width: `${percentRead}%` }} />
              </div>
              <span className={`shrink-0 text-xs ${isCompleted ? 'text-easy-fg' : 'text-muted'}`}>
                {isCompleted ? '✓ Completed' : `${percentRead}% read`}
              </span>
            </div>
          </header>

          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <article className="mx-auto max-w-2xl px-4 py-6 sm:px-8 sm:py-8">
              <div className="mb-6">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                  <Badge tone="primary">Lesson {lesson.order_index ?? 1}</Badge>
                  {lesson.estimated_minutes && <span>{lesson.estimated_minutes} min read</span>}
                </div>
                <h1 className="mt-3 text-2xl font-bold tracking-tight text-ink sm:text-3xl">{lesson.title}</h1>
                {topicTags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {topicTags.map((tag) => (
                      <Badge key={tag} tone="default" className="text-xs">{tag}</Badge>
                    ))}
                  </div>
                )}
              </div>

              {lesson.video_url && (
                <div className="mb-6 aspect-video w-full overflow-hidden rounded-lg bg-black">
                  {lesson.video_url.includes('youtube.com') || lesson.video_url.includes('youtu.be') ? (
                    <iframe
                      src={lesson.video_url.replace('watch?v=', 'embed/')}
                      title={lesson.title}
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                      allowFullScreen
                      className="h-full w-full border-0"
                    />
                  ) : (
                    <video src={lesson.video_url} controls className="h-full w-full" />
                  )}
                </div>
              )}

              {lesson.content_md ? (
                <div ref={contentRef} className="prose prose-slate max-w-none" data-narration-active={narration.active || undefined}>
                  {renderedLesson}
                </div>
              ) : (
                <EmptyState title="No content yet" description="This lesson does not have written content published." />
              )}

              {/* ---- End of the lesson: one next step ---- */}
              <div className="mt-10 space-y-5 border-t border-line pt-6">
                <div className="rounded-lg border border-line bg-raised p-5">
                  <p className="text-base font-semibold text-ink">
                    {isCompleted ? 'Lesson complete - check what you learned' : 'Finished reading? Check what you learned'}
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    A short quiz on this lesson. A wrong answer shows you the exact idea you mixed up.
                  </p>
                  {quizGenError && (
                    <p className="mt-3 rounded border border-hard/40 bg-hard-bg p-2.5 text-xs text-hard-fg">{quizGenError}</p>
                  )}
                  {quota && quota.remaining <= 0 && !lesson.quiz_id && !quizGenError && (
                    <p className="mt-3 rounded border border-medium/40 bg-medium-bg p-2.5 text-xs text-medium-fg">
                      Today&apos;s quiz generation limit has been reached.
                    </p>
                  )}
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <Button variant="primary" loading={generatingQuiz} disabled={generatingQuiz} onClick={handleStartQuiz}>
                      {generatingQuiz ? 'Generating quiz (~8s)...' : 'Quiz me →'}
                    </Button>
                    {quota && !lesson.quiz_id && (
                      <span className="text-xs text-muted">
                        {quota.remaining} quiz generation{quota.remaining === 1 ? '' : 's'} left today
                      </span>
                    )}
                  </div>
                </div>

                <nav aria-label="Lessons" className="flex flex-wrap items-center justify-between gap-3 text-sm">
                  {prevLesson ? (
                    <Link to={`/lessons/${prevLesson.id}`} className="inline-flex min-w-0 items-center gap-1 text-muted hover:text-ink">
                      <ChevronLeft className="h-4 w-4 shrink-0" />
                      <span className="truncate">{prevLesson.title}</span>
                    </Link>
                  ) : (
                    <Link to={`/courses/${courseSlug}`} className="inline-flex items-center gap-1 text-muted hover:text-ink">
                      <ChevronLeft className="h-4 w-4" />
                      Course overview
                    </Link>
                  )}
                  {nextLesson ? (
                    <Link to={`/lessons/${nextLesson.id}`} className="inline-flex min-w-0 items-center gap-1 font-medium text-body hover:text-ink">
                      <span className="truncate">Next: {nextLesson.title}</span>
                      <ChevronRight className="h-4 w-4 shrink-0" />
                    </Link>
                  ) : (
                    <Link to={`/courses/${courseSlug}`} className="inline-flex items-center gap-1 font-medium text-body hover:text-ink">
                      Back to the course
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  )}
                </nav>
              </div>
            </article>
          </div>
        </section>
      </div>

      {/* Tutor Interaction Modal */}
      <Modal
        open={tutorModalOpen}
        onClose={() => setTutorModalOpen(false)}
        title="Ask the AI Tutor"
        footer={
          <div className="flex w-full items-center justify-between">
            <Link to={`/tutor?lessonId=${currentLessonId}`}>
              <Button variant="ghost" size="sm">
                Open Full Tutor Page →
              </Button>
            </Link>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setTutorModalOpen(false)}
            >
              Close
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          {selectedText && (
            <div className="rounded-lg border-2 border-info/30 bg-info-bg p-3.5">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-info-fg">
                Highlighted from the lesson
              </p>
              <p className="line-clamp-4 text-sm font-semibold italic text-body">
                “{selectedText}”
              </p>
            </div>
          )}

          <form onSubmit={handleAskTutorSubmit} className="space-y-3">
            <label
              htmlFor="tutor-question"
              className="block text-xs font-semibold uppercase tracking-wide text-muted"
            >
              {selectedText ? 'Your question (optional)' : 'Your question'}
            </label>
            <textarea
              id="tutor-question"
              rows={3}
              value={tutorQuery}
              onChange={(e) => setTutorQuery(e.target.value)}
              placeholder={
                selectedText
                  ? 'Ask something specific, or leave blank to just have this explained'
                  : 'What would you like the tutor to explain about this lesson?'
              }
              className="field resize-none"
            />
            <div className="flex justify-end">
              <Button
                size="sm"
                loading={tutorLoading}
                type="submit"
                disabled={!tutorQuery.trim() && !selectedText}
              >
                {tutorLoading ? 'Thinking' : 'Explain'}
              </Button>
            </div>
          </form>

          {tutorResponse && (
            <div className="animate-fade-in rounded-lg border border-primary-500/30 bg-primary-500/10 p-4">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-primary-300">
                Redwan explains
              </p>
              <p className="text-sm leading-relaxed text-body">
                {tutorResponse}
              </p>
            </div>
          )}

          {tutorError && (
            <div className="animate-fade-in rounded-lg border-2 border-hard/40 bg-hard-bg p-4">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-hard-fg">
                Could not get an answer
              </p>
              <p className="text-sm font-semibold leading-relaxed text-body">{tutorError}</p>
              <div className="mt-3">
                <Button size="sm" variant="secondary" onClick={handleAskTutorSubmit}>
                  Try again
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}
