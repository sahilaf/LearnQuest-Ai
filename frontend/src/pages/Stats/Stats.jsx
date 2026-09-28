/**
 * Learning Analytics & Misconception Map.
 * OWNER: Member 4.
 *
 * Implements:
 * - Headline metrics summary (lessons, quizzes, avg score, time, retention)
 * - Interactive Misconception Map (Active -> Fading -> Cleared)
 * - Spaced repetition review queue analytics
 * - Topic mastery breakdown (Weakest vs Strongest topics)
 * - Recharts activity timeline with 7d / 30d / 56d windows
 * - Handles 0 data, 1 day, several weeks gracefully
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  BookOpen,
  CheckCircle2,
  Clock,
  RotateCcw,
  Sparkles,
  Target,
} from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import { Badge, Button, Card, ProgressBar, Spinner } from '../../components/ui';
import { mySummary, myActivity, myReviewQueue, myMisconceptions, myMastery } from '../../api/analytics';

function formatDuration(minutes) {
  if (!minutes || minutes <= 0) return '0m';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem > 0 ? `${hours}h ${rem}m` : `${hours}h`;
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export default function Stats({ embedded = false }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [summary, setSummary] = useState(null);
  const [activityData, setActivityData] = useState([]);
  const [activityDays, setActivityDays] = useState(56);
  const [activityMetric, setActivityMetric] = useState('minutes'); // 'minutes' | 'xp'
  const [misconceptions, setMisconceptions] = useState({ items: [], counts: { active: 0, fading: 0, cleared: 0 } });
  const [misconceptionFilter, setMisconceptionFilter] = useState('all'); // 'all' | 'active' | 'fading' | 'cleared'
  const [masteryTopics, setMasteryTopics] = useState([]);
  const [reviewQueue, setReviewQueue] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, actRes, miscRes, mastRes, revRes] = await Promise.allSettled([
        mySummary(),
        myActivity(activityDays),
        myMisconceptions(true),
        myMastery(),
        myReviewQueue(),
      ]);

      if (sumRes.status === 'fulfilled' && sumRes.value) {
        setSummary(sumRes.value);
      }
      if (actRes.status === 'fulfilled' && actRes.value) {
        setActivityData(actRes.value.items || []);
      }
      if (miscRes.status === 'fulfilled' && miscRes.value) {
        setMisconceptions(miscRes.value);
      }
      if (mastRes.status === 'fulfilled' && mastRes.value) {
        setMasteryTopics(mastRes.value.items || []);
      }
      if (revRes.status === 'fulfilled' && revRes.value) {
        setReviewQueue(revRes.value);
      }
    } catch (err) {
      setError(err?.message || 'Failed to load analytics.');
    } finally {
      setLoading(false);
    }
  }, [activityDays]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filtered misconceptions
  const filteredMisconceptions = useMemo(() => {
    const list = misconceptions.items || [];
    if (misconceptionFilter === 'all') return list;
    return list.filter((m) => m.status === misconceptionFilter);
  }, [misconceptions, misconceptionFilter]);

  // Topic mastery sorted weak vs strong
  const sortedTopics = useMemo(() => {
    return [...masteryTopics].sort((a, b) => (a.mastery_score || 0) - (b.mastery_score || 0));
  }, [masteryTopics]);

  const formattedChartData = useMemo(() => {
    if (!activityData || activityData.length === 0) return [];
    return activityData.map((d) => ({
      date: formatDate(d.date),
      minutes: d.minutes || 0,
      xp: d.xp || 0,
      lessons: d.lessons || 0,
      quizzes: d.quizzes || 0,
    }));
  }, [activityData]);

  const totalActivityValue = useMemo(() => {
    return formattedChartData.reduce((acc, curr) => acc + (curr[activityMetric] || 0), 0);
  }, [formattedChartData, activityMetric]);

  return (
    <div className="space-y-8 pb-16">
      {!embedded && (
        <PageHeader
          title="Learning Analytics"
          subtitle="Track your false belief recovery, review retention, and study momentum over time."
        />
      )}

      {loading && !summary ? (
        <div className="flex h-64 items-center justify-center">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <Card className="border-hard/30 bg-hard-bg/20 p-6 text-center text-hard-fg">
          {error}
        </Card>
      ) : (
        <>
          {/* 1. Headline Metrics Grid */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Card className="flex items-center gap-3.5 p-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-info-bg text-info-fg text-lg">
                <Clock className="h-5 w-5" />
              </span>
              <div>
                <div className="text-2xs font-medium uppercase tracking-wider text-muted">Study Time</div>
                <div className="text-xl font-bold text-ink">
                  {formatDuration(summary?.minutes || 0)}
                </div>
              </div>
            </Card>

            <Card className="flex items-center gap-3.5 p-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-500/10 text-primary-400 text-lg">
                <BookOpen className="h-5 w-5" />
              </span>
              <div>
                <div className="text-2xs font-medium uppercase tracking-wider text-muted">Lessons Completed</div>
                <div className="text-xl font-bold text-ink">
                  {summary?.lessons_completed || 0}
                </div>
              </div>
            </Card>

            <Card className="flex items-center gap-3.5 p-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-medium-bg text-medium-fg text-lg">
                <Target className="h-5 w-5" />
              </span>
              <div>
                <div className="text-2xs font-medium uppercase tracking-wider text-muted">Quiz Accuracy</div>
                <div className="text-xl font-bold text-ink">
                  {summary?.avg_score || 0}%
                  <span className="ml-1 text-2xs font-normal text-muted">
                    ({summary?.quizzes_taken || 0} quizzes)
                  </span>
                </div>
              </div>
            </Card>

            <Card className="flex items-center gap-3.5 p-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-easy-bg text-easy-fg text-lg">
                <RotateCcw className="h-5 w-5" />
              </span>
              <div>
                <div className="text-2xs font-medium uppercase tracking-wider text-muted">Review Retention</div>
                <div className="text-xl font-bold text-easy-fg">
                  {summary?.review_queue?.retention_rate || reviewQueue?.retention_rate || 0}%
                </div>
              </div>
            </Card>
          </div>

          {/* 2. MISCONCEPTION MAP - THE CORE SHOWCASE */}
          <div className="space-y-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-ink">Misconception Map</h2>
                  <span className="flex items-center gap-1 rounded-full bg-primary-500/10 px-2.5 py-0.5 text-2xs font-semibold text-primary-400">
                    <Sparkles className="h-3 w-3" />
                    AI Diagnostic
                  </span>
                </div>
                <p className="text-xs text-muted">
                  What you misunderstood → whether it is improving → whether it has been overcome.
                </p>
              </div>

              {/* Status Filter Buttons */}
              <div className="flex items-center gap-1.5 rounded-lg border border-line bg-surface p-1 text-2xs">
                {[
                  { key: 'all', label: `All (${misconceptions.items?.length || 0})` },
                  { key: 'active', label: `Active (${misconceptions.counts?.active || 0})`, tone: 'text-hard-fg' },
                  { key: 'fading', label: `Fading (${misconceptions.counts?.fading || 0})`, tone: 'text-medium-fg' },
                  { key: 'cleared', label: `Cleared (${misconceptions.counts?.cleared || 0})`, tone: 'text-easy-fg' },
                ].map(({ key, label, tone }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setMisconceptionFilter(key)}
                    className={`rounded px-2.5 py-1 font-medium transition-colors ${
                      misconceptionFilter === key
                        ? 'bg-raised font-semibold text-ink shadow-sm'
                        : `${tone || 'text-muted'} hover:text-ink`
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Misconceptions List */}
            {filteredMisconceptions.length === 0 ? (
              <Card className="p-8 text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-easy-bg/40 text-easy-fg">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h3 className="text-sm font-semibold text-ink">
                  {misconceptionFilter === 'all'
                    ? 'No Misconceptions Recorded'
                    : `No ${misconceptionFilter} misconceptions`}
                </h3>
                <p className="mx-auto mt-1 max-w-sm text-xs text-muted leading-relaxed">
                  {misconceptionFilter === 'all'
                    ? 'When an incorrect quiz or practice response reveals a conceptual false belief, Nova captures it here so you can systematically overcome it.'
                    : `You have no misconceptions in the "${misconceptionFilter}" state right now.`}
                </p>
              </Card>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {filteredMisconceptions.map((item, idx) => {
                  const isActive = item.status === 'active';
                  const isFading = item.status === 'fading';
                  const isCleared = item.status === 'cleared';

                  return (
                    <motion.div
                      key={item.topic_tag + idx}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: idx * 0.05 }}
                    >
                      <Card
                        className={`flex h-full flex-col justify-between p-4 transition-all ${
                          isActive
                            ? 'border-hard/30 bg-hard-bg/10'
                            : isFading
                            ? 'border-medium/30 bg-medium-bg/10'
                            : 'border-easy/30 bg-easy-bg/10'
                        }`}
                      >
                        <div className="space-y-2.5">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-2xs font-semibold text-primary-400">
                              {item.topic_tag}
                            </span>
                            <Badge
                              tone={isActive ? 'danger' : isFading ? 'warning' : 'easy'}
                              className="text-[10px] uppercase font-bold"
                            >
                              {item.status}
                            </Badge>
                          </div>

                          <div>
                            <div className="text-2xs font-medium uppercase text-muted mb-0.5">
                              {isCleared ? 'Overcome Belief' : 'Recorded Misconception'}
                            </div>
                            <p className="text-xs text-ink leading-relaxed font-medium">
                              &ldquo;{item.misconception}&rdquo;
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 pt-3 border-t border-line/40 flex items-center justify-between text-2xs text-faint">
                          <div>
                            {isActive && <span>Needs practice to clear</span>}
                            {isFading && (
                              <span className="text-medium-fg font-medium">
                                Streak: {item.correct_streak || 1} correct in a row
                              </span>
                            )}
                            {isCleared && (
                              <span className="text-easy-fg font-medium">
                                Cleared ✓ {item.cleared_at ? formatDate(item.cleared_at) : 'Mastered'}
                              </span>
                            )}
                          </div>

                          {!isCleared && (
                            <Link to={`/tutor?topic=${encodeURIComponent(item.topic_tag)}`}>
                              <Button variant="ghost" size="xs" className="text-2xs text-primary-400">
                                Practice with Tutor →
                              </Button>
                            </Link>
                          )}
                        </div>
                      </Card>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 3. LEARNING ACTIVITY TIMELINE (RECHARTS) */}
          <Card className="p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-ink">Study Activity Timeline</h2>
                  <span className="rounded-full bg-raised px-2 py-0.5 text-2xs font-medium text-muted">
                    Total: {activityMetric === 'minutes' ? formatDuration(totalActivityValue) : `${totalActivityValue} XP`}
                  </span>
                </div>
                <p className="text-xs text-muted">Daily learning volume across your study sessions.</p>
              </div>

              <div className="flex items-center gap-3">
                {/* Metric Selector */}
                <div className="flex items-center rounded-lg border border-line bg-raised/60 p-0.5 text-2xs">
                  <button
                    type="button"
                    onClick={() => setActivityMetric('minutes')}
                    className={`rounded px-2.5 py-1 font-medium transition-colors ${
                      activityMetric === 'minutes' ? 'bg-surface font-semibold text-ink shadow-sm' : 'text-muted hover:text-ink'
                    }`}
                  >
                    Minutes
                  </button>
                  <button
                    type="button"
                    onClick={() => setActivityMetric('xp')}
                    className={`rounded px-2.5 py-1 font-medium transition-colors ${
                      activityMetric === 'xp' ? 'bg-surface font-semibold text-ink shadow-sm' : 'text-muted hover:text-ink'
                    }`}
                  >
                    XP
                  </button>
                </div>

                {/* Days Window */}
                <div className="flex items-center rounded-lg border border-line bg-raised/60 p-0.5 text-2xs">
                  {[
                    { days: 7, label: '7D' },
                    { days: 30, label: '30D' },
                    { days: 56, label: '8W' },
                  ].map(({ days, label }) => (
                    <button
                      key={days}
                      type="button"
                      onClick={() => setActivityDays(days)}
                      className={`rounded px-2.5 py-1 font-medium transition-colors ${
                        activityDays === days ? 'bg-surface font-semibold text-primary-400 shadow-sm' : 'text-muted hover:text-ink'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Recharts Area Container */}
            <div className="mt-6 h-64 w-full">
              {formattedChartData.length === 0 ? (
                <div className="flex h-full items-center justify-center text-xs text-muted">
                  No activity in this time window.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={formattedChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="activityGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222730" vertical={false} />
                    <XAxis
                      dataKey="date"
                      stroke="#6E7785"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      stroke="#6E7785"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      domain={[0, 'auto']}
                    />
                    <Tooltip
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="rounded-lg border border-line bg-surface p-2.5 shadow-xl text-xs">
                              <div className="font-semibold text-ink">{label}</div>
                              <div className="mt-1 text-primary-400 font-medium">
                                {data[activityMetric]} {activityMetric === 'minutes' ? 'mins' : 'XP'}
                              </div>
                              <div className="text-2xs text-muted">
                                {data.lessons} lessons • {data.quizzes} quizzes
                              </div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey={activityMetric}
                      stroke="#a78bfa"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#activityGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </Card>

          {/* 4. Two Column Grid: Topic Mastery & Spaced Repetition Queue */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Topic Mastery Breakdown */}
            <Card className="p-5">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-500/10 text-primary-400">
                    <Target className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Topic Mastery Breakdown</h3>
                </div>
                <span className="text-2xs text-muted">{sortedTopics.length} topics</span>
              </div>

              {sortedTopics.length === 0 ? (
                <div className="p-8 text-center text-xs text-muted">
                  No topic mastery data recorded yet. Complete quizzes to establish your topic mastery profile.
                </div>
              ) : (
                <div className="mt-4 space-y-3.5">
                  {sortedTopics.slice(0, 6).map((t) => {
                    const scorePct = Math.round((t.mastery_score || 0) * 100);
                    const isWeak = scorePct < 60;
                    const isStrong = scorePct >= 80;

                    return (
                      <div key={t.topic_tag} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono text-2xs text-ink font-medium">
                            {t.topic_tag}
                          </span>
                          <span
                            className={`font-semibold text-2xs ${
                              isStrong ? 'text-easy-fg' : isWeak ? 'text-hard-fg' : 'text-medium-fg'
                            }`}
                          >
                            {scorePct}%
                          </span>
                        </div>
                        <ProgressBar
                          value={scorePct}
                          tone={isStrong ? 'easy' : isWeak ? 'danger' : 'warning'}
                          size="xs"
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            {/* Spaced Repetition Review Queue */}
            <Card className="p-5">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-easy-bg text-easy-fg">
                    <RotateCcw className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Review Queue Status</h3>
                </div>
                <Badge
                  tone={
                    (reviewQueue?.due_today || 0) > 0
                      ? 'warning'
                      : 'easy'
                  }
                  className="text-2xs"
                >
                  {(reviewQueue?.due_today || 0) > 0 ? `${reviewQueue.due_today} Due` : 'Caught Up'}
                </Badge>
              </div>

              {/* Review metrics preview */}
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-raised p-2.5">
                  <div className="text-2xs text-muted">Due Today</div>
                  <div className="text-lg font-bold text-ink">{reviewQueue?.due_today || 0}</div>
                </div>
                <div className="rounded-lg bg-raised p-2.5">
                  <div className="text-2xs text-muted">Overdue</div>
                  <div className={`text-lg font-bold ${(reviewQueue?.overdue || 0) > 0 ? 'text-hard-fg' : 'text-ink'}`}>
                    {reviewQueue?.overdue || 0}
                  </div>
                </div>
                <div className="rounded-lg bg-raised p-2.5">
                  <div className="text-2xs text-muted">Total Cards</div>
                  <div className="text-lg font-bold text-ink">{reviewQueue?.total || 0}</div>
                </div>
              </div>

              {/* Queue Items */}
              {reviewQueue?.items && reviewQueue.items.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <div className="text-2xs font-semibold text-muted uppercase tracking-wider">
                    Upcoming Items
                  </div>
                  {reviewQueue.items.slice(0, 3).map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-lg border border-line bg-surface/50 p-2.5 text-xs"
                    >
                      <span className="font-mono text-2xs text-ink">{item.topic_tag}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-2xs text-muted">Streak: {item.streak || 0}</span>
                        {item.is_overdue && (
                          <Badge tone="danger" className="text-[9px]">Overdue</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-6 text-center text-xs text-muted">
                  No pending reviews in your spaced-repetition queue.
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
