/**
 * CourseCatalog - OWNER: Member 2. See plan.md 7.2.
 *
 * Grid with search and subject/difficulty filters.
 */
import PageHeader from '../../components/layout/PageHeader';
import { EmptyState } from '../../components/ui';

export default function CourseCatalog() {
  return (
    <div>
      <PageHeader title="CourseCatalog" subtitle="Owned by Member 2 - plan.md 7.2" />
      <EmptyState
        title="Not built yet"
        description="Grid with search and subject/difficulty filters."
      />
    </div>
  );
}
