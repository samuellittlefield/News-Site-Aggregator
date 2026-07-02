import { GenericBallot, HousePoll } from "../api/client";

const GRADE_STYLES: Record<string, string> = {
  "A+": "bg-emerald-100 text-emerald-700 border-emerald-300",
  "A":  "bg-emerald-100 text-emerald-600 border-emerald-300",
  "A-": "bg-teal-100    text-teal-700    border-teal-300",
  "B+": "bg-blue-100    text-blue-700    border-blue-300",
  "B":  "bg-blue-100    text-blue-600    border-blue-300",
  "B-": "bg-yellow-100  text-yellow-700  border-yellow-300",
  "C+": "bg-orange-100  text-orange-700  border-orange-300",
  "C":  "bg-orange-100  text-orange-600  border-orange-300",
  "C-": "bg-red-100     text-red-700     border-red-300",
  "D":  "bg-red-200     text-red-800     border-red-400",
};

function PollCard({ poll }: { poll: HousePoll }) {
  const margin = poll.dem != null && poll.rep != null ? poll.dem - poll.rep : null;
  const demPct = poll.dem ?? 0;
  const repPct = poll.rep ?? 0;
  const total = demPct + repPct || 100;
  const gradeStyle = poll.grade ? GRADE_STYLES[poll.grade] ?? "bg-black/5 text-ink-muted border-ink/15" : "";

  return (
    <div className="w-full h-full bg-glass-panel backdrop-blur-lg border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-2.5 flex flex-col justify-between gap-1.5">
      <div className="flex items-start justify-between gap-1">
        <span className="text-xs font-bold text-ink">{poll.state}-{poll.district}</span>
        {poll.grade && (
          <span className={`text-[9px] font-bold border rounded px-1 py-px ${gradeStyle}`}>
            {poll.grade}
          </span>
        )}
      </div>
      <p className="text-[10px] text-ink-muted truncate">{poll.pollster}</p>
      {/* D/R split bar */}
      <div className="h-1.5 rounded-full overflow-hidden flex">
        <div className="bg-poll-red-bar" style={{ width: `${(repPct / total) * 100}%` }} />
        <div className="bg-poll-blue-bar" style={{ width: `${(demPct / total) * 100}%` }} />
      </div>
      <div className="flex items-center justify-between text-[9px]">
        <span className="text-poll-red">R {poll.rep?.toFixed(0)}%</span>
        <span className={margin != null ? (margin > 0 ? "text-poll-blue" : "text-poll-red") : "text-ink-muted"}>
          {margin != null ? (margin > 0 ? `D+${margin.toFixed(1)}` : `R+${(-margin).toFixed(1)}`) : "—"}
        </span>
        <span className="text-poll-blue">D {poll.dem?.toFixed(0)}%</span>
      </div>
      {poll.end_date && (
        <p className="text-[9px] text-ink-muted">
          {new Date(poll.end_date).toLocaleDateString([], { month: "short", day: "numeric" })}
          {poll.sample_size ? ` · n=${poll.sample_size.toLocaleString()}` : ""}
          {poll.population ? ` ${poll.population}` : ""}
        </p>
      )}
    </div>
  );
}

function AggregatorCard({ b }: { b: GenericBallot }) {
  const margin = b.dem - b.rep;
  const total = b.dem + b.rep;
  return (
    <div className="w-full h-full bg-glass-panel backdrop-blur-lg border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-2.5 flex flex-col justify-between gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-ink-muted uppercase tracking-wider">Generic Ballot</span>
        <span className="text-[9px] bg-black/5 text-ink-muted border border-ink/15 rounded px-1">Avg</span>
      </div>
      <p className="text-[10px] text-ink truncate">{b.source.replace(/\[\[|\]\]/g, "").split("|")[0]}</p>
      <div className="h-1.5 rounded-full overflow-hidden flex">
        <div className="bg-poll-red-bar" style={{ width: `${(b.rep / total) * 100}%` }} />
        <div className="bg-poll-blue-bar" style={{ width: `${(b.dem / total) * 100}%` }} />
      </div>
      <div className="flex items-center justify-between text-[9px]">
        <span className="text-poll-red">R {b.rep.toFixed(1)}%</span>
        <span className={margin > 0 ? "text-poll-blue" : "text-poll-red"}>
          {margin > 0 ? `D+${margin.toFixed(1)}` : `R+${(-margin).toFixed(1)}`}
        </span>
        <span className="text-poll-blue">D {b.dem.toFixed(1)}%</span>
      </div>
    </div>
  );
}

interface Props {
  polls: HousePoll[];
  ballot: GenericBallot[];
}

export function PollCarousel({ polls, ballot }: Props) {
  const hasPolls = polls.length > 0;

  return (
    <div>
      {!hasPolls && (
        <p className="text-[10px] text-ink-muted mb-2">
          No district polls yet — showing national generic ballot aggregators.
          Individual polls will appear here as they're published.
        </p>
      )}
      <div className="overflow-x-auto -mx-4 px-4 scrollbar-none">
        <div
          className="grid grid-rows-4 grid-flow-col gap-2"
          style={{ gridAutoColumns: "10rem", gridAutoRows: "5.5rem" }}
        >
          {hasPolls
            ? (polls as HousePoll[]).map(p => (
                <div key={p.poll_id} className="min-w-0">
                  <PollCard poll={p} />
                </div>
              ))
            : (ballot as GenericBallot[]).map((b, i) => (
                <div key={i} className="min-w-0">
                  <AggregatorCard b={b} />
                </div>
              ))
          }
        </div>
      </div>
    </div>
  );
}
