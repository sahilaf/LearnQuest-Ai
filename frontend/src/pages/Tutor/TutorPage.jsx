/**
 * TutorPage - OWNER: Member 1. See plan.md 6.7.
 *
 * Split view: AvatarStage left, ChatPanel right. Stacks on mobile.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function TutorPage() {
  return (
    <div>
      <PageHeader title="TutorPage" subtitle="Owned by Member 1 - plan.md 6.7" />
      <EmptyState
        title="Not built yet"
        description="Split view: AvatarStage left, ChatPanel right. Stacks on mobile."
      />
    </div>
  );
}
