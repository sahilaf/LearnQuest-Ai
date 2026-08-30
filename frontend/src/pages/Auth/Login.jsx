/**
 * Login - OWNER: Member 3. See plan.md 8.4.
 *
 * Email/password + Google sign-in.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function Login() {
  return (
    <div>
      <PageHeader title="Login" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Email/password + Google sign-in."
      />
    </div>
  );
}
