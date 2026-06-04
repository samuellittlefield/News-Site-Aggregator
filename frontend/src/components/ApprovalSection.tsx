import { useState } from "react";
import {
  EconBlock,
  useEconCrosstab,
  useEconQuestions,
  useEconTrend,
} from "../api/client";
import { prettyGroup, prettyLabel } from "../lib/econLabels";

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Pick the primary positive/negative rows for the headline + party bars.
// Approval questions use Approve/Disapprove; "Direction of Country" uses
// right-direction / wrong-track.
function primaryPair(keys: string[]): { pos?: string; neg?: string } {
  if (keys.includes("Approve") && keys.includes("Disapprove")) {
    return { pos: "Approve", neg: "Disapprove" };
  }
  const right = keys.find((k) => k.toLowerCase().includes("rightdirection"));
  const wrong = keys.find((k) => k.toLowerCase().includes("wrongtrack"));
  if (right && wrong) return { pos: right, neg: wrong };
  return {};
}

/** Values for the primary positive row, broken out by Dem / Ind / Rep. */
function partyBreakdown(block: EconBlock | undefined, posKey: string | undefined) {
  if (!block || !posKey) return null;
  const demIdx = block.columns.indexOf("Dem");
  const row = block.rows[posKey];
  if (demIdx < 0 || !row) return null;
  return { dem: row[demIdx], ind: row[demIdx + 1], rep: row[demIdx + 2] };
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

// Stacked strong/somewhat intensity bar (approval questions only).
function GradientBar({ topline }: { topline: Record<string, number> }) {
  const segs = [
    { key: "Stronglyapprove", color: "#16a34a" },
    { key: "Somewhatapprove", color: "#86efac" },
    { key: "Somewhatdisapprove", color: "#fca5a5" },
    { key: "Stronglydisapprove", color: "#dc2626" },
  ];
  if (!segs.every((s) => s.key in topline)) return null;
  const total = segs.reduce((sum, s) => sum + topline[s.key], 0) || 100;
  return (
    <div className="flex flex-col gap-1 min-w-[200px]">
      <div className="flex h-5 rounded overflow-hidden">
        {segs.map((s) => (
          <div
            key={s.key}
            style={{ width: `${(topline[s.key] / total) * 100}%`, backgroundColor: s.color }}
            title={`${prettyLabel(s.key)} ${topline[s.key]}%`}
            className="flex items-center justify-center"
          >
            <span className="text-[10px] font-semibold text-gray-900/80">{topline[s.key]}</span>
          </div>
        ))}
      </div>
      <span className="text-xs text-gray-600">Strong ↔ somewhat intensity</span>
    </div>
  );
}

function CrosstabGrid({ block }: { block: EconBlock }) {
  const rowLabels = Object.keys(block.rows);
  return (
    <div className="space-y-1">
      <p className="text-xs text-gray-500 font-medium">{prettyGroup(block.group_line)}</p>
      <div className="overflow-x-auto">
        <table className="text-xs border-collapse">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left font-medium pr-3 py-1 sticky left-0 bg-gray-950" />
              {block.columns.map((c, i) => (
                <th key={i} className="px-2 py-1 text-right font-medium whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowLabels.map((label) => (
              <tr key={label} className="border-t border-gray-800/50">
                <td className="text-left text-gray-300 pr-3 py-1 whitespace-nowrap sticky left-0 bg-gray-950">
                  {prettyLabel(label)}
                </td>
                {block.rows[label].map((v, i) => (
                  <td key={i} className="px-2 py-1 text-right text-gray-400 tabular-nums">{v}%</td>
                ))}
              </tr>
            ))}
            {Object.keys(block.ns).length > 0 && (
              <tr className="border-t border-gray-800">
                <td className="text-left text-gray-600 pr-3 py-1 whitespace-nowrap sticky left-0 bg-gray-950">
                  Unweighted N
                </td>
                {block.columns.map((c, i) => (
                  <td key={i} className="px-2 py-1 text-right text-gray-600 tabular-nums">
                    {block.ns[c]?.toLocaleString() ?? ""}
                  </td>
                ))}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ApprovalSection() {
  const { questions } = useEconQuestions();
  const [activeKey, setActiveKey] = useState("trump_approval");
  const [expanded, setExpanded] = useState(false);
  const { points } = useEconTrend(activeKey);
  const { crosstab } = useEconCrosstab(activeKey);

  if (questions.length === 0 || points.length === 0) return null;

  const latest = points[points.length - 1];
  const tl = latest.topline;
  const { pos, neg } = primaryPair(Object.keys(tl));
  const posVal = pos ? tl[pos] : undefined;
  const negVal = neg ? tl[neg] : undefined;
  const net = posVal != null && negVal != null ? posVal - negVal : null;
  const netSeries = points.map((p) => p.net).filter((n): n is number => n != null);
  const party = partyBreakdown(crosstab?.blocks[1], pos);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Approval & Sentiment
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          Economist/YouGov · {fmtDate(latest.end_date)}
          {latest.sample_size ? ` · n=${latest.sample_size.toLocaleString()}` : ""}
        </span>
      </div>

      {/* Question switcher */}
      <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-none">
        {questions.map((q) => (
          <button
            key={q.key}
            onClick={() => { setActiveKey(q.key); setExpanded(false); }}
            className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeKey === q.key
                ? "bg-gray-800 text-white"
                : "text-gray-500 hover:text-gray-300 bg-gray-900/50"
            }`}
          >
            {q.label}
          </button>
        ))}
      </div>

      <div className="border border-gray-800 rounded-xl p-4 flex flex-col sm:flex-row gap-6 sm:items-center">
        {/* Headline */}
        <div className="flex items-center gap-4">
          {net != null && (
            <div>
              <div className={`text-3xl font-bold ${net >= 0 ? "text-green-400" : "text-red-400"}`}>
                {net > 0 ? "+" : ""}{net}
              </div>
              <div className="text-xs text-gray-500 uppercase tracking-wide">Net</div>
            </div>
          )}
          <div className="text-sm text-gray-400 leading-relaxed">
            {pos && <div><span className="text-green-400 font-semibold">{posVal}%</span> {prettyLabel(pos).toLowerCase()}</div>}
            {neg && <div><span className="text-red-400 font-semibold">{negVal}%</span> {prettyLabel(neg).toLowerCase()}</div>}
          </div>
        </div>

        {/* Net trend sparkline */}
        {netSeries.length >= 2 && (
          <div className="flex flex-col gap-1">
            <NetSparkline values={netSeries} />
            <span className="text-xs text-gray-600">Net over last {netSeries.length} polls</span>
          </div>
        )}

        {/* Strong/somewhat intensity */}
        <GradientBar topline={tl} />

        {/* Breakdown by party */}
        {party && (
          <div className="flex gap-4 sm:ml-auto">
            {([["Dem", party.dem, "bg-blue-500"], ["Ind", party.ind, "bg-purple-400"], ["Rep", party.rep, "bg-red-500"]] as const).map(
              ([label, val, color]) => (
                <div key={label} className="flex flex-col items-center gap-1 w-12">
                  <div className="h-16 w-5 bg-gray-800 rounded relative overflow-hidden flex items-end">
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

      {/* Expandable full crosstab */}
      {crosstab && crosstab.blocks.length > 0 && (
        <div className="space-y-3">
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            {expanded ? "▾ Hide full crosstab" : "▸ Show full demographic crosstab"}
          </button>
          {expanded && (
            <div className="border border-gray-800 rounded-xl p-4 space-y-5">
              {crosstab.blocks.map((b, i) => <CrosstabGrid key={i} block={b} />)}
              {crosstab.source_url && (
                <a
                  href={crosstab.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-xs text-purple-400 hover:text-purple-300"
                >
                  Source: Economist/YouGov tab report (PDF) ↗
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
