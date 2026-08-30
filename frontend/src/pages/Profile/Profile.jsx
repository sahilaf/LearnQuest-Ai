/**
 * Profile - OWNER: Member 3. See plan.md 8.4.
 *
 * Name, avatar and preferences: tutor tone, daily goal, difficulty, timezone.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Profile() {
  return (
    <div>
      <PageHeader title="Profile" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Name, avatar and preferences: tutor tone, daily goal, difficulty, timezone."
      />
    </div>
  );
}
