/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

/**
 * Flat, solid button. See docs/DESIGN_GUIDELINES.md.
 *
 * Sizes were raised on 2026-09-22: the default was 32px tall, which is below
 * what a primary action should ever be on a desktop UI and well below the 44px
 * comfortable touch target on mobile. `md` is now 40px and `lg` is 48px.
 *
 * This system has no "3D" or novelty buttons. Depth is a fill, a border and a
 * hover state - nothing more. One primary button per view; everything else is
 * secondary or ghost.
 */
import { forwardRef } from 'react';

const VARIANTS = {
  primary:
    'bg-primary-600 text-white border border-primary-600 '
    + 'hover:bg-primary-500 hover:border-primary-500 active:bg-primary-700',
  secondary:
    'bg-raised text-ink border border-line-strong hover:border-muted hover:bg-line active:bg-raised',
  easy: 'bg-easy text-canvas border border-easy font-semibold hover:brightness-110 active:brightness-95',
  success:
    'bg-easy text-canvas border border-easy font-semibold hover:brightness-110 active:brightness-95',
  danger: 'bg-hard text-white border border-hard hover:brightness-110 active:brightness-95',
  ghost: 'bg-transparent text-muted border border-transparent hover:bg-raised hover:text-ink',
  link: 'bg-transparent text-primary-400 border border-transparent hover:text-primary-300 hover:underline p-0 h-auto',
};

const SIZES = {
  sm: 'h-9 px-3.5 text-sm gap-1.5',
  md: 'h-10 px-4 text-base gap-2',
  lg: 'h-12 px-6 text-lg gap-2.5',
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
        transition-colors disabled:cursor-not-allowed disabled:opacity-40
        ${VARIANTS[variant] ?? VARIANTS.primary} ${isLink ? '' : (SIZES[size] ?? SIZES.md)} ${className}`}
      {...props}
    >
      {loading && (
        <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
});

export default Button;
