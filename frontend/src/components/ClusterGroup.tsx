import { Trend } from "../api/client";
import { TrendCard } from "./TrendCard";

const CATEGORY_STYLES: Record<string, string> = {
  Sports:        "border-green-800/60 bg-green-950/20",
  Politics:      "border-red-800/60 bg-red-950/20",
  Entertainment: "border-purple-800/60 bg-purple-950/20",
  Technology:    "border-blue-800/60 bg-blue-950/20",
  Business:      "border-yellow-800/60 bg-yellow-950/20",
  Crime:         "border-orange-800/60 bg-orange-950/20",
  Science:       "border-teal-800/60 bg-teal-950/20",
  Culture:       "border-pink-800/60 bg-pink-950/20",
  Other:         "border-gray-700/60 bg-gray-900/20",
};

interface Props {
  name: string;
  category: string | null;
  trends: Trend[];
  onSelect: (id: number) => void;
}

export function ClusterGroup({ name, category, trends, onSelect }: Props) {
  const borderStyle = CATEGORY_STYLES[category ?? "Other"] ?? CATEGORY_STYLES.Other;

  return (
    <div className={`rounded-xl border ${borderStyle} p-4 space-y-3`}>
      <div className="flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-gray-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM14 11a1 1 0 011 1v1h1a1 1 0 110 2h-1v1a1 1 0 11-2 0v-1h-1a1 1 0 110-2h1v-1a1 1 0 011-1z" />
        </svg>
        <span className="text-sm font-semibold text-gray-300">{name}</span>
        <span className="text-xs text-gray-600">{trends.length} related topics</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {trends.map((trend) => (
          <TrendCard key={trend.id} trend={trend} onClick={() => onSelect(trend.id)} />
        ))}
      </div>
    </div>
  );
}
