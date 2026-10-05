/**
 * LearnHub - Unified learning center.
 * Combines My Courses, Browse Catalog, AI Roadmap, and SQL Challenges into one place.
 * Top actions: "Upload Notes" and "Generate a Course".
 */
import { useEffect, useState, useMemo } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  BookOpen,
  Compass,
  Map,
  Code2,
  UploadCloud,
  Sparkles,
} from 'lucide-react';


import { myProgress, generateCourse } from '../../api/courses';
import { myQuota } from '../../api/jobs';
import useGenerationJob from '../../hooks/useGenerationJob';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  ProgressBar,
  Select,
  Spinner,
} from '../../components/ui';

import CourseCatalog from '../Courses/CourseCatalog';
import RoadmapPage from '../Roadmap/RoadmapPage';
import PracticeList from '../Practice/PracticeList';

const N_LESSONS_OPTIONS = [
  { value: '3', label: '3 Lessons (Quick intro)' },
  { value: '4', label: '4 Lessons (Standard track)' },
  { value: '5', label: '5 Lessons (Comprehensive)' },
  { value: '6', label: '6 Lessons (Deep dive)' },
];

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

export default function LearnHub() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const tabParam = searchParams.get('tab') || 'my-courses';
  const activeTab = useMemo(() => {
    if (['my-courses', 'browse', 'roadmap', 'sql-challenges'].includes(tabParam)) {
      return tabParam;
    }
    return 'my-courses';
  }, [tabParam]);

  const setActiveTab = (tab) => {
    setSearchParams({ tab });
  };

  // Enrolled courses state for "My Courses" tab
  const [progressItems, setProgressItems] = useState([]);
  const [loadingProgress, setLoadingProgress] = useState(true);

  // Generate Course Modal state
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [courseGoal, setCourseGoal] = useState('');
  const [nLessons, setNLessons] = useState(4);
  const [courseGoalError, setCourseGoalError] = useState(null);
  const [quota, setQuota] = useState(null);
  const courseJob = useGenerationJob();

  useEffect(() => {
    myQuota().then((q) => q && setQuota(q)).catch(() => {});
  }, []);

  useEffect(() => {
    let isMounted = true;
    setLoadingProgress(true);
    myProgress()
      .then((res) => {
        if (!isMounted) return;
        const items = Array.isArray(res) ? res : res?.items || [];
        setProgressItems(items);
        // If learner has 0 enrollments and hasn't chosen a tab explicitly, switch to browse
        if (items.length === 0 && !searchParams.get('tab')) {
          setSearchParams({ tab: 'browse' }, { replace: true });
        }
      })
      .catch(() => {
        if (isMounted) setProgressItems([]);
      })
      .finally(() => {
        if (isMounted) setLoadingProgress(false);
      });

    return () => {
      isMounted = false;
    };
  }, [searchParams, setSearchParams]);

  // Navigate to course on generation success
  useEffect(() => {
    if (courseJob.status === 'succeeded' && courseJob.result?.slug) {
      setGenerateModalOpen(false);
      navigate(`/courses/${courseJob.result.slug}`);
    }
  }, [courseJob.status, courseJob.result, navigate]);

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

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header with unified actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Learn</h1>
          <p className="mt-1 text-sm text-muted">
            All your learning paths in one place: active courses, roadmap quests, and SQL challenges.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/upload">
            <Button variant="secondary" size="sm">
              <UploadCloud className="h-4 w-4" />
              Upload notes
            </Button>
          </Link>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setGenerateModalOpen(true)}
          >
            <Sparkles className="h-4 w-4" />
            Generate a course
          </Button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-1 border-b border-line pb-px overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('my-courses')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'my-courses'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <BookOpen className="h-4 w-4" />
          My Courses
          {progressItems.length > 0 && (
            <Badge tone="default" className="ml-1 text-[10px]">
              {progressItems.length}
            </Badge>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('browse')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'browse'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <Compass className="h-4 w-4" />
          Browse Tracks
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('roadmap')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'roadmap'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <Map className="h-4 w-4" />
          AI Roadmap
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('sql-challenges')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'sql-challenges'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <Code2 className="h-4 w-4" />
          SQL Challenges
        </button>
      </div>

      {/* Tab 1: My Courses */}
      {activeTab === 'my-courses' && (
        <div className="space-y-6">
          {loadingProgress ? (
            <div className="flex min-h-[300px] items-center justify-center">
              <Spinner size="md" label="Loading enrolled courses..." />
            </div>
          ) : progressItems.length === 0 ? (
            <EmptyState
              title="No enrolled tracks yet"
              description="Start learning by browsing the catalog or generating a customized track."
              action={
                <div className="flex gap-3">
                  <Button variant="primary" onClick={() => setActiveTab('browse')}>
                    Browse Tracks
                  </Button>
                  <Button variant="secondary" onClick={() => setGenerateModalOpen(true)}>
                    Generate a Course ✨
                  </Button>
                </div>
              }
            />
          ) : (
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
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
                          <h3 className="mt-1.5 text-base font-bold text-ink">
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
                        <div className="rounded bg-raised p-2.5 text-xs text-body">
                          <span className="font-semibold text-ink">Up next:</span>{' '}
                          {track.next_lesson_title}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between border-t border-line pt-3.5">
                      <Link
                        to={`/courses/${track.course_slug}`}
                        className="text-xs font-semibold text-muted hover:text-ink"
                      >
                        Syllabus & Overview
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
      )}

      {/* Tab 2: Browse Catalog */}
      {activeTab === 'browse' && (
        <CourseCatalog embedded={true} />
      )}

      {/* Tab 3: AI Roadmap */}
      {activeTab === 'roadmap' && (
        <RoadmapPage embedded={true} />
      )}

      {/* Tab 4: SQL Challenges */}
      {activeTab === 'sql-challenges' && (
        <PracticeList embedded={true} />
      )}

      {/* Modal: Generate a Course */}
      {/* `open`, not `isOpen`: Modal ignores unknown props, so with isOpen the
          dialog never rendered and "Generate a course" silently did nothing. */}
      <Modal
        open={generateModalOpen}
        onClose={() => !courseJob.isRunning && setGenerateModalOpen(false)}
        title="Generate a Custom Course"
        size="md"
      >
        <div className="space-y-4 pt-1">
          <p className="text-xs leading-relaxed text-muted">
            Describe any topic or goal you wish to learn. We'll generate an outline, structured lessons, and practice quizzes automatically.
          </p>

          {courseJob.isRunning ? (
            <div className="space-y-3 py-4">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>Planning and writing your lessons - about a minute...</span>
                <span className="font-mono font-semibold text-ink">{courseJob.progress}%</span>
              </div>
              <ProgressBar value={courseJob.progress} tone="default" size="sm" />
            </div>
          ) : (
            <form onSubmit={handleBuildCourseSubmit} className="space-y-3">
              <Input
                id="modal-course-goal-input"
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
                id="modal-course-lessons-select"
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

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setGenerateModalOpen(false)}
                  disabled={courseJob.isRunning}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={courseJob.isRunning}
                  disabled={courseJob.isRunning || !courseGoal.trim() || (quota && quota.remaining <= 0)}
                >
                  {courseJob.isRunning ? 'Building...' : 'Build Course ✨'}
                </Button>
              </div>
            </form>
          )}
        </div>
      </Modal>
    </div>
  );
}
