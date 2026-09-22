/**
 * RoadmapPage - OWNER: Member 1.
 *
 * The AI-generated quest map: a personalised learning path built from the
 * student's goal and their current topic mastery, rendered as a chain of
 * unlockable quests.
 *
 * The roadmap is a DAG, but it is drawn as a single vertical path because that
 * is how students read a plan. Each node shows what unlocks it, so branching
 * prerequisites stay legible without a graph canvas.
 *
 * Styling follows docs/DESIGN_GUIDELINES.md.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Sparkles,
  Lock,
  Check,
  Play,
  Zap,
  Clock,
  RefreshCw,
  Target,
  Compass,
  AlertCircle,
} from 'lucide-react';

import {
  myRoadmap,
  generateRoadmap,
  completeNode,
  replanRoadmap,
} from '../../api/roadmap';
import PageHeader from '../../components/layout/PageHeader';
import { Badge, Button, Card, ProgressBar, Spinner } from '../../components/ui';

const GOAL_PRESETS = [
  'Become backend-ready in 8 weeks',
  'Get confident with databases and SQL',
  'Learn enough Python to build a project',
  'Prepare for a technical interview',
];

function errorText(err) {
  // api/client.js normalises rejections to { status, detail, code }.
  const { status, detail, code } = err || {};
  if (status === 401 || status === 403) return 'Your session expired. Sign in again.';
  if (status === 0 || code === 'NETWORK_ERROR') {
    return 'Could not reach the server. Check that the backend is running.';
  }
  return detail || `Request failed (${status ?? 'unknown'}).`;
}

/* ------------------------------------------------------------------ *
 * A single quest in the path
 * ------------------------------------------------------------------ */
function QuestNode({ node, index, isLast, onComplete, busy }) {
  const { status } = node;

  const ring = {
    completed: 'bg-easy border-easy text-white',
    available: 'bg-primary-600 border-primary-700 text-white',
    locked: 'bg-line border-line text-faint',
  }[status];

  return (
    <li className="relative flex gap-4">
      {/* Spine: the connector between quests */}
      <div className="flex flex-col items-center">
        <span
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-b-4 text-base font-semibold ${ring}`}
        >
          {status === 'completed' ? (
            <Check className="h-6 w-6" strokeWidth={3} />
          ) : status === 'locked' ? (
            <Lock className="h-5 w-5" />
          ) : (
            index + 1
          )}
        </span>
        {!isLast && (
          <span
            className={`w-1 flex-1 rounded-pill ${
              status === 'completed' ? 'bg-easy' : 'bg-line'
            }`}
          />
        )}
      </div>

      <Card
        className={`mb-5 flex-1 ${status === 'locked' ? 'opacity-70' : ''} ${
          status === 'available' ? 'border-primary-300' : ''
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{node.topic_tag}</Badge>
              {status === 'available' && <Badge tone="primary">Next up</Badge>}
              {status === 'completed' && <Badge tone="easy">Done</Badge>}
            </div>

            <h3 className="text-lg font-semibold leading-snug">{node.title}</h3>
            {node.summary && (
              <p className="mt-1.5 text-sm font-semibold leading-relaxed text-muted">
                {node.summary}
              </p>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-semibold uppercase tracking-wide text-muted">
              <span className="inline-flex items-center gap-1.5">
                <Zap className="h-4 w-4 text-medium-fg" />
                {node.xp_reward} XP
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-4 w-4" />
                {node.estimated_minutes} min
              </span>
            </div>

            {/* Makes the DAG legible without drawing a graph */}
            {status === 'locked' && node.blocked_by?.length > 0 && (
              <p className="mt-3 text-xs font-bold text-faint">
                Unlocks after: {node.blocked_by.join(', ')}
              </p>
            )}
          </div>

          <div className="flex shrink-0 flex-col gap-2">
            {node.lesson_id && status !== 'locked' && (
              <Link to={`/lessons/${node.lesson_id}`}>
                <Button size="sm" variant={status === 'completed' ? 'secondary' : 'primary'}>
                  <Play className="h-4 w-4" />
                  {status === 'completed' ? 'Review' : 'Start'}
                </Button>
              </Link>
            )}
            {status === 'available' && (
              <Button
                size="sm"
                variant="success"
                loading={busy}
                onClick={() => onComplete(node)}
              >
                <Check className="h-4 w-4" />
                Complete
              </Button>
            )}
          </div>
        </div>
      </Card>
    </li>
  );
}

/* ------------------------------------------------------------------ *
 * Goal form, shown when the student has no roadmap yet
 * ------------------------------------------------------------------ */
function GoalForm({ onGenerate, generating, error }) {
  const [goal, setGoal] = useState('');
  const [weeks, setWeeks] = useState(8);

  return (
    <Card className="mx-auto max-w-2xl p-7">
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-lg bg-primary-100 text-primary-900">
        <Compass className="h-7 w-7" />
      </div>

      <h2 className="text-2xl font-semibold">What do you want to achieve?</h2>
      <p className="mt-2 font-semibold leading-relaxed text-muted">
        Describe your goal and Nova will build a personalised quest path from the
        real lessons in the catalogue — ordered around what you already know.
      </p>

      <form
        className="mt-6 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (goal.trim()) onGenerate(goal.trim(), weeks);
        }}
      >
        <div>
          <label
            htmlFor="goal"
            className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted"
          >
            Your goal
          </label>
          <textarea
            id="goal"
            rows={2}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. Become backend-ready in 8 weeks"
            className="field resize-none"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          {GOAL_PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => setGoal(preset)}
              className="rounded-pill border-2 border-line px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:border-primary-300 hover:bg-primary-50 hover:text-primary-800"
            >
              {preset}
            </button>
          ))}
        </div>

        <div>
          <label
            htmlFor="weeks"
            className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted"
          >
            Time available: {weeks} weeks
          </label>
          <input
            id="weeks"
            type="range"
            min={1}
            max={24}
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            className="w-full accent-primary-600"
          />
        </div>

        {error && (
          <div className="rounded-lg border-2 border-hard/40 bg-hard-bg p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-hard-fg">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </p>
          </div>
        )}

        <Button type="submit" size="lg" loading={generating} disabled={!goal.trim()} className="w-full">
          <Sparkles className="h-5 w-5" />
          {generating ? 'Planning your path' : 'Build my roadmap'}
        </Button>
      </form>
    </Card>
  );
}

/* ------------------------------------------------------------------ *
 * Page
 * ------------------------------------------------------------------ */
export default function RoadmapPage() {
  const [roadmap, setRoadmap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [busyNode, setBusyNode] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    myRoadmap()
      .then((res) => {
        if (!cancelled) setRoadmap(res?.roadmap ?? null);
      })
      .catch((err) => {
        if (!cancelled) setError(errorText(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => load(), [load]);

  const handleGenerate = async (goal, weeks) => {
    setGenerating(true);
    setError(null);
    try {
      const res = await generateRoadmap(goal, weeks);
      setRoadmap(res?.roadmap ?? null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleComplete = async (node) => {
    setBusyNode(node.id);
    setError(null);
    try {
      const res = await completeNode(node.id);
      setRoadmap(res?.roadmap ?? null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyNode(null);
    }
  };

  const handleReplan = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await replanRoadmap();
      setRoadmap(res?.roadmap ?? null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Spinner size="lg" label="Loading your roadmap" />
      </div>
    );
  }

  if (!roadmap) {
    return (
      <div>
        <PageHeader
          title="Your quest path"
          subtitle="An AI-built roadmap through the catalogue, personalised to your goal and what you already know."
        />
        <GoalForm onGenerate={handleGenerate} generating={generating} error={error} />
      </div>
    );
  }

  const { progress, nodes } = roadmap;

  return (
    <div>
      <PageHeader
        title="Your quest path"
        subtitle={roadmap.goal}
        action={
          <Button variant="secondary" size="sm" loading={generating} onClick={handleReplan}>
            <RefreshCw className="h-4 w-4" />
            Re-plan
          </Button>
        }
      />

      {/* Progress summary */}
      <Card className="mb-7">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary-100 text-primary-900">
              <Target className="h-6 w-6" />
            </span>
            <div>
              <p className="text-2xl font-semibold leading-none">
                {progress.completed}
                <span className="text-muted">/{progress.total}</span>
              </p>
              <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted">
                Quests complete
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-medium-bg text-medium-fg">
              <Zap className="h-6 w-6" />
            </span>
            <div>
              <p className="text-2xl font-semibold leading-none">{progress.xp_earned}</p>
              <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted">
                of {progress.xp_available} XP
              </p>
            </div>
          </div>

          <div className="min-w-[200px] flex-1">
            <ProgressBar
              value={progress.completed}
              max={progress.total}
              label="Path progress"
              tone={progress.percent === 100 ? 'easy' : 'primary'}
            />
          </div>
        </div>

        {/* Be honest about how the plan was produced. */}
        {roadmap.generated_by === 'fallback' && (
          <p className="mt-4 flex items-center gap-2 rounded-xl bg-medium-bg px-3 py-2 text-xs font-bold text-medium-fg">
            <AlertCircle className="h-4 w-4 shrink-0" />
            The AI planner was unavailable, so this path follows the standard
            curriculum order. Re-plan to try again.
          </p>
        )}
      </Card>

      {error && (
        <div className="mb-6 rounded-lg border-2 border-hard/40 bg-hard-bg p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-hard-fg">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </p>
        </div>
      )}

      <ol className="list-none">
        {nodes.map((node, i) => (
          <QuestNode
            key={node.id}
            node={node}
            index={i}
            isLast={i === nodes.length - 1}
            onComplete={handleComplete}
            busy={busyNode === node.id}
          />
        ))}
      </ol>

      {progress.percent === 100 && (
        <Card className="mt-2 border-easy bg-easy text-center">
          <h3 className="text-xl font-semibold text-easy">
            Path complete — {progress.xp_earned} XP earned
          </h3>
          <p className="mt-2 font-semibold text-muted">
            Set a new goal to keep going.
          </p>
          <div className="mt-5 flex justify-center">
            <Button onClick={handleReplan} loading={generating}>
              <Sparkles className="h-4 w-4" />
              Plan what&apos;s next
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
