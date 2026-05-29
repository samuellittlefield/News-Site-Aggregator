import { ClimateEvent } from "../api/client";

const CATEGORY_STYLES: Record<string, { border: string; badge: string }> = {
  wildfires:    { border: "border-orange-800/50 hover:border-orange-600/70", badge: "bg-orange-950 text-orange-400 border-orange-800" },
  severeStorms: { border: "border-blue-800/50 hover:border-blue-600/70",   badge: "bg-blue-950 text-blue-400 border-blue-800" },
  floods:       { border: "border-cyan-800/50 hover:border-cyan-600/70",   badge: "bg-cyan-950 text-cyan-400 border-cyan-800" },
  tempExtremes: { border: "border-red-800/50 hover:border-red-600/70",     badge: "bg-red-950 text-red-400 border-red-800" },
  drought:      { border: "border-yellow-800/50 hover:border-yellow-600/70", badge: "bg-yellow-950 text-yellow-500 border-yellow-800" },
};

interface Props {
  event: ClimateEvent;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

export function ClimateCard({ event }: Props) {
  const styles = CATEGORY_STYLES[event.category] ?? CATEGORY_STYLES.severeStorms;

  return (
    <div className={`flex-shrink-0 w-64 bg-gray-900 border ${styles.border} rounded-xl p-4 flex flex-col gap-3 transition-colors`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <span className={`text-xs font-semibold border rounded-full px-2 py-0.5 ${styles.badge} flex items-center gap-1`}>
          <span>{event.category_icon}</span>
          <span>{event.category_label}</span>
        </span>
        {event.start_date && (
          <span className="text-xs text-gray-600 shrink-0">{formatDate(event.start_date)}</span>
        )}
      </div>

      {/* Title */}
      <p className="text-sm font-semibold text-white leading-snug line-clamp-2">
        {event.title}
      </p>

      {/* AI summary */}
      {event.ai_summary && (
        <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">
          {event.ai_summary}
        </p>
      )}

      {/* Magnitude + source */}
      <div className="flex items-center justify-between mt-auto pt-1">
        {event.magnitude ? (
          <span className="text-xs text-gray-500">
            {event.magnitude} {event.magnitude_unit}
          </span>
        ) : (
          <span />
        )}
        {event.source_url && (
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-500 hover:text-blue-400 transition-colors"
          >
            Source →
          </a>
        )}
      </div>
    </div>
  );
}
