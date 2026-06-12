import { useServiceStatus } from "../../api/client";
import { Panel } from "./Panel";

export function StatusPanel({ onOpen }: { onOpen: () => void }) {
  const { services, loading } = useServiceStatus();
  const affected = services.filter(s => s.indicator !== "none");
  const critical = affected.some(s => s.indicator === "critical" || s.indicator === "major");

  return (
    <Panel
      title="Internet"
      icon="🌐"
      dot={critical ? "bg-red-500 animate-pulse" : affected.length > 0 ? "bg-amber-500" : "bg-emerald-500"}
      onOpen={onOpen}
    >
      {loading ? (
        <div className="h-10 bg-gray-800/50 rounded-lg animate-pulse" />
      ) : affected.length === 0 ? (
        <p className="text-sm text-gray-400">All {services.length} services operational</p>
      ) : (
        <p className="text-sm text-gray-300">
          <span className="font-bold text-amber-400">{affected.length}</span> affected:{" "}
          <span className="text-gray-400">{affected.slice(0, 3).map(s => s.name).join(", ")}</span>
        </p>
      )}
    </Panel>
  );
}
