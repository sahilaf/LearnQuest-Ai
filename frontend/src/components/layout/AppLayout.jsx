/** Authenticated app shell. OWNER: Member 3. */
import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Map,
  BookOpen,
  Sparkles,
  Shield,
  Users,
  LogOut,
  Trophy,
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { StreakFlame, XPBar, BadgeCelebrationModal } from '../game';
import { myStats } from '../../api/gamification';

/**
 * Shell follows the system's shape (docs/DESIGN_GUIDELINES.md): a top bar for
 * identity and status, a compact left rail for navigation. Dense, flat, and
 * quiet - navigation should recede so the content reads.
 */
const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/roadmap', label: 'Roadmap', icon: Map },
  { to: '/courses', label: 'Courses', icon: BookOpen },
  { to: '/tutor', label: 'AI Tutor', icon: Sparkles },
  { to: '/achievements', label: 'Achievements', icon: Trophy },
];

// Restore these as each one is built (routes already exist in App.jsx):
//   { to: '/achievements', label: 'Achievements', icon: Trophy }
//   { to: '/stats',        label: 'Stats',        icon: BarChart3 }
//   { to: '/history',      label: 'History',      icon: HistoryIcon }
//   { to: '/practice',     label: 'Practice',     icon: Code2 }
// A nav link to a placeholder page is a dead end; one to a missing route 404s.

const MOBILE_NAV = NAV.slice(0, 5);

function initialsOf(name) {
  if (!name) return 'ME';
  return name.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
}

export default function AppLayout() {
  const { user, isAdmin, devMode, logout } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let isMounted = true;
    if (user) {
      myStats()
        .then((res) => {
          if (isMounted && res) setStats(res);
        })
        .catch(() => {});
    }
    return () => {
      isMounted = false;
    };
  }, [user]);

  const railLink = ({ isActive }) =>
    `flex items-center gap-2.5 rounded px-3 py-2 text-sm transition-colors ${
      isActive
        ? 'bg-primary-50 font-medium text-primary-700 dark:bg-primary-900/25 dark:text-primary-300'
        : 'text-muted hover:bg-canvas hover:text-body dark:hover:bg-[#1C222B] dark:hover:text-white'
    }`;

  const tabLink = ({ isActive }) =>
    `flex flex-1 flex-col items-center gap-0.5 rounded px-1 py-1.5 text-2xs transition-colors ${
      isActive ? 'text-primary-700 dark:text-primary-400' : 'text-muted'
    }`;

  return (
    <div className="min-h-full">
      {devMode && (
        <div className="border-b border-medium/30 bg-medium-bg px-4 py-1 text-center text-2xs font-medium text-medium-fg">
          Dev mode — signed in as a local test user
        </div>
      )}

      <header className="sticky top-0 z-30 border-b border-line bg-surface dark:border-[#242B35] dark:bg-[#171C23]">
        <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-2">
          <NavLink to="/dashboard" className="flex shrink-0 items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-primary-600 text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="text-base font-semibold text-ink dark:text-white">LearnQuest</span>
          </NavLink>

          <div className="ml-auto flex items-center gap-3">
            {stats && (
              <div className="flex items-center gap-2">
                <StreakFlame stats={stats} compact />
                <XPBar stats={stats} compact />
              </div>
            )}

            <NavLink
              to="/profile"
              title={user?.full_name ?? 'Profile'}
              className="flex h-7 w-7 items-center justify-center rounded-full bg-canvas text-2xs font-semibold text-muted transition-colors hover:bg-line dark:bg-[#1C222B]"
            >
              {initialsOf(user?.full_name)}
            </NavLink>

            <button
              type="button"
              onClick={logout}
              title="Sign out"
              className="flex h-7 w-7 items-center justify-center rounded text-faint transition-colors hover:bg-canvas hover:text-hard dark:hover:bg-[#1C222B]"
            >
              <LogOut className="h-4 w-4" />
              <span className="sr-only">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1400px] gap-6 px-4 py-5">
        <nav className="sticky top-[3.25rem] hidden h-fit w-48 shrink-0 flex-col gap-0.5 lg:flex">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={railLink}>
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
          {isAdmin && (
            <>
              <span className="label mt-4 px-3">Admin</span>
              <NavLink to="/admin" end className={railLink}>
                <Shield className="h-4 w-4 shrink-0" />
                Overview
              </NavLink>
              <NavLink to="/admin/courses" className={railLink}>
                <BookOpen className="h-4 w-4 shrink-0" />
                Courses
              </NavLink>
              <NavLink to="/admin/users" className={railLink}>
                <Users className="h-4 w-4 shrink-0" />
                Users
              </NavLink>
            </>
          )}
        </nav>

        <main className="min-w-0 flex-1 pb-20 lg:pb-0">
          <Outlet />
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface px-2 py-1 lg:hidden dark:border-[#242B35] dark:bg-[#171C23]">
        <div className="mx-auto flex max-w-lg items-center">
          {MOBILE_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={tabLink}>
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* In-app badge celebration modal with confetti */}
      <BadgeCelebrationModal />
    </div>
  );
}
