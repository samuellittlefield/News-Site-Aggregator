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
];

export function SourcesDisclosure() {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-gray-800 pt-6 mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        {open ? "▾ Hide data sources" : "▸ Show data sources"}
      </button>
      {open && (
        <div className="border border-gray-800 rounded-xl p-4 mt-3 space-y-3">
          {SOURCES.map(s => (
            <div key={s.label} className="text-xs leading-relaxed">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-semibold text-gray-300">{s.label}</span>
                <span className="text-[10px] text-gray-600 whitespace-nowrap">{s.cadence}</span>
              </div>
              <p className="text-gray-500">{s.detail}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
