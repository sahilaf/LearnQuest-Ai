/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

/**
 * A 1px-bordered surface. Depth comes from the border and a level change
 * (canvas -> surface -> raised), never from a drop shadow: on a near-black
 * canvas a shadow is invisible, so stacking them only adds mud.
 */
export default function Card({ className = '', interactive = false, children, ...props }) {
  return (
    <div
      className={`card ${interactive ? 'row-interactive cursor-pointer' : ''} p-5 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4 border-b border-line pb-4">
      <div className="min-w-0">
        <h3 className="text-lg font-semibold leading-tight text-ink">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
