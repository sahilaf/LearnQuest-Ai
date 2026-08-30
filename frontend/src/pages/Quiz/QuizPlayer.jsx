/**
 * QuizPlayer - OWNER: Member 2. See plan.md 7.2.
 *
 * One question per screen, timer, answers persist across refresh.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function QuizPlayer() {
  return (
    <div>
      <PageHeader title="QuizPlayer" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="One question per screen, timer, answers persist across refresh."
      />
    </div>
  );
}
