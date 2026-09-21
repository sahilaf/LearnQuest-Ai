import React from 'react';
import { motion } from 'framer-motion';
import { Flame } from 'lucide-react';

/**
 * StreakFlame Component
 *
 * OWNER: Member 4 (Gamification).
 * Visual streak counter with glowing energetic fire styling.
 * Supports compact mode for navigation headers and full mode for dashboard cards.
 */
export function StreakFlame({
  streak,
  currentStreak,
  current_streak,
  longestStreak,
  longest_streak,
  stats,
  compact = false,
  className = '',
}) {
  const current = streak ?? currentStreak ?? current_streak ?? stats?.current_streak ?? 0;
  const longest = longestStreak ?? longest_streak ?? stats?.longest_streak ?? current;
  const hasStreak = current > 0;

  if (compact) {
    return (
      <div
        className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-all ${
          hasStreak
            ? 'bg-amber-50 text-amber-700 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/50'
            : 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-[#1C222B] dark:text-slate-400'
        } ${className}`}
        title={`Streak: ${current} ${current === 1 ? 'day' : 'days'} • Longest: ${longest} days`}
      >
        <motion.span
          animate={hasStreak ? { scale: [1, 1.15, 1] } : {}}
          transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
          className="inline-flex items-center"
        >
          <Flame
            className={`h-4 w-4 ${
              hasStreak ? 'fill-amber-500 text-amber-500 dark:fill-amber-400 dark:text-amber-400' : 'text-slate-400'
            }`}
          />
        </motion.span>
        <span>{current}</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <motion.div
        whileHover={{ scale: 1.05 }}
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-colors ${
          hasStreak
            ? 'bg-gradient-to-br from-amber-100 to-orange-100 text-amber-600 shadow-sm dark:from-amber-950/70 dark:to-orange-950/50 dark:text-amber-400'
            : 'bg-slate-100 text-slate-400 dark:bg-[#242B35] dark:text-slate-500'
        }`}
      >
        <Flame className={`h-6 w-6 ${hasStreak ? 'fill-amber-500 text-amber-500 animate-pulse' : ''}`} />
      </motion.div>

      <div className="min-w-0">
        <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Day Streak</div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
            {current} {current === 1 ? 'day' : 'days'}
          </span>
          {longest > current && (
            <span className="text-2xs text-slate-400 dark:text-slate-500">
              (Best: {longest})
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default StreakFlame;
