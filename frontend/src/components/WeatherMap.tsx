import "leaflet/dist/leaflet.css";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";

const US_CENTER: [number, number] = [39.5, -98.35];
const US_BOUNDS: [[number, number], [number, number]] = [
  [20, -130],
  [52, -60],
];

interface RainViewerFrame {
  time: number;
  path: string;
}

interface RainViewerData {
  radar: { past: RainViewerFrame[]; nowcast: RainViewerFrame[] };
}

export function WeatherMap() {
  const [radarPath, setRadarPath] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    fetch("https://api.rainviewer.com/public/weather-maps.json")
      .then(r => r.json())
      .then((data: RainViewerData) => {
        const frames = data?.radar?.past ?? [];
        if (frames.length > 0) {
          const latest = frames[frames.length - 1];
          setRadarPath(latest.path);
          setUpdatedAt(new Date(latest.time * 1000));
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-1.5">
    <div className="relative w-full rounded-xl overflow-hidden border border-gray-800" style={{ aspectRatio: "16/5" }}>
      <MapContainer
        center={US_CENTER}
        zoom={4}
        minZoom={3}
        maxZoom={7}
        maxBounds={US_BOUNDS}
        maxBoundsViscosity={0.9}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%", background: "#0f1117" }}
        zoomControl={false}
        attributionControl={false}
      >
        {/* Dark base map */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />

        {/* RainViewer radar overlay */}
        {radarPath && (
          <TileLayer
            url={`https://tilecache.rainviewer.com${radarPath}/256/{z}/{x}/{y}/4/1_1.png`}
            opacity={0.65}
            zIndex={10}
          />
        )}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 z-[1000] flex items-center gap-2 bg-gray-950/80 rounded-lg px-2 py-1 pointer-events-none">
        <span className="text-[10px] text-gray-500 uppercase tracking-wider">Radar</span>
        <div className="flex gap-0.5">
          {["#00c5ff", "#00ff41", "#ffff00", "#ff8c00", "#ff0000"].map((c, i) => (
            <div key={i} className="w-3 h-2 rounded-sm" style={{ backgroundColor: c }} />
          ))}
        </div>
        <span className="text-[10px] text-gray-500">Light → Heavy</span>
      </div>

      {/* Attribution */}
      <div className="absolute bottom-2 right-2 z-[1000] text-[9px] text-gray-600 pointer-events-none">
        © CartoDB
      </div>
    </div>

    {/* Timestamp + source link below the map */}
    <div className="flex items-center gap-1.5 text-[10px] text-gray-600">
      {updatedAt && (
        <span>Radar updated {updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      )}
      <span>·</span>
      <a
        href="https://www.rainviewer.com"
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-gray-400 transition-colors"
      >
        RainViewer ↗
      </a>
    </div>
    </div>
  );
}
