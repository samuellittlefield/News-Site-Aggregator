import { useEconQuestions, useVoteHubApproval, useVoteHubGenericBallot } from "../../api/client";
import { Panel } from "./Panel";

export function PollsPanel({ onOpen }: { onOpen: () => void }) {
  const { data: approval, loading } = useVoteHubApproval();
  const { data: generic } = useVoteHubGenericBallot();
  const { questions } = useEconQuestions();

  const avg = approval?.average ?? null;
  const gb = generic?.average ?? null;
  const econNet = questions.find(q => q.key === "trump_approval")?.latest_net ?? null;

  return (
    <Panel title="2026 Polling" icon="🗳" meta={avg ? `${avg.n_polls} polls / ${avg.window_days}d` : ""} onOpen={onOpen}>
      {loading ? (
        <div className="h-32 bg-gray-800/50 rounded-lg animate-pulse" />
      ) : (
        <div className="space-y-4">
          {avg && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Trump net approval · VoteHub</p>
              <div className="flex items-baseline gap-2">
                <span className={`text-3xl font-bold ${avg.net < 0 ? "text-red-400" : "text-emerald-400"}`}>
                  {avg.net > 0 ? "+" : ""}{avg.net.toFixed(1)}
                </span>
                <span className="text-xs text-gray-500">
                  {avg.approve.toFixed(0)}% app · {avg.disapprove.toFixed(0)}% dis
                </span>
              </div>
              {econNet !== null && (
                <p className="text-[11px] text-gray-600 mt-0.5">
                  Econ/YouGov net {econNet > 0 ? "+" : ""}{econNet.toFixed(1)}
                  {" · "}Δ {(avg.net - econNet).toFixed(1)}
                </p>
              )}
            </div>
          )}

          {gb && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Generic ballot · VoteHub avg</p>
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
              </p>
            </div>
          )}

          {!avg && !gb && <p className="text-sm text-gray-600">No polling data yet.</p>}
        </div>
      )}
    </Panel>
  );
}
