import { useEarthquakes, useFaaStatus } from "../../api/client";
import { Panel } from "./Panel";

export function HazardsPanel({ onOpen }: { onOpen: () => void }) {
  const { data: quakes, loading } = useEarthquakes();
  const { data: faa } = useFaaStatus();

  const groundStops = faa?.events.filter(e => e.type === "ground_stop") ?? [];
  const delays = faa?.events.filter(e => e.type.includes("delay")) ?? [];
  const maxMag = quakes?.summary.max_magnitude ?? null;
  const hot = (maxMag !== null && maxMag >= 5.5) || groundStops.length > 0;

  return (
    <Panel
      title="Hazards"
      icon="⚠️"
      dot={hot ? "bg-red-500 animate-pulse" : "bg-emerald-500"}
      onOpen={onOpen}
    >
      {loading ? (
        <div className="h-16 bg-gray-800/50 rounded-lg animate-pulse" />
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Quakes · 24h</p>
            <p className="text-gray-200">
              <span className="text-xl font-bold">{quakes?.summary.count ?? 0}</span>
              {maxMag !== null && (
                <span className={`ml-2 text-xs ${maxMag >= 5.5 ? "text-red-400" : "text-gray-500"}`}>
                  max M{maxMag.toFixed(1)}
                </span>
              )}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">FAA delays</p>
            <p className="text-gray-200">
              <span className="text-xl font-bold">{delays.length}</span>
              {groundStops.length > 0 && (
                <span className="ml-2 text-xs text-red-400">
                  {groundStops.length} ground stop{groundStops.length > 1 ? "s" : ""} ({groundStops.map(g => g.airport).join(", ")})
                </span>
              )}
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
