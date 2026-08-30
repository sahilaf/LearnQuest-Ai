/**
 * Leaderboard - OWNER: Member 4. See plan.md 9.6.
 *
 * Top 50 plus the caller's rank pinned. Respect leaderboard_opt_out.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Leaderboard() {
  return (
    <div>
      <PageHeader title="Leaderboard" subtitle="Owned by Member 4 - plan.md 9.6" />
      <EmptyState
        title="Not built yet"
        description="Top 50 plus the caller's rank pinned. Respect leaderboard_opt_out."
      />
    </div>
  );
}
