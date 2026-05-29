import { Trend } from "../api/client";

const CATEGORY_STYLES: Record<string, { border: string; bg: string; text: string; back: string }> = {
  Sports:        { border: "border-green-700/70",  bg: "bg-gray-900", text: "text-green-400",  back: "border-green-900/50 bg-gray-900/80" },
  Politics:      { border: "border-red-700/70",    bg: "bg-gray-900", text: "text-red-400",    back: "border-red-900/50 bg-gray-900/80" },
  Entertainment: { border: "border-purple-700/70", bg: "bg-gray-900", text: "text-purple-400", back: "border-purple-900/50 bg-gray-900/80" },
  Technology:    { border: "border-blue-700/70",   bg: "bg-gray-900", text: "text-blue-400",   back: "border-blue-900/50 bg-gray-900/80" },
  Business:      { border: "border-yellow-700/70", bg: "bg-gray-900", text: "text-yellow-500", back: "border-yellow-900/50 bg-gray-900/80" },
  Crime:         { border: "border-orange-700/70", bg: "bg-gray-900", text: "text-orange-400", back: "border-orange-900/50 bg-gray-900/80" },
  Science:       { border: "border-teal-700/70",   bg: "bg-gray-900", text: "text-teal-400",   back: "border-teal-900/50 bg-gray-900/80" },
  Culture:       { border: "border-pink-700/70",   bg: "bg-gray-900", text: "text-pink-400",   back: "border-pink-900/50 bg-gray-900/80" },
  Other:         { border: "border-gray-600/70",   bg: "bg-gray-900", text: "text-gray-400",   back: "border-gray-700/50 bg-gray-900/80" },
};

interface ClusterData {
  id: number;
  name: string;
  category: string | null;
  trends: Trend[];
}

interface Props {
  cluster: ClusterData;
  onSelect: (id: number) => void;
}

export function ClusterStack({ cluster, onSelect }: Props) {
  const cat = cluster.category ?? "Other";
  const styles = CATEGORY_STYLES[cat] ?? CATEGORY_STYLES.Other;
  const stackDepth = Math.min(cluster.trends.length - 1, 2); // 1 or 2 back cards
  const topTrend = cluster.trends.reduce((a, b) =>
    (parseInt(a.traffic_volume ?? "0") >= parseInt(b.traffic_volume ?? "0") ? a : b)
  );

  return (
    // Outer container reserves space for the stack offset
    <div className="flex-shrink-0 w-64 group" style={{ paddingBottom: `${stackDepth * 6}px`, paddingRight: `${stackDepth * 6}px` }}>
      <div className="relative w-full h-52">

        {/* Back cards — physical stack depth */}
        {Array.from({ length: stackDepth }).map((_, i) => {
          const offset = (stackDepth - i) * 6;
          return (
            <div
              key={i}
              className={`absolute inset-0 rounded-xl border ${styles.back}`}
              style={{ transform: `translate(${offset}px, ${offset}px)`, zIndex: i }}
            />
          );
        })}

        {/* Front card */}
        <button
          onClick={() => onSelect(topTrend.id)}
          className={`absolute inset-0 rounded-xl border ${styles.border} ${styles.bg} p-4 flex flex-col gap-3 text-left
            group-hover:-translate-y-0.5 group-hover:shadow-lg transition-all duration-150`}
          style={{ zIndex: stackDepth + 1 }}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2">
            <span className={`text-xs font-semibold ${styles.text}`}>{cat}</span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM2 11a2 2 0 012-2h12a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4z" />
              </svg>
              {cluster.trends.length}
            </span>
          </div>

          {/* Cluster name */}
          <h3 className={`font-bold text-white text-sm leading-snug ${styles.text.replace("text-", "group-hover:text-")} transition-colors`}>
            {cluster.name}
          </h3>

          {/* Topic chips */}
          <div className="flex flex-wrap gap-1.5 mt-auto">
            {cluster.trends.slice(0, 5).map((t) => (
              <button
                key={t.id}
                onClick={(e) => { e.stopPropagation(); onSelect(t.id); }}
                className="text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-full px-2 py-0.5 truncate max-w-[120px] transition-colors"
              >
                {t.title}
              </button>
            ))}
            {cluster.trends.length > 5 && (
              <span className="text-xs text-gray-600">+{cluster.trends.length - 5}</span>
            )}
          </div>

          {/* Traffic of top trend */}
          {topTrend.traffic_volume && (
            <div className="text-xs text-gray-600 mt-auto pt-1 border-t border-gray-800">
              Top: {topTrend.traffic_volume} searches
            </div>
          )}
        </button>
      </div>
    </div>
  );
}
