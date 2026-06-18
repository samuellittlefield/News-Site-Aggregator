import { useState } from "react";
import {
  ChamberForecast, ChamberModel, ModelKnobs,
  useCongressForecast, useMarketHistory, useModelSim,
} from "../api/client";
import { MiniSparkline } from "./dashboard/MiniSparkline";
import { ModelControls } from "./ModelControls";

const DEFAULT_KNOBS: ModelKnobs = {
  tau: 3, delta_house: 5, delta_senate: 7, incumbency_adv: 3, senate_prior_blend: 0.5,
};

const PLATFORM_LABEL: Record<string, string> = {
  kalshi: "Kalshi",
  polymarket: "Polymarket",
};

function pct(v: number | null): string {
  return v === null ? "—" : `${Math.round(v * 100)}%`;
}

/** Sparkline of the favored party's market price history, if we have a market id. */
function FavoredTrend({ marketId }: { marketId: number | null }) {
  const { history } = useMarketHistory(marketId ?? 0, 30);
  if (!marketId) return null;
  const values = history.map(h => h.yes_price).filter((v): v is number => v !== null);
  if (values.length < 2) return null;
  return <MiniSparkline values={values} width={120} height={32} />;
}

function ChamberCard({ chamber, model, tuned }: { chamber: ChamberForecast; model: ChamberModel | null; tuned: boolean }) {
  const dem = chamber.dem_prob;
  const rep = chamber.rep_prob;
  const demLeads = (dem ?? 0) >= (rep ?? 0);
  // Track the favored party's market for the trend line.
  const favoredMarketId = chamber.sources.length
    ? (demLeads ? chamber.sources[0].dem_market_id : chamber.sources[0].rep_market_id)
    : null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-400 uppercase tracking-wider">{chamber.title}</p>
        <FavoredTrend marketId={favoredMarketId} />
      </div>

      <div className="flex items-baseline gap-3">
        <span className={`text-4xl font-bold ${demLeads ? "text-blue-400" : "text-red-400"}`}>
          {demLeads ? pct(dem) : pct(rep)}
        </span>
        <span className="text-sm text-gray-400">
          {demLeads ? "Democratic" : "Republican"} control
        </span>
      </div>

      {/* Split probability bar */}
      <div className="flex h-2 rounded-full overflow-hidden mt-3 bg-gray-800">
        <div className="bg-blue-500" style={{ width: `${(dem ?? 0) * 100}%` }} />
        <div className="bg-red-500" style={{ width: `${(rep ?? 0) * 100}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
        <span>D {pct(dem)}</span>
        <span>R {pct(rep)}</span>
      </div>

      {/* Per-source breakdown (markets) */}
      <div className="mt-3 space-y-1 border-t border-gray-800 pt-2">
        <p className="text-[9px] text-gray-600 uppercase tracking-wider">Markets</p>
        {chamber.sources.length === 0 ? (
          <p className="text-[10px] text-gray-600">No market data available.</p>
        ) : (
          chamber.sources.map(s => (
            <a
              key={s.platform}
              href={s.url ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between text-[11px] text-gray-500 hover:text-gray-300"
            >
              <span>{PLATFORM_LABEL[s.platform] ?? s.platform}</span>
              <span className="font-mono">D {pct(s.dem_prob)} · R {pct(s.rep_prob)} ↗</span>
            </a>
          ))
        )}
      </div>

      {/* Our experimental in-house model — separate from the market consensus */}
      {model && (
        <div className="mt-2 border-t border-dashed border-amber-800/40 pt-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-amber-300/90 flex items-center gap-1.5">
              In-house model
              <span className="text-[8px] uppercase tracking-wide bg-amber-900/40 text-amber-400/90 px-1 py-0.5 rounded">
                {tuned ? "tuned" : "experimental"}
              </span>
            </span>
            <span className="font-mono text-[11px] text-gray-400">
              D {pct(model.dem_prob)} · R {pct(model.rep_prob)}
            </span>
          </div>
          <p className="text-[9px] text-gray-600 mt-0.5">
            median {model.median_dem_seats} D seats (90% range {model.p10_dem_seats}–{model.p90_dem_seats})
            {" · "}{model.n_sims.toLocaleString()} sims · {tuned ? "tuned knobs" : "uncalibrated"}
          </p>
        </div>
      )}
    </div>
  );
}

export function ForecastSection() {
  const { forecast, loading } = useCongressForecast();
  const [tuning, setTuning] = useState(false);
  const [knobs, setKnobs] = useState<ModelKnobs>(DEFAULT_KNOBS);
  const { sim, loading: simLoading } = useModelSim(tuning ? knobs : null);

  if (loading) {
    return <div className="h-40 bg-gray-900 rounded-xl animate-pulse" />;
  }
  if (!forecast || forecast.chambers.every(c => c.sources.length === 0)) {
    return null;
  }

  const dirty = (Object.keys(knobs) as (keyof ModelKnobs)[]).some(k => knobs[k] !== DEFAULT_KNOBS[k]);
  // When tuning, use the freshly-simulated model blocks; otherwise the defaults from /congress.
  const modelFor = (chamber: string): ChamberModel | null =>
    tuning && sim ? (chamber === "house" ? sim.house : sim.senate) : null;

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-gray-600 uppercase tracking-wider">2026 Control of Congress — Forecast</p>
          <p className="text-[10px] text-gray-700">
            Market-implied probabilities · prediction markets refreshed every 10 minutes
          </p>
        </div>
        <button
          onClick={() => setTuning(t => !t)}
          className={`text-[10px] px-2 py-1 rounded border whitespace-nowrap ${
            tuning ? "border-amber-700/60 text-amber-300/90 bg-amber-950/20" : "border-gray-800 text-gray-500 hover:text-gray-300"
          }`}
        >
          ⚙ {tuning ? "Tuning model" : "Tune model"}
        </button>
      </div>

      {tuning && (
        <ModelControls
          knobs={knobs}
          onChange={setKnobs}
          onReset={() => setKnobs(DEFAULT_KNOBS)}
          dirty={dirty}
          loading={simLoading}
        />
      )}

      <div className="grid md:grid-cols-2 gap-3">
        {forecast.chambers.map(c => (
          <ChamberCard key={c.chamber} chamber={c} model={modelFor(c.chamber) ?? c.model} tuned={tuning && !!sim} />
        ))}
      </div>

      {/* Model link-outs (cited, not ingested) */}
      {forecast.references.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-gray-600">
          <span className="uppercase tracking-wider">Model forecasts:</span>
          {forecast.references.map(r => (
            <a
              key={r.name}
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              title={r.note}
              className="text-blue-500/80 hover:text-blue-400"
            >
              {r.name} ↗
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
