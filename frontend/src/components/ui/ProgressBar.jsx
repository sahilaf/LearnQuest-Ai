/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

/** Thin, flat meter. Used for solve % and course completion. */
const TONES = {
  primary: 'bg-primary-600',
  easy: 'bg-easy',
  success: 'bg-easy',
  medium: 'bg-medium',
  hard: 'bg-hard',
  info: 'bg-info',
};

export default function ProgressBar({
  value = 0,
  max = 100,
  label,
  tone = 'primary',
  showValue = true,
  className = '',
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className={className}>
      {label && (
        <div className="mb-1 flex items-center justify-between">
          <span className="label">{label}</span>
          {showValue && <span className="text-xs font-medium text-body dark:text-white">{Math.round(pct)}%</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label || 'Progress'}
        className="h-1.5 w-full overflow-hidden rounded-pill bg-line dark:bg-[#242B35]"
      >
        <div
          className={`h-full rounded-pill transition-[width] duration-300 ${TONES[tone] ?? TONES.primary}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
