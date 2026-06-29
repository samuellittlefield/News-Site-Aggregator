import { useMemo, useState } from "react";
import { DistrictData, DistrictCandidate } from "../api/client";

// ── hex geometry (pointy-top axial → pixel) ─────────────────────────────────
const SIZE = 11;
function hexCenter(q: number, r: number): [number, number] {
  return [SIZE * Math.sqrt(3) * (q + r / 2), SIZE * 1.5 * r];
}
function hexPoints(cx: number, cy: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i - 30);
    pts.push(`${(cx + SIZE * Math.cos(a)).toFixed(2)},${(cy + SIZE * Math.sin(a)).toFixed(2)}`);
  }
  return pts.join(" ");
}

// Presidential-margin (D−R) → diverging blue/red fill. Pres margins run wide,
// so the breakpoints are wider than a poll-margin scale.
function leanColor(m: number | null): string {
  if (m === null) return "#4b5563";
  if (m >= 20) return "#1e3a8a";
  if (m >= 10) return "#2563eb";
  if (m >= 3) return "#60a5fa";
  if (m > -3) return "#6b7280";
  if (m > -10) return "#f87171";
  if (m > -20) return "#dc2626";
  return "#991b1b";
}

function leanLabel(m: number | null): string {
  if (m === null) return "—";
  return m > 0 ? `D+${m.toFixed(1)}` : m < 0 ? `R+${(-m).toFixed(1)}` : "Even";
}

function partyColor(p: string | null): string {
  const x = (p || "").toUpperCase();
  if (x.startsWith("DEM")) return "#3b82f6";
  if (x.startsWith("REP")) return "#ef4444";
  return "#9ca3af";
}

function money(n: number | null): string {
  if (n === null) return "—";
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`;
  return `$${Math.round(n)}`;
}

// "Sykes, Emilia" → "Emilia Sykes" for cleaner search queries.
function searchName(name: string): string {
  const [last, ...rest] = name.split(",");
  return rest.length ? `${rest.join(" ").trim()} ${last.trim()}` : name.trim();
}
function fecUrl(fecId: string | null): string | null {
  return fecId ? `https://www.fec.gov/data/candidate/${fecId}/` : null;
}
function newsUrl(name: string, state: string): string {
  return `https://news.google.com/search?q=${encodeURIComponent(`${searchName(name)} ${state} congress`)}`;
}
function wikiUrl(name: string): string {
  return `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(searchName(name))}`;
}

function ResourceLink({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className="text-gray-500 hover:text-gray-200 transition-colors">
      {label} ↗
    </a>
  );
}

interface Props {
  districts: DistrictData[];
}

function CandidateRow({ c, max, state, openSeat }: { c: DistrictCandidate; max: number; state: string; openSeat: boolean }) {
  const w = max > 0 && c.fundraising_total ? Math.round((c.fundraising_total / max) * 100) : 0;
  const col = partyColor(c.party);
  const fec = fecUrl(c.fec_id);
  // Suppress the "inc" badge on an open seat — the sitting member isn't running.
  const showInc = c.incumbent_challenge === "I" && !openSeat;
  return (
    <div className="mb-2.5">
      <div className="flex items-center gap-1.5 text-[13px] mb-0.5">
        <span className="w-2 h-2 rounded-full flex-none" style={{ background: col }} />
        <span className="text-gray-200">{c.name}</span>
        {showInc && (
          <span className="text-[9px] uppercase tracking-wide text-gray-500 border border-gray-700 rounded px-1">inc</span>
        )}
      </div>
      <div className="flex items-center gap-2 pl-3.5">
        <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${w}%`, background: col }} />
        </div>
        <span className="text-[11px] text-gray-500 tabular-nums w-12 text-right">{money(c.fundraising_total)}</span>
      </div>
      <div className="flex items-center gap-2.5 pl-3.5 mt-1 text-[10px]">
        {fec && <ResourceLink href={fec} label="FEC" />}
        <ResourceLink href={newsUrl(c.name, state)} label="News" />
        <ResourceLink href={wikiUrl(c.name)} label="Wikipedia" />
      </div>
    </div>
  );
}

function DistrictDetail({ d }: { d: DistrictData }) {
  // Headline matchup: normally the incumbent for each party (so a primary
  // challenger who out-raised the sitting member doesn't bury them), else the
  // best-funded. But on an OPEN seat the incumbent isn't running, so we don't
  // elevate them — headline the best-funded instead (the likely nominee).
  // candidates arrive fundraising-sorted, so [0] is the top-funded.
  const dems = d.candidates.filter(c => (c.party || "").toUpperCase().startsWith("DEM"));
  const reps = d.candidates.filter(c => (c.party || "").toUpperCase().startsWith("REP"));
  const pick = (arr: DistrictCandidate[]) =>
    (d.open_seat ? undefined : arr.find(c => c.incumbent_challenge === "I")) || arr[0];
  const headline = [pick(dems), pick(reps)].filter(Boolean) as DistrictCandidate[];
  const maxRaise = Math.max(1, ...headline.map(c => c.fundraising_total || 0));
  const headlineNames = new Set(headline.map(c => c.name));
  const others = d.candidates.filter(c => !headlineNames.has(c.name));

  const ratingLabel = d.cook_rating || d.rating;
  const ratingColor = leanColor(d.pres_margin_2024);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-lg font-semibold text-white">{d.label}</span>
        <span className="text-xs font-medium" style={{ color: ratingColor }}>{leanLabel(d.pres_margin_2024)}</span>
      </div>
      <div className="text-[11px] text-gray-500 mb-3 flex items-center flex-wrap gap-x-1.5">
        <span>{ratingLabel}</span>
        {d.cook_rating && <span className="text-gray-700">· Cook</span>}
        {d.open_seat && <span className="text-amber-500/80">· Open seat</span>}
        <span className="text-gray-700">· 2026</span>
      </div>

      {d.open_seat && d.departing_incumbent && (
        <p className="text-[11px] text-gray-500 mb-3 -mt-1 leading-snug">
          <span className="text-amber-500/70">Open:</span>{" "}
          {d.departing_incumbent.name}
          {d.departing_incumbent.party ? ` (${d.departing_incumbent.party})` : ""}{" "}
          {d.departing_incumbent.reason || "is not seeking re-election"}.
        </p>
      )}

      {headline.length > 0 ? (
        <>{headline.map(c => <CandidateRow key={c.name} c={c} max={maxRaise} state={d.state} openSeat={d.open_seat} />)}</>
      ) : (
        <p className="text-[12px] text-gray-600">No major-party candidates on file yet.</p>
      )}

      {others.length > 0 && (
        <div className="mt-1">
          <p className="text-[10px] uppercase tracking-wider text-gray-600 mb-1">
            Also running ({others.length})
          </p>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5">
            {others.slice(0, 8).map(c => {
              const href = fecUrl(c.fec_id) ?? newsUrl(c.name, d.state);
              return (
                <a key={c.name} href={href} target="_blank" rel="noopener noreferrer"
                   className="text-[11px] text-gray-500 hover:text-gray-300 transition-colors">
                  <span className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle" style={{ background: partyColor(c.party) }} />
                  {c.name.split(",")[0]}
                </a>
              );
            })}
            {others.length > 8 && <span className="text-[11px] text-gray-600">+{others.length - 8} more</span>}
          </div>
        </div>
      )}

      <div className="border-t border-gray-800 my-3" />

      {d.latest_poll && d.latest_poll.margin !== null ? (
        <p className="text-[11px] text-gray-400">
          Latest poll:{" "}
          <span style={{ color: d.latest_poll.margin > 0 ? "#60a5fa" : "#f87171" }}>
            {d.latest_poll.margin > 0 ? "D" : "R"}+{Math.abs(d.latest_poll.margin).toFixed(1)}
          </span>
          {d.latest_poll.pollster ? ` · ${d.latest_poll.pollster}` : ""}
        </p>
      ) : (
        <p className="text-[11px] text-gray-600">No district polls yet — primaries ongoing.</p>
      )}
      {d.house_margin_2024 != null && (
        <p className="text-[11px] text-gray-600 mt-0.5">
          2024 House result: {leanLabel(d.house_margin_2024)}
        </p>
      )}
    </div>
  );
}

export function DistrictMap({ districts }: Props) {
  // Default-select the most competitive district (smallest |pres margin|).
  const defaultLabel = useMemo(() => {
    let best: DistrictData | null = null;
    for (const d of districts) {
      if (d.pres_margin_2024 == null) continue;
      if (!best || Math.abs(d.pres_margin_2024) < Math.abs(best.pres_margin_2024!)) best = d;
    }
    return best?.label ?? districts[0]?.label ?? null;
  }, [districts]);
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  const selectedLabel = selected ?? defaultLabel;
  const selectedD = districts.find(d => d.label === selectedLabel) ?? null;

  const { cells, viewBox } = useMemo(() => {
    const cs = districts.map(d => {
      const [cx, cy] = hexCenter(d.q, d.r);
      return { d, cx, cy };
    });
    if (cs.length === 0) return { cells: cs, viewBox: "0 0 100 100" };
    const xs = cs.map(c => c.cx), ys = cs.map(c => c.cy);
    const pad = SIZE * 1.6;
    const minX = Math.min(...xs) - pad, maxX = Math.max(...xs) + pad;
    const minY = Math.min(...ys) - pad, maxY = Math.max(...ys) + pad;
    return { cells: cs, viewBox: `${minX} ${minY} ${maxX - minX} ${maxY - minY}` };
  }, [districts]);

  if (districts.length === 0) {
    return (
      <div className="w-full rounded-xl border border-gray-800 bg-gray-900 flex items-center justify-center text-gray-600 text-sm" style={{ height: 400 }}>
        No district data
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      <div className="flex-1 min-w-0">
        <svg viewBox={viewBox} width="100%" role="img" aria-label="Hex cartogram of all 435 U.S. House districts colored by 2024 presidential lean">
          {cells.map(({ d, cx, cy }) => {
            const isSel = d.label === selectedLabel;
            const isHov = d.label === hover;
            return (
              <polygon
                key={d.label}
                points={hexPoints(cx, cy)}
                fill={leanColor(d.pres_margin_2024)}
                stroke={isSel ? "#f59e0b" : isHov ? "#e5e7eb" : "rgba(15,17,23,0.55)"}
                strokeWidth={isSel ? 2 : isHov ? 1.4 : 0.8}
                style={{ cursor: "pointer" }}
                onClick={() => setSelected(d.label)}
                onMouseEnter={() => setHover(d.label)}
                onMouseLeave={() => setHover(null)}
              >
                <title>{d.label} · {leanLabel(d.pres_margin_2024)}</title>
              </polygon>
            );
          })}
        </svg>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-[10px] text-gray-500">
          {[
            ["Safe D", "#1e3a8a"], ["Lean D", "#60a5fa"], ["Toss-up", "#6b7280"],
            ["Lean R", "#f87171"], ["Safe R", "#991b1b"],
          ].map(([label, col]) => (
            <span key={label} className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: col }} />{label}
            </span>
          ))}
          <span className="text-gray-700">· colored by 2024 presidential lean · click a district</span>
        </div>
      </div>

      <div className="lg:w-[300px] flex-none">
        {selectedD && <DistrictDetail d={selectedD} />}
      </div>
    </div>
  );
}
