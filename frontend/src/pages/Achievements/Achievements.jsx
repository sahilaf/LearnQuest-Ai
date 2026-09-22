import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Award, CheckCircle2, Lock, Sparkles, Trophy, Zap } from 'lucide-react';
import PageHeader from '../../components/layout/PageHeader';
import { Card, EmptyState, Spinner, ProgressBar } from '../../components/ui';
import { myAchievements } from '../../api/gamification';

/**
 * Format ISO timestamp into a readable date string.
 */
function formatEarnedDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return isoStr;
  }
}

export default function Achievements() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all' | 'earned' | 'locked'

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    myAchievements()
      .then((res) => {
        if (isMounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.message || 'Failed to load achievements.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const earnedBadges = data?.earned || [];
  const lockedBadges = data?.locked || [];
  const allBadges = data?.all || [];

  const totalBadges = data?.total_badges || allBadges.length || 0;
  const totalEarned = data?.total_earned || earnedBadges.length || 0;
  const totalXpEarned = earnedBadges.reduce((sum, b) => sum + (b.xp_reward || 0), 0);

  const displayedBadges =
    filter === 'earned'
      ? earnedBadges
      : filter === 'locked'
      ? lockedBadges
      : allBadges;

  return (
    <div className="space-y-8 pb-12">
      {/* Page Header */}
      <PageHeader
        title="Achievements & Badges"
        subtitle="Celebrate your learning milestones and track your next unlockable badges."
      />

      {/* Summary Stats Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="flex items-center gap-3 p-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-medium-bg text-medium-fg text-xl">
            🏆
          </span>
          <div>
            <div className="text-xs font-medium text-muted">Total Badges</div>
            <div className="text-xl font-bold text-ink">{totalBadges}</div>
          </div>
        </Card>

        <Card className="flex items-center gap-3 p-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-easy-bg text-easy-fg text-xl">
            ✓
          </span>
          <div>
            <div className="text-xs font-medium text-muted">Badges Earned</div>
            <div className="text-xl font-bold text-easy-fg">
              {totalEarned} / {totalBadges}
            </div>
          </div>
        </Card>

        <Card className="flex items-center gap-3 p-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-100 text-primary-600 text-xl">
            ⚡
          </span>
          <div>
            <div className="text-xs font-medium text-muted">Bonus XP Earned</div>
            <div className="text-xl font-bold text-primary-600">
              +{totalXpEarned} XP
            </div>
          </div>
        </Card>

        <Card className="flex items-center gap-3 p-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-500/15 text-primary-300 text-xl">
            🔒
          </span>
          <div>
            <div className="text-xs font-medium text-muted">Remaining to Unlock</div>
            <div className="text-xl font-bold text-ink">
              {lockedBadges.length}
            </div>
          </div>
        </Card>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-line pb-2">
        <button
          type="button"
          onClick={() => setFilter('all')}
          className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
            filter === 'all'
              ? 'bg-primary-600 text-white'
              : 'text-body hover:bg-raised'
          }`}
        >
          All Badges ({allBadges.length})
        </button>

        <button
          type="button"
          onClick={() => setFilter('earned')}
          className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
            filter === 'earned'
              ? 'bg-easy text-white'
              : 'text-body hover:bg-raised'
          }`}
        >
          Earned ({earnedBadges.length})
        </button>

        <button
          type="button"
          onClick={() => setFilter('locked')}
          className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
            filter === 'locked'
              ? 'bg-raised text-white'
              : 'text-body hover:bg-raised'
          }`}
        >
          Locked ({lockedBadges.length})
        </button>
      </div>

      {/* Content Section */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : error ? (
        <EmptyState
          title="Couldn't load achievements"
          description={error}
          actionLabel="Try again"
          onAction={() => window.location.reload()}
        />
      ) : displayedBadges.length === 0 ? (
        <EmptyState
          title="No badges match this filter"
          description={
            filter === 'earned'
              ? 'Complete a lesson or maintain a 7-day streak to earn your first badge!'
              : 'You have unlocked all available badges!'
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {displayedBadges.map((badge) => {
            const isEarned = badge.is_earned;
            const progress = badge.progress || {};
            const pct = progress.percentage ?? (isEarned ? 100 : 0);

            return (
              <motion.div
                key={badge.id || badge.code}
                whileHover={{ y: -3 }}
                transition={{ duration: 0.2 }}
              >
                <Card
                  className={`relative flex flex-col justify-between overflow-hidden p-5 transition-all ${
                    isEarned
                      ? 'border-medium/30 bg-gradient-to-b from-surface to-medium shadow-sm'
                      : 'border-line/70 bg-raised/50 opacity-90'
                  }`}
                >
                  {/* Top Row: Icon + Status Pill */}
                  <div className="flex items-start justify-between gap-3">
                    <div
                      className={`flex h-14 w-14 items-center justify-center rounded-2xl text-3xl shadow-sm transition-transform ${
                        isEarned
                          ? 'bg-gradient-to-tr from-medium to-medium shadow-amber-500/20'
                          : 'bg-line text-muted grayscale'
                      }`}
                    >
                      {badge.icon || <Award className="h-7 w-7" />}
                    </div>

                    {isEarned ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-easy-bg px-2.5 py-0.5 text-xs font-semibold text-easy-fg">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Earned
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-line/80 px-2.5 py-0.5 text-xs font-semibold text-body">
                        <Lock className="h-3 w-3" />
                        Locked
                      </span>
                    )}
                  </div>

                  {/* Middle Content */}
                  <div className="mt-4">
                    <h3 className="text-base font-bold text-ink">
                      {badge.name}
                    </h3>
                    <p className="mt-1 text-xs text-body">
                      {badge.description}
                    </p>
                  </div>

                  {/* Bottom: Progress or Earned Date */}
                  <div className="mt-5 border-t border-line/60 pt-3.5">
                    {isEarned ? (
                      <div className="flex items-center justify-between text-xs text-muted">
                        <span>Earned on {formatEarnedDate(badge.earned_at)}</span>
                        {badge.xp_reward > 0 && (
                          <span className="font-semibold text-medium-fg">
                            +{badge.xp_reward} XP
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-2xs font-medium text-muted">
                          <span>
                            Progress: {progress.current ?? 0} / {progress.target ?? 1} {progress.unit || ''}
                          </span>
                          <span>{pct}%</span>
                        </div>
                        <ProgressBar value={pct} max={100} size="sm" tone="primary" />
                      </div>
                    )}
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
