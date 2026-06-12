import { TrendDetail } from "./components/TrendDetail";
import { Page, useNavigation } from "./lib/useNavigation";
import { AdminPage } from "./pages/AdminPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HazardsPage } from "./pages/HazardsPage";
import { MarketsPage } from "./pages/MarketsPage";
import { NewsPage } from "./pages/NewsPage";
import { PollsPage } from "./pages/PollsPage";
import { StatusPage } from "./pages/StatusPage";
import { TrendsPage } from "./pages/TrendsPage";
import { WeatherPage } from "./pages/WeatherPage";

const NAV_TABS: { page: Page; label: string }[] = [
  { page: "dashboard", label: "Dashboard" },
  { page: "polling", label: "2026 Polling" },
  { page: "markets", label: "Markets" },
];

export default function App() {
  const { page, selectedTrendId, navigate, openTrend, back } = useNavigation();

  if (selectedTrendId !== null) {
    return <TrendDetail id={selectedTrendId} onBack={back} />;
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800 sticky top-0 z-10 bg-gray-950/90 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-1">
            {NAV_TABS.map(({ page: p, label }) => (
              <button
                key={p}
                onClick={() => navigate(p)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  page === p || (p === "dashboard" && !NAV_TABS.some(t => t.page === page))
                    ? "bg-gray-800 text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {/* Breadcrumb back to dashboard from drill-in pages */}
          {!NAV_TABS.some(t => t.page === page) && page !== "admin" && (
            <button
              onClick={() => navigate("dashboard")}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              ← Dashboard
            </button>
          )}
        </div>
      </header>

      {page === "dashboard" && <DashboardPage navigate={navigate} openTrend={openTrend} />}
      {page === "trends" && <TrendsPage onSelect={openTrend} />}
      {page === "polling" && <PollsPage />}
      {page === "markets" && <MarketsPage />}
      {page === "hazards" && <HazardsPage />}
      {page === "weather" && <WeatherPage />}
      {page === "news" && <NewsPage />}
      {page === "status" && <StatusPage />}
      {page === "admin" && <AdminPage />}
    </div>
  );
}
