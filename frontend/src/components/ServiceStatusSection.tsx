import { useServiceStatus } from "../api/client";

const INDICATOR_STYLES: Record<string, { dot: string; text: string; bg: string; border: string }> = {
  none:     { dot: "bg-green-500",  text: "text-green-400",  bg: "bg-green-950/20",  border: "border-gray-800" },
  minor:    { dot: "bg-yellow-400", text: "text-yellow-400", bg: "bg-yellow-950/30", border: "border-yellow-800/60" },
  major:    { dot: "bg-orange-500", text: "text-orange-400", bg: "bg-orange-950/30", border: "border-orange-800/60" },
  critical: { dot: "bg-red-500",    text: "text-red-400",    bg: "bg-red-950/30",    border: "border-red-800/60" },
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 2) return "just now";
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export function ServiceStatusSection() {
  const { services, loading } = useServiceStatus();

  if (loading || services.length === 0) return null;

  const incidents = services.filter(s => s.indicator !== "none");
  const allGreen = incidents.length === 0;

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          {allGreen
            ? <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
            : <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
              </>
          }
        </span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Internet Health
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          {allGreen
            ? `All ${services.length} services operational`
            : `${incidents.length} service${incidents.length > 1 ? "s" : ""} affected`}
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">
        {services.map(svc => {
          const style = INDICATOR_STYLES[svc.indicator] ?? INDICATOR_STYLES.none;
          return (
            <a
              key={svc.id}
              href={svc.page_url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex-shrink-0 w-44 ${style.bg} border ${style.border} rounded-xl p-3 flex flex-col gap-2 hover:border-gray-600 transition-colors`}
            >
              <div className="flex items-center justify-between">
                <span className="text-base leading-none">{svc.icon}</span>
                <span className={`relative flex h-2 w-2`}>
                  {svc.indicator !== "none" && (
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${style.dot} opacity-75`} />
                  )}
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${style.dot}`} />
                </span>
              </div>
              <p className="text-sm font-semibold text-white">{svc.name}</p>
              <p className={`text-xs ${svc.indicator === "none" ? "text-gray-500" : style.text} line-clamp-2 leading-relaxed`}>
                {svc.description || "Operational"}
              </p>
              <p className="text-xs text-gray-600 mt-auto">{timeAgo(svc.fetched_at)}</p>
            </a>
          );
        })}
      </div>
    </section>
  );
}
