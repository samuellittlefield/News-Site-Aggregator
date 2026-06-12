import { useState } from "react";
import { triggerRefresh, useTrends } from "../api/client";
import { NewsSegment } from "../components/NewsSegment";
import { PoliticsSection } from "../components/PoliticsSection";
import { TrendCarousel } from "../components/TrendCarousel";

const DIVIDER = <div className="border-t border-gray-800/60" />;

interface Props {
  onSelect: (id: number) => void;
}

export function TrendsPage({ onSelect }: Props) {
  const { trends, loading, error, refresh } = useTrends();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await triggerRefresh();
    refresh();
    setRefreshing(false);
  };

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {error && (
        <div className="text-center py-8 space-y-2">
          <p className="text-red-400 font-medium">Could not connect to the backend.</p>
          <p className="text-xs text-gray-600 font-mono">{error}</p>
        </div>
      )}

      {!error && (
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Trending</h1>
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="flex items-center gap-2 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 px-3 py-1.5 rounded-lg transition-colors"
          >
            <svg className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      )}

      {!error && (
        loading ? (
          <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex-shrink-0 w-64 h-52 bg-gray-900 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : (
          <TrendCarousel trends={trends} onSelect={onSelect} />
        )
      )}

      {DIVIDER}

      {trends.some(t => t.category === "Politics" || (t.summary?.body ?? "").toLowerCase().includes("congress"))
        ? <PoliticsSection onSelect={onSelect} />
        : <NewsSegment category="politics" label="Politics" icon="🏛" />
      }
    </main>
  );
}
