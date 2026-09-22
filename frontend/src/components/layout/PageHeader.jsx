/** Consistent page title block. OWNER: Member 2. */

/**
 * The title is set in the display serif. That one choice does most of the work
 * separating this from a generic admin template: an editorial face at 30px
 * against the neutral UI sans reads as a designed product rather than a
 * bootstrapped dashboard.
 *
 * `eyebrow` is the mono micro-label above the title - use it for the section a
 * page belongs to ("LEARN", "PRACTICE"), not for a restatement of the title.
 */
export default function PageHeader({ title, subtitle, eyebrow, action }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-line pb-6">
      <div className="min-w-0">
        {eyebrow && <p className="label mb-2">{eyebrow}</p>}
        <h1 className="display text-3xl sm:text-4xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-prose text-base text-muted">{subtitle}</p>}
      </div>
      {action && <div className="flex shrink-0 flex-wrap items-center gap-2.5">{action}</div>}
    </div>
  );
}
