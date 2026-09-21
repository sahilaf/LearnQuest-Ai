/**
 * CourseDetail - OWNER: Member 2. See plan.md §7.2.
 *
 * Course detail page displaying course metadata, ordered lesson list,
 * enrollment status check, and active enrollment action.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { enroll, getCourse, myEnrollments, myProgress } from '../../api/courses';
import { useAuth } from '../../context/AuthContext';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  Spinner,
  Tabs,
} from '../../components/ui';

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

export default function CourseDetail() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();

  const [course, setCourse] = useState(null);
  const [courseProgress, setCourseProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Active view tab: curriculum | skills | quizzes
  const [activeTab, setActiveTab] = useState('curriculum');
  const [expandedLessonId, setExpandedLessonId] = useState(null);

  // Enrollment state
  const [isEnrolled, setIsEnrolled] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState(null);
  const [enrollSuccess, setEnrollSuccess] = useState(false);

  // Fetch course details, enrollments, and progress for the active user
  const loadData = useCallback(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setEnrollError(null);

    const enrollmentPromise =
      isAuthenticated && user
        ? myEnrollments()
        : Promise.resolve({ items: [] });

    const progressPromise =
      isAuthenticated && user
        ? myProgress()
        : Promise.resolve({ items: [] });

    Promise.allSettled([getCourse(slug), enrollmentPromise, progressPromise])
      .then(([courseRes, enrollmentsRes, progressRes]) => {
        if (!isMounted) return;

        if (courseRes.status === 'fulfilled') {
          const courseData = courseRes.value;
          setCourse(courseData);

          // Check enrollment
          if (isAuthenticated && user && enrollmentsRes.status === 'fulfilled') {
            const enrollmentsData = enrollmentsRes.value;
            const items = Array.isArray(enrollmentsData)
              ? enrollmentsData
              : enrollmentsData?.items || [];
            const enrolled = items.some(
              (e) => e.course_id === courseData.id || e.course?.id === courseData.id
            );
            setIsEnrolled(enrolled);
          } else {
            setIsEnrolled(false);
          }

          // Check progress
          if (isAuthenticated && user && progressRes.status === 'fulfilled') {
            const progData = progressRes.value;
            const items = Array.isArray(progData) ? progData : progData?.items || [];
            const prog = items.find(
              (p) => p.course_id === courseData.id || p.course_slug === courseData.slug
            );
            setCourseProgress(prog || null);
          } else {
            setCourseProgress(null);
          }
        } else {
          const detail =
            courseRes.reason?.detail || `Course '${slug}' could not be found.`;
          setError(detail);
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [slug, isAuthenticated, user?.id]);

  useEffect(() => {
    const cancel = loadData();
    return cancel;
  }, [loadData]);

  const handleEnroll = async () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    if (!course?.id || isEnrolled || enrolling) return;

    setEnrolling(true);
    setEnrollError(null);

    try {
      await enroll(course.id);
      setIsEnrolled(true);
      setEnrollSuccess(true);
    } catch (err) {
      console.error('Enrollment failed:', err);
      setEnrollError(
        err?.detail || 'Failed to complete enrollment. Please try again.'
      );
    } finally {
      setEnrolling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[350px] items-center justify-center">
        <Spinner size="lg" label="Loading course details..." />
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="py-6">
        <Link
          to="/courses"
          className="mb-6 inline-flex items-center text-sm font-medium text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
        >
          ← Back to Courses
        </Link>
        <EmptyState
          title="Course Not Found"
          description={error || "We couldn't locate the course you requested."}
          action={
            <div className="flex gap-3">
              <Button variant="secondary" size="sm" onClick={() => navigate('/courses')}>
                Browse Courses
              </Button>
              <Button variant="primary" size="sm" onClick={loadData}>
                Try Again
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  const lessons = useMemo(
    () => [...(course.lessons || [])].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0)),
    [course?.lessons]
  );

  const completedLessonIds = useMemo(
    () => new Set(courseProgress?.completed_lesson_ids || []),
    [courseProgress?.completed_lesson_ids]
  );

  const inProgressLessonIds = useMemo(
    () => new Set(courseProgress?.in_progress_lesson_ids || []),
    [courseProgress?.in_progress_lesson_ids]
  );

  const nextLessonId = courseProgress?.next_lesson_id || lessons[0]?.id;
  const nextLesson = lessons.find((l) => l.id === nextLessonId) || lessons[0];
  const completionPercentage = courseProgress?.completion_percentage ?? 0;
  const completedCount = courseProgress?.completed_lessons ?? 0;
  const isAllCompleted = lessons.length > 0 && completedCount >= lessons.length;

  // Skills matrix: aggregate unique topic tags and the lessons that teach them
  const skillsMatrix = useMemo(() => {
    const map = new Map();
    lessons.forEach((lesson) => {
      (lesson.topic_tags || []).forEach((tag) => {
        if (!map.has(tag)) {
          map.set(tag, []);
        }
        map.get(tag).push(lesson);
      });
    });
    return Array.from(map.entries()).map(([tag, lessonList]) => ({
      tag,
      lessons: lessonList,
    }));
  }, [lessons]);

  // Quizzes list across track
  const quizzesList = useMemo(() => lessons.filter((l) => Boolean(l.quiz_id)), [lessons]);

  const tabsConfig = [
    { id: 'curriculum', label: 'Track Curriculum', badge: lessons.length },
    { id: 'skills', label: 'Skills & Concepts', badge: skillsMatrix.length },
    { id: 'quizzes', label: 'Problems & Quizzes', badge: quizzesList.length },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Breadcrumb / Back Link */}
      <div>
        <Link
          to="/courses"
          className="inline-flex items-center text-sm font-medium text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
        >
          ← Back to Tracks & Courses
        </Link>
      </div>

      {/* Course Hero Banner */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/60 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="default">{course.subject || 'Learning Track'}</Badge>
              <Badge tone={getDifficultyTone(course.difficulty)}>
                {course.difficulty || 'beginner'}
              </Badge>
              {isEnrolled && (
                <Badge tone={isAllCompleted ? 'easy' : 'warning'}>
                  {isAllCompleted ? '✓ Completed' : 'Enrolled'}
                </Badge>
              )}
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50 sm:text-3xl">
              {course.title}
            </h1>

            <p className="text-base text-slate-600 dark:text-slate-300 sm:text-lg">
              {course.description || 'No description provided for this course.'}
            </p>

            {/* Metadata Badges */}
            <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-500 dark:text-slate-400">
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 dark:bg-slate-500" />
                <span>{course.estimated_hours ? `${course.estimated_hours} Hours` : 'Self-paced'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 dark:bg-slate-500" />
                <span>{lessons.length} {lessons.length === 1 ? 'Module' : 'Modules'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 dark:bg-slate-500" />
                <span>{skillsMatrix.length} Core Skills</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 dark:bg-slate-500" />
                <span>{quizzesList.length} Practice Quizzes</span>
              </div>
            </div>

            {/* Progress Bar (if enrolled) */}
            {isEnrolled && lessons.length > 0 && (
              <div className="space-y-1.5 pt-2">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-600 dark:text-slate-300">
                  <span>Track Progress</span>
                  <span>
                    {completedCount} of {lessons.length} completed ({completionPercentage}%)
                  </span>
                </div>
                <ProgressBar
                  value={completionPercentage}
                  tone={isAllCompleted ? 'easy' : 'default'}
                />
              </div>
            )}
          </div>

          {/* Action / Next Step Box */}
          <div className="flex w-full flex-col gap-3 rounded-xl border border-slate-100 bg-slate-50/80 p-5 dark:border-slate-800 dark:bg-slate-800/40 lg:w-80 lg:shrink-0">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              {isEnrolled ? 'Next Action' : 'Start This Track'}
            </h3>

            {isEnrolled ? (
              <div className="space-y-3">
                {isAllCompleted ? (
                  <div className="space-y-3">
                    <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">
                      🎉 Track 100% Completed! Great work mastering this topic.
                    </div>
                    {lessons[0]?.id && (
                      <Link to={`/lessons/${lessons[0].id}`} className="block w-full">
                        <Button variant="secondary" className="w-full">
                          Review Lessons
                        </Button>
                      </Link>
                    )}
                  </div>
                ) : nextLesson ? (
                  <div className="space-y-3">
                    <div className="rounded-lg bg-primary-50 px-3 py-2 text-xs text-primary-800 dark:bg-primary-950/50 dark:text-primary-300">
                      <span className="font-semibold">Next up:</span> {nextLesson.title}
                    </div>
                    <Link to={`/lessons/${nextLesson.id}`} className="block w-full">
                      <Button variant="primary" className="w-full">
                        {completedCount > 0 ? 'Resume Track →' : 'Start Lesson 1 →'}
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <Button variant="secondary" disabled className="w-full">
                    No lessons yet
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <Button
                  variant="primary"
                  loading={enrolling}
                  onClick={handleEnroll}
                  className="w-full"
                >
                  Enroll in Track
                </Button>
                {lessons[0]?.id && (
                  <Link to={`/lessons/${lessons[0].id}`} className="block w-full">
                    <Button variant="secondary" className="w-full text-xs">
                      Preview Lesson 1 →
                    </Button>
                  </Link>
                )}
                <p className="text-center text-xs text-slate-500 dark:text-slate-400">
                  Instant free access • Hands-on practice
                </p>
              </div>
            )}

            {enrollSuccess && (
              <div className="animate-fade-in rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                🎉 Successfully enrolled! You can now start learning below.
              </div>
            )}

            {enrollError && (
              <div className="animate-fade-in rounded-lg bg-rose-50 p-2.5 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
                {enrollError}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* View Switcher Tabs */}
      <div className="space-y-6">
        <Tabs
          tabs={tabsConfig}
          activeTab={activeTab}
          onChange={setActiveTab}
          variant="underline"
        />

        {/* Tab 1: Track Curriculum (Modules, Lessons, Problems) */}
        {activeTab === 'curriculum' && (
          <div className="space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  Track Modules & Lessons
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Follow the structured learning path, read notes, and complete practice challenges.
                </p>
              </div>
              <span className="text-xs font-medium text-slate-500">
                {lessons.length} {lessons.length === 1 ? 'lesson' : 'lessons'}
              </span>
            </div>

            {lessons.length === 0 ? (
              <EmptyState
                title="No lessons published yet"
                description="The instructor has not added any lessons to this track yet. Check back soon!"
              />
            ) : (
              <div className="space-y-3">
                {lessons.map((lesson, idx) => {
                  const lessonNumber = lesson.order_index ?? idx + 1;
                  const topicTags = Array.isArray(lesson.topic_tags) ? lesson.topic_tags : [];
                  const isCompleted = completedLessonIds.has(lesson.id);
                  const isCurrent =
                    !isCompleted &&
                    (inProgressLessonIds.has(lesson.id) || lesson.id === nextLessonId);

                  return (
                    <Card
                      key={lesson.id}
                      className={`flex flex-col gap-4 transition-all ${
                        isCurrent
                          ? 'border-primary-400 bg-primary-50/20 dark:border-primary-600/60 dark:bg-primary-950/10'
                          : 'hover:border-slate-300 dark:hover:border-slate-700'
                      }`}
                    >
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-start gap-3.5">
                          <span
                            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-semibold ${
                              isCompleted
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                : isCurrent
                                ? 'bg-primary-600 text-white'
                                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                            }`}
                          >
                            {isCompleted ? '✓' : lessonNumber}
                          </span>

                          <div className="space-y-1.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <Link
                                to={`/lessons/${lesson.id}`}
                                className="font-semibold text-slate-900 hover:text-primary-600 dark:text-slate-100 dark:hover:text-primary-400"
                              >
                                {lesson.title}
                              </Link>
                              {isCompleted && (
                                <Badge tone="easy" className="text-[10px] py-0 px-1.5">
                                  Completed
                                </Badge>
                              )}
                              {isCurrent && (
                                <Badge tone="warning" className="text-[10px] py-0 px-1.5">
                                  Current
                                </Badge>
                              )}
                              {lesson.quiz_id && (
                                <Badge tone="default" className="text-[10px] py-0 px-1.5">
                                  Quiz Available
                                </Badge>
                              )}
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                              <span>
                                {lesson.estimated_minutes
                                  ? `~${lesson.estimated_minutes} min`
                                  : '10 min'}
                              </span>
                              {topicTags.length > 0 && (
                                <>
                                  <span>•</span>
                                  <div className="flex flex-wrap gap-1">
                                    {topicTags.map((tag) => (
                                      <Badge
                                        key={tag}
                                        tone="default"
                                        className="text-[10px] py-0 px-1.5"
                                      >
                                        {tag}
                                      </Badge>
                                    ))}
                                  </div>
                                </>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-2 justify-end">
                          {lesson.content_md && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-xs text-slate-600 dark:text-slate-300"
                              onClick={() =>
                                setExpandedLessonId((prev) =>
                                  prev === lesson.id ? null : lesson.id
                                )
                              }
                            >
                              {expandedLessonId === lesson.id ? 'Hide Material ▲' : 'Preview Material ▼'}
                            </Button>
                          )}
                          {lesson.quiz_id && (
                            <Link to={`/quiz/${lesson.quiz_id}`}>
                              <Button variant="ghost" size="sm" className="text-xs">
                                Practice Quiz
                              </Button>
                            </Link>
                          )}
                          <Link to={`/lessons/${lesson.id}`}>
                            <Button
                              variant={isCurrent ? 'primary' : 'secondary'}
                              size="sm"
                            >
                              {isCompleted ? 'Review' : isCurrent ? 'Resume →' : 'Start Lesson →'}
                            </Button>
                          </Link>
                        </div>
                      </div>

                      {/* Expandable Lesson Material & Notes */}
                      {expandedLessonId === lesson.id && lesson.content_md && (
                        <div className="mt-3 border-t border-slate-200 pt-4 dark:border-slate-800">
                          <div className="mb-3 flex items-center justify-between">
                            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                              Lesson Materials & Reading Notes
                            </h4>
                            <Link to={`/lessons/${lesson.id}`}>
                              <Button variant="primary" size="sm" className="text-xs">
                                Open in Fullscreen Reader →
                              </Button>
                            </Link>
                          </div>

                          {lesson.video_url && (
                            <div className="mb-4 aspect-video w-full max-w-2xl overflow-hidden rounded-lg bg-black">
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

                          <div className="prose prose-sm max-w-none rounded-lg bg-slate-50 p-4 text-slate-800 dark:bg-slate-900 dark:text-slate-200">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {lesson.content_md}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Skills & Concepts Matrix */}
        {activeTab === 'skills' && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Skills & Concepts Matrix
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Concepts covered in this track and the lessons that teach them.
              </p>
            </div>

            {skillsMatrix.length === 0 ? (
              <EmptyState
                title="No skills tagged yet"
                description="This course does not have structured skill tags configured."
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {skillsMatrix.map(({ tag, lessons: tagLessons }) => (
                  <Card key={tag} className="space-y-2 p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-primary-700 dark:text-primary-300">
                        {tag}
                      </span>
                      <Badge tone="default" className="text-[10px]">
                        {tagLessons.length} {tagLessons.length === 1 ? 'lesson' : 'lessons'}
                      </Badge>
                    </div>
                    <div className="space-y-1 pt-1 border-t border-slate-100 dark:border-slate-800">
                      {tagLessons.map((l) => (
                        <Link
                          key={l.id}
                          to={`/lessons/${l.id}`}
                          className="block truncate text-xs text-slate-600 hover:text-primary-600 dark:text-slate-400 dark:hover:text-primary-400"
                        >
                          • {l.title}
                        </Link>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Practice Problems & Quizzes */}
        {activeTab === 'quizzes' && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Practice Problems & Quizzes
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Test your mastery with AI-evaluated practice problems and diagnostic quizzes.
              </p>
            </div>

            {quizzesList.length === 0 ? (
              <EmptyState
                title="No practice quizzes available yet"
                description="Quizzes for this track will appear once questions are published or generated."
              />
            ) : (
              <div className="space-y-3">
                {quizzesList.map((lesson) => (
                  <Card
                    key={lesson.id}
                    className="flex flex-col gap-3 transition-all hover:border-slate-300 dark:hover:border-slate-700 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded bg-primary-100 text-xs font-bold text-primary-700 dark:bg-primary-950 dark:text-primary-300">
                          Q
                        </span>
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                          {lesson.title} — Practice Quiz
                        </h3>
                      </div>
                      <p className="text-xs text-slate-500">
                        Diagnostic quiz assessing skills in {lesson.topic_tags?.join(', ') || 'this module'}.
                      </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <Link to={`/quiz/${lesson.quiz_id}`}>
                        <Button variant="primary" size="sm">
                          Take Quiz →
                        </Button>
                      </Link>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
