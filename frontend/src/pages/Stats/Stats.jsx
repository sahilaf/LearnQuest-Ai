/**
 * Stats - OWNER: Member 4. See plan.md 9.7.
 *
 * Activity chart, XP over time, mastery radar (data from M1), accuracy trend.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Stats() {
  return (
    <div>
      <PageHeader title="Stats" subtitle="Owned by Member 4 - plan.md 9.7" />
      <EmptyState
        title="Not built yet"
        description="Activity chart, XP over time, mastery radar (data from M1), accuracy trend."
      />
    </div>
  );
}
