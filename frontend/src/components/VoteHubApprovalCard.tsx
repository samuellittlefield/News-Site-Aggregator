import { useEconQuestions, useVoteHubApproval } from "../api/client";
import { MiniSparkline } from "./dashboard/MiniSparkline";
import { classifyAverage, daysSince, fmtFieldworkDate } from "../lib/pollStaleness";

export function VoteHubApprovalCard() {
  const { data, loading } = useVoteHubApproval();
  const { questions } = useEconQuestions();

  if (loading) {
    return <div className="h-28 bg-glass-panel-nested rounded-2xl animate-pulse" />;
  }
  const avg = data?.average ?? null;

  if (!avg) {
    // AC-7/AC-8: never a silent `return null` — say so, and name the last
    // known fieldwork date if there's any poll on record at all.
    const mostRecent = data?.polls?.[0]?.end_date ?? null;
    return (
      <div className="bg-glass-panel backdrop-blur-lg border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-4">
        <p className="text-xs text-ink-muted uppercase tracking-wider mb-2">Trump Approval — VoteHub Live Average</p>
        <p className="text-sm text-ink">
          No polling in the last 21 days.
          {mostRecent
            ? ` Most recent fieldwork ended ${fmtFieldworkDate(mostRecent)}.`
            : " No approval polling on record yet."}
        </p>
      </div>
    );
  }

  const { stale, thin, newestLabel } = classifyAverage(avg.newest_fieldwork_end, avg.n_polls);
  const econNet = questions.find(q => q.key === "trump_approval")?.latest_net ?? null;
  // Poll-by-poll net values, oldest → newest, for the sparkline
  const nets = [...(data?.polls ?? [])]
    .filter(p => p.approve !== null && p.disapprove !== null)
    .reverse()
    .map(p => (p.approve as number) - (p.disapprove as number));

  return (
    <div className="bg-glass-panel backdrop-blur-lg border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-4">
      <div className="flex items-center justify-between mb-2 gap-2">
        <p className="text-xs text-ink-muted uppercase tracking-wider">Trump Approval — VoteHub Live Average</p>
        <p className="text-[10px] text-ink-muted whitespace-nowrap">
          {newestLabel ? `fieldwork through ${newestLabel}` : "no fieldwork date"} · last {avg.window_days} days
        </p>
      </div>
      {stale && (
        <p className="flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-100 border border-amber-300 rounded-lg px-2 py-1 mb-2 w-fit">
          <span aria-hidden>⚠</span> Stale — newest fieldwork {newestLabel}
          {avg.newest_fieldwork_end ? ` (${Math.floor(daysSince(avg.newest_fieldwork_end))}+ days ago)` : ""}
        </p>
      )}
      {thin && (
        <p className="flex items-center gap-1 text-xs font-semibold text-poll-purple bg-poll-purple-bg border border-poll-purple/30 rounded-lg px-2 py-1 mb-2 w-fit">
          <span aria-hidden>◆</span> Based on just {avg.n_polls} poll{avg.n_polls === 1 ? "" : "s"} — not a broad average
        </p>
      )}
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="flex items-baseline gap-3">
            <span className={`text-4xl font-bold ${avg.net < 0 ? "text-poll-red" : "text-poll-positive"}`}>
              {avg.net > 0 ? "+" : ""}{avg.net.toFixed(1)}
            </span>
            <span className="text-sm text-ink-muted">
              {avg.approve.toFixed(1)}% approve · {avg.disapprove.toFixed(1)}% disapprove
            </span>
          </div>
          {econNet !== null && (
            <p className="text-xs text-ink-muted mt-1">
              Cross-check: Economist/YouGov net {econNet > 0 ? "+" : ""}{econNet.toFixed(1)}
              {" · "}delta {(avg.net - econNet) > 0 ? "+" : ""}{(avg.net - econNet).toFixed(1)}
            </p>
          )}
        </div>
        {nets.length >= 2 && (
          <div className="text-right">
            <MiniSparkline values={nets} width={160} height={40} />
            <p className="text-[10px] text-ink-muted mt-0.5">net, last {nets.length} polls</p>
          </div>
        )}
      </div>
    </div>
  );
}
