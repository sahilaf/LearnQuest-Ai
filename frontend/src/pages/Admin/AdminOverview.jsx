/**
 * AdminOverview - OWNER: Member 3. See plan.md 8.4.
 *
 * Counts and charts. M4 supplies the chart components.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function AdminOverview() {
  return (
    <div>
      <PageHeader title="AdminOverview" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Counts and charts. M4 supplies the chart components."
      />
    </div>
  );
}
