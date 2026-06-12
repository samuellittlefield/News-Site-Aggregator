import { useTrends } from "../../api/client";
import { Panel } from "./Panel";

const CATEGORY_COLORS: Record<string, string> = {
  Politics: "text-red-400",
  Technology: "text-blue-400",
  Sports: "text-green-400",
  Entertainment: "text-purple-400",
  Business: "text-amber-400",
};

interface Props {
  onOpen: () => void;
  onSelectTrend: (id: number) => void;
}

export function TrendsPanel({ onOpen, onSelectTrend }: Props) {
  const { trends, loading } = useTrends();
  const top = trends.slice(0, 6);

  return (
    <Panel title="Trending" icon="📈" meta={loading ? "" : `${trends.length} active`} onOpen={onOpen}>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-9 bg-gray-800/50 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <ul className="space-y-1">
          {top.map((t, i) => (
            <li
              key={t.id}
              onClick={(e) => { e.stopPropagation(); onSelectTrend(t.id); }}
              className="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-gray-800 transition-colors"
            >
              <span className="text-xs text-gray-600 font-mono w-4 text-right">{i + 1}</span>
              <span className="flex-1 text-sm text-gray-200 truncate">{t.title}</span>
              {t.category && (
                <span className={`text-[10px] uppercase tracking-wide ${CATEGORY_COLORS[t.category] ?? "text-gray-500"}`}>
                  {t.category}
                </span>
              )}
              {t.rank_velocity > 0 && <span className="text-xs text-emerald-400">▲{t.rank_velocity}</span>}
              {t.rank_velocity < 0 && <span className="text-xs text-gray-600">▼{Math.abs(t.rank_velocity)}</span>}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
