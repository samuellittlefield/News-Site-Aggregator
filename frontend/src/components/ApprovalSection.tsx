import { EconBlock, useEconCrosstab, useEconTrend } from "../api/client";

// Source labels come space-stripped from the PDF text layer; map the recurring
// approval rows back to readable text.
const LABELS: Record<string, string> = {
  Approve: "Approve",
  Disapprove: "Disapprove",
  Stronglyapprove: "Strongly approve",
  Somewhatapprove: "Somewhat approve",
  Somewhatdisapprove: "Somewhat disapprove",
  Stronglydisapprove: "Strongly disapprove",
  Notsure: "Not sure",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Pull the Dem / Ind / Rep "Approve" values from the party-ID demographic block. */
function partyApproval(block: EconBlock | undefined): { dem: number; ind: number; rep: number } | null {
  if (!block) return null;
  const demIdx = block.columns.indexOf("Dem");
  const approve = block.rows["Approve"];
  if (demIdx < 0 || !approve) return null;
  return { dem: approve[demIdx], ind: approve[demIdx + 1], rep: approve[demIdx + 2] };
}

function NetSparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const range = max - min || 1;
  const w = 120, h = 28;
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");
  const zeroY = h - ((0 - min) / range) * h;
  return (
    <svg width={w} height={h} className="overflow-visible">
      <line x1="0" y1={zeroY} x2={w} y2={zeroY} stroke="#374151" strokeWidth="1" strokeDasharray="2 2" />
      <polyline points={pts} fill="none" stroke="#a78bfa" strokeWidth="1.5" />
    </svg>
  );
}

export function ApprovalSection() {
  const { points, loading } = useEconTrend("trump_approval");
  const { crosstab } = useEconCrosstab("trump_approval");

  if (loading || points.length === 0) return null;

  const latest = points[points.length - 1];
  const net = latest.net;
  const approve = latest.topline["Approve"];
  const disapprove = latest.topline["Disapprove"];
  const netSeries = points.map(p => p.net ?? 0);
  const party = partyApproval(crosstab?.blocks[1]);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Presidential Approval
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          Economist/YouGov · {fmtDate(latest.end_date)}
          {latest.sample_size ? ` · n=${latest.sample_size.toLocaleString()}` : ""}
        </span>
      </div>

      <div className="border border-gray-800 rounded-xl p-4 flex flex-col sm:flex-row gap-6 sm:items-center">
        {/* Net approval headline */}
        <div className="flex items-center gap-4">
          <div>
            <div className={`text-3xl font-bold ${net != null && net >= 0 ? "text-green-400" : "text-red-400"}`}>
              {net != null ? `${net > 0 ? "+" : ""}${net}` : "—"}
            </div>
            <div className="text-xs text-gray-500 uppercase tracking-wide">Net approval</div>
          </div>
          <div className="text-sm text-gray-400 leading-relaxed">
            <div><span className="text-green-400 font-semibold">{approve}%</span> approve</div>
            <div><span className="text-red-400 font-semibold">{disapprove}%</span> disapprove</div>
          </div>
        </div>

        {/* Net trend sparkline */}
        <div className="flex flex-col gap-1">
          <NetSparkline values={netSeries} />
          <span className="text-xs text-gray-600">Net over last {points.length} polls</span>
        </div>

        {/* Approve by party */}
        {party && (
          <div className="flex gap-4 sm:ml-auto">
            {([["Dem", party.dem, "bg-blue-500"], ["Ind", party.ind, "bg-purple-400"], ["Rep", party.rep, "bg-red-500"]] as const).map(
              ([label, val, color]) => (
                <div key={label} className="flex flex-col items-center gap-1 w-14">
                  <div className="h-20 w-6 bg-gray-800 rounded relative overflow-hidden flex items-end">
                    <div className={`${color} w-full`} style={{ height: `${val}%` }} />
                  </div>
                  <span className="text-sm font-semibold text-white">{val}%</span>
                  <span className="text-xs text-gray-500">{label}</span>
                </div>
              )
            )}
          </div>
        )}
      </div>
      {party && (
        <p className="text-xs text-gray-600">Approval among partisans · {LABELS.Approve} share by party ID</p>
      )}
    </section>
  );
}
