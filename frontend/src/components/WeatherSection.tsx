import { useState } from "react";
import { useClimateEvents, useExtremeWeather, useRegionalForecast, useRegionalWeather, useWeatherAlerts } from "../api/client";
import { WeatherMap } from "./WeatherMap";

const EXTREME_STYLES: Record<string, { border: string; text: string }> = {
  wildfires:    { border: "border-orange-800/60", text: "text-orange-400" },
  severeStorms: { border: "border-blue-800/60",   text: "text-blue-400"   },
  floods:       { border: "border-cyan-800/60",   text: "text-cyan-400"   },
  tempExtremes: { border: "border-red-800/60",    text: "text-red-400"    },
  drought:      { border: "border-yellow-800/60", text: "text-yellow-500" },
  landslides:   { border: "border-stone-700/60",  text: "text-stone-400"  },
};

const SEVERITY_STYLES: Record<string, { border: string; dot: string }> = {
  Extreme: { border: "border-red-700/70",    dot: "bg-red-500"    },
  Severe:  { border: "border-orange-700/70", dot: "bg-orange-500" },
  Moderate:{ border: "border-yellow-700/70", dot: "bg-yellow-500" },
};

// Event-type color lookup — matched by keyword priority order
const EVENT_COLOR_RULES: [RegExp, string][] = [
  [/tornado/i,                        "text-violet-400"  ],
  [/hurricane|tropical storm/i,       "text-teal-300"    ],
  [/fire weather|red flag/i,          "text-orange-400"  ],
  [/wildfire/i,                       "text-amber-500"   ],
  [/flash flood/i,                    "text-cyan-400"    ],
  [/flood/i,                          "text-blue-400"    ],
  [/blizzard|ice storm/i,             "text-sky-200"     ],
  [/winter storm|winter weather/i,    "text-sky-300"     ],
  [/freeze|frost/i,                   "text-blue-200"    ],
  [/extreme heat|excessive heat/i,    "text-red-400"     ],
  [/heat/i,                           "text-rose-400"    ],
  [/dust storm|haboob/i,              "text-yellow-600"  ],
  [/high wind|wind advisory/i,        "text-emerald-400" ],
  [/thunderstorm|lightning/i,         "text-yellow-300"  ],
  [/dense fog|fog/i,                  "text-slate-400"   ],
  [/marine|coastal|rip current/i,     "text-teal-400"    ],
  [/air quality|smoke/i,              "text-orange-300"  ],
  [/avalanche/i,                      "text-indigo-300"  ],
  [/drought/i,                        "text-yellow-500"  ],
  [/special weather|statement/i,      "text-gray-400"    ],
];

function eventColor(event: string): string {
  for (const [re, cls] of EVENT_COLOR_RULES) {
    if (re.test(event)) return cls;
  }
  return "text-gray-300";
}

function formatDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

function ForecastDrawer({ region }: { region: string }) {
  const { forecast, loading } = useRegionalForecast(region);

  if (loading) {
    return (
      <div className="mt-3 pt-3 border-t border-gray-800 animate-pulse space-y-2">
        {[1, 2, 3].map(i => <div key={i} className="h-8 bg-gray-800 rounded" />)}
      </div>
    );
  }
  if (!forecast) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-800 space-y-2">
      <p className="text-xs text-gray-600 uppercase tracking-wider">3-Day Forecast</p>
      {forecast.days.map(day => (
        <div key={day.date} className="flex items-center justify-between text-xs">
          <span className="text-gray-400 w-8 shrink-0">{day.day_name}</span>
          <span className="text-gray-500 flex-1 px-2 truncate">{day.condition}</span>
          <div className="flex items-center gap-2 shrink-0">
            {day.precipitation_mm != null && day.precipitation_mm > 0 && (
              <span className="text-blue-500">💧{day.precipitation_mm.toFixed(1)}</span>
            )}
            {day.wind_mph != null && (
              <span className="text-gray-600">{Math.round(day.wind_mph)}mph</span>
            )}
            <span className="text-white font-medium">{day.temp_max_f != null ? Math.round(day.temp_max_f) : "—"}°</span>
            <span className="text-gray-500">{day.temp_min_f != null ? Math.round(day.temp_min_f) : "—"}°</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function EventDetailPanel({ category, onClose }: { category: string; onClose: () => void }) {
  const { events } = useClimateEvents();
  const filtered = events.filter(e => e.category === category);

  return (
    <div className="mt-3 p-4 bg-gray-950 border border-gray-700 rounded-xl space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          {filtered.length} active events
        </p>
        <button onClick={onClose} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
          ✕ Close
        </button>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
        {filtered.map(event => (
          <div key={event.eonet_id} className="flex-shrink-0 w-56 bg-gray-900 border border-gray-800 rounded-xl p-3 space-y-2">
            {event.location && (
              <p className="text-xs text-gray-400 flex items-center gap-1">
                <svg className="w-2.5 h-2.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                </svg>
                {event.location}
              </p>
            )}
            <p className="text-xs font-medium text-white leading-snug line-clamp-2">{event.title}</p>
            {event.ai_summary && (
              <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">{event.ai_summary}</p>
            )}
            <div className="flex items-center justify-between text-xs text-gray-600">
              {event.magnitude != null && <span>{event.magnitude.toLocaleString()} {event.magnitude_unit}</span>}
              {event.start_date && <span>{new Date(event.start_date).toLocaleDateString([], { month: "short", day: "numeric" })}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function WeatherSection() {
  const { clusters } = useExtremeWeather();
  const { regions } = useRegionalWeather();
  const { alerts } = useWeatherAlerts();
  const [expandedRegion, setExpandedRegion] = useState<string | null>(null);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const toggleRegion = (region: string) =>
    setExpandedRegion(prev => (prev === region ? null : region));

  return (
    <section className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-gray-300 uppercase tracking-wider">🌦 Weather &amp; Climate</span>
      </div>

      {/* Radar Map */}
      <WeatherMap />

      {/* Strip 1: Notable Weather — NWS alerts + EONET clusters merged */}
      <div className="space-y-2">
        <p className="text-xs text-gray-600 uppercase tracking-wider">Notable Weather</p>
        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">

          {/* NWS alert cards */}
          {alerts.map(alert => {
            const style = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES["Moderate"];
            const isExpanded = expandedCategory === alert.nws_id;
            const alertUrl = `https://www.weather.gov/`;
            return (
              <div key={alert.nws_id} className="flex-shrink-0 w-60 space-y-0">
                <button
                  onClick={() => setExpandedCategory(isExpanded ? null : alert.nws_id)}
                  className={`w-full text-left bg-gray-900 border ${isExpanded ? "border-gray-500" : style.border} hover:border-gray-500 rounded-xl p-4 space-y-2 transition-colors`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold ${eventColor(alert.event)} flex items-center gap-1.5`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${style.dot} animate-pulse`} />
                      {alert.event}
                    </span>
                    <span className="text-xs text-gray-600">{alert.severity}</span>
                  </div>
                  {alert.area_desc && (
                    <p className="text-xs text-gray-400 flex items-center gap-1">
                      <svg className="w-2.5 h-2.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                      </svg>
                      <span className="truncate">{alert.area_desc}</span>
                    </p>
                  )}
                  {alert.headline && (
                    <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">{alert.headline}</p>
                  )}
                  <div className="flex items-center justify-between pt-1 text-xs text-gray-600">
                    {alert.onset && <span>Since {formatDate(alert.onset)}</span>}
                    {alert.expires && <span>Exp {formatDate(alert.expires)}</span>}
                  </div>
                  <p className="text-xs text-gray-600 text-right">tap to expand ›</p>
                </button>

                {isExpanded && (
                  <div className="mt-2 p-3 bg-gray-950 border border-gray-700 rounded-xl space-y-2">
                    {alert.urgency && (
                      <p className="text-xs text-gray-400">
                        <span className="text-gray-600">Urgency:</span> {alert.urgency}
                      </p>
                    )}
                    {alert.expires && (
                      <p className="text-xs text-gray-400">
                        <span className="text-gray-600">Expires:</span> {new Date(alert.expires).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </p>
                    )}
                    <a
                      href={alertUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-xs text-blue-400 hover:text-blue-300 transition-colors pt-1"
                    >
                      View active alerts on weather.gov ↗
                    </a>
                  </div>
                )}
              </div>
            );
          })}

          {/* EONET extreme event cluster cards */}
          {clusters.map((cluster) => {
            const style = EXTREME_STYLES[cluster.category] ?? { border: "border-gray-700", text: "text-gray-400" };
            const isExpanded = expandedCategory === cluster.category;
            return (
              <div key={cluster.category} className="flex-shrink-0 w-60 space-y-0">
                <button
                  onClick={() => setExpandedCategory(isExpanded ? null : cluster.category)}
                  className={`w-full text-left bg-gray-900 border ${isExpanded ? "border-gray-500" : style.border} hover:border-gray-500 rounded-xl p-4 space-y-2 transition-colors`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold ${style.text} flex items-center gap-1`}>
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
                    {cluster.worst_magnitude ? (
                      <span className="text-xs text-gray-600">
                        {cluster.worst_magnitude.toLocaleString()} {cluster.worst_magnitude_unit}
                      </span>
                    ) : <span />}
                    {cluster.worst_date && (
                      <span className="text-xs text-gray-600">{formatDate(cluster.worst_date)}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 text-right">tap to expand ›</p>
                </button>
                {isExpanded && (
                  <EventDetailPanel
                    category={cluster.category}
                    onClose={() => setExpandedCategory(null)}
                  />
                )}
              </div>
            );
          })}

          {alerts.length === 0 && clusters.length === 0 && (
            <p className="text-xs text-gray-600">No active weather alerts.</p>
          )}
        </div>
      </div>

      {/* Strip 2: Regional daily weather — click to expand 3-day */}
      {regions.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-wider">Today's Regional Forecast</p>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
            {regions.map((r) => {
              const isOpen = expandedRegion === r.region;
              return (
                <button
                  key={r.region}
                  onClick={() => toggleRegion(r.region)}
                  className={`flex-shrink-0 text-left bg-gray-900 border rounded-xl p-4 transition-all duration-150
                    ${isOpen ? "w-72 border-blue-700/60" : "w-44 border-gray-800 hover:border-gray-600"}`}
                >
                  <div className="space-y-2">
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
                    {r.condition && <p className="text-xs text-gray-500">{r.condition}</p>}
                    {r.precipitation_mm != null && r.precipitation_mm > 0 && (
                      <p className="text-xs text-blue-500">💧 {r.precipitation_mm.toFixed(1)} mm</p>
                    )}
                  </div>

                  {isOpen && <ForecastDrawer region={r.region} />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
