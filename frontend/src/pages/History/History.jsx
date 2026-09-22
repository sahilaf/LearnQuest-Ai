/**
 * History - OWNER: Member 2. See plan.md §7.2, §7.4.
 *
 * Persisted learning history timeline showing:
 * - Completed lessons, quizzes, quiz scores, and durations
 * - Filtering by activity type (All, Lessons, Quizzes)
 * - Pagination across history items
 * - Quick review navigation
 * - Empty, loading, and error states
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { myHistory } from '../../api/courses';
import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Spinner,
  Tabs,
} from '../../components/ui';

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs}s`;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function formatTimestamp(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

const FILTER_TABS = [
  { id: 'all', label: 'All Activities' },
  { id: 'lesson', label: 'Lessons' },
  { id: 'quiz', label: 'Quizzes' },
];

export default function History() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [activeFilter, setActiveFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchHistory = useCallback(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    const params = {
      page,
      page_size: pageSize,
    };
    if (activeFilter !== 'all') {
      params.item_type = activeFilter;
    }

    myHistory(params)
      .then((data) => {
        if (!isMounted) return;
        const resItems = Array.isArray(data) ? data : data?.items || [];
        setItems(resItems);
        setTotal(data?.total ?? resItems.length);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.warn('Failed to load history:', err);
        setError(err?.detail || 'Unable to load learning history. Please try again.');
        setItems([]);
        setTotal(0);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [page, pageSize, activeFilter]);

  useEffect(() => {
    const cancel = fetchHistory();
    return cancel;
  }, [fetchHistory]);

  const handleTabChange = (newTab) => {
    setActiveFilter(newTab);
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <PageHeader
        title="Learning History"
        subtitle="Chronological record of every lesson completed and quiz attempted."
      />

      {/* Filter Tabs & Total Count */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={FILTER_TABS}
          activeTab={activeFilter}
          onChange={handleTabChange}
          variant="pills"
        />

        <span className="text-xs font-medium text-muted">
          Showing {items.length} of {total} {total === 1 ? 'record' : 'records'}
        </span>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="flex min-h-[300px] items-center justify-center">
          <Spinner size="lg" label="Loading learning history..." />
        </div>
      ) : error ? (
        <Card className="border-hard/30 bg-hard-bg/50 p-6 text-center">
          <p className="text-sm font-medium text-hard-fg">{error}</p>
          <Button variant="primary" size="sm" onClick={fetchHistory} className="mt-4">
            Retry
          </Button>
        </Card>
      ) : items.length === 0 ? (
        <EmptyState
          title="No history recorded"
          description={
            activeFilter === 'all'
              ? 'Start working on a course or take a practice quiz to generate learning history.'
              : `No ${activeFilter} activities found in your timeline.`
          }
          action={
            <Link to="/courses">
              <Button variant="primary" size="sm">
                Browse Courses
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          {/* Dense Table View */}
          <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-line bg-raised/70 font-semibold text-body">
                  <tr>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Title & Track</th>
                    <th className="px-4 py-3">Outcome</th>
                    <th className="px-4 py-3">Time Spent</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((item) => {
                    const isLesson = item.item_type === 'lesson';
                    const isQuiz = item.item_type === 'quiz';

                    return (
                      <tr
                        key={`${item.item_type}-${item.id}`}
                        className="transition-colors hover:bg-raised/60"
                      >
                        {/* Type Column */}
                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 font-medium ${
                              isLesson
                                ? 'bg-info-bg text-info-fg'
                                : 'bg-primary-50 text-primary-700'
                            }`}
                          >
                            <span>{isLesson ? '📖' : '⚡'}</span>
                            <span className="capitalize">{item.item_type}</span>
                          </span>
                        </td>

                        {/* Title & Track Column */}
                        <td className="px-4 py-3">
                          <div className="font-semibold text-ink">
                            {item.title}
                          </div>
                          {item.course_title && (
                            <div className="text-[11px] text-muted">
                              {item.course_title}
                            </div>
                          )}
                        </td>

                        {/* Outcome Column */}
                        <td className="whitespace-nowrap px-4 py-3">
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
                              {item.passed
                                ? `Passed (${item.score ?? 0}%)`
                                : `Score: ${item.score ?? 0}%`}
                            </Badge>
                          )}
                        </td>

                        {/* Time Spent */}
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-body">
                          {formatDuration(item.seconds_spent)}
                        </td>

                        {/* Date */}
                        <td className="whitespace-nowrap px-4 py-3 text-muted">
                          {formatTimestamp(item.completed_at)}
                        </td>

                        {/* Action Column */}
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          {isLesson && item.lesson_id && (
                            <Link to={`/lessons/${item.lesson_id}`}>
                              <Button variant="ghost" size="sm" className="text-xs">
                                Revisit Lesson →
                              </Button>
                            </Link>
                          )}
                          {isQuiz && item.attempt_id && (
                            <Link to={`/quiz/attempts/${item.attempt_id}`}>
                              <Button variant="ghost" size="sm" className="text-xs">
                                Review Results →
                              </Button>
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-muted">
                Page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  ← Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next →
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

