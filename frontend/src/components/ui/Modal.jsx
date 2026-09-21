/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

import { useEffect } from 'react';

const SIZES = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

export default function Modal({
  open,
  onClose,
  title,
  size = 'md',
  className = '',
  children,
  footer,
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/40 transition-opacity" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`card relative z-10 w-full ${SIZES[size] ?? SIZES.md} animate-fade-in p-5 shadow-modal ${className}`}
      >
        {title && <h2 className="mb-3 border-b border-line pb-3 text-lg font-semibold dark:border-[#242B35]">{title}</h2>}
        <div className="text-sm text-body dark:text-[#C6CDD6]">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2 border-t border-line pt-4 dark:border-[#242B35]">{footer}</div>}
      </div>
    </div>
  );
}
