/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

import { createContext, useCallback, useContext, useState } from 'react';

const ToastContext = createContext(null);

// Toasts are solid coloured blocks, not tinted cards - feedback in this
// system is loud and immediate. See docs/DESIGN_GUIDELINES.md.
// Bordered surfaces with a coloured left rule - informative, not celebratory.
const TOAST_TONES = {
  default: 'border-l-4 border-l-muted',
  primary: 'border-l-4 border-l-primary-600',
  easy: 'border-l-4 border-l-easy',
  success: 'border-l-4 border-l-easy',
  info: 'border-l-4 border-l-info',
  warning: 'border-l-4 border-l-medium',
  danger: 'border-l-4 border-l-hard',
  error: 'border-l-4 border-l-hard',
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const push = useCallback((message, tone = 'default', ms = 4000) => {
    const id = crypto.randomUUID();
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), ms);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-3">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`card pointer-events-auto animate-fade-in px-4 py-3 text-sm shadow-dropdown
              ${TOAST_TONES[t.tone] || TOAST_TONES.default}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      push: (message, tone = 'default') => {
        console.info(`[Toast ${tone}]: ${message}`);
      },
    };
  }
  return ctx;
}
