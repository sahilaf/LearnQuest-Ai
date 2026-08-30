/**
 * LessonViewer - OWNER: Member 2. See plan.md 7.2.
 *
 * Markdown + video, prev/next, sticky outline, 'Ask the tutor about this' selection hook, 30s heartbeat, auto-complete at 90% scroll.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function LessonViewer() {
  return (
    <div>
      <PageHeader title="LessonViewer" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="Markdown + video, prev/next, sticky outline, 'Ask the tutor about this' selection hook, 30s heartbeat, auto-complete at 90% scroll."
      />
    </div>
  );
}
