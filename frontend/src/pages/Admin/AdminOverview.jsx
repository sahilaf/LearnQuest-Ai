/**
 * Admin Overview - OWNER: Member 3. See plan.md §8.4 & CHECKLIST.md Slot 7.
 *
 * Displays platform counts: users, courses, enrollments, and active learners today.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  BookOpen,
  GraduationCap,
  Activity,
  Plus,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  Clock,
} from 'lucide-react';

import { overview, listCourses, listUsers } from '../../api/admin';
import PageHeader from '../../components/layout/PageHeader';
import { Badge, Button, Card, Skeleton } from '../../components/ui';

export default function AdminOverview() {
  const [stats, setStats] = useState(null);
  const [recentCourses, setRecentCourses] = useState([]);
  const [recentUsers, setRecentUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchOverviewData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, coursesRes, usersRes] = await Promise.allSettled([
        overview(),
        listCourses({ page_size: 5 }),
        listUsers({ page_size: 5 }),
      ]);

      if (statsRes.status === 'fulfilled') {
        const statsData = statsRes.value?.data || statsRes.value;
        setStats(statsData);
      } else {
        throw statsRes.reason;
      }

      if (coursesRes.status === 'fulfilled') {
        const coursesData = coursesRes.value?.data || coursesRes.value;
        setRecentCourses(coursesData?.items || (Array.isArray(coursesData) ? coursesData : []));
      }
      if (usersRes.status === 'fulfilled') {
        const usersData = usersRes.value?.data || usersRes.value;
        setRecentUsers(usersData?.items || (Array.isArray(usersData) ? usersData : []));
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load admin overview.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverviewData();
  }, []);

  const statCards = [
    {
      id: 'users',
      label: 'Registered users',
      value: stats?.users ?? 0,
      icon: Users,
      badge: 'Total accounts',
      tone: 'primary',
      link: '/admin/users',
    },
    {
      id: 'courses',
      label: 'Active courses',
      value: stats?.courses ?? 0,
      icon: BookOpen,
      badge: 'In catalog',
      tone: 'info',
      link: '/admin/courses',
    },
    {
      id: 'enrollments',
      label: 'Course enrollments',
      value: stats?.enrollments ?? 0,
      icon: GraduationCap,
      badge: 'Student sign-ups',
      tone: 'easy',
      link: '/admin/courses',
    },
    {
      id: 'active',
      label: 'Active learners today',
      value: stats?.active_today ?? 0,
      icon: Activity,
      badge: 'Today',
      tone: stats?.active_today > 0 ? 'easy' : 'neutral',
      link: '/admin/users',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin overview"
        subtitle="Platform activity, database records, and system health at a glance."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchOverviewData}
              disabled={loading}
              title="Refresh metrics"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Link to="/admin/courses">
              <Button variant="primary" size="sm">
                <Plus className="h-3.5 w-3.5" />
                Manage courses
              </Button>
            </Link>
          </div>
        }
      />

      {error && (
        <div className="rounded border border-hard/30 bg-hard-bg p-3 text-sm text-hard-fg">
          <p className="font-medium">Failed to load live metrics: {error}</p>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.id} className="relative flex flex-col justify-between p-4">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-2xs font-semibold uppercase tracking-wider text-muted">
                    {card.label}
                  </span>
                  <div className="mt-1 text-2xl font-semibold text-ink">
                    {loading ? <Skeleton className="h-8 w-16" /> : card.value.toLocaleString()}
                  </div>
                </div>
                <div className="flex h-8 w-8 items-center justify-center rounded bg-canvas text-muted">
                  <Icon className="h-4 w-4" />
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-2.5 text-xs text-muted">
                <Badge tone={card.tone}>{card.badge}</Badge>
                <Link
                  to={card.link}
                  className="inline-flex items-center gap-1 font-medium hover:text-ink"
                >
                  View <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Quick Access & System Info */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Recent Courses Panel */}
        <div className="lg:col-span-2">
          <Card className="p-0">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary-600" />
                <h2 className="text-sm font-semibold text-ink">Courses overview</h2>
              </div>
              <Link
                to="/admin/courses"
                className="text-xs font-medium text-primary-600 hover:text-primary-700"
              >
                View all courses &rarr;
              </Link>
            </div>

            <div className="overflow-x-auto">
              <table className="table-dense w-full">
                <thead>
                  <tr>
                    <th>Title & Subject</th>
                    <th>Difficulty</th>
                    <th>Lessons</th>
                    <th>Status</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-muted">
                        Loading courses...
                      </td>
                    </tr>
                  ) : recentCourses.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-muted">
                        No courses found.
                      </td>
                    </tr>
                  ) : (
                    recentCourses.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <div className="font-medium text-ink">{c.title}</div>
                          <div className="text-2xs text-muted">{c.subject}</div>
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
                        <td className="text-muted">{c.lessons_count ?? 0} lessons</td>
                        <td>
                          <Badge tone={c.is_published ? 'easy' : 'neutral'}>
                            {c.is_published ? 'Published' : 'Draft'}
                          </Badge>
                        </td>
                        <td className="text-right">
                          <Link
                            to={`/courses/${c.slug}`}
                            className="text-xs font-medium text-primary-600 hover:underline"
                          >
                            Preview
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* System & Access Status */}
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex items-center gap-2 border-b border-line pb-3">
              <ShieldCheck className="h-4 w-4 text-easy" />
              <h2 className="text-sm font-semibold text-ink">Admin Privileges</h2>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-muted">
              You are authenticated with role <span className="font-semibold text-ink">admin</span>. You can manage courses, edit lessons, review registered students, and update access permissions.
            </p>
            <div className="mt-4 rounded bg-canvas p-2.5 text-2xs text-muted">
              <div className="flex items-center justify-between">
                <span>Database host:</span>
                <span className="font-mono text-ink">Supabase Cloud</span>
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span>Auth mode:</span>
                <span className="font-mono text-ink">Asymmetric JWKS</span>
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-primary-600" />
                <h2 className="text-sm font-semibold text-ink">Recent Users</h2>
              </div>
              <Link
                to="/admin/users"
                className="text-xs font-medium text-primary-600 hover:underline"
              >
                All users
              </Link>
            </div>

            <div className="mt-3 divide-y divide-line">
              {loading ? (
                <div className="py-3 text-center text-xs text-muted">Loading users...</div>
              ) : recentUsers.length === 0 ? (
                <div className="py-3 text-center text-xs text-muted">No users registered yet.</div>
              ) : (
                recentUsers.slice(0, 4).map((u) => (
                  <div key={u.id} className="flex items-center justify-between py-2 text-xs">
                    <div className="min-w-0 pr-2">
                      <div className="truncate font-medium text-ink">
                        {u.full_name || 'Anonymous User'}
                      </div>
                      <div className="truncate text-2xs text-muted">{u.email}</div>
                    </div>
                    <Badge tone={u.role === 'admin' ? 'primary' : 'neutral'}>
                      {u.role}
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
