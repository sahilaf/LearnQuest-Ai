/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function Skeleton({ className = 'h-4 w-full' }) {
  return (
    <div className={`relative overflow-hidden rounded bg-line ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-surface/40 to-transparent" />
    </div>
  );
}
