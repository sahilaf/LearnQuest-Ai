/**
 * Register - OWNER: Member 3. See plan.md 8.4.
 *
 * Create an account.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Register() {
  return (
    <div>
      <PageHeader title="Register" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Create an account."
      />
    </div>
  );
}
