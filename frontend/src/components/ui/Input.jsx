/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

export default function Input({ label, error, className = '', id, ...props }) {
  const inputId = id || props.name;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full rounded-xl border px-3 py-2 text-sm transition-colors
          dark:bg-slate-800 ${error ? 'border-rose-500' : 'border-slate-300 dark:border-slate-700'}`}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-rose-500">{error}</p>}
    </div>
  );
}
