import { useState } from "react";

interface SourceItem {
  label: string;
  detail: string;
  cadence: string;
}

const SOURCES: SourceItem[] = [
  {
    label: "Generic ballot",
    detail: "National aggregator averages parsed from Wikipedia, plus a VoteHub sample-size-weighted live average.",
    cadence: "Wikipedia 6h · VoteHub hourly",
  },
  {
    label: "House district polls",
    detail: "Individual district polls with pollster grades (538 ratings, vendored — the live 538 feed is dead) over a Wikipedia polls database.",
    cadence: "every 6h",
  },
  {
    label: "Trump approval",
    detail: "VoteHub live rolling average of national approval polls.",
    cadence: "hourly",
  },
  {
    label: "Approval crosstabs",
    detail: "Economist/YouGov weekly tab-report PDFs with full demographic crosstabs.",
    cadence: "every 12h",
  },
  {
    label: "Control-of-Congress forecast",
    detail: "Prediction markets (Kalshi + Polymarket) for House/Senate control. Model forecasts (Silver Bulletin, Race to the WH, Split Ticket) are linked but not ingested.",
    cadence: "markets every 10m",
  },
  {
    label: "Experimental seat model",
    detail: "Our own Monte-Carlo of all 435 House + 35 Senate seats, separate from the markets. Cross-references each seat's last actual result (538 data — captures incumbency) with its 2024 presidential lean (The Downballot), swung by the live generic ballot and nudged by candidate fundraising (FEC). Uncertainty backtested on 2018–24 results. Experimental — it can disagree with the markets.",
    cadence: "recomputed per request",
  },
];

export function SourcesDisclosure() {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-ink/10 pt-6 mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs text-ink-muted hover:text-ink transition-colors"
      >
        {open ? "▾ Hide data sources" : "▸ Show data sources"}
      </button>
      {open && (
        <div className="bg-glass-panel backdrop-blur-lg border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-4 mt-3 space-y-3">
          {SOURCES.map(s => (
            <div key={s.label} className="text-xs leading-relaxed">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-semibold text-ink">{s.label}</span>
                <span className="text-[10px] text-ink-muted whitespace-nowrap">{s.cadence}</span>
              </div>
              <p className="text-ink-muted">{s.detail}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
