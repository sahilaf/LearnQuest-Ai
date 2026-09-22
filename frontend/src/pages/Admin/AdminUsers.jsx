/**
 * Admin Users - OWNER: Member 3. See plan.md §8.3 & §8.4.
 *
 * User management table with search, role filtering, pagination, and role switching.
 */
import { useEffect, useState } from 'react';
import {
  Users,
  Search,
  Shield,
  GraduationCap,
  RefreshCw,
  AlertCircle,
  Check,
} from 'lucide-react';

import { listUsers, updateUser } from '../../api/admin';
import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  Spinner,
} from '../../components/ui';

function initialsOf(name, email) {
  const str = name || email || 'U';
  return str.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
}

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null); // userId currently being updated
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, page_size: pageSize };
      if (search.trim()) params.search = search.trim();
      if (roleFilter) params.role = roleFilter;

      const res = await listUsers(params);
      const data = res?.data || res;
      setUsers(data?.items || (Array.isArray(data) ? data : []));
      setTotal(data?.total || 0);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [page, search, roleFilter]);

  const handleRoleToggle = async (user) => {
    const nextRole = user.role === 'admin' ? 'student' : 'admin';
    if (
      !window.confirm(
        `Change role of "${user.email}" from ${user.role} to ${nextRole}?`
      )
    ) {
      return;
    }

    setActionLoading(user.id);
    setError(null);
    try {
      await updateUser(user.id, { role: nextRole });
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? { ...u, role: nextRole } : u))
      );
      setSuccessMessage(`Updated ${user.email} to ${nextRole}.`);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update user role.');
    } finally {
      setActionLoading(null);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6">
      <PageHeader
        title="User accounts"
        subtitle="Manage learner profiles, view activity timestamps, and grant administrator permissions."
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchUsers}
            disabled={loading}
            title="Refresh user list"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

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

      {/* Filter Bar */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <input
              type="text"
              placeholder="Search by name or email address..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="field pl-8 text-xs"
            />
          </div>

          <div className="w-36">
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setPage(1);
              }}
              className="field text-xs"
            >
              <option value="">All Roles</option>
              <option value="admin">Administrators</option>
              <option value="student">Students</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="table-dense w-full">
            <thead>
              <tr>
                <th>User / Identity</th>
                <th>User ID</th>
                <th>Role</th>
                <th>Joined</th>
                <th>Last Active</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted">
                    <Spinner size="md" className="mx-auto" />
                    <p className="mt-2 text-xs">Loading user list...</p>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted">
                    No users found matching your search.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-canvas text-2xs font-semibold text-muted">
                          {initialsOf(u.full_name, u.email)}
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold text-ink">
                            {u.full_name || 'Anonymous User'}
                          </div>
                          <div className="text-2xs text-muted">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <code className="text-2xs text-muted font-mono">
                        {u.id.slice(0, 8)}...{u.id.slice(-4)}
                      </code>
                    </td>
                    <td>
                      <Badge tone={u.role === 'admin' ? 'primary' : 'neutral'}>
                        {u.role === 'admin' ? (
                          <span className="flex items-center gap-1">
                            <Shield className="h-3 w-3" />
                            Admin
                          </span>
                        ) : (
                          <span className="flex items-center gap-1">
                            <GraduationCap className="h-3 w-3" />
                            Student
                          </span>
                        )}
                      </Badge>
                    </td>
                    <td className="text-2xs text-muted">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="text-2xs text-muted">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={actionLoading === u.id}
                        loading={actionLoading === u.id}
                        onClick={() => handleRoleToggle(u)}
                        title={
                          u.role === 'admin'
                            ? 'Demote to Student'
                            : 'Promote to Admin'
                        }
                      >
                        {u.role === 'admin' ? 'Demote to Student' : 'Promote to Admin'}
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-line px-4 py-3">
            <span className="text-2xs text-muted">
              Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total} users
            </span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="px-2 text-xs text-muted">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
