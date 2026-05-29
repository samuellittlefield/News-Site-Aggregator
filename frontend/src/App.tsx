import { useState } from "react";
import { triggerRefresh, useTrends } from "./api/client";
import { ClimateSection } from "./components/ClimateSection";
import { TrendCarousel } from "./components/TrendCarousel";
import { TrendDetail } from "./components/TrendDetail";

export default function App() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const { trends, loading, error, refresh } = useTrends();

  const handleRefresh = async () => {
    setRefreshing(true);
    await triggerRefresh();
    refresh();
    setRefreshing(false);
  };

  if (selectedId !== null) {
    return <TrendDetail id={selectedId} onBack={() => setSelectedId(null)} />;
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800 sticky top-0 z-10 bg-gray-950/90 backdrop-blur">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Trending Now</h1>
            <p className="text-xs text-gray-500 mt-0.5">Live trending searches + AI briefings</p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="flex items-center gap-2 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 px-3 py-1.5 rounded-lg transition-colors"
          >
            <svg className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
                 fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-10">

        {/* ── Climate segment — leads the page ── */}
        <ClimateSection />

        {/* ── Trending segment ── */}
        {loading && (
          <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex-shrink-0 w-64 h-52 bg-gray-900 rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {error && (
          <div className="text-center py-16 space-y-2">
            <p className="text-red-400 font-medium">Could not connect to the backend.</p>
            <p className="text-sm text-gray-500">Make sure the FastAPI server is running on port 8000.</p>
            <p className="text-xs text-gray-600 font-mono mt-2">{error}</p>
          </div>
        )}

        {!loading && !error && trends.length === 0 && (
          <div className="text-center py-16 space-y-3">
            <p className="text-gray-400">No trends loaded yet.</p>
            <button onClick={handleRefresh} className="text-sm text-blue-400 hover:text-blue-300 underline">
              Trigger a refresh
            </button>
          </div>
        )}

        {!loading && trends.length > 0 && (
          <TrendCarousel
            trends={trends}
            onSelect={setSelectedId}
            count={trends.length}
          />
        )}

      </main>
    </div>
  );
}
