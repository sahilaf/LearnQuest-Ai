/** Shared UI kit. OWNER: Member 2. Everyone imports these - plan.md 4.5. */

/**
 * `underline` (default) is the primary navigation pattern for dense screens.
 * `pills` is a compact segmented control for filters.
 * See docs/DESIGN_GUIDELINES.md.
 */
export default function Tabs({ tabs = [], activeTab, onChange, variant = 'underline', className = '' }) {
  const labelOf = (t) => t.label ?? t.title ?? (t.id ?? t.value);

  const countOf = (tab, isActive) =>
    tab.badge !== undefined && (
      <span
        className={`rounded px-1.5 py-0.5 text-2xs font-medium ${
          isActive ? 'bg-primary-50 text-primary-700'
                   : 'bg-canvas text-muted'
        }`}
      >
        {tab.badge}
      </span>
    );

  if (variant === 'pills') {
    return (
      <div role="tablist" className={`inline-flex rounded border border-line-strong bg-surface p-0.5 ${className}`}>
        {tabs.map((tab) => {
          const id = tab.id ?? tab.value;
          const isActive = id === activeTab;
          return (
            <button
              key={id}
              role="tab"
              type="button"
              aria-selected={isActive}
              onClick={() => onChange?.(id)}
              className={`inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive ? 'bg-primary-600 text-white' : 'text-muted hover:text-body'
              }`}
            >
              {tab.icon && <span>{tab.icon}</span>}
              {labelOf(tab)}
              {countOf(tab, isActive)}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div role="tablist" className={`flex gap-1 border-b border-line ${className}`}>
      {tabs.map((tab) => {
        const id = tab.id ?? tab.value;
        const isActive = id === activeTab;
        return (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={isActive}
            onClick={() => onChange?.(id)}
            className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-muted hover:border-line-strong hover:text-body'
            }`}
          >
            {tab.icon && <span>{tab.icon}</span>}
            {labelOf(tab)}
            {countOf(tab, isActive)}
          </button>
        );
      })}
    </div>
  );
}
