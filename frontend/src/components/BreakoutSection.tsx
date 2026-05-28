import { Trend, useBreakoutTrends } from "../api/client";

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

function BreakoutCard({ trend, onClick }: { trend: Trend; onClick: () => void }) {
  const catStyle = CATEGORY_STYLES[trend.category ?? "Other"] ?? CATEGORY_STYLES.Other;

  return (
    <button
      onClick={onClick}
      className="group flex-shrink-0 w-52 text-left bg-gray-900 hover:bg-gray-800 border border-violet-900/40 hover:border-violet-600/60 rounded-xl p-4 transition-all duration-150 flex flex-col gap-2"
    >
      <div className="flex items-center gap-1.5">
        <svg className="w-3 h-3 text-violet-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.still 0 0-4 0 3 3 0 006 0z" />
        </svg>
        <span className="text-xs font-semibold text-violet-400">Beyond top 10</span>
      </div>

      <p className="font-semibold text-white text-sm leading-snug group-hover:text-violet-300 transition-colors line-clamp-2">
        {trend.title}
      </p>

      {trend.summary && (
        <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">
          {trend.summary.body.slice(0, 80)}…
        </p>
      )}

      <div className="flex items-center gap-2 mt-auto flex-wrap">
        {trend.category && (
          <span className={`text-xs font-medium border rounded-full px-2 py-0.5 ${catStyle}`}>
            {trend.category}
          </span>
        )}
        {trend.wiki_pages.length > 0 && (
          <a
            href={trend.wiki_pages[0].url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-xs text-blue-500 hover:text-blue-400"
          >
            W
          </a>
        )}
      </div>
    </button>
  );
}

interface Props {
  onSelect: (id: number) => void;
}

export function BreakoutSection({ onSelect }: Props) {
  const { breakout, loading } = useBreakoutTrends();

  if (loading || breakout.length === 0) return null;

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-3.5 h-3.5 text-violet-400" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732l-3.354 1.935-1.18 4.455a1 1 0 01-1.933 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732l3.354-1.935 1.18-4.455A1 1 0 0112 2z" clipRule="evenodd" />
        </svg>
        <h2 className="text-sm font-semibold text-violet-400 uppercase tracking-wider">
          Also Trending
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          beyond the top feed · via Google Trends
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none">
        {breakout.map((trend) => (
          <BreakoutCard key={trend.id} trend={trend} onClick={() => onSelect(trend.id)} />
        ))}
      </div>
    </section>
  );
}
