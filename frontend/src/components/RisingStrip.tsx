import { Trend, useRisingTrends } from "../api/client";

const CATEGORY_STYLES: Record<string, string> = {
  Sports:        "bg-green-950 text-green-400 border-green-800",
  Politics:      "bg-red-950 text-red-400 border-red-800",
  Entertainment: "bg-purple-950 text-purple-400 border-purple-800",
  Technology:    "bg-blue-950 text-blue-400 border-blue-800",
  Business:      "bg-yellow-950 text-yellow-500 border-yellow-800",
  Crime:         "bg-orange-950 text-orange-400 border-orange-800",
  Science:       "bg-teal-950 text-teal-400 border-teal-800",
  Culture:       "bg-pink-950 text-pink-400 border-pink-800",
  Other:         "bg-gray-800 text-gray-400 border-gray-700",
};

function formatVelocity(rankVel: number, absVel: number, pct: number): string {
  if (rankVel > 0) {
    return `↑ ${rankVel} spot${rankVel !== 1 ? "s" : ""}`;
  }
  const sign = absVel > 0 ? "+" : "";
  const absStr = absVel >= 1000 ? `${(absVel / 1000).toFixed(1)}K` : String(absVel);
  return `${sign}${absStr} (${sign}${pct}%)`;
}

interface CardProps {
  trend: Trend;
  onClick: () => void;
}

function RisingCard({ trend, onClick }: CardProps) {
  const catStyle = CATEGORY_STYLES[trend.category ?? "Other"] ?? CATEGORY_STYLES.Other;

  return (
    <button
      onClick={onClick}
      className="group flex-shrink-0 w-56 text-left bg-gray-900 hover:bg-gray-800 border border-amber-900/40 hover:border-amber-600/60 rounded-xl p-4 transition-all duration-150 flex flex-col gap-2"
    >
      <div className="flex items-center justify-between gap-2">
        {trend.rank_velocity > 0 || trend.velocity_abs > 0 ? (
          <span className="text-xs font-bold text-amber-400 flex items-center gap-1">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
            {formatVelocity(trend.rank_velocity, trend.velocity_abs, trend.velocity_pct)}
          </span>
        ) : (
          <span className="text-xs font-bold text-orange-400 flex items-center gap-1.5">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-orange-500" />
            </span>
            Just broke in
          </span>
        )}
        {trend.traffic_volume && (
          <span className="text-xs text-gray-500">{trend.traffic_volume}</span>
        )}
      </div>

      <p className="font-semibold text-white text-sm leading-snug group-hover:text-amber-300 transition-colors line-clamp-2">
        {trend.title}
      </p>

      {trend.category && (
        <span className={`self-start text-xs font-medium border rounded-full px-2 py-0.5 ${catStyle}`}>
          {trend.category}
        </span>
      )}
    </button>
  );
}

interface Props {
  onSelect: (id: number) => void;
}

export function RisingStrip({ onSelect }: Props) {
  const { rising, loading } = useRisingTrends();

  if (loading || rising.length === 0) return null;

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
        </span>
        <h2 className="text-sm font-semibold text-amber-400 uppercase tracking-wider">
          Rising Fast
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          biggest jumps since last refresh
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none">
        {rising.map((trend) => (
          <RisingCard key={trend.id} trend={trend} onClick={() => onSelect(trend.id)} />
        ))}
      </div>
    </section>
  );
}
