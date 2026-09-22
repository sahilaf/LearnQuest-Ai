/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

// Status chips: tinted text on a deep, low-chroma backing - never heavy solid
// blocks. Difficulty tones map 1:1 to the words users read.
// See docs/DESIGN_GUIDELINES.md.
const TONES = {
  default: 'bg-raised text-muted',
  neutral: 'bg-raised text-muted',
  primary: 'bg-primary-500/15 text-primary-300',
  info: 'bg-info-bg text-info-fg',

  // Difficulty & status. `success` is an alias for `easy` - same green,
  // different meaning (passed vs low difficulty). Both are used in the app;
  // collapsing them to one key is what caused the duplicate-key bug.
  easy: 'bg-easy-bg text-easy-fg',
  success: 'bg-easy-bg text-easy-fg',
  medium: 'bg-medium-bg text-medium-fg',
  warning: 'bg-medium-bg text-medium-fg',
  hard: 'bg-hard-bg text-hard-fg',
  danger: 'bg-hard-bg text-hard-fg',
};

export default function Badge({ tone = 'default', children, className = '' }) {
  return <span className={`chip ${TONES[tone] ?? TONES.default} ${className}`}>{children}</span>;
}
