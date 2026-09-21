/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

import { forwardRef } from 'react';

const Select = forwardRef(function Select(
  { label, options = [], error, hint, className = '', id, children, ...props },
  ref
) {
  const selectId = id || props.name;
  const describedBy = error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined;

  return (
    <div className={className}>
      {label && (
        <label
          htmlFor={selectId}
          className="mb-1.5 block text-sm font-medium text-body dark:text-[#C6CDD6]"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {/* Native arrows differ per platform, so draw our own. */}
        <select
          ref={ref}
          id={selectId}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={describedBy}
          className={`field cursor-pointer appearance-none pr-9 ${
            error ? 'border-hard focus:border-hard focus:ring-hard/25' : ''
          }`}
          {...props}
        >
          {children ||
            options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
        </select>
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="none"
          className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
        >
          <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      {error && (
        <p id={`${selectId}-error`} className="mt-1.5 text-xs text-hard">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${selectId}-hint`} className="mt-1.5 text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
});

export default Select;
