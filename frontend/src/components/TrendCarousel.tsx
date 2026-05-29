import { useMemo, useState } from "react";
import { Trend, useAnomalyTrends } from "../api/client";
import { ClusterStack } from "./ClusterStack";
import { TrendCard } from "./TrendCard";

type Mode = "default" | "scramble" | "anomaly";

interface ClusterData {
  id: number;
  name: string;
  category: string | null;
  trends: Trend[];
}

function buildCarouselItems(trends: Trend[]) {
  const clusterMap = new Map<number, ClusterData>();
  const ungrouped: Trend[] = [];

  for (const trend of trends) {
    if (trend.cluster_id && trend.cluster_name) {
      if (!clusterMap.has(trend.cluster_id))
        clusterMap.set(trend.cluster_id, { id: trend.cluster_id, name: trend.cluster_name, category: trend.category, trends: [] });
      clusterMap.get(trend.cluster_id)!.trends.push(trend);
    } else {
      ungrouped.push(trend);
    }
  }

  const clusters = Array.from(clusterMap.values()).sort((a, b) => b.trends.length - a.trends.length);
  return [
    ...clusters.map(c => ({ type: "cluster" as const, data: c })),
    ...ungrouped.map(t => ({ type: "trend" as const, data: t })),
  ];
}

function AnomalyLabel({ trend }: { trend: Trend }) {
  const isDropoff = !trend.is_active;  // type hint — inactive = dropoff
  if (isDropoff) {
    return (
      <span className="text-xs font-semibold text-purple-400 flex items-center gap-1">
        <span>📉</span> Dropped off · was trending {trend.appearance_count * 3}h
      </span>
    );
  }
  if (trend.appearance_count === 1)
    return <span className="text-xs font-semibold text-orange-400 flex items-center gap-1"><span>🆕</span> Just broke in</span>;
  if (trend.rank_velocity >= 2)
    return <span className="text-xs font-semibold text-amber-400 flex items-center gap-1"><span>🚀</span> ↑{trend.rank_velocity} spots fast</span>;
  return null;
}

interface Props {
  trends: Trend[];
  onSelect: (id: number) => void;
  count: number;
}

export function TrendCarousel({ trends, onSelect, count }: Props) {
  const [mode, setMode] = useState<Mode>("default");
  const [scrambleSeed, setScrambleSeed] = useState(0);
  const { trends: anomalies, loading: anomalyLoading } = useAnomalyTrends();

  const defaultItems = useMemo(() => buildCarouselItems(trends), [trends]);

  const displayItems = useMemo(() => {
    if (mode === "scramble") {
      const all = [...defaultItems];
      for (let i = all.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [all[i], all[j]] = [all[j], all[i]];
      }
      return all;
    }
    return defaultItems;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, scrambleSeed, defaultItems]);

  const handleScramble = () => {
    setMode("scramble");
    setScrambleSeed(s => s + 1);
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <p className="text-xs text-gray-600">{count} topics · sorted by signal</p>
          <div className="flex items-center gap-1.5 text-[10px] text-gray-600">
            <span className="border border-blue-800 text-blue-400 rounded px-1 font-bold">G</span>
            <span>Google</span>
            <span className="border border-gray-600 text-gray-400 rounded px-1 font-bold ml-1">W</span>
            <span>Wikipedia</span>
            <span className="border border-orange-800 text-orange-400 rounded px-1 font-bold ml-1">R</span>
            <span>Reddit</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMode("default")}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "default"
                ? "border-gray-600 text-gray-300 bg-gray-800"
                : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            Default
          </button>
          <button
            onClick={handleScramble}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "scramble"
                ? "border-amber-700 text-amber-400 bg-amber-950/40"
                : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            🔀 Scramble
          </button>
          <button
            onClick={() => setMode("anomaly")}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
              mode === "anomaly"
                ? "border-purple-700 text-purple-400 bg-purple-950/40"
                : "border-gray-800 text-gray-600 hover:text-gray-400"
            }`}
          >
            ⚡ Anomaly
          </button>
        </div>
      </div>

      {/* Anomaly mode */}
      {mode === "anomaly" && (
        <div>
          {anomalyLoading ? (
            <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4">
              {[1, 2, 3].map(i => <div key={i} className="flex-shrink-0 w-64 h-52 bg-gray-900 rounded-xl animate-pulse" />)}
            </div>
          ) : anomalies.length === 0 ? (
            <p className="text-sm text-gray-600 py-4">No anomalies detected right now — everything is trending normally.</p>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-4 scrollbar-none -mx-4 px-4">
              {anomalies.map(t => (
                <div key={t.id} className="flex-shrink-0 w-64 flex flex-col gap-1.5">
                  <AnomalyLabel trend={t} />
                  <TrendCard trend={t} onClick={() => onSelect(t.id)} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Default / Scramble mode */}
      {mode !== "anomaly" && (
        <div className="flex gap-3 overflow-x-auto pb-4 scrollbar-none -mx-4 px-4">
          {displayItems.map(item =>
            item.type === "cluster" ? (
              <ClusterStack key={`cluster-${item.data.id}`} cluster={item.data} onSelect={onSelect} />
            ) : (
              <div key={item.data.id} className="flex-shrink-0 w-64">
                <TrendCard trend={item.data} onClick={() => onSelect(item.data.id)} />
              </div>
            )
          )}
        </div>
      )}
    </section>
  );
}
