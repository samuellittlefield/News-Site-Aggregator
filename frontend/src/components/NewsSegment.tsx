import { Trend, useNews } from "../api/client";
import { ClusterStack } from "./ClusterStack";
import { TrendCard } from "./TrendCard";

interface Props {
  category: "politics" | "transportation";
  label: string;
  icon: string;
  trends: Trend[];       // cross-referenced from Top 10
  onSelect: (id: number) => void;
}

// Build cluster data from trends that share the same cluster_id
function extractClusters(trends: Trend[]) {
  const map = new Map<number, { id: number; name: string; category: string | null; trends: Trend[] }>();
  const ungrouped: Trend[] = [];
  for (const t of trends) {
    if (t.cluster_id && t.cluster_name) {
      if (!map.has(t.cluster_id)) map.set(t.cluster_id, { id: t.cluster_id, name: t.cluster_name, category: t.category, trends: [] });
      map.get(t.cluster_id)!.trends.push(t);
    } else {
      ungrouped.push(t);
    }
  }
  return { clusters: Array.from(map.values()), ungrouped };
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function NewsSegment({ category, label, icon, trends, onSelect }: Props) {
  const { articles } = useNews(category);
  const { clusters, ungrouped } = extractClusters(trends);
  const hasTrending = clusters.length > 0 || ungrouped.length > 0;

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-base">{icon}</span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">{label}</h2>
      </div>

      {/* Trending cross-references with stack treatment */}
      {hasTrending && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-600 uppercase tracking-wider">Trending Now</p>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {clusters.map(c => (
              <ClusterStack key={`c-${c.id}`} cluster={c} onSelect={onSelect} />
            ))}
            {ungrouped.map(t => (
              <div key={t.id} className="flex-shrink-0 w-64">
                <TrendCard trend={t} onClick={() => onSelect(t.id)} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Independent news articles */}
      {articles.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-600 uppercase tracking-wider">Latest News</p>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {articles.map(a => (
              <a key={a.id} href={a.url ?? "#"} target="_blank" rel="noopener noreferrer"
                 className="flex-shrink-0 w-64 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 flex flex-col gap-2 transition-colors group">
                <p className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors leading-snug line-clamp-3">
                  {a.title}
                </p>
                {a.ai_summary && (
                  <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">{a.ai_summary}</p>
                )}
                <div className="flex items-center justify-between mt-auto pt-1">
                  <span className="text-xs text-gray-600 truncate">{a.source}</span>
                  <span className="text-xs text-gray-600 shrink-0">{timeAgo(a.published_at)}</span>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
