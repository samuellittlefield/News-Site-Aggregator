import { GenericBallot } from "../api/client";

interface Props {
  ballot: GenericBallot[];
}

export function GenericBallotBar({ ballot }: Props) {
  if (ballot.length === 0) return null;

  // Average across all aggregators
  const avgRep = ballot.reduce((s, b) => s + b.rep, 0) / ballot.length;
  const avgDem = ballot.reduce((s, b) => s + b.dem, 0) / ballot.length;
  const total = avgRep + avgDem;
  const repPct = (avgRep / total) * 100;
  const demPct = (avgDem / total) * 100;
  const margin = avgDem - avgRep;
  const leader = margin > 0 ? "D" : "R";
  const marginAbs = Math.abs(margin).toFixed(1);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span className="font-semibold text-ink uppercase tracking-wider">Generic Ballot</span>
        <span>
          {leader === "D"
            ? <span className="text-poll-blue">Democrats +{marginAbs}</span>
            : <span className="text-poll-red">Republicans +{marginAbs}</span>}
          <span className="text-ink-muted ml-2">· avg of {ballot.length} aggregators</span>
        </span>
      </div>

      {/* Split bar */}
      <div className="relative h-6 rounded-lg overflow-hidden flex">
        <div
          className="flex items-center justify-start pl-2 text-xs font-bold text-white bg-poll-red-bar"
          style={{ width: `${repPct}%` }}
        >
          R {avgRep.toFixed(1)}%
        </div>
        <div
          className="flex items-center justify-end pr-2 text-xs font-bold text-white bg-poll-blue-bar"
          style={{ width: `${demPct}%` }}
        >
          D {avgDem.toFixed(1)}%
        </div>
      </div>

      {/* Individual aggregators */}
      <div className="flex gap-3 overflow-x-auto scrollbar-none pb-1">
        {ballot.map(b => (
          <div key={b.source} className="flex-shrink-0 text-[10px] text-ink-muted flex items-center gap-1">
            <span className="text-ink">{b.source.replace(/\[\[|\]\]/g, "").split("|")[0]}</span>
            <span className="text-poll-red">R{b.rep.toFixed(1)}</span>
            <span className="text-ink-muted">/</span>
            <span className="text-poll-blue">D{b.dem.toFixed(1)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
