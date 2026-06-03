import { GenericBallot, HousePoll } from "../api/client";

const GRADE_STYLES: Record<string, string> = {
  "A+": "bg-emerald-900 text-emerald-300 border-emerald-700",
  "A":  "bg-emerald-900 text-emerald-400 border-emerald-800",
  "A-": "bg-teal-900   text-teal-300    border-teal-700",
  "B+": "bg-blue-900   text-blue-300    border-blue-700",
  "B":  "bg-blue-900   text-blue-400    border-blue-800",
  "B-": "bg-yellow-900 text-yellow-300  border-yellow-700",
  "C+": "bg-orange-900 text-orange-300  border-orange-700",
  "C":  "bg-orange-900 text-orange-400  border-orange-800",
  "C-": "bg-red-900    text-red-400     border-red-800",
  "D":  "bg-red-950    text-red-500     border-red-900",
};

function PollCard({ poll }: { poll: HousePoll }) {
  const margin = poll.dem != null && poll.rep != null ? poll.dem - poll.rep : null;
  const demPct = poll.dem ?? 0;
  const repPct = poll.rep ?? 0;
  const total = demPct + repPct || 100;
  const gradeStyle = poll.grade ? GRADE_STYLES[poll.grade] ?? "bg-gray-800 text-gray-400 border-gray-700" : "";

  return (
    <div className="w-full h-full bg-gray-900 border border-gray-800 rounded-xl p-2.5 flex flex-col justify-between gap-1.5">
      <div className="flex items-start justify-between gap-1">
        <span className="text-xs font-bold text-white">{poll.state}-{poll.district}</span>
        {poll.grade && (
          <span className={`text-[9px] font-bold border rounded px-1 py-px ${gradeStyle}`}>
            {poll.grade}
          </span>
        )}
      </div>
      <p className="text-[10px] text-gray-400 truncate">{poll.pollster}</p>
      {/* D/R split bar */}
      <div className="h-1.5 rounded-full overflow-hidden flex">
        <div className="bg-red-600" style={{ width: `${(repPct / total) * 100}%` }} />
        <div className="bg-blue-600" style={{ width: `${(demPct / total) * 100}%` }} />
      </div>
      <div className="flex items-center justify-between text-[9px]">
        <span className="text-red-400">R {poll.rep?.toFixed(0)}%</span>
        <span className={margin != null ? (margin > 0 ? "text-blue-400" : "text-red-400") : "text-gray-600"}>
          {margin != null ? (margin > 0 ? `D+${margin.toFixed(1)}` : `R+${(-margin).toFixed(1)}`) : "—"}
        </span>
        <span className="text-blue-400">D {poll.dem?.toFixed(0)}%</span>
      </div>
      {poll.end_date && (
        <p className="text-[9px] text-gray-600">
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
    <div className="w-full h-full bg-gray-900 border border-gray-800 rounded-xl p-2.5 flex flex-col justify-between gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-gray-500 uppercase tracking-wider">Generic Ballot</span>
        <span className="text-[9px] bg-gray-800 text-gray-400 border border-gray-700 rounded px-1">Avg</span>
      </div>
      <p className="text-[10px] text-gray-300 truncate">{b.source.replace(/\[\[|\]\]/g, "").split("|")[0]}</p>
      <div className="h-1.5 rounded-full overflow-hidden flex">
        <div className="bg-red-600" style={{ width: `${(b.rep / total) * 100}%` }} />
        <div className="bg-blue-600" style={{ width: `${(b.dem / total) * 100}%` }} />
      </div>
      <div className="flex items-center justify-between text-[9px]">
        <span className="text-red-400">R {b.rep.toFixed(1)}%</span>
        <span className={margin > 0 ? "text-blue-400" : "text-red-400"}>
          {margin > 0 ? `D+${margin.toFixed(1)}` : `R+${(-margin).toFixed(1)}`}
        </span>
        <span className="text-blue-400">D {b.dem.toFixed(1)}%</span>
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
        <p className="text-[10px] text-gray-600 mb-2">
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
