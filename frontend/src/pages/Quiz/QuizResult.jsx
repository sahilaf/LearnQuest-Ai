/**
 * QuizResult - OWNER: Member 2. See plan.md 7.2.
 *
 * Score plus per-question explanations, retake.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function QuizResult() {
  return (
    <div>
      <PageHeader title="QuizResult" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="Score plus per-question explanations, retake."
      />
    </div>
  );
}
