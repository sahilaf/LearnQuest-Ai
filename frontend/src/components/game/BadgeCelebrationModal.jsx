import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Award, Sparkles, X, Zap } from 'lucide-react';
import { myAchievements } from '../../api/gamification';

const SEEN_BADGES_KEY = 'learnquest_seen_badges';

/**
 * ConfettiParticle Component
 * Renders celebratory particle bursts using Framer Motion.
 */
function ConfettiParticle({ index }) {
  const colors = ['#F59E0B', '#3B82F6', '#10B981', '#EC4899', '#8B5CF6', '#EF4444'];
  const color = colors[index % colors.length];

  // Random radial trajectory
  const angle = (index / 32) * 2 * Math.PI + (Math.random() * 0.2 - 0.1);
  const distance = 80 + Math.random() * 140;
  const x = Math.cos(angle) * distance;
  const y = Math.sin(angle) * distance - 20;

  return (
    <motion.div
      className="absolute h-2.5 w-2.5 rounded-full"
      style={{ backgroundColor: color }}
      initial={{ x: 0, y: 0, opacity: 1, scale: 0 }}
      animate={{
        x,
        y: [0, y, y + 60],
        opacity: [1, 1, 0],
        scale: [0, 1.4, 0.6],
        rotate: Math.random() * 360,
      }}
      transition={{ duration: 1.8, ease: 'easeOut' }}
    />
  );
}

/**
 * BadgeCelebrationModal Component
 *
 * OWNER: Member 4 (Gamification).
 * Pops up when a new badge is earned, plays confetti animation,
 * and records seen badges in localStorage so it does not repeat.
 */
export function BadgeCelebrationModal({ badge: explicitBadge, onClose }) {
  const [activeBadge, setActiveBadge] = useState(explicitBadge || null);

  // If no explicit badge was passed, check for newly earned unacknowledged badges
  useEffect(() => {
    if (explicitBadge) {
      setActiveBadge(explicitBadge);
      return;
    }

    let isMounted = true;
    myAchievements()
      .then((data) => {
        if (!isMounted || !data?.earned?.length) return;

        let seen = [];
        try {
          seen = JSON.parse(localStorage.getItem(SEEN_BADGES_KEY) || '[]');
        } catch {
          seen = [];
        }

        // Find the most recently earned badge that hasn't been celebrated yet
        const uncelebrated = data.earned.find((b) => !seen.includes(b.id) && !seen.includes(b.code));
        if (uncelebrated) {
          setActiveBadge(uncelebrated);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [explicitBadge]);

  const handleDismiss = () => {
    if (activeBadge) {
      try {
        const seen = JSON.parse(localStorage.getItem(SEEN_BADGES_KEY) || '[]');
        if (activeBadge.id && !seen.includes(activeBadge.id)) seen.push(activeBadge.id);
        if (activeBadge.code && !seen.includes(activeBadge.code)) seen.push(activeBadge.code);
        localStorage.setItem(SEEN_BADGES_KEY, JSON.stringify(seen));
      } catch {
        // Fallback
      }
    }
    setActiveBadge(null);
    if (onClose) onClose();
  };

  if (!activeBadge) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleDismiss}
          className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm"
        />

        {/* Modal Card */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.8, opacity: 0, y: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 350 }}
          className="relative w-full max-w-sm overflow-hidden rounded-2xl border border-amber-200/40 bg-white p-6 text-center shadow-2xl dark:border-amber-500/20 dark:bg-[#171C23]"
        >
          {/* Close button */}
          <button
            type="button"
            onClick={handleDismiss}
            className="absolute right-3.5 top-3.5 flex h-7 w-7 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-[#242B35] dark:hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>

          {/* Confetti Spawner */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            {Array.from({ length: 32 }).map((_, i) => (
              <ConfettiParticle key={i} index={i} />
            ))}
          </div>

          {/* Badge Icon with Glow */}
          <div className="relative mx-auto my-3 flex h-24 w-24 items-center justify-center">
            <motion.div
              animate={{ rotate: [0, 360], scale: [1, 1.1, 1] }}
              transition={{ repeat: Infinity, duration: 12, ease: 'linear' }}
              className="absolute inset-0 rounded-full bg-gradient-to-tr from-amber-400/30 to-orange-400/30 blur-lg dark:from-amber-500/20 dark:to-orange-500/20"
            />
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.15, type: 'spring', stiffness: 300, damping: 20 }}
              className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-400 to-amber-500 text-4xl shadow-lg shadow-amber-500/30"
            >
              {activeBadge.icon || <Award className="h-10 w-10 text-white" />}
            </motion.div>
          </div>

          {/* Heading */}
          <div className="mb-1 flex items-center justify-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
            <Sparkles className="h-3.5 w-3.5" />
            Badge Unlocked!
          </div>

          <h3 className="text-xl font-bold text-slate-900 dark:text-white">
            {activeBadge.name}
          </h3>

          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {activeBadge.description}
          </p>

          {/* XP Bonus Pill */}
          {activeBadge.xp_reward > 0 && (
            <div className="mx-auto mt-3 inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
              <Zap className="h-3.5 w-3.5 fill-amber-500 text-amber-500" />
              +{activeBadge.xp_reward} Bonus XP
            </div>
          )}

          {/* Action button */}
          <div className="mt-6">
            <button
              type="button"
              onClick={handleDismiss}
              className="w-full rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 py-2.5 text-sm font-bold text-white shadow-md shadow-amber-500/25 transition-all hover:opacity-95 active:scale-[0.98]"
            >
              Awesome!
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

export default BadgeCelebrationModal;
