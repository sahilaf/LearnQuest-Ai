/**
 * CourseDetail - OWNER: Member 2. See plan.md 7.2.
 *
 * Lesson list with completion ticks, progress ring, continue-where-you-left-off.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function CourseDetail() {
  return (
    <div>
      <PageHeader title="CourseDetail" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="Lesson list with completion ticks, progress ring, continue-where-you-left-off."
      />
    </div>
  );
}
