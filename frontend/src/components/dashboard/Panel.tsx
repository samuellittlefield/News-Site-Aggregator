import { ReactNode } from "react";

interface Props {
  title: string;
  icon?: string;
  /** Small text on the right of the title row (e.g. a count or freshness) */
  meta?: string | null;
  /** Status dot color class, e.g. "bg-emerald-500" */
  dot?: string;
  onOpen?: () => void;
  className?: string;
  children: ReactNode;
}

export function Panel({ title, icon, meta, dot, onOpen, className = "", children }: Props) {
  return (
    <section
      onClick={onOpen}
      className={`bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col min-h-0 ${
        onOpen ? "cursor-pointer hover:border-gray-600 transition-colors" : ""
      } ${className}`}
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
          {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />}
          {icon && <span className="text-sm leading-none">{icon}</span>}
          {title}
        </h2>
        <div className="flex items-center gap-1.5 text-xs text-gray-600">
          {meta}
          {onOpen && (
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          )}
        </div>
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </section>
  );
}
