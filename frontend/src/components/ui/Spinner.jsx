/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function Spinner({ size = 'md', label = 'Loading' }) {
  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-10 w-10' };
  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-block animate-spin rounded-full border-2 border-primary-600 border-t-transparent ${sizes[size]}`}
    />
  );
}
