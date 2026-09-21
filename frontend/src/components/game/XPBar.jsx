import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Zap } from 'lucide-react';

/**
 * XPBar Component
 *
 * OWNER: Member 4 (Gamification).
 * Displays level, current XP, and progression to the next level.
 * Supports full card/widget mode and compact mode for navigation bars.
 */
export function XPBar({
  xp,
  level,
  nextLevelXp,
  next_level_xp,
  stats,
  compact = false,
  showDetails = true,
  className = '',
}) {
  // Extract values with priority: direct props > stats object > defaults
  const currentXp = xp ?? stats?.xp ?? 0;
  const currentLevel = level ?? stats?.level ?? 1;
  const targetXp = nextLevelXp ?? next_level_xp ?? stats?.next_level_xp ?? 282;

  // Percentage progress to next level
  const pct = targetXp > 0 ? Math.min(100, Math.max(0, Math.round((currentXp / targetXp) * 100))) : 0;

  if (compact) {
    return (
      <div
        className={`flex items-center gap-1.5 rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 transition-all hover:bg-primary-100 dark:bg-primary-950/40 dark:text-primary-300 dark:hover:bg-primary-900/50 ${className}`}
        title={`Level ${currentLevel} • ${currentXp} / ${targetXp} XP (${pct}%)`}
      >
        <Zap className="h-3.5 w-3.5 text-primary-500 dark:text-primary-400" />
        <span>Lvl {currentLevel}</span>
        <span className="text-primary-400 dark:text-primary-500">•</span>
        <span>{currentXp} XP</span>
      </div>
    );
  }

  return (
    <div className={`w-full ${className}`}>
      {showDetails && (
        <div className="mb-1.5 flex items-center justify-between text-xs font-medium">
          <span className="flex items-center gap-1 text-slate-700 dark:text-slate-200 font-semibold">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-primary-100 text-primary-700 dark:bg-primary-900/60 dark:text-primary-300 text-2xs">
              L{currentLevel}
            </span>
            Level {currentLevel}
          </span>
          <span className="text-slate-500 dark:text-slate-400">
            <strong className="text-slate-800 dark:text-slate-100">{currentXp}</strong> / {targetXp} XP
          </span>
        </div>
      )}

      {/* Progress Track */}
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Level ${currentLevel} progress`}
        className="relative h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-[#242B35]"
      >
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-primary-500 to-indigo-500"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}

export default XPBar;
