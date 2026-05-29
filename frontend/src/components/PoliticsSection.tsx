import { Trend, usePoliticalTrends } from "../api/client";

function heatLevel(t: Trend): { label: string; color: string; dot: string } {
  if (t.appearance_count === 1)
    return { label: "Breaking", color: "text-orange-400", dot: "bg-orange-500" };
  if (t.rank_velocity >= 3)
    return { label: `↑ ${t.rank_velocity} spots`, color: "text-amber-400", dot: "bg-amber-500" };
  if (t.rank_velocity > 0)
    return { label: "Rising", color: "text-yellow-400", dot: "bg-yellow-500" };
  if (t.appearance_count >= 6)
    return { label: "Sustained", color: "text-blue-400", dot: "bg-blue-500" };
  return { label: "Active", color: "text-gray-400", dot: "bg-gray-500" };
}

function PoliticalCard({ trend, onSelect }: { trend: Trend; onSelect: (id: number) => void }) {
  const heat = heatLevel(trend);

  return (
    <button
      onClick={() => onSelect(trend.id)}
      className="group flex-shrink-0 w-64 text-left bg-gray-900 border border-gray-800 hover:border-red-800/60 rounded-xl p-4 flex flex-col gap-3 transition-colors"
    >
      {/* Heat indicator + traffic */}
      <div className="flex items-center justify-between gap-2">
        <span className={`flex items-center gap-1.5 text-xs font-semibold ${heat.color}`}>
          <span className="relative flex h-1.5 w-1.5">
            {(trend.appearance_count === 1 || trend.rank_velocity > 0) && (
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${heat.dot} opacity-75`} />
            )}
            <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${heat.dot}`} />
          </span>
          {heat.label}
        </span>
        {trend.traffic_volume && (
          <span className="text-xs text-gray-500">{trend.traffic_volume}</span>
        )}
      </div>

      {/* Title */}
      <p className="text-sm font-semibold text-white group-hover:text-red-400 transition-colors leading-snug line-clamp-2">
        {trend.title}
      </p>

      {/* Summary preview */}
      {trend.summary && (
        <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed flex-1">
          {trend.summary.body}
        </p>
      )}

      {/* Metrics row */}
      <div className="flex items-center gap-3 text-xs text-gray-600 mt-auto pt-1 border-t border-gray-800">
        <span title="Trending for">
          ~{trend.appearance_count * 3}h
        </span>
        {trend.rank_velocity !== 0 && (
          <span className={trend.rank_velocity > 0 ? "text-amber-500" : "text-gray-600"}>
            {trend.rank_velocity > 0 ? `↑${trend.rank_velocity}` : `↓${Math.abs(trend.rank_velocity)}`} rank
          </span>
        )}
        {trend.wiki_pages.length > 0 && (
          <span className="text-blue-600 ml-auto">W</span>
        )}
      </div>
    </button>
  );
}

interface Props {
  onSelect: (id: number) => void;
}

export function PoliticsSection({ onSelect }: Props) {
  const { trends, loading } = usePoliticalTrends();

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-base">🏛</span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Politics</h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          trending activity · sorted by velocity
        </span>
      </div>

      {loading && (
        <div className="flex gap-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex-shrink-0 w-64 h-40 bg-gray-900 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!loading && trends.length === 0 && (
        <div className="text-sm text-gray-600 py-4">
          No political trending topics right now — check back soon.
        </div>
      )}

      {!loading && trends.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
          {trends.map(t => (
            <PoliticalCard key={t.id} trend={t} onSelect={onSelect} />
          ))}
        </div>
      )}
    </section>
  );
}
