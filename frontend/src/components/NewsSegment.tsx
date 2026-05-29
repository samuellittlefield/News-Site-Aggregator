import { useNews } from "../api/client";

interface Props {
  category: "politics" | "transportation";
  label: string;
  icon: string;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function NewsSegment({ category, label, icon }: Props) {
  const { articles, loading } = useNews(category);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-base">{icon}</span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">{label}</h2>
      </div>

      {loading && (
        <div className="flex gap-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex-shrink-0 w-64 h-36 bg-gray-900 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!loading && articles.length === 0 && (
        <p className="text-sm text-gray-600 py-2">No recent articles found.</p>
      )}

      {!loading && articles.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
          {articles.map(a => (
            <a
              key={a.id}
              href={a.url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 w-64 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 flex flex-col gap-2 transition-colors group"
            >
              <p className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors leading-snug line-clamp-3">
                {a.title}
              </p>
              {a.ai_summary && (
                <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed flex-1">
                  {a.ai_summary}
                </p>
              )}
              <div className="flex items-center justify-between mt-auto pt-1 text-xs text-gray-600">
                <span className="truncate">{a.source}</span>
                <span className="shrink-0 ml-2">{timeAgo(a.published_at)}</span>
              </div>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}
