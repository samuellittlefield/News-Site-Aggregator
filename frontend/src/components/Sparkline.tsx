import { PageView, usePageViews, useTrendHistory } from "../api/client";

interface Props {
  trendId: number;
  wikiTitle?: string;
}

const W = 320;
const H = 80;
const PAD = { top: 10, right: 16, bottom: 22, left: 40 };
const IW = W - PAD.left - PAD.right;
const IH = H - PAD.top - PAD.bottom;

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString([], { month: "short", day: "numeric" });
}

function fmtViews(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}K` : String(n);
}

// ── Page-views sparkline (preferred) ────────────────────────────────────────

function PageViewSparkline({ views }: { views: PageView[] }) {
  if (views.length < 2) return null;

  const vals = views.map((v) => v.views);
  const maxV = Math.max(...vals, 1);
  const minV = Math.min(...vals);
  const peakIdx = vals.indexOf(maxV);

  const x = (i: number) => PAD.left + (i / (views.length - 1)) * IW;
  const y = (v: number) => PAD.top + IH - ((v - minV) / (maxV - minV || 1)) * IH;

  const points = views.map((v, i) => ({ x: x(i), y: y(v.views), ...v }));
  const line = points.map((p) => `${p.x},${p.y}`).join(" ");
  const fill = `M${points[0].x},${PAD.top + IH} ` +
    points.map((p) => `L${p.x},${p.y}`).join(" ") +
    ` L${points[points.length - 1].x},${PAD.top + IH} Z`;

  const last = points[points.length - 1];
  const peak = points[peakIdx];
  const isRising = vals[vals.length - 1] > vals[0];
  const color = isRising ? "#34d399" : "#60a5fa";

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="block" style={{ height: H }}>
      {/* Y-axis labels */}
      <text x={PAD.left - 4} y={PAD.top + 4} textAnchor="end" fontSize={9} fill="#4b5563">
        {fmtViews(maxV)}
      </text>
      <text x={PAD.left - 4} y={PAD.top + IH + 4} textAnchor="end" fontSize={9} fill="#4b5563">
        {fmtViews(minV)}
      </text>

      {/* Baseline */}
      <line x1={PAD.left} x2={W - PAD.right} y1={PAD.top + IH} y2={PAD.top + IH}
        stroke="#1f2937" strokeWidth={1} />

      {/* Fill */}
      <path d={fill} fill={color} fillOpacity={0.1} />

      {/* Line */}
      <polyline points={line} fill="none" stroke={color} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" />

      {/* Peak marker */}
      <circle cx={peak.x} cy={peak.y} r={3} fill={color} />
      <text x={peak.x} y={peak.y - 6} textAnchor="middle" fontSize={8} fill={color}>
        ↑{fmtViews(maxV)}
      </text>

      {/* Latest dot */}
      {peakIdx !== points.length - 1 && (
        <circle cx={last.x} cy={last.y} r={2.5} fill={color} />
      )}

      {/* X-axis labels */}
      <text x={points[0].x} y={H - 4} textAnchor="middle" fontSize={9} fill="#4b5563">
        {fmtDate(views[0].view_date)}
      </text>
      <text x={last.x} y={H - 4} textAnchor="middle" fontSize={9} fill="#4b5563">
        {fmtDate(views[views.length - 1].view_date)}
      </text>
    </svg>
  );
}

// ── Rank-snapshot sparkline (fallback) ───────────────────────────────────────

function RankSparkline({ trendId }: { trendId: number }) {
  const { history, loading } = useTrendHistory(trendId);
  if (loading) return <div className="h-[80px] bg-gray-800/50 rounded-lg animate-pulse" />;

  const points = history.filter((p) => p.rank !== null) as Array<{
    captured_at: string; rank: number;
  }>;
  if (points.length < 2) return null;

  const timestamps = points.map((p) => new Date(p.captured_at).getTime());
  const minT = Math.min(...timestamps), maxT = Math.max(...timestamps);
  const tx = (ts: string) =>
    PAD.left + ((new Date(ts).getTime() - minT) / (maxT - minT || 1)) * IW;
  const ry = (r: number) => PAD.top + ((r - 1) / 9) * IH;

  const coords = points.map((p) => ({ x: tx(p.captured_at), y: ry(p.rank), ...p }));
  const line = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const rising = coords[coords.length - 1].y < coords[0].y;
  const color = rising ? "#34d399" : "#f87171";

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="block" style={{ height: H }}>
      {[1, 5, 10].map((r) => (
        <g key={r}>
          <line x1={PAD.left} x2={W - PAD.right} y1={ry(r)} y2={ry(r)}
            stroke="#1f2937" strokeWidth={1} />
          <text x={PAD.left - 4} y={ry(r) + 4} textAnchor="end" fontSize={9} fill="#4b5563">
            #{r}
          </text>
        </g>
      ))}
      <polyline points={line} fill="none" stroke={color} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" />
      {coords.map((c, i) => <circle key={i} cx={c.x} cy={c.y} r={2.5} fill={color} />)}
      <text x={coords[0].x} y={H - 4} textAnchor="middle" fontSize={9} fill="#4b5563">
        {new Date(coords[0].captured_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </text>
      <text x={coords[coords.length - 1].x} y={H - 4} textAnchor="middle" fontSize={9} fill="#4b5563">
        {new Date(coords[coords.length - 1].captured_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </text>
    </svg>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function Sparkline({ trendId, wikiTitle }: Props) {
  const { views, loading } = usePageViews(trendId);

  if (loading) {
    return <div className="h-[80px] bg-gray-800/50 rounded-lg animate-pulse" />;
  }

  const hasPageViews = views.length >= 7;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          {hasPageViews ? "Wikipedia interest" : "Rank history"}
        </p>
        {hasPageViews && wikiTitle && (
          <p className="text-xs text-gray-600 truncate max-w-[180px]">{wikiTitle}</p>
        )}
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {hasPageViews ? (
          <PageViewSparkline views={views} />
        ) : (
          <RankSparkline trendId={trendId} />
        )}
      </div>
      <p className="text-xs text-gray-600">
        {hasPageViews
          ? `Daily Wikipedia page views · last ${views.length} days`
          : `Feed rank · #1 = highest position`}
      </p>
    </div>
  );
}
