/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

/**
 * Flat, compact button. See docs/DESIGN_GUIDELINES.md.
 *
 * This system has no "3D" or novelty buttons: depth comes from a 1px border and
 * a hover state, nothing more. One primary button per view; everything else is
 * secondary or ghost.
 */
import { forwardRef } from 'react';

const VARIANTS = {
  primary:
    'bg-primary-600 text-white border border-primary-600 hover:bg-primary-700 hover:border-primary-700 active:bg-primary-800',
  secondary:
    'bg-surface text-body border border-line-strong hover:bg-canvas hover:border-muted active:bg-line/60 '
    + 'dark:bg-[#171C23] dark:text-[#C6CDD6] dark:border-[#2D3643] dark:hover:bg-[#1C222B]',
  easy:
    'bg-easy text-white border border-easy hover:brightness-95 active:brightness-90',
  success:
    'bg-easy text-white border border-easy hover:brightness-95 active:brightness-90',
  danger:
    'bg-hard text-white border border-hard hover:brightness-95 active:brightness-90',
  ghost:
    'bg-transparent text-muted border border-transparent hover:bg-canvas hover:text-body '
    + 'dark:hover:bg-[#1C222B] dark:hover:text-white',
  link:
    'bg-transparent text-primary-600 border border-transparent hover:underline p-0 h-auto dark:text-primary-400',
};

const SIZES = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-1.5',
  lg: 'h-10 px-4 text-base gap-2',
};

const Button = forwardRef(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    disabled = false,
    className = '',
    children,
    ...props
  },
  ref
) {
  const isLink = variant === 'link';
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded font-medium
        transition-colors disabled:cursor-not-allowed disabled:opacity-50
        ${VARIANTS[variant] ?? VARIANTS.primary} ${isLink ? '' : (SIZES[size] ?? SIZES.md)} ${className}`}
      {...props}
    >
      {loading && (
        <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
});

export default Button;
