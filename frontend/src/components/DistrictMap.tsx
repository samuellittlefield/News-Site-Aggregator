import { useEffect, useRef, useState } from "react";
import { DistrictData } from "../api/client";

// Deck.gl renders in a canvas — load dynamically to avoid SSR issues
// and import only what we need
let DeckGL: any = null;
let ColumnLayer: any = null;

async function loadDeck() {
  if (DeckGL) return;
  const [deckModule, layersModule] = await Promise.all([
    import("@deck.gl/react"),
    import("@deck.gl/layers"),
  ]);
  DeckGL = deckModule.default ?? deckModule.DeckGL;
  ColumnLayer = layersModule.ColumnLayer;
}

const INITIAL_VIEW = {
  longitude: -96,
  latitude: 38,
  zoom: 3.8,
  pitch: 45,
  bearing: 0,
};

const COOK_LABEL: Record<string, string> = {
  "Toss-up": "Toss-up 🟣",
  "Lean D":  "Lean D 🔵",
  "Lean R":  "Lean R 🔴",
  "Likely D":"Likely D 🔵",
  "Likely R":"Likely R 🔴",
};

interface Props {
  districts: DistrictData[];
}

export function DistrictMap({ districts }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; d: DistrictData } | null>(null);
  const [gradeFilter, setGradeFilter] = useState<"all" | "ab">("all");
  const deckRef = useRef<any>(null);

  useEffect(() => {
    loadDeck().then(() => setLoaded(true)).catch(() => {});
  }, []);

  if (!loaded || districts.length === 0) {
    return (
      <div className="w-full rounded-xl border border-gray-800 bg-gray-900 flex items-center justify-center text-gray-600 text-sm" style={{ height: 400 }}>
        {!loaded ? "Loading 3D map…" : "No district data"}
      </div>
    );
  }

  const data = districts.filter(d => gradeFilter === "all" || d.poll_count > 0);

  const layer = new ColumnLayer({
    id: "districts",
    data,
    diskResolution: 12,
    radius: 18_000,
    extruded: true,
    pickable: true,
    getPosition: (d: DistrictData) => [d.lng, d.lat],
    getElevation: (d: DistrictData) => d.height,
    getFillColor: (d: DistrictData) => d.color,
    getLineColor: [30, 30, 30],
    lineWidthMinPixels: 1,
    elevationScale: 1,
    onHover: ({ object, x, y }: any) => {
      setTooltip(object ? { x, y, d: object } : null);
    },
  });

  return (
    <div className="space-y-2">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-[10px] text-gray-600">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: "#9650a0" }} /> Purple = Toss-up</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: "#1e64dc" }} /> Blue = D lead</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: "#d01428" }} /> Red = R lead</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: "#5a5a5a" }} /> Gray = no polls yet</span>
          <span className="text-gray-700">· Height = polling intensity</span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="text-gray-600">Show:</span>
          <button
            onClick={() => setGradeFilter("all")}
            className={`px-2 py-0.5 rounded border transition-colors ${gradeFilter === "all" ? "border-gray-500 text-gray-300 bg-gray-800" : "border-gray-800 text-gray-600 hover:text-gray-400"}`}
          >
            All districts
          </button>
          <button
            onClick={() => setGradeFilter("ab")}
            className={`px-2 py-0.5 rounded border transition-colors ${gradeFilter === "ab" ? "border-gray-500 text-gray-300 bg-gray-800" : "border-gray-800 text-gray-600 hover:text-gray-400"}`}
          >
            Polled only
          </button>
        </div>
      </div>

      {/* Map */}
      <div className="relative w-full rounded-xl overflow-hidden border border-gray-800" style={{ height: 420 }}>
        <DeckGL
          ref={deckRef}
          initialViewState={INITIAL_VIEW}
          controller={true}
          layers={[layer]}
          style={{ position: "relative" }}
          parameters={{ depthTest: true }}
        >
          {/* CartoDB dark basemap tiles via plain tile layer */}
          <div
            style={{
              position: "absolute", inset: 0, zIndex: -1,
              background: "#0f1117",
            }}
          />
        </DeckGL>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute z-50 pointer-events-none bg-gray-950/95 border border-gray-700 rounded-xl p-3 space-y-1 text-xs shadow-xl"
            style={{ left: tooltip.x + 12, top: tooltip.y - 10, minWidth: 180 }}
          >
            <p className="font-bold text-white">{tooltip.d.state}-{tooltip.d.district}</p>
            <p className="text-gray-400">{COOK_LABEL[tooltip.d.cook_rating ?? ""] ?? tooltip.d.cook_rating ?? "Competitive"}</p>
            {tooltip.d.latest_margin != null ? (
              <p className={tooltip.d.latest_margin > 0 ? "text-blue-400" : "text-red-400"}>
                Latest: {tooltip.d.latest_margin > 0 ? "D" : "R"} +{Math.abs(tooltip.d.latest_margin).toFixed(1)}%
                {tooltip.d.latest_pollster ? ` (${tooltip.d.latest_pollster})` : ""}
              </p>
            ) : (
              <p className="text-gray-600">No polls yet · 2024 margin: {tooltip.d.margin_2024 != null
                ? (tooltip.d.margin_2024 > 0 ? `D+${tooltip.d.margin_2024.toFixed(1)}` : `R+${(-tooltip.d.margin_2024).toFixed(1)}`)
                : "—"}</p>
            )}
            <p className="text-gray-600">{tooltip.d.poll_count} poll{tooltip.d.poll_count !== 1 ? "s" : ""} this cycle</p>
          </div>
        )}
      </div>
    </div>
  );
}
