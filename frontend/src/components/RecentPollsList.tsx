import { useVoteHubApproval, useVoteHubGenericBallot, VoteHubPoll } from "../api/client";

function fmtDates(p: VoteHubPoll): string {
  const fmt = (s: string) => new Date(s).toLocaleDateString([], { month: "short", day: "numeric" });
  if (p.start_date && p.end_date) return `${fmt(p.start_date)}–${fmt(p.end_date)}`;
  if (p.end_date) return fmt(p.end_date);
  return "—";
}

function PollRow({ poll }: { poll: VoteHubPoll }) {
  const isApproval = poll.poll_type === "approval";
  return (
    <div className="flex items-center gap-3 bg-glass-panel border border-glass-border-soft rounded-[14px] shadow-[0_2px_8px_rgba(74,61,112,0.06)] px-3 py-2 text-sm">
      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        isApproval ? "bg-poll-purple-bg text-poll-purple" : "bg-blue-100 text-poll-blue"
      }`}>
        {isApproval ? "APPROVAL" : "GENERIC"}
      </span>
      <span className="flex-1 text-ink truncate">
        {poll.pollster}
        {poll.sponsors.length > 0 && <span className="text-ink-muted"> / {poll.sponsors[0]}</span>}
      </span>
      <span className="text-xs text-ink-muted hidden sm:inline">{fmtDates(poll)}</span>
      {poll.sample_size && (
        <span className="text-xs text-ink-muted hidden md:inline">
          n={poll.sample_size.toLocaleString()}{poll.population ? ` ${poll.population.toUpperCase()}` : ""}
        </span>
      )}
      {isApproval ? (
        <span className="font-mono text-xs">
          <span className="text-poll-positive">{poll.approve?.toFixed(0) ?? "—"}</span>
          <span className="text-ink-muted"> / </span>
          <span className="text-poll-red">{poll.disapprove?.toFixed(0) ?? "—"}</span>
        </span>
      ) : (
        <span className="font-mono text-xs">
          <span className="text-poll-blue">D {poll.dem?.toFixed(0) ?? "—"}</span>
          <span className="text-ink-muted"> / </span>
          <span className="text-poll-red">R {poll.rep?.toFixed(0) ?? "—"}</span>
        </span>
      )}
    </div>
  );
}

export function RecentPollsList() {
  const { data: approval } = useVoteHubApproval();
  const { data: generic } = useVoteHubGenericBallot();

  // Interleave both types, newest first
  const polls = [...(approval?.polls ?? []), ...(generic?.polls ?? [])]
    .sort((a, b) => (b.end_date ?? "").localeCompare(a.end_date ?? ""))
    .slice(0, 15);

  if (polls.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs text-ink-muted uppercase tracking-wider">Latest National Polls — VoteHub</p>
      <div className="space-y-1.5">
        {polls.map(p => <PollRow key={p.votehub_id} poll={p} />)}
      </div>
    </div>
  );
}
