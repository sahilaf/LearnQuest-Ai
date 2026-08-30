/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function Select({ label, options = [], className = '', id, ...props }) {
  const selectId = id || props.name;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={selectId} className="mb-1.5 block text-sm font-medium">
          {label}
        </label>
      )}
      <select
        id={selectId}
        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
