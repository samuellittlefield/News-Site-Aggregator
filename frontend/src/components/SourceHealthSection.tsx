import { useSourceRuns, type SourceRun } from "../api/client";

/** Health of our *own* scheduled ingestion jobs (distinct from third-party
 *  "Internet Health" in ServiceStatusSection). Flags a source when its latest
 *  run failed, or when its last success is older than that source's own expected
 *  cadence (AC-7), and surfaces the last error inline (AC-8). */

type Health = "ok" | "stale" | "failure" | "never_run";

const STYLES: Record<Health, { dot: string; text: string; bg: string; border: string }> = {
  ok:        { dot: "bg-green-500",  text: "text-gray-500",   bg: "bg-green-950/20",  border: "border-gray-800" },
  stale:     { dot: "bg-yellow-400", text: "text-yellow-400", bg: "bg-yellow-950/30", border: "border-yellow-800/60" },
  failure:   { dot: "bg-red-500",    text: "text-red-400",    bg: "bg-red-950/30",    border: "border-red-800/60" },
  never_run: { dot: "bg-gray-600",   text: "text-gray-500",   bg: "bg-gray-900/40",   border: "border-gray-800" },
};

function minutesSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 60000;
}

function timeAgo(iso: string): string {
  const m = Math.floor(minutesSince(iso));
  if (m < 2) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function classify(s: SourceRun): Health {
  if (s.status === "failure") return "failure";
  if (s.status === "never_run" || !s.last_success_at) return "never_run";
  // Flagged stale once the last good run is older than this source's cadence.
  if (minutesSince(s.last_success_at) > s.cadence_minutes) return "stale";
  return "ok";
}

function statusLabel(s: SourceRun, health: Health): string {
  if (health === "never_run") return "never run";
  if (health === "failure") {
    // Show how stale the last *good* data is, if we ever had any.
    return s.last_success_at ? `failing · good data ${timeAgo(s.last_success_at)}` : "failing";
  }
  const rel = s.last_success_at ? timeAgo(s.last_success_at) : "—";
  return health === "stale" ? `stale · ${rel}` : rel;
}

export function SourceHealthSection() {
  const { sources, loading } = useSourceRuns();

  if (loading || sources.length === 0) return null;

  const flagged = sources.filter(s => {
    const h = classify(s);
    return h === "failure" || h === "stale";
  });
  const allHealthy = flagged.length === 0;

  // Problem sources first, then alphabetical by label.
  const order: Record<Health, number> = { failure: 0, stale: 1, never_run: 2, ok: 3 };
  const sorted = [...sources].sort((a, b) => {
    const d = order[classify(a)] - order[classify(b)];
    return d !== 0 ? d : a.label.localeCompare(b.label);
  });

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          {allHealthy
            ? <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
            : <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
              </>
          }
        </span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Data Sources
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          {allHealthy
            ? `All ${sources.length} sources current`
            : `${flagged.length} source${flagged.length > 1 ? "s" : ""} need attention`}
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
        {sorted.map(src => {
          const health = classify(src);
          const style = STYLES[health];
          const flaggedCard = health === "failure" || health === "stale";
          return (
            <div
              key={src.source_id}
              className={`flex-shrink-0 w-52 ${style.bg} border ${style.border} rounded-xl p-3 flex flex-col gap-2`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white truncate">{src.label}</p>
                <span className="relative flex h-2 w-2 flex-shrink-0">
                  {flaggedCard && (
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${style.dot} opacity-75`} />
                  )}
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${style.dot}`} />
                </span>
              </div>
              <p className={`text-xs ${style.text} leading-relaxed`}>
                {statusLabel(src, health)}
                {src.item_count != null && health === "ok" && (
                  <span className="text-gray-600"> · {src.item_count} items</span>
                )}
              </p>
              {health === "failure" && src.error_message && (
                <p className="text-xs text-red-400/80 line-clamp-2 leading-snug font-mono break-words">
                  {src.error_message.slice(0, 160)}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
