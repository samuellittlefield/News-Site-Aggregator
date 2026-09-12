import { useEconQuestions, useVoteHubApproval, useVoteHubGenericBallot } from "../../api/client";
import { Panel } from "./Panel";
import { classifyAverage, fmtFieldworkDate } from "../../lib/pollStaleness";

function StalenessBadge({ stale, thin, nPolls }: { stale: boolean; thin: boolean; nPolls: number }) {
  if (!stale && !thin) return null;
  return (
    <span className="flex items-center gap-1 flex-wrap justify-end">
      {stale && (
        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded text-amber-400 bg-amber-950/40">
          ⚠ stale
        </span>
      )}
      {thin && (
        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded text-purple-300 bg-purple-950/40">
          ◆ {nPolls} poll{nPolls === 1 ? "" : "s"} only
        </span>
      )}
    </span>
  );
}

export function PollsPanel({ onOpen }: { onOpen: () => void }) {
  const { data: approval, loading } = useVoteHubApproval();
  const { data: generic } = useVoteHubGenericBallot();
  const { questions } = useEconQuestions();

  const avg = approval?.average ?? null;
  const gb = generic?.average ?? null;
  const avgStaleness = avg ? classifyAverage(avg.newest_fieldwork_end, avg.n_polls) : null;
  const gbStaleness = gb ? classifyAverage(gb.newest_fieldwork_end, gb.n_polls) : null;
  const econNet = questions.find(q => q.key === "trump_approval")?.latest_net ?? null;

  return (
    <Panel title="2026 Polling" icon="🗳" meta={avg ? `${avg.n_polls} polls / ${avg.window_days}d` : ""} onOpen={onOpen}>
      {loading ? (
        <div className="h-32 bg-gray-800/50 rounded-lg animate-pulse" />
      ) : (
        <div className="space-y-4">
          {avg ? (
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Trump net approval · VoteHub</p>
                <StalenessBadge stale={avgStaleness!.stale} thin={avgStaleness!.thin} nPolls={avg.n_polls} />
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`text-3xl font-bold ${avg.net < 0 ? "text-red-400" : "text-emerald-400"}`}>
                  {avg.net > 0 ? "+" : ""}{avg.net.toFixed(1)}
                </span>
                <span className="text-xs text-gray-500">
                  {avg.approve.toFixed(0)}% app · {avg.disapprove.toFixed(0)}% dis
                </span>
              </div>
              <p className="text-[11px] text-gray-600 mt-0.5">
                {avgStaleness!.newestLabel ? `fieldwork through ${avgStaleness!.newestLabel}` : ""}
                {econNet !== null && (
                  <> · Econ/YouGov net {econNet > 0 ? "+" : ""}{econNet.toFixed(1)}
                  {" · "}Δ {(avg.net - econNet).toFixed(1)}</>
                )}
              </p>
            </div>
          ) : (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Trump net approval · VoteHub</p>
              <p className="text-xs text-gray-600">
                No approval polling in the last 21 days.
                {approval?.polls?.[0]?.end_date
                  ? ` Last: ${fmtFieldworkDate(approval.polls[0].end_date)}.`
                  : ""}
              </p>
            </div>
          )}

          {gb ? (
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Generic ballot · VoteHub avg</p>
                <StalenessBadge stale={gbStaleness!.stale} thin={gbStaleness!.thin} nPolls={gb.n_polls} />
              </div>
              <div className="h-5 rounded-full overflow-hidden flex text-[10px] font-semibold leading-5">
                <div
                  className="bg-blue-600 text-blue-100 pl-2"
                  style={{ width: `${(gb.dem / (gb.dem + gb.rep)) * 100}%` }}
                >
                  D {gb.dem.toFixed(1)}
                </div>
                <div
                  className="bg-red-600 text-red-100 pr-2 text-right flex-1"
                >
                  R {gb.rep.toFixed(1)}
                </div>
              </div>
              <p className="text-[11px] text-gray-600 mt-1">
                {gb.margin > 0 ? "D" : "R"}+{Math.abs(gb.margin).toFixed(1)} · {gb.n_polls} polls
                {gbStaleness!.newestLabel ? ` · fieldwork through ${gbStaleness!.newestLabel}` : ""}
              </p>
            </div>
          ) : (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Generic ballot · VoteHub avg</p>
              <p className="text-xs text-gray-600">
                No generic-ballot polling in the last 21 days.
                {generic?.polls?.[0]?.end_date
                  ? ` Last: ${fmtFieldworkDate(generic.polls[0].end_date)}.`
                  : ""}
              </p>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
