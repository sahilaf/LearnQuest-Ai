/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

import { forwardRef } from 'react';

const Input = forwardRef(function Input(
  { label, error, hint, className = '', id, ...props },
  ref
) {
  const inputId = id || props.name;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;

  return (
    <div className={className}>
      {label && (
        <label
          htmlFor={inputId}
          className="mb-1.5 block text-sm font-medium text-body dark:text-[#C6CDD6]"
        >
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={describedBy}
        className={`field ${
          error ? 'border-hard focus:border-hard focus:ring-hard/25' : ''
        }`}
        {...props}
      />
      {error && (
        <p id={`${inputId}-error`} className="mt-1.5 text-xs text-hard">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${inputId}-hint`} className="mt-1.5 text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
});

export default Input;
