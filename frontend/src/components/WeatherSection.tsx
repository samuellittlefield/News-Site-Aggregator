import { useExtremeWeather, useRegionalWeather } from "../api/client";

const EXTREME_STYLES: Record<string, string> = {
  wildfires:    "border-orange-800/60 text-orange-400",
  severeStorms: "border-blue-800/60 text-blue-400",
  floods:       "border-cyan-800/60 text-cyan-400",
  tempExtremes: "border-red-800/60 text-red-400",
  drought:      "border-yellow-800/60 text-yellow-500",
};

function formatDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

export function WeatherSection() {
  const { clusters, loading: extremeLoading } = useExtremeWeather();
  const { regions, loading: regionalLoading } = useRegionalWeather();

  if (extremeLoading && regionalLoading) return null;

  return (
    <section className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-gray-300 uppercase tracking-wider">🌦 Weather &amp; Climate</span>
      </div>

      {/* Strip 1: Extreme events by type */}
      {clusters.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-wider">Extreme Events</p>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {clusters.map((cluster) => {
              const colorClass = EXTREME_STYLES[cluster.category] ?? "border-gray-700 text-gray-400";
              return (
                <div key={cluster.category}
                     className={`flex-shrink-0 w-60 bg-gray-900 border ${colorClass.split(" ")[0]} rounded-xl p-4 space-y-2`}>
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold ${colorClass.split(" ")[1]} flex items-center gap-1`}>
                      <span>{cluster.icon}</span>
                      <span>{cluster.label}</span>
                    </span>
                    <span className="text-xs text-gray-500">{cluster.count} active</span>
                  </div>
                  {cluster.worst_location && (
                    <p className="text-xs text-gray-400 flex items-center gap-1">
                      <svg className="w-2.5 h-2.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                      </svg>
                      {cluster.worst_location}
                    </p>
                  )}
                  {cluster.worst_summary && (
                    <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">{cluster.worst_summary}</p>
                  )}
                  <div className="flex items-center justify-between pt-1">
                    {cluster.worst_magnitude && (
                      <span className="text-xs text-gray-600">{cluster.worst_magnitude.toLocaleString()} {cluster.worst_magnitude_unit}</span>
                    )}
                    {cluster.worst_date && (
                      <span className="text-xs text-gray-600">{formatDate(cluster.worst_date)}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Strip 2: Regional daily weather */}
      {regions.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-wider">Today's Regional Forecast</p>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {regions.map((r) => (
              <div key={r.region}
                   className="flex-shrink-0 w-44 bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
                <div>
                  <p className="text-xs font-semibold text-gray-300">{r.region}</p>
                  <p className="text-xs text-gray-600">{r.city}</p>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-bold text-white">
                    {r.temp_max_f != null ? Math.round(r.temp_max_f) : "—"}°
                  </span>
                  <span className="text-sm text-gray-500">
                    / {r.temp_min_f != null ? Math.round(r.temp_min_f) : "—"}°
                  </span>
                </div>
                {r.condition && (
                  <p className="text-xs text-gray-500">{r.condition}</p>
                )}
                {r.precipitation_mm != null && r.precipitation_mm > 0 && (
                  <p className="text-xs text-blue-500">💧 {r.precipitation_mm.toFixed(1)} mm</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
