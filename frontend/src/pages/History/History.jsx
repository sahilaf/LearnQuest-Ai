/**
 * History - OWNER: Member 2. See plan.md 7.2.
 *
 * Timeline of lessons and attempts, filter by course.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function History() {
  return (
    <div>
      <PageHeader title="History" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="Timeline of lessons and attempts, filter by course."
      />
    </div>
  );
}
