/**
 * Admin Courses - OWNER: Member 3. See plan.md §8.3, §8.4 & CHECKLIST.md Slot 7.
 *
 * Course and Lesson CRUD with publish toggling, markdown editor with live preview,
 * lesson ordering, and strict topic_tags validation.
 */
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import {
  BookOpen,
  Plus,
  Search,
  CheckCircle2,
  XCircle,
  Edit2,
  Trash2,
  ArrowLeft,
  Eye,
  FileText,
  Tag,
  Clock,
  ArrowUp,
  ArrowDown,
  Layers,
  AlertCircle,
  Save,
  Check,
} from 'lucide-react';

import {
  listCourses,
  getCourse,
  createCourse,
  updateCourse,
  deleteCourse,
  createLesson,
  updateLesson,
  deleteLesson,
} from '../../api/admin';
import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  Input,
  Modal,
  Select,
  Spinner,
} from '../../components/ui';

const TOPIC_VOCABULARY = [
  'dbms.er_model',
  'dbms.normalization',
  'dbms.sql_joins',
  'dbms.transactions',
  'web.rest_api',
  'web.auth',
  'web.react',
  'lang.python.basics',
  'lang.python.oop',
  'lang.python.data_structures',
  'algo.sorting',
  'algo.trees',
  'algo.graphs',
];

function slugify(text) {
  return String(text || '')
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export default function AdminCourses() {
  const [courses, setCourses] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Filters
  const [search, setSearch] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Active view: 'list' or 'edit'
  const [activeCourseId, setActiveCourseId] = useState(null);
  const [activeCourse, setActiveCourse] = useState(null);
  const [courseLoading, setCourseLoading] = useState(false);

  // Course Form Modal (Create or Edit Metadata)
  const [courseModalOpen, setCourseModalOpen] = useState(false);
  const [courseForm, setCourseForm] = useState({
    title: '',
    slug: '',
    description: '',
    subject: 'Database Systems',
    difficulty: 'intermediate',
    estimated_hours: 6,
    is_published: true,
  });

  // Lesson Form Modal (Create or Edit Lesson)
  const [lessonModalOpen, setLessonModalOpen] = useState(false);
  const [editingLessonId, setEditingLessonId] = useState(null);
  const [lessonForm, setLessonForm] = useState({
    title: '',
    order_index: 1,
    estimated_minutes: 15,
    video_url: '',
    topic_tags: [],
    content_md: '',
  });
  const [tagInput, setTagInput] = useState('');
  const [activeLessonTab, setActiveLessonTab] = useState('write'); // 'write' or 'preview'
  const [lessonError, setLessonError] = useState(null);

  const fetchCourses = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (subjectFilter) params.subject = subjectFilter;
      if (statusFilter === 'published') params.is_published = true;
      if (statusFilter === 'draft') params.is_published = false;

      const res = await listCourses(params);
      const data = res?.data || res;
      setCourses(data?.items || (Array.isArray(data) ? data : []));
      setTotal(data?.total || (Array.isArray(data) ? data.length : 0));
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load courses.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCourses();
  }, [search, subjectFilter, statusFilter]);

  const loadCourseDetail = async (id) => {
    setCourseLoading(true);
    setError(null);
    try {
      const res = await getCourse(id);
      const data = res?.data || res;
      setActiveCourse(data);
      setActiveCourseId(id);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load course details.');
    } finally {
      setCourseLoading(false);
    }
  };

  const handleOpenCreateCourse = () => {
    setCourseForm({
      title: '',
      slug: '',
      description: '',
      subject: 'Database Systems',
      difficulty: 'intermediate',
      estimated_hours: 6,
      is_published: true,
    });
    setCourseModalOpen(true);
  };

  const handleSaveCourse = async (e) => {
    e.preventDefault();
    if (!courseForm.title.trim()) return;

    setActionLoading(true);
    setError(null);
    try {
      const payload = {
        ...courseForm,
        slug: courseForm.slug.trim() || slugify(courseForm.title),
        estimated_hours: Number(courseForm.estimated_hours) || 1,
      };

      if (activeCourseId) {
        const res = await updateCourse(activeCourseId, payload);
        const updated = res?.data || res;
        setActiveCourse((prev) => ({ ...prev, ...updated }));
        setSuccessMessage('Course updated successfully.');
      } else {
        const res = await createCourse(payload);
        const created = res?.data || res;
        setSuccessMessage('Course created successfully.');
        setCourseModalOpen(false);
        if (created?.id) {
          await loadCourseDetail(created.id);
        }
      }
      setCourseModalOpen(false);
      fetchCourses();
    } catch (err) {
      const errorMsg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Failed to save course.';
      setError(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
    } finally {
      setActionLoading(false);
    }
  };

  const handleTogglePublish = async (course) => {
    setActionLoading(true);
    try {
      const nextState = !course.is_published;
      await updateCourse(course.id, { is_published: nextState });
      setCourses((prev) =>
        prev.map((c) => (c.id === course.id ? { ...c, is_published: nextState } : c))
      );
      if (activeCourse?.id === course.id) {
        setActiveCourse((prev) => ({ ...prev, is_published: nextState }));
      }
      setSuccessMessage(`Course ${nextState ? 'published' : 'moved to drafts'}.`);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update publish state.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteCourse = async (course) => {
    if (!window.confirm(`Are you sure you want to delete "${course.title}"? This cannot be undone.`)) {
      return;
    }
    setActionLoading(true);
    try {
      await deleteCourse(course.id);
      setSuccessMessage(`Course "${course.title}" deleted.`);
      if (activeCourseId === course.id) {
        setActiveCourseId(null);
        setActiveCourse(null);
      }
      fetchCourses();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to delete course.');
    } finally {
      setActionLoading(false);
    }
  };

  // --- Lesson Management ---

  const handleOpenCreateLesson = () => {
    const nextOrder = (activeCourse?.lessons?.length || 0) + 1;
    setEditingLessonId(null);
    setLessonForm({
      title: '',
      order_index: nextOrder,
      estimated_minutes: 15,
      video_url: '',
      topic_tags: [],
      content_md: '# Overview\n\nExplain the primary concepts clearly...',
    });
    setLessonError(null);
    setActiveLessonTab('write');
    setLessonModalOpen(true);
  };

  const handleOpenEditLesson = (lesson) => {
    setEditingLessonId(lesson.id);
    setLessonForm({
      title: lesson.title,
      order_index: lesson.order_index,
      estimated_minutes: lesson.estimated_minutes,
      video_url: lesson.video_url || '',
      topic_tags: lesson.topic_tags || [],
      content_md: lesson.content_md || '',
    });
    setLessonError(null);
    setActiveLessonTab('write');
    setLessonModalOpen(true);
  };

  const handleAddTag = (tagToAdd) => {
    const cleanTag = (tagToAdd || tagInput).trim().toLowerCase();
    if (!cleanTag) return;
    if (!lessonForm.topic_tags.includes(cleanTag)) {
      setLessonForm((prev) => ({
        ...prev,
        topic_tags: [...prev.topic_tags, cleanTag],
      }));
    }
    setTagInput('');
    setLessonError(null);
  };

  const handleRemoveTag = (tagToRemove) => {
    setLessonForm((prev) => ({
      ...prev,
      topic_tags: prev.topic_tags.filter((t) => t !== tagToRemove),
    }));
  };

  const handleSaveLesson = async (e) => {
    e.preventDefault();
    if (!lessonForm.title.trim()) {
      setLessonError('Lesson title is required.');
      return;
    }

    // STRICT VALIDATION RULE: plan.md §3.1 & §8.3
    if (!lessonForm.topic_tags || lessonForm.topic_tags.length === 0) {
      setLessonError('Validation error: A lesson MUST have at least one topic_tag (plan.md §3.1).');
      return;
    }

    if (!lessonForm.content_md.trim()) {
      setLessonError('Lesson markdown content cannot be empty.');
      return;
    }

    setActionLoading(true);
    setLessonError(null);
    try {
      const payload = {
        title: lessonForm.title.trim(),
        order_index: Number(lessonForm.order_index) || 1,
        estimated_minutes: Number(lessonForm.estimated_minutes) || 10,
        video_url: lessonForm.video_url.trim() || null,
        topic_tags: lessonForm.topic_tags,
        content_md: lessonForm.content_md,
      };

      if (editingLessonId) {
        await updateLesson(editingLessonId, payload);
        setSuccessMessage('Lesson updated successfully.');
      } else {
        await createLesson(activeCourseId, payload);
        setSuccessMessage('Lesson added successfully.');
      }

      setLessonModalOpen(false);
      await loadCourseDetail(activeCourseId);
      fetchCourses();
    } catch (err) {
      setLessonError(
        err?.response?.data?.detail || err.message || 'Failed to save lesson.'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteLesson = async (lessonId, title) => {
    if (!window.confirm(`Delete lesson "${title}"?`)) return;
    setActionLoading(true);
    try {
      await deleteLesson(lessonId);
      setSuccessMessage(`Lesson "${title}" deleted.`);
      await loadCourseDetail(activeCourseId);
      fetchCourses();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to delete lesson.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleMoveLessonOrder = async (lesson, direction) => {
    const lessons = [...(activeCourse?.lessons || [])];
    const currentIndex = lessons.findIndex((l) => l.id === lesson.id);
    const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;

    if (targetIndex < 0 || targetIndex >= lessons.length) return;

    const targetLesson = lessons[targetIndex];
    const currentOrder = lesson.order_index;
    const targetOrder = targetLesson.order_index;

    setActionLoading(true);
    try {
      await Promise.all([
        updateLesson(lesson.id, { order_index: targetOrder }),
        updateLesson(targetLesson.id, { order_index: currentOrder }),
      ]);
      await loadCourseDetail(activeCourseId);
    } catch (err) {
      setError('Failed to reorder lessons.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast banner for messages */}
      {successMessage && (
        <div className="flex items-center justify-between rounded border border-easy/30 bg-easy-bg p-3 text-xs text-easy-fg animate-fade-in">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="text-xs hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-between rounded border border-hard/30 bg-hard-bg p-3 text-xs text-hard-fg animate-fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-xs hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* =========================================================
          VIEW 1: Course Catalog Table (List View)
         ========================================================= */}
      {!activeCourseId && (
        <>
          <PageHeader
            title="Course management"
            subtitle="Create, edit, tag, and publish courses and lessons across the curriculum."
            action={
              <Button variant="primary" size="sm" onClick={handleOpenCreateCourse}>
                <Plus className="h-3.5 w-3.5" />
                New course
              </Button>
            }
          />

          {/* Filter Bar */}
          <Card className="p-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative min-w-[220px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
                <input
                  type="text"
                  placeholder="Search courses by title or description..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="field pl-8 text-xs"
                />
              </div>

              <div className="w-40">
                <select
                  value={subjectFilter}
                  onChange={(e) => setSubjectFilter(e.target.value)}
                  className="field text-xs"
                >
                  <option value="">All Subjects</option>
                  <option value="Database Systems">Database Systems</option>
                  <option value="Programming">Programming</option>
                  <option value="Web Development">Web Development</option>
                  <option value="Algorithms">Algorithms</option>
                </select>
              </div>

              <div className="w-36">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="field text-xs"
                >
                  <option value="all">All Statuses</option>
                  <option value="published">Published Only</option>
                  <option value="draft">Drafts Only</option>
                </select>
              </div>
            </div>
          </Card>

          {/* Courses Table */}
          <Card className="p-0">
            <div className="overflow-x-auto">
              <table className="table-dense w-full">
                <thead>
                  <tr>
                    <th>Course Title & Subject</th>
                    <th>Slug</th>
                    <th>Difficulty</th>
                    <th>Est. Hours</th>
                    <th>Lessons</th>
                    <th>Status</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-muted">
                        <Spinner size="md" className="mx-auto" />
                        <p className="mt-2 text-xs">Loading course catalog...</p>
                      </td>
                    </tr>
                  ) : courses.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-muted">
                        No courses match your filter criteria.
                      </td>
                    </tr>
                  ) : (
                    courses.map((c) => (
                      <tr key={c.id}>
                        <td className="max-w-xs">
                          <button
                            type="button"
                            onClick={() => loadCourseDetail(c.id)}
                            className="text-left font-semibold text-ink hover:text-primary-600"
                          >
                            {c.title}
                          </button>
                          <div className="text-2xs text-muted">{c.subject}</div>
                        </td>
                        <td>
                          <code className="text-2xs text-muted">{c.slug}</code>
                        </td>
                        <td>
                          <Badge
                            tone={
                              c.difficulty === 'beginner'
                                ? 'easy'
                                : c.difficulty === 'intermediate'
                                ? 'medium'
                                : 'hard'
                            }
                          >
                            {c.difficulty}
                          </Badge>
                        </td>
                        <td className="text-muted">{c.estimated_hours} hrs</td>
                        <td>
                          <span className="font-medium text-ink">
                            {c.lessons_count ?? 0}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            onClick={() => handleTogglePublish(c)}
                            disabled={actionLoading}
                            title={c.is_published ? 'Click to unpublish' : 'Click to publish'}
                            className="cursor-pointer"
                          >
                            <Badge tone={c.is_published ? 'easy' : 'neutral'}>
                              {c.is_published ? 'Published' : 'Draft'}
                            </Badge>
                          </button>
                        </td>
                        <td className="text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => loadCourseDetail(c.id)}
                              title="Edit course and manage lessons"
                            >
                              <Edit2 className="h-3 w-3" />
                              Manage
                            </Button>
                            <Link to={`/courses/${c.slug}`} target="_blank">
                              <Button variant="ghost" size="sm" title="Preview student view">
                                <Eye className="h-3 w-3" />
                              </Button>
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteCourse(c)}
                              title="Delete course"
                              className="text-hard hover:bg-hard-bg"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {/* =========================================================
          VIEW 2: Course & Lesson Editor (Single Course View)
         ========================================================= */}
      {activeCourseId && (
        <div className="space-y-6">
          <div className="flex items-center justify-between border-b border-line pb-4">
            <button
              type="button"
              onClick={() => {
                setActiveCourseId(null);
                setActiveCourse(null);
                fetchCourses();
              }}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to all courses
            </button>

            <div className="flex items-center gap-2">
              <Link to={`/courses/${activeCourse?.slug}`} target="_blank">
                <Button variant="secondary" size="sm">
                  <Eye className="h-3.5 w-3.5" />
                  Student view
                </Button>
              </Link>
              <Button
                variant={activeCourse?.is_published ? 'secondary' : 'primary'}
                size="sm"
                onClick={() => activeCourse && handleTogglePublish(activeCourse)}
                disabled={actionLoading}
              >
                {activeCourse?.is_published ? (
                  <>
                    <XCircle className="h-3.5 w-3.5" />
                    Unpublish
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Publish Course
                  </>
                )}
              </Button>
            </div>
          </div>

          {courseLoading ? (
            <div className="py-12 text-center">
              <Spinner size="lg" className="mx-auto" />
              <p className="mt-2 text-sm text-muted">Loading course details...</p>
            </div>
          ) : !activeCourse ? (
            <div className="py-8 text-center text-hard">Course not found.</div>
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Left Column: Course Details Card */}
              <div className="space-y-4 lg:col-span-1">
                <Card className="p-4">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <h2 className="text-sm font-semibold text-ink">
                      Course Metadata
                    </h2>
                    <Badge tone={activeCourse.is_published ? 'easy' : 'neutral'}>
                      {activeCourse.is_published ? 'Published' : 'Draft'}
                    </Badge>
                  </div>

                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleSaveCourse(e);
                    }}
                    className="mt-4 space-y-3"
                  >
                    <div>
                      <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                        Title
                      </label>
                      <input
                        type="text"
                        value={activeCourse.title}
                        onChange={(e) =>
                          setActiveCourse((prev) => ({ ...prev, title: e.target.value }))
                        }
                        className="field text-xs"
                        required
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                        Slug
                      </label>
                      <input
                        type="text"
                        value={activeCourse.slug}
                        onChange={(e) =>
                          setActiveCourse((prev) => ({ ...prev, slug: e.target.value }))
                        }
                        className="field text-xs font-mono"
                        required
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                          Subject
                        </label>
                        <select
                          value={activeCourse.subject}
                          onChange={(e) =>
                            setActiveCourse((prev) => ({ ...prev, subject: e.target.value }))
                          }
                          className="field text-xs"
                        >
                          <option value="Database Systems">Database Systems</option>
                          <option value="Programming">Programming</option>
                          <option value="Web Development">Web Development</option>
                          <option value="Algorithms">Algorithms</option>
                        </select>
                      </div>

                      <div>
                        <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                          Difficulty
                        </label>
                        <select
                          value={activeCourse.difficulty}
                          onChange={(e) =>
                            setActiveCourse((prev) => ({ ...prev, difficulty: e.target.value }))
                          }
                          className="field text-xs"
                        >
                          <option value="beginner">Beginner</option>
                          <option value="intermediate">Intermediate</option>
                          <option value="advanced">Advanced</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                        Est. Hours
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="200"
                        value={activeCourse.estimated_hours}
                        onChange={(e) =>
                          setActiveCourse((prev) => ({
                            ...prev,
                            estimated_hours: Number(e.target.value),
                          }))
                        }
                        className="field text-xs"
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                        Description
                      </label>
                      <textarea
                        rows={3}
                        value={activeCourse.description || ''}
                        onChange={(e) =>
                          setActiveCourse((prev) => ({
                            ...prev,
                            description: e.target.value,
                          }))
                        }
                        className="field text-xs"
                      />
                    </div>

                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      loading={actionLoading}
                      onClick={async () => {
                        setActionLoading(true);
                        try {
                          await updateCourse(activeCourse.id, {
                            title: activeCourse.title,
                            slug: activeCourse.slug,
                            subject: activeCourse.subject,
                            difficulty: activeCourse.difficulty,
                            estimated_hours: activeCourse.estimated_hours,
                            description: activeCourse.description,
                          });
                          setSuccessMessage('Course details saved.');
                        } catch (err) {
                          setError('Failed to save changes.');
                        } finally {
                          setActionLoading(false);
                        }
                      }}
                      className="w-full justify-center"
                    >
                      <Save className="h-3.5 w-3.5" />
                      Save course details
                    </Button>
                  </form>
                </Card>
              </div>

              {/* Right Column: Lessons List & Manager */}
              <div className="space-y-4 lg:col-span-2">
                <Card className="p-4">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <div>
                      <h2 className="text-sm font-semibold text-ink">
                        Curriculum Lessons ({activeCourse.lessons?.length || 0})
                      </h2>
                      <p className="text-2xs text-muted">
                        Lessons must include topic_tags for AI recommendation and misconception tracking.
                      </p>
                    </div>
                    <Button variant="primary" size="sm" onClick={handleOpenCreateLesson}>
                      <Plus className="h-3.5 w-3.5" />
                      Add lesson
                    </Button>
                  </div>

                  {activeCourse.lessons?.length === 0 ? (
                    <div className="py-8 text-center">
                      <FileText className="mx-auto h-8 w-8 text-faint" />
                      <p className="mt-2 text-sm font-medium text-ink">
                        No lessons added yet
                      </p>
                      <p className="text-xs text-muted">
                        Add the first lesson to start building this course's syllabus.
                      </p>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="mt-3"
                        onClick={handleOpenCreateLesson}
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Create first lesson
                      </Button>
                    </div>
                  ) : (
                    <div className="mt-4 space-y-2">
                      {activeCourse.lessons?.map((lesson, idx) => (
                        <div
                          key={lesson.id}
                          className="flex items-center justify-between rounded border border-line bg-surface p-3 transition-colors hover:border-line-strong"
                        >
                          <div className="flex items-start gap-3 min-w-0 flex-1 pr-3">
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-canvas text-2xs font-bold text-muted">
                              {lesson.order_index}
                            </span>
                            <div className="min-w-0 flex-1">
                              <h3 className="truncate text-xs font-semibold text-ink">
                                {lesson.title}
                              </h3>
                              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                                <span className="inline-flex items-center gap-1 text-2xs text-muted">
                                  <Clock className="h-3 w-3" />
                                  {lesson.estimated_minutes}m
                                </span>
                                {lesson.topic_tags?.map((tag) => (
                                  <Badge key={tag} tone="primary">
                                    {tag}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          </div>

                          <div className="flex shrink-0 items-center gap-1">
                            {/* Reorder Up/Down */}
                            <button
                              type="button"
                              disabled={idx === 0 || actionLoading}
                              onClick={() => handleMoveLessonOrder(lesson, 'up')}
                              className="rounded p-1 text-muted hover:bg-canvas hover:text-ink disabled:opacity-30"
                              title="Move up"
                            >
                              <ArrowUp className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              disabled={idx === activeCourse.lessons.length - 1 || actionLoading}
                              onClick={() => handleMoveLessonOrder(lesson, 'down')}
                              className="rounded p-1 text-muted hover:bg-canvas hover:text-ink disabled:opacity-30"
                              title="Move down"
                            >
                              <ArrowDown className="h-3.5 w-3.5" />
                            </button>

                            {/* Edit & Delete */}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenEditLesson(lesson)}
                              title="Edit lesson and markdown"
                            >
                              <Edit2 className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteLesson(lesson.id, lesson.title)}
                              className="text-hard hover:bg-hard-bg"
                              title="Delete lesson"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =========================================================
          MODAL 1: Create / Edit Course Modal
         ========================================================= */}
      <Modal
        open={courseModalOpen}
        onClose={() => setCourseModalOpen(false)}
        title="Create New Course"
        size="md"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCourseModalOpen(false)}
              disabled={actionLoading}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveCourse}
              loading={actionLoading}
            >
              Save Course
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSaveCourse} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium">Course Title</label>
            <input
              type="text"
              placeholder="e.g. Distributed Systems Architecture"
              value={courseForm.title}
              onChange={(e) => {
                const title = e.target.value;
                setCourseForm((prev) => ({
                  ...prev,
                  title,
                  slug: prev.slug ? prev.slug : slugify(title),
                }));
              }}
              className="field text-xs"
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium">URL Slug</label>
            <input
              type="text"
              placeholder="distributed-systems-architecture"
              value={courseForm.slug}
              onChange={(e) =>
                setCourseForm((prev) => ({ ...prev, slug: slugify(e.target.value) }))
              }
              className="field text-xs font-mono"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-xs font-medium">Subject</label>
              <select
                value={courseForm.subject}
                onChange={(e) =>
                  setCourseForm((prev) => ({ ...prev, subject: e.target.value }))
                }
                className="field text-xs"
              >
                <option value="Database Systems">Database Systems</option>
                <option value="Programming">Programming</option>
                <option value="Web Development">Web Development</option>
                <option value="Algorithms">Algorithms</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium">Difficulty</label>
              <select
                value={courseForm.difficulty}
                onChange={(e) =>
                  setCourseForm((prev) => ({ ...prev, difficulty: e.target.value }))
                }
                className="field text-xs"
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium">Estimated Hours</label>
            <input
              type="number"
              min="1"
              max="100"
              value={courseForm.estimated_hours}
              onChange={(e) =>
                setCourseForm((prev) => ({
                  ...prev,
                  estimated_hours: Number(e.target.value),
                }))
              }
              className="field text-xs"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium">Description</label>
            <textarea
              rows={3}
              placeholder="Summary of skills and practical knowledge taught..."
              value={courseForm.description}
              onChange={(e) =>
                setCourseForm((prev) => ({ ...prev, description: e.target.value }))
              }
              className="field text-xs"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer pt-1">
            <input
              type="checkbox"
              checked={courseForm.is_published}
              onChange={(e) =>
                setCourseForm((prev) => ({ ...prev, is_published: e.target.checked }))
              }
              className="rounded border-line text-primary-600 focus:ring-primary-600/20"
            />
            <span className="text-xs font-medium text-ink">
              Publish immediately to student catalog
            </span>
          </label>
        </form>
      </Modal>

      {/* =========================================================
          MODAL 2: Lesson Editor with Markdown & Tag Validation
         ========================================================= */}
      <Modal
        open={lessonModalOpen}
        onClose={() => setLessonModalOpen(false)}
        title={editingLessonId ? 'Edit Lesson & Markdown' : 'Add Lesson to Course'}
        size="xl"
        footer={
          <div className="flex items-center justify-between w-full">
            <div className="text-2xs text-muted">
              {lessonForm.topic_tags.length === 0 ? (
                <span className="text-hard font-medium">
                  At least one topic_tag is required.
                </span>
              ) : (
                <span>{lessonForm.topic_tags.length} tag(s) selected</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setLessonModalOpen(false)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveLesson}
                loading={actionLoading}
                disabled={lessonForm.topic_tags.length === 0 || !lessonForm.title.trim()}
              >
                Save Lesson
              </Button>
            </div>
          </div>
        }
      >
        <div className="space-y-4">
          {lessonError && (
            <div className="rounded border border-hard/30 bg-hard-bg p-2.5 text-xs text-hard-fg">
              {lessonError}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="sm:col-span-2">
              <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                Lesson Title
              </label>
              <input
                type="text"
                placeholder="e.g. SQL Subqueries and CTEs"
                value={lessonForm.title}
                onChange={(e) =>
                  setLessonForm((prev) => ({ ...prev, title: e.target.value }))
                }
                className="field text-xs"
                required
              />
            </div>

            <div>
              <label className="mb-1 block text-2xs font-semibold uppercase text-muted">
                Est. Minutes
              </label>
              <input
                type="number"
                min="1"
                max="180"
                value={lessonForm.estimated_minutes}
                onChange={(e) =>
                  setLessonForm((prev) => ({
                    ...prev,
                    estimated_minutes: Number(e.target.value),
                  }))
                }
                className="field text-xs"
              />
            </div>
          </div>

          {/* Topic Tags Picker — REQUIRED by plan.md §3.1 & §8.3 */}
          <div className="rounded border border-line bg-canvas/60 p-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-ink flex items-center gap-1.5">
                <Tag className="h-3.5 w-3.5 text-primary-600" />
                Topic Tags (Required for Misconceptions & AI Recs)
              </label>
              <span className="text-2xs text-muted">Press Enter to add tag</span>
            </div>

            {/* Selected Tags Chips */}
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {lessonForm.topic_tags.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 rounded bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700"
                >
                  {t}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(t)}
                    className="hover:text-hard"
                  >
                    &times;
                  </button>
                </span>
              ))}
              {lessonForm.topic_tags.length === 0 && (
                <span className="text-2xs text-hard">
                  No tags selected. Please select or type at least one tag.
                </span>
              )}
            </div>

            {/* Tag Input & Suggestions */}
            <div className="mt-2.5 flex items-center gap-2">
              <input
                type="text"
                placeholder="Type tag and press Enter (e.g. dbms.sql_joins)"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddTag(tagInput);
                  }
                }}
                className="field text-xs"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => handleAddTag(tagInput)}
                disabled={!tagInput.trim()}
              >
                Add
              </Button>
            </div>

            {/* Quick Vocabulary Tags */}
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <span className="text-2xs text-muted">Suggestions:</span>
              {TOPIC_VOCABULARY.slice(0, 7).map((sug) => (
                <button
                  key={sug}
                  type="button"
                  onClick={() => handleAddTag(sug)}
                  disabled={lessonForm.topic_tags.includes(sug)}
                  className="rounded border border-line bg-surface px-1.5 py-0.5 text-2xs text-muted hover:border-line-strong hover:text-ink disabled:opacity-40"
                >
                  +{sug}
                </button>
              ))}
            </div>
          </div>

          {/* Markdown Content with Write / Preview Tabs */}
          <div>
            <div className="flex items-center justify-between border-b border-line pb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveLessonTab('write')}
                  className={`px-3 py-1 text-xs font-semibold rounded ${
                    activeLessonTab === 'write'
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  Write Markdown
                </button>
                <button
                  type="button"
                  onClick={() => setActiveLessonTab('preview')}
                  className={`px-3 py-1 text-xs font-semibold rounded ${
                    activeLessonTab === 'preview'
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  Live Preview
                </button>
              </div>

              {activeLessonTab === 'write' && (
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() =>
                      setLessonForm((prev) => ({
                        ...prev,
                        content_md: prev.content_md + '\n\n## Section Title\n',
                      }))
                    }
                    className="rounded px-1.5 py-0.5 text-2xs text-muted hover:bg-canvas"
                  >
                    +H2
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setLessonForm((prev) => ({
                        ...prev,
                        content_md:
                          prev.content_md + '\n\n```sql\nSELECT * FROM table;\n```\n',
                      }))
                    }
                    className="rounded px-1.5 py-0.5 text-2xs text-muted hover:bg-canvas"
                  >
                    +SQL
                  </button>
                </div>
              )}
            </div>

            <div className="mt-2">
              {activeLessonTab === 'write' ? (
                <textarea
                  rows={14}
                  value={lessonForm.content_md}
                  onChange={(e) =>
                    setLessonForm((prev) => ({ ...prev, content_md: e.target.value }))
                  }
                  placeholder="# Lesson Overview&#10;&#10;Explain the concepts here in Markdown..."
                  className="field font-mono text-xs leading-relaxed"
                  required
                />
              ) : (
                <div className="max-h-[380px] min-h-[250px] overflow-y-auto rounded border border-line bg-canvas p-4 text-xs leading-relaxed">
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {lessonForm.content_md}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
