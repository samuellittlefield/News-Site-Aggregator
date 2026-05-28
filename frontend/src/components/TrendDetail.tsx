import { useTrendDetail } from "../api/client";
import { ArticleList } from "./ArticleList";
import { Sparkline } from "./Sparkline";

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
  id: number;
  onBack: () => void;
}

export function TrendDetail({ id, onBack }: Props) {
  const { trend, loading, error } = useTrendDetail(id);

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="max-w-2xl mx-auto px-4 py-8">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-300 mb-8 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to trends
        </button>

        {loading && (
          <div className="space-y-4 animate-pulse">
            <div className="h-8 bg-gray-800 rounded w-3/4" />
            <div className="h-4 bg-gray-800 rounded w-1/4" />
            <div className="h-24 bg-gray-800 rounded mt-6" />
          </div>
        )}

        {error && (
          <p className="text-red-400 text-sm">Failed to load: {error}</p>
        )}

        {trend && (
          <article className="space-y-8">
            <header className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-bold text-white">{trend.title}</h1>
                {trend.traffic_volume && (
                  <span className="text-xs font-medium bg-blue-950 text-blue-300 border border-blue-800 rounded-full px-2.5 py-0.5">
                    {trend.traffic_volume} searches
                  </span>
                )}
                {trend.category && (
                  <span className={`text-xs font-medium border rounded-full px-2.5 py-0.5 ${CATEGORY_STYLES[trend.category] ?? CATEGORY_STYLES.Other}`}>
                    {trend.category}
                  </span>
                )}
                {trend.appearance_count === 1 && (
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-orange-400">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-orange-500" />
                    </span>
                    Breaking
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-600">
                {trend.geo}
                {trend.first_seen_at && (
                  <> · First seen {new Date(trend.first_seen_at).toLocaleString()}</>
                )}
                {trend.appearance_count > 1 && (
                  <> · Trending for ~{trend.appearance_count * 3}h</>
                )}
              </p>
            </header>

            {trend.summary ? (
              <section className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-blue-400 uppercase tracking-wider">
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" />
                  </svg>
                  AI Briefing
                </div>
                <p className="text-gray-200 text-sm leading-relaxed">{trend.summary.body}</p>
              </section>
            ) : (
              <section className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <p className="text-sm text-gray-500 italic">No AI summary available yet.</p>
              </section>
            )}

            {(() => {
              const primary = trend.wiki_pages.find((w) => w.is_primary) ?? trend.wiki_pages[0];
              return (
                <>
                  <Sparkline trendId={trend.id} wikiTitle={primary?.title} />

                  {trend.wiki_pages.length > 0 && (
                    <section className="space-y-3">
                      {trend.wiki_pages.map((wiki) => (
                        <div key={wiki.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                          <div className="flex gap-4 p-5">
                            {wiki.thumbnail_url && (
                              <img
                                src={wiki.thumbnail_url}
                                alt={wiki.title}
                                className="w-16 h-16 rounded-lg object-cover shrink-0"
                              />
                            )}
                            <div className="flex flex-col gap-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Wikipedia</span>
                                {wiki.is_primary && (
                                  <span className="text-xs text-blue-500 font-medium">Primary</span>
                                )}
                              </div>
                              <p className="font-semibold text-white leading-snug">{wiki.title}</p>
                              {wiki.description && (
                                <p className="text-xs text-gray-400">{wiki.description}</p>
                              )}
                            </div>
                          </div>
                          {wiki.is_primary && wiki.extract && (
                            <p className="text-sm text-gray-300 leading-relaxed px-5 pb-4 line-clamp-4">
                              {wiki.extract}
                            </p>
                          )}
                          <div className="border-t border-gray-800 px-5 py-3">
                            <a
                              href={wiki.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                            >
                              Read full article on Wikipedia →
                            </a>
                          </div>
                        </div>
                      ))}
                    </section>
                  )}
                </>
              );
            })()}

            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                Related Articles
              </h2>
              <ArticleList articles={trend.articles} />
            </section>
          </article>
        )}
      </div>
    </div>
  );
}
