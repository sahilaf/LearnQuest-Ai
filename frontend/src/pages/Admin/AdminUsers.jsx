/**
 * AdminUsers - OWNER: Member 3. See plan.md 8.4.
 *
 * Users table: search, filter by role, change role.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function AdminUsers() {
  return (
    <div>
      <PageHeader title="AdminUsers" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Users table: search, filter by role, change role."
      />
    </div>
  );
}
