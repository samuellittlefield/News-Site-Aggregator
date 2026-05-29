import { ClimateEvent } from "../api/client";

const CATEGORY_STYLES: Record<string, { border: string; badge: string; glow: string }> = {
  wildfires:    { border: "border-orange-800/60 hover:border-orange-500/80", badge: "bg-orange-950 text-orange-400 border-orange-800", glow: "bg-orange-950/20" },
  severeStorms: { border: "border-blue-800/60 hover:border-blue-500/80",    badge: "bg-blue-950 text-blue-400 border-blue-800",    glow: "bg-blue-950/20" },
  floods:       { border: "border-cyan-800/60 hover:border-cyan-500/80",    badge: "bg-cyan-950 text-cyan-400 border-cyan-800",    glow: "bg-cyan-950/20" },
  tempExtremes: { border: "border-red-800/60 hover:border-red-500/80",      badge: "bg-red-950 text-red-400 border-red-800",      glow: "bg-red-950/20" },
  drought:      { border: "border-yellow-800/60 hover:border-yellow-500/80", badge: "bg-yellow-950 text-yellow-500 border-yellow-800", glow: "bg-yellow-950/20" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

interface Props {
  event: ClimateEvent;
}

export function ClimateCard({ event }: Props) {
  const styles = CATEGORY_STYLES[event.category] ?? CATEGORY_STYLES.severeStorms;

  return (
    <div className={`flex-shrink-0 w-64 bg-gray-900 border ${styles.border} rounded-xl overflow-hidden flex flex-col transition-colors`}>
      {/* Location banner */}
      {event.location && (
        <div className={`${styles.glow} border-b border-gray-800/60 px-4 py-2 flex items-center gap-1.5`}>
          <svg className="w-3 h-3 text-gray-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
          </svg>
          <span className="text-xs text-gray-400 truncate">{event.location}</span>
        </div>
      )}

      <div className="p-4 flex flex-col gap-3 flex-1">
        {/* Category + date */}
        <div className="flex items-center justify-between gap-2">
          <span className={`text-xs font-semibold border rounded-full px-2 py-0.5 ${styles.badge} flex items-center gap-1 shrink-0`}>
            <span>{event.category_icon}</span>
            <span>{event.category_label}</span>
          </span>
          {event.start_date && (
            <span className="text-xs text-gray-600">{formatDate(event.start_date)}</span>
          )}
        </div>

        {/* Title */}
        <p className="text-sm font-semibold text-white leading-snug line-clamp-2">
          {event.title}
        </p>

        {/* AI summary */}
        {event.ai_summary && (
          <p className="text-xs text-gray-400 leading-relaxed line-clamp-3 flex-1">
            {event.ai_summary}
          </p>
        )}

        {/* Magnitude + source */}
        <div className="flex items-center justify-between pt-1">
          {event.magnitude ? (
            <span className="text-xs text-gray-500">
              {event.magnitude.toLocaleString()} {event.magnitude_unit}
            </span>
          ) : <span />}
          {event.source_url && (
            <a href={event.source_url} target="_blank" rel="noopener noreferrer"
               className="text-xs text-blue-500 hover:text-blue-400 transition-colors">
              Source →
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
