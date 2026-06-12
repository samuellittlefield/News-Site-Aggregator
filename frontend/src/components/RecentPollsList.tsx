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
    <div className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        isApproval ? "bg-violet-900/50 text-violet-300" : "bg-blue-900/50 text-blue-300"
      }`}>
        {isApproval ? "APPROVAL" : "GENERIC"}
      </span>
      <span className="flex-1 text-gray-300 truncate">
        {poll.pollster}
        {poll.sponsors.length > 0 && <span className="text-gray-600"> / {poll.sponsors[0]}</span>}
      </span>
      <span className="text-xs text-gray-600 hidden sm:inline">{fmtDates(poll)}</span>
      {poll.sample_size && (
        <span className="text-xs text-gray-600 hidden md:inline">
          n={poll.sample_size.toLocaleString()}{poll.population ? ` ${poll.population.toUpperCase()}` : ""}
        </span>
      )}
      {isApproval ? (
        <span className="font-mono text-xs">
          <span className="text-emerald-400">{poll.approve?.toFixed(0) ?? "—"}</span>
          <span className="text-gray-600"> / </span>
          <span className="text-red-400">{poll.disapprove?.toFixed(0) ?? "—"}</span>
        </span>
      ) : (
        <span className="font-mono text-xs">
          <span className="text-blue-400">D {poll.dem?.toFixed(0) ?? "—"}</span>
          <span className="text-gray-600"> / </span>
          <span className="text-red-400">R {poll.rep?.toFixed(0) ?? "—"}</span>
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
      <p className="text-xs text-gray-600 uppercase tracking-wider">Latest National Polls — VoteHub</p>
      <div className="space-y-1.5">
        {polls.map(p => <PollRow key={p.votehub_id} poll={p} />)}
      </div>
    </div>
  );
}
