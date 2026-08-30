/**
 * Achievements - OWNER: Member 4. See plan.md 9.4.
 *
 * Earned and locked badges with progress.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Achievements() {
  return (
    <div>
      <PageHeader title="Achievements" subtitle="Owned by Member 4 - plan.md 9.4" />
      <EmptyState
        title="Not built yet"
        description="Earned and locked badges with progress."
      />
    </div>
  );
}
