/**
 * Dashboard - OWNER: Member 2. See plan.md 7.2.
 *
 * Assembles widgets from all four modules: progress (M2), XP/streak/challenges (M4), recommendations (M1).
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Dashboard() {
  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="Assembles widgets from all four modules: progress (M2), XP/streak/challenges (M4), recommendations (M1)."
      />
    </div>
  );
}
