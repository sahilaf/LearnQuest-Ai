/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

// Status chips: quiet tinted text, never heavy solid blocks. Difficulty tones
// map 1:1 to the words users read. See docs/DESIGN_GUIDELINES.md.
const TONES = {
  default: 'bg-canvas text-muted dark:bg-[#1C222B] dark:text-[#8A94A2]',
  neutral: 'bg-canvas text-muted dark:bg-[#1C222B] dark:text-[#8A94A2]',
  primary: 'bg-primary-50 text-primary-700 dark:bg-primary-900/25 dark:text-primary-300',
  info: 'bg-info-bg text-info-fg dark:bg-info/15 dark:text-info',

  // Difficulty. `success` is an alias for `easy` - same green, different
  // meaning (passed vs low difficulty), and both are used in the app.
  easy: 'bg-easy-bg text-easy-fg dark:bg-easy/15 dark:text-easy',
  success: 'bg-easy-bg text-easy-fg dark:bg-easy/15 dark:text-easy',
  medium: 'bg-medium-bg text-medium-fg dark:bg-medium/15 dark:text-medium',
  warning: 'bg-medium-bg text-medium-fg dark:bg-medium/15 dark:text-medium',
  hard: 'bg-hard-bg text-hard-fg dark:bg-hard/15 dark:text-hard',
  danger: 'bg-hard-bg text-hard-fg dark:bg-hard/15 dark:text-hard',
};

export default function Badge({ tone = 'default', children, className = '' }) {
  return <span className={`chip ${TONES[tone] ?? TONES.default} ${className}`}>{children}</span>;
}
