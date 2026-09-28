/**
 * ForYouPanel - OWNER: Member 1. Rendered on the Dashboard.
 *
 * What to do next, and why. Three sources, loaded together:
 *
 *   next quest        the first available node on the student's AI roadmap.
 *                     The roadmap computed this all along (`next_node_key`,
 *                     commented "the UI leads with this") and nothing on the
 *                     first screen after login ever showed it - gap G3.
 *   recommendations   ranked lessons, each with the reason that ranked it.
 *   daily plan        today's time budget, filled with review first.
 *
 * Self-contained on purpose: it loads its own data rather than threading three
 * more requests through the Dashboard's, so dropping it in touches one line of
 * someone else's page. Each section fails independently - a missing roadmap
 * must not hide a working recommendation list.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, CalendarClock, Compass, Map as MapIcon } from 'lucide-react';

import RecommendationCard from './RecommendationCard';
import { Badge, Card, CardHeader, Spinner } from '../ui';
import { myRoadmap } from '../../api/roadmap';
import {
  dailyPlan,
  dismissRecommendation,
  listRecommendations,
} from '../../api/recommendations';

const KIND_LABEL = { revision: 'Review', lesson: 'Lesson', quiz: 'Quiz' };

function NextQuest({ roadmap }) {
  const next = roadmap?.nodes?.find((n) => n.node_key === roadmap?.progress?.next_node_key);

  if (!roadmap) {
    return (
      <Card>
        <CardHeader title="Your roadmap" subtitle="An AI-planned path from where you are to your goal." />
        <p className="mb-4 text-sm text-muted">You have not set a goal yet.</p>
        <Link to="/roadmap" className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-400 hover:text-primary-300">
          Plan my roadmap <ArrowRight className="h-4 w-4" />
        </Link>
      </Card>
    );
  }

  if (!next) {
    return (
      <Card>
        <CardHeader title="Your roadmap" subtitle={roadmap.goal} />
        <p className="text-sm text-muted">
          Every step is complete - {roadmap.progress?.xp_earned ?? 0} XP earned. Set a new goal on
          the roadmap page.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="label flex items-center gap-1.5">
          <MapIcon className="h-3.5 w-3.5" />
          Next on your roadmap
        </span>
        <Badge tone="primary">+{next.xp_reward} XP</Badge>
      </div>
      <h3 className="text-lg font-semibold text-ink">{next.title}</h3>
      {next.summary && <p className="mt-1.5 text-sm text-muted">{next.summary}</p>}
      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="text-sm text-faint">
          {roadmap.progress?.completed}/{roadmap.progress?.total} steps · {roadmap.progress?.percent}%
        </span>
        <Link
          to={next.lesson_id ? `/lessons/${next.lesson_id}` : '/roadmap'}
          className="inline-flex h-10 items-center gap-2 rounded bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-500"
        >
          Start <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </Card>
  );
}

function DailyPlan({ plan }) {
  if (!plan?.items?.length) return null;
  return (
    <Card>
      <CardHeader
        title="Today's plan"
        subtitle={`${plan.planned_minutes} of ${plan.minutes} minutes - review first, because that is what makes it stick.`}
      />
      <ol className="space-y-2">
        {plan.items.map((item, index) => (
          <li key={`${item.kind}-${index}`}>
            <Link
              to={item.link || '/dashboard'}
              className="row-interactive flex items-start gap-3 rounded-lg border border-line p-3"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-pill bg-raised font-mono text-xs text-muted">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="font-medium text-ink">{item.title}</span>
                  <Badge>{KIND_LABEL[item.kind] || item.kind}</Badge>
                </span>
                <span className="mt-0.5 block text-sm text-muted">{item.reason}</span>
              </span>
              <span className="shrink-0 font-mono text-xs text-faint">{item.minutes}m</span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export default function ForYouPanel() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [roadmap, setRoadmap] = useState(null);
  const [recs, setRecs] = useState([]);
  const [plan, setPlan] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([myRoadmap(), listRecommendations(), dailyPlan()])
      .then(([roadmapRes, recsRes, planRes]) => {
        if (roadmapRes.status === 'fulfilled') setRoadmap(roadmapRes.value?.roadmap ?? null);
        if (recsRes.status === 'fulfilled') setRecs(recsRes.value?.items ?? []);
        if (planRes.status === 'fulfilled') setPlan(planRes.value ?? null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const dismiss = (id) => {
    setRecs((current) => current.filter((r) => r.id !== id));
    dismissRecommendation(id).catch(() => {
      /* Hidden locally regardless; it will not be re-ranked for an hour. */
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <NextQuest roadmap={roadmap} />
        <DailyPlan plan={plan} />
      </div>

      {recs.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary-400" />
            <h2 className="text-lg font-semibold text-ink">Recommended for you</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {recs.map((rec) => (
              <RecommendationCard
                key={rec.id || rec.target_id}
                kind={rec.kind}
                title={rec.title}
                reason={rec.reason}
                onOpen={() => navigate(rec.link || `/lessons/${rec.target_id}`)}
                onDismiss={() => dismiss(rec.id)}
              />
            ))}
          </div>
        </div>
      )}

      {!recs.length && plan && !plan.items?.length && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <CalendarClock className="h-4 w-4" />
          Nothing is due right now. Take a quiz and the app will start planning around you.
        </p>
      )}
    </section>
  );
}
