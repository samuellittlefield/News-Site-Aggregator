import { useAstronomy } from "../../api/client";
import { Panel } from "./Panel";

const PHASE_ICONS: Record<string, string> = {
  "New Moon": "🌑",
  "Waxing Crescent": "🌒",
  "First Quarter": "🌓",
  "Waxing Gibbous": "🌔",
  "Full Moon": "🌕",
  "Waning Gibbous": "🌖",
  "Last Quarter": "🌗",
  "Waning Crescent": "🌘",
};

export function AstronomyPanel() {
  const { sky, loading } = useAstronomy();
  const nextEvent = sky?.events[0] ?? null;

  return (
    <Panel title="Tonight's Sky" icon="🔭">
      {loading || !sky ? (
        <div className="h-10 bg-gray-800/50 rounded-lg animate-pulse" />
      ) : (
        <div className="text-sm text-gray-300 space-y-1">
          <p>
            {PHASE_ICONS[sky.moon.phase] ?? "🌙"} {sky.moon.phase} ·{" "}
            <span className="text-gray-500">{Math.round(sky.moon.illumination)}%</span>
          </p>
          {nextEvent && (
            <p className="text-xs text-gray-500 line-clamp-1">
              {nextEvent.icon} {nextEvent.title} · {nextEvent.date}
            </p>
          )}
        </div>
      )}
    </Panel>
  );
}
