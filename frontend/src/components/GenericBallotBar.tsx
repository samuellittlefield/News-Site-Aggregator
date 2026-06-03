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
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="font-semibold text-gray-300 uppercase tracking-wider">Generic Ballot</span>
        <span>
          {leader === "D"
            ? <span className="text-blue-400">Democrats +{marginAbs}</span>
            : <span className="text-red-400">Republicans +{marginAbs}</span>}
          <span className="text-gray-600 ml-2">· avg of {ballot.length} aggregators</span>
        </span>
      </div>

      {/* Split bar */}
      <div className="relative h-6 rounded-lg overflow-hidden flex">
        <div
          className="flex items-center justify-start pl-2 text-xs font-bold text-white"
          style={{ width: `${repPct}%`, background: "linear-gradient(90deg, #d01428, #e04060)" }}
        >
          R {avgRep.toFixed(1)}%
        </div>
        <div
          className="flex items-center justify-end pr-2 text-xs font-bold text-white"
          style={{ width: `${demPct}%`, background: "linear-gradient(90deg, #4080d0, #1e64dc)" }}
        >
          D {avgDem.toFixed(1)}%
        </div>
      </div>

      {/* Individual aggregators */}
      <div className="flex gap-3 overflow-x-auto scrollbar-none pb-1">
        {ballot.map(b => (
          <div key={b.source} className="flex-shrink-0 text-[10px] text-gray-600 flex items-center gap-1">
            <span className="text-gray-500">{b.source.replace(/\[\[|\]\]/g, "").split("|")[0]}</span>
            <span className="text-red-400">R{b.rep.toFixed(1)}</span>
            <span className="text-gray-700">/</span>
            <span className="text-blue-400">D{b.dem.toFixed(1)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
