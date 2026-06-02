import { useMemo, useState } from "react";
import { Trend, useAnomalyTrends } from "../api/client";
import { TrendCard } from "./TrendCard";

const PAGE_SIZE = 20;

type Mode = "default" | "scramble" | "anomaly";

function AnomalyLabel({ trend }: { trend: Trend }) {
  if (!trend.is_active)
    return <span className="text-xs font-semibold text-purple-400 flex items-center gap-1"><span>📉</span> Dropped off · was trending {trend.appearance_count * 3}h</span>;
  if (trend.appearance_count === 1)
    return <span className="text-xs font-semibold text-orange-400 flex items-center gap-1"><span>🆕</span> Just broke in</span>;
  if (trend.rank_velocity >= 2)
    return <span className="text-xs font-semibold text-amber-400 flex items-center gap-1"><span>🚀</span> ↑{trend.rank_velocity} spots fast</span>;
  return null;
}

interface Props {
  trends: Trend[];
  onSelect: (id: number) => void;
}

export function TrendCarousel({ trends, onSelect }: Props) {
  const [mode, setMode] = useState<Mode>("default");
  const [scrambleSeed, setScrambleSeed] = useState(0);
  const [page, setPage] = useState(1);
  const { trends: anomalies, loading: anomalyLoading } = useAnomalyTrends();

  const sortedTrends = useMemo(() => {
    if (mode !== "scramble") return trends;
    const all = [...trends];
    // seeded shuffle
    for (let i = all.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [all[i], all[j]] = [all[j], all[i]];
    }
    return all;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, scrambleSeed, trends]);

  const displayTrends = sortedTrends.slice(0, page * PAGE_SIZE);
  const hasMore = displayTrends.length < sortedTrends.length;

  const handleScramble = () => {
    setMode("scramble");
    setScrambleSeed(s => s + 1);
    setPage(1);
  };

  const handleModeChange = (m: Mode) => {
    setMode(m);
    setPage(1);
  };

  return (
    <section>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <p className="text-xs text-gray-500">
            <span className="text-gray-300 font-medium">{trends.length}</span> topics
          </p>
          <div className="flex items-center gap-1 text-[10px] text-gray-600">
            <span className="border border-amber-800 text-amber-400 rounded px-1 font-bold">⚡4h</span>
            <span className="border border-blue-800 text-blue-400 rounded px-1 font-bold">G24h</span>
            <span className="border border-gray-600 text-gray-300 rounded px-1 font-bold">NYT</span>
            <span className="border border-gray-600 text-gray-400 rounded px-1 font-bold">W</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleModeChange("default")}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "default" ? "border-gray-600 text-gray-300 bg-gray-800" : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            Default
          </button>
          <button
            onClick={handleScramble}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "scramble" ? "border-amber-700 text-amber-400 bg-amber-950/40" : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            🔀 Scramble
          </button>
          <button
            onClick={() => handleModeChange("anomaly")}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "anomaly" ? "border-purple-700 text-purple-400 bg-purple-950/40" : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            ⚡ Anomaly
          </button>
        </div>
      </div>

      {/* Anomaly mode */}
      {mode === "anomaly" && (
        anomalyLoading ? (
          <div className="grid grid-cols-2 gap-3">
            {[1,2,3,4].map(i => <div key={i} className="h-44 bg-gray-900 rounded-xl animate-pulse" />)}
          </div>
        ) : anomalies.length === 0 ? (
          <p className="text-sm text-gray-600 py-4">No anomalies detected right now — everything is trending normally.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {anomalies.map(t => (
              <div key={t.id} className="flex flex-col gap-1.5">
                <AnomalyLabel trend={t} />
                <TrendCard trend={t} onClick={() => onSelect(t.id)} />
              </div>
            ))}
          </div>
        )
      )}

      {/* Default / Scramble mode — 2-column grid */}
      {mode !== "anomaly" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            {displayTrends.map(trend => (
              <div key={trend.id} className="flex flex-col gap-1">
                {/* Cluster label above card */}
                {trend.cluster_name && (
                  <p className="text-[10px] text-gray-600 font-medium px-1 truncate">
                    <span className="text-gray-700">●</span> {trend.cluster_name}
                  </p>
                )}
                <TrendCard trend={trend} onClick={() => onSelect(trend.id)} />
              </div>
            ))}
          </div>

          {hasMore && (
            <div className="mt-6 flex flex-col items-center gap-1">
              <button
                onClick={() => setPage(p => p + 1)}
                className="text-sm text-gray-500 hover:text-gray-300 border border-gray-800 hover:border-gray-600 rounded-lg px-5 py-2 transition-colors"
              >
                Show more · {Math.min(PAGE_SIZE, sortedTrends.length - displayTrends.length)} remaining
              </button>
              <p className="text-xs text-gray-700">Showing {displayTrends.length} of {sortedTrends.length}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
