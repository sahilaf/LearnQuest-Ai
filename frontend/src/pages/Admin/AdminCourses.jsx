/**
 * AdminCourses - OWNER: Member 3. See plan.md 8.4.
 *
 * Course table plus the editor: markdown preview, lesson reorder, tag picker.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function AdminCourses() {
  return (
    <div>
      <PageHeader title="AdminCourses" subtitle="Owned by Member 3 - plan.md 8.4" />
      <EmptyState
        title="Not built yet"
        description="Course table plus the editor: markdown preview, lesson reorder, tag picker."
      />
    </div>
  );
}
