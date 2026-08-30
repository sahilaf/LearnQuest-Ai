/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function EmptyState({ title, description, action, icon = null }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 p-10 text-center dark:border-slate-700">
      {icon && <div className="mb-3 text-slate-400">{icon}</div>}
      <h3 className="font-medium">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
