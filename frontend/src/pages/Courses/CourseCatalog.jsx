/**
 * CourseCatalog - OWNER: Member 2. See plan.md §7.2.
 *
 * Course catalog page consuming backend course data with search,
 * subject/difficulty filtering, pagination, enrollment indicators,
 * loading state, error state, and empty state.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listCourses, myEnrollments } from '../../api/courses';
import { useAuth } from '../../context/AuthContext';
import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Select,
  Spinner,
} from '../../components/ui';

const SUBJECT_OPTIONS = [
  { value: '', label: 'All Subjects' },
  { value: 'Database Systems', label: 'Database Systems' },
  { value: 'Computer Science', label: 'Computer Science' },
  { value: 'Programming', label: 'Programming' },
  { value: 'Web Development', label: 'Web Development' },
];

const DIFFICULTY_OPTIONS = [
  { value: '', label: 'All Difficulties' },
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
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

export default function CourseCatalog() {
  const { user, isAuthenticated } = useAuth();
  const [courses, setCourses] = useState([]);
  const [enrolledCourseIds, setEnrolledCourseIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [subject, setSubject] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(9);
  const [total, setTotal] = useState(0);

  // Fetch enrollments strictly for the current authenticated user
  useEffect(() => {
    let isMounted = true;
    if (!isAuthenticated || !user) {
      setEnrolledCourseIds(new Set());
      return;
    }

    myEnrollments()
      .then((res) => {
        if (!isMounted) return;
        const items = Array.isArray(res) ? res : res?.items || [];
        const ids = new Set(
          items.map((enr) => enr.course_id || enr.course?.id).filter(Boolean)
        );
        setEnrolledCourseIds(ids);
      })
      .catch(() => {
        setEnrolledCourseIds(new Set());
      });
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, user?.id]);

  // Fetch courses whenever filters or page changes
  const fetchCourses = useCallback(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    const params = {
      page,
      page_size: pageSize,
    };
    if (search.trim()) params.search = search.trim();
    if (subject) params.subject = subject;
    if (difficulty) params.difficulty = difficulty;

    listCourses(params)
      .then((data) => {
        if (!isMounted) return;
        const items = Array.isArray(data) ? data : data?.items || [];
        setCourses(items);
        setTotal(data?.total ?? items.length);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.warn('Failed to load courses from API:', err);
        setError(err?.detail || 'Unable to connect to course service. Please try again.');
        setCourses([]);
        setTotal(0);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [search, subject, difficulty, page, pageSize]);

  useEffect(() => {
    const cancel = fetchCourses();
    return cancel;
  }, [fetchCourses]);

  // Reset page when filters change
  const handleSearchChange = (e) => {
    setSearch(e.target.value);
    setPage(1);
  };

  const handleSubjectChange = (e) => {
    setSubject(e.target.value);
    setPage(1);
  };

  const handleDifficultyChange = (e) => {
    setDifficulty(e.target.value);
    setPage(1);
  };

  const resetFilters = () => {
    setSearch('');
    setSubject('');
    setDifficulty('');
    setPage(1);
  };

  const hasActiveFilters = Boolean(search || subject || difficulty);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <PageHeader
        title="Explore Courses"
        subtitle="Browse available courses, filter by topic or difficulty, and start learning with AI support."
      />

      {/* Filter and Search Bar */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <Input
            id="course-search"
            type="search"
            placeholder="Search courses by title, topic, or description..."
            value={search}
            onChange={handleSearchChange}
          />
        </div>
        <div>
          <Select
            id="subject-filter"
            value={subject}
            onChange={handleSubjectChange}
            options={SUBJECT_OPTIONS}
          />
        </div>
        <div>
          <Select
            id="difficulty-filter"
            value={difficulty}
            onChange={handleDifficultyChange}
            options={DIFFICULTY_OPTIONS}
          />
        </div>
      </div>

      {/* API Error State */}
      {error && (
        <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold">Error Loading Courses</p>
              <p className="mt-0.5">{error}</p>
            </div>
            <Button variant="danger" size="sm" onClick={fetchCourses}>
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Content Area */}
      {loading ? (
        <div className="flex min-h-[280px] items-center justify-center">
          <Spinner size="lg" label="Loading courses" />
        </div>
      ) : courses.length === 0 ? (
        <EmptyState
          title={hasActiveFilters ? 'No matching courses found' : 'No courses available'}
          description={
            hasActiveFilters
              ? 'Try adjusting your search query or filters to find what you are looking for.'
              : 'There are no published courses at this time. Check back later!'
          }
          action={
            hasActiveFilters && (
              <Button variant="secondary" size="sm" onClick={resetFilters}>
                Clear filters
              </Button>
            )
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {courses.map((course) => {
              const isEnrolled = enrolledCourseIds.has(course.id);
              const lessonCount =
                course.lesson_count ?? course.lessons_count ?? course.lessons?.length;

              return (
                <Card
                  key={course.id || course.slug}
                  className="flex flex-col justify-between transition-shadow hover:shadow-md"
                >
                  <div>
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <Badge tone="default">{course.subject || 'General'}</Badge>
                        <Badge tone={getDifficultyTone(course.difficulty)}>
                          {course.difficulty || 'beginner'}
                        </Badge>
                      </div>
                      {isEnrolled && <Badge tone="easy">Enrolled</Badge>}
                    </div>
                    <Link to={`/courses/${course.slug || course.id}`}>
                      <h2 className="text-lg font-semibold text-slate-900 transition-colors hover:text-primary-600 dark:text-slate-100 dark:hover:text-primary-400">
                        {course.title}
                      </h2>
                    </Link>
                    <p className="mt-2 line-clamp-3 text-sm text-slate-600 dark:text-slate-400">
                      {course.description || 'No description provided.'}
                    </p>
                  </div>

                  <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
                    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <span>
                        {course.estimated_hours ? `${course.estimated_hours} hrs` : 'Self-paced'}
                      </span>
                      {lessonCount !== undefined && (
                        <>
                          <span>•</span>
                          <span>{lessonCount} lessons</span>
                        </>
                      )}
                    </div>
                    <Link to={`/courses/${course.slug || course.id}`}>
                      <Button variant={isEnrolled ? 'secondary' : 'primary'} size="sm">
                        {isEnrolled ? 'Continue' : 'View Course'}
                      </Button>
                    </Link>
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-between border-t border-slate-200 pt-4 dark:border-slate-800">
              <p className="text-sm text-slate-500">
                Showing page <span className="font-medium text-slate-800 dark:text-slate-200">{page}</span> of{' '}
                <span className="font-medium text-slate-800 dark:text-slate-200">{totalPages}</span> ({total} total courses)
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
