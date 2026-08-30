/** Authenticated app shell. OWNER: Member 3. */
import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

const NAV = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/courses', label: 'Courses' },
  { to: '/tutor', label: 'AI Tutor' },
  { to: '/achievements', label: 'Achievements' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/stats', label: 'Stats' },
  { to: '/history', label: 'History' },
];

export default function AppLayout() {
  const { user, isAdmin, devMode, logout } = useAuth();

  return (
    <div className="min-h-full">
      {devMode && (
        <div className="bg-amber-500 px-4 py-1.5 text-center text-xs font-medium text-amber-950">
          Dev mode - Firebase is not configured. Auth is stubbed (plan.md 8.2).
        </div>
      )}

      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <NavLink to="/dashboard" className="text-lg font-bold text-primary-600">
            LearnQuest
          </NavLink>

          <nav className="hidden gap-1 md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-primary-50 font-medium text-primary-700 dark:bg-primary-900/40 dark:text-primary-200'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            {isAdmin && (
              <NavLink
                to="/admin"
                className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Admin
              </NavLink>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {/* TODO(M4): drop <XPBar /> and <StreakFlame /> in here. */}
            <NavLink to="/profile" className="text-sm text-slate-600 dark:text-slate-300">
              {user?.full_name ?? 'Profile'}
            </NavLink>
            <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-900">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
