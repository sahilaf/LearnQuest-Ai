/**
 * ForgotPassword - OWNER: Member 3. See plan.md 8.4.
 *
 * Firebase password reset.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function ForgotPassword() {
  return (
    <div>
      <PageHeader title="ForgotPassword" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Firebase password reset."
      />
    </div>
  );
}
