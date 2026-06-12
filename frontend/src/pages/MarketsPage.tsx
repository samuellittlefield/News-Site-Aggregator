import { Market, useMarketHistory, useMarkets } from "../api/client";
import { MiniSparkline } from "../components/dashboard/MiniSparkline";

function fmtVolume(v: number | null): string {
  if (v === null) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function MarketCard({ market }: { market: Market }) {
  const { history } = useMarketHistory(market.id);
  const prices = history.map(h => h.yes_price).filter((p): p is number => p !== null);
  const pct = market.yes_price !== null ? Math.round(market.yes_price * 100) : null;

  return (
    <a
      href={market.url ?? undefined}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-600 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-200 leading-snug flex-1">{market.question}</p>
        {pct !== null && (
          <span className={`text-lg font-bold font-mono ${pct >= 50 ? "text-emerald-400" : "text-gray-400"}`}>
            {pct}%
          </span>
        )}
      </div>
      <div className="flex items-center justify-between mt-3">
        <p className="text-xs text-gray-600">
          24h vol {fmtVolume(market.volume_24h)}
          {market.end_date && (
            <span> · ends {new Date(market.end_date).toLocaleDateString([], { month: "short", day: "numeric" })}</span>
          )}
        </p>
        {prices.length >= 2 && <MiniSparkline values={prices} />}
      </div>
    </a>
  );
}

export function MarketsPage() {
  const { markets, loading } = useMarkets(40);

  // Group by event title for multi-outcome questions
  const groups = new Map<string, Market[]>();
  for (const m of markets) {
    const key = m.event_title ?? m.question;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-gray-200">Prediction Markets</h1>
        <p className="text-xs text-gray-600 mt-1">
          Top politics markets by 24h volume · Polymarket · refreshed every 10 minutes
        </p>
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-28 bg-gray-900 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : markets.length === 0 ? (
        <p className="text-gray-600">No market data yet — the first refresh may still be running.</p>
      ) : (
        <div className="space-y-8">
          {Array.from(groups.entries()).map(([title, group]) => (
            <section key={title}>
              {group.length > 1 && (
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{title}</h2>
              )}
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
                {group.map(m => <MarketCard key={m.id} market={m} />)}
              </div>
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
