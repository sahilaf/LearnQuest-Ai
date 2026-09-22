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
 * Shell shape (docs/DESIGN_GUIDELINES.md): a full-height sidebar pinned to the
 * left edge, a top bar for identity and status, content in a wide measured
 * column. Dark, flat and quiet - navigation should recede so the content reads.
 *
 * Redesigned 2026-09-22. The previous shell put the nav *inside* a 1400px
 * centred container with a 16px gutter, so on a 1920 screen you got roughly
 * 260px of dead margin on each side while the content itself felt cramped -
 * empty and tight at the same time, which is the worst of both. Now the
 * sidebar is anchored to the viewport edge and the content column uses `.shell`
 * (1600px, gutters that grow with the viewport).
 */
const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/roadmap', label: 'Roadmap', icon: Map },
  { to: '/courses', label: 'Courses', icon: BookOpen },
  { to: '/tutor', label: 'AI Tutor', icon: Sparkles },
  { to: '/achievements', label: 'Achievements', icon: Trophy },
];

// Restore these as each one is built (routes already exist in App.jsx):
//   { to: '/stats',        label: 'Stats',        icon: BarChart3 }
//   { to: '/history',      label: 'History',      icon: HistoryIcon }
//   { to: '/practice',     label: 'Practice',     icon: Code2 }
// A nav link to a placeholder page is a dead end; one to a missing route 404s.

const MOBILE_NAV = NAV.slice(0, 5);

const ADMIN_NAV = [
  { to: '/admin', label: 'Overview', icon: Shield, end: true },
  { to: '/admin/courses', label: 'Courses', icon: BookOpen },
  { to: '/admin/users', label: 'Users', icon: Users },
];

function initialsOf(name) {
  if (!name) return 'ME';
  return name.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
}

/**
 * Active state is a violet left edge plus a raised background. On a near-black
 * canvas a tint alone is too subtle to scan, and a full violet fill would make
 * navigation shout louder than the page it frames.
 */
function navLinkClass({ isActive }) {
  return `relative flex items-center gap-3 rounded px-3 py-2.5 text-base transition-colors ${
    isActive
      ? 'bg-raised font-medium text-ink before:absolute before:inset-y-1.5 before:-left-px before:w-0.5 before:rounded-full before:bg-primary-500'
      : 'text-muted hover:bg-raised/60 hover:text-ink'
  }`;
}

function tabLinkClass({ isActive }) {
  return `flex flex-1 flex-col items-center gap-1 rounded px-1 py-2 text-2xs font-medium transition-colors ${
    isActive ? 'text-primary-400' : 'text-muted'
  }`;
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

  return (
    <div className="min-h-full bg-canvas">
      {devMode && (
        <div className="border-b border-medium/30 bg-medium-bg px-4 py-1.5 text-center text-xs font-medium text-medium-fg">
          Dev mode — signed in as a local test user
        </div>
      )}

      <div className="flex min-h-full">
        {/* Sidebar, anchored to the viewport edge rather than floating inside
            a centred container. */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface lg:flex">
          <NavLink
            to="/dashboard"
            className="flex h-16 shrink-0 items-center gap-2.5 border-b border-line px-5"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded bg-primary-600 text-white">
              <Sparkles className="h-4.5 w-4.5" />
            </span>
            <span className="text-lg font-semibold tracking-tight text-ink">LearnQuest</span>
          </NavLink>

          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
            <span className="label px-3 pb-1 pt-2">Learn</span>
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} className={navLinkClass}>
                <Icon className="h-[18px] w-[18px] shrink-0" />
                {label}
              </NavLink>
            ))}

            {isAdmin && (
              <>
                <span className="label px-3 pb-1 pt-5">Admin</span>
                {ADMIN_NAV.map(({ to, label, icon: Icon, end }) => (
                  <NavLink key={to} to={to} end={end} className={navLinkClass}>
                    <Icon className="h-[18px] w-[18px] shrink-0" />
                    {label}
                  </NavLink>
                ))}
              </>
            )}
          </nav>

          <div className="shrink-0 border-t border-line p-3">
            <NavLink
              to="/profile"
              className="flex items-center gap-3 rounded px-3 py-2.5 transition-colors hover:bg-raised"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-raised text-xs font-semibold text-body">
                {initialsOf(user?.full_name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-ink">
                  {user?.full_name ?? 'Your profile'}
                </span>
                <span className="block truncate text-2xs text-faint">{user?.email}</span>
              </span>
            </NavLink>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-line bg-canvas/85 backdrop-blur">
            <div className="shell flex h-16 items-center gap-4">
              <NavLink to="/dashboard" className="flex shrink-0 items-center gap-2.5 lg:hidden">
                <span className="flex h-8 w-8 items-center justify-center rounded bg-primary-600 text-white">
                  <Sparkles className="h-4.5 w-4.5" />
                </span>
                <span className="text-lg font-semibold tracking-tight text-ink">LearnQuest</span>
              </NavLink>

              <div className="ml-auto flex items-center gap-4">
                {stats && (
                  <div className="flex items-center gap-3">
                    <StreakFlame stats={stats} compact />
                    <XPBar stats={stats} compact />
                  </div>
                )}

                <NavLink
                  to="/profile"
                  title={user?.full_name ?? 'Profile'}
                  className="flex h-9 w-9 items-center justify-center rounded-pill bg-raised text-xs font-semibold text-body transition-colors hover:text-ink lg:hidden"
                >
                  {initialsOf(user?.full_name)}
                </NavLink>

                <button
                  type="button"
                  onClick={logout}
                  title="Sign out"
                  className="flex h-9 w-9 items-center justify-center rounded text-muted transition-colors hover:bg-raised hover:text-hard"
                >
                  <LogOut className="h-[18px] w-[18px]" />
                  <span className="sr-only">Sign out</span>
                </button>
              </div>
            </div>
          </header>

          <main className="shell min-w-0 flex-1 py-8 pb-24 lg:pb-12">
            <Outlet />
          </main>
        </div>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface px-2 py-1 lg:hidden">
        <div className="mx-auto flex max-w-lg items-center">
          {MOBILE_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={tabLinkClass}>
              <Icon className="h-5 w-5" />
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
