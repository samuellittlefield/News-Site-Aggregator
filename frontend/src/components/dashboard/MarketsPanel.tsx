import { useMarkets } from "../../api/client";
import { Panel } from "./Panel";

export function MarketsPanel({ onOpen }: { onOpen: () => void }) {
  const { markets, loading } = useMarkets(8);
  const top = markets.slice(0, 5);

  return (
    <Panel title="Prediction Markets" icon="🎲" meta="Polymarket" onOpen={onOpen}>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 bg-gray-800/50 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : top.length === 0 ? (
        <p className="text-sm text-gray-600">No market data yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {top.map((m) => (
            <li key={m.id} className="flex items-center gap-2">
              <span className="flex-1 text-xs text-gray-300 leading-snug line-clamp-2">{m.question}</span>
              {m.yes_price !== null && (
                <span
                  className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded ${
                    m.yes_price >= 0.5 ? "bg-emerald-900/60 text-emerald-300" : "bg-gray-800 text-gray-400"
                  }`}
                >
                  {Math.round(m.yes_price * 100)}%
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
