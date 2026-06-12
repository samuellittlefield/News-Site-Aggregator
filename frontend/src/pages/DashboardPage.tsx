import { Page } from "../lib/useNavigation";
import { TrendsPanel } from "../components/dashboard/TrendsPanel";
import { PollsPanel } from "../components/dashboard/PollsPanel";
import { MarketsPanel } from "../components/dashboard/MarketsPanel";
import { HazardsPanel } from "../components/dashboard/HazardsPanel";
import { WeatherPanel } from "../components/dashboard/WeatherPanel";
import { NewsPanel } from "../components/dashboard/NewsPanel";
import { StatusPanel } from "../components/dashboard/StatusPanel";
import { AstronomyPanel } from "../components/dashboard/AstronomyPanel";

interface Props {
  navigate: (page: Page) => void;
  openTrend: (id: number) => void;
}

export function DashboardPage({ navigate, openTrend }: Props) {
  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      <div className="grid grid-cols-2 md:grid-cols-6 xl:grid-cols-12 gap-3">
        {/* Rows 1–2: the three deep panels */}
        <div className="col-span-2 md:col-span-6 xl:col-span-6 [&>section]:h-full">
          <TrendsPanel onOpen={() => navigate("trends")} onSelectTrend={openTrend} />
        </div>
        <div className="col-span-2 md:col-span-3 xl:col-span-3 [&>section]:h-full">
          <PollsPanel onOpen={() => navigate("polling")} />
        </div>
        <div className="col-span-2 md:col-span-3 xl:col-span-3 [&>section]:h-full">
          <MarketsPanel onOpen={() => navigate("markets")} />
        </div>

        {/* Row 3: situational panels */}
        <div className="col-span-2 md:col-span-3 xl:col-span-4 [&>section]:h-full">
          <HazardsPanel onOpen={() => navigate("hazards")} />
        </div>
        <div className="col-span-2 md:col-span-3 xl:col-span-4 [&>section]:h-full">
          <WeatherPanel onOpen={() => navigate("weather")} />
        </div>
        <div className="col-span-2 md:col-span-6 xl:col-span-4 [&>section]:h-full">
          <NewsPanel onOpen={() => navigate("news")} />
        </div>

        {/* Row 4: slim strips */}
        <div className="col-span-1 md:col-span-3 xl:col-span-6 [&>section]:h-full">
          <StatusPanel onOpen={() => navigate("status")} />
        </div>
        <div className="col-span-1 md:col-span-3 xl:col-span-6 [&>section]:h-full">
          <AstronomyPanel />
        </div>
      </div>
    </main>
  );
}
