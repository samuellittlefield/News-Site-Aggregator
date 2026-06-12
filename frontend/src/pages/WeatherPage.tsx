import { AstronomySection } from "../components/AstronomySection";
import { WeatherSection } from "../components/WeatherSection";

export function WeatherPage() {
  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      <WeatherSection />
      <div className="border-t border-gray-800/60" />
      <AstronomySection />
    </main>
  );
}
