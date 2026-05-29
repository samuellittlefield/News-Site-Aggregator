import { Trend } from "../api/client";

const SOURCE_TAG_STYLES: Record<string, { label: string; cls: string }> = {
  google_4h:    { label: "⚡4h",  cls: "bg-amber-950 text-amber-400 border-amber-800" },
  google_24h:   { label: "G24h", cls: "bg-blue-950 text-blue-400 border-blue-800" },
  nyt_shared:   { label: "NYT↑", cls: "bg-gray-800 text-gray-200 border-gray-600" },
  nyt_emailed:  { label: "NYT✉", cls: "bg-gray-800 text-gray-200 border-gray-600" },
  nyt_home:     { label: "NYT",  cls: "bg-gray-800 text-gray-200 border-gray-600" },
  nyt_us:       { label: "NYT",  cls: "bg-gray-800 text-gray-200 border-gray-600" },
  nyt_world:    { label: "NYT",  cls: "bg-gray-800 text-gray-200 border-gray-600" },
  wikipedia:    { label: "W",    cls: "bg-gray-800 text-gray-300 border-gray-600" },
  reddit:       { label: "R",    cls: "bg-orange-950 text-orange-400 border-orange-800" },
  nyt:          { label: "NYT",  cls: "bg-gray-800 text-gray-200 border-gray-600" },
};

function dedupeSources(sources: string[]): string[] {
  // Collapse multiple nyt_* into one "NYT" tag
  const hasNyt = sources.some(s => s.startsWith("nyt"));
  const nonNyt = sources.filter(s => !s.startsWith("nyt"));
  return hasNyt ? [...nonNyt, "nyt_home"] : nonNyt;
}

const CATEGORY_STYLES: Record<string, string> = {
  Sports:        "bg-green-950 text-green-400 border-green-800",
  Politics:      "bg-red-950 text-red-400 border-red-800",
  Entertainment: "bg-purple-950 text-purple-400 border-purple-800",
  Technology:    "bg-blue-950 text-blue-400 border-blue-800",
  Business:      "bg-yellow-950 text-yellow-500 border-yellow-800",
  Crime:         "bg-orange-950 text-orange-400 border-orange-800",
  Science:       "bg-teal-950 text-teal-400 border-teal-800",
  Culture:       "bg-pink-950 text-pink-400 border-pink-800",
  Other:         "bg-gray-800 text-gray-400 border-gray-700",
};

interface Props {
  trend: Trend;
  onClick: () => void;
}

export function TrendCard({ trend, onClick }: Props) {
  const preview = trend.summary?.body
    ? trend.summary.body.slice(0, 100) + (trend.summary.body.length > 100 ? "…" : "")
    : null;

  const wiki = trend.wiki_pages.find((w) => w.is_primary) ?? trend.wiki_pages[0] ?? null;

  return (
    <button
      onClick={onClick}
      className="group text-left bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-all duration-150 flex flex-col gap-3"
    >
      {/* Header row: title + wiki thumbnail (if available) */}
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-semibold text-white text-lg leading-snug group-hover:text-blue-400 transition-colors">
          {trend.title}
        </h2>

        {wiki ? (
          <a
            href={wiki.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            title={`Wikipedia: ${wiki.title}`}
            className="wiki-thumb shrink-0 relative rounded-lg overflow-hidden border border-gray-700 hover:border-blue-500 transition-colors"
            style={{ width: 52, height: 52 }}
          >
            {wiki.thumbnail_url ? (
              <img
                src={wiki.thumbnail_url}
                alt={wiki.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full bg-gray-800 flex items-center justify-center text-gray-500 text-xs font-bold">
                W
              </div>
            )}
            {/* "Wikipedia" label slides up on hover */}
            <span className="absolute inset-x-0 bottom-0 bg-blue-600/90 text-white text-[9px] font-semibold text-center py-0.5 translate-y-full group-[.wiki-thumb]:translate-y-0 transition-transform leading-tight opacity-0 hover:opacity-100">
              Wiki
            </span>
          </a>
        ) : trend.traffic_volume ? (
          <span className="shrink-0 text-xs font-medium bg-blue-950 text-blue-300 border border-blue-800 rounded-full px-2.5 py-0.5">
            {trend.traffic_volume}
          </span>
        ) : null}
      </div>

      {/* Traffic badge under title when wiki thumbnail is taking the badge slot */}
      {wiki && trend.traffic_volume && (
        <span className="self-start text-xs font-medium bg-blue-950 text-blue-300 border border-blue-800 rounded-full px-2.5 py-0.5">
          {trend.traffic_volume}
        </span>
      )}

      {preview && (
        <p className="text-sm text-gray-400 leading-relaxed line-clamp-3">{preview}</p>
      )}

      <div className="flex items-center flex-wrap gap-1.5 mt-auto">
        {/* Category badge */}
        {trend.category && (
          <span className={`text-xs font-medium border rounded-full px-2 py-0.5 ${CATEGORY_STYLES[trend.category] ?? CATEGORY_STYLES.Other}`}>
            {trend.category}
          </span>
        )}

        {/* Velocity indicator */}
        {(trend.rank_velocity > 0 || trend.velocity_abs > 0) && (
          <span className="text-xs font-semibold text-amber-400 flex items-center gap-0.5">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
            {trend.rank_velocity > 0
              ? `↑ ${trend.rank_velocity}`
              : trend.velocity_abs >= 1000
                ? `+${(trend.velocity_abs / 1000).toFixed(1)}K`
                : `+${trend.velocity_abs}`}
          </span>
        )}

        {/* Breaking indicator */}
        {trend.appearance_count === 1 && (
          <span className="flex items-center gap-1 text-xs font-semibold text-orange-400">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-orange-500" />
            </span>
            Breaking
          </span>
        )}

        <div className="flex items-center gap-1 ml-auto flex-wrap justify-end">
          {/* Multi-source attribution tags */}
          {dedupeSources(trend.sources_list ?? []).slice(0, 3).map(src => {
            const tag = SOURCE_TAG_STYLES[src];
            return tag ? (
              <span key={src} className={`text-[9px] font-bold border rounded px-1 py-0.5 ${tag.cls}`}>
                {tag.label}
              </span>
            ) : null;
          })}
          <span className="text-xs text-gray-600">
            {new Date(trend.fetched_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
      </div>
    </button>
  );
}
