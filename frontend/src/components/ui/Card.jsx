/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function Card({ className = '', children, ...props }) {
  return (
    <div className={`card p-5 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h3 className="font-semibold">{title}</h3>
        {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
