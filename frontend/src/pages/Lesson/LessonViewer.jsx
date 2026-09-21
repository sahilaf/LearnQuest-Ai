/**
 * LessonViewer - OWNER: Member 2. See plan.md §7.2.
 *
 * Full lesson viewer with Markdown rendering, video embeds, sticky outline,
 * auto-completion on 90% scroll, 30s heartbeat progress updates,
 * previous/next navigation, and "Ask the tutor about this" integration.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link, useNavigate, useParams } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { getLesson, updateProgress } from '../../api/lessons';
import { explain } from '../../api/tutor';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Modal,
  ProgressBar,
  Spinner,
} from '../../components/ui';

function slugify(text) {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export default function LessonViewer() {
  const { lessonId, id } = useParams();
  const currentLessonId = lessonId || id;
  const navigate = useNavigate();

  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Progress state
  const [isCompleted, setIsCompleted] = useState(false);
  const [secondsSpent, setSecondsSpent] = useState(0);
  const [scrollProgress, setScrollProgress] = useState(0);

  const secondsSpentRef = useRef(0);
  const isCompletedRef = useRef(false);
  const scrollRestoredRef = useRef(false);

  // Tutor modal state
  const [tutorModalOpen, setTutorModalOpen] = useState(false);
  const [selectedText, setSelectedText] = useState('');
  const [tutorQuery, setTutorQuery] = useState('');
  const [tutorLoading, setTutorLoading] = useState(false);
  const [tutorResponse, setTutorResponse] = useState(null);
  const [tutorError, setTutorError] = useState(null);

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
            window.scrollTo({ top: savedPos, behavior: 'smooth' });
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
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      updateProgress(currentLessonId, {
        status: isCompletedRef.current ? 'completed' : 'in_progress',
        seconds_spent: secondsSpentRef.current,
        last_position: Math.round(scrollTop),
      }).catch(() => {});
    }, 30000);

    return () => {
      clearInterval(timer);
      clearInterval(heartbeat);

      // Best effort flush on leave
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      updateProgress(currentLessonId, {
        status: isCompletedRef.current ? 'completed' : 'in_progress',
        seconds_spent: secondsSpentRef.current,
        last_position: Math.round(scrollTop),
      }).catch(() => {});
    };
  }, [currentLessonId]);

  // 3. Scroll tracking & 90% auto-completion
  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight;
      const clientHeight = document.documentElement.clientHeight;
      const totalScrollable = scrollHeight - clientHeight;

      if (totalScrollable <= 0) return;

      const pct = Math.min(100, Math.max(0, (scrollTop / totalScrollable) * 100));
      setScrollProgress(Math.round(pct));

      // Auto-complete at ~90% scroll depth
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

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [currentLessonId]);

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
    const el = document.getElementById(idToScroll);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
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
      <div className="flex min-h-[400px] items-center justify-center">
        <Spinner size="lg" label="Loading lesson..." />
      </div>
    );
  }

  if (error || !lesson) {
    return (
      <div className="py-8">
        <EmptyState
          title="Lesson Not Found"
          description={error || 'Unable to display this lesson.'}
          action={
            <Button variant="secondary" onClick={() => navigate('/courses')}>
              Return to Courses
            </Button>
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

  return (
    <div className="space-y-6 pb-20">
      {/* Top Breadcrumb & Progress Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4 dark:border-slate-800">
        <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <Link
            to="/courses"
            className="hover:text-slate-900 dark:hover:text-slate-100"
          >
            Courses
          </Link>
          {course && (
            <>
              <span>/</span>
              <Link
                to={`/courses/${courseSlug}`}
                className="hover:text-slate-900 dark:hover:text-slate-100"
              >
                {course.title}
              </Link>
            </>
          )}
          <span>/</span>
          <span className="font-medium text-slate-800 dark:text-slate-200">
            Lesson {lesson.order_index ?? 1}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {isCompleted ? (
            <Badge tone="easy">✓ Completed</Badge>
          ) : (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>{scrollProgress}% read</span>
              <div className="w-24">
                <ProgressBar value={scrollProgress} max={100} />
              </div>
            </div>
          )}

          <Button variant="secondary" size="sm" onClick={handleOpenTutor}>
            ✨ Ask the tutor about this
          </Button>
        </div>
      </div>

      {/* Main Grid: Content Area & Sticky Outline */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Left Column: Lesson Content */}
        <div className="lg:col-span-8 space-y-6">
          {/* Lesson Header */}
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <Badge tone="primary">Lesson {lesson.order_index ?? 1}</Badge>
              {lesson.estimated_minutes && (
                <span className="text-xs text-slate-500">
                  ⏱ {lesson.estimated_minutes} min read
                </span>
              )}
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50 sm:text-4xl">
              {lesson.title}
            </h1>

            {topicTags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {topicTags.map((tag) => (
                  <Badge key={tag} tone="default" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Video Embed (if available) */}
          {lesson.video_url && (
            <div className="aspect-video w-full overflow-hidden rounded-lg bg-black shadow-sm">
              {lesson.video_url.includes('youtube.com') ||
              lesson.video_url.includes('youtu.be') ? (
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

          {/* Markdown Content */}
          {lesson.content_md ? (
            <div className="prose prose-slate max-w-none dark:prose-invert">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children, ...props }) => {
                    const hId = slugify(children);
                    return (
                      <h1
                        id={hId}
                        className="mt-8 mb-4 scroll-mt-24 text-2xl font-bold text-slate-900 dark:text-slate-100"
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
                        className="mt-7 mb-3 scroll-mt-24 text-xl font-bold text-slate-900 dark:text-slate-100 border-b border-slate-100 pb-2 dark:border-slate-800"
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
                        className="mt-6 mb-2 scroll-mt-24 text-lg font-semibold text-slate-800 dark:text-slate-200"
                        {...props}
                      >
                        {children}
                      </h3>
                    );
                  },
                  p: ({ children, ...props }) => (
                    <p
                      className="my-3 leading-relaxed text-slate-700 dark:text-slate-300"
                      {...props}
                    >
                      {children}
                    </p>
                  ),
                  ul: ({ children, ...props }) => (
                    <ul
                      className="my-3 list-disc list-inside space-y-1 text-slate-700 dark:text-slate-300"
                      {...props}
                    >
                      {children}
                    </ul>
                  ),
                  ol: ({ children, ...props }) => (
                    <ol
                      className="my-3 list-decimal list-inside space-y-1 text-slate-700 dark:text-slate-300"
                      {...props}
                    >
                      {children}
                    </ol>
                  ),
                  code: ({ inline, className, children, ...props }) => {
                    return inline ? (
                      <code
                        className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-primary-700 dark:bg-slate-800 dark:text-primary-300"
                        {...props}
                      >
                        {children}
                      </code>
                    ) : (
                      <pre className="my-4 overflow-x-auto rounded-xl bg-slate-900 p-4 font-mono text-xs text-slate-100 dark:bg-slate-950">
                        <code className={className} {...props}>
                          {children}
                        </code>
                      </pre>
                    );
                  },
                  blockquote: ({ children, ...props }) => (
                    <blockquote
                      className="my-4 border-l-4 border-primary-500 bg-primary-50/40 py-2 pl-4 italic text-slate-700 dark:bg-primary-950/20 dark:text-slate-300"
                      {...props}
                    >
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {lesson.content_md}
              </ReactMarkdown>
            </div>
          ) : (
            <EmptyState
              title="No Content Yet"
              description="This lesson does not have written content published."
            />
          )}

          {/* Completion Celebration Card */}
          {isCompleted && (
            <Card className="border-emerald-200 bg-emerald-50/60 p-5 dark:border-emerald-900/50 dark:bg-emerald-950/30">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="font-semibold text-emerald-900 dark:text-emerald-200">
                    🎉 Lesson Completed!
                  </h3>
                  <p className="text-xs text-emerald-700 dark:text-emerald-300">
                    You have finished reading this lesson. Ready to test your understanding with a quiz?
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {lesson?.quiz_id && (
                    <Link to={`/quiz/${lesson.quiz_id}`}>
                      <Button variant="primary" size="sm">
                        Take Practice Quiz →
                      </Button>
                    </Link>
                  )}
                  {nextLesson ? (
                    <Link to={`/lessons/${nextLesson.id}`}>
                      <Button variant="secondary" size="sm">
                        Next Lesson →
                      </Button>
                    </Link>
                  ) : (
                    <Link to={`/courses/${courseSlug}`}>
                      <Button variant="secondary" size="sm">
                        Course Completed ✓
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Bottom Navigation Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 pt-6 dark:border-slate-800">
            {prevLesson ? (
              <Link to={`/lessons/${prevLesson.id}`}>
                <Button variant="secondary">
                  ← Previous: {prevLesson.title}
                </Button>
              </Link>
            ) : (
              <Link to={`/courses/${courseSlug}`}>
                <Button variant="secondary">
                  ← Course Overview
                </Button>
              </Link>
            )}

            <div className="flex items-center gap-2">
              {lesson?.quiz_id && (
                <Link to={`/quiz/${lesson.quiz_id}`}>
                  <Button variant="secondary">
                    Practice Quiz 🎯
                  </Button>
                </Link>
              )}

              {nextLesson ? (
                <Link to={`/lessons/${nextLesson.id}`}>
                  <Button variant="primary">
                    Next: {nextLesson.title} →
                  </Button>
                </Link>
              ) : (
                <Link to={`/courses/${courseSlug}`}>
                  <Button variant="secondary">
                    Finish Course ✓
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Sticky Table of Contents & Lesson Info */}
        <div className="lg:col-span-4">
          <div className="sticky top-20 space-y-6">
            {/* Outline Card */}
            {outline.length > 0 && (
              <Card className="p-5">
                <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">
                  On this page
                </h3>
                <nav className="space-y-1 text-sm max-h-[50vh] overflow-y-auto pr-1">
                  {outline.map((item, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => scrollToHeading(item.id)}
                      className={`block w-full text-left transition-colors hover:text-primary-600 dark:hover:text-primary-400 ${
                        item.level === 1
                          ? 'font-medium text-slate-800 dark:text-slate-200 py-1'
                          : item.level === 2
                          ? 'pl-3 text-xs text-slate-600 dark:text-slate-400 py-0.5'
                          : 'pl-6 text-[11px] text-slate-500 py-0.5'
                      }`}
                    >
                      {item.text}
                    </button>
                  ))}
                </nav>
              </Card>
            )}

            {/* Practice Quiz Card */}
            {lesson?.quiz_id && (
              <Card className="border-line bg-surface p-5 dark:border-[#242B35] dark:bg-[#171C23]">
                <div className="space-y-2">
                  <span className="label text-easy-fg dark:text-easy">
                    Assessment
                  </span>
                  <h4 className="text-base font-semibold text-ink dark:text-white">
                    Lesson Practice Quiz
                  </h4>
                  <p className="text-xs leading-relaxed text-muted dark:text-[#8A94A2]">
                    Test your understanding of the concepts covered in this lesson.
                  </p>
                  <Link to={`/quiz/${lesson.quiz_id}`} className="block pt-1">
                    <Button variant="primary" size="sm" className="w-full">
                      Start Quiz 🎯
                    </Button>
                  </Link>
                </div>
              </Card>
            )}

            {/* Tutor Shortcut Card */}
            <Card className="bg-primary-50 p-5 dark:bg-primary-900/20">
              <div className="space-y-2">
                <span className="label text-primary-700 dark:text-primary-300">
                  Personal AI tutor
                </span>
                <h4 className="text-base font-semibold">Need clarification?</h4>
                <p className="text-xs font-semibold leading-relaxed text-muted dark:text-[#8A94A2]">
                  Highlight any text on the page, then ask Nova to break it down for you.
                </p>
                <Button size="sm" onClick={handleOpenTutor} className="mt-2 w-full">
                  Ask about this lesson
                </Button>
              </div>
            </Card>

            {/* Course Syllabus Drawer / Sibling Lessons */}
            {course?.lessons && course.lessons.length > 0 && (
              <Card className="p-5">
                <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">
                  Course Lessons
                </h3>
                <div className="space-y-1.5 max-h-[35vh] overflow-y-auto text-xs pr-1">
                  {course.lessons.map((sibling) => {
                    const isCurrent = String(sibling.id) === String(lesson.id);
                    return (
                      <Link
                        key={sibling.id}
                        to={`/lessons/${sibling.id}`}
                        className={`flex items-center justify-between rounded-lg px-2.5 py-2 transition-colors ${
                          isCurrent
                            ? 'bg-primary-50 font-semibold text-primary-700 dark:bg-primary-950 dark:text-primary-300'
                            : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                        }`}
                      >
                        <span className="truncate pr-2">
                          {sibling.order_index}. {sibling.title}
                        </span>
                        {isCurrent && (
                          <span className="shrink-0 text-[10px] text-primary-600 font-bold">
                            Current
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </Card>
            )}
          </div>
        </div>
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
              className="block text-xs font-semibold uppercase tracking-wide text-muted dark:text-[#8A94A2]"
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
            <div className="animate-fade-in rounded-lg border-2 border-primary-200 bg-primary-50 p-4 dark:border-primary-900 dark:bg-primary-900/20">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-primary-700 dark:text-primary-300">
                Nova explains
              </p>
              <p className="text-sm font-semibold leading-relaxed text-body dark:text-white">
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
    </div>
  );
}
