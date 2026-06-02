import { useMemo, useState } from "react";
import { Trend, useAnomalyTrends } from "../api/client";
import { TrendCard } from "./TrendCard";

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
  const { trends: anomalies, loading: anomalyLoading } = useAnomalyTrends();

  const displayTrends = useMemo(() => {
    if (mode !== "scramble") return trends;
    const all = [...trends];
    for (let i = all.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [all[i], all[j]] = [all[j], all[i]];
    }
    return all;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, scrambleSeed, trends]);

  const handleScramble = () => {
    setMode("scramble");
    setScrambleSeed(s => s + 1);
  };

  return (
    <section>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
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
            onClick={() => setMode("default")}
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
            onClick={() => setMode("anomaly")}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "anomaly" ? "border-purple-700 text-purple-400 bg-purple-950/40" : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            ⚡ Anomaly
          </button>
        </div>
      </div>

      {/* Anomaly mode — single row, full-size cards, horizontal scroll */}
      {mode === "anomaly" && (
        anomalyLoading ? (
          <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-none">
            {[1,2,3,4].map(i => <div key={i} className="flex-shrink-0 w-64 h-44 bg-gray-900 rounded-xl animate-pulse" />)}
          </div>
        ) : anomalies.length === 0 ? (
          <p className="text-sm text-gray-600 py-4">No anomalies detected right now.</p>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-none">
            {anomalies.map(t => (
              <div key={t.id} className="flex-shrink-0 w-64 flex flex-col gap-1.5">
                <AnomalyLabel trend={t} />
                <TrendCard trend={t} onClick={() => onSelect(t.id)} />
              </div>
            ))}
          </div>
        )
      )}

      {/* Default / Scramble — 2-row horizontal grid, compact cards */}
      {mode !== "anomaly" && (
        <div
          className="overflow-x-auto -mx-4 px-4 pb-2 scrollbar-none"
        >
          <div
            className="grid grid-rows-2 grid-flow-col gap-2"
            style={{ gridAutoColumns: "11rem", gridAutoRows: "5.5rem" }}
          >
            {displayTrends.map(trend => (
              <div key={trend.id} className="flex flex-col gap-0.5 min-w-0">
                {trend.cluster_name && (
                  <p className="text-[9px] text-gray-700 font-medium px-0.5 truncate leading-tight">
                    ● {trend.cluster_name}
                  </p>
                )}
                <div className="flex-1 min-h-0">
                  <TrendCard trend={trend} onClick={() => onSelect(trend.id)} compact />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
