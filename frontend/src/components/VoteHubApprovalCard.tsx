import { useEconQuestions, useVoteHubApproval } from "../api/client";
import { MiniSparkline } from "./dashboard/MiniSparkline";

export function VoteHubApprovalCard() {
  const { data, loading } = useVoteHubApproval();
  const { questions } = useEconQuestions();

  if (loading) {
    return <div className="h-28 bg-glass-panel-nested rounded-2xl animate-pulse" />;
  }
  const avg = data?.average ?? null;
  if (!avg) return null;

  const econNet = questions.find(q => q.key === "trump_approval")?.latest_net ?? null;
  // Poll-by-poll net values, oldest → newest, for the sparkline
  const nets = [...(data?.polls ?? [])]
    .filter(p => p.approve !== null && p.disapprove !== null)
    .reverse()
    .map(p => (p.approve as number) - (p.disapprove as number));

  return (
    <div className="bg-glass-panel backdrop-blur-lg border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-ink-muted uppercase tracking-wider">Trump Approval — VoteHub Live Average</p>
        <p className="text-[10px] text-ink-muted">{avg.n_polls} polls · last {avg.window_days} days</p>
      </div>
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
