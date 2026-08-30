/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

const TONES = {
  default: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  primary: 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-200',
  success: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200',
  warning: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200',
  danger: 'bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200',
};

export default function Badge({ tone = 'default', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
