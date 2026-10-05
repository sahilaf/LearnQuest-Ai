/**
 * Leaderboard - OWNER: Member 4.
 *
 * Ranked by XP. The caller's own row is always shown, pinned below the table
 * when they are outside the visible top, because a leaderboard that only shows
 * other people tells most learners nothing about themselves.
 *
 * Weekly by default: an all-time board is won by whoever joined first, and a
 * newcomer looking at it learns only that they cannot catch up.
 */
import { useCallback, useEffect, useState } from 'react';
import { Flame, Trophy } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import { Badge, Button, Card, EmptyState, Spinner } from '../../components/ui';
import { leaderboard } from '../../api/gamification';

const PERIODS = [
  { value: 'weekly', label: 'This week' },
  { value: 'all', label: 'All time' },
];

/** Gold, silver, bronze - the only place colour marks rank, not status. */
const MEDAL = {
  1: 'bg-medium-bg text-medium-fg',
  2: 'bg-raised text-body',
  3: 'bg-hard-bg text-hard-fg',
};

function RankCell({ rank }) {
  if (MEDAL[rank]) {
    return (
      <span className={`inline-flex h-8 w-8 items-center justify-center rounded-pill font-mono text-sm font-semibold ${MEDAL[rank]}`}>
        {rank}
      </span>
    );
  }
  return <span className="inline-flex h-8 w-8 items-center justify-center font-mono text-sm text-muted">{rank}</span>;
}

function Row({ entry, isMe }) {
  return (
    <tr className={isMe ? 'bg-primary-500/10' : 'row-interactive'}>
      <td className="w-16">
        <RankCell rank={entry.rank} />
      </td>
      <td>
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-raised text-xs font-semibold text-body">
            {(entry.name || '?').trim().slice(0, 2).toUpperCase()}
          </span>
          <span className="font-medium text-ink">{entry.name || 'Learner'}</span>
          {isMe && <Badge tone="primary">You</Badge>}
        </div>
      </td>
      <td className="hidden text-muted sm:table-cell">Level {entry.level}</td>
      <td className="hidden sm:table-cell">
        <span className="inline-flex items-center gap-1.5 text-muted">
          <Flame className="h-4 w-4 text-medium" />
          {entry.streak ?? 0}
        </span>
      </td>
      <td className="text-right font-mono font-semibold text-ink">{(entry.xp ?? 0).toLocaleString()}</td>
    </tr>
  );
}

export default function Leaderboard({ embedded = false }) {
  const [period, setPeriod] = useState('weekly');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    leaderboard({ period, scope: 'global' })
      .then(setData)
      .catch((err) => setError(err?.detail || 'Could not load the leaderboard.'))
      .finally(() => setLoading(false));
  }, [period]);

  useEffect(load, [load]);

  const items = data?.items || [];
  const me = data?.me;
  const meIsVisible = me && items.some((e) => e.user_id === me.user_id);

  return (
    <div>
      {!embedded ? (
        <PageHeader
          eyebrow="Compete"
          title="Leaderboard"
          subtitle="Ranked by XP. Every lesson and quiz counts."
          action={
            <div className="flex rounded-lg border border-line bg-surface p-1">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPeriod(p.value)}
                  className={`rounded px-3.5 py-1.5 text-sm font-medium transition-colors ${
                    period === p.value ? 'bg-primary-600 text-white' : 'text-muted hover:text-ink'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          }
        />
      ) : (
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-medium text-muted">Ranked by XP earned.</p>
          <div className="flex rounded-lg border border-line bg-surface p-1">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setPeriod(p.value)}
                className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                  period === p.value ? 'bg-primary-600 text-white' : 'text-muted hover:text-ink'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <EmptyState
          title="Leaderboard unavailable"
          description={error}
          action={<Button variant="secondary" size="sm" onClick={load}>Try again</Button>}
        />
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon={<Trophy className="h-5 w-5" />}
          title="No rankings yet"
          description="Rankings appear once learners start earning XP. Finish a lesson to get on the board."
        />
      )}

      {!loading && !error && items.length > 0 && (
        <Card className="overflow-hidden p-0">
          <table className="table-dense">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Learner</th>
                <th className="hidden sm:table-cell">Level</th>
                <th className="hidden sm:table-cell">Streak</th>
                <th className="text-right">XP</th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => (
                <Row key={entry.user_id} entry={entry} isMe={me && entry.user_id === me.user_id} />
              ))}
              {me && !meIsVisible && (
                <>
                  <tr>
                    <td colSpan={5} className="py-1 text-center text-faint">···</td>
                  </tr>
                  <Row entry={me} isMe />
                </>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
