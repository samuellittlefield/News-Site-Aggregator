import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import { Earthquake, FaaEvent, useEarthquakes, useFaaStatus } from "../api/client";

const WORLD_CENTER: [number, number] = [25, -40];

const FAA_TYPE_LABELS: Record<string, string> = {
  ground_stop: "Ground stop",
  ground_delay: "Ground delay",
  arrival_delay: "Arrival delay",
  departure_delay: "Departure delay",
  closure: "Closure",
};

function magColor(mag: number | null): string {
  if (mag === null) return "#6b7280";
  if (mag >= 6) return "#ef4444";
  if (mag >= 5) return "#f97316";
  if (mag >= 4) return "#eab308";
  return "#60a5fa";
}

function QuakeMap({ quakes }: { quakes: Earthquake[] }) {
  return (
    <div className="rounded-xl overflow-hidden border border-gray-800" style={{ height: 380 }}>
      <MapContainer
        center={WORLD_CENTER}
        zoom={2}
        minZoom={2}
        maxZoom={9}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%", background: "#0f1117" }}
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />
        {quakes.map(q => (
          q.lat !== null && q.lng !== null && (
            <CircleMarker
              key={q.usgs_id}
              center={[q.lat, q.lng]}
              radius={Math.max(3, (q.magnitude ?? 2) * 2.2)}
              pathOptions={{
                color: magColor(q.magnitude),
                fillColor: magColor(q.magnitude),
                fillOpacity: 0.45,
                weight: 1,
              }}
            >
              <Tooltip>
                M{q.magnitude?.toFixed(1)} — {q.place}
              </Tooltip>
            </CircleMarker>
          )
        ))}
      </MapContainer>
    </div>
  );
}

function FaaTable({ events }: { events: FaaEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-gray-600">No active FAA delay programs.</p>;
  }
  return (
    <div className="space-y-1.5">
      {events.map((e, i) => (
        <div key={i} className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
          <span className="font-mono font-bold text-gray-200 w-12">{e.airport}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
            e.type === "ground_stop" ? "bg-red-900/60 text-red-300" :
            e.type === "closure" ? "bg-gray-800 text-gray-400" :
            "bg-amber-900/50 text-amber-300"
          }`}>
            {FAA_TYPE_LABELS[e.type] ?? e.type}
          </span>
          <span className="flex-1 text-xs text-gray-500 truncate">{e.reason}</span>
          {e.avg_delay && <span className="text-xs text-gray-400">{e.avg_delay}</span>}
          {e.end_time && <span className="text-xs text-gray-600">until {e.end_time}</span>}
        </div>
      ))}
    </div>
  );
}

export function HazardsPage() {
  const { data: quakeData, loading: quakesLoading } = useEarthquakes(2.5, 24 * 7);
  const { data: faa, loading: faaLoading } = useFaaStatus();

  const quakes = quakeData?.earthquakes ?? [];
  const last24h = quakes.filter(q => q.time && Date.now() - new Date(q.time).getTime() < 24 * 3600 * 1000);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-gray-200">Hazards</h1>
        <p className="text-xs text-gray-600 mt-1">
          USGS earthquakes (M2.5+ last 7 days, refreshed every 5 min) · FAA airspace status (every 10 min)
        </p>
      </div>

      <section className="space-y-3">
        <div className="flex items-baseline gap-4">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Earthquakes</h2>
          {quakeData && (
            <p className="text-xs text-gray-600">
              {last24h.length} in last 24h · max M{quakeData.summary.max_magnitude?.toFixed(1) ?? "—"}
            </p>
          )}
        </div>
        {quakesLoading ? (
          <div className="h-[380px] bg-gray-900 rounded-xl animate-pulse" />
        ) : (
          <QuakeMap quakes={quakes} />
        )}
        <div className="grid md:grid-cols-2 gap-1.5">
          {quakes.slice(0, 10).map(q => (
            <a
              key={q.usgs_id}
              href={q.url ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 hover:border-gray-600 transition-colors"
            >
              <span className="font-mono font-bold text-sm" style={{ color: magColor(q.magnitude) }}>
                M{q.magnitude?.toFixed(1)}
              </span>
              <span className="flex-1 text-xs text-gray-400 truncate">{q.place}</span>
              {q.time && (
                <span className="text-xs text-gray-600">
                  {new Date(q.time).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
            </a>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">FAA Airspace</h2>
        {faaLoading ? (
          <div className="h-24 bg-gray-900 rounded-xl animate-pulse" />
        ) : (
          <FaaTable events={faa?.events ?? []} />
        )}
      </section>
    </main>
  );
}
