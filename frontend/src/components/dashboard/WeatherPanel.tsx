import { useExtremeWeather, useWeatherAlerts } from "../../api/client";
import { Panel } from "./Panel";

export function WeatherPanel({ onOpen }: { onOpen: () => void }) {
  const { alerts, loading } = useWeatherAlerts();
  const { clusters } = useExtremeWeather();

  const extreme = alerts.filter(a => a.severity === "Extreme").length;
  const severe = alerts.filter(a => a.severity === "Severe").length;
  const worst = clusters[0] ?? null;

  return (
    <Panel
      title="Weather & Climate"
      icon="🌪"
      dot={extreme > 0 ? "bg-red-500 animate-pulse" : severe > 0 ? "bg-amber-500" : "bg-emerald-500"}
      meta={`${alerts.length} alerts`}
      onOpen={onOpen}
    >
      {loading ? (
        <div className="h-16 bg-gray-800/50 rounded-lg animate-pulse" />
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2">
            {extreme > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-900/60 text-red-300 font-medium">
                {extreme} Extreme
              </span>
            )}
            {severe > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-900/60 text-amber-300 font-medium">
                {severe} Severe
              </span>
            )}
            {extreme === 0 && severe === 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">
                No severe alerts
              </span>
            )}
          </div>
          {worst && (
            <p className="text-xs text-gray-400 leading-snug">
              {worst.icon} <span className="text-gray-300">{worst.worst_title}</span>
              {worst.worst_location && <span className="text-gray-600"> · {worst.worst_location}</span>}
            </p>
          )}
        </div>
      )}
    </Panel>
  );
}
