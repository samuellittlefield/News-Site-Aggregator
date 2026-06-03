import { useEffect, useState } from "react";
import { triggerRefresh, useTrends } from "./api/client";
import { AstronomySection } from "./components/AstronomySection";
import { NewsSegment } from "./components/NewsSegment";
import { PoliticsSection } from "./components/PoliticsSection";
import { ServiceStatusSection } from "./components/ServiceStatusSection";
import { TrendCarousel } from "./components/TrendCarousel";
import { TrendDetail } from "./components/TrendDetail";
import { WeatherSection } from "./components/WeatherSection";
import { PollsPage } from "./pages/PollsPage";
import { AdminPage } from "./pages/AdminPage";

type Page = "monitor" | "polling" | "admin";

const DIVIDER = <div className="border-t border-gray-800/60" />;

export default function App() {
  const [activePage, setActivePage] = useState<Page>("monitor");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const { trends, loading, error, refresh } = useTrends();

  const handleSelect = (id: number) => {
    window.history.pushState({ trendId: id }, "");
    setSelectedId(id);
  };

  const handleBack = () => {
    setSelectedId(null);
  };

  const handlePageSwitch = (page: Page) => {
    setActivePage(page);
    setSelectedId(null);
    window.history.pushState({ page }, "");
  };

  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      if (e.state?.trendId) return;
      if (e.state?.page) { setActivePage(e.state.page); return; }
      setSelectedId(null);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await triggerRefresh();
    refresh();
    setRefreshing(false);
  };

  if (selectedId !== null) {
    return <TrendDetail id={selectedId} onBack={handleBack} />;
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800 sticky top-0 z-10 bg-gray-950/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          {/* Nav tabs */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => handlePageSwitch("monitor")}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activePage === "monitor"
                  ? "bg-gray-800 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Situation Monitor
            </button>
            <button
              onClick={() => handlePageSwitch("polling")}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activePage === "polling"
                  ? "bg-gray-800 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              2026 Polling
            </button>
          </div>

          {/* Refresh (monitor only) */}
          {activePage === "monitor" && (
            <button onClick={handleRefresh} disabled={refreshing || loading}
              className="flex items-center gap-2 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 px-3 py-1.5 rounded-lg transition-colors">
              <svg className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          )}
        </div>
      </header>

      {/* Polling page */}
      {activePage === "polling" && <PollsPage />}

      {/* Admin page — not linked from nav, accessed via handlePageSwitch("admin") */}
      {activePage === "admin" && <AdminPage />}

      {/* Situation Monitor page */}
      {activePage === "monitor" && (
        <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">

          {error && (
            <div className="text-center py-8 space-y-2">
              <p className="text-red-400 font-medium">Could not connect to the backend.</p>
              <p className="text-xs text-gray-600 font-mono">{error}</p>
            </div>
          )}

          {/* 1 ── Top Trending */}
          {!error && (
            loading ? (
              <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex-shrink-0 w-64 h-52 bg-gray-900 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : (
              <TrendCarousel trends={trends} onSelect={handleSelect} />
            )
          )}

          {DIVIDER}

          {/* 2 ── Weather & Climate */}
          <WeatherSection />

          {DIVIDER}

          {/* 3 ── Politics */}
          {trends.some(t => t.category === "Politics" || (t.summary?.body ?? "").toLowerCase().includes("congress"))
            ? <PoliticsSection onSelect={handleSelect} />
            : <NewsSegment category="politics" label="Politics" icon="🏛" />
          }

          {DIVIDER}

          {/* 4 ── Transportation */}
          <NewsSegment category="transportation" label="Transportation" icon="🚆" />

          {DIVIDER}

          {/* 5 ── Astronomy */}
          <AstronomySection />

          {DIVIDER}

          {/* 6 ── Internet Health */}
          <ServiceStatusSection />

        </main>
      )}
    </div>
  );
}
