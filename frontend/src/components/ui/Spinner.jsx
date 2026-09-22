/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function Spinner({ size = 'md', label = 'Loading' }) {
  const sizes = { sm: 'h-4 w-4 border-2', md: 'h-6 w-6 border-2', lg: 'h-8 w-8 border-[3px]' };
  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-block animate-spin rounded-full border-line border-t-primary-600 ${sizes[size] ?? sizes.md}`}
    />
  );
}
