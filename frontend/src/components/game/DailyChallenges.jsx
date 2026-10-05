/**
 * DailyChallenges component.
 * OWNER: Member 4.
 *
 * Renders today's 3 daily challenges with live progress, rewards,
 * and an interactive reward claim flow.
 */
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Sparkles, Zap, Clock } from 'lucide-react';
import { todaysChallenges, claimChallenge } from '../../api/gamification';
import { Card, Button, ProgressBar } from '../ui';

export default function DailyChallenges({ onClaimed }) {
  const [challenges, setChallenges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [claimingId, setClaimingId] = useState(null);
  const [claimFeedback, setClaimFeedback] = useState(null);

  const fetchChallenges = async () => {
    try {
      setLoading(true);
      const res = await todaysChallenges();
      if (res && res.items) {
        setChallenges(res.items);
      }
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChallenges();
  }, []);

  const handleClaim = async (challenge) => {
    if (!challenge.is_completed || challenge.is_claimed || claimingId) return;

    try {
      setClaimingId(challenge.id);
      const res = await claimChallenge(challenge.id);
      if (res && res.claimed) {
        setClaimFeedback({
          id: challenge.id,
          xp: res.xp_awarded,
        });

        // Update local state to claimed
        setChallenges((prev) =>
          prev.map((c) => (c.id === challenge.id ? { ...c, is_claimed: true } : c))
        );

        if (onClaimed) {
          onClaimed(res);
        }

        setTimeout(() => setClaimFeedback(null), 3000);
      }
    } catch (err) {
      // Ignore or show error
    } finally {
      setClaimingId(null);
    }
  };

  if (loading && challenges.length === 0) {
    return (
      <Card className="p-5">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="h-5 w-36 animate-pulse rounded bg-raised" />
          <div className="h-4 w-20 animate-pulse rounded bg-raised" />
        </div>
        <div className="mt-4 space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-raised/60" />
          ))}
        </div>
      </Card>
    );
  }

  if (challenges.length === 0) {
    return null;
  }

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-500/10 text-primary-400">
            <Zap className="h-4 w-4" />
          </span>
          <h3 className="text-sm font-semibold text-ink">Daily Challenges</h3>
        </div>
        <div className="flex items-center gap-1.5 text-2xs text-faint">
          <Clock className="h-3.5 w-3.5" />
          <span>Resets daily</span>
        </div>
      </div>

      <div className="mt-4 space-y-3.5">
        {challenges.map((ch) => {
          const progressPct = Math.min(
            100,
            Math.round(((ch.progress_value || 0) / (ch.target_value || 1)) * 100)
          );
          const isClaiming = claimingId === ch.id;
          const showCelebration = claimFeedback?.id === ch.id;

          return (
            <div
              key={ch.id}
              className={`relative overflow-hidden rounded-xl border p-3.5 transition-all ${
                ch.is_claimed
                  ? 'border-line/40 bg-surface/40 opacity-75'
                  : ch.is_completed
                  ? 'border-easy-fg/30 bg-easy-bg/20 shadow-sm'
                  : 'border-line bg-surface/80'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-ink">{ch.title}</span>
                    <span className="flex items-center gap-1 rounded-full bg-primary-500/10 px-2 py-0.5 text-2xs font-medium text-primary-400">
                      +{ch.xp_reward} XP
                    </span>
                  </div>
                  <p className="mt-0.5 text-2xs text-muted leading-relaxed">{ch.description}</p>
                </div>

                {/* Claim / Status Action */}
                <div className="shrink-0">
                  {ch.is_claimed ? (
                    <span className="flex items-center gap-1 rounded-pill bg-raised px-2.5 py-1 text-2xs font-medium text-faint">
                      <CheckCircle2 className="h-3 w-3 text-easy-fg" />
                      Claimed
                    </span>
                  ) : ch.is_completed ? (
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handleClaim(ch)}
                      disabled={isClaiming}
                      className="relative text-2xs px-3 py-1 font-semibold animate-pulse"
                    >
                      {isClaiming ? 'Claiming...' : `Claim +${ch.xp_reward} XP`}
                    </Button>
                  ) : (
                    <span className="text-2xs font-medium text-muted">
                      {ch.progress_value} / {ch.target_value}
                    </span>
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              {!ch.is_claimed && (
                <div className="mt-2.5">
                  <div className="flex justify-between text-[10px] text-faint mb-1">
                    <span>Progress</span>
                    <span>{progressPct}%</span>
                  </div>
                  <ProgressBar
                    value={progressPct}
                    tone={ch.is_completed ? 'easy' : 'primary'}
                    size="xs"
                  />
                </div>
              )}

              {/* Reward Feedback Popup */}
              {showCelebration && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center bg-canvas/90 backdrop-blur-sm"
                >
                  <div className="flex items-center gap-1.5 text-sm font-bold text-easy-fg">
                    <Sparkles className="h-4 w-4" />
                    +{claimFeedback.xp} XP Claimed!
                  </div>
                </motion.div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
